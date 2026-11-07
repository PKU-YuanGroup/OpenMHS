"""OpenMHS driver for gh.alexlegoshin/idm-dnkmetr: the GW Instek GPP-4323 DC power supply.

The upstream repository is a measurement application around a generic pyvisa SCPI class.  Its GPP-4323 profile
(instruments/gwinstek_psu_generic.json) binds ``VSET1:<value>``, ``ISET1:<value>``, ``ALLOUTON``/``ALLOUTOFF``,
``VOUT1?`` and ``IOUT1?``.  A ScpiDriver command table cannot express the two writes faithfully: the upstream
appends the value to the command prefix without a separator, and the SCPI bridge would have to receive
``VSET1:12.0000`` as one token.  This package therefore uses a direct Driver over the upstream class
``drivers:PowerSupply`` (a ScpiInstrument configured by a profile), with a hardware factory that opens that class
and adds the two readback commands the profile's own notes confirm (``VSET1?``/``ISET1?``).

* reads: instrument identity, measured output voltage and current, and the setpoint and current limit read back
  from the instrument;
* writes: output voltage setpoint and current limit, each limited by a number the clone states;
* action: close or open the output (``ALLOUTON``/``ALLOUTOFF``), an extension because no catalogue class expresses
  a power-supply output;
* e-stop: open the output (``ALLOUTOFF``).

Every Fact and Limit cites a line of the clone at the pinned commit (8f69873e51d2dce10c292feda3a44f745f1af5c1).
This package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

PROFILE = "instruments/gwinstek_psu_generic.json"
UPSTREAM = "drivers.py"


class Gpp4323(Driver):
    device_id = "gpp4323"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "drivers:PowerSupply"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeGpp4323"}
    vendor, model = "GW Instek", "GPP-4323"
    display_name = "GW Instek GPP-4323 DC power supply"
    tags = ["power supply", "dc source", "gpp-4323", "gw instek", "scpi"]
    facts = [
        Fact("The GPP-4323 profile maps set_voltage to 'VSET1:{value:.4f}' and set_current_limit to "
             "'ISET1:{value:.4f}'", source="upstream_code", ref=f"{PROFILE}:21-22"),
        Fact("The profile switches the output with ALLOUTON (on) and ALLOUTOFF (off)", source="upstream_code",
             ref=f"{PROFILE}:27-28"),
        Fact("The profile measures output voltage with VOUT1? and output current with IOUT1?", source="upstream_code",
             ref=f"{PROFILE}:24-25"),
        Fact("In tracking-series mode the terminals supply 0 to 64 V and only channel 1 is controlled",
             source="upstream_code", ref=f"{PROFILE}:7"),
        Fact("The profile declares max_voltage_v 64.0", source="upstream_code", ref=f"{PROFILE}:30"),
        Fact("The profile declares max_current_limit_a 3.0", source="upstream_code", ref=f"{PROFILE}:31"),
        Fact("The profile notes confirm that VSET1? and ISET1? read back the value that was set",
             source="upstream_code", ref=f"{PROFILE}:7"),
        Fact("VOUT1? and IOUT1? append a unit suffix, and query_number extracts the first number",
             source="upstream_code", ref=f"{UPSTREAM}:29-39"),
        Fact("PowerSupply.set_voltage writes set_voltage and set_current_limit writes set_current_limit",
             source="upstream_code", ref=f"{UPSTREAM}:117-122"),
        Fact("PowerSupply.enable_output writes output_on_value or output_off_value according to its state",
             source="upstream_code", ref=f"{UPSTREAM}:124-127"),
        Fact("PowerSupply.measure_voltage and measure_current query the profile's measure commands",
             source="upstream_code", ref=f"{UPSTREAM}:129-135"),
        Fact("A serial profile with baud_rate 'auto' detects the speed from the *IDN? reply",
             source="upstream_code", ref=f"{UPSTREAM}:61-72"),
        Fact("The profile records the identity 'GW INSTEK,GPP-74323,SN:GEZ823770,V1.22'", source="upstream_code",
             ref=f"{PROFILE}:7"),
    ]
    safe_state = "output disabled (ALLOUTOFF); the voltage and current setpoints keep their last applied values"

    # -- reads -----------------------------------------------------------------------------------------------
    @read("identity", type="string", description="Instrument identity from *IDN?")
    def identity(self):
        return self.native.idn()

    @read("voltage", unit="V", description="Output voltage measured by the supply (VOUT1?)")
    def voltage(self):
        return self.native.measure_voltage()

    @read("current", unit="A", description="Output current measured by the supply (IOUT1?)")
    def current(self):
        return self.native.measure_current()

    @read("voltage_setpoint", unit="V", description="Voltage setpoint read back from the supply (VSET1?)")
    def voltage_setpoint(self):
        return self.native.query_number("set_voltage_readback")

    @read("current_limit", unit="A", description="Current limit read back from the supply (ISET1?)")
    def current_limit(self):
        return self.native.query_number("current_limit_readback")

    # -- writes ----------------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V", description="Output voltage setpoint (VSET1)",
           limit=Limit(min=0, max=64.0, source="upstream_code", ref=f"{PROFILE}:7",
                       reason="the profile notes give 0-64 V at the terminals in tracking-series mode; max_voltage_v "
                              "on line 30 repeats the maximum"))
    def set_voltage_setpoint(self, value):
        self.native.set_voltage(value)

    @write("current_limit", unit="A", description="Current limit (ISET1)",
           limit=Limit(max=3.0, source="upstream_code", ref=f"{PROFILE}:31",
                       reason="max_current_limit_a is 3.0 A; no line of the clone states a lower bound"))
    def set_current_limit(self, value):
        self.native.set_current_limit(value)

    # -- action and safety -----------------------------------------------------------------------------------
    @action(name="x-cap.alexlegoshin.enable_output.v1",
            description="Close or open the power-supply output (ALLOUTON/ALLOUTOFF)",
            input={"enabled": Field("boolean",
                                    description="True to close the output (ALLOUTON), False to open it (ALLOUTOFF)")},
            output={"enabled": Field("boolean",
                                     description="The state sent to the supply; the profile has no output-state "
                                                 "query")})
    def enable_output(self, enabled):
        self.native.enable_output(enabled)
        return {"enabled": enabled}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends ALLOUTOFF."""
        self.native.enable_output(False)

    def teardown(self):
        self.native.close()
