"""OpenMHS driver for gh.sanket7941/pyinstrument: the SCPI power supply of the pyinstrument collection.

A direct Driver (decorated methods) over the upstream class ``pyinstrument.instrument:PSupply``
(pyinstrument/instrument.py:60).  The card's ``family:scpi`` / ``helper:ScpiDriver`` guess does not fit the
interface: ``PSupply`` is a small object API whose methods build each SCPI line from a literal and a number at run
time (``"VOLT " + str(Volt)``, pyinstrument/instrument.py:82; ``"CURR " + str(Current)``, line 86) around a VISA
resource the caller passes in (lines 61-62), so this package is a direct driver with a ``native.py`` factory; the
deviation is recorded in RESULT.json.  The wire syntax itself is the upstream's and is never re-derived here.

* reads: the output voltage and current the resource reports for ``MEASure:VOLTage:DC?`` and
  ``MEASure:CURRent:DC?`` (pyinstrument/instrument.py:90 and 93);
* writes: the voltage and current setpoints (``VOLT`` and ``CURR``, lines 82 and 86) and the output state
  (``:OUTPut:STATe 1`` / ``:OUTPut:STATe 0``, lines 74 and 78).  The upstream code states no voltage or current
  range, so both setpoints carry ``Limit.operator_required`` and are refused until the site overlay supplies a
  bound (site-limits.example.json is the example);
* capabilities: ``cap.measure.voltage.v1`` and ``cap.measure.current.v1`` take one sample through the two query
  methods;
* the native stop is ``PSupply.off``: ``:OUTPut:STATe 0`` disables the output (line 78).

Every Fact cites a line of the clone at the pinned commit 74278e53b075418f155d0567410e03a8503f347f.  This package
is model-authored and unreviewed, and the hardware backend was never opened; the gate checks the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream file of the native class, relative to the clone root.
MODULE = "pyinstrument/instrument.py"


class PyinstrumentPSupply(Driver):
    device_id = "psupply"
    device_kind = "instrument.smu"
    mode = "hardware"
    risk = "R1"
    native = "pyinstrument.instrument:PSupply"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePSupply"}
    model = "PSupply (generic SCPI programmable power supply)"
    display_name = "pyinstrument PSupply power supply"
    tags = ["power supply", "psu", "scpi", "visa", "voltage", "current"]
    facts = [
        Fact("PSupply stores the VISA resource it is constructed with as self.PS", source="upstream_code",
             ref=f"{MODULE}:61-62"),
        Fact("PSupply.chk queries '*IDN?' on the resource", source="upstream_code", ref=f"{MODULE}:64-65"),
        Fact("PSupply.on writes ':OUTPut:STATe 1' and PSupply.off writes ':OUTPut:STATe 0'", source="upstream_code",
             ref=f"{MODULE}:73-79"),
        Fact("setVolt writes 'VOLT ' followed by the value", source="upstream_code", ref=f"{MODULE}:81-82"),
        Fact("setCurr writes 'CURR ' followed by the value", source="upstream_code", ref=f"{MODULE}:85-86"),
        Fact("measureVolt queries 'MEASure:VOLTage:DC?' and returns the resource's reply", source="upstream_code",
             ref=f"{MODULE}:89-90"),
        Fact("measureCurr queries 'MEASure:CURRent:DC?' and returns the resource's reply", source="upstream_code",
             ref=f"{MODULE}:92-93"),
        Fact("The upstream README lists a digital power supply among the instruments it controls over VISA",
             source="vendor_doc", ref="README.md:2"),
    ]
    safe_state = "output disabled: PSupply.off writes ':OUTPut:STATe 0'"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("voltage", unit="V",
          description="Voltage the resource reports for the output (MEASure:VOLTage:DC?)")
    def voltage(self):
        return float(self.native.measureVolt())

    @read("current", unit="A",
          description="Current the resource reports for the output (MEASure:CURRent:DC?)")
    def current(self):
        return float(self.native.measureCurr())

    # -- writes --------------------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V",
           description="Output voltage setpoint written with 'VOLT <value>'",
           limit=Limit.operator_required(
               "the upstream code states no voltage range; the site supplies the bound of the installed supply"))
    def set_voltage_setpoint(self, value):
        self.native.setVolt(float(value))

    @write("current_setpoint", unit="A",
           description="Output current setpoint written with 'CURR <value>'",
           limit=Limit.operator_required(
               "the upstream code states no current range; the site supplies the bound of the installed supply"))
    def set_current_setpoint(self, value):
        self.native.setCurr(float(value))

    @write("output_enabled", type="boolean",
           description="Output state: True calls PSupply.on (':OUTPut:STATe 1'), False calls PSupply.off "
                       "(':OUTPut:STATe 0')")
    def set_output_enabled(self, value):
        if value:
            self.native.on()
        else:
            self.native.off()

    # -- measurement capabilities ---------------------------------------------------------------------------------
    @action(cap="cap.measure.voltage.v1",
            description="Read one DC voltage sample from the supply output (MEASure:VOLTage:DC?)",
            input={"dc": Field("boolean",
                               description="True for the DC sample the supply reports; False (RMS) is not "
                                           "supported by this query")})
    def measure_voltage(self, dc=True):
        if not dc:
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                "the PSupply measureVolt method queries MEASure:VOLTage:DC?, a DC measurement; an RMS measurement "
                "is not supported")
        return {"voltage": float(self.native.measureVolt())}

    @action(cap="cap.measure.current.v1",
            description="Read one DC current sample from the supply output (MEASure:CURRent:DC?)",
            input={"channel": Field("string",
                                    description="Channel or terminal name accepted by the class schema; the "
                                                "upstream class has one output, so the value is not used")})
    def measure_current(self, channel=None):
        return {"current": float(self.native.measureCurr())}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: PSupply.off writes ':OUTPut:STATe 0' (pyinstrument/instrument.py:77-79)."""
        self.native.off()
