"""OpenMHS driver for gh.capotosto/py_instrument_driver_package: a Keysight E4980A precision LCR meter over SCPI.

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream package is a collection of pyvisa
instrument wrappers; the E4980A wrapper is ``instrument_module/keysight_E4980A.py`` (class
``KeysightE4980A``).  Its commands are fixed SCPI words with the value appended (``:FREQuency {frequency}`` at
line 198, ``:APERture {mode},{averages}`` at line 264), so a command table reproduces the wire syntax.  The bridge
owns the transport (``host``/``port`` for raw SCPI or a ``visa_resource`` for pyvisa), and the upstream package is
neither imported nor installed by this package.

* reads: the impedance measurement function, test frequency, AC voltage and current levels, automatic level
  control, aperture mode and averaging rate, DC bias state and voltage, DC bias autorange, cable length, correction
  method, data format, long ASCII formatting, exponent digits, trigger source and delay, continuous initiation,
  impedance range and autorange;
* writes: the measurement function, test frequency, AC voltage and current levels, automatic level control, DC bias
  state and voltage, cable length and impedance range, each limited by a value the upstream code states or bounded by
  the operator.  The other settings are read-only here: the MCP projection bounds the single configure tool to 2048
  bytes, and a narrower configure contract is enforced rather than a truncated one;
* actions: fetch the formatted measurement (primary, secondary and status code), the corrected impedance
  (resistance and reactance), the four signal monitors, one entry of the error queue, and set the aperture mode and
  averaging rate in one command;
* the e-stop writes ``:BIAS:STATe OFF`` and then the safe-state binding writes ``:ABORt``, so the DC bias is removed
  and the current measurement is aborted.  At R1 this is a software e-stop; no independent hardware stop is cited.

The upstream does not state a frequency, signal-level, DC-bias or impedance-range bound, so those limits are
``Limit.operator_required`` and the operator supplies them in ``site-limits.json`` before any write.  The package's
``site-limits.example.json`` is an example of such an overlay.  The status text of
``fetch_formatted_with_status`` is not exposed: the action returns the numeric status code the clone parses, and the
caller maps it to a message (the clone's table is at lines 34-40).  List sweep, bin sorting, correction execution and
the correction states are not served.

Every Fact and Limit cites a line of the clone at the pinned commit
(1512bb3c1d76a16ada54cf042019a88710b7e12f).  This package is model-authored and unreviewed, is checked on the fake
backend only, and never ran on hardware.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

MODULE = "instrument_module/keysight_E4980A.py"
VISA = "instrument_module/visa_utils.py"

MEASUREMENT_FUNCTIONS = [
    "CPD", "CPQ", "CPG", "CPRP",
    "CSD", "CSQ", "CSRS",
    "LPD", "LPQ", "LPG", "LPRP", "LPRD",
    "LSD", "LSQ", "LSRS", "LSRD",
    "RX", "ZTD", "ZTR", "GB", "YTD", "YTR", "VDID",
]  # MODULE:18-24


class KeysightE4980AScpi(ScpiDriver):
    device_id = "e4980a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "instrument_module.keysight_E4980A:KeysightE4980A"
    backends = {"fake": ".fake:FakeKeysightE4980A"}
    vendor = "Keysight Technologies"
    model = "E4980A precision LCR meter"
    display_name = "Keysight E4980A precision LCR meter"
    tags = ["lcr meter", "impedance", "keysight", "e4980a", "scpi", "visa"]
    safe_state = "DC bias off and the current measurement aborted"
    # The clone queries *IDN? (MODULE:91-95) but documents no expected identity pattern, so the probe asserts none.
    idn = {"expect": None}
    # The clone reads and clears the error queue with :SYSTem:ERRor? (MODULE:153-171); the bridge checks it after
    # each write, with the same command and the standard "0,No error" success form.
    error_query = ":SYSTem:ERRor?"
    facts = [
        Fact("The module controls Keysight E4980A series Precision LCR Meters with the class KeysightE4980A",
             source="upstream_code", ref=f"{MODULE}:1-15"),
        Fact("The accepted impedance measurement functions are CPD, CPQ, CPG, CPRP, CSD, CSQ, CSRS, LPD, LPQ, LPG, "
             "LPRP, LPRD, LSD, LSQ, LSRS, LSRD, RX, ZTD, ZTR, GB, YTD, YTR and VDID",
             source="upstream_code", ref=f"{MODULE}:18-24"),
        Fact("The measurement function is set with ':FUNCtion:IMPedance <function>' and queried with "
             "':FUNCtion:IMPedance?'", source="upstream_code", ref=f"{MODULE}:185-190"),
        Fact("A setting is sent as a fixed command word followed by the value, for example "
             "f':FREQuency {frequency}'", source="upstream_code", ref=f"{MODULE}:198"),
        Fact("A query is sent as a fixed query word, for example ':FREQuency?'", source="upstream_code",
             ref=f"{MODULE}:203"),
        Fact("Boolean states are written as ON or OFF and read back as 1/ON or 0/OFF", source="upstream_code",
             ref=f"{MODULE}:73-86"),
        Fact("The aperture command is ':APERture <mode>,<averages>', with the instrument spellings SHORt, MEDium "
             "and LONG, and the averaging rate is checked to lie from 1 to 256", source="upstream_code",
             ref=f"{MODULE}:246-264"),
        Fact("The cable length is one of 0, 1, 2 or 4 metres", source="upstream_code", ref=f"{MODULE}:534-535"),
        Fact("The exponent field accepts 2 or 3 digits", source="upstream_code", ref=f"{MODULE}:673-674"),
        Fact("The correction method is written as SINGle or MULTiple", source="upstream_code",
             ref=f"{MODULE}:548-560"),
        Fact("The data format command is ':FORMat:DATA ASCii' or ':FORMat:DATA REAL,64'", source="upstream_code",
             ref=f"{MODULE}:639-642"),
        Fact("The trigger source is written as INternal, HOLD, EXternal or BUS", source="upstream_code",
             ref=f"{MODULE}:367-383"),
        Fact("fetch_formatted queries ':FETCh:IMPedance:FORMatted?' and parses primary value, secondary value and "
             "a numeric status code", source="upstream_code", ref=f"{MODULE}:416-430"),
        Fact("fetch_corrected_impedance queries ':FETCh:IMPedance:CORRected?' and parses resistance and reactance "
             "in ohms", source="upstream_code", ref=f"{MODULE}:445-458"),
        Fact("The signal monitors fetch AC voltage, AC current, DC voltage and DC current from "
             "':FETCh:SMONitor:VAC?', ':FETCh:SMONitor:IAC?', ':FETCh:SMONitor:VDC?' and ':FETCh:SMONitor:IDC?'",
             source="upstream_code", ref=f"{MODULE}:506-528"),
        Fact("One error-queue entry is read from ':SYSTem:ERRor?' and get_all_system_errors stops when the code "
             "before the first comma is 0", source="upstream_code", ref=f"{MODULE}:153-171"),
        Fact("abort sends ':ABORt' and returns the trigger system to idle", source="upstream_code",
             ref=f"{MODULE}:339-342"),
        Fact("The DC bias state is set with ':BIAS:STATe <state>' and queried with ':BIAS:STATe?'",
             source="upstream_code", ref=f"{MODULE}:304-313"),
        Fact("The DC bias voltage is set with ':BIAS:VOLTage:LEVel <voltage>' and queried with "
             "':BIAS:VOLTage:LEVel?'", source="upstream_code", ref=f"{MODULE}:315-324"),
        Fact("The raw SCPI socket port is 5025 and a VISA resource is 'TCPIP0::<ip>::5025::SOCKET' or "
             "'TCPIP0::<ip>::INSTR'", source="upstream_code", ref=f"{VISA}:43-49"),
    ]
    parameters = {
        "measurement_function": Field(
            "string", writable=True,
            description="Impedance measurement function (see allowed set)",
            limit=Limit(allowed=MEASUREMENT_FUNCTIONS, source="upstream_code", ref=f"{MODULE}:18-24")),
        "frequency": Field(
            "number", unit="Hz", writable=True,
            description="AC test frequency",
            limit=Limit.operator_required(
                "The clone's set_frequency sends the value without a range; no text states the E4980A frequency "
                "bounds, so the operator supplies them")),
        "voltage_level": Field(
            "number", unit="V", writable=True,
            description="AC test signal voltage",
            limit=Limit.operator_required(
                "The clone's set_voltage_level sends the value without a range; no text states the E4980A AC "
                "voltage bounds, so the operator supplies them")),
        "current_level": Field(
            "number", unit="A", writable=True,
            description="AC test signal current",
            limit=Limit.operator_required(
                "The clone's set_current_level sends the value without a range; no text states the E4980A AC "
                "current bounds, so the operator supplies them")),
        "alc": Field("boolean", writable=True,
                     description="Automatic level control on or off"),
        "aperture_mode": Field(
            "string", enum=["SHORT", "SHOR", "SHORt", "MEDIUM", "MED", "MEDium", "LONG"],
            description="Measurement time mode read from :APERture? (SHORT, MEDIUM or LONG)"),
        "aperture_averages": Field(
            "integer", unit="1",
            description="Averaging rate read from :APERture? (1 to 256)"),
        "dc_bias_state": Field("boolean", writable=True,
                               description="DC bias on or off"),
        "dc_bias_voltage": Field(
            "number", unit="V", writable=True,
            description="DC bias voltage",
            limit=Limit.operator_required(
                "The clone's set_dc_bias_voltage sends the value without a range; no text states the E4980A DC "
                "bias bounds, so the operator supplies them")),
        "dc_bias_autorange": Field("boolean",
                                   description="DC bias autoranging on or off"),
        "cable_length": Field(
            "number", unit="m", writable=True,
            description="Test cable length (0, 1, 2 or 4 m)",
            limit=Limit(allowed=[0, 1, 2, 4], source="upstream_code", ref=f"{MODULE}:534")),
        "correction_method": Field(
            "string", enum=["SINGLE", "SING", "SINGle", "MULTIPLE", "MULT", "MULTiple"],
            description="Correction method (SINGLE or MULTIPLE)"),
        "data_format": Field(
            "string", enum=["ASCII", "ASCii", "REAL,64", "REAL64", "REAL"],
            description="Measurement data format (ASCII or REAL,64)"),
        "ascii_long": Field("boolean",
                            description="Long ASCII formatting on or off"),
        "exponent_digits": Field(
            "integer", unit="1", enum=[2, 3],
            description="ASCII exponent digits (2 or 3)"),
        "trigger_source": Field(
            "string", enum=["INTERNAL", "INternal", "HOLD", "EXTERNAL", "EXternal", "BUS"],
            description="Trigger source"),
        "trigger_delay": Field(
            "number", unit="s",
            description="Trigger delay"),
        "initiate_continuous": Field("boolean",
                                     description="Continuous measurement initiation"),
        "impedance_range": Field(
            "number", unit="Ohm", writable=True,
            description="Impedance measurement range",
            limit=Limit.operator_required(
                "The clone's set_impedance_range sends the value without a range; no text states the E4980A "
                "impedance ranges, so the operator supplies them")),
        "impedance_autorange": Field("boolean",
                                     description="Impedance autoranging on or off"),
    }
    reads = {
        "measurement_function": {"query": ":FUNCtion:IMPedance?", "parse": {"kind": "str"}},
        "frequency": {"query": ":FREQuency?", "parse": {"kind": "float"}},
        "voltage_level": {"query": ":VOLTage:LEVel?", "parse": {"kind": "float"}},
        "current_level": {"query": ":CURRent:LEVel?", "parse": {"kind": "float"}},
        "alc": {"query": ":AMPLitude:ALC?", "parse": {"kind": "bool"}},
        "aperture_mode": {"query": ":APERture?", "parse": {
            "kind": "regex", "pattern": r"^\s*([^,]+),", "group": 1}},
        "aperture_averages": {"query": ":APERture?", "parse": {
            "kind": "int", "pattern": r"^\s*[^,]+,\s*([0-9]+)\s*$", "group": 1}},
        "dc_bias_state": {"query": ":BIAS:STATe?", "parse": {"kind": "bool"}},
        "dc_bias_voltage": {"query": ":BIAS:VOLTage:LEVel?", "parse": {"kind": "float"}},
        "dc_bias_autorange": {"query": ":BIAS:RANGe:AUTO?", "parse": {"kind": "bool"}},
        "cable_length": {"query": ":CORRection:LENGth?", "parse": {"kind": "float"}},
        "correction_method": {"query": ":CORRection:METHod?", "parse": {"kind": "str"}},
        "data_format": {"query": ":FORMat:DATA?", "parse": {"kind": "str"}},
        "ascii_long": {"query": ":FORMat:ASCii:LONG?", "parse": {"kind": "bool"}},
        "exponent_digits": {"query": ":FORMat:EXPonent:DIGit?", "parse": {"kind": "int"}},
        "trigger_source": {"query": ":TRIGger:SOURce?", "parse": {"kind": "str"}},
        "trigger_delay": {"query": ":TRIGger:TDEL?", "parse": {"kind": "float"}},
        "initiate_continuous": {"query": ":INITiate:CONTinuous?", "parse": {"kind": "bool"}},
        "impedance_range": {"query": ":FUNCtion:IMPedance:RANGe?", "parse": {"kind": "float"}},
        "impedance_autorange": {"query": ":FUNCtion:IMPedance:RANGe:AUTO?", "parse": {"kind": "bool"}},
    }
    writes = {
        "measurement_function": {"write": ":FUNCtion:IMPedance {value}", "type": "string"},
        "frequency": {"write": ":FREQuency {value}", "type": "number"},
        "voltage_level": {"write": ":VOLTage:LEVel {value}", "type": "number"},
        "current_level": {"write": ":CURRent:LEVel {value}", "type": "number"},
        "alc": {"write": ":AMPLitude:ALC {value}", "type": "string",
                "enum_map": {True: "ON", False: "OFF"}},
        "dc_bias_state": {"write": ":BIAS:STATe {value}", "type": "string",
                          "enum_map": {True: "ON", False: "OFF"}},
        "dc_bias_voltage": {"write": ":BIAS:VOLTage:LEVel {value}", "type": "number"},
        "cable_length": {"write": ":CORRection:LENGth {value}", "type": "number"},
        "impedance_range": {"write": ":FUNCtion:IMPedance:RANGe {value}", "type": "number"},
    }
    commands = {
        "x-cap.capotosto.fetch_formatted.v1": {
            "query": ":FETCh:IMPedance:FORMatted?",
            "parse": {"kind": "regex",
                      "pattern": r"^\s*(?P<primary>[^,]+),\s*(?P<secondary>[^,]+),\s*(?P<status>[^,]+)\s*$"},
            "result": {"map": {
                "primary": {"from": "primary", "type": "number"},
                "secondary": {"from": "secondary", "type": "number"},
                "status": {"from": "status", "type": "integer"},
            }},
            "description": "Fetch the latest formatted measurement",
        },
        "x-cap.capotosto.fetch_impedance.v1": {
            "query": ":FETCh:IMPedance:CORRected?",
            "parse": {"kind": "regex",
                      "pattern": r"^\s*(?P<resistance>[^,]+),\s*(?P<reactance>[^,]+)\s*$"},
            "result": {"map": {
                "resistance": {"from": "resistance", "type": "number"},
                "reactance": {"from": "reactance", "type": "number"},
            }},
            "description": "Fetch corrected impedance as resistance and reactance",
        },
        "x-cap.capotosto.fetch_vac.v1": {
            "query": ":FETCh:SMONitor:VAC?", "parse": {"kind": "float"},
            "result": {"map": {"voltage": {"from": "output.$", "type": "number"}}},
            "description": "Fetch the monitored AC voltage",
        },
        "x-cap.capotosto.fetch_iac.v1": {
            "query": ":FETCh:SMONitor:IAC?", "parse": {"kind": "float"},
            "result": {"map": {"current": {"from": "output.$", "type": "number"}}},
            "description": "Fetch the monitored AC current",
        },
        "x-cap.capotosto.fetch_vdc.v1": {
            "query": ":FETCh:SMONitor:VDC?", "parse": {"kind": "float"},
            "result": {"map": {"voltage": {"from": "output.$", "type": "number"}}},
            "description": "Fetch the monitored DC voltage",
        },
        "x-cap.capotosto.fetch_idc.v1": {
            "query": ":FETCh:SMONitor:IDC?", "parse": {"kind": "float"},
            "result": {"map": {"current": {"from": "output.$", "type": "number"}}},
            "description": "Fetch the monitored DC current",
        },
        "x-cap.capotosto.read_error.v1": {
            "query": ":SYSTem:ERRor?", "parse": {"kind": "str"},
            "result": {"map": {"error": {"from": "output.$", "type": "string"}}},
            "description": "Read and remove one entry of the instrument error queue",
        },
        "x-cap.capotosto.set_aperture.v1": {
            "write": ":APERture {mode},{averages}",
            "args": {
                "mode": {"from": "input.mode",
                         "enum_map": {"SHORT": "SHORt", "MEDIUM": "MEDium", "LONG": "LONG"}},
                "averages": {"from": "input.averages", "type": "integer"},
            },
            "description": "Set the measurement time mode and averaging rate",
        },
    }
    actions = {
        "x-cap.capotosto.fetch_formatted.v1": Action(
            name="fetch_formatted",
            description="Fetch the latest formatted measurement: primary value, secondary value and status code",
            output={
                "primary": Field("number", unit="1",
                                 description="Primary formatted value in the unit of the selected function"),
                "secondary": Field("number", unit="1",
                                   description="Secondary formatted value in the unit of the selected function"),
                "status": Field("integer", unit="1",
                                description="Measurement status code: -1 no data, 0 normal, 1 overload, "
                                            "3 signal source overloaded, 4 ALC unable to regulate"),
            }),
        "x-cap.capotosto.fetch_impedance.v1": Action(
            name="fetch_impedance",
            description="Fetch corrected impedance as resistance and reactance",
            output={
                "resistance": Field("number", unit="Ohm", description="Corrected resistance"),
                "reactance": Field("number", unit="Ohm", description="Corrected reactance"),
            }),
        "x-cap.capotosto.fetch_vac.v1": Action(
            name="fetch_vac",
            description="Fetch the monitored AC voltage (:FETCh:SMONitor:VAC?)",
            output={"voltage": Field("number", unit="V", description="Monitored AC voltage")}),
        "x-cap.capotosto.fetch_iac.v1": Action(
            name="fetch_iac",
            description="Fetch the monitored AC current (:FETCh:SMONitor:IAC?)",
            output={"current": Field("number", unit="A", description="Monitored AC current")}),
        "x-cap.capotosto.fetch_vdc.v1": Action(
            name="fetch_vdc",
            description="Fetch the monitored DC voltage (:FETCh:SMONitor:VDC?)",
            output={"voltage": Field("number", unit="V", description="Monitored DC voltage")}),
        "x-cap.capotosto.fetch_idc.v1": Action(
            name="fetch_idc",
            description="Fetch the monitored DC current (:FETCh:SMONitor:IDC?)",
            output={"current": Field("number", unit="A", description="Monitored DC current")}),
        "x-cap.capotosto.read_error.v1": Action(
            name="read_error",
            description="Read and remove one entry of the instrument error queue (:SYSTem:ERRor?)",
            output={"error": Field("string",
                                   description="Error code and message, for example '0,\"No error\"'")}),
        "x-cap.capotosto.set_aperture.v1": Action(
            name="set_aperture",
            description="Set the measurement time mode and averaging rate",
            input={
                "mode": Field("string", description="Measurement time mode",
                              limit=Limit(allowed=["SHORT", "MEDIUM", "LONG"], source="upstream_code",
                                          ref=f"{MODULE}:246-252")),
                "averages": Field("integer", unit="1", description="Averaging rate from 1 to 256",
                                  limit=Limit(min=1, max=256, source="upstream_code", ref=f"{MODULE}:261")),
            }),
    }
    safety_bindings = {
        "estop": {"write": ":BIAS:STATe OFF"},
        "safe_state": {"write": ":ABORt"},
    }
