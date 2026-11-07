"""Fake backend of the IKA RCT digital 5 driver: an in-memory stand-in for the upstream hotplate class.

Gate G7: every method defined here exists on ``Minerva.Hardware.Hotplates.IkaHotplate:RCTDigital5``
(IkaHotplate.py:217-765).  The upstream class talks to the plate over a serial line; this fake replaces that transport
with plain attributes and never imports the upstream package.  The starting values and the reset values are test data,
marked ``# placeholder``; they are not facts about any plate and are not copied into a Fact or a Limit.  The values
never move by themselves, so reading the state twice gives the same state.  ``start_heating``, ``start_stirring`` and
the stop methods update the setpoints the reads report, so a write or an action has an observable effect.
"""


class FakeRCTDigital5:
    """In-memory ``RCTDigital5``: the same public methods, no serial port."""

    EMERGENCY_STOP_REQUEST = False

    def __init__(self, **_options):
        self._device_name = "RCT digital"               # placeholder
        self._external_temperature = 21.5               # placeholder
        self._hotplate_temperature = 21.0               # placeholder
        self._stirring_speed = 0.0                      # placeholder
        self._viscosity_trend = 0.0                     # placeholder
        self._temperature_setpoint = 0.0                # placeholder
        self._safety_temperature = 120.0                # placeholder
        self._stirring_speed_setpoint = 0.0             # placeholder
        self._heating = False
        self._stirring = False
        self._connected = True

    # -- reads (IkaHotplate.py:217, 236, 257, 278, 299, 320, 339, 358) -------------------------------------------
    def read_device_name(self, log: bool = True) -> str:
        return self._device_name

    def read_current_external_sensor_value(self, log: bool = True, is_polling: bool = False) -> float:
        return self._external_temperature

    def read_current_hotplate_sensor_value(self, log: bool = True, is_polling: bool = False) -> float:
        return self._hotplate_temperature

    def read_current_stirring_speed_value(self, log: bool = True, is_polling: bool = False) -> float:
        return self._stirring_speed

    def read_current_viscosity_trend_value(self, log: bool = True, is_polling: bool = False) -> float:
        return self._viscosity_trend

    def read_temperature_setpoint(self, log: bool = True) -> float:
        return self._temperature_setpoint

    def read_safety_temperature_value(self, log: bool = True) -> float:
        return self._safety_temperature

    def read_stirring_speed_setpoint(self, log: bool = True) -> float:
        return self._stirring_speed_setpoint

    # -- writes (IkaHotplate.py:377, 397) -------------------------------------------------------------------------
    def set_temperature_setpoint(self, value: float, log: bool = True) -> None:
        self._temperature_setpoint = float(value)

    def set_stirring_speed_setpoint(self, value: float, log: bool = True) -> None:
        self._stirring_speed_setpoint = float(value)

    # -- heating and stirring (IkaHotplate.py:417, 438, 459, 480) --------------------------------------------------
    def start_heating(self, value=None, log: bool = True) -> None:
        if value is not None:
            self.set_temperature_setpoint(value=value, log=log)
        self._heating = True

    def stop_heating(self, reset_setpoint: bool = True, log: bool = True) -> None:
        self._heating = False
        if reset_setpoint:
            self.set_temperature_setpoint(value=0, log=log)

    def start_stirring(self, value=None, log: bool = True) -> None:
        if value is not None:
            self.set_stirring_speed_setpoint(value=value, log=log)
        self._stirring = True

    def stop_stirring(self, reset_setpoint: bool = True, log: bool = True) -> None:
        self._stirring = False
        if reset_setpoint:
            self.set_stirring_speed_setpoint(value=0, log=log)

    # -- stop path and teardown (IkaHotplate.py:203, 751) ---------------------------------------------------------
    def emergency_stop(self) -> bool:
        FakeRCTDigital5.EMERGENCY_STOP_REQUEST = True
        self.stop_heating()
        self.stop_stirring()
        return True

    def disconnect(self) -> None:
        self.stop_heating()
        self.stop_stirring()
        self._connected = False
