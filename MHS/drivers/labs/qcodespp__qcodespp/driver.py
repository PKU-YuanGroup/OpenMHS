"""OpenMHS driver for gh.qcodespp/qcodespp: the Keithley 2450 source measure unit.

DEVIATION FROM THE CARD: the card names the ``qcodes`` family and the ``QcodesDriver`` helper.  Every class of this
driver pack, including the card's ``Keithley_2450`` entry, constructs its QCoDeS Parameters with ``add_parameter``
(Keithley_2450.py:13-120); G7's QCoDeS profile proves only an explicit ``self.<name> = Parameter(...)`` constructor
and refuses ``add_parameter`` (qcodes-driver.md, "G7 checks the exact assignment ... Arbitrary add_parameter ... not
inferred").  The real runtime here is an object whose measurement methods and SCPI commands are ordinary methods, so
this package uses a direct ``Driver`` over the pinned class with ``native.py`` as the hardware factory and a
source-shaped fake; the alternative was blocked HELPER_MISSING.

What is served, all from the source-visible methods and Parameters of ``Keithley_2450``:

* reads: ``voltage`` (``_get_volt`` parsed by ``_volt_parser``), ``current`` (``_get_current`` parsed by
  ``_curr_parser``), ``resistance`` (``_get_resistance`` parsed by ``_resistance_parser``), ``output``
  (``:OUTP:STAT?``), ``source`` (``:SOUR:FUNC?``), ``compliancev`` (``SOUR:CURR:VLIM:LEV?``) and ``compliancei``
  (``SOUR:VOLT:ILIM:LEV?``);
* writes (``cap.device.configure.v1``): ``voltage`` (``_set_volt``), ``current`` (``_set_current``), ``output``
  (``:OUTP:STAT {:d}``), ``source`` (``_set_mode_and_sense``), ``compliancev`` and ``compliancei`` (the two
  compliance commands of the upstream Parameters).  The ``voltage`` and ``current`` setters require the output on and
  select their matching source function through ``_set_mode_and_sense`` when needed; the upstream methods alone raise
  when the source is in the other mode.  No text in the clone states any voltage, current or compliance bound, so
  every numeric field is ``Limit.operator_required`` and stays refused until the site overlay supplies it;
  ``site-limits.example.json`` is an example overlay.

The native stop is the input-free safe-state action ``x-cap.qcodespp.output_off.v1``: it writes ``:OUTP:STAT 0`` and
reads ``:OUTP:STAT?`` back; the ``@estop`` method writes the same command so the stop is never only a software latch.
The measurement reads check ``:OUTP:STAT?`` and return no value while the output is off instead of propagating the
upstream ``RuntimeError``, so the resource stays readable in the safe state; they never report a cached measurement.
The command is the setter of the upstream ``output`` Parameter (Keithley_2450.py:93-96); the source keeps its
configured level, but the output is disabled and the latch refuses further actuation.  This is not a hardware e-stop
and the package makes no claim that it opens a physical relay.

Every Fact cites the clone at the pinned commit 77090fc8f3ece9831887c8a07bd1249d343d18c1.  The package is
model-authored and unreviewed (``reviewed_by`` is null); it has been checked on the fake backend only and has never
opened a VISA session.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The selected upstream module, relative to the clone root.
SOURCE = "qcodespp/instrument_drivers/tektronix/Keithley_2450.py"

#: No text in the clone states a voltage, current or compliance range; these are operator decisions at deployment.
VOLTAGE_LIMIT = Limit.operator_required(
    "the clone states no voltage range or limit for the Keithley 2450; the connected load and source range are an "
    "operator decision (Keithley_2450.py:49-60, 136-143)")
CURRENT_LIMIT = Limit.operator_required(
    "the clone states no current range or limit for the Keithley 2450; the connected load and source range are an "
    "operator decision (Keithley_2450.py:62-73, 164-171)")
COMPLIANCEV_LIMIT = Limit.operator_required(
    "the clone states no voltage-compliance range for the Keithley 2450; the permitted voltage across the load is "
    "an operator decision (Keithley_2450.py:37-41)")
COMPLIANCEI_LIMIT = Limit.operator_required(
    "the clone states no current-compliance range for the Keithley 2450; the permitted current through the load is "
    "an operator decision (Keithley_2450.py:43-47)")


def _number(reply: object, what: str) -> float:
    """A float from a single-value SCPI reply; a malformed reply is a device fault, not a zero."""
    try:
        return float(str(reply).strip().strip('"'))
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the Keithley 2450 reply for {what} is not a number: {reply!r}") from exc


def _mode(reply: object) -> str:
    """The source function from ``:SOUR:FUNC?``; strip the quotes some firmware returns."""
    text = str(reply or "").strip().strip('"')
    if text not in ("VOLT", "CURR"):
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the Keithley 2450 replied {reply!r} to :SOUR:FUNC?, not VOLT or CURR")
    return text


def _output_state(reply: object) -> bool:
    """The output relay state from ``:OUTP:STAT?``; any value other than 0 or 1 is a device fault."""
    text = str(reply).strip().strip('"')
    try:
        value = int(text)
    except (TypeError, ValueError) as exc:
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the Keithley 2450 replied {reply!r} to :OUTP:STAT?, not 0 or 1") from exc
    if value not in (0, 1):
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the Keithley 2450 replied {reply!r} to :OUTP:STAT?, not 0 or 1")
    return value == 1


class Keithley2450(Driver):
    device_id = "keithley-2450"
    device_kind = "instrument.smu"
    mode = "hardware"
    #: No source-backed voltage ceiling excludes hazardous sourcing. Use conservative R3 until a bounded
    #: deployment and output-enable contract are established; the card's R1 floor is insufficient.
    risk = "R3"
    native = "qcodespp.instrument_drivers.tektronix.Keithley_2450:Keithley_2450"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeKeithley2450"}
    vendor, model = "Keithley", "2450 SourceMeter"
    display_name = "Keithley 2450 source measure unit (qcodespp driver)"
    tags = ["qcodes", "visa", "scpi", "source-measure-unit", "keithley", "2450", "voltage-source", "current-source"]
    safe_state = ("source output off with :OUTP:STAT 0 (the command of the upstream output Parameter); the configured "
                  "source level remains set but is not driven, and the e-stop latch refuses further actuation")
    facts = [
        Fact("Keithley_2450 is a QCoDeS VisaInstrument whose docstring calls it a voltage source that behaves "
             "similarly to the K2400 series driver", source="upstream_code", ref=f"{SOURCE}:5-8"),
        Fact("The constructor takes name and address and passes terminator '\\n' to VisaInstrument",
             source="upstream_code", ref=f"{SOURCE}:10-11"),
        Fact("rangev_source, rangev_sense, rangei_source and rangei_sense are Parameters with source/sense voltage "
             "and current range queries and '{:f}' setters", source="upstream_code", ref=f"{SOURCE}:13-35"),
        Fact("compliancev is a Parameter whose get_cmd is SOUR:CURR:VLIM:LEV? and whose set_cmd is "
             "SOUR:CURR:VLIM:LEV {:.16f}", source="upstream_code", ref=f"{SOURCE}:37-41"),
        Fact("compliancei is a Parameter whose get_cmd is SOUR:VOLT:ILIM:LEV? and whose set_cmd is "
             "SOUR:VOLT:ILIM:LEV {:.16f}", source="upstream_code", ref=f"{SOURCE}:43-47"),
        Fact("volt is a Parameter with unit V whose get_cmd is self._get_volt and set_cmd is self._set_volt; its "
             "docstring says a voltage read is an error while the output is off", source="upstream_code",
             ref=f"{SOURCE}:49-60"),
        Fact("curr is a Parameter with unit A whose get_cmd is self._get_current and set_cmd is self._set_current; "
             "its docstring says a current read is an error while the output is off", source="upstream_code",
             ref=f"{SOURCE}:62-73"),
        Fact("source is a Parameter with an Enum('VOLT', 'CURR') validator, get_cmd ':SOUR:FUNC?' and set_cmd "
             "self._set_mode_and_sense", source="upstream_code", ref=f"{SOURCE}:76-80"),
        Fact("sense is a Parameter with get_cmd ':SENS:FUNC?' and set_cmd ':SENS:FUNC \"{:s}\"'",
             source="upstream_code", ref=f"{SOURCE}:82-86"),
        Fact("output is a Parameter with get_cmd ':OUTP:STAT?' and set_cmd ':OUTP:STAT {:d}'",
             source="upstream_code", ref=f"{SOURCE}:93-96"),
        Fact("_get_volt raises when output() is 0, returns READ? when sense starts with \"VOLT, and otherwise "
             "returns SOUR:VOLT? when source() is VOLT", source="upstream_code", ref=f"{SOURCE}:125-134"),
        Fact("_set_volt raises when output() is 0 and otherwise writes :SOUR:VOLT:LEV with eight decimals when "
             "source() is VOLT", source="upstream_code", ref=f"{SOURCE}:136-143"),
        Fact("_get_current raises when output() is 0, returns READ? when sense starts with \"CURR, and otherwise "
             "returns SOUR:CURR? when source() is CURR", source="upstream_code", ref=f"{SOURCE}:153-162"),
        Fact("_set_current raises when output() is 0 and otherwise writes :SOUR:CURR:LEV with sixteen decimals when "
             "source() is CURR", source="upstream_code", ref=f"{SOURCE}:164-171"),
        Fact("_get_resistance raises when output() is 0 and returns READ? when sense is CURR with source VOLT or "
             "when source is CURR with sense VOLT", source="upstream_code", ref=f"{SOURCE}:174-183"),
        Fact("_set_mode_and_sense sets sense to CURR for VOLT and to VOLT for CURR, then writes :SOUR:FUNC",
             source="upstream_code", ref=f"{SOURCE}:208-216"),
        Fact("reset documents a return to GPIB defaults and cancellation of pending commands, and writes :*RST",
             source="upstream_code", ref=f"{SOURCE}:218-229"),
        Fact("_volt_parser returns field 0, _curr_parser returns field 1 and _resistance_parser returns field 0 "
             "divided by field 1 of a comma-separated reply", source="upstream_code", ref=f"{SOURCE}:231-242"),
        Fact("The constructor adds Parameters for ranges, compliance, voltage, current, source and sense mode, "
             "four-wire sense, output, NPLC and resistance, then calls connect_message", source="upstream_code",
             ref=f"{SOURCE}:13-120"),
    ]

    # -- reads ----------------------------------------------------------------------------------------------------
    def _output_on(self) -> bool:
        """The output state read directly from :OUTP:STAT?, the same query the upstream output Parameter uses."""
        return _output_state(self.native.ask(":OUTP:STAT?"))

    @read("voltage", unit="V",
          description="Measured voltage when sensing VOLT, otherwise the source voltage setpoint when sourcing "
                      "VOLT; omitted while the output is off (the upstream method raises in that state)")
    def voltage(self):
        if not self._output_on():
            return None
        reply = self.native._get_volt()
        if "," in str(reply):
            return float(self.native._volt_parser(reply))
        return _number(reply, "voltage")

    @read("current", unit="A",
          description="Measured current when sensing CURR, otherwise the source current setpoint when sourcing "
                      "CURR; omitted while the output is off (the upstream method raises in that state)")
    def current(self):
        if not self._output_on():
            return None
        reply = self.native._get_current()
        if "," in str(reply):
            return float(self.native._curr_parser(reply))
        return _number(reply, "current")

    @read("resistance", unit="Ohm",
          description="Resistance from the voltage/current measurement pair; omitted while the output is off (the "
                      "upstream method raises in that state)")
    def resistance(self):
        if not self._output_on():
            return None
        reply = self.native._get_resistance()
        if "," in str(reply):
            return float(self.native._resistance_parser(reply))
        return _number(reply, "resistance")

    @read("output", type="boolean", description="Output on (true) or off (false) from :OUTP:STAT?")
    def output(self):
        return _output_state(self.native.ask(":OUTP:STAT?"))

    @read("source", type="string", enum=["VOLT", "CURR"],
          description="Source function from :SOUR:FUNC?: VOLT or CURR")
    def source(self):
        return _mode(self.native.ask(":SOUR:FUNC?"))

    @read("compliancev", unit="V",
          description="Voltage compliance limit from SOUR:CURR:VLIM:LEV?, applied while sourcing current")
    def compliancev(self):
        return _number(self.native.ask("SOUR:CURR:VLIM:LEV?"), "voltage compliance")

    @read("compliancei", unit="A",
          description="Current compliance limit from SOUR:VOLT:ILIM:LEV?, applied while sourcing voltage")
    def compliancei(self):
        return _number(self.native.ask("SOUR:VOLT:ILIM:LEV?"), "current compliance")

    # -- writes ---------------------------------------------------------------------------------------------------
    @write("voltage", unit="V",
           description="Source voltage: requires the output on, selects source mode VOLT with _set_mode_and_sense "
                       "when needed, then writes the level with _set_volt",
           limit=VOLTAGE_LIMIT)
    def set_voltage(self, value):
        if not self._output_on():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the upstream voltage setter requires the output on; turn the output on first")
        if self.source() != "VOLT":
            self.native._set_mode_and_sense("VOLT")
        self.native._set_volt(float(value))

    @write("current", unit="A",
           description="Source current: requires the output on, selects source mode CURR with _set_mode_and_sense "
                       "when needed, then writes the level with _set_current",
           limit=CURRENT_LIMIT)
    def set_current(self, value):
        if not self._output_on():
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the upstream current setter requires the output on; turn the output on first")
        if self.source() != "CURR":
            self.native._set_mode_and_sense("CURR")
        self.native._set_current(float(value))

    @write("output", type="boolean",
           description="Turn the source output on or off with :OUTP:STAT 1 or :OUTP:STAT 0")
    def set_output(self, value):
        self.native.write(":OUTP:STAT {:d}".format(1 if value else 0))

    @write("source", type="string", enum=["VOLT", "CURR"],
           description="Source function written by _set_mode_and_sense; the upstream setter also changes sense to "
                       "the opposite function and writes :SOUR:FUNC")
    def set_source(self, value):
        self.native._set_mode_and_sense(value)

    @write("compliancev", unit="V",
           description="Voltage compliance written with SOUR:CURR:VLIM:LEV; this is the voltage limit while "
                       "sourcing current",
           limit=COMPLIANCEV_LIMIT)
    def set_compliancev(self, value):
        self.native.write("SOUR:CURR:VLIM:LEV {:.16f}".format(float(value)))

    @write("compliancei", unit="A",
           description="Current compliance written with SOUR:VOLT:ILIM:LEV; this is the current limit while "
                       "sourcing voltage",
           limit=COMPLIANCEI_LIMIT)
    def set_compliancei(self, value):
        self.native.write("SOUR:VOLT:ILIM:LEV {:.16f}".format(float(value)))

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.qcodespp.output_off.v1", safe_state=True,
            description="Input-free safe state: turn the source output off with :OUTP:STAT 0 and confirm "
                        ":OUTP:STAT? reports it off",
            output={"output": Field("boolean", description="False once :OUTP:STAT? reports the output off")})
    def output_off(self):
        self.native.write(":OUTP:STAT 0")
        state = _output_state(self.native.ask(":OUTP:STAT?"))
        if state:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the Keithley 2450 still reports its output on after :OUTP:STAT 0")
        return {"output": False}

    @estop
    def stop(self):
        """Native stop: the output-off command, sent without a query so no reply is mistaken for a measurement."""
        self.native.write(":OUTP:STAT 0")

    def teardown(self):
        """Close the VISA session through the QCoDeS instrument."""
        self.native.close()
