"""Fake backend of the Ocean Optics TEC driver: an in-memory stand-in for oceanoptics.base:OceanOpticsTEC.

Gate G7: every public method here exists on oceanoptics.base:OceanOpticsTEC (base.py:312-439).  The driver also
reaches three private methods of the class, ``_tec_controller_get_status`` (base.py:430), ``_set_tec_controller_state``
(base.py:327) and ``_set_fan_state`` (base.py:317); they exist upstream and are defined here with the same names.

The upstream methods block for about 0.1 s per USB command and set_TEC_temperature waits 2 s for the cooldown
(base.py:383-395); the fake returns immediately because it has no transport.  The values never move by themselves,
so reading the state twice gives the same state.  Nothing here talks to a device.
"""


class FakeOceanOpticsTEC:
    def __init__(self, **_options):
        # Every value below is fake starting state (test data), not a device fact.
        self._tec_temperature = -10.0      # placeholder, degrees Celsius
        self._pcb_temperature = 25.0       # placeholder, degrees Celsius
        self._heatsink_temperature = 24.0  # placeholder, degrees Celsius
        self._setpoint = -15.0             # placeholder, degrees Celsius
        self._tec_enabled = 1              # placeholder
        self._fan_enabled = 1              # placeholder

    # -- reads ------------------------------------------------------------------------------------------------
    def get_TEC_temperature(self):
        return self._tec_temperature

    def get_temperatures(self):
        """The upstream returns (pcb, heatsink) from command 0x6C (base.py:357-370)."""
        return (self._pcb_temperature, self._heatsink_temperature)

    def _tec_controller_get_status(self):
        """The upstream order is (TEC enable, FAN enable, TEC setpoint), base.py:430-439."""
        return (self._tec_enabled, self._fan_enabled, self._setpoint)

    # -- writes -------------------------------------------------------------------------------------------------
    def set_TEC_temperature(self, temperature):
        """The upstream disables the TEC, writes the setpoint, switches the fan on and re-enables the TEC."""
        self._set_tec_controller_state(0x00)
        self._setpoint = float(temperature)
        self._set_fan_state(0x01)
        self._set_tec_controller_state(0x01)
        return self.get_TEC_temperature()

    def _set_tec_controller_state(self, state):
        """0x01 enables the TEC controller, 0x00 disables it (base.py:327-333)."""
        self._tec_enabled = 1 if state else 0

    def _set_fan_state(self, state):
        """The upstream always switches the fan on (base.py:317-323); keep that behaviour here."""
        self._fan_enabled = 1
