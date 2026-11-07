"""OpenMHS driver for gh.abduznik/instrumation: a Rigol DS1054Z oscilloscope over its SCPI methods.

The card proposes the ScpiDriver family, but the upstream class builds every channel command from parts:
``:CHANnel{channel}:DISPlay ...`` (rigol.py:163-176) and ``:WAVeform:SOURce CHANnel{channel}`` (rigol.py:395-406).
A command table can only send a template whose first token occurs literally in the clone, so it cannot reproduce
those numbers without changing the wire syntax.  This package is therefore a direct Driver over the upstream class
``instrumation.drivers.rigol:RigolDS1054Z`` (DEVIATION FROM THE CARD); the fake implements the same methods and the
gate checks its surface against the class in the clone.

The device is a four-channel 50 MHz oscilloscope with a 1 GSa/s sample rate (docs/experiments/rigol_ds1054z.md:10).
This driver exposes scalar settings and acquisition control only:

* reads: identity, acquisition type, sample rate, timebase mode/scale/offset, trigger mode/sweep/status/source/
  slope/level and channel 1 display/coupling/scale/offset/probe/bandwidth limit/invert;
* writes: acquisition type, timebase scale, trigger sweep/source/slope/level and channel 1 display/coupling/
  scale/bandwidth limit.  A numeric setting whose range the clone does not state is
  ``Limit.operator_required``: the site supplies it and until then every write is refused;
* actions: run, force trigger and a safe-state stop, each reporting the trigger status afterwards;
* the e-stop and the safe-state action both call the native ``stop`` method (``:STOP``, rigol.py:104-106).

NOT COVERED: the waveform array (``get_waveform``/``get_waveform_raw``), the screenshot, the per-channel
measurement helpers, the acquisition averages/memory depth, the timebase offset and the channel 1 offset, probe
ratio and inversion.  Channels 2-4 are not exposed by this scalar package; the upstream class configures all four
(``_validate_channel`` 1..4, rigol.py:159-161) and the methods are named for channel 1 here because the runtime has
one state field per name.

Every Limit and Fact cites a line of the clone at the pinned commit.  This package is model-authored and
unreviewed; it is checked on the fake backend only and no hardware run is claimed.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

RIGOL = "src/instrumation/drivers/rigol.py"
DOC = "docs/experiments/rigol_ds1054z.md"

#: Acquisition modes accepted by set_acquire_type (rigol.py:124-127).
ACQUIRE_TYPES = ("NORMAL", "AVERAGES", "PEAK", "HRESOLUTION")
#: Channel input couplings accepted by set_channel_coupling (rigol.py:186-188).
COUPLINGS = ("AC", "DC", "GND")
#: Bandwidth limits accepted by set_channel_bw_limit (rigol.py:249-251).
BW_LIMITS = ("20M", "OFF")
#: Edge trigger sources listed by set_edge_trigger_source (rigol.py:326-327).
TRIGGER_SOURCES = ("CHANnel1", "CHANnel2", "CHANnel3", "CHANnel4", "EXT", "DEMath")
#: Trigger slopes accepted by set_edge_trigger_slope (rigol.py:341-344).
TRIGGER_SLOPES = ("POSITIVE", "NEGATIVE", "RFALL")
#: Trigger sweeps accepted by set_trigger_sweep (rigol.py:362-367).
TRIGGER_SWEEPS = ("AUTO", "NORMAL", "SINGLE")


class RigolDS1054ZDriver(Driver):
    device_id = "rigol-ds1054z"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "instrumation.drivers.rigol:RigolDS1054Z"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRigolDS1054Z"}
    vendor, model = "RIGOL Technologies", "DS1054Z"
    display_name = "RIGOL DS1054Z oscilloscope"
    tags = ["oscilloscope", "rigol", "ds1054z", "ds1000z", "scpi", "instrument"]
    facts = [
        Fact("The DS1054Z is a 50 MHz, 4-channel digital oscilloscope with a 1 GSa/s sample rate",
             source="vendor_doc", ref=f"{DOC}:10"),
        Fact("The DS1054Z belongs to the MSO1000Z/DS1000Z family", source="vendor_doc", ref=f"{DOC}:3-4"),
        Fact("The driver supports the MSO1000Z/DS1000Z series and implements edge trigger only",
             source="upstream_code", ref=f"{RIGOL}:56-61"),
        Fact("The scope has four channels and the driver rejects a channel outside 1..4",
             source="upstream_code", ref=f"{RIGOL}:159-161"),
        Fact("Identity is queried with *IDN? and the experiment document prints 'RIGOL,DS1054Z,...'",
             source="vendor_doc", ref=f"{DOC}:44"),
        Fact("set_acquire_type accepts NORMAL, AVERAGES, PEAK and HRESOLUTION",
             source="upstream_code", ref=f"{RIGOL}:124-127"),
        Fact("set_acquire_averages accepts powers of two from 2 to 1024 (2^n, n=1..10)",
             source="upstream_code", ref=f"{RIGOL}:133-143"),
        Fact("The memory depth is given only as examples: 14k, 140k and 14M points, and the experiment document "
             "uses 14000000 points", source="upstream_code", ref=f"{RIGOL}:145-151"),
        Fact("The experiment document configures the timebase with 1 ms/div and the trigger level with 1.0 V",
             source="vendor_doc", ref=f"{DOC}:51-55"),
        Fact("Channel coupling is AC, DC or GND", source="upstream_code", ref=f"{RIGOL}:186-188"),
        Fact("The bandwidth limit accepts 20M or OFF", source="upstream_code", ref=f"{RIGOL}:249-251"),
        Fact("The edge trigger source list is CHANnel1..CHANnel4, EXT and DEMath",
             source="upstream_code", ref=f"{RIGOL}:323-329"),
        Fact("The edge trigger slopes are POSITIVE, NEGATIVE and RFALL",
             source="upstream_code", ref=f"{RIGOL}:341-344"),
        Fact("The trigger sweeps are AUTO, NORMAL and SINGLE", source="upstream_code", ref=f"{RIGOL}:362-367"),
        Fact("run writes :RUN, stop writes :STOP and force_trigger writes :TFORce",
             source="upstream_code", ref=f"{RIGOL}:100-114"),
        Fact("shutdown_safety stops the acquisition and then synchronises the instrument",
             source="upstream_code", ref=f"{RIGOL}:560-562"),
    ]
    safe_state = "acquisition stopped with :STOP and the trigger held off (the native stop)"

    # -- reads ---------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identification returned by *IDN?")
    def read_identity(self):
        return self.native.get_id()

    @read("acquire_type", type="string", description="Acquisition mode (:ACQuire:TYPE?)")
    def read_acquire_type(self):
        return self.native.get_acquire_type()

    @read("sample_rate", unit="Hz", description="Current sample rate (:ACQuire:SRATe?)")
    def read_sample_rate(self):
        return self.native.get_sample_rate()

    @read("timebase_mode", type="string", description="Timebase mode, MAIN, XY or ROLL (:TIMebase:MODE?)")
    def read_timebase_mode(self):
        return self.native.get_timebase_mode()

    @read("timebase_scale", unit="s", description="Horizontal scale in seconds per division (:TIMebase:SCALe?)")
    def read_timebase_scale(self):
        return self.native.get_timebase_scale()

    @read("timebase_offset", unit="s", description="Horizontal offset from the trigger point (:TIMebase:OFFSet?)")
    def read_timebase_offset(self):
        return self.native.get_timebase_offset()

    @read("trigger_mode", type="string", description="Trigger mode, EDGE or another mode (:TRIGger:MODE?)")
    def read_trigger_mode(self):
        return self.native.get_trigger_mode()

    @read("trigger_sweep", type="string", description="Trigger sweep mode (:TRIGger:SWEep?)")
    def read_trigger_sweep(self):
        return self.native.get_trigger_sweep()

    @read("trigger_status", type="string", description="Trigger status such as TD, WAIT, AUTO or STOP")
    def read_trigger_status(self):
        return self.native.get_trigger_status()

    @read("edge_trigger_source", type="string", description="Edge trigger source (:TRIGger:EDGe:SOURce?)")
    def read_edge_trigger_source(self):
        return self.native.get_edge_trigger_source()

    @read("edge_trigger_slope", type="string", description="Edge trigger slope (:TRIGger:EDGe:SLOPe?)")
    def read_edge_trigger_slope(self):
        return self.native.get_edge_trigger_slope()

    @read("edge_trigger_level", unit="V", description="Edge trigger level (:TRIGger:EDGe:LEVel?)")
    def read_edge_trigger_level(self):
        return self.native.get_edge_trigger_level()

    @read("ch1_display", type="boolean", description="Channel 1 display state (:CHANnel1:DISPlay?)")
    def read_ch1_display(self):
        return self.native.get_channel_display(1)

    @read("ch1_coupling", type="string", description="Channel 1 input coupling (:CHANnel1:COUPling?)")
    def read_ch1_coupling(self):
        return self.native.get_channel_coupling(1)

    @read("ch1_scale", unit="V", description="Channel 1 vertical scale in volts per division")
    def read_ch1_scale(self):
        return self.native.get_channel_scale(1)

    @read("ch1_offset", unit="V", description="Channel 1 vertical offset (:CHANnel1:OFFSet?)")
    def read_ch1_offset(self):
        return self.native.get_channel_offset(1)

    @read("ch1_probe", unit="1", description="Channel 1 probe attenuation ratio (:CHANnel1:PROBe?)")
    def read_ch1_probe(self):
        return self.native.get_channel_probe(1)

    @read("ch1_bw_limit", type="string", description="Channel 1 bandwidth limit (:CHANnel1:BWLimit?)")
    def read_ch1_bw_limit(self):
        return self.native.get_channel_bw_limit(1)

    @read("ch1_invert", type="boolean", description="Channel 1 inversion state (:CHANnel1:INVert?)")
    def read_ch1_invert(self):
        return self.native.get_channel_invert(1)

    # -- writes --------------------------------------------------------------------------------------------
    @write("acquire_type", type="string", description="Acquisition mode",
           limit=Limit(allowed=ACQUIRE_TYPES, source="upstream_code", ref=f"{RIGOL}:124-127"))
    def write_acquire_type(self, value):
        self.native.set_acquire_type(value)
        return value

    @write("timebase_scale", unit="s", description="Horizontal scale, s/div",
           limit=Limit.operator_required(
               "the clone's docstring gives only an example range, 1e-9 to 50.0 s/div (rigol.py:297), not the "
               "specification of this unit; the site supplies the timebase range"))
    def write_timebase_scale(self, value):
        self.native.set_timebase_scale(value)
        return value

    @write("trigger_sweep", type="string", description="Trigger sweep",
           limit=Limit(allowed=TRIGGER_SWEEPS, source="upstream_code", ref=f"{RIGOL}:362-367"))
    def write_trigger_sweep(self, value):
        self.native.set_trigger_sweep(value)
        return value

    @write("edge_trigger_source", type="string", description="Edge trigger source",
           limit=Limit(allowed=TRIGGER_SOURCES, source="upstream_code", ref=f"{RIGOL}:323-329"))
    def write_edge_trigger_source(self, value):
        self.native.set_edge_trigger_source(value)
        return value

    @write("edge_trigger_slope", type="string", description="Edge trigger slope",
           limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code", ref=f"{RIGOL}:341-344"))
    def write_edge_trigger_slope(self, value):
        self.native.set_edge_trigger_slope(value)
        return value

    @write("edge_trigger_level", unit="V", description="Edge trigger level",
           limit=Limit.operator_required(
               "the clone states no trigger level range (setter at rigol.py:350-352); the site supplies the "
               "range its probe and signal allow"))
    def write_edge_trigger_level(self, value):
        self.native.set_edge_trigger_level(value)
        return value

    @write("ch1_display", type="boolean", description="Channel 1 display")
    def write_ch1_display(self, value):
        self.native.set_channel_display(1, bool(value))
        return bool(value)

    @write("ch1_coupling", type="string", description="Channel 1 coupling",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{RIGOL}:186-188"))
    def write_ch1_coupling(self, value):
        self.native.set_channel_coupling(1, value)
        return value

    @write("ch1_scale", unit="V", description="Channel 1 scale, V/div",
           limit=Limit.operator_required(
               "the clone's docstring gives only an example, 0.01 to 10.0 V/div (rigol.py:201), not the "
               "specification of this unit; the site supplies the scale range of its probe"))
    def write_ch1_scale(self, value):
        self.native.set_channel_scale(1, value)
        return value

    @write("ch1_bw_limit", type="string", description="Channel 1 bandwidth limit",
           limit=Limit(allowed=BW_LIMITS, source="upstream_code", ref=f"{RIGOL}:249-251"))
    def write_ch1_bw_limit(self, value):
        self.native.set_channel_bw_limit(1, value)
        return value

    # -- actions -------------------------------------------------------------------------------------------
    @action(name="x-cap.abduznik.run.v1", description="Start the acquisition (:RUN) and report the trigger status",
            output={"trigger_status": Field("string", description="Trigger status after :RUN (:TRIGger:STATus?)")})
    def run(self):
        self.native.run()
        return {"trigger_status": self.native.get_trigger_status()}

    @action(name="x-cap.abduznik.force_trigger.v1",
            description="Force a trigger event (:TFORce) and report the trigger status",
            output={"trigger_status": Field("string", description="Trigger status after :TFORce")})
    def force_trigger(self):
        self.native.force_trigger()
        return {"trigger_status": self.native.get_trigger_status()}

    @action(name="x-cap.abduznik.stop.v1", safe_state=True,
            description="Stop the acquisition (:STOP), the safe state, and report the trigger status",
            output={"trigger_status": Field("string", description="Trigger status after :STOP")})
    def stop_acquisition(self):
        self.native.stop()
        return {"trigger_status": self.native.get_trigger_status()}

    # -- safety --------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then writes :STOP."""
        self.native.stop()
