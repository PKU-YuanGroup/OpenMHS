"""OpenMHS driver for gh.aaron-mott/keithley-2200: the Keithley 2200 series DC power supply over SCPI.

The upstream clone is one class, ``KEI2220S`` (``2220 Programmable DC Power Supplies.py:11``).  It opens a VISA
resource in its constructor (lines 35-39) and every method writes or queries one line of text: ``VOLT`` and
``CURR`` for the set points, ``OUTP`` for the output relay, ``VOLT:PROT`` and ``VOLT:PROT:STAT`` for overvoltage
protection, ``MEAS:VOLT?`` and ``MEAS:CURR?`` for a new measurement, and ``FETCh:POW?`` for the last measured
power.  That is line-oriented SCPI, so this package is a :class:`~mhs.driver.ScpiDriver` command map; the bridge
opens the transport itself (raw SCPI over TCP or a VISA resource) and neither the clone nor ``visa`` is imported.
The upstream constructor is also misspelled (``__innit__``) and calls ``open_resource(self.instr_address)``
although the parameter is named ``inst_address`` (lines 13, 36), so the upstream class is not usable as shipped.

* reads: the voltage and current set points, the output state, the overvoltage protection threshold and its
  enable state, and the last/current voltage, current and power measurements;
* writes: voltage, current, output on/off, overvoltage protection threshold and its enable state.  No text of the
  clone states the range of the connected unit: ``set_volt`` and ``set_ovp`` have a 0 through 30 V code check
  (lines 695-699 and 721-725) while ``set_curr`` lists different maxima for 2200-60-2 and 2200-72-1 models
  (lines 245-257), so every numeric write is ``Limit.operator_required`` until the operator's overlay supplies
  the range of the installed supply;
* safety: the e-stop writes ``OUTP OFF``.  The clone documents no hardware emergency-stop input, so the
  independent stop required at this risk is the no-input ``x-cap.aaron-mott.output_off.v1`` safe-state action,
  which writes the same command through the same SCPI transport.

Every Fact cites a line of the clone at the pinned commit 348fb5df70d92bd96593452e188c90f0ae3d71c4.  The package
is model-authored and unreviewed; only the fake backend was run, and its values are test data.  It does not claim
a hardware e-stop or a hardware run.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

UPSTREAM = "2220 Programmable DC Power Supplies.py"

#: The numeric writes are operator-required because the clone does not state the range of the connected model.
VOLTAGE_LIMIT = Limit.operator_required(
    "the clone's set_volt writes VOLT but its code check is only 0 through 30 V "
    f"({UPSTREAM}:695-699), while set_curr lists a 2200-60-2 and a 2200-72-1 model "
    f"({UPSTREAM}:245-257); the voltage range of the installed unit is an operator decision")
CURRENT_LIMIT = Limit.operator_required(
    "the clone's set_curr writes CURR and lists different per-model maxima of 1.2, 1.5, 2.5, 3 and 5 A "
    f"({UPSTREAM}:245-257) but never states which model is connected; the current limit of the installed unit "
    "is an operator decision")
OVP_LIMIT = Limit.operator_required(
    "the clone's set_ovp writes VOLT:PROT but its code check is only 0 through 30 V "
    f"({UPSTREAM}:721-725), which does not cover the 60 V and 72 V models the class handles; the protection "
    "range of the installed unit is an operator decision")


class Keithley2200(ScpiDriver):
    device_id = "keithley-2200"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R3"
    native = "pyfile:2220 Programmable DC Power Supplies.py#KEI2220S"
    backends = {"fake": ".fake:FakeKeithley2200"}
    vendor, model = "Keithley Instruments", "Keithley 2200 series programmable DC power supply"
    display_name = "Keithley 2200 series programmable DC power supply (KEI2220S)"
    tags = ["keithley", "2200", "power supply", "dc power supply", "scpi", "visa"]
    facts = [
        Fact("The upstream KEI2220S class defines a misspelled __innit__ routine containing the VISA resource open",
             source="upstream_code", ref=f"{UPSTREAM}:11-39"),
        Fact("The README says the program uses National Instruments VISA to communicate with the Keithley Series "
             "2200 Programmable DC Power Supplies", source="vendor_doc", ref="README.md:1"),
        Fact("The README says the author could not test the code on the instrument", source="vendor_doc",
             ref="README.md:2"),
        Fact("The __innit__ parameter is inst_address, but open_resource is called with self.instr_address, which "
             "the routine never sets", source="upstream_code", ref=f"{UPSTREAM}:13-39"),
        Fact("get_info queries *IDN? and splits the reply into manufacturer, model, serial number and firmware "
             "version", source="upstream_code", ref=f"{UPSTREAM}:120-128"),
        Fact("A new current measurement is initiated with MEAS:CURR? and a new voltage measurement with MEAS:VOLT?",
             source="upstream_code", ref=f"{UPSTREAM}:135-149"),
        Fact("FETCh:POW? returns the last measured output power without initiating a measurement; the instrument "
             "recomputes power about every 100 ms", source="upstream_code", ref=f"{UPSTREAM}:109-118"),
        Fact("set_curr writes CURR and accepts a per-model maximum of 1.2, 1.5, 2.5, 3 or 5 A",
             source="upstream_code", ref=f"{UPSTREAM}:245-257"),
        Fact("set_volt writes VOLT and its code accepts only 0 through 30 V", source="upstream_code",
             ref=f"{UPSTREAM}:695-699"),
        Fact("set_ovp writes VOLT:PROT and its code accepts only 0 through 30 V", source="upstream_code",
             ref=f"{UPSTREAM}:721-725"),
        Fact("set_output_state contains OUTP writes and get_output_state queries OUTP?; its ON/OFF string branch appends literal .upper() text", source="upstream_code",
             ref=f"{UPSTREAM}:614-633"),
        Fact("set_ovp_state contains VOLT:PROT:STAT writes and queries; its ON/OFF string branch appends literal .upper() text",
             source="upstream_code", ref=f"{UPSTREAM}:731-750"),
    ]
    safe_state = "output disabled with OUTP OFF (voltage and current set points left unchanged)"
    #: The clone states no expected *IDN? reply.  The bridge probes *IDN? as the upstream get_info does, but this
    #: driver accepts any non-empty identity instead of inventing a pattern.
    idn = True

    parameters = {
        "voltage": Field(
            "number", unit="V", writable=True,
            description="Output voltage set point (VOLT)",
            limit=VOLTAGE_LIMIT),
        "current": Field(
            "number", unit="A", writable=True,
            description="Output current limit set point (CURR)",
            limit=CURRENT_LIMIT),
        "output": Field(
            "boolean", writable=True,
            description="Output relay enabled (OUTP ON) or disabled (OUTP OFF)"),
        "overvoltage_protection": Field(
            "number", unit="V", writable=True,
            description="Overvoltage protection threshold (VOLT:PROT)",
            limit=OVP_LIMIT),
        "overvoltage_protection_enabled": Field(
            "boolean", writable=True,
            description="Overvoltage protection enabled (VOLT:PROT:STAT ON) or disabled (OFF)"),
        "measured_voltage": Field(
            "number", unit="V",
            description="Output voltage measured by a new MEAS:VOLT? measurement"),
        "measured_current": Field(
            "number", unit="A",
            description="Output current measured by a new MEAS:CURR? measurement"),
        "measured_power": Field(
            "number", unit="W",
            description="Last output power measured by the instrument (FETCh:POW?, recomputed about every 100 ms)"),
    }
    reads = {
        "voltage": {"query": "VOLT?", "parse": {"kind": "float"}},
        "current": {"query": "CURR?", "parse": {"kind": "float"}},
        "output": {"query": "OUTP?", "parse": {"kind": "bool"}},
        "overvoltage_protection": {"query": "VOLT:PROT?", "parse": {"kind": "float"}},
        "overvoltage_protection_enabled": {"query": "VOLT:PROT:STAT?", "parse": {"kind": "bool"}},
        "measured_voltage": {"query": "MEAS:VOLT?", "parse": {"kind": "float"}},
        "measured_current": {"query": "MEAS:CURR?", "parse": {"kind": "float"}},
        "measured_power": {"query": "FETCh:POW?", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage": {"write": "VOLT {value:g}", "type": "number"},
        "current": {"write": "CURR {value:g}", "type": "number"},
        "output": {"write": "OUTP {value}", "type": "string", "enum_map": {True: "ON", False: "OFF"}},
        "overvoltage_protection": {"write": "VOLT:PROT {value:g}", "type": "number"},
        "overvoltage_protection_enabled": {"write": "VOLT:PROT:STAT {value}", "type": "string",
                                           "enum_map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.aaron-mott.output_off.v1": {
            "write": "OUTP OFF",
            "description": "Disable the output with OUTP OFF; the declared safe state",
        },
    }
    actions = {
        "x-cap.aaron-mott.output_off.v1": Action(
            name="output_off",
            description="Disable the output with OUTP OFF (the declared safe state); no input, no output",
            safe_state=True),
    }
    safety_bindings = {
        "estop": {"write": "OUTP OFF", "description": "Disable the output with OUTP OFF"},
    }
