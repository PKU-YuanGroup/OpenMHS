"""Fake backend of the ARI M1 mirror-section driver: a source-shaped stand-in for ``ari_sxn_common.ari_ophyd.M1``.

The upstream ``M1`` Device (src/ari_sxn_common/ari_ophyd.py:38) owns the mirror motor Components, a
``_VacuumDevices`` child, a ``BaffleSlit`` child and a ``Diagnostic`` child.  This fake holds the same public child
names and, below them, the same child names and Signal-shaped objects the driver reads.  It implements only the
calls this read-only package makes: ``Signal.get(use_monitor=...)`` on the readbacks, gauges and current means.
Model review: the trigger stand-ins were removed with the served trigger; the upstream children's triggers are
ophyd ``SingleTrigger``/``NSLS_EM`` code outside the clone, which a done-status fake could not represent.

Nothing here imports ophyd, epics, nslsii or the upstream package, opens a Channel Access connection or reads an
IOC.  Every numeric value and location name is a placeholder chosen for the tests, not a fact about any device.
"""

from collections import namedtuple


class _FakeSignal:
    """One read-only classic Signal stand-in: ``get(use_monitor=...)`` returns the stored value."""

    def __init__(self, value):
        self._value = value
        self.use_monitor_calls = []
        self.gets = 0

    def get(self, *, use_monitor=None):
        self.gets += 1
        self.use_monitor_calls.append(use_monitor)
        return self._value

    def put(self, value):
        self._value = value


class _FakeMotor:
    """One ``ID29EpicsMotor`` stand-in with the two members the upstream class names (user_setpoint/user_readback)."""

    def __init__(self, position):
        self.user_readback = _FakeSignal(position)
        self.user_setpoint = _FakeSignal(position)

    @property
    def position(self):
        return self.user_readback._value


class _FakeCurrent:
    def __init__(self, value):
        self.mean_value = _FakeSignal(value)


class _FakeCurrents:
    """The ``ID29EM`` current child: current1 through current4 with a mean_value each."""

    def __init__(self, values):
        self.current1 = _FakeCurrent(values[0])
        self.current2 = _FakeCurrent(values[1])
        self.current3 = _FakeCurrent(values[2])
        self.current4 = _FakeCurrent(values[3])


class _FakeBaffleSlit:
    """The ``BaffleSlit`` child: four blade motors and the currents."""

    def __init__(self):
        self.top = _FakeMotor(1.0)       # placeholder
        self.bottom = _FakeMotor(2.0)    # placeholder
        self.inboard = _FakeMotor(3.0)   # placeholder
        self.outboard = _FakeMotor(4.0)  # placeholder
        self.currents = _FakeCurrents((0.1, 0.2, 0.3, 0.4))  # placeholders
        self.currents.top = self.currents.current1
        self.currents.bottom = self.currents.current2
        self.currents.inboard = self.currents.current3
        self.currents.outboard = self.currents.current4


class _FakeDiagnostic:
    """The ``Diagnostic`` child: blade/filter motors and the currents."""

    def __init__(self):
        self.blade = _FakeMotor(5.0)    # placeholder
        self.filter = _FakeMotor(6.0)   # placeholder
        self.currents = _FakeCurrents((0.5, 0.6, 0.7, 0.8))  # placeholders


class _FakeAriSxnC:
    """The ``_AriSxnC`` vacuum child with the three gauge Signals the driver reads."""

    def __init__(self):
        self.ccg = _FakeSignal(1.1e-7)  # placeholder
        self.tcg = _FakeSignal(2.2e-3)  # placeholder
        self.ip = _FakeSignal(3.3e-8)   # placeholder


class _FakeVacuumDevices:
    def __init__(self):
        self.AriSxnC = _FakeAriSxnC()


_FAKE_LOCATIONS = namedtuple("Locations", ["park", "beam"])


class _FakeLocationSignal:
    """The ``DeviceWithLocations.LocationSignal`` stand-in: ``get`` returns the placeholder location flags."""

    def __init__(self):
        self.gets = 0

    def get(self):
        self.gets += 1
        return _FAKE_LOCATIONS(park=True, beam=False)


class FakeM1:
    """The ``M1`` stand-in; one child object per public Component the driver touches."""

    def __init__(self, **_options):
        self.Ry_coarse = _FakeMotor(10.0)  # placeholder
        self.Ry_fine = _FakeMotor(11.0)    # placeholder
        self.Rz = _FakeMotor(12.0)         # placeholder
        self.x = _FakeMotor(13.0)          # placeholder
        self.y = _FakeMotor(14.0)          # placeholder
        self.vacuum = _FakeVacuumDevices()
        self.slits = _FakeBaffleSlit()
        self.diag = _FakeDiagnostic()
        self.locations = _FakeLocationSignal()
        self.photocurrent = self.diag.currents.current1.mean_value
