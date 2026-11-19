"""OpenMHS driver for gh.krystalmonolith/skippy-mcp: a Rigol MSO/DSO oscilloscope over SCPI/PyVISA.

A direct Driver over the upstream high-level ``skippy_mcp.driver.scope:Scope`` class.  The card proposes a
``ScpiDriver`` (family ``scpi``, decision ``family-config``), but the upstream interface is an object with typed
methods, not a table of fixed command lines: each channel, logic and trigger command is assembled at run time from
the channel number and typed arguments, and a capture or measurement is selected from an enum and then checked
against ``:SYSTem:ERRor?`` (scope.py:102-157).  A fixed command table cannot reproduce those lines, so this package
is a direct Driver over the upstream class with a ``native.py`` factory (DEVIATION FROM THE CARD, recorded in
RESULT.json).

* the served resource is analog channel 1 plus the shared edge trigger and acquisition control;
* reads: identity, the channel-1 display, vertical scale, offset, coupling, probe ratio and bandwidth limit, and
  the trigger mode, edge source, edge slope and edge level, read through the upstream ``Scope.raw_scpi`` escape
  hatch;
* writes: the channel-1 display, vertical scale and coupling (bounded by values the clone states), and the offset,
  probe ratio and trigger level as ``Limit.operator_required`` because the clone states no numeric range for them;
* actions: one scalar automatic measurement, one acquisition command (RUN, STOP or SINGle), and one edge-trigger
  configuration; the e-stop sends the native STOP through ``Scope.capture``.

NOT COVERED: the waveform array.  ``Scope.read_waveform`` returns a time/voltage trace from ``:WAVeform:DATA?``
(scope.py:184-213); no catalogue class carries a trace array, so this package serves the scalar measurements and
the settings of the oscilloscope, not the samples.  The screenshot bytes, logic channels, bus decode, the raw SCPI
tool and the channel-2 to channel-4 vertical settings are not exposed either.

The clone states the write forms of the channel and trigger commands and only one read-back query,
``:CHANnel<n>:SCALe?`` (dialect/base.py:78-79).  The other read-back queries this driver sends follow the same
command nodes with a trailing ``?``; they were not verified on an instrument.  Nothing here ran on hardware.

Every Limit and Fact cites a line of the clone at the pinned commit (0f35e7dca264dc7956d7a083bcc4a652c7aac6a5).
This package is model-authored and unreviewed, is checked on the fake backend only, and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

SCOPE = "packages/skippy-mcp/src/skippy_mcp/driver/scope.py"
SESSION = "packages/skippy-mcp/src/skippy_mcp/driver/session.py"
TRANSPORT = "packages/skippy-mcp/src/skippy_mcp/transport/pyvisa_transport.py"
DIALECT = "packages/skippy-mcp/src/skippy_mcp/dialect/base.py"
MSO5000 = "packages/skippy-mcp/src/skippy_mcp/dialect/mso5000.py"
ENUMS = "packages/skippy-mcp/src/skippy_mcp/core/enums.py"
MODELS = "packages/skippy-mcp/src/skippy_mcp/core/models.py"
PYPROJECT = "packages/skippy-mcp/pyproject.toml"

#: The one analog channel this package serves; the clone validates channels 1 to 4 (models.py:49, scope.py:268-273).
CHANNEL = 1

#: API tokens and their SCPI spellings, copied from the clone's enum classes (enums.py:31-73).
COUPLINGS = ["dc", "ac", "gnd"]
BANDWIDTH_LIMITS = ["off", "20m"]
TRIGGER_MODES = ["edge", "pulse", "pattern"]
TRIGGER_SLOPES = ["rising", "falling", "either"]
MEASURE_ITEMS = ["vpp", "vrms", "freq", "period", "duty", "rise", "fall", "delay", "phase"]
CAPTURE_ACTIONS = ["run", "stop", "single"]
MEASURE_SOURCES = ["ch1", "ch2", "ch3", "ch4"]

#: The SCPI tokens the instrument sends back, mapped to the API tokens above.
_COUPLING_FROM_SCPI = {"DC": "dc", "AC": "ac", "GND": "gnd"}
_BANDWIDTH_FROM_SCPI = {"OFF": "off", "20M": "20m"}
_TRIGGER_MODE_FROM_SCPI = {"EDGE": "edge", "PULSe": "pulse", "PATTern": "pattern"}
_TRIGGER_SLOPE_FROM_SCPI = {"POSitive": "rising", "NEGative": "falling", "RFALl": "either"}
_SOURCE_FROM_SCPI = {
    "CHANnel1": "ch1", "CHANnel2": "ch2", "CHANnel3": "ch3", "CHANnel4": "ch4",
}


class SkippyScope(Driver):
    device_id = "skippy-scope"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "skippy_mcp.driver.scope:Scope"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeScope"}
    vendor = "RIGOL Technologies"
    model = "MSO5000/DS5000 series oscilloscope"
    display_name = "RIGOL MSO5000/DS5000 series oscilloscope (skippy_mcp.Scope)"
    tags = ["oscilloscope", "scpi", "visa", "rigol", "mso5000", "mso5204", "skippy-mcp"]
    facts = [
        Fact("The repository is an MCP server that drives a Rigol MSO/DSO oscilloscope over SCPI/PyVISA",
             source="vendor_doc", ref="README.md:3-4"),
        Fact("The package declares pyvisa and pyvisa-py as runtime dependencies and no vendor scope SDK",
             source="upstream_code", ref=f"{PYPROJECT}:14-18"),
        Fact("Scope is the high-level control of one connected instrument",
             source="upstream_code", ref=f"{SCOPE}:53-54"),
        Fact("establish queries *IDN?, selects the dialect and returns a Scope",
             source="upstream_code", ref=f"{SESSION}:30-35"),
        Fact("PyVisaTransport.open opens a VISA resource and sets newline read and write terminators",
             source="upstream_code", ref=f"{TRANSPORT}:36-53"),
        Fact("Scope.identify returns the parsed identity", source="upstream_code", ref=f"{SCOPE}:86-87"),
        Fact("Scope.reset writes the dialect reset command and then the clear-status command",
             source="upstream_code", ref=f"{SCOPE}:93-95"),
        Fact("Scope.configure_channel writes the display, scale, offset, coupling, bandwidth limit and probe "
             "ratio of one channel, then checks :SYSTem:ERRor?", source="upstream_code", ref=f"{SCOPE}:102-119"),
        Fact("Scope.configure_logic requires at least one digital channel, validates it against the model's "
             "count and writes enable and threshold for each channel", source="upstream_code",
             ref=f"{SCOPE}:122-135"),
        Fact("Scope.configure_trigger writes the trigger mode and, only in EDGE mode, the source, slope and "
             "level", source="upstream_code", ref=f"{SCOPE}:138-147"),
        Fact("Scope.capture writes RUN, STOP or SINGle and then checks :SYSTem:ERRor?", source="upstream_code",
             ref=f"{SCOPE}:150-157"),
        Fact("Scope.measure queries one measurement item, parses a float, rejects the 9.9e37 sentinel and "
             "returns the value with a unit", source="upstream_code", ref=f"{SCOPE}:160-175"),
        Fact("Scope.screenshot returns the native screenshot bytes", source="upstream_code",
             ref=f"{SCOPE}:178-181"),
        Fact("The MSO5000 screenshot is always a 24-bit BMP", source="upstream_code", ref=f"{MSO5000}:28-32"),
        Fact("Scope.read_waveform transfers a byte waveform, converts it with the preamble and downsamples it "
             "to max_points", source="upstream_code", ref=f"{SCOPE}:184-213"),
        Fact("Scope.raw_scpi queries when the command ends in '?' and writes otherwise", source="upstream_code",
             ref=f"{SCOPE}:257-265"),
        Fact("The MSO5000 dialect declares 4 analog channels, 16 digital channels and a vertical scale from "
             "5.0e-4 to 10.0 V/div", source="upstream_code", ref=f"{MSO5000}:20-26"),
        Fact("The API coupling tokens are dc, ac and gnd, with the SCPI spellings DC, AC and GND",
             source="upstream_code", ref=f"{ENUMS}:31-36"),
        Fact("The API bandwidth-limit tokens are off and 20m, with the SCPI spellings OFF and 20M",
             source="upstream_code", ref=f"{ENUMS}:39-43"),
        Fact("The trigger modes are edge, pulse and pattern, with the SCPI spellings EDGE, PULSe and PATTern",
             source="upstream_code", ref=f"{ENUMS}:46-51"),
        Fact("The edge-trigger slopes are rising, falling and either, with the SCPI spellings POSitive, "
             "NEGative and RFALl", source="upstream_code", ref=f"{ENUMS}:54-59"),
        Fact("The measurement items are vpp, vrms, freq, period, duty, rise, fall, delay and phase",
             source="upstream_code", ref=f"{ENUMS}:62-73"),
        Fact("The capture actions are run, stop and single", source="upstream_code", ref=f"{ENUMS}:118-123"),
        Fact("DeviceLimits carries the per-model channel counts and vertical-scale bounds used for "
             "pre-validation", source="upstream_code", ref=f"{MODELS}:46-53"),
        Fact("The dialect translates CH1 to CHANnel1 for a source token", source="upstream_code",
             ref=f"{DIALECT}:62-69"),
    ]
    safe_state = "acquisition stopped; the frozen display is left as it is"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Identity string of the oscilloscope (the *IDN? reply)")
    def identity(self):
        idn = self.native.identify()
        return f"{idn.manufacturer},{idn.model},{idn.serial},{idn.firmware}"

    @read("channel1_enabled", type="boolean", description="True while analog channel 1 is displayed")
    def channel1_enabled(self):
        return self._query(":CHANnel1:DISPlay?").strip() in ("1", "ON")

    @read("channel1_scale_v_per_div", unit="V",
          description="Vertical scale of channel 1 in volts per division (the value is V/div)")
    def channel1_scale_v_per_div(self):
        return float(self._query(":CHANnel1:SCALe?"))

    @read("channel1_offset_v", unit="V", description="Vertical offset of channel 1 in volts")
    def channel1_offset_v(self):
        return float(self._query(":CHANnel1:OFFSet?"))

    @read("channel1_coupling", type="string", description="Input coupling of channel 1: dc, ac or gnd")
    def channel1_coupling(self):
        token = self._query(":CHANnel1:COUPling?").strip()
        if token not in _COUPLING_FROM_SCPI:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unexpected coupling reply {token!r}")
        return _COUPLING_FROM_SCPI[token]

    @read("channel1_probe_ratio", unit="1", description="Probe attenuation factor of channel 1")
    def channel1_probe_ratio(self):
        return float(self._query(":CHANnel1:PROBe?"))

    @read("channel1_bandwidth_limit", type="string",
          description="Bandwidth filter of channel 1: off or 20m (20 MHz)")
    def channel1_bandwidth_limit(self):
        token = self._query(":CHANnel1:BWLimit?").strip()
        if token not in _BANDWIDTH_FROM_SCPI:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unexpected bandwidth-limit reply {token!r}")
        return _BANDWIDTH_FROM_SCPI[token]

    @read("trigger_mode", type="string", description="Trigger mode: edge, pulse or pattern")
    def trigger_mode(self):
        token = self._query(":TRIGger:MODE?").strip()
        if token not in _TRIGGER_MODE_FROM_SCPI:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unexpected trigger-mode reply {token!r}")
        return _TRIGGER_MODE_FROM_SCPI[token]

    @read("trigger_edge_source", type="string", description="Edge-trigger source: ch1, ch2, ch3 or ch4")
    def trigger_edge_source(self):
        token = self._query(":TRIGger:EDGE:SOURce?").strip()
        return _SOURCE_FROM_SCPI.get(token, token)

    @read("trigger_edge_slope", type="string", description="Edge-trigger slope: rising, falling or either")
    def trigger_edge_slope(self):
        token = self._query(":TRIGger:EDGE:SLOPe?").strip()
        if token not in _TRIGGER_SLOPE_FROM_SCPI:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"unexpected trigger-slope reply {token!r}")
        return _TRIGGER_SLOPE_FROM_SCPI[token]

    @read("trigger_edge_level_v", unit="V", description="Edge-trigger level in volts")
    def trigger_edge_level_v(self):
        return float(self._query(":TRIGger:EDGE:LEVel?"))

    # -- writes ------------------------------------------------------------------------------------------------
    @write("channel1_enabled", type="boolean", description="Display analog channel 1")
    def set_channel1_enabled(self, value):
        self.native.configure_channel({"channel": CHANNEL, "enabled": bool(value)})
        return bool(value)

    @write("channel1_scale_v_per_div", unit="V",
           description="Channel 1 vertical scale in volts per division (V/div)",
           limit=Limit(min=5.0e-4, max=10.0, source="upstream_code", ref=f"{MSO5000}:24-25",
                       reason="the MSO5000 DeviceLimits bounds the vertical scale"))
    def set_channel1_scale_v_per_div(self, value):
        self.native.configure_channel({"channel": CHANNEL, "scale_v_per_div": float(value)})
        return float(value)

    @write("channel1_offset_v", unit="V", description="Channel 1 vertical offset in volts",
           limit=Limit.operator_required(
               "the clone writes :CHANnel<n>:OFFSet without a numeric range (scope.py:111-112)"))
    def set_channel1_offset_v(self, value):
        self.native.configure_channel({"channel": CHANNEL, "offset_v": float(value)})
        return float(value)

    @write("channel1_coupling", type="string", description="Channel 1 input coupling: dc, ac or gnd",
           limit=Limit(allowed=COUPLINGS, source="upstream_code", ref=f"{ENUMS}:34-36",
                       reason="the Coupling enum lists the SCPI spellings"))
    def set_channel1_coupling(self, value):
        self.native.configure_channel({"channel": CHANNEL, "coupling": str(value)})
        return str(value)

    @write("channel1_probe_ratio", unit="1", description="Channel 1 probe attenuation factor",
           limit=Limit.operator_required(
               "the clone writes :CHANnel<n>:PROBe without a numeric range or allowed set (scope.py:117-118)"))
    def set_channel1_probe_ratio(self, value):
        self.native.configure_channel({"channel": CHANNEL, "probe_ratio": float(value)})
        return float(value)

    @write("channel1_bandwidth_limit", type="string",
           description="Channel 1 bandwidth filter: off or 20m (20 MHz)",
           limit=Limit(allowed=BANDWIDTH_LIMITS, source="upstream_code", ref=f"{ENUMS}:42-43",
                       reason="the BandwidthLimit enum lists the SCPI spellings"))
    def set_channel1_bandwidth_limit(self, value):
        self.native.configure_channel({"channel": CHANNEL, "bandwidth_limit": str(value)})
        return str(value)

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name="x-cap.krystalmonolith.scope_measure.v1",
            description="Read one scalar automatic measurement item from one analog channel",
            input={
                "item": Field("string", description="Measurement item: vpp, vrms, freq, period, duty, rise, "
                                                    "fall, delay or phase",
                              enum=MEASURE_ITEMS),
                "source": Field("string", description="Analog channel the measurement reads",
                                enum=MEASURE_SOURCES),
            },
            output={
                "value": Field("number", description="Measured value in the instrument's unit for the item"),
                "unit": Field("string", description="Unit of the measured value: V, Hz, s, % or deg"),
            })
    def measure(self, item="vpp", source="ch1"):
        result = self.native.measure(item, source)
        return {"value": float(result.value), "unit": str(result.unit)}

    @action(name="x-cap.krystalmonolith.scope_capture.v1",
            description="Start, stop or arm one acquisition on the oscilloscope",
            input={
                "capture_action": Field("string", description="Acquisition command: run, stop or single",
                                        enum=CAPTURE_ACTIONS,
                                        limit=Limit(allowed=CAPTURE_ACTIONS, source="upstream_code",
                                                    ref=f"{ENUMS}:121-123",
                                                    reason="the CaptureAction enum lists the commands")),
            },
            output={
                "accepted": Field("boolean", description="True when the native command completed without an "
                                                        "instrument error"),
            })
    def capture(self, capture_action="run"):
        self.native.capture(str(capture_action))
        return {"accepted": True}

    @action(name="x-cap.krystalmonolith.scope_trigger.v1",
            description="Configure the trigger mode and, in edge mode, the edge source, slope and level",
            input={
                "mode": Field("string", description="Trigger mode: edge, pulse or pattern",
                              enum=TRIGGER_MODES,
                              limit=Limit(allowed=TRIGGER_MODES, source="upstream_code",
                                          ref=f"{ENUMS}:49-51",
                                          reason="the TriggerMode enum lists the modes")),
                "source": Field("string", description="Edge-trigger source: ch1, ch2, ch3 or ch4",
                                enum=MEASURE_SOURCES),
                "slope": Field("string", description="Edge-trigger slope: rising, falling or either",
                               enum=TRIGGER_SLOPES,
                               limit=Limit(allowed=TRIGGER_SLOPES, source="upstream_code",
                                           ref=f"{ENUMS}:57-59",
                                           reason="the TriggerSlope enum lists the slopes")),
                "trigger_level_v": Field("number", unit="V", description="Edge-trigger level in volts",
                                         limit=Limit.operator_required(
                                             "the clone writes :TRIGger:EDGE:LEVel without a numeric range "
                                             "(dialect/base.py:120-121)")),
            },
            output={
                "mode": Field("string", description="Trigger mode read back after the write"),
            })
    def configure_trigger(self, mode="edge", source=None, slope=None, trigger_level_v=None):
        self.native.configure_trigger({
            "mode": str(mode),
            "source": None if source is None else str(source),
            "slope": None if slope is None else str(slope),
            "trigger_level_v": None if trigger_level_v is None else float(trigger_level_v),
        })
        return {"mode": self.trigger_mode()}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """Halt the acquisition (native STOP): the frozen display is the safe state of this instrument."""
        self.native.capture("stop")

    # -- helpers -----------------------------------------------------------------------------------------------
    def _query(self, command):
        reply = self.native.raw_scpi(command)
        if reply is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", f"the scope returned no reply to {command!r}")
        return reply
