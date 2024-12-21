import logging
from collections.abc import Iterator
from typing import Any

from anytree import Node, PreOrderIter
from anytree.search import find
import board
from busio import I2C

from . import constants
from . import controls
from . import datastructures
from . import devices
from . import meters
from . import profiles

logger = logging.getLogger(__name__)

ROOT = constants.NONE

ROOT_NAME      = 'root'
VIRTUAL_NAME   = 'virtual-bus'
I2C_NAME       = 'i2c-bus'

class Metadata:
    def __init__(self, device_type: int):
        self._device_type = device_type

    @property
    def is_root(self) -> bool:
        return self._device_type == constants.NONE

    @property
    def is_physical(self) -> bool:
        return not bool(self._device_type & constants.VIRTUAL)

    @property
    def is_virtual(self) -> bool:
        return bool(self._device_type & constants.VIRTUAL)
        
    @property
    def is_bus(self) -> bool:
        return bool(self._device_type & constants.BUS)

    @property
    def is_virtual_bus(self) -> bool:
        typ = self._device_type
        return bool(typ & constants.BUS) and bool(typ & constants.VIRTUAL)

    @property
    def is_mux(self) -> bool:
        return bool(self._device_type & constants.MUX)

    @property
    def is_channel(self) -> bool:
        return bool(self._device_type & constants.CHANNEL)

    @property
    def is_device(self) -> bool:
        return bool(self._device_type & constants.DEVICE)

    @property
    def is_virtual_device(self) -> bool:
        typ = self._device_type
        return bool(typ & constants.DEVICE) and bool(typ & constants.VIRTUAL)

    @property
    def is_meter(self) -> bool:
        return bool(self._device_type & constants.METER)

    @property
    def is_virtual_meter(self) -> bool:
        typ = self._device_type
        return bool(typ & constants.METER) and bool(typ & constants.VIRTUAL)

    @property
    def is_detector(self) -> bool:
        return bool(self._device_type & constants.DETECTOR)

