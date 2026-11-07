"""Fake backend of the HP 6632B driver: an in-memory stand-in for py6632B.py6632B:HP6632B.

Gate G7: every public method defined here exists on the upstream class (py6632B/py6632B.py:22).  The values are test
data, marked ``# placeholder``; they are not device facts or safety limits.  The fake stores the set points as if the
supply were in constant-voltage operation, so a set or an output change is visible in the read state.  Nothing here
talks to a device or starts the upstream logging thread.  ``stop`` only disables the output; it does not call the
upstream ``isAlive``/``join`` path (the logging thread is never started).
"""

import collections

# The upstream module defines the same namedtuple (py6632B/py6632B.py:19); only the date/time members are unused.
Measurement = collections.namedtuple("Measurement", ["date", "time", "volt", "curr"])


class FakeHP6632B:
    def __init__(self, **_options):
        self._voltage = 0.0                              # placeholder
        self._current = 0.0                              # placeholder
        self._output = False                             # placeholder
        self._identity = "HEWLETT-PACKARD,6632B,0,0"     # placeholder

    def identify(self):
        return self._identity

    def get_volt_and_curr(self):
        return Measurement("", "", self._voltage, self._current)   # placeholder date and time

    def get_output_state(self):
        return "1" if self._output else "0"          # placeholder replies; OUTP:STAT? answers 1 or 0

    def set_volt_and_curr(self, volt, curr):
        self._voltage = float(volt)
        self._current = float(curr) / 1000.0          # the command is in mA; the measurement is in A

    def set_output_state(self, state):
        self._output = state == 1

    def stop(self):
        self._output = False
