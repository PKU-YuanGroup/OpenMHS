"""OpenMHS driver for gh.daanwielens/research-python: the Lake Shore 332 temperature controller.

The upstream repository is a set of Tkinter programs, not an importable library: importing ``Lake.py`` builds its
window and opens a PyVISA resource (``Lake.py:191, 266-269``).  This package therefore binds the Lake Shore
commands that occur verbatim in ``Lake.py`` through the card's ``ScpiDriver`` family; the upstream module is never
imported.  The driver covers one device of the repository; the SR830 lock-in and the Oxford IPS120/ITC503 magnet and
temperature controllers are separate devices and are not covered here.

* reads: the control-loop temperature (``KRDG?``), the Celsius reading (``CRDG?``), the loop-1 setpoint
  (``SETP? 1``), heater range (``RANGE?``), heater output (``HTR?``), loop-1 PID reply (``PID? 1``) and manual
  output (``MOUT? 1``);
* writes: the loop-1 setpoint (``SETP 1,<kelvin>``), the heater range (``RANGE <index>``) and the manual output
  (``MOUT 1,<percent>``), each limited by a range the upstream GUI states;
* the ``x-cap.daanwielens.set_pid.v1`` action writes the three loop-1 PID terms in the one command the upstream
  sends (``PID 1,<p>,<i>,<d>``); the catalogue has no PID class, so it is an extension;
* safety: the e-stop and the ``x-cap.daanwielens.heater_off.v1`` safe-state action write ``RANGE 0``, which is the
  upstream's first heater range (Off).  The declared risk is R2 because the controller drives a heater whose high
  range is 50 W (``Lake.py:33``).

Every Fact and Limit cites a line of the clone at the pinned commit
(c17811c9b43bc581f5523f1e9eafd9dce1fdb9d2).  This package is model-authored and unreviewed: it is checked on the
fake backend only, its evidence is ``contract_checked`` and it never ran on hardware.  The hardware backend of the
SCPI bridge needs the operator's ``visa_resource`` (the upstream hardcodes ``GPIB0::12::INSTR``) or ``host``/``port``.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

LAKE = "Lake.py"


class Lakeshore332(ScpiDriver):
    """Lake Shore Model 332 temperature controller over the text commands of the upstream program."""

    device_id = "lakeshore332"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    backends = {"fake": ".fake:FakeLakeshore332"}
    vendor = "Lake Shore Cryotronics"
    model = "Model 332 temperature controller"
    display_name = "Lake Shore Model 332 temperature controller"
    tags = ["temperature controller", "lakeshore", "model 332", "pid", "scpi", "gpib"]
    facts = [
        Fact("The upstream program controls the Lake Shore 332 temperature controller and its PID loop",
             source="vendor_doc", ref="README.md:39-41"),
        Fact("The upstream programs reach the instruments through PyVISA and NI-VISA",
             source="vendor_doc", ref="README.md:5"),
        Fact("The Lake Shore is opened as the VISA resource GPIB0::12::INSTR", source="upstream_code",
             ref=f"{LAKE}:47"),
        Fact("The control-loop temperature is read with KRDG? and the Celsius reading with CRDG?",
             source="upstream_code", ref=f"{LAKE}:48-49"),
        Fact("The heater range is read with RANGE? and the heater output with HTR?", source="upstream_code",
             ref=f"{LAKE}:50-51"),
        Fact("Setpoint 1 is read with SETP? 1", source="upstream_code", ref=f"{LAKE}:52"),
        Fact("The setpoint entry is labelled with kelvin", source="upstream_code", ref=f"{LAKE}:118"),
        Fact("Setpoint 1 is written as SETP 1,<value>", source="upstream_code", ref=f"{LAKE}:177"),
        Fact("Loop 1 PID is read with PID? 1", source="upstream_code", ref=f"{LAKE}:85"),
        Fact("Loop 1 PID is written as PID 1,<p>,<i>,<d>", source="upstream_code", ref=f"{LAKE}:179"),
        Fact("Manual output 1 is read with MOUT? 1", source="upstream_code", ref=f"{LAKE}:86"),
        Fact("Manual output is written as MOUT 1,<value>", source="upstream_code", ref=f"{LAKE}:178"),
        Fact("The heater range is written as RANGE <index>", source="upstream_code", ref=f"{LAKE}:180"),
        Fact("Heater range 0 is Off; ranges 1, 2 and 3 are low (0.5 W), medium (5 W) and high (50 W)",
             source="upstream_code", ref=f"{LAKE}:33"),
        Fact("The setpoint entry is labelled 4.5 to 280", source="upstream_code", ref=f"{LAKE}:119"),
        Fact("The P and I entries are labelled 0.1 to 1000", source="upstream_code", ref=f"{LAKE}:124-129"),
        Fact("The D entry is labelled 0 to 200", source="upstream_code", ref=f"{LAKE}:134"),
        Fact("The manual output entry is labelled 0.0 to 100.0", source="upstream_code", ref=f"{LAKE}:139"),
        Fact("The manual output is displayed in percent", source="upstream_code", ref=f"{LAKE}:247"),
        Fact("The controller temperature is displayed in kelvin and the Celsius reading with a degree-Celsius "
             "suffix", source="upstream_code", ref=f"{LAKE}:54-55"),
        Fact("The heater output is displayed in percent", source="upstream_code", ref=f"{LAKE}:57"),
        Fact("Importing the upstream file builds the Tk window, so this package does not import it",
             source="upstream_code", ref=f"{LAKE}:191"),
    ]
    safe_state = "heater range set to 0 (off), so the heater output is disabled"
    idn = False

    parameters = {
        "temperature": Field(
            "number", unit="K", description="Control-loop temperature in kelvin (KRDG?)"),
        "temperature_celsius": Field(
            "number", unit="Cel", description="Temperature in degrees Celsius (CRDG?)"),
        "setpoint": Field(
            "number", unit="K", writable=True,
            description="Loop 1 setpoint in kelvin, written as SETP 1,<value>",
            limit=Limit(min=4.5, max=280, source="upstream_code", ref=f"{LAKE}:119",
                        reason="the setpoint entry is labelled [4.5 - 280] K")),
        "heater_range": Field(
            "integer", unit="1", writable=True,
            description="Heater range index 0 (off), 1 (low), 2 (medium) or 3 (high), written as RANGE <value>",
            limit=Limit(allowed=[0, 1, 2, 3], source="upstream_code", ref=f"{LAKE}:33",
                        reason="the heater range dictionary maps the indexes 0, 1, 2 and 3 to Off, Low, "
                               "Medium and High")),
        "heater_output": Field(
            "number", unit="%", description="Heater output in percent (HTR?)"),
        "pid": Field(
            "string", description="Loop 1 PID terms as the controller reports them (PID? 1)"),
        "manual_output": Field(
            "number", unit="%", writable=True,
            description="Manual heater output in percent, written as MOUT 1,<value>",
            limit=Limit(min=0.0, max=100.0, source="upstream_code", ref=f"{LAKE}:139",
                        reason="the manual output entry is labelled [0.0 - 100.0] percent")),
    }

    reads = {
        "temperature": {"query": "KRDG?", "parse": {"kind": "float"}},
        "temperature_celsius": {"query": "CRDG?", "parse": {"kind": "float"}},
        "setpoint": {"query": "SETP? 1", "parse": {"kind": "float"}},
        "heater_range": {"query": "RANGE?", "parse": {"kind": "int"}},
        "heater_output": {"query": "HTR?", "parse": {"kind": "float"}},
        "pid": {"query": "PID? 1", "parse": {"kind": "str"}},
        "manual_output": {"query": "MOUT? 1", "parse": {"kind": "float"}},
    }

    writes = {
        "setpoint": {"write": "SETP 1,{value:.6g}", "type": "number"},
        "heater_range": {"write": "RANGE {value:d}", "type": "integer"},
        "manual_output": {"write": "MOUT 1,{value:.6g}", "type": "number"},
    }

    commands = {
        "x-cap.daanwielens.set_pid.v1": {
            "write": "PID 1,{p:g},{i:g},{d:g}",
            "args": {
                "p": {"from": "p", "type": "number"},
                "i": {"from": "i", "type": "number"},
                "d": {"from": "d", "type": "number"},
            },
            "description": "Write the three loop-1 PID terms as one PID command",
        },
        "x-cap.daanwielens.heater_off.v1": {
            "write": "RANGE 0",
            "description": "Set the heater range to 0 (off); the declared safe state",
        },
    }

    actions = {
        "x-cap.daanwielens.set_pid.v1": Action(
            name="set_pid",
            description="Set the loop-1 proportional, integral and derivative terms",
            risk="R2",
            input={
                "p": Field("number", unit="1", description="Proportional term",
                           limit=Limit(min=0.1, max=1000, source="upstream_code", ref=f"{LAKE}:124",
                                       reason="the P entry is labelled [0.1 - 1000]")),
                "i": Field("number", unit="1", description="Integral term",
                           limit=Limit(min=0.1, max=1000, source="upstream_code", ref=f"{LAKE}:129",
                                       reason="the I entry is labelled [0.1 - 1000]")),
                "d": Field("number", unit="1", description="Derivative term",
                           limit=Limit(min=0, max=200, source="upstream_code", ref=f"{LAKE}:134",
                                       reason="the D entry is labelled [0 - 200]")),
            },
        ),
        "x-cap.daanwielens.heater_off.v1": Action(
            name="heater_off",
            description="Set the heater range to 0 (off) as the declared safe state",
            risk="R2",
            safe_state=True,
        ),
    }

    safety_bindings = {"estop": {"write": "RANGE 0"}}
