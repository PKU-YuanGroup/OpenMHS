"""Fake backend of the APS machine-parameter monitor: a source-shaped stand-in for ApsMachineParametersDevice.

The upstream Device (apstools/devices/aps_machine.py:38) holds one EpicsSignalRO object per Component.  This fake holds
one ``_FakeEpicsSignalRO`` per bound Component, under the same attribute names, and implements only the call the
driver makes on it: ``get(use_monitor=...)``.  Each signal keeps the ``use_monitor`` argument of every call so the
package test can check that every read asks for a fresh value (``use_monitor=False``).

Nothing here imports ophyd, pyepics or apstools, opens a Channel Access connection or reads a PV.  The fake has no
public method of its own (gate G7 checks the fake's members against the upstream class).  Every value is a
placeholder chosen for the tests, not a fact about the storage ring.
"""


class _FakeEpicsSignalRO:
    """One read-only Signal: ``get`` returns the stored value; nothing can set it."""

    def __init__(self, value):
        self._value = value
        self._use_monitor = []

    def get(self, *, use_monitor=None):
        self._use_monitor.append(use_monitor)
        return self._value


class FakeApsMachineParametersDevice:
    def __init__(self, **_options):
        self.current = _FakeEpicsSignalRO(101.5)                     # placeholder
        self.machine_status = _FakeEpicsSignalRO("USER OPERATIONS")  # placeholder (one of the strings at :73-81)
        self.operating_mode = _FakeEpicsSignalRO("Delivered Beam")   # placeholder (one of the strings at :83-90)
        self.shutter_status = _FakeEpicsSignalRO("PERMIT")           # placeholder
        self.shutters_open = _FakeEpicsSignalRO(2)                   # placeholder
        self.fill_number = _FakeEpicsSignalRO(4021)                  # placeholder
        self.orbit_correction = _FakeEpicsSignalRO(1)                # placeholder
