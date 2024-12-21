import abc
from collections.abc import Iterator

import adafruit_bmp3xx
import adafruit_scd4x
import adafruit_sht4x
import adafruit_veml7700
from busio import I2C

from . import constants
from . import profiles

class DeviceInterface(metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'real_device') and
                callable(subclass.real_device) or
                NotImplemented)

    @abc.abstractmethod
    def address(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def board(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abc.abstractmethod
    def capabilities(self) -> list[int]:
        raise NotImplementedError

    @abc.abstractmethod
    def capabilities_gen(self) -> Iterator[int]:
        raise NotImplementedError

    @abc.abstractmethod
    def bus(self) -> I2C:
        raise NotImplementedError

    @abc.abstractmethod
    def bus_id(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def real_device(self):
        raise NotImplementedError

class Device(DeviceInterface):
    def __init__(self, bus: I2C | None, name: str, board: int, capabilities: list[int],
                 address: int):
        self._bus = bus
        self._name = name
        self._board = board
        self._caps = capabilities
        self._address = address

    @property
    def address(self) -> int | str:
        return self._address

    @property
    def board(self) -> int:
        return self._board

    @property
    def name(self) -> str:
        return self._name

    @property
    def capabilities(self) -> list[int]:
        return self._caps

    def capabilities_gen(self) -> Iterator[int]:
        for cap in self._caps:
            yield cap

    @property
    def bus(self) -> I2C:
        return self._bus

    @property
    def bus_id(self) -> int:
        r = 0
        if self._bus is not None and 'channel_switch' in self._bus.__dict__:
            n = int.from_bytes(self._bus.channel_switch, 'little')
            while n > 1:
                n = n >> 1
                r = r + 1
        return r

class VirtualDevice(Device):
    def __init__(self, name: str, board: int, capabilities: list[int],
                 address: int = constants.VIRTUAL_ADDR):
        super().__init__(None, name, board, capabilities, address)
    
    @property
    def real_device(self):
        return None

class Bmp390(Device):
    def __init__(self, bus: I2C, name: str, board: int, capabilities: list[int],
                 address: int = 119):
        super().__init__(bus, name, board, capabilities, address)
        self._bmp = adafruit_bmp3xx.BMP3XX_I2C(bus, address)

    @property
    def real_device(self):
        return self._bmp

class Sht41(Device):
    def __init__(self, bus: I2C, name: str, board: int, capabilities: list[int],
                 address: int = 68):
        super().__init__(bus, name, board, capabilities, address)
        self._sht = adafruit_sht4x.SHT4x(bus, address)

    @property
    def real_device(self):
        return self._sht

class Veml7700(Device):
    def __init__(self, bus: I2C, name: str, board: int, capabilities: list[int],
                 address: int = 16):
        super().__init__(bus, name, board, capabilities, address)
        self._veml7700 = adafruit_veml7700.VEML7700(bus, address)

    @property
    def real_device(self):
        return self._veml7700

class Scd41(Device):
    def __init__(self, bus: I2C, name: str, board: int, capabilities: list[int],
                 address: int = 98):
        super().__init__(bus, name, board, capabilities, address)
        self._scd = adafruit_scd4x.SCD4X(bus, address)

    @property
    def real_device(self):
        return self._scd

class DeviceFactory:
    def __init__(self):
        self._ctors = {}

    def register_device(self, board, ctor):
        self._ctors[board] = ctor

    def get_device(self, bus: I2C, name: str, board: int, capabilities: list[int],
                   address: int) -> DeviceInterface:
        ctor = self._ctors.get(board)
        if not ctor:
            raise ValueError(board)

        return ctor(bus, name, board, capabilities, address)

device_factory = DeviceFactory()
device_factory.register_device(constants.BMP390, Bmp390)
device_factory.register_device(constants.SHT41, Sht41)
device_factory.register_device(constants.VEML7700, Veml7700)
device_factory.register_device(constants.SCD41, Scd41)
