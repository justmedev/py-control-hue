import datetime
import json
import os
from enum import Enum

import requests as requests
import urllib3

from time import sleep
from os import path
from colormath.color_conversions import convert_color
from colormath.color_objects import sRGBColor, xyYColor
from requests import Response
from urllib3.exceptions import InsecureRequestWarning
from config import full_path

urllib3.disable_warnings(category=InsecureRequestWarning)


class DebugMode(Enum):
    OFF = 0
    CREATE_DEBUG_FILES = 1


class Hue:
    bridge_api_url = None
    bridge_clip_url = None
    user = None
    api_key = None
    api_username = None
    debug_mode = DebugMode.OFF
    json_file_dir = full_path + 'data'

    def __init__(self, ipaddr: str | None = None, auto_connect: bool = True):
        self.try_load_config()
        if self.bridge_api_url and self.bridge_clip_url:
            return

        if ipaddr is not None:
            self.bridge_api_url = f'http://{ipaddr}/api'
            self.bridge_clip_url = f'https://{ipaddr}/clip/v2'

            self.save_config()
            return

        res = requests.get('https://discovery.meethue.com')
        if res.status_code == 200:
            self.bridge_api_url = f'http://{res.json()[0]["internalipaddress"]}/api'
            self.bridge_clip_url = f'https://{res.json()[0]["internalipaddress"]}/clip/v2'

            self.save_config()
        else:
            print('Something went wrong trying to connect to https://discovery.meethue.com!')

        if auto_connect:
            self.link()

    def link(self, force=False):
        if not force and self.api_key and self.api_username:
            return

        if self.bridge_api_url is None or self.bridge_clip_url is None:
            print('Bridge api client connection failed to initialize properly.')
            return

        req_body = {
            'devicetype': 'PyHueController#justmedev',
            'generateclientkey': True,
        }
        res = requests.post(self.bridge_api_url, json=req_body).json()[0]
        if 'error' in res:
            if res['error']['type'] == 101:
                print('Press the link button on your Hue bridge and try again.')
                exit()

        self.api_username = res['success']['username']
        self.api_key = res['success']['clientkey']

        self.save_config()
        print('Successfully connected to the Hue bridge.')

    # region CLIP API v2 request and writing responses to a file
    def write_response_to_file(self, response: Response):
        if self.debug_mode != DebugMode.CREATE_DEBUG_FILES:
            return

        json_str = json.dumps({
            'req': {
                'method': response.request.method,
                'url': response.request.url,
                'headers': str(response.request.headers),
                'body': response.request.body,
            },
            'res': {
                'status_code': response.status_code,
                'url': response.url,
                'headers': str(response.headers),
                'body': str(response.content),
                'cookies': str(response.cookies),
                'elapsed': str(response.elapsed),
                'history': str(response.history),
            }
        }, indent=2)

        with open(f'{self.json_file_dir}/response_log.json', 'w+') as file:
            file.write(json_str)

        with open(f'{self.json_file_dir}/raw_response.json', 'w+') as file:
            try:
                file.write(json.dumps(response.json()))
            except TypeError:
                pass

    def clip_request(self, method: str,
                     path: str,
                     data: str | None = None,
                     headers: dict | None = None,
                     verify_ssl_cert: bool = False,
                     api_key_header: bool = True,
                     log_response_to_file: bool = True):
        if data is None and method != 'GET':
            print(f'Method \'{method}\' needs a \'data\' argument!')
            exit(1)

        if headers is None:
            headers = {}
        if api_key_header:
            headers['hue-application-key'] = self.api_username

        response = requests.request(method,
                                    url=f'{self.bridge_clip_url}{path}',
                                    headers=headers,
                                    data=data,
                                    verify=verify_ssl_cert)
        if log_response_to_file:
            self.write_response_to_file(response)

        return (
            response,
            len(response.json()['errors']) > 0,
        )

    # endregion

    # region Load/Save to config file
    def try_load_config(self):
        if not path.exists(f'{self.json_file_dir}/api_config.json'):
            return

        with open(f'{self.json_file_dir}/api_config.json', 'r') as f:
            data = json.loads(f.read())

            self.api_username = data['api_username']
            self.api_key = data['api_key']
            self.bridge_api_url = data['bridge_api_url']
            self.bridge_clip_url = data['bridge_clip_url']

    def save_config(self):
        with open(f'{self.json_file_dir}/api_config.json', 'w+') as f:
            data = {
                'api_username': self.api_username,
                'api_key': self.api_key,
                'bridge_api_url': self.bridge_api_url,
                'bridge_clip_url': self.bridge_clip_url,
            }

            f.write(json.dumps(data))

    def save_light_setup(self, json_str: str):
        raise DeprecationWarning()
        # with open(f'{self.json_file_dir}/light_setup.json', 'w+') as file:
        #     file.write(json_str)

    def load_light_setup(self):
        raise DeprecationWarning()
        # if not path.exists(f'{self.json_file_dir}/light_setup.json'):
        #     return None
        #
        # with open(f'{self.json_file_dir}/light_setup.json', 'r') as file:
        #     return json.loads(file.read())

    def get_light_setup_id_by_name(self, name: str, device_type: str = 'lights'):
        raise DeprecationWarning()
        # setup = self.load_light_setup()
        # for device in setup[device_type]:
        #     if device['name'].lower() == name.lower():
        #         return device['rid']
        #
        # return None

    # endregion

    # region Cashing
    def refresh_cash(self, refresh_rooms: bool = False, refresh_device: bool = False, refresh_scenes: bool = False,
                     wipe: bool = False, log=lambda x: x, scheduled_refresh: bool = True):
        """
        Refresh the cash.json file to reflect changes
        :param refresh_rooms: Collect data of all the rooms
        :param refresh_device: Collect the device specific data; Also collects light infos
        :param refresh_scenes: Collect data of all the scenes
        :param wipe: Delete the existing file and completely rewrite it
        :param log: Specify a log function (If empty: No log is shown)
        :param scheduled_refresh: if True, will check last_updated and only update if necessary
        """
        file_path = f'{self.json_file_dir}/cash.json'
        existing_cash = {
            'last_updated': -1,
            'device': {},
            'lights': [],
            'rooms': [],
            'scenes': [],
        }

        if path.exists(file_path):
            if wipe:
                log('Deleting/Wiping existing cash...')
                os.remove(file_path)
            else:
                log('Reading existing cash...')
                with open(file_path, 'r') as file:
                    existing_cash = json.loads(file.read())

        # 7200 = 3600 * 2 (two hours)
        if scheduled_refresh and datetime.datetime.utcnow().timestamp() - 7200 >= existing_cash['last_updated']:
            print('The cash hasn\'t been refreshed in a while. Refreshing it now...\n')

            refresh_device = True
            refresh_rooms = True
            refresh_scenes = True
        else:
            return

        existing_cash['last_updated'] = datetime.datetime.utcnow().timestamp()

        if refresh_device:
            log('Collecting device and light infos...')
            device_info = self.get_device_info(cashed=False)
            existing_cash['device'] = device_info['data'][0]
            existing_cash['lights'] = device_info['data'][1:]
            sleep(0.2)

        if refresh_rooms:
            log('Collecting room infos')
            existing_cash['rooms'] = self.get_rooms(cashed=False)['data']
            sleep(0.2)

        if refresh_scenes:
            log('Collecting scene infos')
            existing_cash['scenes'] = self.get_scenes(cashed=False)['data']
            sleep(0.2)

        log('Writing results to file...')
        with open(file_path, 'w+') as file:
            file.write(json.dumps(existing_cash))

        log('Done')

    def get_from_cash(self, key: str):
        file_path = f'{self.json_file_dir}/cash.json'

        if path.exists(file_path):
            with open(file_path, 'r') as file:
                return json.loads(file.read())[key]
        return None

    # endregion

    # region GET: Light, rooms, scenes and Device info
    def get_device_info(self, cashed: bool = True):
        if cashed:
            cashed_res = self.get_from_cash('device')
            if cashed_res is not None:
                return cashed_res

        (res, failed) = self.clip_request('GET', '/resource/device')
        if failed:
            print('unable to get device info!')
            return

        return res.json()['data']

    def get_lights(self, cashed: bool = True):
        if cashed:
            cashed_res = self.get_from_cash('lights')
            if cashed_res is not None:
                return cashed_res

        (res, failed) = self.clip_request('GET', '/resource/light')
        if failed:
            print('Something went wrong trying to get the lights.')
            return

        return res.json()['data']

    def get_scenes(self, cashed: bool = True):
        if cashed:
            cashed_res = self.get_from_cash('scenes')
            if cashed_res is not None:
                return cashed_res

        (res, failed) = self.clip_request('GET', '/resource/scene')
        if failed:
            print('Something went wrong trying to get the scenes.')
            return

        return res.json()['data']

    def get_rooms(self, cashed: bool = True):
        if cashed:
            cashed_res = self.get_from_cash('rooms')
            if cashed_res is not None:
                return cashed_res

        (res, failed) = self.clip_request('GET', '/resource/room')
        if failed:
            print('Something went wrong trying to get the rooms.')
            return

        return res.json()['data']

    # endregion

    # region SET: Light, Room light states and rename lights/rooms
    def set_light_state(self, light_id: str, rgb: tuple[int, int, int], on_state: bool = True,
                        brightness: int | None = None):
        xyy_color = convert_color(sRGBColor(*rgb), xyYColor)

        req_data = {
            'on': {
                'on': on_state,
            },
            'color': {
                'xy': {
                    'x': xyy_color.xyy_x,
                    'y': xyy_color.xyy_y,
                },
            },
            'dimming': {},
        }

        if brightness is not None:
            req_data['dimming']['brightness'] = brightness

        (res, failed) = self.clip_request('PUT', f'/resource/light/{light_id}', json.dumps(req_data))
        if failed:
            print('CLIP Req to set_light_state failed.')
            return

    def set_room_light_states(self, room_id: str, rgb: tuple[int, int, int], brightness: int | None = None):
        (res, failed) = self.clip_request('GET', f'/resource/room/{room_id}')
        if failed:
            print(f'Something went wrong trying to get information for room {room_id}'
                  f'while executing set_room_light_states!')
            return

        for service in res.json()['data'][0]['services']:
            if service['rtype'] == 'light':
                self.set_light_state(service['rid'], rgb, True, brightness)
                sleep(0.2)

    def rename_light_or_room(self, id: str, new_name: str, room: bool = False):
        print('This doesn\'t seem to work with the Hue API.')
        if len(new_name) > 32 or len(new_name) <= 1:
            return None

        data = {
            'metadata': {
                'name': new_name
            }
        }
        self.clip_request('PUT', f'/resource/{"room" if room else "light"}/{id}', json.dumps(data))
    # endregion


if __name__ == '__main__':
    hue = Hue()
    lights = hue.get_lights()

    for light in lights['data']:
        print(light['metadata']['name'])

    # hue.set_light_state('f3be19b5-aaed-48e1-8c8e-018af99a16c9', 0, 0, 255, True, brightness=50)
    # hue.set_room_light_states('5dff10b4-d410-44d2-9120-72b8f6fa4ea7', 0, 255, 0)
