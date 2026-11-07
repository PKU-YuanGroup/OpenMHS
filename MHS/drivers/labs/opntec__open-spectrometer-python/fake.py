"""Fake backend of the TCD1304 driver: an in-memory stand-in for TCD1304:TCD1304.

Gate G7: the public members defined here exist on the upstream class: poweron and poweroff (TCD1304.py:50-56)
and read_signal (TCD1304.py:75-87).  The two instance attributes the driver reads, integration_time and
master_clock_frequency, are assigned by the upstream constructor (TCD1304.py:42-43).  Nothing here talks to a
device; this class is a separate object and never derives from TCD1304 (G3 FAKE_IS_NATIVE).

Every number below is test data of this stand-in, not a device fact, and is marked ``# placeholder``.  A real
read_signal returns 3694 * 2 = 7388 samples (TCD1304.py:79-82); this fake returns eight so the gate receipt stays
small.  The values never change by themselves, so reading the state twice gives the same state.
"""

#: Captured samples of this stand-in (placeholder test data, not a device fact).
SAMPLES = [10.0, 20.0, 30.0, 90.0, 50.0, 40.0, 20.0, 10.0]  # placeholder


class FakeTCD1304:
    def __init__(self, **_options):
        self.integration_time = 10e-6             # placeholder test data; the constructor default is not a bound
        self.master_clock_frequency = 2e6         # placeholder test data
        self._powered = False
        self.poweron()
        self._start_sh_clock()

    def poweron(self):
        self._powered = True

    def poweroff(self):
        self._powered = False

    def _start_sh_clock(self):
        self._sh_period = float(self.integration_time)   # placeholder test data

    def read_signal(self):
        if not self._powered:
            return [0.0] * len(SAMPLES)           # placeholder test data
        return list(SAMPLES)
