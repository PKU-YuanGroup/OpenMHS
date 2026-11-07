"""Fake backend of the tekinstr MDO3000 driver: an in-memory stand-in for ``tekinstr.mdo3000.oscilloscope:Oscilloscope``.

Gate G7: every public method and every attribute the driver touches exists on ``Oscilloscope`` in the clone
(``tekinstr/mdo3000/oscilloscope.py`` and its base ``tekinstr/oscilloscope.py``): sample_rate, record_length,
horizontal_scale, horizontal_delay_mode, acquisition_mode, acquisition_count, num_averages, acquisition_state,
single_acquisition, trigger_state and force_trigger.  A write reaches the attribute the next read returns.

The clone ships a pyvisa-sim device file (``tests/test_sim/sim_hw.yml``) for the upstream test suite, not a mock of
the Oscilloscope object, so this file is an in-memory stand-in, not a recording or a transcript.  Every number below
is test data, not a device fact: each is marked ``# placeholder`` and none is copied into a Fact, a Limit or a
reference.  Nothing here talks to an instrument.
"""

#: Test values of a freshly opened in-memory oscilloscope.
_SAMPLE_RATE = 1000000000.0  # placeholder
_RECORD_LENGTH = 10000  # placeholder
_HORIZONTAL_SCALE = 1e-06  # placeholder
_TRIGGER_STATE = "READY"  # placeholder


class FakeOscilloscope:
    """A fresh in-memory oscilloscope per endpoint; all values are placeholders, not a recording."""

    def __init__(self, **_options):
        self.sample_rate = _SAMPLE_RATE
        self.record_length = _RECORD_LENGTH
        self.horizontal_scale = _HORIZONTAL_SCALE
        self.horizontal_delay_mode = "pretrigger_percent"  # placeholder
        self.acquisition_mode = "SAMPLE"  # placeholder
        self.acquisition_count = 0  # placeholder
        self.num_averages = 2  # placeholder
        self.acquisition_state = "STOP"  # placeholder
        self.single_acquisition = False  # placeholder
        self.trigger_state = _TRIGGER_STATE

    def force_trigger(self):
        """Simulate the effect of TRIGGER FORCE: the trigger state becomes TRIGGER (a placeholder)."""
        self.trigger_state = "TRIGGER"  # placeholder
