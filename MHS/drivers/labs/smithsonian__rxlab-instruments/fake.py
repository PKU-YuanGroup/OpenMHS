"""Fake backend of the Agilent E8257D driver: an in-memory stand-in for ``labinstruments.agilent:AgilentE8257D``.

Gate G7 checks every public method defined here against the upstream class (agilent.py:49-156 and the inherited
names in generic.py:59-68).  The stand-in implements exactly the methods the driver calls:

* ``set_frequency`` (agilent.py:63-73) and ``get_frequency`` (agilent.py:75-87);
* ``set_power`` (agilent.py:89-99) and ``get_power`` (agilent.py:101-120);
* ``power_on`` / ``power_off`` (agilent.py:136-146) and ``get_output_state`` (agilent.py:148-156);
* ``get_id`` (generic.py:59-63), ``reset`` (generic.py:65-68) and ``close`` (generic.py:54-57).

The state starts at the values marked below and every one of them is test data for this stand-in, never a Fact, a
Limit or a reference.  Nothing here talks to an instrument.
"""

#: Unit multipliers of the frequency argument, as in agilent.py:169-172.
_UNIT_HZ = {"ghz": 1e9, "mhz": 1e6, "khz": 1e3, "hz": 1.0}


class FakeE8257D:
    def __init__(self, **_options):
        self._frequency_hz = 1.0e9          # placeholder test data: initial CW frequency in hertz
        self._power_dbm = -20.0             # placeholder test data: initial CW output power in dBm
        self._output = False                # placeholder test data: the stand-in starts with the RF output off
        self._identity = "Agilent Technologies E8257D 0 0.0"  # placeholder test data: identity reply
        self._frequency_writes = []
        self._power_writes = []
        self._on_calls = 0
        self._off_calls = 0
        self._reset_calls = 0

    def set_frequency(self, value, units="GHz"):
        """Set the CW frequency; the upstream method writes ':FREQ <value><units>' (agilent.py:72)."""
        self._frequency_hz = float(value) * _UNIT_HZ[units.lower()]
        self._frequency_writes.append((float(value), units))

    def get_frequency(self, units="GHz"):
        """Return the CW frequency in the requested unit; the upstream method queries ':FREQ?' (agilent.py:86)."""
        return self._frequency_hz / _UNIT_HZ[units.lower()]

    def set_power(self, value, units="dBm"):
        """Set the CW output power; the upstream method writes ':POW <value><units>' (agilent.py:98)."""
        self._power_dbm = float(value)
        self._power_writes.append((float(value), units))

    def get_power(self, units="dBm"):
        """Return the CW output power in dBm; the upstream method queries ':UNIT:POW' then ':POW?' (agilent.py:114)."""
        return self._power_dbm

    def power_on(self):
        """Turn the RF output on; the upstream method writes ':OUTP ON' (agilent.py:136-140)."""
        self._output = True
        self._on_calls += 1

    def power_off(self):
        """Turn the RF output off; the upstream method writes ':OUTP OFF' (agilent.py:142-146)."""
        self._output = False
        self._off_calls += 1

    def get_output_state(self):
        """Return the RF output state as an integer; the upstream method queries 'OUTP:STAT?' (agilent.py:156)."""
        return int(self._output)

    def get_id(self):
        """Return the identity string; the upstream method queries '*IDN?' (generic.py:59-63)."""
        return self._identity

    def reset(self):
        """Count one '*RST' (generic.py:65-68).

        The clone's docstring says only "Reset instrument" and does not state the frequency, the power or the
        RF output.  The three values below are placeholder test data for this stand-in so a later query still
        has a reply.  They are not the instrument's defaults and no Fact, Limit or receipt cites them.
        """
        self._frequency_hz = 1.0e9          # placeholder test data: not a stated *RST default
        self._power_dbm = -20.0             # placeholder test data: not a stated *RST default
        self._output = False                # placeholder test data: not a stated *RST output state
        self._reset_calls += 1

    def close(self):
        """Close the connection; the upstream method closes the socket (generic.py:54-57)."""
