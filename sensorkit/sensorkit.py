from importlib import import_module
import logging
from typing import Any

from busio import I2C

from .calibration import Calibration
from .config import Config
from .constants import (to_capabilities,
                        to_device_type,
                        to_device_ids,
                        VIRTUAL,
)
from .datastructures import Store
from .devices import device_factory, DeviceInterface
from .devicetree import DeviceTree

logger = logging.getLogger(__name__)

class SensorKit:
    def __init__(self, bus: I2C, config: dict[str, Any], scheduler,
                 store: dict[str, Any] | None = None):
        self._bus = bus
        self._config = Config(config)

        self._store = Store(store)
        self._store.tree = DeviceTree(bus)
        self._store.tree.build(self._store)
        self._scheduler = scheduler

        self._static_args = {
            'store': self._store,
            'scheduler': self._scheduler,
        }

        self._virtual_devices = self._config.virtual_devices
        for dev in self._virtual_devices:
            conf = self._virtual_devices[dev]
            objs = self._instantiate_device(conf)

            for d in objs:
                self._store.tree.add(dev, d, (to_device_type[conf['type']] | VIRTUAL))

        calibrations = self._config.calibrations
        self._build_calibrations(calibrations)

    def _build_calibrations(self, calibrations) -> None:
        for c in calibrations:
            for d in self._store.tree.devices_iter(lambda node: node.obj.board == to_device_ids[c]):
                for conf in calibrations[c]:
                    target = conf['target']
                    source = conf['source']
                    def __filter(node):
                        name = source['device']
                        measurement = conf['measurement']
    
                        if node.name == name:
                            if to_capabilities[measurement] == node.obj.measurement:
                                return True
                        return False
                    sources = self._store.tree.findall(__filter)
                    cobj = Calibration(c, conf, d, sources, self._store, self._scheduler)
                    cobj.start(True)

    def _instantiate_device(self, config: dict[str, Any]) -> DeviceInterface:
        module = import_module(config['module'], package='sensorkit')

        builder_name = config['builder']
        builder = getattr(module, builder_name)
        build_obj = builder(config['capabilities'])

        args = { **self._static_args, **config['args'] }
        objects = build_obj(**args)

        return objects
