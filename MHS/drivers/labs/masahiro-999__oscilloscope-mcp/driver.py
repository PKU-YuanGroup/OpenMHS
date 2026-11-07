"""OpenMHS driver for gh.masahiro-999/oscilloscope-mcp: a RIGOL DS1000Z-series oscilloscope.

A direct Driver (decorated methods) over the upstream device class
``oscilloscope_mcp.instruments.rigol_ds1000z:RigolDs1000z``.  The upstream class owns a
``ScpiLan`` transport (raw TCP, port 5555) and a model profile loaded from
``src/oscilloscope_mcp/instruments/profiles``; it validates every write against that
profile before sending a SCPI burst and returns dataclass snapshots.

* reads: identity, active channel count, the CH1 vertical setup, the timebase, the
  acquisition mode and the trigger state;
* writes: CH1 scale, offset, probe ratio, coupling and display; timebase scale, offset
  and mode; acquire type and averaging count; trigger sweep and coupling.  Every numeric
  write carries a bound the DS1000Z family profile declares in the clone;
* actions: ``measure`` (the scope-side automatic measurements) and ``run_control``
  (RUN / STOP / SINGLE / FORCE);
* the native stop (``:STOP`` through ``run_control``) is the e-stop; the safe state is
  acquisition stopped.

Not covered: the waveform array (``:WAV:DATA?``) and the screenshot block
(``:DISP:DATA?``).  Both are IEEE-488.2 binary blocks; a NORMal waveform is about 1200
screen points and a RAW waveform can be up to 24M points.  The standard carries scalar
state and measurements, not that array, so this package stops at the scalar functions.

Every Fact and Limit cites the pinned clone at
e45773551e2b956e1fb086ad99cbfec546eaad4b.  This package is model-authored and unreviewed;
the acceptance gate runs the fake backend only.  At R1 the loader does not refuse a
model-authored hardware backend (that refusal applies at R2 and R3), so the hardware
path remains untested until a human reviews the package.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_MEASURE_ITEMS = (
    "VMAX", "VMIN", "VPP", "VTOP", "VBASE", "VAMP", "VAVG", "VRMS",
    "OVERSHOOT", "PRESHOOT", "PERIOD", "FREQUENCY", "RTIME", "FTIME",
    "PWIDTH", "NWIDTH", "PDUTY", "NDUTY", "RDELAY", "FDELAY", "RPHASE", "FPHASE",
)
_CHANNELS = ("CHAN1", "CHAN2", "CHAN3", "CHAN4")
_PROFILE = "src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml"


class _ChannelSetup:
    """The attributes ``RigolDs1000z.set_channel`` reads from its ChannelSetup argument.

    ``driver.py`` is imported by the gate without the upstream package installed, so it
    cannot import the upstream dataclass.  The upstream setter only reads these
    attributes; a duck-typed object keeps the call and the SCPI wire unchanged.
    """

    def __init__(self, channel, *, scale_v_per_div=None, offset_v=None, coupling=None,
                 display=None, probe=None):
        self.channel = channel
        self.scale_v_per_div = scale_v_per_div
        self.offset_v = offset_v
        self.coupling = coupling
        self.display = display
        self.probe = probe
        self.bw_limit = None
        self.invert = None
        self.units = None


class _TimebaseSetup:
    """The attributes ``RigolDs1000z.set_timebase`` reads from its TimebaseSetup argument."""

    def __init__(self, *, s_per_div=None, offset_s=None, mode=None):
        self.s_per_div = s_per_div
        self.offset_s = offset_s
        self.mode = mode


class _AcquireSetup:
    """The attributes ``RigolDs1000z.set_acquire`` reads from its AcquireSetup argument."""

    def __init__(self, *, type=None, averages=None, memory_depth=None):
        self.type = type
        self.averages = averages
        self.memory_depth = memory_depth


class _TriggerSetup:
    """The attributes ``RigolDs1000z.set_trigger`` reads from its TriggerSetup argument."""

    def __init__(self, *, mode=None, sweep=None, coupling=None, holdoff_s=None, params=None):
        self.mode = mode
        self.sweep = sweep
        self.coupling = coupling
        self.holdoff_s = holdoff_s
        self.params = dict(params or {})


class RigolDs1000zScope(Driver):
    device_id = "rigol-ds1000z"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "oscilloscope_mcp.instruments.rigol_ds1000z:RigolDs1000z"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRigolDs1000z"}
    vendor, model = "RIGOL", "DS1000Z series (DS1054Z / DS1074Z / DS1104Z)"
    display_name = "RIGOL DS1000Z-series oscilloscope (RigolDs1000z)"
    tags = ["oscilloscope", "instrument", "scpi", "rigol", "ds1000z", "measurement"]
    facts = [
        Fact("The DS1000Z module drives the DS1054Z, DS1074Z and DS1104Z over line-based SCPI on raw TCP port 5555",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:1-6"),
        Fact("RigolDs1000z implements the Scope interface for every DS1000Z-series scope",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:54-55"),
        Fact("get_channel reads scale, offset, coupling, display, probe, bandwidth limit, invert and units for one "
             "channel", source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:104-116"),
        Fact("set_channel validates every requested field before sending one burst, with the probe ratio first",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:118-145"),
        Fact("get_timebase reads :TIM:MAIN:SCAL?, :TIM:MAIN:OFFS? and :TIM:MODE?",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:147-152"),
        Fact("set_timebase validates the mode, scale and offset before sending one burst",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:154-168"),
        Fact("get_acquire reads :ACQ:TYPE?, :ACQ:AVER?, :ACQ:MDEP? and :ACQ:SRAT?",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:174-188"),
        Fact("set_acquire validates every requested field before sending one burst",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:190-206"),
        Fact("get_trigger reads the global trigger fields and every readable parameter of the current trigger mode",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:212-236"),
        Fact("set_trigger validates all parameters up front and sends them in one burst with the mode first",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:238-280"),
        Fact("run_control writes the root command the profile maps to RUN, STOP, SINGLE or FORCE",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:282-287"),
        Fact("measure validates the measurement items and sources before querying :MEAS:ITEM? per item",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:293-333"),
        Fact("read_waveform reads about 1200 screen points in NORMal mode and up to 24M acquisition points in RAW "
             "mode, which requires the scope to be stopped",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/rigol_ds1000z.py:399-404"),
        Fact("The vertical scale range is 1.0e-3 to 100.0 V/div and the vertical offset range is -100.0 to 100.0 V",
             source="upstream_code", ref=_PROFILE + ":65-66"),
        Fact("The timebase scale range is 5.0e-9 to 50 s/div and the timebase offset range is -100.0 to 100.0 s",
             source="upstream_code", ref=_PROFILE + ":69-70"),
        Fact("The channel probe ratios are the 16 declared ratios from 0.01 to 1000",
             source="upstream_code", ref=_PROFILE + ":62"),
        Fact("The averaging counts are the powers of two from 2 to 1024",
             source="upstream_code", ref=_PROFILE + ":73"),
        Fact("The profile declares channel coupling AC/DC/GND, timebase modes MAIN/XY/ROLL, acquire types "
             "NORMal/AVERages/PEAK/HRESolution, trigger sweeps AUTO/NORMAL/SINGLE and trigger couplings "
             "AC/DC/LFReject/HFReject",
             source="upstream_code", ref=_PROFILE + ":61-80"),
        Fact("The DS1104Z has four analog channels and 24 Mpts of acquisition memory",
             source="upstream_code", ref="src/oscilloscope_mcp/instruments/profiles/rigol_ds1104z.yaml:14-21"),
    ]
    safe_state = "acquisition stopped (:STOP); the scope drives no output"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Response to *IDN?: vendor, model, serial and firmware")
    def identity(self):
        return self.native.idn()

    @read("active_channel_count", type="integer", description="Number of analog channels currently displayed")
    def active_channel_count(self):
        return self.native.active_channel_count()

    @read("channel_1_scale", unit="V", description="CH1 vertical scale in volts per division")
    def channel_1_scale(self):
        return self.native.get_channel(1).scale_v_per_div

    @read("channel_1_offset", unit="V", description="CH1 vertical offset in volts")
    def channel_1_offset(self):
        return self.native.get_channel(1).offset_v

    @read("channel_1_probe", unit="1", description="CH1 probe attenuation ratio")
    def channel_1_probe(self):
        return self.native.get_channel(1).probe

    @read("channel_1_coupling", type="string", description="CH1 input coupling (AC, DC or GND)")
    def channel_1_coupling(self):
        return self.native.get_channel(1).coupling

    @read("channel_1_display", type="boolean", description="True while CH1 is displayed")
    def channel_1_display(self):
        return self.native.get_channel(1).display

    @read("timebase_scale", unit="s", description="Main timebase scale in seconds per division")
    def timebase_scale(self):
        return self.native.get_timebase().s_per_div

    @read("timebase_offset", unit="s", description="Main timebase offset in seconds")
    def timebase_offset(self):
        return self.native.get_timebase().offset_s

    @read("timebase_mode", type="string", description="Timebase mode (MAIN, XY or ROLL)")
    def timebase_mode(self):
        return self.native.get_timebase().mode

    @read("acquire_type", type="string", description="Acquisition type (NORMal, AVERages, PEAK or HRESolution)")
    def acquire_type(self):
        return self.native.get_acquire().type

    @read("acquire_averages", type="integer", unit="1", description="Averaging count")
    def acquire_averages(self):
        return self.native.get_acquire().averages

    @read("acquire_memory_depth", type="string", description="Memory depth: AUTO or a point count")
    def acquire_memory_depth(self):
        return str(self.native.get_acquire().memory_depth)

    @read("acquire_sample_rate", unit="Hz", description="Current sample rate in samples per second")
    def acquire_sample_rate(self):
        return self.native.get_acquire().sample_rate

    @read("trigger_mode", type="string", description="Current trigger mode keyword")
    def trigger_mode(self):
        return self.native.get_trigger().mode

    @read("trigger_status", type="string", description="Trigger status from :TRIG:STAT? (TD, WAIT, RUN, AUTO or STOP)")
    def trigger_status(self):
        return self.native.get_trigger().status

    @read("trigger_sweep", type="string", description="Trigger sweep mode (AUTO, NORMAL or SINGLE)")
    def trigger_sweep(self):
        return self.native.get_trigger().sweep

    @read("trigger_coupling", type="string", description="Trigger coupling (AC, DC, LFReject or HFReject)")
    def trigger_coupling(self):
        return self.native.get_trigger().coupling

    @read("trigger_holdoff", unit="s", description="Trigger holdoff in seconds")
    def trigger_holdoff(self):
        return self.native.get_trigger().holdoff_s

    # -- writes -----------------------------------------------------------------------------------------------
    @write("channel_1_scale", unit="V", description="CH1 vertical scale in volts per division",
           limit=Limit(min=1.0e-3, max=100.0, unit="V", source="upstream_code", ref=_PROFILE + ":65"))
    def set_channel_1_scale(self, value):
        self.native.set_channel(_ChannelSetup(1, scale_v_per_div=value))

    @write("channel_1_offset", unit="V", description="CH1 vertical offset in volts",
           limit=Limit(min=-100.0, max=100.0, unit="V", source="upstream_code", ref=_PROFILE + ":66"))
    def set_channel_1_offset(self, value):
        self.native.set_channel(_ChannelSetup(1, offset_v=value))

    @write("channel_1_probe", unit="1", description="CH1 probe attenuation ratio",
           limit=Limit(allowed=[0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000],
                       unit="1", source="upstream_code", ref=_PROFILE + ":62"))
    def set_channel_1_probe(self, value):
        self.native.set_channel(_ChannelSetup(1, probe=value))

    @write("channel_1_coupling", type="string", enum=["AC", "DC", "GND"],
           description="CH1 input coupling")
    def set_channel_1_coupling(self, value):
        self.native.set_channel(_ChannelSetup(1, coupling=value))

    @write("channel_1_display", type="boolean", description="Display CH1 on or off")
    def set_channel_1_display(self, value):
        self.native.set_channel(_ChannelSetup(1, display=value))

    @write("timebase_scale", unit="s", description="Main timebase scale in seconds per division",
           limit=Limit(min=5.0e-9, max=50.0, unit="s", source="upstream_code", ref=_PROFILE + ":69"))
    def set_timebase_scale(self, value):
        self.native.set_timebase(_TimebaseSetup(s_per_div=value))

    @write("timebase_offset", unit="s", description="Main timebase offset in seconds",
           limit=Limit(min=-100.0, max=100.0, unit="s", source="upstream_code", ref=_PROFILE + ":70"))
    def set_timebase_offset(self, value):
        self.native.set_timebase(_TimebaseSetup(offset_s=value))

    @write("timebase_mode", type="string", enum=["MAIN", "XY", "ROLL"], description="Timebase mode")
    def set_timebase_mode(self, value):
        self.native.set_timebase(_TimebaseSetup(mode=value))

    @write("acquire_type", type="string", enum=["NORMal", "AVERages", "PEAK", "HRESolution"],
           description="Acquisition type")
    def set_acquire_type(self, value):
        self.native.set_acquire(_AcquireSetup(type=value))

    @write("acquire_averages", type="integer", unit="1", description="Averaging count",
           limit=Limit(allowed=[2, 4, 8, 16, 32, 64, 128, 256, 512, 1024], unit="1",
                       source="upstream_code", ref=_PROFILE + ":73"))
    def set_acquire_averages(self, value):
        self.native.set_acquire(_AcquireSetup(averages=value))

    @write("trigger_sweep", type="string", enum=["AUTO", "NORMAL", "SINGLE"], description="Trigger sweep mode")
    def set_trigger_sweep(self, value):
        self.native.set_trigger(_TriggerSetup(sweep=value))

    @write("trigger_coupling", type="string", enum=["AC", "DC", "LFReject", "HFReject"],
           description="Trigger coupling")
    def set_trigger_coupling(self, value):
        self.native.set_trigger(_TriggerSetup(coupling=value))

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.masahiro-999.measure.v1",
            description="Read the scope-side automatic measurements for one or more items on a channel",
            input={
                "items": Field("array", min_items=1,
                               items=Field("string", enum=list(_MEASURE_ITEMS),
                                           description="Canonical measurement item name"),
                               description="Automatic measurement items to query"),
                "source": Field("string", enum=list(_CHANNELS),
                                description="Primary channel the measurements are taken on"),
                "source2": Field("string", enum=list(_CHANNELS),
                                 description="Second channel for the two-source delay and phase items"),
            },
            output={
                "values": Field("object",
                                description="Measured value per canonical item name; null when unmeasurable"),
                "source": Field("string", description="Primary channel the measurements were taken on"),
                "source2": Field("string", nullable=True,
                                 description="Second channel used for two-source items, or null"),
                "items": Field("array", items=Field("string", description="Canonical measurement item name"),
                               description="Items queried, in request order"),
            })
    def measure(self, items, source="CHAN1", source2=None):
        """Query the scope-side measurements and echo the request alongside the values."""
        requested = list(items)
        values = self.native.measure(requested, source, source2)
        return {"values": values, "source": source, "source2": source2, "items": requested}

    @action(name="x-cap.masahiro-999.run_control.v1",
            description="Start, stop, arm a single acquisition, or force a trigger",
            input={"action": Field("string", enum=["RUN", "STOP", "SINGLE", "FORCE"],
                                   description="Run control action to apply")},
            output={
                "action": Field("string", description="Canonical action the scope applied"),
                "status": Field("string", nullable=True,
                                description="Trigger status after the action (:TRIG:STAT?)"),
            })
    def run_control(self, action):
        """Apply a run/arm command and report the trigger status the scope reports afterwards."""
        applied = self.native.run_control(action)
        return {"action": applied, "status": self.native.get_trigger().status}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="run_control")
    def stop(self):
        """The native stop: :STOP.  The runtime latches first, then calls this method."""
        self.native.run_control("STOP")
