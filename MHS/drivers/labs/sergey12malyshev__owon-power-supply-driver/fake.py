"""Fake backend of the OWON driver: an in-memory stand-in for owon_ps:OwonPowerSupply.

Gate G7: every public method defined here exists on the upstream class owon_ps:OwonPowerSupply in the clone
(owon_ps.py:45-101).  The driver reaches no other attribute of the backend.  The upstream class sends one SCPI
command per method and returns the reply string; this fake keeps the same method shapes and returns the same kinds
of values (floats for the queries that upstream casts with float(), strings for the raw replies).

Every number and reply string below is test data, not a statement about a device; each is marked "# placeholder".
Nothing here talks to a device.
"""


class FakeOwonPowerSupply:
    def __init__(self, **_options):
        self._reset_state()

    def _reset_state(self):
        # all values below are placeholders (test data), not device facts or limits
        self._voltage = 5.0          # placeholder
        self._current = 0.5          # placeholder
        self._voltage_limit = 10.0   # placeholder
        self._current_limit = 2.0    # placeholder
        self._output = False         # placeholder
        self._identity = "OWON,FAKE-SP,0,0.0"        # placeholder
        self._all = "5.000,0.000,0.000,0.000"        # placeholder

    def output_on(self):
        self._output = True
        return "OK"                   # placeholder

    def output_off(self):
        self._output = False
        return "OK"                   # placeholder

    def get_outputState(self):
        return "1" if self._output else "0"          # placeholder reply

    def get_identity(self):
        return self._identity

    def reset_config(self):
        self._reset_state()
        return "OK"                   # placeholder

    def set_voltage(self, voltage):
        self._voltage = round(float(voltage), 3)

    def get_voltage(self):
        return self._voltage

    def measure_voltage(self):
        return self._voltage if self._output else 0.0

    def set_voltage_limit(self, voltage):
        self._voltage_limit = round(float(voltage), 3)

    def get_voltage_limit(self):
        return self._voltage_limit

    def set_current(self, current):
        self._current = round(float(current), 3)

    def get_current(self):
        return self._current

    def measure_current(self):
        return self._current if self._output else 0.0

    def set_current_limit(self, current):
        self._current_limit = round(float(current), 3)

    def get_current_limit(self):
        return self._current_limit

    def get_power(self):
        return round(self._voltage * self._current, 3) if self._output else 0.0

    def get_all_parametrs(self):
        return self._all

    def disconnect(self):
        self._output = False
