"""OpenMHS driver for gh.yongxb/keithley-smu-controls: the Keithley 2450 source-measure unit.

The upstream repository is a set of standalone PyVISA/PyMeasure scripts, not a class or a package
(``Keithley_control_2450.py:37-40``).  The 2450 script opens the first USB VISA resource and writes Keithley
Test Script Processor (TSP) text lines through ``keithley.write`` (lines 45-87); it queries ``*IDN?`` (line 41)
and reads measurements back with ``print(...)`` (lines 123-131).  This package does not import or run the clone:
the interface is line-oriented text, so the driver is a :class:`~mhs.driver.ScpiDriver` command map as the card's
family and helper say, and the SCPI bridge opens a raw-TCP or VISA transport itself.  ``native`` names the card's
2450 entry object for traceability only (the clone has no class).

Covered, in the current-source mode the 2450 script selects (``is_source_current = True``, line 11):

* the DC source current (``smu.source.func = smu.FUNC_DC_CURRENT`` and ``smu.source.level``, lines 57-58);
* the voltage compliance limit while sourcing current (``smu.source.vlimit.level``, line 61);
* the source output (``smu.source.output = smu.ON`` / ``smu.OFF``, lines 87 and 184);
* the measured voltage and current, each read with the function selection and ``smu.measure.read()`` of lines
  123-131;
* the e-stop and a ``safe_state=True`` action that disable the output and zero the source level.

Every Fact cites a line of the clone at the pinned commit (6afb567c29125beb133facbbe62bb88c37d8529f).  The
clone states no source or compliance range: both writable quantities are ``Limit.operator_required`` and the
site-limits overlay supplies the envelope.  The package is model-authored and unreviewed, and no hardware backend
was run.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

UPSTREAM = "Keithley_control_2450.py"

#: Written by the e-stop, the safe-state action and the safe-state binding: output off first, then the source level
#: zeroed.  The clone zeroes the level, waits soak_time and then disables the output (lines 173-184); an e-stop cannot
#: wait, so this driver disables the output first and does not reproduce the soak delay.
SAFE_COMMAND = "smu.source.output = smu.OFF;smu.source.level = 0"


class Keithley2450(ScpiDriver):
    device_id = "keithley2450"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R3"
    native = "Keithley_control_2450:keithley"
    backends = {"fake": ".fake:FakeKeithley2450"}
    vendor, model = "Keithley Instruments", "Keithley 2450 source-measure unit"
    display_name = "Keithley 2450 source-measure unit"
    tags = ["keithley", "2450", "source-measure unit", "smu", "tsp", "visa"]
    facts = [
        Fact("The repository contains standalone scripts for the Keithley 2400, 2450 and 2657A source-measure units",
             source="vendor_doc", ref="README.md:12-14"),
        Fact("The 2450 script opens the first USB VISA resource as the module-level object keithley",
             source="upstream_code", ref=f"{UPSTREAM}:37-40"),
        Fact("The 2450 script queries *IDN? after opening the resource", source="upstream_code",
             ref=f"{UPSTREAM}:41"),
        Fact("The 2450 script configures current source mode with smu.source.func = smu.FUNC_DC_CURRENT, "
             "smu.source.level and smu.source.vlimit.level", source="upstream_code",
             ref=f"{UPSTREAM}:56-63"),
        Fact("The 2450 script configures voltage source mode with smu.source.func = smu.FUNC_DC_VOLTAGE, "
             "smu.source.level and smu.source.ilimit.level", source="upstream_code",
             ref=f"{UPSTREAM}:67-74"),
        Fact("The 2450 script turns the source output on with smu.source.output = smu.ON", source="upstream_code",
             ref=f"{UPSTREAM}:87"),
        Fact("The 2450 script sets the source level to zero and waits soak_time before writing "
             "smu.source.output = smu.OFF", source="upstream_code", ref=f"{UPSTREAM}:173-184"),
        Fact("The 2450 script reads a voltage measurement by setting smu.measure.func to smu.FUNC_DC_VOLTAGE and "
             "calling smu.measure.read on a source buffer", source="upstream_code", ref=f"{UPSTREAM}:123-126"),
        Fact("The 2450 script reads a current measurement by setting smu.measure.func to smu.FUNC_DC_CURRENT and "
             "calling smu.measure.read on a source buffer", source="upstream_code", ref=f"{UPSTREAM}:128-131"),
        Fact("The 2450 script creates a source buffer with buffer.make(buffer_size) before measuring",
             source="upstream_code", ref=f"{UPSTREAM}:80"),
        Fact("The README names PyVISA as the connection library for the 2450 and 2657A and PyMeasure for the 2400",
             source="vendor_doc", ref="README.md:20-21"),
    ]
    safe_state = "source output disabled and the source level set to zero"

    parameters = {
        "voltage": Field("number", unit="V",
                         description="Measured voltage (smu.measure.read after selecting smu.FUNC_DC_VOLTAGE)"),
        "current": Field("number", unit="A",
                         description="Measured current (smu.measure.read after selecting smu.FUNC_DC_CURRENT)"),
        "source_current": Field(
            "number", unit="A", writable=True,
            description="DC current source level (smu.source.level in current source mode); the operator supplies "
                        "the safe envelope",
            limit=Limit.operator_required(
                "the clone writes smu.source.level with the value of its input parameter and states no current "
                "range (Keithley_control_2450.py:56-63); the operator must supply the source-current envelope")),
        "compliance_voltage": Field(
            "number", unit="V", writable=True,
            description="Voltage compliance limit while sourcing current (smu.source.vlimit.level); the operator "
                        "supplies the safe envelope",
            limit=Limit.operator_required(
                "the clone sets smu.source.vlimit.level from its voltage_limit parameter and states no compliance "
                "range (Keithley_control_2450.py:61-63); the operator must supply the compliance envelope")),
        "output": Field("boolean", writable=True,
                        description="Source output enabled (smu.source.output = smu.ON) or disabled"),
    }
    reads = {
        "voltage": {"query": "smu.measure.func = smu.FUNC_DC_VOLTAGE;print(smu.measure.read())",
                    "parse": {"kind": "float"}},
        "current": {"query": "smu.measure.func = smu.FUNC_DC_CURRENT;print(smu.measure.read())",
                    "parse": {"kind": "float"}},
        "source_current": {"query": "print(smu.source.level)", "parse": {"kind": "float"}},
        "compliance_voltage": {"query": "print(smu.source.vlimit.level)", "parse": {"kind": "float"}},
        "output": {"query": "print(smu.source.output)",
                   "parse": {"kind": "bool", "true": "smu.ON", "false": "smu.OFF"}},
    }
    writes = {
        "source_current": {"write": "smu.source.func = smu.FUNC_DC_CURRENT;smu.source.level = {value:.10g}",
                           "type": "number"},
        "compliance_voltage": {"write": "smu.source.vlimit.level = {value:.10g}", "type": "number"},
        "output": {"write": "smu.source.output = {value}", "type": "string",
                   "enum_map": {True: "smu.ON", False: "smu.OFF"}},
    }
    commands = {
        "x-cap.yongxb.safe_state.v1": {
            "write": SAFE_COMMAND,
            "description": "Disable the source output and set the source current to zero",
        },
    }
    actions = {
        "x-cap.yongxb.safe_state.v1": Action(
            name="safe_state",
            description="Disable the source output and set the source current to zero",
            safe_state=True),
    }
    safety_bindings = {
        "estop": {"write": SAFE_COMMAND},
        "safe_state": {"write": SAFE_COMMAND},
    }
