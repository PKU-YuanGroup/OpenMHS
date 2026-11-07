"""Fake backend of the HXN beamline status monitor: a source-shaped stand-in for BeamlineStatus.

The upstream Device (``startup/10-optics.py:13``) holds one ``EpicsSignalRO`` object per Component.  This fake holds
one ``_PlaceholderSignalRO`` per Component, under the same four attribute names, and implements only the call the
driver makes on it: ``get(use_monitor=...)``.  Each signal records the ``use_monitor`` argument of every call so the
package tests can check that each read asks for a fresh value (``use_monitor=False``).

Nothing here imports ophyd, pyepics or the upstream startup script, opens a Channel Access connection or reads a PV.
The fake has no public method of its own (gate G7 checks the fake's members against the upstream class).  Every value
is a placeholder chosen for the tests, not a fact about the HXN beamline.
"""


class _PlaceholderSignalRO:
    """One read-only Signal: ``get`` returns the stored value; nothing can set it."""

    def __init__(self, value):
        self._value = value
        self._use_monitor = []

    def get(self, *, use_monitor=None):
        self._use_monitor.append(use_monitor)
        return self._value


class FakeBeamlineStatus:
    def __init__(self, **_options):
        self.shutter_status = _PlaceholderSignalRO(1)        # placeholder
        self.beam_current = _PlaceholderSignalRO(500.0)      # placeholder
        self.beamline_enabled = _PlaceholderSignalRO(1)      # placeholder
        self.cryo_filling = _PlaceholderSignalRO(0)          # placeholder
