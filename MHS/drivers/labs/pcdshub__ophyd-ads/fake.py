"""Fake backend of the TwinCAT NC axis telemetry driver: a source-shaped stand-in for ``NcAxis``.

The upstream Device (ophyd_ads/devices.py:7-18) holds one ``AdsSignal`` object per Component.  This fake holds one
``_FakeAdsSignal`` per served Component, under the same attribute names, and implements only the call the driver makes
on it: ``get()``.  ``AdsSignal.get`` reads the Symbol over ADS (ophyd_ads/signal.py:72-78); a fake cannot open an ADS
connection, so it returns a stored value and counts the calls.  It does not implement ``put`` because this read-only
package never calls it.

Nothing here imports ophyd, pyads or the upstream package, opens an ADS connection or reads a PLC.  The fake has no
public method of its own; gate G7 therefore checks only the attribute names the driver touches against ``NcAxis``.
Every value is a placeholder chosen for the tests, not a fact about any axis.
"""


class _FakeAdsSignal:
    """One AdsSignal stand-in: ``get`` returns the stored value and records the call."""

    def __init__(self, value):
        self._value = value
        self._gets = 0

    def get(self):
        self._gets += 1
        return self._value


class FakeNcAxis:
    """One stand-in per telemetry Component of ``NcAxis``; all values are placeholders."""

    def __init__(self, **_options):
        self.act_acc = _FakeAdsSignal(0.25)          # placeholder
        self.act_pos = _FakeAdsSignal(12.5)          # placeholder
        self.act_pos_modulo = _FakeAdsSignal(12.5)   # placeholder
        self.act_torque = _FakeAdsSignal(0.1)        # placeholder
        self.act_velo = _FakeAdsSignal(1.5)          # placeholder
        self.axis_state = _FakeAdsSignal(1)          # placeholder
        self.cmd_no = _FakeAdsSignal(2)              # placeholder
        self.control_d_word = _FakeAdsSignal(3)      # placeholder
        self.couple_state = _FakeAdsSignal(4)        # placeholder
        self.ctrl_output = _FakeAdsSignal(5)         # placeholder
        self.drive_output = _FakeAdsSignal(6)        # placeholder
