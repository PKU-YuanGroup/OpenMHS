"""OpenMHS driver for gh.aimoda/rigol-dho824-mcp: the RIGOL DHO824 oscilloscope over SCPI (a family driver).

A ScpiDriver is configuration only: the class attributes below are the command map of the SCPI bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream repository is an MCP server whose
``RigolDHO824`` class owns a pyvisa resource and sends the SCPI lines of its ``@mcp.tool`` handlers; this driver
ports the scalar settings and status of that class, and the bridge opens the instrument itself (a ``visa_resource``
or ``host``/``port``, options of the hardware backend), so the upstream package is not imported by this driver.

* reads: identity, acquisition/trigger status, the digital voltmeter (enabled, mode and current voltage), the
  channel-1 display, coupling, vertical scale, offset, probe ratio, invert and 20 MHz bandwidth limit, and the main
  timebase scale and offset;
* writes: those settings and the acquisition status (RUN/STOP); the vertical-scale range is operator-required
  because the clone states it only for a 1X probe, while other probe ratios remain selectable;
* ``x-cap.aimoda.single.v1`` arms one acquisition (``:SING``);
* ``x-cap.aimoda.read_error.v1`` reads the oldest entry of the instrument error queue (``:SYSTem:ERRor?``);
* the e-stop writes ``:STOP`` without a confirming trigger-status query or error-queue check.

The instrument's trace array is NOT COVERED (see RESULT.json notes): the clone captures the waveform with
``:WAV:DATA?`` in WORD format through pyvisa's binary query and writes a JSON file, and no catalogue class
carries an oscilloscope trace yet.  This package serves the scope's scalar settings and status, not the samples.

Every sourced Limit and Fact cites the clone at the pinned commit (2b177ae161463c911dce3608ab37e8cadcefc4f6).
The example overlay is for a preconfigured 1X, voltage-axis deployment and is not applied automatically. A live
deployment must supply bounds appropriate to its allowed probe ratios and channel settings. The fake does not model
probe-dependent changes to the scale or offset, instrument rejection of state-dependent settings, or acquisition
timing. Reads do not reproduce the upstream's checked-query error-queue checks. This package is model-authored;
validation uses the fake backend only, with no instrument run.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

SERVER = "src/rigol_dho824_mcp/server.py"
GUIDE = "manuals/DHO800900_ProgrammingGuide_EN.md"
DATASHEET = "manuals/DHO800_DataSheet_EN.md"

#: The probe attenuation ratios the :CHANnel<n>:PROBe command accepts, in the order of the programming guide.
PROBE_RATIOS = [
    0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0,
    200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0, 20000.0, 50000.0,
]


class RigolDho824(ScpiDriver):
    """The DHO824's scalar settings, DVM readings and acquisition control over SCPI."""

    device_id = "rigol-dho824"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "rigol_dho824_mcp.server:RigolDHO824"
    backends = {"fake": ".fake:FakeRigolDho824"}
    vendor, model = "RIGOL Technologies", "DHO824 (DHO800 series)"
    display_name = "RIGOL DHO824 oscilloscope"
    tags = ["oscilloscope", "rigol", "dho824", "dho804", "scpi", "visa", "instrument"]
    safe_state = ("acquisition :STOP command written; no trigger-status read-back or electrical isolation is confirmed")
    idn = {"expect": "^RIGOL TECHNOLOGIES,DHO8"}
    error_query = ":SYSTem:ERRor?"
    facts = [
        Fact("The clone supports only the DHO804 and DHO824 oscilloscopes (identical hardware)",
             source="vendor_doc", ref="README.md:16"),
        Fact("The clone's supported firmware version is 00.01.04", source="vendor_doc", ref="README.md:22"),
        Fact("The class RigolDHO824 manages communication with the Rigol DHO824 oscilloscope",
             source="upstream_code", ref=f"{SERVER}:1297-1298"),
        Fact("The constructor creates pyvisa's ResourceManager",
             source="upstream_code", ref=f"{SERVER}:1308"),
        Fact("connect() opens self.resource_string with pyvisa's exclusive_lock access mode",
             source="upstream_code", ref=f"{SERVER}:1503-1506"),
        Fact("A checked write sends the command with pyvisa's write and then queries ':SYSTem:ERRor?'",
             source="upstream_code", ref=f"{SERVER}:1348-1349"),
        Fact("A checked query sends the command with pyvisa's query and then queries ':SYSTem:ERRor?'",
             source="upstream_code", ref=f"{SERVER}:1374-1375"),
        Fact("get_identity() queries '*IDN?' when no identity is cached", source="upstream_code",
             ref=f"{SERVER}:1572-1588"),
        Fact("The identity string has the format 'RIGOL TECHNOLOGIES,<model>,<serial>,<version>'",
             source="upstream_code", ref=f"{SERVER}:1601"),
        Fact("The DVM is enabled or disabled with ':DVM:ENABle ON' or ':DVM:ENABle OFF'",
             source="upstream_code", ref=f"{SERVER}:1702-1705"),
        Fact("DVMMode defines the values ACRM (AC RMS), DC (DC average) and DCRM (AC+DC RMS)",
             source="upstream_code", ref=f"{SERVER}:295-297"),
        Fact("The current DVM voltage is queried with ':DVM:CURRent?' and parsed as a float in volts",
             source="upstream_code", ref=f"{SERVER}:1739-1746"),
        Fact("The channel configuration queries ':CHAN<n>:' display, coupling, probe, bandwidth limit, scale, "
             "offset and invert", source="upstream_code", ref=f"{SERVER}:2440-2446"),
        Fact("The main timebase scale and offset are queried with ':TIM:MAIN:SCAL?' and ':TIM:MAIN:OFFS?'",
             source="upstream_code", ref=f"{SERVER}:2578-2579"),
        Fact("A run, stop or single acquisition is requested with ':RUN', ':STOP' or ':SING', after which the "
             "trigger status is queried with ':TRIG:STAT?'", source="upstream_code", ref=f"{SERVER}:2679-2721"),
        Fact("The trigger status query returns TD, WAIT, RUN, AUTO, or STOP", source="vendor_doc",
             ref=f"{GUIDE}:14189"),
        Fact("At a 1X probe ratio, the DHO800 series vertical scale ranges from 500 uV/div to 10 V/div",
             source="vendor_doc", ref=f"{GUIDE}:3856"),
        Fact("The probe ratio affects the value and settable range of the current vertical scale",
             source="vendor_doc", ref=f"{GUIDE}:3892"),
        Fact("The DHO800 series time base range is 5 ns/div to 500 s/div", source="vendor_doc",
             ref=f"{DATASHEET}:162"),
        Fact("The channel coupling values are AC, DC and GND", source="vendor_doc", ref=f"{GUIDE}:3686"),
        Fact("The programming guide lists discrete probe attenuation ratios from 0.001 to 50000",
             source="vendor_doc", ref=f"{GUIDE}:3886"),
        Fact("The bandwidth limit query returns 20M or OFF", source="vendor_doc", ref=f"{GUIDE}:3664"),
        Fact("Waveform capture selects WORD format and reads ':WAV:DATA?' with _query_binary_values_checked",
             source="upstream_code", ref=f"{SERVER}:2220-2273"),
    ]
    parameters = {
        "identity": Field("string", description="Instrument identity (*IDN?)"),
        "acquisition_status": Field(
            "string", writable=True,
            description="Acquisition state: write RUN or STOP; read TD, WAIT, RUN, AUTO or STOP",
            limit=Limit(allowed=["RUN", "STOP"], source="upstream_code", ref=f"{SERVER}:2679-2697",
                        reason="RUN is the :RUN command (line 2679); STOP is the :STOP command (line 2697)")),
        "dvm_enabled": Field("boolean", writable=True,
                             description="Digital voltmeter enabled (:DVM:ENABle)"),
        "dvm_voltage": Field("number", unit="V",
                             description="Current digital-voltmeter voltage reading (:DVM:CURRent?), a 4-digit "
                                         "measurement on the selected analog channel"),
        "dvm_mode": Field(
            "string", writable=True,
            description="DVM mode: ACRM (AC RMS), DC or DCRM (AC+DC RMS)",
            limit=Limit(allowed=["ACRM", "DC", "DCRM"], source="upstream_code", ref=f"{SERVER}:295-297")),
        "channel1_display": Field("boolean", writable=True, description="Channel 1 shown on screen"),
        "channel1_coupling": Field(
            "string", writable=True, description="Channel 1 coupling mode",
            limit=Limit(allowed=["AC", "DC", "GND"], source="vendor_doc", ref=f"{GUIDE}:3686")),
        "channel1_scale": Field(
            "number", unit="V", writable=True,
            description="Channel 1 vertical scale in V/div",
            limit=Limit.operator_required(
                "The guide states 500 uV/div to 10 V/div only at a 1X probe ratio (" + GUIDE +
                ":3854-3856); changing the probe ratio changes the scale range (line 3892). Supply deployment "
                "bounds valid for the configured channel and every permitted probe ratio.")),
        "channel1_offset": Field("number", unit="V", description="Channel 1 vertical offset in volts"),
        "channel1_probe": Field(
            "number", unit="1", writable=True, description="Channel 1 probe attenuation ratio",
            limit=Limit(allowed=PROBE_RATIOS, source="vendor_doc", ref=f"{GUIDE}:3886")),
        "channel1_invert": Field("boolean", writable=True, description="Channel 1 waveform inverted"),
        "channel1_bandwidth_limit": Field(
            "string", writable=True, description="Channel 1 bandwidth limit: 20M or OFF",
            limit=Limit(allowed=["20M", "OFF"], source="vendor_doc", ref=f"{GUIDE}:3664")),
        "timebase_scale": Field(
            "number", unit="s", writable=True,
            description="Main timebase scale in s/div",
            limit=Limit(min=5e-9, max=500.0, unit="s", source="vendor_doc", ref=f"{DATASHEET}:162")),
        "timebase_offset": Field("number", unit="s", description="Main timebase offset in seconds"),
    }
    reads = {
        "identity": {"query": "*IDN?", "parse": {"kind": "str"}},
        "acquisition_status": {"query": ":TRIG:STAT?", "parse": {"kind": "str"}},
        "dvm_enabled": {"query": ":DVM:ENABle?", "parse": {"kind": "bool"}},
        "dvm_voltage": {"query": ":DVM:CURRent?", "parse": {"kind": "float"}},
        "dvm_mode": {"query": ":DVM:MODE?", "parse": {"kind": "str"}},
        "channel1_display": {"query": ":CHAN1:DISP?", "parse": {"kind": "bool"}},
        "channel1_coupling": {"query": ":CHAN1:COUP?", "parse": {"kind": "str"}},
        "channel1_scale": {"query": ":CHAN1:SCAL?", "parse": {"kind": "float"}},
        "channel1_offset": {"query": ":CHAN1:OFFS?", "parse": {"kind": "float"}},
        "channel1_probe": {"query": ":CHAN1:PROB?", "parse": {"kind": "float"}},
        "channel1_invert": {"query": ":CHAN1:INV?", "parse": {"kind": "bool"}},
        "channel1_bandwidth_limit": {"query": ":CHAN1:BWL?", "parse": {"kind": "str"}},
        "timebase_scale": {"query": ":TIM:MAIN:SCAL?", "parse": {"kind": "float"}},
        "timebase_offset": {"query": ":TIM:MAIN:OFFS?", "parse": {"kind": "float"}},
    }
    writes = {
        "acquisition_status": {"write": "{value}", "type": "string",
                               "enum_map": {"RUN": ":RUN", "STOP": ":STOP"}},
        "dvm_enabled": {"write": ":DVM:ENABle {value}",
                        "enum_map": {True: "ON", False: "OFF"}},
        "dvm_mode": {"write": ":DVM:MODE {value}", "type": "string"},
        "channel1_display": {"write": ":CHAN1:DISP {value}",
                             "enum_map": {True: "ON", False: "OFF"}},
        "channel1_coupling": {"write": ":CHAN1:COUP {value}", "type": "string"},
        "channel1_scale": {"write": ":CHAN1:SCAL {value:g}", "type": "number"},
        "channel1_probe": {"write": ":CHAN1:PROB {value:g}", "type": "number"},
        "channel1_invert": {"write": ":CHAN1:INV {value}",
                            "enum_map": {True: "ON", False: "OFF"}},
        "channel1_bandwidth_limit": {"write": ":CHAN1:BWL {value}", "type": "string"},
        "timebase_scale": {"write": ":TIM:MAIN:SCAL {value:g}", "type": "number"},
    }
    commands = {
        "x-cap.aimoda.single.v1": {
            "write": ":SING",
            "result": {"command": {"value": ":SING"}},
        },
        "x-cap.aimoda.read_error.v1": {
            "query": ":SYSTem:ERRor?", "parse": {"kind": "str"},
            "result": {"map": {"error": "output.$"}},
        },
    }
    actions = {
        "x-cap.aimoda.single.v1": Action(
            name="single",
            description="Arm one acquisition (:SING); the action reports the command it sent",
            output={"command": Field("string", description="The SCPI command sent (:SING)")}),
        "x-cap.aimoda.read_error.v1": Action(
            name="read_error",
            description="Read and remove the oldest entry of the instrument error queue (:SYSTem:ERRor?)",
            output={"error": Field("string",
                                   description="Error number and description, e.g. '0,\"No error\"'")}),
    }
    safety_bindings = {"estop": {"write": ":STOP"}}
