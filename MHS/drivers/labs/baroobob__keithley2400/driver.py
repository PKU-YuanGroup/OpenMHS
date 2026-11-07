"""OpenMHS driver for gh.baroobob/keithley2400: the Keithley 2400 source-measure unit over SCPI.

The upstream clone is a Python 2 module of ten module-level functions and no class (``keithley2400.py:28-39``); it
writes SCPI lines through the Prologix GPIB-USB adapter module ``prologixGPIBUSB`` (line 45) and uses Python 2
``print`` statements (lines 154 and 236).  This package does not import or run it.  The interface is line-oriented
text SCPI, so the driver is a :class:`~mhs.driver.ScpiDriver` command map.  The ``native`` attribute names the
connection function of the clone for traceability only (the clone has no class); the SCPI bridge opens a raw-SCPI
TCP socket or a VISA resource itself.

Covered:

* the source-voltage setpoint, the one quantity the upstream lets a user set non-zero: ``voltage`` reads
  ``SOUR:VOLT?`` and writes ``SOUR:VOLT`` (``set_voltage_source``, ``keithley2400.py:152-156``).  The clone states
  no minimum or maximum, only a 5 uV resolution (lines 153-155), so the limit is ``operator_required``;
* the source output, which the upstream enables on connect with ``OUTP ON`` (line 81): ``output`` reads ``OUTP?``
  and writes ``OUTP ON`` or ``OUTP OFF``.  The driver does not enable the output on connect; the operator does;
* three single-sample measurement actions, current, voltage and resistance.  Each configures the measurement
  function the clone configures (``current_mode``, ``voltage_mode``, ``resistance_mode``, lines 64-68, 160-164 and
  146-148) and then sends the read sequence of ``read`` for one sample (lines 114-121).  The interval bound comes
  from the docstring of ``read`` (lines 248-251).  The current action leaves the source voltage at its setpoint;
  the voltage action sets the source current to zero as the clone does.  The read-only ``trigger_delay`` state
  reads back the ``TRIG:DEL`` the last measurement action applied;
* the e-stop and the ``safe_state=True`` action write ``OUTP OFF`` and zero both source quantities.

Not covered: multi-sample reads (``samples > 1`` returns the ``Time`` and ``Data`` lists, lines 139-142), live
readings (``enable_live_readings``, lines 86-90), the Prologix adapter setup (GPIB address 24 and clear, lines
74-77), and the Python 2 transport.  The hardware backend expects a preconfigured raw-SCPI TCP endpoint or VISA
resource for the 2400; it does not configure the Prologix adapter.  No hardware backend was run; this package is
model-authored and unreviewed.
"""

from mhs.driver import Action, Fact, Field, Limit, ScpiDriver

UPSTREAM = "keithley2400.py"

#: The interval bound of ``read`` for one sample: 0 through 99 (keithley2400.py:248-250).  The same docstring gives
#: the allowed values 0, 1, 10, 60, 600 and 3600 for more than one sample, which this single-sample driver does not
#: cover.
INTERVAL_LIMIT = Limit(min=0, max=99, unit="s", source="upstream_code", ref=f"{UPSTREAM}:248-250",
                       reason="the read docstring allows an interval of 0 through 99 s when one sample is requested")


def _interval_field() -> Field:
    return Field("number", unit="s",
                 description="Delay between the trigger and each sample (0 through 99 s for one sample)",
                 limit=INTERVAL_LIMIT)


