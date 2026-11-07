"""OpenMHS driver for gh.sergey12malyshev/owon-power-supply-driver: an OWON SP/SPE DC power supply.

A direct Driver (decorated methods) over the upstream class owon_ps:OwonPowerSupply.  The upstream class wraps one
pyserial port and every method sends one SCPI command or query and reads one reply line (owon_ps.py:33-41), so the
driver is a plain synchronous object driver: each method calls self.native.

* reads: the voltage and current set points, the measured output voltage, current and power, the voltage and
  current limit settings, the output state, the identity response and the raw MEASure:ALL:INFO? reply;
* writes: the voltage and current set points, the voltage and current limit settings, and the output state.
  No text file of the clone states a complete range for the generic OwonPowerSupply class, so all four numeric
  bounds are Limit.operator_required: every one of those writes is refused MHS.SAFETY.LIMITS_UNSET until the site
  supplies the range of its unit (site-limits.example.json shows an example overlay for the tested SPE3051);
* actions: an x-cap.reset_config for *RST and an x-cap.output_off safe-state action (OUTPut OFF), both with inline
  schemas because the catalogue has no class for them;
* the native stop is output_off, called by @estop and by the safe-state action.

Every Fact cites a line of the clone at the pinned commit 37ec9d93df28640d7522162922472cc531be7758.  This package
is model-authored and unreviewed.  The loader refuses the hardware backend of an unreviewed model-written package
only at R2 and R3; this driver is R1, so nothing mechanically prevents a hardware run: an operator must not pass
--allow-hardware until a human has reviewed the package.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


class OwonPowerSupplyDriver(Driver):
    device_id = "owon-power-supply"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "owon_ps:OwonPowerSupply"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOwonPowerSupply"}
    vendor, model = "OWON", "SP/SPE series single-channel DC power supply"
    display_name = "OWON power supply (owon_ps.OwonPowerSupply)"
    tags = ["power-supply", "dc-source", "scpi", "serial"]
    facts = [
        Fact("The class opens a pyserial port with the port, baud rate and timeout given to __init__ and keeps the "
             "port object in serial_port", source="upstream_code", ref="owon_ps.py:18-24"),
        Fact("send() appends a newline to the command and reads one reply line", source="upstream_code",
             ref="owon_ps.py:33-41"),
        Fact("output_on() and output_off() send OUTPut ON and OUTPut OFF, and get_outputState() sends OUTPut?",
             source="upstream_code", ref="owon_ps.py:45-52"),
        Fact("get_identity() sends *IDN? and reset_config() sends *RST", source="upstream_code",
             ref="owon_ps.py:54-59"),
        Fact("set_voltage() writes VOLTage with three decimals and get_voltage() reads VOLTage?",
             source="upstream_code", ref="owon_ps.py:67-71"),
        Fact("measure_voltage() reads MEASure:VOLTage?", source="upstream_code", ref="owon_ps.py:73-74"),
        Fact("set_voltage_limit() writes VOLTage:LIMit with three decimals and the code comments a 1 V minimum",
             source="upstream_code", ref="owon_ps.py:76-77"),
        Fact("get_voltage_limit() reads VOLTage:LIMit?", source="upstream_code", ref="owon_ps.py:79-80"),
        Fact("set_current() writes CURRent with three decimals and get_current() reads CURRent?",
             source="upstream_code", ref="owon_ps.py:82-86"),
        Fact("measure_current() reads MEASure:CURRent?", source="upstream_code", ref="owon_ps.py:88-89"),
        Fact("set_current_limit() writes CURRent:LIMit with three decimals and the code comments a 100 mA minimum",
             source="upstream_code", ref="owon_ps.py:91-92"),
        Fact("get_current_limit() reads CURRent:LIMit?", source="upstream_code", ref="owon_ps.py:94-95"),
        Fact("get_power() reads MEAS:POW?", source="upstream_code", ref="owon_ps.py:97-98"),
        Fact("get_all_parametrs() sends MEASure:ALL:INFO? and returns the reply unparsed", source="upstream_code",
             ref="owon_ps.py:100-101"),
        Fact("The upstream example names the tested model SPE3051 as a 30 V, 5 A, 150 W supply",
             source="upstream_code", ref="example.py:3-5"),
        Fact("The README describes the package as a SCPI driver for the OWON power supply, tested on the SPA3051 "
             "model, connected as a virtual COM port", source="vendor_doc", ref="README.md:3-5"),
    ]
    safe_state = "output disabled (OUTPut OFF); the voltage and current set points are left unchanged"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("voltage_setpoint", unit="V", description="Output voltage set point (VOLTage?)")
    def voltage_setpoint(self):
        return self.native.get_voltage()

    @read("voltage", unit="V", description="Measured output voltage (MEASure:VOLTage?)")
    def voltage(self):
        return self.native.measure_voltage()

    @read("current_setpoint", unit="A", description="Output current set point (CURRent?)")
    def current_setpoint(self):
        return self.native.get_current()

    @read("current", unit="A", description="Measured output current (MEASure:CURRent?)")
    def current(self):
        return self.native.measure_current()

    @read("power", unit="W", description="Measured output power (MEAS:POW?)")
    def power(self):
        return self.native.get_power()

    @read("voltage_limit", unit="V", description="Voltage limit setting (VOLTage:LIMit?)")
    def voltage_limit(self):
        return self.native.get_voltage_limit()

    @read("current_limit", unit="A", description="Current limit setting (CURRent:LIMit?)")
    def current_limit(self):
        return self.native.get_current_limit()

    @read("output_enabled", type="boolean", description="True while the output is on (OUTPut?)")
    def output_enabled(self):
        return self._output_state()

    @read("identity", type="string", description="Reply of *IDN? (identification string)")
    def identity(self):
        return self.native.get_identity()

    @read("all_parameters", type="string",
          description="Raw reply of MEASure:ALL:INFO? (the full measurement block, unparsed)")
    def all_parameters(self):
        return self.native.get_all_parametrs()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("voltage_setpoint", unit="V", description="Output voltage set point, written with three decimals",
           limit=Limit.operator_required(
               "the clone states no complete voltage range for the generic OwonPowerSupply class: example.py:4 "
               "names 30 V only for the tested SPE3051 and the class declares no model; the site supplies the range "
               "of the installed unit"))
    def set_voltage_setpoint(self, value):
        self.native.set_voltage(value)
        return self.native.get_voltage()

    @write("current_setpoint", unit="A", description="Output current set point, written with three decimals",
           limit=Limit.operator_required(
               "the clone states no complete current range for the generic OwonPowerSupply class: example.py:4 "
               "names 5 A only for the tested SPE3051 and the class declares no model; the site supplies the range "
               "of the installed unit"))
    def set_current_setpoint(self, value):
        self.native.set_current(value)
        return self.native.get_current()

    @write("voltage_limit", unit="V", description="Voltage limit setting, written with three decimals",
           limit=Limit.operator_required(
               "owon_ps.py:77 comments a 1 V minimum but states no upper bound for the generic class; the site "
               "supplies the range of the installed unit"))
    def set_voltage_limit(self, value):
        self.native.set_voltage_limit(value)
        return self.native.get_voltage_limit()

    @write("current_limit", unit="A", description="Current limit setting, written with three decimals",
           limit=Limit.operator_required(
               "owon_ps.py:92 comments a 100 mA minimum but states no upper bound for the generic class; the site "
               "supplies the range of the installed unit"))
    def set_current_limit(self, value):
        self.native.set_current_limit(value)
        return self.native.get_current_limit()

    @write("output_enabled", type="boolean",
           description="Enable (OUTPut ON) or disable (OUTPut OFF) the output", risk="R1")
    def set_output_enabled(self, value):
        if value:
            self.native.output_on()
        else:
            self.native.output_off()
        return self._output_state()

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.sergey12malyshev.reset_config.v1", risk="R1",
            description="Reset the instrument to its factory configuration (*RST); it takes no input",
            output={"reset": Field("boolean", description="True once *RST was sent")})
    def reset_config(self):
        self.native.reset_config()
        return {"reset": True}

    @action(name="x-cap.sergey12malyshev.output_off.v1", safe_state=True, risk="R1",
            description="Disable the output (OUTPut OFF); it takes no input and is the declared safe state",
            output={"output_enabled": Field("boolean", description="False once the output is disabled")})
    def output_off(self):
        self.native.output_off()
        return {"output_enabled": False}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="output_off")
    def stop(self):
        """The native stop: the runtime latches first, then sends OUTPut OFF."""
        self.native.output_off()

    # -- helpers ------------------------------------------------------------------------------------------------
    def _output_state(self):
        reply = str(self.native.get_outputState()).strip().upper()
        if reply in ("1", "ON"):
            return True
        if reply in ("0", "OFF"):
            return False
        raise DriverFailed("MHS.DEVICE.FAULTED", f"OUTPut? returned an unrecognised state {reply!r}")

    def teardown(self):
        self.native.disconnect()
