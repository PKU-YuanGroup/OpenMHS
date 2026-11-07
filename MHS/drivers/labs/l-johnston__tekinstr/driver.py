"""OpenMHS driver for gh.l-johnston/tekinstr: a Tektronix MDO3000-series oscilloscope over VISA SCPI.

A direct Driver over ``tekinstr.mdo3000.oscilloscope:Oscilloscope`` (the model's oscilloscope subsystem, built by
``tekinstr.mdo3000.mdo3000:MDO3000`` after ``tekinstr:CommChannel`` identified the instrument).  The card proposes a
``ScpiDriver`` (family ``scpi``, decision ``family-config``), but the upstream interface is an object with
properties, and the channel commands are assembled by the upstream from parts (``CH{ch}:...``, a channel number plus
a setting); a command table would cover only the fixed timebase commands and would have to invent the channel
syntax.  So this package is a direct Driver over the upstream class with a ``native.py`` factory (DEVIATION FROM
THE CARD, recorded in RESULT.json).

* the served resource is the oscilloscope's timebase, acquisition and trigger-status state;
* reads: sample rate, record length, horizontal scale, delay mode, acquisition mode, acquisition count, number of
  averages, acquisition state, single/continuous acquisition and trigger state;
* writes: record length, horizontal scale, delay mode, acquisition mode, number of averages, acquisition state
  and single/continuous acquisition.  The record length and number-of-averages writes are restricted to the sets
  the upstream docstrings state; the horizontal scale has no bound in the clone, so it is
  ``Limit.operator_required`` and every write is refused until the site supplies the timebase range;
* action: force a trigger event and report the trigger state afterwards;
* the e-stop stops the acquisition (``ACQUIRE:STATE STOP``); the frozen display is this instrument's safe state.

NOT COVERED: the waveform array.  ``Oscilloscope.read`` returns a ``WaveformDT`` or a numpy array of the acquired
samples (``tekinstr/oscilloscope.py:240-325``) and no catalogue class carries a trace array; this package serves the
settings and the trigger state and does not transfer samples.  Channel vertical settings (``Channel``) are also not
served: they sit on a per-channel object whose attributes the upstream class does not declare directly.

Every Fact and Limit cites a line of the clone at the pinned commit (7949430c1a6818d30aec152663c18dde85f2a7d7).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

INIT = "tekinstr/__init__.py"
BASE = "tekinstr/oscilloscope.py"
MDO = "tekinstr/mdo3000/oscilloscope.py"
MODEL = "tekinstr/mdo3000/mdo3000.py"

#: The record lengths the MDO3000 Oscilloscope docstring states (mdo3000/oscilloscope.py:34).
RECORD_LENGTHS = [1000, 10000, 100000, 1000000, 5000000, 10000000]

#: The acquisition modes the MDO3000 Oscilloscope docstring states (mdo3000/oscilloscope.py:80).
ACQUISITION_MODES = ["SAMPLE", "PEAKDETECT", "HIRES", "AVERAGE", "ENVELOPE"]

#: The number of waveforms to average: powers of two from 2 to 512 (oscilloscope.py:115).
NUM_AVERAGES = [2 ** power for power in range(1, 10)]

#: The delay modes of the MDO3000 Oscilloscope (mdo3000/oscilloscope.py:43).
DELAY_MODES = ["delay_time", "pretrigger_percent"]

#: The two acquisition states (oscilloscope.py:136).
ACQUISITION_STATES = ["RUN", "STOP"]

_TIME_SCALE_REASON = (
    "the clone sends HORIZONTAL:SCALE from a float without stating a range (tekinstr/oscilloscope.py:41); "
    "the operator supplies the timebase bound for this bench")


class MDO3000Scope(Driver):
    device_id = "mdo3000"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "tekinstr.mdo3000.oscilloscope:Oscilloscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOscilloscope"}
    vendor = "Tektronix"
    model = "MDO3000 series oscilloscope"
    display_name = "Tektronix MDO3000 series oscilloscope (tekinstr.Oscilloscope)"
    tags = ["oscilloscope", "tektronix", "mdo3000", "scpi", "visa", "test instrument"]
    facts = [
        Fact("CommChannel opens a TCPIP VISA resource and identifies the instrument by *IDN? before returning "
             "the model class", source="upstream_code", ref=f"{INIT}:43-58"),
        Fact("MDO3000 builds its Oscilloscope subsystem with the ANALOG:NUMCHANNELS count of CONFIGURATION",
             source="upstream_code", ref=f"{MODEL}:18-22"),
        Fact("sample_rate reads HORIZONTAL:SAMPLERATE? and is the rate the oscilloscope always acquires at",
             source="upstream_code", ref=f"{MDO}:24-30"),
        Fact("record_length takes 1e3, 1e4, 1e5, 1e6, 5e6 or 1e7 samples and is written as "
             "HORIZONTAL:RECORDLENGTH", source="upstream_code", ref=f"{MDO}:32-39"),
        Fact("horizontal_scale is the amount of time per division read and written as HORIZONTAL:SCALE",
             source="upstream_code", ref=f"{BASE}:33-41"),
        Fact("horizontal_delay_mode is delay_time or pretrigger_percent and is written as HORIZONTAL:DELAY:MODE "
             "ON/OFF", source="upstream_code", ref=f"{MDO}:41-54"),
        Fact("acquisition_mode is SAMPLE, PEAKDETECT, HIRES, AVERAGE or ENVELOPE",
             source="upstream_code", ref=f"{MDO}:78-89"),
        Fact("num_averages is the number of waveforms to average; the range is 2 to 512 in powers of 2",
             source="upstream_code", ref=f"{BASE}:112-122"),
        Fact("acquisition_state starts or stops the acquisition with RUN (1) or STOP (0)",
             source="upstream_code", ref=f"{BASE}:134-142"),
        Fact("single_acquisition writes ACQUIRE:STOPAFTER SEQUENCE for True and RUNSTOP for False",
             source="upstream_code", ref=f"{BASE}:144-158"),
        Fact("force_trigger writes TRIGGER FORCE", source="upstream_code", ref=f"{BASE}:327-329"),
        Fact("trigger_state is one of ARMED, AUTO, READY, SAVE or TRIGGER",
             source="upstream_code", ref=f"{BASE}:331-334"),
        Fact("read returns the acquired waveform samples as a WaveformDT or a numpy array",
             source="upstream_code", ref=f"{BASE}:240-325"),
        Fact("The upstream README reads channel CH1 through CommChannel and receives a waveform object",
             source="vendor_doc", ref="README.md:13-18"),
        Fact("The MDO3000 series is one of the supported model families", source="vendor_doc", ref="README.md:31-32"),
    ]
    safe_state = "acquisition stopped (ACQUIRE:STATE STOP); the frozen display is left as it is"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("sample_rate", unit="Hz", description="Sample rate of the acquisition in samples per second")
    def sample_rate(self):
        return float(self.native.sample_rate)

    @read("record_length", type="integer", unit="1",
          description="Record length in samples; the front panel offers 1e3 to 1e7 samples")
    def record_length(self):
        return int(self.native.record_length)

    @read("horizontal_scale", unit="s",
          description="Horizontal timebase in seconds per division (the value is s/div)")
    def horizontal_scale(self):
        return float(self.native.horizontal_scale)

    @read("horizontal_delay_mode", type="string",
          description="Horizontal position reference: delay_time or pretrigger_percent")
    def horizontal_delay_mode(self):
        return str(self.native.horizontal_delay_mode)

    @read("acquisition_mode", type="string",
          description="How the oscilloscope builds each sample: SAMPLE, PEAKDETECT, HIRES, AVERAGE or ENVELOPE")
    def acquisition_mode(self):
        return str(self.native.acquisition_mode)

    @read("acquisition_count", type="integer", unit="1",
          description="Number of acquisitions since the acquisition state was set to RUN")
    def acquisition_count(self):
        return int(self.native.acquisition_count)

    @read("num_averages", type="integer", unit="1",
          description="Number of waveforms averaged in AVERAGE mode (a power of two from 2 to 512)")
    def num_averages(self):
        return int(self.native.num_averages)

    @read("acquisition_state", type="string", description="Acquisition run state: RUN or STOP")
    def acquisition_state(self):
        return str(self.native.acquisition_state)

    @read("single_acquisition", type="boolean",
          description="True when a single sequence is acquired, False for continuous acquisition")
    def single_acquisition(self):
        return bool(self.native.single_acquisition)

    @read("trigger_state", type="string",
          description="Trigger state reported by the instrument: ARMED, AUTO, READY, SAVE or TRIGGER")
    def trigger_state(self):
        return str(self.native.trigger_state)

    # -- writes ------------------------------------------------------------------------------------------------
    @write("record_length", type="integer", unit="1",
           description="Record length in samples, kept to the front-panel values",
           limit=Limit(allowed=RECORD_LENGTHS, source="upstream_code", ref=f"{MDO}:34",
                       reason="the docstring lists the record lengths the front panel offers"))
    def set_record_length(self, value):
        self.native.record_length = int(value)

    @write("horizontal_scale", unit="s",
           description="Horizontal timebase in seconds per division (the value is s/div)",
           limit=Limit.operator_required(_TIME_SCALE_REASON))
    def set_horizontal_scale(self, value):
        self.native.horizontal_scale = float(value)

    @write("horizontal_delay_mode", type="string",
           description="Horizontal position reference: delay_time or pretrigger_percent",
           limit=Limit(allowed=DELAY_MODES, source="upstream_code", ref=f"{MDO}:43",
                       reason="the docstring names the two modes"))
    def set_horizontal_delay_mode(self, value):
        self.native.horizontal_delay_mode = str(value)

    @write("acquisition_mode", type="string",
           description="How the oscilloscope builds each sample",
           limit=Limit(allowed=ACQUISITION_MODES, source="upstream_code", ref=f"{MDO}:80",
                       reason="the docstring lists the five acquisition modes"))
    def set_acquisition_mode(self, value):
        self.native.acquisition_mode = str(value)

    @write("num_averages", type="integer", unit="1",
           description="Number of waveforms averaged in AVERAGE mode (a power of two from 2 to 512)",
           limit=Limit(allowed=NUM_AVERAGES, source="upstream_code", ref=f"{BASE}:115",
                       reason="the docstring states the range 2 to 512 in powers of 2"))
    def set_num_averages(self, value):
        self.native.num_averages = int(value)

    @write("acquisition_state", type="string", description="Start (RUN) or stop (STOP) the acquisition",
           limit=Limit(allowed=ACQUISITION_STATES, source="upstream_code", ref=f"{BASE}:136",
                       reason="the docstring names RUN (1) and STOP (0)"))
    def set_acquisition_state(self, value):
        self.native.acquisition_state = str(value)

    @write("single_acquisition", type="boolean",
           description="True acquires one sequence, False acquires continuously")
    def set_single_acquisition(self, value):
        self.native.single_acquisition = bool(value)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.l-johnston.force_trigger.v1",
            description="Force a trigger event and report the trigger state afterwards",
            output={"trigger_state": Field("string",
                                           description="Trigger state reported after the forced event")})
    def force_trigger(self):
        self.native.force_trigger()
        return {"trigger_state": str(self.native.trigger_state)}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop_acquisition(self):
        """Stop the acquisition (ACQUIRE:STATE STOP): the frozen display is the safe state of this instrument."""
        self.native.acquisition_state = "STOP"
