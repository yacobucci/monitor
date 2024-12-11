from apscheduler.schedulers.background import BackgroundScheduler
import argparse
import asyncio
from contextlib import asynccontextmanager
import logging
import sys

import board
from busio import I2C
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
import uvicorn

from api import metrics
from config import Config
from sensorkit import controls
from sensorkit import datastructures
from sensorkit import devices
from sensorkit import meters
from tools.getters import url_get, OpenMeteoHandler

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

def main():
    parser = argparse.ArgumentParser(description='monitor.py: I2C sensor monitor')
    parser.add_argument(
        '--config-file',
        help='Global configuration file',
        default='${HOME}/.config/sensorkit-monitor/config.yaml'
    )
    args = parser.parse_args()

    config = Config(args.config_file)

    try:
        # XXX i know this is a file, but disambiguate to stream eventually
        #    h = logging.StreamHandler(sys.stdout)
        #    f = logging.Formatter('%(levelname)s %(asctime)s : %(message)s')
        #    h.setFormatter(f)
        #    logger.addHandler(h)
        dest = config.log_destination
        level = config.log_level
        fmt = config.log_format

        logging.basicConfig(filename=dest, encoding='utf-8', format=fmt)
        set_log_level(level, logger)
    except AttributeError as e:
        print(sys.stderr, 'disabling custom logging, using defaults')
        h = logging.StreamHandler(sys.stdout)
        f = logging.Formatter('%(levelname)s %(asctime)s : %(message)s')
        h.setFormatter(f)
        logger.addHandler(h)

    app = Starlette(debug=True)
    state = datastructures.State(app.state)

    all_meters = setup_bus_devices(state)
    logger.debug('all devices available: %s', all_meters)

    try:
        #XXX parse units, so to not assume minutes
        interval = config.altimeter_calibration_interval
        #units = config.altimeter_calibration_interval_units

        logger.debug('getting mean sea level pressure for altimeter calibration')

        handler = OpenMeteoHandler()
        url_get(logger, state, location, params, handler.handle_response)
        logger.debug('calibration pressure stored: %s', state.altimeter_calibration)

        logger.debug('adding calibration job to scheduler')

        #XXX make objects so can configure with data from config
        scheduler.add_job(url_get, 'interval', minutes=interval, kwargs = {
            'logger': logger,
            'state': state,
            'url': location,
            'params': params,
            'handler': handler.handle_response
        })
    except AttributeError as e:
        logger.info('disabling altimeter calibration - %s', e)

    try:
        encoding = config.metrics_encoding
        labels = config.metrics_labels
        endpoint = config.metrics_endpoint

        exporter = metrics.metrics_factory.get_exporter(encoding)
        app.add_route(endpoint, exporter.export)
    except AttributeError as e:
        logger.info('disabling metrics exporting - %s', e)

    state.meters = all_meters

    scheduler.start()

    host = config.host
    port = config.port
    config = uvicorn.Config(app, host=host, port=port, log_level='debug')
    server = uvicorn.Server(config)
    server.run()

if __name__ == '__main__':
    main()
