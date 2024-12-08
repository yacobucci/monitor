from apscheduler.schedulers.background import BackgroundScheduler
import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import logging
import sys
import urllib.parse
import urllib.request

import board
from busio import I2C
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from modules import controls
from modules import datastructures
from modules import devices
from modules import meters
from modules import metrics

logger = logging.getLogger(__name__)

def set_log_level(level: str, logger: logging.Logger):
    if level == 'debug':
        logger.setLevel(logging.DEBUG)
    elif level == 'info':
        logger.setLevel(logging.INFO)
    elif level == 'warning':
        logger.setLevel(logging.WARNING)
    elif level == 'error':
        logger.setLevel(logging.ERROR)
    elif level == 'crit':
        logger.setLevel(logging.CRITICAL)
    else:
        raise ValueError(level)

scheduler = BackgroundScheduler()
state = None

location = 'https://api.open-meteo.com/v1/forecast?'
params = {
    'latitude': 39.7592537,
    'longitude': -105.1230315,
    'current': 'pressure_msl'
}

def create_meters(i2c: I2C, state: datastructures.State,
                  ignore_addr_set: set) -> list[meters.MeterInterface]:
    objects = []
    if i2c.try_lock():
        addresses = i2c.scan()
        i2c.unlock()

        logger.info('device scan %s, ignore set %s',
                        [hex(n) for n in addresses],
                        [hex(n) for n in ignore_addr_set])

        for a in addresses:
            if a in ignore_addr_set:
                logger.debug('ignoring addr %s, filtered by ignore_addr_set argument', hex(a))
                continue

            logger.debug('setting up device address %s', hex(a))

            dev = devices.device_types[a]
            logger.debug('found device: %s', dev)

            for cap in dev.capabilities_gen():
                try:
                    m = meters.meter_factory.get_meter(dev.device_id, cap, dev, i2c, state)
                    objects.append(m)
                except ValueError as e:
                    logger.warning('name %s, board %s, capability %s - no associated ctor',
                                       dev.name, dev.device_id, cap)
    return objects

def setup_bus_devices(state: datastructures.StateInterface) -> list[meters.MeterInterface]:
    all_meters = []
    i2c = board.I2C()

    bus_devices = i2c.scan()
    logger.debug('initial scan results: %s', [hex(n) for n in bus_devices])

    if len(bus_devices) == 1:
        logger.info('single device bus, checking for multiplexer presence')

        addr = bus_devices[0]
        d = devices.device_types[addr]
        if d.is_mux():
            logger.info('multiplexer %s found at addr %s, setting up multiple channels',
                        d.name, hex(addr))

            mux = controls.mux_factory.get_mux(d.device_id, i2c)
            logger.info('multiplexer supported channels: %s', len(mux))

            for virtual_i2c in mux.channels():
                ignore_addr_set = set([ mux.address ])
                objects = create_meters(virtual_i2c, state, ignore_addr_set)
                logger.info('meters %s', meters)
                all_meters.extend(objects)
        else:
            logger.info('single device on bus, setting up meters')
            all_meters = create_meters(virtual_i2c, state, {})
    else:
        logger.info('multiple devices on bus, setting up meters')
        all_meters = create_meters(virtual_i2c, state, {})

    return all_meters

# XXX add typing information to contents argument
def open_meteo_handler(state: datastructures.StateInterface, contents) -> None:
    logger.debug('open_meteo_handler called with status %s', contents.status)

    if contents.status != 200:
        logger.warning('open_meteo_handler failed GET, using pre-set MSL')
        return

    data = contents.read()
    obj = json.loads(data)
    msl = obj['current']['pressure_msl']
    logger.debug('open_meteo_handler: acquired mean sea level pressure %s', msl)

    set_state = False
    original_msl = None
    try:
        original_msl = state.msl
        if msl != original_msl:
            logger.debug('open_meteo_handler: mean sea level pressure changed')
            set_state = True
    except:
        set_state = True
    finally:
        if set_state is True:
            logger.info('open_meteo_handler: updating mean sea level pressure from %s to %s',
                        original_msl, msl)
            state.msl = msl
        else:
            logger.debug('open_meteo_handler: no change in mean sea level pressure (%s, %s)',
                         original_msl, msl)

def url_get(state: datastructures.StateInterface, url: str, params: dict,
            handler: callable) -> None:
    endpoint = url + urllib.parse.urlencode(params)

    logger.debug('calling api endpoint %s', endpoint)
    contents = urllib.request.urlopen(endpoint)
    handler(state, contents)

def main():
    parser = argparse.ArgumentParser(description='monitor.py: I2C sensor monitor')
    parser.add_argument(
        '--log',
        help='Log file'
    )
    parser.add_argument(
        '--log-level',
        help='Log Level',
        default='debug'
    )
    parser.add_argument(
        '--prometheus',
        help='Setup a prometheus metrics endpoint',
        action=argparse.BooleanOptionalAction,
        default=False
    )
    parser.add_argument(
        '--mean-sea-level-pressure',
        help='Get OpenMeteo Mean Sea Level Pressure - calibrates altimeters',
        action=argparse.BooleanOptionalAction,
        default=False
    )
    args = parser.parse_args()

    if args.log is not None and len(args.log) > 0:
        logging.basicConfig(filename=args.log, encoding='utf-8',
                            format='%(levelname)s %(asctime)s : %(message)s')
    else:
        h = logging.StreamHandler(sys.stdout)
        f = logging.Formatter('%(levelname)s %(asctime)s : %(message)s')
        h.setFormatter(f)
        logger.addHandler(h)

    set_log_level(args.log_level, logger)

    app = Starlette(debug=True)
    state = datastructures.StarletteState(app.state)

    all_meters = setup_bus_devices(state)
    logger.debug('all devices available: %s', all_meters)

    if args.mean_sea_level_pressure:
        logger.debug('getting mean sea level pressure for startup')
        url_get(state, location, params, open_meteo_handler)

        logger.debug('setting mean sea level pressure into app: %s', state.msl)

        logger.debug('starting background scheduler')
        # XXX make interval configurable
        # XXX make scheduler global and only add job here?
        scheduler.add_job(url_get, "interval", minutes = 60, kwargs = {
            'state': state,
            'url': location,
            'params': params,
            'handler': open_meteo_handler
        }) 

    if args.prometheus is True:
        exporter = metrics.metrics_factory.get_exporter('prometheus')
        app.add_route('/metrics', exporter.export)
    state.meters = all_meters

    scheduler.start()

    config = uvicorn.Config(app, host='0.0.0.0', port=8000, log_level=args.log_level)
    server = uvicorn.Server(config)
    server.run()

if __name__ == '__main__':
    main()
