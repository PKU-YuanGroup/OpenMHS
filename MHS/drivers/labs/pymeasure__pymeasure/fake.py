"""Fake backend of the DMM6500 driver: an in-memory stand-in for the upstream
``pymeasure.instruments.keithley.keithleyDMM6500:KeithleyDMM6500``.

Gate G7: every public method and property defined here exists on that upstream class: the three ``measure_*``
methods (keithleyDMM6500.py:583, 700, 811), the ``:READ?`` measurement properties ``voltage``, ``current`` and
``resistance`` (keithleyDMM6500.py:486, 603, 719), the ``mode``, ``nplc`` and ``digits`` properties
(keithleyDMM6500.py:262, 349, 368), ``scan_stop`` (keithleyDMM6500.py:1315) and ``close``
(keithleyDMM6500.py:238).  The signatures mirror the upstream ones: ``measure_resistance(wires=2)`` accepts only 2
or 4 and raises ValueError otherwise, like keithleyDMM6500.py:822-829.

The starting values are test data, not device facts (each one is marked ``# placeholder``): they are the state of
this stand-in only, never a Fact, a Limit or a reference.  The values do not move by themselves, so reading the
state twice gives the same state.  Nothing here talks to an instrument.
"""


class FakeKeithleyDMM6500:
    def __init__(self, **_options):
        self._mode = "voltage"          # placeholder test data
        self._nplc = 1.0                # placeholder test data
        self._digits = 6                # placeholder test data
        self._voltage = 5.0             # placeholder test data
        self._current = 0.01            # placeholder test data
        self._resistance = 1000.0       # placeholder test data
        self._open = True

    # -- the state properties the driver reads and writes -------------------------------------------------------
    @property
    def mode(self):
        return self._mode

    @property
    def nplc(self):
        return self._nplc

    @nplc.setter
    def nplc(self, value):
        self._nplc = float(value)

    @property
    def digits(self):
        return self._digits

    @property
    def voltage(self):
        return self._voltage

    @property
    def current(self):
        return self._current

    @property
    def resistance(self):
        return self._resistance

    # -- mode selection, like the upstream measure_* methods ----------------------------------------------------
    def measure_voltage(self, max_voltage=1, ac=False):
        self._mode = "voltage ac" if ac else "voltage"

    def measure_current(self, max_current=10e-3, ac=False):
        self._mode = "current ac" if ac else "current"

    def measure_resistance(self, max_resistance=10e6, wires=2):
        if wires == 2:
            self._mode = "resistance"
        elif wires == 4:
            self._mode = "resistance 4W"
        else:
            raise ValueError("Keithley DMM6500 only supports 2 or 4 wire resistance measurements.")

    # -- the native stop and the connection --------------------------------------------------------------------
    def scan_stop(self):
        self._open = True

    def close(self):
        self._open = False
