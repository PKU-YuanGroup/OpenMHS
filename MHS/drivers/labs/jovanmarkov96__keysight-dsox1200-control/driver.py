"""OpenMHS driver for gh.jovanmarkov96/keysight-dsox1200-control: Keysight InfiniiVision 1200 X-Series scopes.

A direct Driver over the upstream high-level class ``keysight_dsox1200.instrument:DSOX1200``.  The card proposes a
``ScpiDriver`` (family ``scpi``, decision ``family-config``), but the upstream interface is an object with methods,
not a table of fixed command lines: every channel command embeds the channel number (``:CHANnel1:SCALe``) and is
assembled at run time, so a command table cannot reproduce the lines the device receives (G7).  This package is a
direct Driver over the upstream class with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in
RESULT.json).

* the served resource is analog channel 1 plus the shared timebase, edge trigger and acquisition; the settings are
  read back through the upstream query methods of the same name;
* reads: identity, the channel-1 display, coupling, probe ratio, scale, offset, invert, the timebase
  mode, scale and position, the edge-trigger source, level, slope and sweep, the acquisition type, count and
  points, the sample rate and the acquisition completion percentage;
* writes: the channel-1 display, coupling, scale and offset, the timebase scale, the trigger source and level, and
  the acquisition type.  The vertical scale and offset, the timebase scale and the trigger level are
  ``Limit.operator_required`` because the clone states no numeric range for them.  The other settings the clone
  exposes are read-only here, because the MCP projection bounds one tool to 2048 bytes and the configure tool is
  the only writable-state tool;
* actions: one scalar automatic measurement from the scope's current measurement source, run, single and autoscale,
  and a ``safe_state`` stop;
* the e-stop sends the native stop (``:STOP``): the acquisition is halted and the frozen display is this
  instrument's safe state.

NOT COVERED: the waveform array.  ``capture_waveform``/``capture_all_channels`` transfer an IEEE 488.2 binary block
(:WAVeform:DATA?) as a ``WaveformData`` with time and voltage arrays; no catalogue class carries a trace array, so
this package serves the scalar measurements and the settings of the oscilloscope, not the samples.  The screenshot
array (PNG bytes), markers, FFT, DVM and the GUI are not exposed either.

Every Fact and Limit cites a line of the clone at the pinned commit (34ba50a758b9f4e8773dee788c3f9a4c04455f8f).  This
package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

INSTRUMENT = "src/keysight_dsox1200/instrument.py"
MODELS = "src/keysight_dsox1200/models.py"

#: The one analog channel this package serves; the clone validates every channel against 1 to 4 (instrument.py:46).
CHANNEL = 1

#: Coupling, acquisition, timebase and edge-trigger spellings of the upstream enum classes.
COUPLINGS = ["AC", "DC", "GND"]                                              # MODELS:13-16
ACQUIRE_TYPES = ["NORMal", "AVERage", "HRESolution", "PEAK"]                  # MODELS:30-34
TRIGGER_SOURCES = ["CHANnel1", "CHANnel2", "CHANnel3", "CHANnel4", "EXTernal", "LINE"]  # MODELS:50-56

#: The scalar automatic measurements of :MEASure, keyed by the name this driver serves (instrument.py:644-704).
MEASURE_ITEMS = {
    "frequency": "measure_frequency",
    "period": "measure_period",
    "duty_cycle": "measure_duty_cycle",
    "vmax": "measure_vmax",
    "vmin": "measure_vmin",
    "vpp": "measure_vpp",
    "vrms": "measure_vrms",
    "vaverage": "measure_vaverage",
    "vamplitude": "measure_vamplitude",
    "vtop": "measure_vtop",
    "vbase": "measure_vbase",
    "risetime": "measure_risetime",
    "falltime": "measure_falltime",
    "phase": "measure_phase",
    "delay": "measure_delay",
    "nwidth": "measure_nwidth",
    "pwidth": "measure_pwidth",
    "overshoot": "measure_overshoot",
    "preshoot": "measure_preshoot",
    "counter": "measure_counter",
}


class _Scpi(str):
    """A SCPI spelling with the ``.value`` member of the upstream ``str``-Enum classes (models.py:13-16).

    The upstream setters read ``coupling.value`` and write the exact spelling (instrument.py:260-261); this
    object supplies that member without importing the upstream package, which is not installed on the fake
    backend.
    """

    @property
    def value(self):
        return str(self)


class KeysightDsox1200Control(Driver):
    device_id = "keysight-dsox1200"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "keysight_dsox1200.instrument:DSOX1200"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeDSOX1200"}
    vendor = "Keysight Technologies"
    model = "InfiniiVision 1200 X-Series oscilloscope"
    display_name = "Keysight InfiniiVision 1200 X-Series oscilloscope (keysight_dsox1200.DSOX1200)"
    tags = ["oscilloscope", "keysight", "infiniivision", "dsox1200", "edux1052", "scpi", "visa"]
    facts = [
        Fact("The clone supports the DSOX1202A/G, DSOX1204A/G and EDUX1052A/G oscilloscopes",
             source="upstream_code", ref=f"{INSTRUMENT}:3"),
        Fact("The connection is a VISA resource opened by pyvisa with a newline read and write terminator",
             source="upstream_code", ref=f"{INSTRUMENT}:86-91"),
        Fact("identify queries *IDN? and returns the stripped identity string", source="upstream_code",
             ref=f"{INSTRUMENT}:165-167"),
        Fact("reset sends *RST and waits 0.5 s", source="upstream_code", ref=f"{INSTRUMENT}:169-172"),
        Fact("run, stop and single send :RUN, :STOP and :SINGle; the stop docstring says it halts acquisitions",
             source="upstream_code", ref=f"{INSTRUMENT}:215-225"),
        Fact("A channel number must be one of 1, 2, 3 and 4; another value raises ValidationError",
             source="upstream_code", ref=f"{INSTRUMENT}:46-54"),
        Fact("configure_channel sets the channel display, coupling, probe, range, scale, offset, invert, label, "
             "bandwidth limit and unit", source="upstream_code", ref=f"{INSTRUMENT}:319-354"),
        Fact("channel_scale takes volts per division, channel_range takes the full-scale voltage and "
             "channel_offset takes volts", source="upstream_code", ref=f"{INSTRUMENT}:273-289"),
        Fact("timebase_scale takes seconds per division and timebase_position takes seconds",
             source="upstream_code", ref=f"{INSTRUMENT}:373-385"),
        Fact("configure_trigger_edge sets the source, level in volts, slope, sweep and coupling",
             source="upstream_code", ref=f"{INSTRUMENT}:466-479"),
        Fact("acquire_count sets the number of averages, 2 to 65536, when the acquisition type is AVERage",
             source="upstream_code", ref=f"{INSTRUMENT}:496-498"),
        Fact("acquire_srate_query reads the sample rate the scope derives from the timebase",
             source="upstream_code", ref=f"{INSTRUMENT}:510-512"),
        Fact("acquire_complete returns the percentage of required waveforms acquired", source="upstream_code",
             ref=f"{INSTRUMENT}:514-516"),
        Fact("The automatic measurements query :MEASure:<item>? and return a float; measure_counter is the "
             "hardware counter frequency measurement", source="upstream_code", ref=f"{INSTRUMENT}:644-704"),
        Fact("capture_waveform transfers :WAVeform:DATA? as a binary block and returns time and voltage arrays",
             source="upstream_code", ref=f"{INSTRUMENT}:551-608"),
        Fact("The enums carry the exact SCPI spellings used by the setters: coupling, acquire type, trigger "
             "sweep, trigger slope, trigger source and timebase mode", source="upstream_code",
             ref=f"{MODELS}:13-72"),
    ]
    safe_state = "acquisition stopped with :STOP; the frozen display is the safe state of the oscilloscope"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN?)")
    def identity(self):
        return self.native.identify()

    @read("channel1_display", type="boolean", description="Channel 1 shown on screen")
    def channel1_display(self):
        return bool(self.native.channel_display_query(CHANNEL))

    @read("channel1_coupling", type="string", description="Channel 1 coupling")
    def channel1_coupling(self):
        return str(self.native.channel_coupling_query(CHANNEL))

    @read("channel1_probe_ratio", unit="1", description="Channel 1 probe attenuation ratio")
    def channel1_probe_ratio(self):
        return float(self.native.channel_probe_query(CHANNEL))

    @read("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div")
    def channel1_scale_v_per_div(self):
        return float(self.native.channel_scale_query(CHANNEL))

    @read("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts")
    def channel1_offset_v(self):
        return float(self.native.channel_offset_query(CHANNEL))

    @read("channel1_invert", type="boolean", description="Channel 1 waveform inverted")
    def channel1_invert(self):
        return bool(self.native.channel_invert_query(CHANNEL))

    @read("timebase_mode", type="string", description="Timebase mode")
    def timebase_mode(self):
        return str(self.native.timebase_mode_query())

    @read("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div")
    def timebase_scale_s_per_div(self):
        return float(self.native.timebase_scale_query())

    @read("timebase_position_s", unit="s", description="Timebase position in seconds")
    def timebase_position_s(self):
        return float(self.native.timebase_position_query())

    @read("trigger_source", type="string", description="Edge-trigger source")
    def trigger_source(self):
        return str(self.native.trigger_edge_source_query())

    @read("trigger_level_v", unit="V", description="Edge-trigger level in volts")
    def trigger_level_v(self):
        return float(self.native.trigger_edge_level_query())

    @read("trigger_slope", type="string", description="Edge-trigger slope")
    def trigger_slope(self):
        return str(self.native.trigger_edge_slope_query())

    @read("trigger_sweep", type="string", description="Trigger sweep mode")
    def trigger_sweep(self):
        return str(self.native.trigger_sweep_query())

    @read("acquire_type", type="string", description="Acquisition type")
    def acquire_type(self):
        return str(self.native.acquire_type_query())

    @read("acquire_count", type="integer", unit="1", description="Number of averages for AVERage acquisition")
    def acquire_count(self):
        return int(self.native.acquire_count_query())

    @read("acquire_points", type="integer", unit="1", description="Data points acquired per waveform")
    def acquire_points(self):
        return int(self.native.acquire_points_query())

    @read("sample_rate_hz", unit="Hz", description="Sample rate derived from the timebase")
    def sample_rate_hz(self):
        return float(self.native.acquire_srate_query())

    @read("acquire_complete", type="integer", unit="1",
          description="Percentage of required waveforms acquired")
    def acquire_complete(self):
        return int(self.native.acquire_complete())

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("channel1_display", type="boolean", description="Show channel 1")
    def set_channel1_display(self, value):
        self.native.channel_display(CHANNEL, bool(value))
        return bool(self.native.channel_display_query(CHANNEL))

    @write("channel1_coupling", type="string", description="Channel 1 coupling",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{MODELS}:13-16"))
    def set_channel1_coupling(self, value):
        self.native.channel_coupling(CHANNEL, _Scpi(value))
        return str(self.native.channel_coupling_query(CHANNEL))

    @write("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div",
           limit=Limit.operator_required(
               "the clone states only the 8 x V/div full-scale formula, not a per-division range; the range "
               "depends on the probe ratio and the model (instrument.py:273-282)"))
    def set_channel1_scale_v_per_div(self, value):
        self.native.channel_scale(CHANNEL, float(value))
        return float(self.native.channel_scale_query(CHANNEL))

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "the clone states no offset range; it depends on the vertical scale and the probe ratio "
               "(instrument.py:287-289)"))
    def set_channel1_offset_v(self, value):
        self.native.channel_offset(CHANNEL, float(value))
        return float(self.native.channel_offset_query(CHANNEL))

    @write("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div",
           limit=Limit.operator_required(
               "the clone states no timebase range; it depends on the model and the timebase mode "
               "(instrument.py:373-378)"))
    def set_timebase_scale_s_per_div(self, value):
        self.native.timebase_scale(float(value))
        return float(self.native.timebase_scale_query())

    @write("trigger_source", type="string", description="Edge-trigger source",
           limit=Limit(allowed=TRIGGER_SOURCES, source="upstream_code", ref=f"{MODELS}:50-56"))
    def set_trigger_source(self, value):
        self.native.trigger_edge_source(_Scpi(value))
        return str(self.native.trigger_edge_source_query())

    @write("trigger_level_v", unit="V", description="Edge-trigger level in volts",
           limit=Limit.operator_required(
               "the clone states no trigger level bound; it depends on the trigger source range "
               "(instrument.py:456-460)"))
    def set_trigger_level_v(self, value):
        self.native.trigger_edge_level(float(value))
        return float(self.native.trigger_edge_level_query())

    @write("acquire_type", type="string", description="Acquisition type",
           limit=Limit(allowed=ACQUIRE_TYPES, source="upstream_code", ref=f"{MODELS}:30-34"))
    def set_acquire_type(self, value):
        self.native.acquire_type(_Scpi(value))
        return str(self.native.acquire_type_query())

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.jovanmarkov96.measure.v1",
            description="Read one scalar automatic measurement from the scope's current measurement source",
            input={"item": Field("string", description="Measurement item, for example vpp, frequency or period",
                                 enum=list(MEASURE_ITEMS))},
            output={"value": Field("number", description="Measured value in the instrument's unit for the item")})
    def measure(self, item):
        return {"value": float(getattr(self.native, MEASURE_ITEMS[item])())}

    @action(name="x-cap.jovanmarkov96.run.v1", description="Start continuous acquisitions (:RUN)",
            output={"acquire_complete": Field("integer", unit="1",
                                              description="Acquisition completion percentage after :RUN")})
    def run(self):
        self.native.run()
        return {"acquire_complete": int(self.native.acquire_complete())}

    @action(name="x-cap.jovanmarkov96.single.v1", description="Arm one acquisition (:SINGle)",
            output={"acquire_complete": Field("integer", unit="1",
                                              description="Acquisition completion percentage after :SINGle")})
    def single(self):
        self.native.single()
        return {"acquire_complete": int(self.native.acquire_complete())}

    @action(name="x-cap.jovanmarkov96.autoscale.v1",
            description="Auto-configure the vertical, timebase and trigger settings (:AUToscale)",
            output={"channel1_scale_v_per_div": Field("number", unit="V",
                                                      description="Channel 1 vertical scale after autoscale"),
                    "channel1_offset_v": Field("number", unit="V",
                                               description="Channel 1 vertical offset after autoscale")})
    def autoscale(self):
        self.native.autoscale()
        return {"channel1_scale_v_per_div": float(self.native.channel_scale_query(CHANNEL)),
                "channel1_offset_v": float(self.native.channel_offset_query(CHANNEL))}

    @action(name="x-cap.jovanmarkov96.stop_acquisition.v1", safe_state=True,
            description="Stop acquisitions (:STOP, the safe state); it takes no input",
            output={"acquire_complete": Field("integer", unit="1",
                                              description="Acquisition completion percentage after :STOP")})
    def stop_acquisition(self):
        self.native.stop()
        return {"acquire_complete": int(self.native.acquire_complete())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends :STOP."""
        self.native.stop()

    def teardown(self):
        self.native.close()
