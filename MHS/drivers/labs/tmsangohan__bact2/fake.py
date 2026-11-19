"""Fake backend of the bact2 vacuum sensor: a source-shaped stand-in for the ophyd VacuumSensor.

The upstream Device (bact2/ophyd/devices/raw/vacuum.py:3) holds one ``EpicsSignalRO`` per Component.  This fake holds
one ``_FakeEpicsSignalRO`` per bound Component, under the same attribute names, and implements only the call the
driver makes on it: ``get(use_monitor=...)``.  Each signal keeps the ``use_monitor`` argument of every call, so the
package test can prove that every read asks for a fresh value (``use_monitor=False``).

The fake also implements ``stop`` because the R1 driver declares the inherited ophyd ``Device.stop`` as its e-stop
binding (driver.py, ``safety_bindings``).  The stop only counts calls: the upstream sensor has no actuator, and the
package does not pretend that this method changes a physical device.

Nothing here imports ophyd, pyepics or bact2, opens a Channel Access connection or reads a PV.  Every value is a
placeholder chosen for the tests, not a fact about the vacuum system.
"""


class _FakeEpicsSignalRO:
    """One read-only Signal: ``get`` returns the stored value; nothing can set it."""

    def __init__(self, value):
        self.value = value
        self.get_calls = []

    def get(self, *, use_monitor=None):
        self.get_calls.append(use_monitor)
        return self.value


class FakeVacuumSensor:
    def __init__(self, **_options):
        self.pressure = _FakeEpicsSignalRO(1.0e-7)   # placeholder
        self.quality = _FakeEpicsSignalRO(1.0)       # placeholder
        self.stop_calls = 0

    def stop(self):
        """The inherited ophyd Device.stop: a no-op on this sensor, recorded for the tests."""
        self.stop_calls += 1
