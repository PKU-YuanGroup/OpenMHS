"""OpenMHS driver for gh.valiantandupright/oscilloscope-mcp: a Keysight InfiniiVision SCPI oscilloscope.

A direct Driver over the upstream class ``osc.scope:Scope``.  The card proposes a ``ScpiDriver`` (family ``scpi``,
decision ``family-config``), but the upstream interface is an object whose methods build SCPI commands from parts
at run time: every channel command embeds the channel number in a prefix (``:CHANnel{channel}``) and the waveform
capture transfers an IEEE 488.2 binary block through ``query_binary_values``.  A fixed text command table cannot
reproduce those lines or the binary block, so this package is a direct Driver with a ``native.py`` factory
(DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: identity, channel 1 display/coupling/probe/scale/offset, the timebase mode/scale/position and sample rate,
  and the edge-trigger source/level/slope/sweep;
* writes: channel 1 display/coupling/scale/offset, timebase scale/position and trigger source/level.  The probe
  ratio, timebase mode, trigger slope and trigger sweep are read-only state; they are written by the
  ``configure_channel``, ``configure_timebase`` and ``configure_trigger`` actions (the configure state tool stays
  within the MCP projection's tool-size bound).  The clone states allowed sets for coupling, probe, slope, sweep,
  timebase mode and trigger source, and a 1-2-5 division table for V/div and s/div; it states no continuous range
  for the vertical scale, offset, timebase position or trigger level. Those and the deployment-dependent channel
  and trigger-source selections are ``Limit.operator_required`` and
  are refused ``MHS.SAFETY.LIMITS_UNSET`` until the site overlay supplies the range of the installed instrument.
  The upstream web control clamps trigger level to +-1000 V; this control guard is not an instrument rating;
* actions: identity, one scalar automatic measurement, a waveform capture with the returned time and voltage
  samples and their statistics, channel/timebase/trigger configuration on channels 1 to 4, run, single, autoscale
  and an input-free safe-state stop;
* the e-stop sends ``:STOP`` and requires an empty queried instrument error queue. The upstream has no
  run-state readback, so only command acceptance is reported; acquisition quiescence is not sensed. The error
  queue drains up to 32 queries and shares the VISA lock with capture, so a stop can exceed the endpoint budget.

NOT COVERED: the PNG screen capture (``Scope.screenshot``, a binary image block) has no catalogue class and no
artifact store in this package, so it is not exposed.  Multi-channel settings are written through the
``configure_channel`` action and returned in its output, but only channel 1 is part of the continuously read
resource state.

Every Fact and Limit cites a line of the clone at the pinned commit
(20c25de5a2f01cdf037b10c7d68a170bc233f4c4).  This package is model-authored and unreviewed, is checked on the fake
backend only, and never ran on an instrument.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SCOPE = "osc/scope.py"
CONFIG = "osc/config.py"
SCALES = "osc/scales.py"
WEB = "web/server.py"

#: The automatic measurement items of the upstream table (scope.py:43-57).
MEASUREMENT_ITEMS = ["vpp", "vmax", "vmin", "vavg", "vrms", "amplitude", "top", "base", "frequency",
                     "period", "dutycycle", "rise_time", "fall_time"]

#: Allowed tokens of the upstream web control (web/server.py:119-123).
COUPLINGS = ["DC", "AC"]
SLOPES = ["POS", "NEG", "EITH"]
SWEEPS = ["AUTO", "NORM"]
TIMEBASE_MODES = ["MAIN", "XY", "ROLL"]
PROBES = [1.0, 10.0, 100.0, 1000.0]
TRIGGER_SOURCES = ["CHANNEL1", "CHANNEL2", "CHANNEL3", "CHANNEL4", "EXT"]


def _channel(status, channel):
    for item in status.get("channels") or []:
        if int(item.get("channel", 0)) == channel:
            return item
    raise RuntimeError(f"the instrument status has no channel {channel}")


def _number(value):
    return None if value is None else float(value)


class OscilloscopeMcp(Driver):
    device_id = "oscilloscope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "osc.scope:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "Keysight Technologies"
    model = "InfiniiVision DSOX1204A and compatible SCPI oscilloscopes"
    display_name = "Keysight InfiniiVision oscilloscope over SCPI (osc.scope.Scope)"
    tags = ["oscilloscope", "keysight", "infiniivision", "dsox1204a", "scpi", "visa", "usbtmc"]
    facts = [
        Fact("The project targets a Keysight DSOX1204A and other benchtop oscilloscopes supporting USBTMC and SCPI",
             source="vendor_doc", ref="README.md:34"),
        Fact("The module is the SCPI driver layer of the Keysight InfiniiVision series and depends only on pyvisa "
             "over NI-VISA USBTMC", source="upstream_code", ref=f"{SCOPE}:1-4"),
        Fact("The connection is a pyvisa ResourceManager and an open VISA resource with newline terminators and a "
             "timeout from config.TIMEOUT_MS", source="upstream_code", ref=f"{SCOPE}:122-131"),
        Fact("The SCPI timeout defaults to 10000 ms and can be overridden with SCOPE_TIMEOUT_MS",
             source="upstream_code", ref=f"{CONFIG}:31-32"),
        Fact("write sends one command line and query returns one stripped reply line", source="upstream_code",
             ref=f"{SCOPE}:158-170"),
        Fact("identify queries *IDN? and splits the reply into manufacturer, model, serial and firmware",
             source="upstream_code", ref=f"{SCOPE}:185-194"),
        Fact("status reads the timebase, all channels, the edge trigger and the acquisition type and points",
             source="upstream_code", ref=f"{SCOPE}:206-239"),
        Fact("autoscale, run, stop and single send :AUToscale, :RUN, :STOP and :SINGle", source="upstream_code",
             ref=f"{SCOPE}:242-252"),
        Fact("configure_channel writes scale, offset, coupling, display and probe ratio on a channel",
             source="upstream_code", ref=f"{SCOPE}:254-274"),
        Fact("ChannelSetting documents scale in V/div and offset in V",
             source="upstream_code", ref=f"{SCOPE}:94-101"),
        Fact("configure_timebase sets the mode and the s/div scale and position in seconds", source="upstream_code",
             ref=f"{SCOPE}:276-288"),
        Fact("configure_trigger writes the edge source, level, slope and sweep", source="upstream_code",
             ref=f"{SCOPE}:290-304"),
        Fact("capture asks for :WAVeform:POINts?, transfers :WAVeform:DATA? as 8-bit samples, converts the preamble "
             "and decimates the envelope using max_return", source="upstream_code",
             ref=f"{SCOPE}:307-386"),
        Fact("The clone declares NO_MEASUREMENT=9.9e36 for measurements that cannot be made",
             source="upstream_code", ref=f"{SCOPE}:38-40"),
        Fact("The numeric parser returns None for an absent or unparsable value and values whose absolute value "
             "is at least half of NO_MEASUREMENT", source="upstream_code", ref=f"{SCOPE}:60-70"),
        Fact("measure queries :MEASure:<item>? CHANnel<n> for each requested item", source="upstream_code",
             ref=f"{SCOPE}:388-405"),
        Fact("The V/div table spans 1 mV/div to 5 V/div and the s/div table 2 ns/div to 50 s/div in 1-2-5 steps",
             source="upstream_code",
             ref=f"{SCALES}:15-23"),
        Fact("The web control accepts coupling DC/AC, slope POS/NEG/EITH, sweep AUTO/NORM, timebase mode MAIN/XY/ROLL, "
             "and probe ratios 1/10/100/1000", source="upstream_code",
             ref=f"{WEB}:119-123"),
        Fact("The web trigger-source parser accepts CHANNELn or CHANn when n is within config.CHANNEL_COUNT, plus EXT",
             source="upstream_code", ref=f"{WEB}:157-170"),
        Fact("The channel count is configurable with SCOPE_CHANNEL_COUNT and defaults to four",
             source="upstream_code", ref=f"{CONFIG}:34-36"),
        Fact("errors queries :SYSTem:ERRor? up to 32 times, stops at a reply beginning +0 and returns other replies",
             source="upstream_code", ref=f"{SCOPE}:196-204"),
        Fact("The web control clamps a trigger level to -1000 V and 1000 V before sending it", source="upstream_code",
             ref=f"{WEB}:224-225"),
        Fact("The clone requests 2000 waveform points and decimates to at most 500 by default", source="upstream_code",
             ref=f"{CONFIG}:38-42"),
        Fact("A logged session shows the automatic measurement commands as :MEASure:VPP? CHANnel1 and "
             ":MEASure:FREQuency? CHANnel1", source="vendor_doc", ref="README.md:418-420"),
    ]
    safe_state = ("the :STOP request has an empty queried instrument error queue and the latch refuses new "
                  "acquisition commands; acquisition state is not sensed and electrical inputs remain connected")

    def _check_errors(self, errors):
        if not isinstance(errors, list) or errors:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"instrument error queue was not clear: {errors!r}")

    def _check_native_errors(self):
        self._check_errors(self.native.errors())

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN? raw reply)")
    def identity(self):
        return str(self.native.identify().get("raw") or "")

    @read("channel1_display", type="boolean", description="Channel 1 shown on screen")
    def channel1_display(self):
        return bool(_channel(self.native.status(), 1).get("display"))

    @read("channel1_coupling", type="string", description="Channel 1 input coupling")
    def channel1_coupling(self):
        return str(_channel(self.native.status(), 1).get("coupling") or "")

    @read("channel1_probe_ratio", unit="1", description="Channel 1 probe attenuation ratio")
    def channel1_probe_ratio(self):
        return _number(_channel(self.native.status(), 1).get("probe"))

    @read("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div")
    def channel1_scale_v_per_div(self):
        return _number(_channel(self.native.status(), 1).get("scale"))

    @read("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts")
    def channel1_offset_v(self):
        return _number(_channel(self.native.status(), 1).get("offset"))

    @read("timebase_mode", type="string", description="Timebase mode (MAIN, XY or ROLL)")
    def timebase_mode(self):
        return str((self.native.status().get("timebase") or {}).get("mode") or "")

    @read("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div")
    def timebase_scale_s_per_div(self):
        return _number((self.native.status().get("timebase") or {}).get("scale"))

    @read("timebase_position_s", unit="s", description="Timebase horizontal position in seconds")
    def timebase_position_s(self):
        return _number((self.native.status().get("timebase") or {}).get("position"))

    @read("sample_rate_hz", unit="Hz", description="Sample rate the instrument derives from the timebase")
    def sample_rate_hz(self):
        return _number((self.native.status().get("timebase") or {}).get("sample_rate"))

    @read("trigger_source", type="string", description="Edge-trigger source")
    def trigger_source(self):
        return str((self.native.status().get("trigger") or {}).get("source") or "")

    @read("trigger_level_v", unit="V", description="Edge-trigger level in volts")
    def trigger_level_v(self):
        return _number((self.native.status().get("trigger") or {}).get("level"))

    @read("trigger_slope", type="string", description="Edge-trigger slope")
    def trigger_slope(self):
        return str((self.native.status().get("trigger") or {}).get("slope") or "")

    @read("trigger_sweep", type="string", description="Trigger sweep mode")
    def trigger_sweep(self):
        return str((self.native.status().get("trigger") or {}).get("sweep") or "")

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("channel1_display", type="boolean", description="Show channel 1")
    def set_channel1_display(self, value):
        self.native.configure_channel(1, display=bool(value))
        self._check_native_errors()
        return bool(_channel(self.native.status(), 1).get("display"))

    @write("channel1_coupling", type="string", description="Channel 1 input coupling",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{WEB}:119"))
    def set_channel1_coupling(self, value):
        self.native.configure_channel(1, coupling=str(value))
        self._check_native_errors()
        return str(_channel(self.native.status(), 1).get("coupling") or "")

    @write("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div",
           limit=Limit.operator_required(
               "the clone lists the 1-2-5 V/div table (osc/scales.py:15-16) but says the table endpoints follow "
               "the manual and must be checked on the unit; the site supplies the range of its instrument"))
    def set_channel1_scale_v_per_div(self, value):
        self.native.configure_channel(1, scale=float(value))
        self._check_native_errors()
        return _number(_channel(self.native.status(), 1).get("scale"))

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "the clone states no offset range and its own clamp is only a guard (osc/scales.py:25-31); the "
               "limit depends on the vertical scale and the probe ratio of the installed instrument"))
    def set_channel1_offset_v(self, value):
        self.native.configure_channel(1, offset=float(value))
        self._check_native_errors()
        return _number(_channel(self.native.status(), 1).get("offset"))

    @write("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div",
           limit=Limit.operator_required(
               "the clone lists the 1-2-5 s/div table (osc/scales.py:18-23) but says the table endpoints follow "
               "the manual and must be checked on the unit; the site supplies the range of its instrument"))
    def set_timebase_scale_s_per_div(self, value):
        self.native.configure_timebase(scale=float(value))
        self._check_native_errors()
        return _number((self.native.status().get("timebase") or {}).get("scale"))

    @write("timebase_position_s", unit="s", description="Timebase horizontal position in seconds",
           limit=Limit.operator_required(
               "the clone states no horizontal-position range; its clamp (osc/scales.py:25-31) is a guard, not the "
               "instrument bound, which depends on the timebase scale"))
    def set_timebase_position_s(self, value):
        self.native.configure_timebase(position=float(value))
        self._check_native_errors()
        return _number((self.native.status().get("timebase") or {}).get("position"))

    @write("trigger_source", type="string", description="Edge-trigger source",
           limit=Limit.operator_required("the operator lists trigger sources present on the installed instrument"))
    def set_trigger_source(self, value):
        self.native.configure_trigger(source=str(value))
        self._check_native_errors()
        return str((self.native.status().get("trigger") or {}).get("source") or "")

    @write("trigger_level_v", unit="V", description="Edge-trigger level in volts",
           limit=Limit.operator_required("the web clamp is a control guard, not an instrument range; "
                                         "the operator supplies the trigger-level envelope"))
    def set_trigger_level_v(self, value):
        self.native.configure_trigger(level=float(value))
        self._check_native_errors()
        return _number((self.native.status().get("trigger") or {}).get("level"))

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.valiantandupright.identify.v1", description="Read the *IDN? identity of the instrument",
            output={"identity": Field("string", description="Raw *IDN? reply"),
                    "manufacturer": Field("string", description="Manufacturer field"),
                    "model": Field("string", description="Model field"),
                    "serial": Field("string", description="Serial number field"),
                    "firmware": Field("string", description="Firmware field")})
    def identify_action(self):
        data = self.native.identify()
        return {"identity": str(data.get("raw") or ""),
                "manufacturer": str(data.get("manufacturer") or ""),
                "model": str(data.get("model") or ""),
                "serial": str(data.get("serial") or ""),
                "firmware": str(data.get("firmware") or "")}

    @action(name="x-cap.valiantandupright.measure.v1",
            description="Read one scalar automatic measurement on one channel",
            input={"channel": Field("integer", unit="1", description="Installed analog channel index",
                                    limit=Limit.operator_required("the upstream channel count is configurable; "
                                                                  "the operator lists installed channels")),
                   "item": Field("string", description="Automatic measurement item",
                                 enum=list(MEASUREMENT_ITEMS))},
            output={"channel": Field("integer", unit="1", description="Channel the measurement was taken on"),
                    "item": Field("string", description="Measurement item"),
                    "value": Field("number", nullable=True,
                                   description="Measured value, or null when the instrument reports no measurement")})
    def measure(self, channel, item):
        values = self.native.measure(int(channel), [str(item)])
        self._check_native_errors()
        return {"channel": int(channel), "item": str(item), "value": values[str(item)]}

    @action(name="x-cap.valiantandupright.capture.v1",
            description="Capture one waveform and return the decimated time and voltage samples with statistics",
            input={"channel": Field("integer", unit="1", description="Installed analog channel index",
                                    limit=Limit.operator_required("the upstream channel count is configurable; "
                                                                  "the operator lists installed channels"))},
            output={"channel": Field("integer", unit="1", description="Channel captured"),
                    "points": Field("integer", unit="1", description="Points acquired before decimation"),
                    "returned_points": Field("integer", unit="1", description="Samples returned"),
                    "decimation": Field("integer", unit="1", description="Envelope decimation factor"),
                    "time_span_s": Field("number", unit="s", description="Time span of the captured record"),
                    "sample_rate_hz": Field("number", unit="Hz", nullable=True,
                                            description="Sample rate derived from the time increment"),
                    "time_s": Field("array", items=Field("number"), description="Sample times in seconds"),
                    "voltage_v": Field("array", items=Field("number"), description="Sample voltages in volts"),
                    "stats": Field("object", description="Statistics of the complete captured record",
                                   properties={
                                       "vmin": Field("number", unit="V", nullable=True,
                                                     description="Minimum voltage"),
                                       "vmax": Field("number", unit="V", nullable=True,
                                                     description="Maximum voltage"),
                                       "vmean": Field("number", unit="V", nullable=True, description="Mean voltage"),
                                       "vpp": Field("number", unit="V", nullable=True,
                                                    description="Peak-to-peak voltage"),
                                       "vrms": Field("number", unit="V", nullable=True, description="RMS voltage")})})
    def capture(self, channel):
        result = self.native.capture(int(channel))
        self._check_errors(result["warnings"])
        stats = result["stats"]
        return {"channel": int(result["channel"]),
                "points": int(result["points"]),
                "returned_points": int(result["returned_points"]),
                "decimation": int(result["decimation"]),
                "time_span_s": float(result["time_span"]),
                "sample_rate_hz": _number(result["sample_rate"]),
                "time_s": [float(value) for value in result["times"]],
                "voltage_v": [float(value) for value in result["volts"]],
                "stats": {key: _number(stats.get(source)) for key, source in
                          [("vmin", "min"), ("vmax", "max"), ("vmean", "mean"), ("vpp", "vpp"), ("vrms", "rms")]}}

    @action(name="x-cap.valiantandupright.configure_channel.v1",
            description="Set channel display, coupling, probe, vertical scale and offset on one channel",
            input={"channel": Field("integer", unit="1", description="Installed analog channel index",
                                    limit=Limit.operator_required("the upstream channel count is configurable; "
                                                                  "the operator lists installed channels")),
                   "scale_v_per_div": Field("number", unit="V", required=False, nullable=True,
                                            description="Vertical scale in V/div",
                                            limit=Limit.operator_required(
                                                "the clone lists a 1-2-5 V/div table but says its endpoints need "
                                                "a check on the unit; the site supplies the range")),
                   "offset_v": Field("number", unit="V", required=False, nullable=True,
                                     description="Vertical offset in volts",
                                     limit=Limit.operator_required(
                                         "the clone states no offset range; it depends on the vertical scale and "
                                         "probe ratio of the installed instrument")),
                   "coupling": Field("string", required=False, nullable=True, enum=list(COUPLINGS),
                                     description="Input coupling (DC or AC)"),
                   "display": Field("boolean", required=False, nullable=True, description="Show this channel"),
                   "probe_ratio": Field("number", unit="1", required=False, nullable=True, enum=list(PROBES),
                                        description="Probe attenuation ratio",
                                        limit=Limit(allowed=PROBES, source="upstream_code", ref=f"{WEB}:123"))},
            output={"channel": Field("integer", unit="1", description="Channel configured"),
                    "scale_v_per_div": Field("number", unit="V", nullable=True, description="Scale after the write"),
                    "offset_v": Field("number", unit="V", nullable=True, description="Offset after the write"),
                    "coupling": Field("string", nullable=True, description="Coupling after the write"),
                    "display": Field("boolean", nullable=True, description="Display state after the write"),
                    "probe_ratio": Field("number", unit="1", nullable=True,
                                         description="Probe ratio after the write")})
    def configure_channel(self, channel, scale_v_per_div=None, offset_v=None, coupling=None, display=None,
                          probe_ratio=None):
        options = {"scale": scale_v_per_div, "offset": offset_v, "coupling": coupling, "display": display,
                   "probe": probe_ratio}
        payload = {name: value for name, value in options.items() if value is not None}
        self.native.configure_channel(int(channel), **payload)
        self._check_native_errors()
        current = _channel(self.native.status(), int(channel))
        return {"channel": int(channel),
                "scale_v_per_div": _number(current.get("scale")),
                "offset_v": _number(current.get("offset")),
                "coupling": None if current.get("coupling") is None else str(current.get("coupling")),
                "display": None if current.get("display") is None else bool(current.get("display")),
                "probe_ratio": _number(current.get("probe"))}

    @action(name="x-cap.valiantandupright.configure_timebase.v1",
            description="Set the timebase mode, scale and horizontal position",
            input={"scale_s_per_div": Field("number", unit="s", required=False, nullable=True,
                                            description="Timebase scale in s/div",
                                            limit=Limit.operator_required(
                                                "the clone lists a 1-2-5 s/div table but says its endpoints need a "
                                                "check on the unit; the site supplies the range")),
                   "position_s": Field("number", unit="s", required=False, nullable=True,
                                       description="Horizontal position in seconds",
                                       limit=Limit.operator_required(
                                           "the clone states no horizontal-position range; it depends on the "
                                           "timebase scale of the installed instrument")),
                   "mode": Field("string", required=False, nullable=True, enum=list(TIMEBASE_MODES),
                                 description="Timebase mode (MAIN, XY or ROLL)")},
            output={"scale_s_per_div": Field("number", unit="s", nullable=True,
                                             description="Timebase scale after the write"),
                    "position_s": Field("number", unit="s", nullable=True,
                                        description="Horizontal position after the write"),
                    "mode": Field("string", nullable=True, description="Timebase mode after the write")})
    def configure_timebase(self, scale_s_per_div=None, position_s=None, mode=None):
        self.native.configure_timebase(scale=scale_s_per_div, position=position_s, mode=mode)
        self._check_native_errors()
        current = self.native.status().get("timebase") or {}
        return {"scale_s_per_div": _number(current.get("scale")),
                "position_s": _number(current.get("position")),
                "mode": None if current.get("mode") is None else str(current.get("mode"))}

    @action(name="x-cap.valiantandupright.configure_trigger.v1",
            description="Set the edge-trigger source, level, slope and sweep",
            input={"source": Field("string", required=False, nullable=True, enum=list(TRIGGER_SOURCES),
                                   description="Trigger source (CHANNEL1..4 or EXT)",
                                   limit=Limit.operator_required("the operator lists trigger sources present "
                                                                 "on the installed instrument")),
                   "level_v": Field("number", unit="V", required=False, nullable=True,
                                    description="Trigger level in volts",
                                    limit=Limit.operator_required("the web clamp is a control guard, not an instrument range; "
                                                                  "the operator supplies the trigger-level envelope")),
                   "slope": Field("string", required=False, nullable=True, enum=list(SLOPES),
                                  description="Edge slope (POS, NEG or EITH)"),
                   "sweep": Field("string", required=False, nullable=True, enum=list(SWEEPS),
                                  description="Sweep mode (AUTO or NORM)")},
            output={"source": Field("string", nullable=True, description="Trigger source after the write"),
                    "level_v": Field("number", unit="V", nullable=True, description="Trigger level after the write"),
                    "slope": Field("string", nullable=True, description="Slope after the write"),
                    "sweep": Field("string", nullable=True, description="Sweep mode after the write")})
    def configure_trigger(self, source=None, level_v=None, slope=None, sweep=None):
        self.native.configure_trigger(source=source, level=level_v, slope=slope, sweep=sweep)
        self._check_native_errors()
        current = self.native.status().get("trigger") or {}
        return {"source": None if current.get("source") is None else str(current.get("source")),
                "level_v": _number(current.get("level")),
                "slope": None if current.get("slope") is None else str(current.get("slope")),
                "sweep": None if current.get("sweep") is None else str(current.get("sweep"))}

    @action(name="x-cap.valiantandupright.run.v1", description="Start continuous acquisitions (:RUN)",
            output={"acquire_points": Field("integer", unit="1",
                                            description="Waveform points reported by the acquisition settings")})
    def run(self):
        self.native.run()
        self._check_native_errors()
        return {"acquire_points": int(self.native.status()["acquire"]["points"])}

    @action(name="x-cap.valiantandupright.single.v1", description="Arm one acquisition (:SINGle)",
            output={"acquire_points": Field("integer", unit="1",
                                            description="Waveform points reported by the acquisition settings")})
    def single(self):
        self.native.single()
        self._check_native_errors()
        return {"acquire_points": int(self.native.status()["acquire"]["points"])}

    @action(name="x-cap.valiantandupright.autoscale.v1",
            description="Auto-configure vertical, timebase and trigger settings (:AUToscale)",
            output={"channel1_scale_v_per_div": Field("number", unit="V", nullable=True,
                                                      description="Channel 1 scale after autoscale"),
                    "channel1_offset_v": Field("number", unit="V", nullable=True,
                                               description="Channel 1 offset after autoscale"),
                    "timebase_scale_s_per_div": Field("number", unit="s", nullable=True,
                                                      description="Timebase scale after autoscale")})
    def autoscale(self):
        self.native.autoscale()
        self._check_native_errors()
        current = self.native.status()
        channel = _channel(current, 1)
        return {"channel1_scale_v_per_div": _number(channel.get("scale")),
                "channel1_offset_v": _number(channel.get("offset")),
                "timebase_scale_s_per_div": _number((current.get("timebase") or {}).get("scale"))}

    @action(name="x-cap.valiantandupright.stop_acquisition.v1", safe_state=True,
            description="Send :STOP and require an empty instrument error queue; acquisition state is not sensed",
            output={"command": Field("string", description="The SCPI command the native stop sent")})
    def stop_acquisition(self):
        self.native.stop()
        self._check_native_errors()
        return {"command": ":STOP"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Send STOP and check the instrument error queue; acquisition state is not sensed."""
        self.native.stop()
        self._check_native_errors()

    def teardown(self):
        self.native.close()
