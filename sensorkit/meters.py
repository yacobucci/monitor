import abc
from collections.abc import Iterator
import typing

from busio import I2C

from . import datastructures
from . import devices
from .constants import (TEMPERATURE,
                        PRESSURE,
                        ALTITUDE,
                        RELATIVE_HUMIDITY,
                        CO2,
                        LUX,
                        AMBIENT_LIGHT,
                        CELSIUS_UNITS,
                        HECTOPASCAL_UNITS,
                        METER_UNITS,
                        PERC_RELATIVE_HUMIDITY_UNITS,
                        AMBIENT_LIGHT_UNITS,
                        LUX_UNITS,
                        PPM_UNITS,
                        BMP390,
                        SHT41,
                        VEML7700,
                        SCD41,
)

class MeterInterface(devices.DeviceInterface, metaclass=abc.ABCMeta):
    @classmethod
    def __subclasshook__(cls, subclass):
        return (hasattr(subclass, 'measure') and
                callable(subclass.measure) and
                hasattr(subclass, 'measurement') and
                callable(subclass.measurement) and
                hasattr(subclass, 'units') and
                callable(subclass.units) or
                NotImplemented)

    @abc.abstractmethod
    def measure(self) -> float:
        raise NotImplementedError

    @abc.abstractmethod
    def measurement(self) -> int:
        raise NotImplementedError

    @abc.abstractmethod
    def units(self) -> str:
        raise NotImplementedError

class Meter(MeterInterface):
    def __init__(self, device):
        self._device = device

    @property
    def address(self) -> int:
        return self._device.address

    @property
    def board(self) -> int:
        return self._device.board

    @property
    def name(self) -> str:
        return self._device.name

    @property
    def capabilities(self) -> list[int]:
        return self._device.capabilities

    @property
    def capabilities_gen(self) -> Iterator[int]:
        for cap in self._device.capabilities:
            yield cap

    @property
    def bus(self) -> I2C:
        return self._device.bus

    @property
    def bus_id(self) -> int:
        return self._device.bus_id

#
# BMP390 based measurements
class Bmp390Temperature(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        bmp = self._real_device
        return bmp.temperature

    @property
    def measurement(self) -> int:
        return TEMPERATURE

    @property
    def units(self) -> str:
        return CELSIUS_UNITS

    @property
    def real_device(self):
        return self._real_device

class Bmp390Pressure(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        bmp = self._real_device
        return bmp.pressure

    @property
    def measurement(self) -> int:
        return PRESSURE

    @property
    def units(self) -> str:
        return HECTOPASCAL_UNITS

    @property
    def real_device(self):
        return self._real_device

class Bmp390Altitude(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        bmp = self._real_device
        return bmp.altitude

    @property
    def measurement(self) -> int:
        return ALTITUDE

    @property
    def units(self) -> str:
        return METER_UNITS

    @property
    def real_device(self):
        return self._real_device
# END BMP390

#
# SHT41 (SHT4x) measurements
class Sht41Temperature(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        sht = self._real_device
        temp, _ =  sht.measurements
        return temp

    @property
    def measurement(self) -> int:
        return TEMPERATURE

    @property
    def units(self) -> str:
        return CELSIUS_UNITS

    @property
    def real_device(self):
        return self._real_device

class Sht41RelativeHumidity(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        sht = self._real_device
        _, rh = sht.measurements
        return rh

    @property
    def measurement(self) -> int:
        return RELATIVE_HUMIDITY

    @property
    def units(self) -> str:
        return PERC_RELATIVE_HUMIDITY_UNITS

    @property
    def real_device(self):
        return self._real_device
# END SHT41 (SHT4x)

#
# VEML7700 measurements
class Veml7700AmbientLight(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        veml7700 = self._real_device
        l = veml7700.light
        return l

    @property
    def measurement(self) -> int:
        return AMBIENT_LIGHT

    @property
    def units(self) -> str:
        return AMBIENT_LIGHT_UNITS

    @property
    def real_device(self):
        return self._real_device

class Veml7700Lux(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        veml7700 = self._real_device
        l = veml7700.lux
        return l

    @property
    def measurement(self) -> int:
        return LUX

    @property
    def units(self) -> str:
        return LUX_UNITS

    @property
    def real_device(self):
        return self._real_device
# END VEML7700

#
# SCD41 (SCD4x) measurements
class Scd41Temperature(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        scd = self._real_device
        temp = scd.temperature
        return temp

    @property
    def measurement(self) -> int:
        return TEMPERATURE

    @property
    def units(self) -> str:
        return CELSIUS_UNITS

    @property
    def real_device(self):
        return self._real_device

class Scd41RelativeHumidity(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> float:
        scd = self._real_device
        rh = scd.relative_humidity
        return rh

    @property
    def measurement(self) -> int:
        return RELATIVE_HUMIDITY

    @property
    def units(self) -> str:
        return PERC_RELATIVE_HUMIDITY_UNITS

    @property
    def real_device(self):
        return self._real_device

class Scd41CO2(Meter):
    def __init__(self, device, store: datastructures.Store | None = None):
        super().__init__(device)
        self._real_device = device.real_device
        self._store = store

    @property
    def measure(self) -> int:
        scd = self._real_device
        co2 = scd.CO2
        return co2

    @property
    def measurement(self) -> int:
        return CO2

    @property
    def units(self) -> str:
        return PPM_UNITS

    @property
    def real_device(self):
        return self._real_device
# END SCD41 (SCD4x)

class MeterFactory:
    def __init__(self):
        self._boards = {}

    def register_board(self, board, ctor):
        try:
            dev_board = self._boards[board]
            dev_board['ctor'] = ctor
        except KeyError as e:
            self._board[board] = dict()
            self._board[board]['ctor'] = ctor

    def register_meter(self, board, measurement: int, ctor):
        try:
            dev_board = self._boards[board]
            dev_board[measurement] = ctor
        except KeyError as e:
            self._boards[board] = dict()
            self._boards[board][measurement] = ctor

    def get_meter(self, measurement: int, device: devices.Device,
                  store: datastructures.Store | None = None) -> MeterInterface:
        dev_board = self._boards.get(device.board)
        ctor = dev_board.get(measurement)
        if not ctor:
            raise ValueError('{}:{}'.format(device.board, measurement))

        return ctor(device, store)

meter_factory = MeterFactory()
meter_factory.register_meter(BMP390, TEMPERATURE, Bmp390Temperature)
meter_factory.register_meter(BMP390, PRESSURE, Bmp390Pressure)
meter_factory.register_meter(BMP390, ALTITUDE, Bmp390Altitude)
meter_factory.register_meter(SHT41, TEMPERATURE, Sht41Temperature)
meter_factory.register_meter(SHT41, RELATIVE_HUMIDITY, Sht41RelativeHumidity)
meter_factory.register_meter(VEML7700, AMBIENT_LIGHT, Veml7700AmbientLight)
meter_factory.register_meter(VEML7700, LUX, Veml7700Lux)
meter_factory.register_meter(SCD41, TEMPERATURE, Scd41Temperature)
meter_factory.register_meter(SCD41, RELATIVE_HUMIDITY, Scd41RelativeHumidity)
meter_factory.register_meter(SCD41, CO2, Scd41CO2)
