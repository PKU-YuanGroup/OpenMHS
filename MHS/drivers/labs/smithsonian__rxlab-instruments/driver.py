"""OpenMHS driver for gh.smithsonian/rxlab-instruments: the Agilent E8257D PSG signal generator.

The upstream repository is a family of laboratory instrument classes.  This package binds one entry symbol,
``labinstruments.agilent:AgilentE8257D`` (agilent.py:49), because the card is a family-config task and the four
entry classes control unrelated instruments.  A direct Driver is used instead of the card's ScpiDriver guess: the
upstream getter ``AgilentE8257D.get_power`` sends two commands (``:UNIT:POW <units>`` and then ``:POW?``,
agilent.py:112-120), and ``get_id`` and ``reset`` are inherited from ``GenericInstrument`` (generic.py:59-68), which
a one-query-per-field command table cannot express.  The wire syntax is the upstream's and is not re-derived here.

* reads: the CW frequency (``:FREQ?``), the CW output power (``:UNIT:POW dBm`` then ``:POW?``), the RF output
  state (``OUTP:STAT?``) and the identity (``*IDN?``);
* writes: frequency (``:FREQ <value>Hz``), power (``:POW <value>dBm``) and the RF output state (``:OUTP ON`` /
  ``:OUTP OFF``);
* the native stop is ``power_off``: ``:OUTP OFF`` (agilent.py:142-146);
* the safety reset sends nothing.  ``GenericInstrument.reset`` writes ``*RST`` (generic.py:65-68) and its
  docstring says only "Reset instrument", which does not state the effect on the RF output.  That call is the
  ordinary command ``x-cap.smithsonian.scpi_rst.v1`` and not a reset step (SAFE-042);
* the upstream code states no frequency or power range, so both numeric setpoints carry
  ``Limit.operator_required`` and are refused until the site overlay supplies a bound
  (``site-limits.example.json`` shows the shape).

Every Fact cites a line of the clone at the pinned commit 2fbf8e6913e9eb2143088ed3a0b49d01a22fb93c.  This package
is model-authored, unreviewed, and no hardware backend was run.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream module of the bound class, relative to the clone root.
MODULE = "labinstruments/agilent.py"
#: The generic SCPI base class of the upstream package.
GENERIC = "labinstruments/generic.py"


class E8257D(Driver):
    device_id = "e8257d"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "labinstruments.agilent:AgilentE8257D"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeE8257D"}
    vendor = "Agilent"
    model = "E8257D PSG analog signal generator"
    display_name = "Agilent E8257D PSG signal generator"
    tags = ["signal generator", "rf", "agilent", "e8257d", "e8267d", "scpi"]
    facts = [
        Fact("AgilentE8257D controls an E8257D PSG analog signal generator and is expected to work with the E8267D "
             "as well", source="upstream_code", ref=f"{MODULE}:49-53"),
        Fact("The repository lists the Agilent E8257D/67D PSG analog signal generator among the supported "
             "instruments", source="vendor_doc", ref="README.md:37"),
        Fact('set_frequency writes ":FREQ <value><units>"', source="upstream_code", ref=f"{MODULE}:72"),
        Fact('get_frequency queries ":FREQ?" and divides the reply by the requested unit multiplier',
             source="upstream_code", ref=f"{MODULE}:86-87"),
        Fact('set_power writes ":POW <value><units>"', source="upstream_code", ref=f"{MODULE}:98"),
        Fact('get_power selects the unit with ":UNIT:POW <units>" and then queries ":POW?"',
             source="upstream_code", ref=f"{MODULE}:112-120"),
        Fact('power_on writes ":OUTP ON" and power_off writes ":OUTP OFF"', source="upstream_code",
             ref=f"{MODULE}:136-146"),
        Fact('get_output_state queries "OUTP:STAT?" and returns the reply as an integer', source="upstream_code",
             ref=f"{MODULE}:148-156"),
        Fact('get_id sends "*IDN?" and replaces commas with spaces', source="upstream_code", ref=f"{GENERIC}:59-63"),
        Fact('GenericInstrument.reset sends "*RST" and its docstring says "Reset instrument"',
             source="upstream_code", ref=f"{GENERIC}:65-68"),
        Fact("GenericInstrument opens the default port 5025 and reads the identity while connecting",
             source="upstream_code", ref=f"{GENERIC}:27-49"),
        Fact("The accepted frequency units are GHz, MHz, kHz and Hz", source="upstream_code",
             ref=f"{MODULE}:169-172"),
        Fact("The frequency setter defaults to GHz and the power setter to dBm", source="upstream_code",
             ref=f"{MODULE}:63-89"),
        Fact("The README example sets 15 GHz, -20 dBm and turns the RF output on", source="vendor_doc",
             ref="README.md:63-66"),
        Fact("The two setters pass the caller's frequency and power into their commands without a range check",
             source="upstream_code", ref=f"{MODULE}:72-98"),
    ]
    safe_state = "RF output off (:OUTP OFF)"

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("frequency", unit="Hz", description="CW frequency read with :FREQ? and returned in Hz")
    def frequency(self):
        return float(self.native.get_frequency(units="Hz"))

    @read("power", unit="dBm",
          description="CW output power read after selecting dBm with :UNIT:POW and querying :POW?")
    def power(self):
        return float(self.native.get_power(units="dBm"))

    @read("output_enabled", type="boolean",
          description="RF output state read with OUTP:STAT? (1 is on, 0 is off)")
    def output_enabled(self):
        return bool(self.native.get_output_state())

    @read("identity", type="string", description="Identity reply to *IDN? with commas replaced by spaces")
    def identity(self):
        return self.native.get_id()

    # -- writes --------------------------------------------------------------------------------------------------
    @write("frequency", unit="Hz",
           description="CW frequency written with :FREQ <value>Hz; the site supplies the installed generator's range",
           limit=Limit.operator_required(
               "the upstream set_frequency formats the caller's value into ':FREQ {value}{units}' "
               "(labinstruments/agilent.py:72) without stating a range; the operator supplies the frequency range "
               "of the installed generator"))
    def set_frequency(self, value):
        self.native.set_frequency(float(value), units="Hz")

    @write("power", unit="dBm",
           description="CW output power written with :POW <value>dBm; the site supplies the allowed power",
           limit=Limit.operator_required(
               "the upstream set_power formats the caller's value into ':POW {value}{units}' "
               "(labinstruments/agilent.py:98) without stating a range; the operator supplies the power limit of "
               "the installed setup"))
    def set_power(self, value):
        self.native.set_power(float(value), units="dBm")

    @write("output_enabled", type="boolean",
           description="RF output state: True calls power_on (':OUTP ON'), False calls power_off (':OUTP OFF')")
    def set_output_enabled(self, value):
        if value:
            self.native.power_on()
        else:
            self.native.power_off()

    # -- safety and recovery -------------------------------------------------------------------------------------
    @action(name="x-cap.smithsonian.scpi_rst.v1",
            description="Call GenericInstrument.reset, which writes '*RST' (labinstruments/generic.py:65-68). "
                        "The docstring says only 'Reset instrument' and does not state the effect on the RF "
                        "output, the frequency or the power. An ordinary command: the safety reset does not call "
                        "it, and it is not a re-enable or a safe-state action. A later read returns the "
                        "instrument's reply and does not state what '*RST' set. The operator confirms the "
                        "instrument, including whether the RF output is enabled.",
            output={"command_sent": Field(
                "boolean",
                description="True after GenericInstrument.reset returned. Not a reading of the RF output, "
                            "the frequency or the power.")})
    def scpi_rst(self):
        """The upstream ``GenericInstrument.reset`` (*RST). Not the safety reset (SAFE-042)."""
        self.native.reset()
        return {"command_sent": True}

    @estop
    def stop(self):
        """The native stop: power_off writes ':OUTP OFF' (labinstruments/agilent.py:142-146). It does not send *RST."""
        self.native.power_off()
