"""Fake backend of the TPR trigger driver: an in-memory stand-in for pcdsdevices.tpr:TprTrigger.

Gate G7 checks the public methods of ``FakeTprTrigger`` against the pinned ``TprTrigger`` class.  This fake defines
only the six methods that class defines after ``__init__``: ``enable``, ``disable``, ``enable_ch``, ``disable_ch``,
``enable_trg`` and ``disable_trg`` (``pcdsdevices/tpr.py:154-178``).  The signal stand-ins live in private classes and
are instance attributes, under the upstream Component names (``enable_ch_cmd``, ``enable_trg_cmd``, ``eventrate``,
``label``, ``delay_ticks``, ``delay_taps``, ``delay_setpoint``, ``ns_delay``, ``width_ticks``, ``width_setpoint`` and
``width``); nothing here imports ophyd, pyepics or pcdsdevices, opens Channel Access or reads a PV.  Every value below
is a placeholder for the tests, not a fact about a timing system.

Upstream semantics the fake keeps (model review): ``ns_delay`` and ``width`` are derived signals whose ``get`` computes
the delay from the tick and tap members and the width from the tick member with the upstream constants
(``pcdsdevices/tpr.py:13-31``), and whose ``put`` writes only the last member, the setpoint (``_put_last``,
``pcdsdevices/tpr.py:34-36``).  The fake has no IOC: a setpoint write does not change the tick and tap members, so the
derived reads stay where the placeholders put them.  The real IOC's conversion from the setpoint to ticks and taps is
not in the clone and is not modelled.
"""

#: the upstream constants (pcdsdevices/tpr.py:15-16), used only to compute the derived reads the same way
_TPR_TICK_NS = 70 / 13
_TPR_TAP_NS = 0.08


class _FakeStatus:
    """A finished Status: what the driver waits on after a setpoint ``set``."""

    def __init__(self, success=True):
        self.done = True
        self.success = success

    def wait(self, timeout=None):
        if not self.success:
            raise RuntimeError("placeholder: the setpoint set failed")


class _FakeSignal:
    """A stored value with the calls the driver makes: ``get()``, ``put(value)`` and ``set(value, ...)``."""

    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def put(self, value):
        self.value = value

    def set(self, value, timeout=None, settle_time=None):
        self.value = value
        return _FakeStatus()


class _FakeDerivedSignal:
    """``ns_delay``/``width``: get from the member signals, put to the last member only (the upstream ``_put_last``)."""

    def __init__(self, members, calculate):
        self._members = members
        self._calculate = calculate

    def get(self):
        return self._calculate(*(member.get() for member in self._members))

    def put(self, value):
        self._members[-1].put(value)
        return _FakeStatus()


class FakeTprTrigger:
    def __init__(self, **_options):
        # The enable command values start at 0 (disabled); both are placeholders.
        self.enable_ch_cmd = _FakeSignal(0)          # placeholder
        self.enable_trg_cmd = _FakeSignal(0)         # placeholder
        self.eventrate = _FakeSignal(0.0)            # placeholder
        self.label = _FakeSignal("TPR channel")      # placeholder
        self.delay_ticks = _FakeSignal(2)            # placeholder
        self.delay_taps = _FakeSignal(3)             # placeholder
        self.delay_setpoint = _FakeSignal(11.0)      # placeholder
        self.width_ticks = _FakeSignal(1)            # placeholder
        self.width_setpoint = _FakeSignal(5.0)       # placeholder
        self.ns_delay = _FakeDerivedSignal(
            [self.delay_ticks, self.delay_taps, self.delay_setpoint],
            lambda ticks, taps, _setpoint: ticks * _TPR_TICK_NS + taps * _TPR_TAP_NS)
        self.width = _FakeDerivedSignal(
            [self.width_ticks, self.width_setpoint],
            lambda ticks, _setpoint: ticks * _TPR_TICK_NS)

    # -- the six public methods of pcdsdevices.tpr:TprTrigger after __init__ ---------------------------------
    def enable(self):
        self.enable_ch()
        self.enable_trg()

    def disable(self):
        self.disable_ch()
        self.disable_trg()

    def enable_ch(self):
        self.enable_ch_cmd.put(1)

    def disable_ch(self):
        self.enable_ch_cmd.put(0)

    def enable_trg(self):
        self.enable_trg_cmd.put(1)

    def disable_trg(self):
        self.enable_trg_cmd.put(0)
