"""Fake EA-PS 10060-170 source for the pv-emulator driver package.

The fake implements only the public attributes of the upstream class named by ``native``
(``comm.bridge:EAPowerSupply``): ``read_meas_fast``, ``get_output_state``, ``get_error_code``, ``set_voltage``,
``set_current_limit``, ``output`` and the ``cached_vset``/``cached_iset`` properties.  It issues no serial I/O and
records the setpoints and the output state in plain attributes.  The initial values are test data, not device facts;
each is marked ``# placeholder``.  The measured values follow the cached setpoints while the output is on, as a
source feeding a load would; with the output off they read zero.
"""


class FakeEAPowerSupply:
    """A stand-in for the upstream EAPowerSupply; no serial port and no network."""

    def __init__(self, **_options):
        self._voltage_set = 0.0               # placeholder
        self._current_set = 0.0               # placeholder
        self._output_on = False               # placeholder
        self._error_code = 0                  # placeholder

    # -- measurements ------------------------------------------------------------------------------------------
    def read_meas_fast(self):
        """Return (V, I, P) like the upstream; zero while the output is off."""
        if not self._output_on:
            return 0.0, 0.0, 0.0
        voltage = self._voltage_set
        current = self._current_set
        return voltage, current, voltage * current

    def get_output_state(self):
        """Return 1 while the output is on, like OUTP:STAT?."""
        return 1 if self._output_on else 0

    def get_error_code(self):
        """Return the SCPI error code; this fake has an empty error queue."""
        return self._error_code

    # -- setpoints ---------------------------------------------------------------------------------------------
    def set_voltage(self, value):
        self._voltage_set = float(value)

    def set_current_limit(self, value):
        self._current_set = float(value)

    def output(self, on):
        self._output_on = bool(on)

    @property
    def cached_vset(self):
        return self._voltage_set

    @property
    def cached_iset(self):
        return self._current_set
