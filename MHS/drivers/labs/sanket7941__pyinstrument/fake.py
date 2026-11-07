"""Fake backend of the pyinstrument PSupply driver: an in-memory stand-in for pyinstrument.instrument:PSupply.

Gate G7 checks every public method defined here against the upstream class
(pyinstrument/instrument.py:60-93).  The stand-in implements exactly the six methods the driver calls:

* ``on`` (line 73) and ``off`` (line 77): the output state;
* ``setVolt`` (line 81) and ``setCurr`` (line 85): the voltage and current setpoints;
* ``measureVolt`` (line 89) and ``measureCurr`` (line 92): the two measurement queries.

The upstream methods return the resource's reply text; the stand-in returns the same shape (a string) so the
driver's float conversion is exercised.  The measured value follows the setpoint while the output is enabled and is
zero while it is disabled; that is test behaviour, not a claim about a real instrument.

Every number below is test data for this stand-in, never a Fact, a Limit or a reference: each one is marked
``# placeholder``.  Nothing here talks to a device.
"""


class FakePSupply:
    def __init__(self, **_options):
        self._voltage_setpoint = 0.0    # placeholder test data: initial voltage setpoint in volts
        self._current_setpoint = 0.0    # placeholder test data: initial current setpoint in amperes
        self._output = True             # placeholder test data: the stand-in starts with its output enabled
        #: Native calls observed by the package tests (not part of the upstream surface).
        self.on_calls = 0
        self.off_calls = 0
        self.voltage_writes = []
        self.current_writes = []

    def on(self):
        """Turn the output on; the upstream method writes ':OUTPut:STATe 1' (pyinstrument/instrument.py:73-75)."""
        self._output = True
        self.on_calls += 1
        return "power supply is ON"

    def off(self):
        """Turn the output off; the upstream method writes ':OUTPut:STATe 0' (pyinstrument/instrument.py:77-79)."""
        self._output = False
        self.off_calls += 1
        return "power supply is OFF"

    def setVolt(self, Volt):
        """Set the voltage setpoint; the upstream method writes 'VOLT <value>' (pyinstrument/instrument.py:81-83)."""
        self._voltage_setpoint = float(Volt)
        self.voltage_writes.append(float(Volt))
        return "set voltage %d", Volt

    def setCurr(self, Current):
        """Set the current setpoint; the upstream method writes 'CURR <value>' (pyinstrument/instrument.py:85-87)."""
        self._current_setpoint = float(Current)
        self.current_writes.append(float(Current))
        return " set Current %d", Current

    def measureVolt(self):
        """Return the measured output voltage as text (the upstream method queries MEASure:VOLTage:DC?)."""
        value = self._voltage_setpoint if self._output else 0.0   # placeholder test data: disabled output reads 0 V
        return "%.6g" % value

    def measureCurr(self):
        """Return the measured output current as text (the upstream method queries MEASure:CURRent:DC?)."""
        value = self._current_setpoint if self._output else 0.0   # placeholder test data: disabled output reads 0 A
        return "%.6g" % value
