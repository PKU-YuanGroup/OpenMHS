"""OpenMHS driver for gh.kajalbiju/psi_bluesky_backend: the Mercury iTC temperature controller.

A direct Driver (decorated methods) over the upstream class ``Bluesky4.mercury_itc:MercuryITC``.  The upstream class
opens a PyVISA resource itself (``Bluesky4/mercury_itc.py:9-14``) and builds each command from the fixed device
address ``STILL_DB6.T1`` (line 6) and a loop register (TSET, HSET, P, I, D); a ScpiDriver command table cannot
reproduce a line whose text is assembled at run time, so this package uses a direct driver and a native.py factory.
The driver covers one device of the repository; the SR830 lock-in and the SIM928 voltage source are separate
instruments and are not covered.

* reads: the measured temperature (TEMP:SIG:TEMP), the temperature-loop setpoint (TSET), the heater-loop setpoint
  (HSET) and the P, I and D terms of the temperature loop;
* writes: the temperature-loop setpoint (TSET), the heater-loop setpoint (HSET) and P, I and D, each with an
  ``operator_required`` limit because no line of the clone states a range;
* the e-stop and the safe-state action write the temperature-loop setpoint 0 K (TSET 0), so the loop's PID control
  does not heat, and then the heater-loop setpoint 0 (HSET 0), the heater output of manual mode;
* the temperature-loop setpoint is sent with ``write`` because the upstream ``set_gas_flow`` follows its SET with a
  literal query string containing ``{device_address}`` (line 59), and the driver reads it back with the upstream
  ``get_gas_flow`` (line 154), which reads TSET despite its name.

Every Fact cites a line of the clone at the pinned commit (59252b014ef37fc4f2de2e37eda1fca755afe50f).  This package
is model-authored and unreviewed; it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream module that holds MercuryITC.
MERCURY = "Bluesky4/mercury_itc.py"

#: The device address the upstream module fixes for every command (line 6).
DEVICE_ADDRESS = "STILL_DB6.T1"

#: Why a loop term needs the site's bound (the clone states no numeric range).
_OPERATOR_REASON = (
    "no line of the clone states a valid range for this loop value; the upstream module only builds the SET/READ "
    "command and never checks a range, so the site supplies the range of its Mercury iTC")


class MercuryITC(Driver):
    device_id = "mercury-itc"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "Bluesky4.mercury_itc:MercuryITC"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMercuryITC"}
    vendor, model = "Oxford Instruments", "Mercury iTC temperature controller"
    display_name = "Oxford Instruments Mercury iTC temperature controller (PSI Bluesky4)"
    tags = ["temperature controller", "mercury itc", "cryogenic", "pid", "visa"]
    facts = [
        Fact("The module fixes the Mercury iTC device address STILL_DB6.T1", source="upstream_code",
             ref=f"{MERCURY}:6"),
        Fact("connect opens a pyvisa resource and sets the newline write and read terminators",
             source="upstream_code", ref=f"{MERCURY}:9-14"),
        Fact("query connects, sends the command through pyvisa's query and disconnects",
             source="upstream_code", ref=f"{MERCURY}:20-29"),
        Fact("write connects, sends the command and disconnects", source="upstream_code",
             ref=f"{MERCURY}:31-38"),
        Fact("read_temperature sends READ:DEV:<address>:TEMP:SIG:TEMP and parses the last field, stripping a "
             "trailing K", source="upstream_code", ref=f"{MERCURY}:41-49"),
        Fact("set_p_value sends SET:DEV:<address>:TEMP:LOOP:P:<value> and reads back LOOP:P",
             source="upstream_code", ref=f"{MERCURY}:62-66"),
        Fact("set_i_value sends SET:DEV:<address>:TEMP:LOOP:I:<value> and reads back LOOP:I",
             source="upstream_code", ref=f"{MERCURY}:68-72"),
        Fact("set_d_value sends SET:DEV:<address>:TEMP:LOOP:D:<value> and reads back LOOP:D",
             source="upstream_code", ref=f"{MERCURY}:74-78"),
        Fact("set_heater_setpoint sends SET:DEV:<address>:TEMP:LOOP:HSET:<value> and reads back LOOP:HSET",
             source="upstream_code", ref=f"{MERCURY}:80-84"),
        Fact("set_flow_setpoint sends SET:DEV:<address>:TEMP:LOOP:FSET:<value> and reads back LOOP:FSET",
             source="upstream_code", ref=f"{MERCURY}:86-90"),
        Fact("set_gas_flow writes LOOP:TSET but its follow-up query is a literal string containing "
             "{device_address}, so this driver sends the SET line through write instead",
             source="upstream_code", ref=f"{MERCURY}:56-60"),
        Fact("get_gas_flow reads LOOP:TSET and removes the last character of the reply as a unit suffix",
             source="upstream_code", ref=f"{MERCURY}:153-161"),
        Fact("get_p_value, get_i_value, get_d_value and get_heater_setpoint read LOOP:P, LOOP:I, LOOP:D and LOOP:HSET",
             source="upstream_code", ref=f"{MERCURY}:104-150"),
        Fact("The only numeric default in the class is the 10000 ms VISA timeout, a transport timeout and not a "
             "device range", source="upstream_code", ref=f"{MERCURY}:12"),
        Fact("The upstream README describes the repository as the backend for controlling instruments at PSI",
             source="vendor_doc", ref="README.md:1"),
    ]
    safe_state = ("temperature-loop setpoint written to 0 K (TSET 0), so the PID loop does not heat, and heater-loop "
                  "setpoint written to 0 (HSET 0), the manual heater output")

    # -- reads -------------------------------------------------------------------------------------------------
    @read("temperature", unit="K", description="Temperature measured by the Mercury iTC (TEMP:SIG:TEMP)")
    def temperature(self):
        return self.native.read_temperature()

    @read("temperature_setpoint", unit="K",
          description="Temperature-loop setpoint (TSET), read through the upstream get_gas_flow method")
    def temperature_setpoint(self):
        return self.native.get_gas_flow()

    @read("heater_setpoint", unit="1",
          description="Heater-loop setpoint (HSET), in the unit the controller is configured for")
    def heater_setpoint(self):
        return self.native.get_heater_setpoint()

    @read("p_value", unit="1", description="Proportional term of the temperature loop")
    def p_value(self):
        return self.native.get_p_value()

    @read("i_value", unit="1", description="Integral term of the temperature loop")
    def i_value(self):
        return self.native.get_i_value()

    @read("d_value", unit="1", description="Derivative term of the temperature loop")
    def d_value(self):
        return self.native.get_d_value()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("temperature_setpoint", unit="K",
           description="Temperature-loop setpoint (TSET), in kelvin like the temperature reply",
           limit=Limit.operator_required(
               "the clone writes TSET (Bluesky4/mercury_itc.py:57) but states no valid range; the site sets the "
               "temperature range its sample and cryostat allow"))
    def set_temperature_setpoint(self, value):
        self.native.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:TSET:{value}")
        return self.native.get_gas_flow()

    @write("heater_setpoint", unit="1",
           description="Heater-loop setpoint (HSET) in the controller's configured unit",
           limit=Limit.operator_required(
               "the clone writes HSET (Bluesky4/mercury_itc.py:81) but states no valid range; the site sets the "
               "heater-loop range of its unit"))
    def set_heater_setpoint(self, value):
        self.native.set_heater_setpoint(value)
        return self.native.get_heater_setpoint()

    @write("p_value", unit="1", description="Proportional term of the temperature loop",
           limit=Limit.operator_required(_OPERATOR_REASON))
    def set_p_value(self, value):
        self.native.set_p_value(value)
        return self.native.get_p_value()

    @write("i_value", unit="1", description="Integral term of the temperature loop",
           limit=Limit.operator_required(_OPERATOR_REASON))
    def set_i_value(self, value):
        self.native.set_i_value(value)
        return self.native.get_i_value()

    @write("d_value", unit="1", description="Derivative term of the temperature loop",
           limit=Limit.operator_required(_OPERATOR_REASON))
    def set_d_value(self, value):
        self.native.set_d_value(value)
        return self.native.get_d_value()

    # -- safety ---------------------------------------------------------------------------------------------------
    @action(name="x-cap.kajalbiju.heater_off.v1", safe_state=True,
            description="Drive the temperature-loop setpoint to 0 K and the heater-loop setpoint to 0 (the safe "
                        "state); it takes no input",
            output={"heater_setpoint": Field("number", unit="1",
                                             description="Heater-loop setpoint after the action")})
    def heater_off(self):
        self._heater_off()
        return {"heater_setpoint": self.native.get_heater_setpoint()}

    @estop
    def stop(self):
        """The native stop: the runtime latches first, then writes TSET 0 and HSET 0."""
        self._heater_off()

    def _heater_off(self):
        # TSET first: with the loop's PID control on, the controller sets the heater output itself and HSET (the
        # manual output) alone would not stop it; with TSET at 0 K the loop does not heat.  Both writes are the ones
        # this driver already sends (set_temperature_setpoint, Bluesky4/mercury_itc.py:57 and :81).
        self.native.write(f"SET:DEV:{DEVICE_ADDRESS}:TEMP:LOOP:TSET:0")
        self.native.set_heater_setpoint(0.0)
