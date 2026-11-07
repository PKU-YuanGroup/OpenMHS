"""OpenMHS driver for gh.bgamari/harvard-syringe-pump: a Harvard Apparatus OEM syringe pump module.

A SerialDriver is configuration only: the class attributes below are the command map of the serial bridge, and the
runtime enforces every limit before a command reaches the wire.  The upstream clone is Python 2 code whose class
``harvardpump.pump:Model44`` drives the pump through a ``serial.Serial`` (harvardpump/pump.py:136-137); the GTK UI
instantiates that class (harvardpump_ui:10) on ``/dev/ttyUSB0`` (harvardpump_ui:136).  The bridge opens the serial
line itself, so this package works without importing the clone (the clone is never imported or run).  The fake
backend is the package's own pyserial-like transport.

* reads: the syringe diameter (DIA), the flow rate (RAT), the target volume (TGT), the pump mode (MOD), the
  accumulated volume (DEL) and the firmware version (VER);
* writes: diameter, flow rate, target volume and mode.  The flow rate is always sent in the mL/min range
  (``RAT <value> MM``); the clone has four ranges and this package covers that one.  No text of the clone states a
  numeric diameter, flow-rate or volume range, so those three writes are ``Limit.operator_required``: every write is
  refused ``MHS.SAFETY.LIMITS_UNSET`` until an operator overlay supplies the range of the installed syringe
  (``site-limits.example.json`` shows the overlay).  The GTK spin-button maxima are UI defaults, not device bounds;
  ``_format_float`` only truncates the encoded value and raises above 1e6, which is an encoder guard, not a device
  range (harvardpump/pump.py:171-173);
* actions: start the pump (RUN), stop it (STP), and select the direction (DIR INF or DIR REF).  Each action reports
  the pump status taken from the prompt character of its reply;
* the e-stop and the safe-state action send STP.  A pump dispenses liquid, so the driver is R2 even though the card's
  floor is R0; there is no independent hardware e-stop in the text of the clone, so the safe-state action
  ``x-cap.bgamari.stop_pump.v1`` is the R2 stop path (SAFE-045).

The reply framing is the one the clone reads: LF, the reply text ending at CR, then a digit and one of the prompt
characters (harvardpump/pump.py:144-165).  The bridge reads until CR and parses the value or the prompt with a regular
expression.  Values are sent with at most six significant digits; the upstream ``_format_float`` instead truncates a
six-decimal representation to six characters, and a command table cannot reproduce that truncation, so the formatting
of a number differs while the command words, spaces and range token are those of the clone.

Every Fact cites a line of the clone at the pinned commit d28b04fae0695570f3e91f3d2871875f9b7a5211.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran on hardware.
"""

from mhs.driver import Action, Fact, Field, Limit, SerialDriver

CLONE = "harvardpump/pump.py"
UI = "harvardpump_ui"

#: The status names an action may report from a prompt (harvardpump/pump.py:126-133).  Both ``*`` and ``:`` mean
#: stopped, so the prompt itself is parsed first and this map turns it into the name the clone gives it.
PROMPT_STATUS = {
    ":": "stopped",
    ">": "running",
    "<": "reverse",
    "/": "paused",
    "*": "stopped",
    "^": "wait",
}
#: The reply parser of an action: the prompt is the last character before the line end.
_PROMPT_PARSE = {"kind": "regex", "pattern": r"(?P<prompt>[:><*/^])\s*$"}
#: Map the prompt character to the status name of the clone.
_PROMPT_RESULT = {"status": {"from": "output.prompt", "enum_map": PROMPT_STATUS}}
#: A reply value is a decimal number at the start of the reply; the first one is the value (the rest is CR, a
#: status digit and the prompt).  The anchor keeps an error reply such as "?12" from reading as 12.
_NUMBER = r"^\s*([-+]?\d+(?:\.\d+)?)"
_NUMBER_PARSE = {"kind": "float", "pattern": _NUMBER, "group": 1}


