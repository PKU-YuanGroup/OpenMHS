"""Fake backend of the Tektronix DPO70000 driver: an in-memory stand-in for the upstream class.

Gate G7: every public property and method here exists on
``instruments.tektronix.tekdpo70000:TekDPO70000`` or on one of its bases (``run``, ``stop`` and ``force_trigger``
on the class; ``reset`` and ``trigger`` inherited from ``SCPIInstrument``).  The fake returns strings for the enum
properties because the driver normalizes an upstream Enum member with its ``name``; it never imports upstream code.

The starting values are test data of this fake, not device defaults, datasheet ranges or facts.  They are marked
``# placeholder`` and never cited.  The values never move by themselves, so reading the state twice gives the same
state.  Nothing here talks to a device.
"""


class FakeTekDPO70000:
    def __init__(self, **_options):
        self._enhanced_enob = "AUTO"      # placeholder
        self._enhanced_state = False      # placeholder
        self._interp_8bit = "AUTO"        # placeholder
        self._magnivu = False             # placeholder
        self._mode = "sample"             # placeholder
        self._mode_actual = "sample"      # placeholder
        self._num_acquisitions = 0        # placeholder
        self._num_avgs = 16               # placeholder
        self._num_envelop = 100           # placeholder
        self._num_frames = 0              # placeholder
        self._acquire_state = "stop"      # placeholder
        self._trigger_state = "ready"     # placeholder

    @property
    def acquire_enhanced_enob(self):
        return self._enhanced_enob

    @property
    def acquire_enhanced_state(self):
        return self._enhanced_state

    @property
    def acquire_interp_8bit(self):
        return self._interp_8bit

    @property
    def acquire_magnivu(self):
        return self._magnivu

    @property
    def acquire_mode(self):
        return self._mode

    @property
    def acquire_mode_actual(self):
        return self._mode_actual

    @property
    def acquire_num_acquisitions(self):
        return self._num_acquisitions

    @property
    def acquire_num_avgs(self):
        return self._num_avgs

    @property
    def acquire_num_envelop(self):
        return self._num_envelop

    @property
    def acquire_num_frames(self):
        return self._num_frames

    @property
    def acquire_state(self):
        return self._acquire_state

    @property
    def trigger_state(self):
        return self._trigger_state

    def run(self):
        self._acquire_state = "run"       # placeholder

    def stop(self):
        self._acquire_state = "stop"      # placeholder

    def force_trigger(self):
        self._trigger_state = "armed"     # placeholder

    def trigger(self):
        self._trigger_state = "armed"     # placeholder

    def reset(self):
        self._enhanced_enob = "AUTO"      # placeholder
        self._enhanced_state = False      # placeholder
        self._interp_8bit = "AUTO"        # placeholder
        self._magnivu = False             # placeholder
        self._mode = "sample"             # placeholder
        self._mode_actual = "sample"      # placeholder
        self._num_acquisitions = 0        # placeholder
        self._num_avgs = 16               # placeholder
        self._num_envelop = 100           # placeholder
        self._num_frames = 0              # placeholder
        self._acquire_state = "stop"      # placeholder
        self._trigger_state = "ready"     # placeholder