class Keithley2400(ScpiDriver):
    device_id = "keithley2400"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R3"
    native = "keithley2400:open_connection"
    backends = {"fake": ".fake:FakeKeithley2400"}
    vendor, model = "Keithley Instruments", "Keithley 2400 source-measure unit"
    display_name = "Keithley 2400 source-measure unit"
    tags = ["keithley", "2400", "source-measure unit", "smu", "scpi"]
    facts = [
        Fact("The user API is ten module-level functions, not a class", source="upstream_code",
             ref=f"{UPSTREAM}:28-39"),
        Fact("The module imports prologixGPIBUSB as the GPIB transport and Error from errors", source="upstream_code",
             ref=f"{UPSTREAM}:44-46"),
        Fact("The module uses Python 2 print statements", source="upstream_code", ref=f"{UPSTREAM}:154"),
        Fact("open_connection sets the GPIB address to 24 and clears the selected device", source="upstream_code",
             ref=f"{UPSTREAM}:74-77"),
        Fact("open_connection checks the *IDN? reply for 'KEITHLEY INSTRUMENTS INC.,MODEL 2400' and writes "
             "OUTP ON", source="upstream_code", ref=f"{UPSTREAM}:78-81"),
        Fact("current_mode writes SOUR:FUNC VOLT, SOUR:VOLT 0, CONF:CURR and FORM:ELEM CURR", source="upstream_code",
             ref=f"{UPSTREAM}:64-68"),
        Fact("voltage_mode writes SOUR:FUNC CURR, SOUR:CURR 0, CONF:VOLT and FORM:ELEM VOLT", source="upstream_code",
             ref=f"{UPSTREAM}:160-164"),
        Fact("resistance_mode writes CONF:RES and FORM:ELEM RES", source="upstream_code",
             ref=f"{UPSTREAM}:146-148"),
        Fact("read writes ARM:COUN 1, TRIG:COUN samples, TRIG:DEL interval and READ?", source="upstream_code",
             ref=f"{UPSTREAM}:114-121"),
        Fact("For more than one sample the allowed intervals are 0, 1, 10, 60, 600 and 3600 s; for one sample the "
             "interval is 0 through 99 s; samples is 1 to 100", source="upstream_code",
             ref=f"{UPSTREAM}:248-251"),
        Fact("set_voltage_source writes SOUR:VOLT followed by the value and warns that the source has a maximum "
             "resolution of 5 uV", source="upstream_code", ref=f"{UPSTREAM}:152-156"),
        Fact("disable_voltage_source writes SOUR:VOLT 0", source="upstream_code", ref=f"{UPSTREAM}:102-103"),
        Fact("A read of one sample returns one value; with more than one sample it returns Time and Data lists",
             source="upstream_code", ref=f"{UPSTREAM}:139-142"),
        Fact("enable_live_readings writes ARM:COUN INF, TRIG:DEL 0 and INIT", source="upstream_code",
             ref=f"{UPSTREAM}:86-90"),
        Fact("The upstream README calls the project a Python module for controlling a Keithley 2400 source-measure "
             "unit and says it depends on prologixGPIBUSB", source="vendor_doc", ref="README.md:4-5"),
    ]
    safe_state = "source output disabled and source voltage and source current set to zero"
    idn = {"expect": r"KEITHLEY INSTRUMENTS INC\.,MODEL 2400"}

    parameters = {
        "voltage": Field(
            "number", unit="V", writable=True,
            description="Source voltage setpoint (SOUR:VOLT); the operator supplies the safe envelope",
            limit=Limit.operator_required(
                "the clone writes SOUR:VOLT with any value and states only a 5 uV resolution "
                "(keithley2400.py:152-156); it states no minimum or maximum voltage, so the operator must supply "
                "the source-voltage envelope")),
        "output": Field("boolean", writable=True,
                        description="Source output enabled (OUTP ON) or disabled (OUTP OFF)"),
        "trigger_delay": Field("number", unit="s",
                               description="Trigger delay (TRIG:DEL) applied by the last measurement action"),
    }
    reads = {
        "voltage": {"query": "SOUR:VOLT?", "parse": {"kind": "float"}},
        "output": {"query": "OUTP?", "parse": {"kind": "bool"}},
        "trigger_delay": {"query": "TRIG:DEL?", "parse": {"kind": "float"}},
    }
    writes = {
        "voltage": {"write": "SOUR:VOLT {value:g}", "type": "number"},
        "output": {"write": "OUTP {value}", "type": "string",
                   "enum_map": {True: "ON", False: "OFF"}},
    }
    commands = {
        "x-cap.baroobob.measure_current.v1": {
            "query": "SOUR:FUNC VOLT;CONF:CURR;FORM:ELEM CURR;ARM:COUN 1;TRIG:COUN 1;TRIG:DEL {interval:f};READ?",
            "args": {"interval": {"from": "input.interval", "type": "number"}},
            "parse": {"kind": "float"},
            "result": {"map": {"current": "output.$"}},
            "description": "Configure current measurement in source-voltage mode and read one sample",
        },
        "x-cap.baroobob.measure_voltage.v1": {
            "query": "SOUR:FUNC CURR;SOUR:CURR 0;CONF:VOLT;FORM:ELEM VOLT;ARM:COUN 1;TRIG:COUN 1;"
                     "TRIG:DEL {interval:f};READ?",
            "args": {"interval": {"from": "input.interval", "type": "number"}},
            "parse": {"kind": "float"},
            "result": {"map": {"voltage": "output.$"}},
            "description": "Configure voltage measurement in source-current mode and read one sample",
        },
        "x-cap.baroobob.measure_resistance.v1": {
            "query": "CONF:RES;FORM:ELEM RES;ARM:COUN 1;TRIG:COUN 1;TRIG:DEL {interval:f};READ?",
            "args": {"interval": {"from": "input.interval", "type": "number"}},
            "parse": {"kind": "float"},
            "result": {"map": {"resistance": "output.$"}},
            "description": "Configure resistance measurement and read one sample",
        },
        "x-cap.baroobob.safe_state.v1": {
            "write": "OUTP OFF;SOUR:VOLT 0;SOUR:CURR 0",
            "description": "Disable the source output and set both source quantities to zero",
        },
    }
    actions = {
        "x-cap.baroobob.measure_current.v1": Action(
            name="measure_current",
            description="Configure current measurement (CONF:CURR, FORM:ELEM CURR) in source-voltage mode and read "
                        "one sample with the trigger settings of the clone; the source voltage is not changed",
            input={"interval": _interval_field()},
            output={"current": Field("number", unit="A", description="Measured current")}),
        "x-cap.baroobob.measure_voltage.v1": Action(
            name="measure_voltage",
            description="Configure voltage measurement (CONF:VOLT, FORM:ELEM VOLT) with the source current set to "
                        "zero and read one sample with the trigger settings of the clone",
            input={"interval": _interval_field()},
            output={"voltage": Field("number", unit="V", description="Measured voltage")}),
        "x-cap.baroobob.measure_resistance.v1": Action(
            name="measure_resistance",
            description="Configure resistance measurement (CONF:RES, FORM:ELEM RES) and read one sample with the "
                        "trigger settings of the clone; the source setting is not changed",
            input={"interval": _interval_field()},
            output={"resistance": Field("number", unit="Ohm", description="Measured resistance")}),
        "x-cap.baroobob.safe_state.v1": Action(
            name="safe_state",
            description="Disable the source output and set the source voltage and source current to zero",
            safe_state=True),
    }
    safety_bindings = {
        "estop": {"write": "OUTP OFF;SOUR:VOLT 0;SOUR:CURR 0"},
        "safe_state": {"write": "OUTP OFF;SOUR:VOLT 0;SOUR:CURR 0"},
    }
