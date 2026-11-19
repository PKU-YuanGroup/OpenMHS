"""OpenMHS driver for gh.zinntikumugai/rigol-oscilloscope-mcp: RIGOL oscilloscopes over SCPI.

A direct Driver over the upstream high-level class
``rigol_oscilloscope_mcp.driver.scope:ScopeDriver``.  The card proposes a ``ScpiDriver`` (family ``scpi``,
decision ``family-config``), but the upstream interface is an object whose methods assemble commands from a
model profile and whose waveform and screenshot reads are IEEE 488.2 binary blocks; a fixed command table cannot
reproduce those lines or carry the binary data (G7).  This package is therefore a direct Driver over the upstream
class with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in RESULT.json).

* the served resource is analog channel 1 plus the shared timebase, edge trigger and acquisition;
* reads: identity, channel 1 display, coupling, vertical scale, offset, probe ratio and bandwidth limit, the
  timebase scale and position, the trigger type, sweep mode and acquisition status;
* writes: channel 1 display, coupling, vertical scale and offset, and the timebase scale and position; the vertical
  scale and offset and the timebase scale and position are ``Limit.operator_required`` because the clone's generic
  profile states no numeric range for them and the range depends on the model and probe;
* actions: one scalar automatic measurement, edge-trigger configuration, run, and a ``safe_state`` acquisition
  stop; the trigger source, slope and sweep use the profile's declared semantic spellings, and the trigger level and
  holdoff are ``Limit.operator_required``;
* the e-stop sends the checked native ``:STOP`` and requires a ``STOP`` trigger-status readback. A missing or
  different status leaves the stop failed and latched; independently enabled AFG output is unchanged.

NOT COVERED: the waveform array and the screenshot array.  ``read_waveform`` transfers a ``:WAVeform:DATA?``
binary block as a preamble plus samples, and ``capture_screenshot_bytes`` returns image bytes; no catalogue class
or artifact binding used here carries a trace array, so this package serves the scalar measurements and settings
of the oscilloscope, not the samples or the screen image.  The AFG, decode, math, cursor, histogram, meter and
reference subsystems are also not exposed.

Every Fact and Limit cites a line of the clone at the pinned commit (54a1061e23910d31cb30335fa76600409d92b951).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SCOPE = "src/rigol_oscilloscope_mcp/driver/scope.py"
SESSION = "src/rigol_oscilloscope_mcp/driver/session.py"
GENERIC = "src/rigol_oscilloscope_mcp/profiles/data/rigol-generic.yaml"
PARSERS = "src/rigol_oscilloscope_mcp/driver/parsers.py"
LAN = "src/rigol_oscilloscope_mcp/transport/lan.py"
CONNECTION = "src/rigol_oscilloscope_mcp/service/connection.py"

#: The one analog channel this package serves; the upstream accepts CH1-CH<analog_channels> (scope.py:855-871).
CHANNEL = "CH1"

#: Coupling spellings of the upstream constant (scope.py:146).
COUPLINGS = ["DC", "AC", "GND"]

#: Trigger sources the clone's source parser accepts for analog channels and the non-channel forms
#: (scope.py:597, 603); the analog channel count itself comes from the resolved model profile.
TRIGGER_SOURCES = ["CH1", "CH2", "CH3", "CH4", "EXT", "EXT5", "ACLINE"]

#: Semantic trigger slope names of the profile dialect (rigol-generic.yaml:25-28).
TRIGGER_SLOPES = ["rising", "falling", "either"]

#: Semantic sweep names the upstream parser maps (parsers.py:24-33).
TRIGGER_SWEEPS = ["auto", "normal", "single"]

#: The five measurement items the generic profile declares (rigol-generic.yaml:11).
MEASURE_ITEMS = ["frequency", "period", "vpp", "vmax", "vmin"]


class RigolOscilloscopeMcp(Driver):
    device_id = "rigol-oscilloscope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "rigol_oscilloscope_mcp.driver.scope:ScopeDriver"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScopeDriver"}
    vendor = "RIGOL Technologies"
    model = "RIGOL oscilloscope (profile-driven SCPI)"
    display_name = "RIGOL oscilloscope (rigol_oscilloscope_mcp.ScopeDriver)"
    tags = ["oscilloscope", "rigol", "scpi", "lan", "usb", "instrument"]
    facts = [
        Fact("ScopeDriver is the profile-driven driver that turns semantic operations into RIGOL SCPI and "
             "parses the replies", source="upstream_code", ref=f"{SCOPE}:836-837"),
        Fact("identify queries *IDN? and splits the reply into manufacturer, model, serial and firmware",
             source="upstream_code", ref=f"{SCOPE}:895-909"),
        Fact("get_channel reads the display, vertical scale, offset, coupling, impedance, probe ratio and "
             "bandwidth limit of one channel", source="upstream_code", ref=f"{SCOPE}:955-971"),
        Fact("get_timebase reads the main timebase scale and offset and the sample rate and memory depth",
             source="upstream_code", ref=f"{SCOPE}:978-987"),
        Fact("get_trigger reads the current trigger type's subtree plus the sweep mode and trigger status",
             source="upstream_code", ref=f"{SCOPE}:1025-1046"),
        Fact("measure queries :MEASure:ITEM? for each requested item and reports a sentinel value as unknown",
             source="upstream_code", ref=f"{SCOPE}:1082-1129"),
        Fact("configure_trigger writes the trigger mode first when asked, then each requested subtree item, "
             "and reads every setting back", source="upstream_code", ref=f"{SCOPE}:1449-1518"),
        Fact("set_channel_scale writes :CHANnelN:SCALe and returns the read-back value",
             source="upstream_code", ref=f"{SCOPE}:1358-1364"),
        Fact("set_timebase_scale writes :TIMebase:MAIN:SCALe and returns the read-back value",
             source="upstream_code", ref=f"{SCOPE}:1435-1439"),
        Fact("run writes :RUN and stop writes :STOP through the checked SCPI session",
             source="upstream_code", ref=f"{SCOPE}:3353-3357"),
        Fact("get_trigger_status queries :TRIGger:STATus? and strips and uppercases its reply",
             source="upstream_code", ref=f"{SCOPE}:1050-1052"),
        Fact("write_checked writes the command then calls check_error, which queries ERROR_QUERY and raises "
             "ScopeError on an error reply",
             source="upstream_code", ref=f"{SESSION}:96-122"),
        Fact("The generic profile declares four analog channels, the measurements frequency, period, vpp, "
             "vmax and vmin, edge trigger, screenshot and waveform download",
             source="upstream_code", ref=f"{GENERIC}:6-24"),
        Fact("The screenshot and waveform reads return IEEE 488.2 binary blocks through query_binary",
             source="upstream_code", ref=f"{SCOPE}:1307-1346"),
        Fact("read_waveform writes the waveform source, mode and format, reads the preamble and then "
             "transfers :WAVeform:DATA? as a binary block", source="upstream_code", ref=f"{SCOPE}:1326-1346"),
        Fact("The LAN transport is a raw TCP socket whose default port is 5555",
             source="upstream_code", ref=f"{LAN}:20-34"),
        Fact("The upstream connection resolves the model profile from the *IDN? reply and builds a "
             "ScopeDriver over the session", source="upstream_code", ref=f"{CONNECTION}:169-172"),
    ]
    safe_state = ("acquisition reports STOP after the checked :STOP command; no electrical isolation is claimed "
                  "and any independently enabled AFG output is unchanged; a missing or different status fails the stop")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity from *IDN?")
    def identity(self):
        idn = self.native.identify()
        return f"{idn.manufacturer},{idn.model},{idn.serial},{idn.firmware}"

    @read("channel1_display", type="boolean", description="Channel 1 shown on screen")
    def channel1_display(self):
        return bool(self.native.get_channel(CHANNEL).enabled)

    @read("channel1_coupling", type="string", description="Channel 1 input coupling")
    def channel1_coupling(self):
        return str(self.native.get_channel(CHANNEL).coupling)

    @read("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in volts per division")
    def channel1_scale_v_per_div(self):
        return float(self.native.get_channel(CHANNEL).scale_v_per_div)

    @read("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts")
    def channel1_offset_v(self):
        return float(self.native.get_channel(CHANNEL).offset_v)

    @read("channel1_probe_ratio", unit="1", description="Channel 1 probe attenuation ratio")
    def channel1_probe_ratio(self):
        return float(self.native.get_channel(CHANNEL).probe_ratio)

    @read("channel1_bandwidth_limit", type="boolean",
          description="Channel 1 bandwidth limit enabled")
    def channel1_bandwidth_limit(self):
        return bool(self.native.get_channel(CHANNEL).bandwidth_limit)

    @read("timebase_scale_s_per_div", unit="s", description="Main timebase scale in seconds per division")
    def timebase_scale_s_per_div(self):
        return float(self.native.get_timebase().scale_s_per_div)

    @read("timebase_position_s", unit="s", description="Main timebase horizontal position in seconds")
    def timebase_position_s(self):
        return float(self.native.get_timebase().position_s)

    @read("trigger_type", type="string", description="Current trigger type reported by :TRIGger:MODE?")
    def trigger_type(self):
        return str(self.native.get_trigger().type)

    @read("trigger_sweep_mode", type="string", description="Trigger sweep mode")
    def trigger_sweep_mode(self):
        return str(self.native.get_trigger().sweep_mode)

    @read("trigger_status", type="string", description="Raw :TRIGger:STATus? value, for example TD or STOP")
    def trigger_status(self):
        return str(self.native.get_trigger_status())

    # -- writes --------------------------------------------------------------------------------------------------
    @write("channel1_display", type="boolean", description="Show channel 1")
    def set_channel1_display(self, value):
        return bool(self.native.set_channel_enabled(CHANNEL, bool(value)))

    @write("channel1_coupling", type="string", description="Channel 1 input coupling",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{SCOPE}:146"))
    def set_channel1_coupling(self, value):
        return str(self.native.set_channel_coupling(CHANNEL, str(value)))

    @write("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in volts per division",
           limit=Limit.operator_required(
               "the generic profile states no vertical-scale range; the model and probe ratio set it, so the "
               "operator supplies the bound (scope.py:1358-1363)"))
    def set_channel1_scale_v_per_div(self, value):
        return float(self.native.set_channel_scale(CHANNEL, float(value)))

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "the generic profile states no offset range; it depends on the vertical scale and probe ratio, "
               "so the operator supplies the bound (scope.py:1366-1371)"))
    def set_channel1_offset_v(self, value):
        return float(self.native.set_channel_offset(CHANNEL, float(value)))

    @write("timebase_scale_s_per_div", unit="s", description="Main timebase scale in seconds per division",
           limit=Limit.operator_required(
               "the generic profile states no timebase range; the model and acquisition mode set it, so the "
               "operator supplies the bound (scope.py:1435-1439)"))
    def set_timebase_scale_s_per_div(self, value):
        return float(self.native.set_timebase_scale(float(value)))

    @write("timebase_position_s", unit="s", description="Main timebase horizontal position in seconds",
           limit=Limit.operator_required(
               "the generic profile states no horizontal-position range; the timebase scale sets it, so the "
               "operator supplies the bound (scope.py:1441-1445)"))
    def set_timebase_position_s(self, value):
        return float(self.native.set_timebase_position(float(value)))

    # -- actions -------------------------------------------------------------------------------------------------
    @action(name="x-cap.zinntikumugai.measure.v1",
            description="Read one scalar automatic measurement on channel 1",
            input={"item": Field("string", description="Measurement item to query",
                                 enum=MEASURE_ITEMS)},
            output={"value": Field("number", description="Measured value in the item's unit"),
                    "key": Field("string", description="SI-unit key the clone uses for the measurement")})
    def measure(self, item):
        results = self.native.measure(CHANNEL, [item])
        if not results or results[0].value is None:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the oscilloscope reports no value for measurement {item!r}")
        result = results[0]
        return {"value": float(result.value), "key": str(result.key)}

    @action(name="x-cap.zinntikumugai.configure_trigger.v1",
            description="Select the edge trigger and apply supplied settings; omitted edge settings are unchanged",
            input={
                "source": Field("string", description="Trigger source",
                                limit=Limit(allowed=TRIGGER_SOURCES, source="upstream_code",
                                            ref=f"{SCOPE}:597-603")),
                "level_v": Field("number", unit="V", description="Trigger level in volts",
                                 limit=Limit.operator_required(
                                     "the clone states no trigger-level range; it depends on the source, "
                                     "vertical scale and offset (scope.py:1449-1518)")),
                "slope": Field("string", description="Edge slope",
                               limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code",
                                           ref=f"{GENERIC}:25-28")),
                "sweep_mode": Field("string", description="Trigger sweep mode",
                                    limit=Limit(allowed=TRIGGER_SWEEPS, source="upstream_code",
                                                ref=f"{PARSERS}:24-33")),
                "holdoff_s": Field("number", unit="s", description="Trigger holdoff in seconds",
                                   limit=Limit.operator_required(
                                       "the clone states no holdoff range; it depends on the timebase and "
                                       "trigger mode (scope.py:1449-1518)")),
            },
            output={"type": Field("string", description="Trigger type after the change"),
                    "source": Field("string", description="Trigger source after the change", required=False),
                    "level_v": Field("number", unit="V", description="Trigger level after the change",
                                     required=False),
                    "slope": Field("string", description="Edge slope after the change", required=False),
                    "sweep_mode": Field("string", description="Sweep mode after the change")})
    def configure_trigger(self, source=None, level_v=None, slope=None, sweep_mode=None, holdoff_s=None):
        self.native.configure_trigger(type="edge", source=source, level_v=level_v, slope=slope,
                                      sweep_mode=sweep_mode, holdoff_s=holdoff_s)
        state = self.native.get_trigger()
        applied = {"type": str(state.type), "sweep_mode": str(state.sweep_mode)}
        if state.source is not None:
            applied["source"] = str(state.source)
        if state.level_v is not None:
            applied["level_v"] = float(state.level_v)
        if state.slope is not None:
            applied["slope"] = str(state.slope)
        return applied

    @action(name="x-cap.zinntikumugai.run.v1", description="Start continuous acquisitions (:RUN)",
            output={"trigger_status": Field("string", description="Trigger status after :RUN")})
    def run(self):
        self.native.run()
        return {"trigger_status": str(self.native.get_trigger_status())}

    @action(name="x-cap.zinntikumugai.stop_acquisition.v1", safe_state=True,
            description="Stop acquisitions (:STOP, the safe state); it takes no input",
            output={"trigger_status": Field("string", description="Trigger status after :STOP")})
    def stop_acquisition(self):
        return {"trigger_status": self._stop_acquisition()}

    # -- safety --------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Require the native stop's error check and an acquisition STOP read-back."""
        self._stop_acquisition()

    def _stop_acquisition(self):
        self.native.stop()
        status = self.native.get_trigger_status()
        if not isinstance(status, str) or status.strip().upper() != "STOP":
            raise DriverFailed("MHS.SAFETY.SAFE_STATE_UNREACHED",
                               f"acquisition stop was not confirmed (trigger status {status!r})")
        return "STOP"

    def teardown(self):
        session = getattr(self.native, "session", None)
        if session is not None:
            session.transport.close()