class DeviceTree:
    def __init__(self, i2c: I2C):
        self._i2c = i2c

        self._root = Node(ROOT_NAME, obj=None, metadata=Metadata(ROOT))
        self._i2c_bus = Node(I2C_NAME, parent=self._root, obj=self._i2c,
                             metadata=Metadata(constants.BUS))
        # /virtual-bus/
        #             |- {name}
        #             |- {name}
        self._virtual_bus = Node(VIRTUAL_NAME, parent=self._root, obj=None,
                                 metadata=Metadata(constants.BUS | constants.VIRTUAL))

    def build(self, store: datastructures.Store) -> None:
        self._build_tree(self._i2c, self._i2c_bus, store)

    # Helper to find meters, common use case
    def meters_iter(self, _filter = None) -> Iterator[meters.MeterInterface]:
        if _filter is not None and not callable(_filter):
            raise TypeError('_filter argument must be callable or None')

        def __decorate_filter(_filter = None):
            def __filter(node: Node) -> bool:
                meta = getattr(node, 'metadata', None)
                if meta is not None:
                    is_returnable = meta.is_meter
                    if is_returnable and _filter is not None and callable(_filter):
                        is_returnable = is_returnable and _filter(node)
                    return is_returnable
                return False
            return __filter

        for node in PreOrderIter(self._root, __decorate_filter(_filter)):
            yield node.obj

    def measurement_iter(self, measurement: int) -> Iterator[meters.MeterInterface]:
        def __filter(node: Node) -> bool:
            if hasattr(node, 'obj'):
                obj = node.obj
                if measurement == obj.measurement:
                    return True
            return False

        for m in self.meters_iter(__filter):
            yield m

    def measurement_by_board_iter(self, measurement: int,
                                  board: int) -> Iterator[meters.MeterInterface]:
        def __filter(node: Node) -> bool:
            if hasattr(node, 'obj'):
                obj = node.obj
                if measurement == obj.measurement and board == obj.board:
                    return True
            return False

        for m in self.meters_iter(__filter):
            yield m

    def devices_iter(self, _filter = None) -> Iterator[devices.DeviceInterface]:
        if _filter is not None and not callable(_filter):
            raise TypeError('_filter argument must be callable or None')

        def __decorate_filter(_filter = None):
            def __filter(node: Node) -> bool:
                meta = getattr(node, 'metadata', None)
                if meta is not None:
                    is_returnable = meta.is_device
                    if is_returnable and _filter is not None and callable(_filter):
                        is_returnable = is_returnable and _filter(node)
                    return is_returnable
                return False
            return __filter

        for node in PreOrderIter(self._root, __decorate_filter(_filter)):
            yield node.obj

    def devices_by_board_iter(self, board: int) -> Iterator[devices.DeviceInterface]:
        def __filter(node: Node) -> bool:
            if hasattr(node, 'obj'):
                obj = node.obj
                if board == obj.board:
                    return True
            return False

        for d in self.devices_iter(__filter):
            yield d

    # General purpose filtered iterator
    def filtered_iter(self, _filter: callable) -> Iterator[Any]:
        def __decorate_filter(_filter = None):
            def __filter(node: Node) -> bool:
                return _filter(node)
            return __filter

        for node in PreOrderIter(self._root, __decorate_filter(_filter)):
            yield node.obj

    # simple wrapper for anytree
    def findall(self, filter_=None):
        from anytree import findall as anytree_findall
        found = anytree_findall(self._root, filter_)
        objects = list()
        for f in found:
            objects.append(f.obj)
        return objects

    # XXX puke, need to add some logging, but keeping the print template for now
    def add(self, name, obj, typ, **kwargs) -> Node:
        #print('DEBUG {}'.format(type(obj)))
        #print('DEBUG {} is a {} {}'.format(type(obj), meters.Meter,
        #                                   issubclass(type(obj), meters.Meter)))
        #print('DEBUG {} is a {} {}'.format(type(obj), meters.MeterInterface,
        #                                   issubclass(type(obj), meters.MeterInterface)))
        #print('DEBUG {} is a {} {}'.format(type(obj), devices.DeviceInterface,
        #                                   issubclass(type(obj), devices.DeviceInterface)))
        #print('DEBUG {} has a {} {}'.format(type(obj), '_device', hasattr(obj, '_device')))
        #print('DEBUG {} has a {} {}'.format(type(obj), devices.VirtualDevice,
        #                                    #issubclass(type(obj._device), devices.VirtualDevice)))
        #                                    isinstance(obj._device, devices.VirtualDevice)))
        #print('DEBUG {} has a {} {}'.format(type(obj), devices.Bmp390,
        #                                    #issubclass(type(obj._device), devices.Bmp390)))
        #                                    isinstance(obj._device, devices.Bmp390)))

        # XXX right now only supporting virtual or i2c, needs more work when bus is 
        # abstracted away and there are multiple physical buses
        if hasattr(obj, '_device') is False:
            raise ValueError('cannot determine if {} is physical or virtual'.format(obj))
        if isinstance(obj._device, devices.VirtualDevice):
            parent = self._virtual_bus
            typ = constants.VIRTUAL
        else:
            parent = self._i2c_bus
            typ = NONE

        if issubclass(type(obj), meters.MeterInterface):
            typ = typ | constants.METER
        elif issubclass(type(obj), controls.MuxInterface):
            typ = typ | constants.MUX
        elif issubclass(type(obj), devices.DeviceInterface):
            typ = typ | constants.DEVICE
        else:
            m = 'unsupported type, must be one of MeterInterface, MuxInterface, or DeviceInterface'
            raise ValueError(m)

        #print('DEBUG is_virtual {}'.format(bool(typ & constants.VIRTUAL)))
        #print('DEBUG is_meter {}'.format(bool(typ & constants.METER)))
        #print('DEBUG is_mux {}'.format(bool(typ & constants.MUX)))
        #print('DEBUG is_device {}'.format(bool(typ & constants.DEVICE)))

        n = Node(name, parent=self._virtual_bus, obj=obj, metadata=Metadata(typ), **kwargs)
        return n

    def _build_tree(self, i2c, parent, store: datastructures.Store, addr_filter: set = set()):
        try:
            if i2c.try_lock():
                devs = i2c.scan()
            i2c.unlock()
        except AttributeError:
            devs = i2c.scan()

        logger.debug('initial scan results: %s',
                     [hex(n) for n in devs],
                     [hex(n) for n in addr_filter])

        devs = [n for n in devs if n not in addr_filter]

        for addr in devs:
            logger.info('building node for address: %s', addr)

            d = profiles.profiles[addr]

            self._build_node(i2c, addr, d, parent, store)

    def _build_node(self, i2c, address, profile, parent, store: datastructures.Store):
        if profile.is_mux():
            logger.info('multiplexer %s found at addr %s, setting up multiple channels',
                        profile.name, hex(address))

            mux = controls.mux_factory.get_mux(i2c, profile.name, profile.device_id,
                                               profile.capabilities, address)
            logger.info('multiplexer supported channels: %s', len(mux))

            node = Node(address, parent=parent, obj=mux,
                        metadata=Metadata(constants.MUX))
            
            def channel_bus(channel) -> int:
                r = 0
                if 'channel_switch' in channel.__dict__:
                    n = int.from_bytes(channel.channel_switch, 'little')
                    while n > 1:
                        n = n >> 1
                        r = r + 1
                return r
            for channel in mux.channels():
                chan = Node(channel_bus(channel), parent=node, obj=channel,
                            metadata=Metadata(constants.CHANNEL))
                addr_set = set()
                addr_set.add(mux.address)
                self._build_tree(channel, chan, store, addr_set)
        else:
            dev = devices.device_factory.get_device(i2c, profile.name, profile.device_id,
                                                    profile.capabilities, address)
            node = Node(address, parent=parent, obj=dev,
                        metadata=Metadata(constants.DEVICE))
            self._build_leaves(i2c, address, dev, node, store)

    def _build_leaves(self, i2c, address, device, parent, store: datastructures.Store):
        # XXX only do this for meters, eventually need to discriminate with detectors
        for cap in device.capabilities_gen():
            try:
                m = meters.meter_factory.get_meter(cap, device, store)
                leaf = Node(constants.to_capability_strings[cap], parent=parent, obj=m,
                            metadata=Metadata(constants.METER))
            except ValueError as e:
                logger.warning('name %s, board %s, capability %s - no ctor',
                               profile.name, profile.device_id, cap)
