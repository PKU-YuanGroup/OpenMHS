"""OpenMHS driver for gh.antercreeper/keyscope-mcp: Keysight InfiniiVision oscilloscopes.

A direct Driver over the upstream high-level class ``keyscope_mcp.scope:Oscilloscope``.  The task card proposes a
``ScpiDriver`` (family ``scpi``, decision ``family-config``). This package instead binds the upstream object's
measurement and acquisition methods and its scalar settings through a direct Driver with a ``native.py`` factory
(DEVIATION FROM THE CARD). The source-backed waveform binary transfer is outside this package's scalar contract.

* the served resource is analog channel 1 plus the shared timebase, edge trigger and acquisition;
* reads: identity, channel-1 display, coupling, scale, offset and invert, the timebase scale and position, the
  edge-trigger source, level and slope, and the acquisition type and count;
* writes: channel-1 display, coupling, scale, offset and invert, the timebase scale and position, the trigger level
  and the acquisition type.  The clone states no numeric range for the scale, offset, timebase or trigger level, so
  those five writes are ``Limit.operator_required`` and ``site-limits.example.json`` is an example overlay;
* actions: one scalar automatic measurement on either channel, run, single, autoscale, reset to defaults, and a
  ``safe_state`` acquisition stop;
* the e-stop sends ``:STOP`` and requires a true ``*OPC?`` and a zero error code;
  the hardware factory closes the VISA session without upstream close()'s ``:RUN``.

NOT COVERED: the waveform array.  ``get_waveform`` transfers an IEEE 488.2 binary block (:WAVeform:DATA?) and
returns time and voltage arrays; no catalogue class carries an oscilloscope trace, so this package serves the
scalar measurements and the settings of the oscilloscope, not the samples.  The screenshot bytes (:DISPlay:DATA?),
the setup block (:SYSTem:SETup?), *LRN? and the arbitrary raw-command path are not exposed either.

Every Fact and Limit cites a line of the clone at the pinned commit (344dc93cf9f151672d0b07dc4b29f780ae38bd08).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SCOPE = "keyscope_mcp/scope.py"
DSL = "keyscope_mcp/dsl.py"

#: The analog channel this package serves; the DSL validates a channel against 1 and 2 (dsl.py:214).
CHANNEL = 1

#: Automatic measurement names accepted by the DSL and mapped to :MEASure:<item>? (dsl.py:436-439).
MEASUREMENTS = [
    "vpp", "vmax", "vmin", "vamp", "vtop", "vbase", "vavg", "vrms",
    "freq", "per", "rise", "fall", "pwid", "nwid", "duty", "over", "preshoot",
]

#: Coupling spellings the DSL writes (dsl.py:251-253).
COUPLINGS = ["AC", "DC"]

#: Acquisition type spellings the DSL writes (dsl.py:402-403).
ACQUIRE_TYPES = ["NORMal", "AVERage", "HRESolution", "PEAK"]


def _query_float(native, command: str) -> float:
    return float(native.query(command))


def _query_bool(native, command: str) -> bool:
    return bool(int(native.query(command)))


def _query_text(native, command: str) -> str:
    return native.query(command).strip().strip('"').upper()


def _operation_complete(native) -> bool:
    if native.opc() is not True:
        raise DriverFailed("MHS.DEVICE.FAULTED", "the scope did not acknowledge operation completion")
    code, message = native.get_error()
    if code != 0:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"scope error {code}: {message}")
    return True


class Keyscope(Driver):
    device_id = "keyscope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "keyscope_mcp.scope:Oscilloscope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOscilloscope"}
    vendor = "Keysight Technologies"
    model = "InfiniiVision EDUX1052G / DSOX1102G oscilloscope"
    display_name = "Keysight InfiniiVision oscilloscope (keyscope-mcp.Oscilloscope)"
    tags = ["oscilloscope", "keysight", "infiniivision", "edux1052g", "dsox1102g", "scpi", "visa"]
    facts = [
        Fact("The supported hardware table lists the EDUX1052G and DSOX1102G as verified and other "
             "InfiniiVision models as likely compatible",
             source="vendor_doc", ref="README.md:284-288"),
        Fact("The constructor creates pyvisa's pure-Python ResourceManager '@py'",
             source="upstream_code", ref=f"{SCOPE}:28-30"),
        Fact("connect() opens the VISA resource, sets the timeout and uses newline read and write terminators", source="upstream_code",
             ref=f"{SCOPE}:59-63"),
        Fact("The connection sets :WAVeform:UNSigned OFF and :WAVeform:BYTeorder LSBFirst for waveform transfers",
             source="upstream_code", ref=f"{SCOPE}:72-74"),
        Fact("idn() queries *IDN?", source="upstream_code", ref=f"{SCOPE}:242-243"),
        Fact("reset() writes *RST", source="upstream_code", ref=f"{SCOPE}:245-246"),
        Fact("opc() queries *OPC? and returns True only when the reply is '1'", source="upstream_code",
             ref=f"{SCOPE}:248-249"),
        Fact("run(), stop() and single() write :RUN, :STOP and :SINGle", source="upstream_code",
             ref=f"{SCOPE}:251-258"),
        Fact("autoscale() writes :AUToscale", source="upstream_code", ref=f"{SCOPE}:263-264"),
        Fact("get_error() reads one entry of the error FIFO with :SYSTem:ERRor? and returns a code and message",
             source="upstream_code", ref=f"{SCOPE}:222-228"),
        Fact("The upstream close() attempts :RUN before closing the VISA session and suppresses both errors",
             source="upstream_code", ref=f"{SCOPE}:76-86"),
        Fact("measure() selects :MEASure:SOURce CHANnel<n> and then queries :MEASure:<item>? CHANnel<n>, returning "
             "a float", source="upstream_code", ref=f"{SCOPE}:353-356"),
        Fact("The DSL lists the measurement names vpp, vmax, vmin, vamp, vtop, vbase, vavg, vrms, freq, per, rise, "
             "fall, pwid, nwid, duty, over and preshoot",
             source="upstream_code", ref=f"{DSL}:436-439"),
        Fact("The DSL accepts only channel 1 or 2 for channel configuration", source="upstream_code",
             ref=f"{DSL}:214"),
        Fact("The DSL calls parse_voltage for channel scale and offset", source="upstream_code",
             ref=f"{DSL}:233-247"),
        Fact("The DSL calls parse_time for timebase scale and position", source="upstream_code",
             ref=f"{DSL}:281-292"),
        Fact("The DSL calls parse_voltage for the trigger level", source="upstream_code",
             ref=f"{DSL}:338-341"),
        Fact("parse_voltage converts voltage strings to volts", source="upstream_code",
             ref="keyscope_mcp/units.py:30-45"),
        Fact("parse_time converts time strings to seconds", source="upstream_code",
             ref="keyscope_mcp/units.py:48-56"),
        Fact("The DSL acquisition modes are NORMal, AVERage, HRESolution and PEAK", source="upstream_code",
             ref=f"{DSL}:402-403"),
        Fact("query_binary reads an IEEE 488.2 #n<length><data> binary block", source="upstream_code",
             ref=f"{SCOPE}:181-212"),
        Fact("get_waveform sets :WAVeform:SOURce, :WAVeform:FORMat, :WAVeform:POINts and reads "
             ":WAVeform:PREamble? before :WAVeform:DATA?", source="upstream_code", ref=f"{SCOPE}:274-290"),
    ]
    safe_state = ("acquisition stop (:STOP) acknowledged by *OPC? = 1 and a zero error-FIFO code; "
                  "this is command completion, not a sensed acquisition-state read; session close sends no :RUN")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity (*IDN?)")
    def identity(self):
        return self.native.idn()

    @read("channel1_display", type="boolean", description="Channel 1 shown on screen")
    def channel1_display(self):
        return _query_bool(self.native, f":CHANnel{CHANNEL}:DISPlay?")

    @read("channel1_coupling", type="string", description="Channel 1 coupling")
    def channel1_coupling(self):
        return _query_text(self.native, f":CHANnel{CHANNEL}:COUPling?")

    @read("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div")
    def channel1_scale_v_per_div(self):
        return _query_float(self.native, f":CHANnel{CHANNEL}:SCALe?")

    @read("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts")
    def channel1_offset_v(self):
        return _query_float(self.native, f":CHANnel{CHANNEL}:OFFSet?")

    @read("channel1_invert", type="boolean", description="Channel 1 waveform inverted")
    def channel1_invert(self):
        return _query_bool(self.native, f":CHANnel{CHANNEL}:INVert?")

    @read("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div")
    def timebase_scale_s_per_div(self):
        return _query_float(self.native, ":TIMebase:SCALe?")

    @read("timebase_position_s", unit="s", description="Timebase position in seconds")
    def timebase_position_s(self):
        return _query_float(self.native, ":TIMebase:POSition?")

    @read("trigger_source", type="string", description="Edge-trigger source")
    def trigger_source(self):
        return _query_text(self.native, ":TRIGger:EDGE:SOURce?")

    @read("trigger_level_v", unit="V", description="Edge-trigger level in volts")
    def trigger_level_v(self):
        return _query_float(self.native, ":TRIGger:EDGE:LEVel?")

    @read("trigger_slope", type="string", description="Edge-trigger slope")
    def trigger_slope(self):
        return _query_text(self.native, ":TRIGger:EDGE:SLOPe?")

    @read("acquire_type", type="string", description="Acquisition type")
    def acquire_type(self):
        return _query_text(self.native, ":ACQuire:TYPE?")

    @read("acquire_count", type="integer", unit="1", description="Number of averages for AVERage acquisition")
    def acquire_count(self):
        return int(self.native.query(":ACQuire:COUNt?"))

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("channel1_display", type="boolean", description="Show channel 1")
    def set_channel1_display(self, value):
        self.native.write(f":CHANnel{CHANNEL}:DISPlay {'ON' if value else 'OFF'}")
        return _query_bool(self.native, f":CHANnel{CHANNEL}:DISPlay?")

    @write("channel1_coupling", type="string", description="Channel 1 coupling",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{DSL}:251-254"))
    def set_channel1_coupling(self, value):
        self.native.write(f":CHANnel{CHANNEL}:COUPling {value}")
        return _query_text(self.native, f":CHANnel{CHANNEL}:COUPling?")

    @write("channel1_scale_v_per_div", unit="V", description="Channel 1 vertical scale in V/div",
           limit=Limit.operator_required(
               "the clone states no vertical scale range; it depends on the model, the probe ratio and the "
               "vertical window (keyscope_mcp/scope.py:274-283 only selects the waveform source)"))
    def set_channel1_scale_v_per_div(self, value):
        self.native.write(f":CHANnel{CHANNEL}:SCALe {value:.10g}")
        return _query_float(self.native, f":CHANnel{CHANNEL}:SCALe?")

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "the clone states no offset range; it depends on the vertical scale and the probe ratio "
               "(keyscope_mcp/dsl.py:243-244 only parses a voltage)"))
    def set_channel1_offset_v(self, value):
        self.native.write(f":CHANnel{CHANNEL}:OFFSet {value:.10g}")
        return _query_float(self.native, f":CHANnel{CHANNEL}:OFFSet?")

    @write("channel1_invert", type="boolean", description="Invert the channel 1 waveform")
    def set_channel1_invert(self, value):
        self.native.write(f":CHANnel{CHANNEL}:INVert {'ON' if value else 'OFF'}")
        return _query_bool(self.native, f":CHANnel{CHANNEL}:INVert?")

    @write("timebase_scale_s_per_div", unit="s", description="Timebase scale in s/div",
           limit=Limit.operator_required(
               "the clone states no timebase scale range; it depends on the model and the timebase mode "
               "(keyscope_mcp/dsl.py:283-284 only parses a time)"))
    def set_timebase_scale_s_per_div(self, value):
        self.native.write(f":TIMebase:SCALe {value:.10g}")
        return _query_float(self.native, ":TIMebase:SCALe?")

    @write("timebase_position_s", unit="s", description="Timebase position in seconds",
           limit=Limit.operator_required(
               "the clone states no timebase position range; it depends on the timebase scale "
               "(keyscope_mcp/dsl.py:291-292 only parses a time)"))
    def set_timebase_position_s(self, value):
        self.native.write(f":TIMebase:POSition {value:.10g}")
        return _query_float(self.native, ":TIMebase:POSition?")

    @write("trigger_level_v", unit="V", description="Edge-trigger level in volts",
           limit=Limit.operator_required(
               "the clone states no trigger level range; it depends on the trigger source and the vertical "
               "scale (keyscope_mcp/dsl.py:339-341 only parses a voltage)"))
    def set_trigger_level_v(self, value):
        self.native.write(f":TRIGger:EDGE:LEVel {value:.10g}")
        return _query_float(self.native, ":TRIGger:EDGE:LEVel?")

    @write("acquire_type", type="string", description="Acquisition type",
           limit=Limit(allowed=ACQUIRE_TYPES, source="upstream_code", ref=f"{DSL}:402-403"))
    def set_acquire_type(self, value):
        self.native.write(f":ACQuire:TYPE {value}")
        return _query_text(self.native, ":ACQuire:TYPE?")

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.antercreeper.measure.v1",
            description="Read one scalar automatic measurement from one channel",
            input={"channel": Field("integer", unit="1", description="Analog channel number (1 or 2)",
                                    limit=Limit(min=1, max=2, source="upstream_code", ref=f"{DSL}:214")),
                   "measurement": Field("string", description="Automatic measurement item",
                                        enum=MEASUREMENTS,
                                        limit=Limit(allowed=MEASUREMENTS, source="upstream_code",
                                                    ref=f"{DSL}:436-439"))},
            output={"value": Field("number",
                                   description="Measured value in the instrument's unit for the item "
                                               "(V, s, Hz or a ratio)")})
    def measure(self, channel, measurement):
        value = float(self.native.measure(int(channel), measurement))
        if value > 1e30:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               f"the scope returned its no-measurement sentinel for {measurement}")
        return {"value": value}

    @action(name="x-cap.antercreeper.run.v1", description="Start continuous acquisition (:RUN)",
            output={"operation_complete": Field("boolean", description="*OPC? reply after :RUN")})
    def run(self):
        self.native.run()
        return {"operation_complete": _operation_complete(self.native)}

    @action(name="x-cap.antercreeper.single.v1", description="Arm one acquisition (:SINGle)",
            output={"operation_complete": Field("boolean", description="*OPC? reply after :SINGle")})
    def single(self):
        self.native.single()
        return {"operation_complete": _operation_complete(self.native)}

    @action(name="x-cap.antercreeper.autoscale.v1",
            description="Auto-configure the vertical, timebase and trigger settings (:AUToscale)",
            output={"channel1_scale_v_per_div": Field("number", unit="V",
                                                      description="Channel 1 vertical scale after autoscale"),
                    "channel1_offset_v": Field("number", unit="V",
                                               description="Channel 1 vertical offset after autoscale")})
    def autoscale(self):
        self.native.autoscale()
        _operation_complete(self.native)
        return {"channel1_scale_v_per_div": _query_float(self.native, f":CHANnel{CHANNEL}:SCALe?"),
                "channel1_offset_v": _query_float(self.native, f":CHANnel{CHANNEL}:OFFSet?")}

    @action(name="x-cap.antercreeper.reset_to_defaults.v1",
            description="Reset the oscilloscope settings to their defaults (*RST)",
            output={"operation_complete": Field("boolean", description="*OPC? reply after *RST")})
    def reset_to_defaults(self):
        self.native.reset()
        return {"operation_complete": _operation_complete(self.native)}

    @action(name="x-cap.antercreeper.stop_acquisition.v1", safe_state=True,
            description="Stop acquisition (:STOP, the safe state); it takes no input",
            output={"operation_complete": Field("boolean", description="*OPC? reply after :STOP")})
    def stop_acquisition(self):
        self.native.stop()
        return {"operation_complete": _operation_complete(self.native)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The runtime latches first; an unacknowledged or rejected stop raises."""
        self.native.stop()
        _operation_complete(self.native)

    def teardown(self):
        self.native.close()