class HarvardSyringePump(SerialDriver):
    device_id = "harvard-syringe-pump"
    device_kind = "fluid.pump"
    mode = "hardware"
    #: R2, above the card's floor: a pump that dispenses liquid is at least R2 (MHS/spec/04-safety.md).  The model
    #: review raised it; the hardware backend of this model-written package stays refused until a human signs
    #: reviewed_by.
    risk = "R2"
    native = "harvardpump.pump:Model44"
    backends = {"fake": ".fake:FakeHarvardSyringePump"}
    vendor, model = "Harvard Apparatus", "OEM syringe pump module (Model 44)"
    display_name = "Harvard Apparatus OEM syringe pump (Model 44)"
    tags = ["syringe pump", "pump", "serial", "infuse", "withdraw", "harvard apparatus"]
    facts = [
        Fact("Model 44 is the syringe pump class the GTK UI instantiates", source="upstream_code",
             ref=f"{UI}:10"),
        Fact("The GTK UI opens the pump on /dev/ttyUSB0", source="upstream_code", ref=f"{UI}:136"),
        Fact("The serial line is 9600 baud with two stop bits", source="upstream_code", ref=f"{CLONE}:136-137"),
        Fact("A command is written as text followed by a carriage return", source="upstream_code",
             ref=f"{CLONE}:140-142"),
        Fact("A reply begins with LF, its text ends at CR, and the frame ends with a digit and one of the prompt "
             "characters", source="upstream_code", ref=f"{CLONE}:144-165"),
        Fact("The prompts are ':' stopped, '>' running, '<' reverse, '/' paused, '*' stopped and '^' wait for a "
             "dispense trigger", source="upstream_code", ref=f"{CLONE}:126-133"),
        Fact("The pump caches the status named by the prompt of the last reply", source="upstream_code",
             ref=f"{CLONE}:160-165"),
        Fact("set_diameter sends 'DIA <value>' and its docstring names the syringe diameter in millimetres",
             source="upstream_code", ref=f"{CLONE}:179-182"),
        Fact("get_diameter sends 'DIA', get_target_volume sends 'TGT' and get_volume_accum sends 'DEL'",
             source="upstream_code", ref=f"{CLONE}:206-208"),
        Fact("get_flow_rate sends 'RAT' and splits the reply into a value and a unit token; the token 'ml/mn' means "
             "mL/min", source="upstream_code", ref=f"{CLONE}:195-204"),
        Fact("set_flow_rate sends 'RAT <value> <range token>' and the range token for mL/min is 'MM'",
             source="upstream_code", ref=f"{CLONE}:227-238"),
        Fact("start sends 'RUN', stop sends 'STP', clear_volume_accum sends 'CLD' and reverse sends 'DIR REV'",
             source="upstream_code", ref=f"{CLONE}:216-220"),
        Fact("set_direction sends 'DIR INF' for forward and 'DIR REF' for reverse", source="upstream_code",
             ref=f"{CLONE}:222-225"),
        Fact("set_target_volume sends 'TGT <value>'; clear_target sends 'TGT 0'", source="upstream_code",
             ref=f"{CLONE}:219-243"),
        Fact("set_pump_mode sends 'MOD PMP', set_volume_mode sends 'MOD VOL', and get_mode sends 'MOD' and lowercases "
             "the reply", source="upstream_code", ref=f"{CLONE}:245-256"),
        Fact("get_version sends 'VER'", source="upstream_code", ref=f"{CLONE}:184-187"),
        Fact("_format_float rejects a value above 1e6 and truncates its formatted form to six characters; it is an "
             "encoder guard and an encoder truncation, not a range of the pump", source="upstream_code",
             ref=f"{CLONE}:171-173"),
        Fact("The UI's range table gives the mL/min range the volume unit mL", source="upstream_code",
             ref=f"{UI}:60-65"),
        Fact("The UI displays the Model 44 target volume in mL", source="upstream_code", ref=f"{UI}:124"),
        Fact("The upstream setup.py describes the package as a Python interface to Harvard Apparatus OEM syringe pump "
             "modules", source="upstream_code", ref="setup.py:3-5"),
    ]
    safe_state = "pump stopped with STP; no new motion until a RUN"

    #: The serial line settings of the clone: 9600 baud and two stop bits (harvardpump/pump.py:136-137).  The bridge
    #: reads until CR because the reply text ends at CR (harvardpump/pump.py:144-165).
    baudrate = 9600
    stopbits = 2
    timeout_s = 0.5
    terminator = "\r"
    encoding = "ascii"

    parameters = {
        "diameter": Field(
            "number", unit="mm", writable=True, description="Syringe diameter (DIA)",
            limit=Limit.operator_required(
                "the syringe diameter depends on the syringe fitted; no text of the clone states a diameter range, "
                "and _format_float only truncates the encoded value (harvardpump/pump.py:171-173), so the site "
                "supplies the diameter envelope")),
        "flow_rate": Field(
            "number", unit="mL/min", writable=True,
            description="Flow rate in the mL/min range (RAT <value> MM); the other three ranges are not covered",
            limit=Limit.operator_required(
                "the clone sends any formatted value with one of four range tokens and states no numeric range "
                "(harvardpump/pump.py:227-238); the site supplies the flow-rate envelope of the installed syringe "
                "and tubing")),
        "target_volume": Field(
            "number", unit="mL", writable=True, description="Target volume (TGT)",
            limit=Limit.operator_required(
                "the target volume depends on the syringe and no text of the clone states a volume range; the UI's "
                "spin-button maximum is a UI default, not a device bound (harvardpump_ui:536-537), so the site "
                "supplies the volume envelope")),
        "mode": Field(
            "string", writable=True,
            description="Pump mode token: PMP for pump mode and VOL for volume mode (MOD)",
            limit=Limit(allowed=["PMP", "VOL"], source="upstream_code", ref=f"{CLONE}:245-251",
                        reason="set_pump_mode sends MOD PMP and set_volume_mode sends MOD VOL")),
        "accumulated_volume": Field(
            "number", unit="mL", description="Volume accumulated by the pump (DEL), in mL for the mL/min range"),
        "version": Field("string", description="Firmware version returned by VER"),
    }
    reads = {
        "diameter": {"command": "DIA", "parse": _NUMBER_PARSE},
        "flow_rate": {"command": "RAT",
                      "parse": {"kind": "float", "pattern": _NUMBER + r"\s*ml/mn", "group": 1}},
        "target_volume": {"command": "TGT", "parse": _NUMBER_PARSE},
        "mode": {"command": "MOD", "parse": {"kind": "regex",
                                            "pattern": "([Pp][Mm][Pp]|[Vv][Oo][Ll])", "group": 1}},
        "accumulated_volume": {"command": "DEL", "parse": _NUMBER_PARSE},
        "version": {"command": "VER", "parse": {"kind": "regex", "pattern": r"^([^\r]+)", "group": 1}},
    }
    writes = {
        "diameter": {"command": "DIA {value:.6g}", "type": "number"},
        "flow_rate": {"command": "RAT {value:.6g} MM", "type": "number"},
        "target_volume": {"command": "TGT {value:.6g}", "type": "number"},
        "mode": {"command": "MOD {value}", "type": "string"},
    }
    commands = {
        "x-cap.bgamari.start_pump.v1": {
            "command": "RUN", "parse": _PROMPT_PARSE, "result": _PROMPT_RESULT,
        },
        "x-cap.bgamari.stop_pump.v1": {
            "command": "STP", "parse": _PROMPT_PARSE, "result": _PROMPT_RESULT,
        },
        "x-cap.bgamari.set_direction.v1": {
            "command": "DIR {direction}",
            "args": {"direction": {"from": "input.direction"}},
            "parse": _PROMPT_PARSE,
            "result": _PROMPT_RESULT,
        },
    }
    actions = {
        "x-cap.bgamari.start_pump.v1": Action(
            name="start_pump", description="Start the pump with its configured flow rate, target volume and mode "
                                           "(RUN); the reply prompt reports the resulting status",
            output={"status": Field("string", description="Status named by the reply prompt")}),
        "x-cap.bgamari.stop_pump.v1": Action(
            name="stop_pump", safe_state=True,
            description="Stop the pump (STP), the safe state; the reply prompt reports the resulting status",
            output={"status": Field("string", description="Status named by the reply prompt")}),
        "x-cap.bgamari.set_direction.v1": Action(
            name="set_direction",
            description="Select the pumping direction (DIR INF or DIR REF); the reply prompt reports the resulting "
                        "status",
            input={"direction": Field(
                "string", enum=["INF", "REF"], description="Direction token: INF for forward and REF for reverse",
                limit=Limit(allowed=["INF", "REF"], source="upstream_code", ref=f"{CLONE}:222-225",
                            reason="set_direction sends DIR INF or DIR REF"))},
            output={"status": Field("string", description="Status named by the reply prompt")}),
    }
    safety_bindings = {"estop": {"command": "STP"}}
