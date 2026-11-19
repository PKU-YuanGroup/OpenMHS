"""Fake backend of the AFG-2225 driver: an in-memory stand-in for devices.afg2225:AFG2225.

Gate G7 checks the members of this class against the upstream class in the pinned clone.  The upstream AFG2225 has
two ``ChannelCreator`` attributes, ``ch1`` and ``ch2`` (src/test_engine/devices/afg2225.py:96-97), whose channel
objects expose the controls this fake mirrors: ``shape``, ``frequency``, ``amplitude``, ``offset``, ``phase``,
``output_enabled``, ``load``, ``duty_cycle`` and ``ramp_symmetry`` (afg2225.py:24-87).  The upstream root class also
has ``sync_phase()`` (afg2225.py:156-162) and the ``error`` measurement (afg2225.py:172-175); this fake defines those
only.  Nothing here talks to an instrument.

Every starting value and canned reply below is test data, not a device fact: each is marked ``# placeholder`` and is
never cited by a Fact or a Limit.
"""

#: Waveform names the upstream AFG2225Channel accepts (afg2225.py:18-21).  Reproduced here so the fake answers in
#: the same vocabulary as the driver; it is not a measurement or a bound.
SHAPES = ("sine", "square", "ramp", "pulse", "noise", "user")
LOADS = ("50ohm", "highZ")


class _FakeChannel:
    """One channel: plain attributes with the names the upstream AFG2225Channel controls expose."""

    def __init__(self, number):
        self.number = number
        self.shape = "sine"                 # placeholder
        self.frequency = 1000.0             # placeholder
        self.amplitude = 1.0                # placeholder
        self.offset = 0.0                   # placeholder
        self.phase = 0.0                    # placeholder
        self.output_enabled = False         # placeholder
        self.load = "50ohm"                 # placeholder
        self.duty_cycle = 50.0              # placeholder
        self.ramp_symmetry = 50.0           # placeholder


class FakeAFG2225:
    """A two-channel fake; the driver only uses the channel controls and the native synchronization call."""

    def __init__(self, **_options):
        self.ch1 = _FakeChannel(1)
        self.ch2 = _FakeChannel(2)
        self._last_error = '0,"No error"'   # placeholder

    @property
    def error(self):
        """The upstream error measurement is read without a call (the robot library reads ``device.error``)."""
        return self._last_error

    def sync_phase(self):
        """Model command completion only; the clone does not specify phase-register readback after synchronization."""
