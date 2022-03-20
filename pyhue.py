#!/usr/bin/env python3
import json
import math

import click

from main import Hue, DebugMode

# region setup
hue = Hue()
hue.refresh_cache(scheduled_refresh=True)
hue.debug_mode = DebugMode.CREATE_DEBUG_FILES


@click.group()
def cli():
    pass


# endregion

# region set light state and set room state
@cli.command('light')
@click.argument('light_name')
@click.option('--is-id', is_flag=True, default=False)
@click.option('--rgb', required=True, help='RGB color values', nargs=3, type=int)  # --rgb 255 0 0
@click.option('-b', '--brightness', help='Brightness of the light', default=None)
def control_light(light_name, is_id, rgb, brightness=None):
    """ Control a single Hue light """
    click.echo('Working on it...')

    light_id = light_name
    if not is_id:
        light = hue.get_light_by_name(name=light_name)
        if light is None:
            click.echo(f'Unable to find light with name \'{light_name}\'! Have you refreshed the cache after renaming?')
            exit()
        light_id = light['id']

    print(light_id)

    hue.set_light_state(light_id=light_id, rgb=rgb, on_state=True, brightness=brightness)
    click.echo('Done!')


@cli.command('room')
@click.argument('room_name')
@click.option('--is-id', is_flag=True, default=False)
@click.option('--rgb', required=True, help='RGB color values', nargs=3, type=int)  # --rgb 255 0 0
@click.option('-b', '--brightness', help='Brightness of the light', default=None)
def control_room(room_name, is_id, rgb, brightness=None):
    """ Control all the lights in a room """
    click.echo('Working on it...')

    room_id = room_name
    if not is_id:
        room_id = hue.get_light_setup_id_by_name(room_name)
        if room_id is None:
            click.echo(f'Unable to find light with name \'{room_name}\'!')
            exit()

    hue.set_room_light_states(room_id=room_id, rgb=rgb, brightness=brightness)
    click.echo('Done!')


# endregion

# region caching-related commands
@cli.command('refresh-cache')
@click.option('-d', '--device', is_flag=True, default=False)
@click.option('-r', '--rooms', is_flag=True, default=False)
@click.option('-s', '--scenes', is_flag=True, default=False)
@click.option('-l', '--lights', is_flag=True, default=False)
@click.option('-w', '--wipe', is_flag=True, default=False)
def refresh_cache(device, rooms, scenes, lights, wipe):
    """ Refresh the existing cache """

    if not device and not rooms and not rooms:
        click.echo('Nothing to refresh. Specify what you want to refresh with --rooms, --device and/or --scenes.'
                   '\n\'pyhue refresh-cache --help\' for more help')

    hue.refresh_cache(refresh_rooms=rooms, refresh_device=device, refresh_scenes=scenes, refresh_lights=lights,
                      wipe=wipe, log=click.echo)


# endregion

# region DEPRECATED SETUP
@cli.command('add-setup-entry', deprecated=True)
@click.option('-l', '--for-light', prompt='Is this for a light? (False if it is for a room)', is_flag=True, type=bool)
@click.option('-n', '--name', prompt='What do you want to name the device?', help='The lamps name')
@click.option('--rid', prompt='What rid does the device currently have? (You can check with pyhue ls)',
              help='The lamps rid')
def add_setup_entry(for_light, name, rid):
    """ Add an entry to the named setup file """
    raise DeprecationWarning()
    # existing_setup = hue.load_light_setup()
    #
    # new_setup = {
    #     'rooms': [],
    #     'lights': [],
    # }
    # if existing_setup is not None:
    #     new_setup = existing_setup
    #
    # for device in new_setup['lights' if for_light else 'rooms']:
    #     if device['name'].lower() == name.lower():
    #         print(
    #             f'Name \'{name}\' is already in use by another device. Consider changing the name or removing the other entry!')
    #         exit()
    #
    # new_setup['lights' if for_light else 'rooms'].append({
    #     'name': name,
    #     'rid': rid,
    # })
    #
    # hue.save_light_setup(json.dumps(new_setup))
    #
    # click.echo(f'\nAdded device with rid \'{rid}\' and name \'{name}\' successfully!')


@cli.command('remove-setup-entry', deprecated=True)
@click.option('-l', '--for-light', prompt='Is this for a light? (False if it is for a room)', type=bool)
@click.option('--rid', prompt='What rid does the device currently have? (You can check with pyhue ls)',
              help='The lamps rid')
def remove_setup_entry(for_light, rid):
    """ Remove an entry from the named setup file """
    raise DeprecationWarning()

    # existing_setup = hue.load_light_setup()
    # if existing_setup is None:
    #     click.echo('There was no setup file. Created one for you')
    #     exit()
    #
    # new_setup = existing_setup
    # del_index: int | None = None
    #
    # for (i, device) in enumerate(new_setup['lights' if for_light else 'rooms']):
    #     if device['rid'] == rid:
    #         del_index = i
    #
    # if del_index is None:
    #     click.echo(f'Couldn\'t find entry in list for rid \'{rid}\'')
    #     exit()
    #
    # new_setup['lights' if for_light else 'rooms'].pop(del_index)
    # hue.save_light_setup(json.dumps(new_setup))
    #
    # click.echo(f'\nRemoved device with rid \'{rid}\' successfully!')


# endregion

# region ls and rn commands
@cli.command('ls')
@click.option('-l', '--long', help='A more human-readable way of displaying', is_flag=True, default=False)
@click.option('-t', '--type', help='List with type of device (room/light)', is_flag=True, default=False)
@click.option('-n', '--names', help='List with names', is_flag=True, default=False)
@click.option('-i', '--ids/--no-ids', help='List with/without the ids', default=False)
@click.option('-r', '--rooms', help='List rooms', is_flag=True, default=False)
@click.option('-L', '--no-lights', help='Do not list the lights', is_flag=True, default=False)
@click.option('-C', '--no-cache', help='Do not get the info out of the cache', is_flag=True, default=False)
def list_lights(long, type, names, ids, rooms, no_lights, no_cache):
    """ List all the lights and or rooms """
    responses = {
        'rooms': hue.get_rooms(cached=not no_cache) if rooms else None,
        'lights': hue.get_lights(cached=not no_cache) if not no_lights else None,
    }

    if not long and not names and not ids:
        ids = True

    for key in responses:
        device_data = responses[key]
        if device_data is None:
            continue

        for device in device_data:
            message = ''
            if type:
                message += f'{"room " if key == "rooms" else "light"} '

            message += device['id'] if ids else ''

            if names:
                message += f'{" " if ids else ""}{device["metadata"]["name"]}'

            click.echo(message)


@cli.command('rn', deprecated=True)
@click.argument('id')
@click.argument('new_name')
@click.option('-r', '--room/--light', default=False)
def rename_light(id, new_name, room):
    """ Rename a room/light """
    print('Sorry. At the current state of the v2 API, api clients are not allowed to rename Hue lights/rooms.'
          ' This might never be a feature.\nInstead, you can do it via the Android/iOS app!')
    #
    # if len(new_name) > 32 or len(new_name) <= 1:
    #     click.echo('New name has to be between 1 and 32 characters!')
    #     exit()
    #
    # if room:
    #     click.echo('Sorry. This is not implemented yet in the official Hue API that this software uses.')
    #     exit()
    #
    # hue.rename_light_or_room(id, new_name, room)


# endregion

if __name__ == '__main__':
    cli()
