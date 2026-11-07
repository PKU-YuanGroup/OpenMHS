"""OpenMHS driver for gh.akperuht/pydaq: the Digimess PN300 programmable power supply.

The upstream repository is a collection of laboratory instrument classes; this package binds the PN300 class of
``Control_lib/instrument_control.py``, one of the repository's entry symbols.  The PN300 is a GPIB power supply
whose protocol is line-oriented text (``SEL_A``, ``OUT_ON``, ``VSET 1.0``, ``VOUT?``), so the card's ``ScpiDriver``
family expresses it directly.  The upstream class builds each command from a word plus a value; those words occur
verbatim in the clone, and this driver keeps their spelling and case.

The driver reads the selected source, output state, operating mode, source type, protection mode, voltage and
current setpoints and measured output voltage and current.  It writes the discrete state fields through the
commands named in the upstream class and writes the two analogue setpoints only inside a site overlay: the clone
states the units but no single voltage range, and its current docstring gives mode-dependent ranges with non-numeric
glyphs, so both bounds are ``operator_required``.

The e-stop and the ``x-cap.akperuht.output_off.v1`` safe-state action both write ``OUT_OFF``, the command the
upstream class uses to disable the output.  The declared risk is R2: a power supply can deliver energy into an
unknown load, so an unreviewed model-written package must not open the hardware backend.

Every Fact and Limit cites a line of the clone at the pinned commit
(edb7584d00891aa0f1a0ef483d12d1d59ab4f794).  This package is model-authored and unreviewed; no hardware run was
performed.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

CLONE = "Control_lib/instrument_control.py"


class Pn300(ScpiDriver):
    """Digimess PN300 programmable power supply over GPIB text commands."""

    device_id = "pn300"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R2"
    native = "Control_lib.instrument_control:PN300"
    backends = {"fake": ".fake:FakePn300"}
    vendor = "Digimess"
    model = "PN300 programmable power supply"
    display_name = "Digimess PN300 power supply"
    tags = ["power supply", "dc source", "pn300", "scpi", "gpib"]
    facts = [
        Fact("The PN300 is a Digimess programmable power supply controlled over GPIB",
             source="upstream_code", ref=f"{CLONE}:1637-1639"),
        Fact("The instrument is identified with *IDN? on connection",
             source="upstream_code", ref=f"{CLONE}:1664"),
        Fact("reset writes *RST", source="upstream_code", ref=f"{CLONE}:1713-1722"),
        Fact("Source A or B is selected with SEL_A or SEL_B", source="upstream_code",
             ref=f"{CLONE}:1724-1744"),
        Fact("The active source is read with SEL? and its reply contains SEL_A or SEL_B",
             source="upstream_code", ref=f"{CLONE}:1746-1763"),
        Fact("The output is switched on with OUT_ON and off with OUT_OFF",
             source="upstream_code", ref=f"{CLONE}:1766-1797"),
        Fact("The output state is read with OUT?", source="upstream_code",
             ref=f"{CLONE}:1766-1797"),
        Fact("The operating mode is selected with OPER_IND, OPER_TRAC or OPER_PAR and read with OPER?",
             source="upstream_code", ref=f"{CLONE}:1799-1846"),
        Fact("The source is constant current with CONT_CC or constant voltage with CONT_CV, read with CONT?",
             source="upstream_code", ref=f"{CLONE}:1849-1890"),
        Fact("The voltage setpoint is written as VSET <volts> and read with VSET?",
             source="upstream_code", ref=f"{CLONE}:1892-1911"),
        Fact("The current setpoint is written as ISET <amperes> and read with ISET?",
             source="upstream_code", ref=f"{CLONE}:1913-1947"),
        Fact("The measured output voltage and current are read with VOUT? and IOUT?",
             source="upstream_code", ref=f"{CLONE}:1968-1996"),
        Fact("The protection mode is read with PROT? and the reply names LIMITING or CUT-OUT",
             source="upstream_code", ref=f"{CLONE}:2020-2035"),
    ]
    safe_state = "output disabled with OUT_OFF"
    idn = True

    parameters = {
        "output": Field(
            "string", writable=True,
            description="Output state: ON (OUT_ON) or OFF (OUT_OFF)",
            limit=Limit(allowed=["ON", "OFF"], source="upstream_code", ref=f"{CLONE}:1766-1797",
                        reason="OUT_ON and OUT_OFF are the two output commands the upstream class writes")),
        "source": Field(
            "string", writable=True,
            description="Active source: A (SEL_A) or B (SEL_B)",
            limit=Limit(allowed=["A", "B"], source="upstream_code", ref=f"{CLONE}:1724-1744",
                        reason="SEL_A and SEL_B select the two sources")),
        "operating_mode": Field(
            "string", writable=True,
            description="Operating mode: IND (independent), TRAC (tracking) or PAR (parallel)",
            limit=Limit(allowed=["IND", "TRAC", "PAR"], source="upstream_code",
                        ref=f"{CLONE}:1799-1824",
                        reason="OPER_IND, OPER_TRAC and OPER_PAR are the three mode commands")),
        "source_type": Field(
            "string", writable=True,
            description="Regulation mode: CC (constant current, CONT_CC) or CV (constant voltage, CONT_CV)",
            limit=Limit(allowed=["CC", "CV"], source="upstream_code", ref=f"{CLONE}:1849-1871",
                        reason="CONT_CC and CONT_CV are the two regulation commands")),
        "protection": Field(
            "string",
            description="Protection mode read with PROT?: LIM (limiting) or CUT (cut-out)"),
        "voltage": Field(
            "number", unit="V", writable=True,
            description="Voltage setpoint in volts (VSET)",
            limit=Limit.operator_required(
                "The upstream code states the voltage setpoint in volts but gives no voltage range; the operator "
                "sets the deployment bound in site-limits.json.")),
        "current": Field(
            "number", unit="A", writable=True,
            description="Current setpoint in amperes (ISET)",
            limit=Limit.operator_required(
                "The upstream docstring gives only mode-dependent current ranges, written with non-numeric glyphs; "
                "no single bound is stated, so the operator sets the deployment bound in site-limits.json.")),
        "measured_voltage": Field(
            "number", unit="V",
            description="Measured output voltage in volts (VOUT?)"),
        "measured_current": Field(
            "number", unit="A",
            description="Measured output current in amperes (IOUT?)"),
    }

    reads = {
        "output": {"query": "OUT?", "parse": {"kind": "regex", "pattern": r"OUT_(?P<state>ON|OFF)",
                                              "group": "state"}},
        "source": {"query": "SEL?", "parse": {"kind": "regex", "pattern": r"SEL_(?P<state>[AB])",
                                              "group": "state"}},
        "operating_mode": {"query": "OPER?",
                           "parse": {"kind": "regex", "pattern": r"OPER_(?P<state>IND|TRAC|PAR)",
                                     "group": "state"}},
        "source_type": {"query": "CONT?", "parse": {"kind": "regex", "pattern": r"CONT_(?P<state>CC|CV)",
                                                    "group": "state"}},
        "protection": {"query": "PROT?", "parse": {"kind": "regex", "pattern": r"PROT_(?P<state>LIM|CUT)",
                                                   "group": "state"}},
        "voltage": {"query": "VSET?", "parse": {"kind": "float"}},
        "current": {"query": "ISET?", "parse": {"kind": "float"}},
        "measured_voltage": {"query": "VOUT?", "parse": {"kind": "float"}},
        "measured_current": {"query": "IOUT?", "parse": {"kind": "float"}},
    }

    writes = {
        "output": {"write": "OUT_{value}", "type": "string"},
        "source": {"write": "SEL_{value}", "type": "string"},
        "operating_mode": {"write": "OPER_{value}", "type": "string"},
        "source_type": {"write": "CONT_{value}", "type": "string"},
        "voltage": {"write": "VSET {value}", "type": "number"},
        "current": {"write": "ISET {value}", "type": "number"},
    }

    commands = {
        "x-cap.akperuht.output_off.v1": {
            "write": "OUT_OFF",
            "description": "Disable the power supply output",
        },
    }
    actions = {
        "x-cap.akperuht.output_off.v1": Action(
            name="output_off",
            description="Disable the power supply output (the declared safe state)",
            safe_state=True),
    }
    safety_bindings = {"estop": {"write": "OUT_OFF"}}
