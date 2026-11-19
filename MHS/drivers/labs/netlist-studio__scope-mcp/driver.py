"""OpenMHS driver for gh.netlist-studio/scope-mcp: a Keysight/Agilent MSOX2024A oscilloscope over SCPI.

A direct Driver over the upstream high-level class ``scope:Scope``.  The card proposes a ``ScpiDriver`` (family
``scpi``, decision ``family-config``), but every upstream command is assembled from parts: the channel number is
formatted into ``:CHANnel<n>:`` and the trigger source into ``CHANnel<n>`` (``scope.py:80``, ``122``), the waveform
and screenshot replies are IEEE 488.2 binary blocks (``scope.py:210-232``, ``317-318``), and ``set_trigger`` writes
a sequence of commands only for edge mode (``scope.py:118-124``).  A fixed text command table cannot reproduce those
lines or carry those replies, so this package is a direct Driver over the upstream class with a ``native.py``
factory (DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the identity and the OPERegister condition; channel 1 scale, offset, coupling, display and bandwidth limit;
  the timebase scale, delay and mode; the trigger mode, edge source, level, slope and sweep;
* writes: channel 1 scale, offset, coupling, display and bandwidth limit; the timebase scale and delay; the
  trigger source channel, level and slope.  The numeric spans and the trigger level are ``Limit.operator_required``
  because the clone states no numeric range for them;
* actions: one scalar automatic measurement, continuous run, one single acquisition and stop;
* the e-stop sends the native stop (``:STOP``) and confirms the RUN bit is clear before reporting acquisition
  stopped. It does not stop external equipment attached to the oscilloscope.

NOT COVERED: the waveform array, the PNG screenshot and the UART serial decode.  ``get_waveform`` returns time and
voltage arrays from an IEEE 488.2 block (``scope.py:188-232``), ``screenshot`` returns PNG bytes
(``scope.py:315-318``) and ``get_serial_data`` returns decoded text rows (``scope.py:278-297``); no catalogue class
of this package carries those arrays, so this package serves the scalar measurements and the settings of the
oscilloscope, not the samples.  ``measure_all`` and ``get_state`` are not exposed as actions either; the runtime
already reads every state field.

Every Fact and Limit cites a line of the clone at the pinned commit (877a4f6324a581f3b7d4c8de57d719b258d9d9f0).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The one analog channel whose settings this package serves; the MCP tool schema accepts channels 1 to 4
#: (scope_server.py:108), and this package reads and writes channel 1.
CHANNEL = 1

#: The automatic measurement names of the upstream PARAMETERS map (scope.py:137-151).
MEASUREMENTS = [
    "frequency", "period", "vpp", "vrms", "vmax", "vmin", "vaverage",
    "duty", "rise", "fall", "overshoot", "preshoot", "width",
]

#: The couplings the upstream set_channel documents (scope.py:79).
COUPLINGS = ["AC", "DC", "GND"]

#: The slopes the upstream set_trigger documents (scope.py:112).
SLOPES = ["positive", "negative", "either"]


def _channel_limit() -> Limit:
    return Limit(allowed=[1, 2, 3, 4], source="upstream_code", ref="scope_server.py:108",
                 reason="the MCP tool schema restricts the channel to 1, 2, 3 and 4")


def _trigger_source_limit() -> Limit:
    return Limit(allowed=[1, 2, 3, 4], source="upstream_code", ref="scope_server.py:152")


def _coupling_limit() -> Limit:
    return Limit(allowed=COUPLINGS, source="upstream_code", ref="scope.py:79")


def _slope_limit() -> Limit:
    return Limit(allowed=SLOPES, source="upstream_code", ref="scope.py:112")


def _measurement_limit() -> Limit:
    return Limit(allowed=MEASUREMENTS, source="upstream_code", ref="scope.py:137-151",
                 reason="the keys of the PARAMETERS command map")


def _number_is_unbounded(what: str) -> Limit:
    return Limit.operator_required(
        f"the clone states no numeric range for {what}; the operator supplies the bound for this bench")


def _scpi_bool(reply) -> bool:
    text = str(reply).strip().upper()
    if text in ("1", "ON", "TRUE"):
        return True
    if text in ("0", "OFF", "FALSE"):
        return False
    raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET", f"the scope returned an unexpected boolean {reply!r}")


def _source_channel(reply) -> int:
    digits = "".join(character for character in str(reply) if character.isdigit())
    if not digits:
        raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                           f"the scope returned an unexpected trigger source {reply!r}")
    return int(digits)


def _slope_name(reply) -> str:
    text = str(reply).strip().upper()
    if text.startswith("POS"):
        return "positive"
    if text.startswith("NEG"):
        return "negative"
    if text.startswith("EIT"):
        return "either"
    raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                       f"the scope returned an unexpected trigger slope {reply!r}")


class ScopeMcp(Driver):
    device_id = "msox2024a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "scope:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "Keysight Technologies"
    model = "InfiniiVision MSOX2024A"
    display_name = "Keysight/Agilent MSOX2024A oscilloscope (scope-mcp.Scope)"
    tags = ["oscilloscope", "keysight", "agilent", "msox2024a", "scpi", "visa", "ethernet"]
    facts = [
        Fact("The upstream is an MCP server for controlling a Keysight/Agilent oscilloscope over Ethernet",
             source="vendor_doc", ref="README.md:5"),
        Fact("The tested oscilloscope is the Agilent MSOX2024A with firmware 02.43.2018020635",
             source="vendor_doc", ref="README.md:9"),
        Fact("The constructor opens a VISA resource TCPIP0::<ip>::inst0::INSTR through pyvisa's pure-Python "
             "ResourceManager '@py'", source="upstream_code", ref="scope.py:15-16"),
        Fact("The VISA session uses a newline read terminator and a newline write terminator",
             source="upstream_code", ref="scope.py:18-19"),
        Fact("query sends a SCPI query and strips the reply; write sends SCPI text and ignores a blank command",
             source="upstream_code", ref="scope.py:23-28"),
        Fact("reset sends *RST and then *CLS", source="upstream_code", ref="scope.py:33-35"),
        Fact("run, stop, single and autoscale write :RUN, :STOP, :SINGle and :AUToscale",
             source="upstream_code", ref="scope.py:39-49"),
        Fact("set_timebase writes :TIMebase:SCALe in seconds per division and set_timebase_delay writes "
             ":TIMebase:DELay in seconds", source="upstream_code", ref="scope.py:53-59"),
        Fact("get_timebase reads the scale in seconds per division, the delay in seconds and the timebase mode",
             source="upstream_code", ref="scope.py:61-66"),
        Fact("set_channel configures the channel scale in V/div, offset in V, coupling AC|DC|GND, display and "
             "bandwidth limit", source="upstream_code", ref="scope.py:70-90"),
        Fact("get_channel reads the channel scale, offset, coupling, display and bandwidth limit",
             source="upstream_code", ref="scope.py:92-101"),
        Fact("set_trigger writes the trigger mode and, in edge mode, the edge source, slope and level in volts",
             source="upstream_code", ref="scope.py:105-124"),
        Fact("get_trigger reads the trigger mode, edge source, level in volts, slope and sweep",
             source="upstream_code", ref="scope.py:126-133"),
        Fact("The automatic measurement names are frequency, period, vpp, vrms, vmax, vmin, vaverage, duty, "
             "rise, fall, overshoot, preshoot and width", source="upstream_code", ref="scope.py:137-151"),
        Fact("A measurement above the no-measurement threshold is reported as 'no_signal'",
             source="upstream_code", ref="scope.py:168-174"),
        Fact("get_waveform requests an IEEE 488.2 binary block from :WAVeform:DATA? and returns time and voltage "
             "arrays", source="upstream_code", ref="scope.py:188-232"),
        Fact("get_serial_data arms a single acquisition, polls :OPERegister:CONDition? up to 100 times, "
             "breaking when the RUN bit (bit 3) clears, then reads the lister as an IEEE 488.2 block",
             source="upstream_code", ref="scope.py:283-294"),
        Fact("screenshot reads the display as a PNG binary block from :DISPlay:DATA?",
             source="upstream_code", ref="scope.py:315-318"),
        Fact("get_state returns the identity, timebase, trigger and channels 1 to 4",
             source="upstream_code", ref="scope.py:330-337"),
        Fact("The MCP tool schema restricts the channel to 1, 2, 3 and 4",
             source="upstream_code", ref="scope_server.py:108"),
        Fact("The MCP trigger tool restricts the slope to positive, negative or either",
             source="upstream_code", ref="scope_server.py:154"),
    ]
    safe_state = ("acquisition stopped with :STOP and the RUN bit (bit 3) of :OPERegister:CONDition? "
                  "read back clear; this does not stop any external circuit connected to the scope")

    # -- reads -------------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (the *IDN? reply)")
    def identity(self):
        return self.native.idn()

    @read("operation_condition", unit="1",
          description=":OPERegister:CONDition? bit mask; bit 3 is the RUN bit")
    def operation_condition(self):
        return self._operation_condition()

    @read("channel1_scale_v_per_div", unit="V", description="V/div")
    def channel1_scale_v_per_div(self):
        return float(self.native.get_channel(CHANNEL)["scale_v_per_div"])

    @read("channel1_offset_v", unit="V", description="V")
    def channel1_offset_v(self):
        return float(self.native.get_channel(CHANNEL)["offset_v"])

    @read("channel1_coupling", type="string", description="AC, DC or GND")
    def channel1_coupling(self):
        return str(self.native.get_channel(CHANNEL)["coupling"]).strip().upper()

    @read("channel1_enabled", type="boolean", description="Display")
    def channel1_enabled(self):
        return _scpi_bool(self.native.get_channel(CHANNEL)["display"])

    @read("channel1_bwlimit", type="boolean", description="Bandwidth limit")
    def channel1_bwlimit(self):
        return _scpi_bool(self.native.get_channel(CHANNEL)["bwlimit"])

    @read("timebase_scale_s_per_div", unit="s", description="s/div")
    def timebase_scale_s_per_div(self):
        return float(self.native.get_timebase()["scale_s_per_div"])

    @read("timebase_delay_s", unit="s", description="Trigger delay")
    def timebase_delay_s(self):
        return float(self.native.get_timebase()["delay_s"])

    @read("timebase_mode", type="string", description="Timebase mode as the scope reports it")
    def timebase_mode(self):
        return str(self.native.get_timebase()["mode"]).strip().upper()

    @read("trigger_mode", type="string", description="Trigger mode as the scope reports it")
    def trigger_mode(self):
        return str(self.native.get_trigger()["mode"]).strip().upper()

    @read("trigger_source_channel", unit="1", description="Channel 1 to 4")
    def trigger_source_channel(self):
        return _source_channel(self.native.get_trigger()["source"])

    @read("trigger_level_v", unit="V", description="V")
    def trigger_level_v(self):
        return float(self.native.get_trigger()["level_v"])

    @read("trigger_slope", type="string", description="Edge slope")
    def trigger_slope(self):
        return _slope_name(self.native.get_trigger()["slope"])

    @read("trigger_sweep", type="string", description="Trigger sweep mode as the scope reports it")
    def trigger_sweep(self):
        return str(self.native.get_trigger()["sweep"]).strip().upper()

    # -- writes ------------------------------------------------------------------------------------------------------
    @write("channel1_scale_v_per_div", unit="V", description="V/div",
           limit=_number_is_unbounded("the channel scale"))
    def set_channel1_scale_v_per_div(self, value):
        self.native.set_channel(CHANNEL, scale=value)
        return float(self.native.get_channel(CHANNEL)["scale_v_per_div"])

    @write("channel1_offset_v", unit="V", description="V",
           limit=_number_is_unbounded("the channel offset"))
    def set_channel1_offset_v(self, value):
        self.native.set_channel(CHANNEL, offset=value)
        return float(self.native.get_channel(CHANNEL)["offset_v"])

    @write("channel1_coupling", type="string", description="AC, DC or GND",
           limit=_coupling_limit())
    def set_channel1_coupling(self, value):
        self.native.set_channel(CHANNEL, coupling=value)
        return str(self.native.get_channel(CHANNEL)["coupling"]).strip().upper()

    @write("channel1_enabled", type="boolean", description="Display")
    def set_channel1_enabled(self, value):
        self.native.set_channel(CHANNEL, enabled=value)
        return _scpi_bool(self.native.get_channel(CHANNEL)["display"])

    @write("channel1_bwlimit", type="boolean", description="Bandwidth limit")
    def set_channel1_bwlimit(self, value):
        self.native.set_channel(CHANNEL, bwlimit=value)
        return _scpi_bool(self.native.get_channel(CHANNEL)["bwlimit"])

    @write("timebase_scale_s_per_div", unit="s", description="s/div",
           limit=_number_is_unbounded("the timebase scale"))
    def set_timebase_scale_s_per_div(self, value):
        self.native.set_timebase(value)
        return float(self.native.get_timebase()["scale_s_per_div"])

    @write("timebase_delay_s", unit="s", description="Trigger delay",
           limit=_number_is_unbounded("the timebase delay"))
    def set_timebase_delay_s(self, value):
        self.native.set_timebase_delay(value)
        return float(self.native.get_timebase()["delay_s"])

    @write("trigger_source_channel", unit="1", description="Channel 1 to 4",
           limit=_trigger_source_limit())
    def set_trigger_source_channel(self, value):
        return _source_channel(self._apply_trigger(source=int(value))["source"])

    @write("trigger_level_v", unit="V", description="V",
           limit=_number_is_unbounded("the trigger level"))
    def set_trigger_level_v(self, value):
        return float(self._apply_trigger(level=float(value))["level_v"])

    @write("trigger_slope", type="string", description="Edge slope",
           limit=_slope_limit())
    def set_trigger_slope(self, value):
        return _slope_name(self._apply_trigger(slope=str(value))["slope"])

    # -- actions -----------------------------------------------------------------------------------------------------
    @action(name="x-cap.netlist-studio.measure.v1",
            description="Run one scalar automatic measurement on one analog channel",
            input={
                "channel": Field("integer", unit="1", description="Analog channel 1 to 4",
                                 limit=_channel_limit()),
                "parameter": Field("string", description="Automatic measurement name",
                                   limit=_measurement_limit()),
            },
            output={
                "channel": Field("integer", unit="1", description="Measured analog channel"),
                "parameter": Field("string", description="Automatic measurement name"),
                "value": Field("number", description="Measured scalar in the unit of the parameter"),
            })
    def measure(self, channel, parameter):
        result = self.native.measure(int(channel), str(parameter))
        if not isinstance(result, (int, float)) or isinstance(result, bool):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the scope returned no numeric measurement: {result!r}")
        return {"channel": int(channel), "parameter": str(parameter), "value": float(result)}

    @action(name="x-cap.netlist-studio.run.v1",
            description="Start continuous acquisition (:RUN)",
            output={"operation_condition": Field("integer", unit="1",
                                                 description=":OPERegister:CONDition? after :RUN")})
    def run(self):
        self.native.run()
        return {"operation_condition": self._operation_condition()}

    @action(name="x-cap.netlist-studio.single.v1",
            description="Arm one acquisition (:SINGle)",
            output={"operation_condition": Field("integer", unit="1",
                                                 description=":OPERegister:CONDition? after :SINGle")})
    def single(self):
        self.native.single()
        return {"operation_condition": self._operation_condition()}

    @action(name="x-cap.netlist-studio.stop.v1",
            description="Stop acquisition (:STOP)",
            output={"operation_condition": Field("integer", unit="1",
                                                 description=":OPERegister:CONDition? after :STOP")})
    def stop_acquisition(self):
        self.stop()
        return {"operation_condition": self._operation_condition()}

    # -- safety ------------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        self.native.stop()
        if self._operation_condition() & 8:
            raise DriverFailed("MHS.DEVICE.FAULTED", "the scope still reports RUN after :STOP")

    def teardown(self):
        self.native.close()

    # -- helpers -----------------------------------------------------------------------------------------------------
    def _operation_condition(self) -> int:
        raw = self.native.query(":OPERegister:CONDition?")
        try:
            value = int(str(raw).strip())
            if value < 0:
                raise ValueError("negative operation-condition mask")
            return value
        except ValueError as exc:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               f"the scope returned an unexpected operation condition {raw!r}") from exc

    def _apply_trigger(self, *, source=None, level=None, slope=None):
        state = self.native.get_trigger()
        self.native.set_trigger(
            _source_channel(state["source"]) if source is None else source,
            float(state["level_v"]) if level is None else level,
            _slope_name(state["slope"]) if slope is None else slope,
        )
        return self.native.get_trigger()
