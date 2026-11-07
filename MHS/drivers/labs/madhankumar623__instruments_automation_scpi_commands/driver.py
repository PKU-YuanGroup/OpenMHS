"""OpenMHS driver for gh.madhankumar623/instruments_automation_scpi_commands: the DC supply of a lab script.

The upstream clone is one Python script of module-level functions, not a class (PowerSupply_Automation.py:99-130).
It opens three VISA resources and a Modbus client at import time (lines 49-57) and maps five MCU samples S1 to S5
onto three supplies (lines 60-66).  This package does not import or run that script.  It is a ScpiDriver command map
for the first supply, ``DCsupply_1`` (line 11), and the two channels the upstream maps to it: channel 2 (S1) and
channel 3 (S2) (lines 60-66).  The other two supplies and the Modbus temperature path are not covered.

The upstream functions select a channel with ``INST:NSEL`` and then write ``VOLT``, ``CURR`` or ``OUTP`` (lines
99-130).  The command map repeats those words and the channel selection on one line, for example
``INST:NSEL 2;VOLT {value:g}``.  The upstream never reads the set points or the output state back; this driver uses
the standard query forms ``VOLT?``, ``CURR?`` and ``OUTP?`` so a write has an observable state, and it reads the
measured voltage and current with the upstream's ``MEAS:VOLT?`` and ``MEAS:CURR?`` queries.  The SCPI bridge opens
the transport itself: ``native`` names the card's Set_Voltage entry function for traceability only, and the clone is
never imported.

* reads: the voltage and current set points and the output state of channels 2 and 3, and their measured voltage
  and current;
* writes: the two voltage set points, the two current set points and the two output states.  The clone states no
  output voltage or current range: DEFAULT_VOLTAGE = 13.6 V and DEFAULT_CURRENT_LIMIT = 0.1 A are only the starting
  values of initialize_supplies, which the comment says can be changed (lines 26-28).  Every numeric set point is
  therefore ``Limit.operator_required`` and is refused ``MHS.SAFETY.LIMITS_UNSET`` until the operator supplies the
  installed unit's range in site-limits.json (site-limits.example.json is an example only);
* safety: the supply can energize an external load, so the device is R2.  The native stop switches both controlled
  channels off (``INST:NSEL 2;OUTP OFF;INST:NSEL 3;OUTP OFF``), the same command the upstream shutdown_supplies loop
  sends for every mapped channel (lines 242-249).  The safe state is a ``safe_state=True`` action with that command;
  no line of the clone documents an independent hardware e-stop, so ``estop_physical_ref`` is not set.

Every Fact and Limit cites a line of the clone at the pinned commit 2080effa969d0a911188f24e92f5d9551f1b22c9.  This
package is model-authored and unreviewed; the fake backend is checked by the acceptance gate and nothing here ran on
hardware.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

#: The upstream script, relative to the clone root.
UPSTREAM = "PowerSupply_Automation.py"

#: The clone states no output voltage or current range; the two macros are only the starting profile of the script.
_VOLTAGE_BOUND = Limit.operator_required(
    "the clone states no output voltage range: Set_Voltage writes VOLT with any value, and DEFAULT_VOLTAGE = 13.6 V is "
    "only the starting value the comment says can be changed (PowerSupply_Automation.py:26-28, 99-102); the operator "
    "supplies the installed unit's range in site-limits.json")
_CURRENT_BOUND = Limit.operator_required(
    "the clone states no output current range: Set_Current writes CURR with any value, and DEFAULT_CURRENT_LIMIT = "
    "0.1 A is only the starting value the comment says can be changed (PowerSupply_Automation.py:26-28, 105-108); "
    "the operator supplies the installed unit's range in site-limits.json")

#: The safe state of the one supply this package serves: both controlled channels off.  The same command is the
#: native stop and the command of the safe_state=True action.
SAFE_COMMAND = "INST:NSEL 2;OUTP OFF;INST:NSEL 3;OUTP OFF"


class InstrumentsAutomationScpiCommands(ScpiDriver):
    device_id = "madhankumar623-psu"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R2"
    native = "PowerSupply_Automation:Set_Voltage"
    backends = {"fake": ".fake:FakePowerSupply"}
    model = "Programmable DC power supply (DCsupply_1, channels 2 and 3)"
    display_name = "Programmable DC power supply (PowerSupply_Automation.py, DCsupply_1)"
    tags = ["power-supply", "dc-source", "scpi", "visa", "mcu-monitoring"]
    facts = [
        Fact("The clone is a script of module-level functions: it opens three VISA resources and a Modbus client at "
             "import time, before any function is called", source="upstream_code", ref=f"{UPSTREAM}:49-57"),
        Fact("DCsupply_1 is the VISA resource USB0::0x2A8D::0x1202::MY61005119::0::INSTR", source="upstream_code",
             ref=f"{UPSTREAM}:11"),
        Fact("SUPPLY_CHANNEL_MAP maps S1 to powerSupply_1 channel 2 and S2 to powerSupply_1 channel 3",
             source="upstream_code", ref=f"{UPSTREAM}:60-66"),
        Fact("Set_Voltage selects the channel with INST:NSEL and writes VOLT", source="upstream_code",
             ref=f"{UPSTREAM}:99-102"),
        Fact("Set_Current selects the channel with INST:NSEL and writes CURR", source="upstream_code",
             ref=f"{UPSTREAM}:105-108"),
        Fact("Get_Voltage selects the channel with INST:NSEL and queries MEAS:VOLT?", source="upstream_code",
             ref=f"{UPSTREAM}:111-114"),
        Fact("Get_Current selects the channel with INST:NSEL and queries MEAS:CURR?", source="upstream_code",
             ref=f"{UPSTREAM}:117-120"),
        Fact("ON_OFF_Voltage selects the channel, accepts only ON or OFF and writes OUTP with that state",
             source="upstream_code", ref=f"{UPSTREAM}:123-130"),
        Fact("DEFAULT_VOLTAGE = 13.6 V and DEFAULT_CURRENT_LIMIT = 0.1 A are the starting profile of "
             "initialize_supplies; the comment says they can be changed", source="upstream_code",
             ref=f"{UPSTREAM}:26-28"),
        Fact("The README calls 13.6 V and 0.1 A default test parameters that can be changed before a new batch",
             source="vendor_doc", ref="README.md:39-48"),
        Fact("shutdown_supplies turns every mapped channel off through ON_OFF_Voltage", source="upstream_code",
             ref=f"{UPSTREAM}:242-249"),
        Fact("The README maps five MCU samples S1-S5 onto three supplies", source="vendor_doc",
             ref="README.md:23-37"),
        Fact("The chamber temperature is read from a Modbus holding register, not from the supply",
             source="upstream_code", ref=f"{UPSTREAM}:133-141"),
        Fact("The README says the temperature is a Modbus holding register value divided by 10.0", source="vendor_doc",
             ref="README.md:125"),
    ]
    safe_state = ("both controlled outputs of DCsupply_1 are switched off "
                  "(INST:NSEL 2;OUTP OFF and INST:NSEL 3;OUTP OFF); the voltage and current set points are unchanged")
    idn = False

    parameters = {
        "voltage_setpoint_ch2": Field(
            "number", unit="V", writable=True,
            description="Channel 2 voltage set point (S1 on DCsupply_1; INST:NSEL 2;VOLT)",
            limit=_VOLTAGE_BOUND),
        "current_setpoint_ch2": Field(
            "number", unit="A", writable=True,
            description="Channel 2 current set point (S1 on DCsupply_1; INST:NSEL 2;CURR)",
            limit=_CURRENT_BOUND),
        "output_enabled_ch2": Field(
            "boolean", writable=True,
            description="Channel 2 output enabled (S1 on DCsupply_1; OUTP ON or OUTP OFF)"),
        "voltage_ch2": Field(
            "number", unit="V",
            description="Channel 2 measured output voltage (MEAS:VOLT? after INST:NSEL 2)"),
        "current_ch2": Field(
            "number", unit="A",
            description="Channel 2 measured output current (MEAS:CURR? after INST:NSEL 2)"),
        "voltage_setpoint_ch3": Field(
            "number", unit="V", writable=True,
            description="Channel 3 voltage set point (S2 on DCsupply_1; INST:NSEL 3;VOLT)",
            limit=_VOLTAGE_BOUND),
        "current_setpoint_ch3": Field(
            "number", unit="A", writable=True,
            description="Channel 3 current set point (S2 on DCsupply_1; INST:NSEL 3;CURR)",
            limit=_CURRENT_BOUND),
        "output_enabled_ch3": Field(
            "boolean", writable=True,
            description="Channel 3 output enabled (S2 on DCsupply_1; OUTP ON or OUTP OFF)"),
        "voltage_ch3": Field(
            "number", unit="V",
            description="Channel 3 measured output voltage (MEAS:VOLT? after INST:NSEL 3)"),
        "current_ch3": Field(
            "number", unit="A",
            description="Channel 3 measured output current (MEAS:CURR? after INST:NSEL 3)"),
    }
    reads = {
        "voltage_setpoint_ch2": {"query": "INST:NSEL 2;VOLT?", "parse": {"kind": "float"}},
        "current_setpoint_ch2": {"query": "INST:NSEL 2;CURR?", "parse": {"kind": "float"}},
        "output_enabled_ch2": {"query": "INST:NSEL 2;OUTP?", "parse": {"kind": "bool"}},
        "voltage_ch2": {"query": "INST:NSEL 2;MEAS:VOLT?", "parse": {"kind": "float"}},
        "current_ch2": {"query": "INST:NSEL 2;MEAS:CURR?", "parse": {"kind": "float"}},
        "voltage_setpoint_ch3": {"query": "INST:NSEL 3;VOLT?", "parse": {"kind": "float"}},
        "current_setpoint_ch3": {"query": "INST:NSEL 3;CURR?", "parse": {"kind": "float"}},
        "output_enabled_ch3": {"query": "INST:NSEL 3;OUTP?", "parse": {"kind": "bool"}},
        "voltage_ch3": {"query": "INST:NSEL 3;MEAS:VOLT?", "parse": {"kind": "float"}},
        "current_ch3": {"query": "INST:NSEL 3;MEAS:CURR?", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage_setpoint_ch2": {"write": "INST:NSEL 2;VOLT {value:g}", "type": "number"},
        "current_setpoint_ch2": {"write": "INST:NSEL 2;CURR {value:g}", "type": "number"},
        "output_enabled_ch2": {"write": "INST:NSEL 2;OUTP {value}", "type": "string",
                               "enum_map": {True: "ON", False: "OFF"}},
        "voltage_setpoint_ch3": {"write": "INST:NSEL 3;VOLT {value:g}", "type": "number"},
        "current_setpoint_ch3": {"write": "INST:NSEL 3;CURR {value:g}", "type": "number"},
        "output_enabled_ch3": {"write": "INST:NSEL 3;OUTP {value}", "type": "string",
                               "enum_map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.madhankumar623.output_off.v1": {
            "write": SAFE_COMMAND,
            "description": "Switch both controlled channel outputs of DCsupply_1 off",
        },
    }
    actions = {
        "x-cap.madhankumar623.output_off.v1": Action(
            name="output_off", safe_state=True, risk="R2",
            description="Switch both controlled channel outputs of DCsupply_1 off (INST:NSEL 2;OUTP OFF and "
                        "INST:NSEL 3;OUTP OFF); it takes no input and is the declared safe state"),
    }
    safety_bindings = {"estop": {"write": SAFE_COMMAND}}
