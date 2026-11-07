"""OpenMHS driver for gh.prathameshnium/pica-python-instrument-control-and-automation: a Cryo-con Model 34.

A direct Driver over the upstream backend class
``pica.cryocon.T_Control_CC34_DirectControl_GUI:Cryocon34Backend`` (pica/cryocon/T_Control_CC34_DirectControl_GUI.py:547).
The upstream class wraps one paced PyVISA session to a Cryo-con Model 34 and exposes the SCPI calls of the
controller: four input channels A-D and two control loops, loop 1 (HEATER) and loop 2 (AOUT) (line 562, line 586).

* reads: the channel A temperature, the loop 1 setpoint, the control state, the heater read-back, loop type and
  source, the output limits, the ramp rate, the channel units, the input name and alarm state, the ambient reading,
  the identification, the error queue, the display settings, the keypad lockout, loop 1's load and the factory sensor
  index;
* writes: the loop 1 setpoint, maximum power, maximum setpoint, manual power, loop type and source, display filter
  time constant and heater load.  Display resolution, input name, keypad lockout and factory sensor index are
  read-only in this package: the factory sensor index needs a count the clone does not state, and none of them is
  part of the control path;
* actions: engage the control loops and stop them (STOP is the safe state and the e-stop).  The setpoint write is
  immediate; the package exposes no ramp action.

The controller reports temperature and setpoint in the display unit of the source channel (line 1071).  The driver
publishes kelvin and requires the source channel to display Kelvin, as the suite's Cryo-con variants verify before a
run (docs/User_Manual.md:895-896); it refuses a controller configured in C, F or S rather than guessing a conversion.

The numeric writes whose safe range depends on the cryostat and the sample are ``Limit.operator_required``: the site
overlay supplies them (site-limits.example.json shows the overlay).  The bounds the controller itself enforces are
cited for the enumeration writes.

This package is model-authored and unreviewed.  It runs on the fake backend only; the loader refuses the hardware
backend of a model-authored R2 package until a human signs reviewed_by in driver.lock.json.  No hardware run was made.
"""

import re as _re

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The leading number of a Cryo-con reply.  The controller may append its unit character ('4.200K', '0.0%') and
#: returns status strings such as '-------' when the sensor is faulty; the parser rejects those rather than guessing.
_NUMBER = _re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")


def _number(raw, what):
    """Parse the leading number of a reply; raise a typed failure for a status string."""
    text = str(raw).strip().rstrip("%").strip()
    match = _NUMBER.match(text)
    if not match:
        raise DriverFailed("MHS.DEVICE.STATE_INVALID", f"{what} returned {text!r}, which is not a number")
    return float(match.group(0))


def _integer(raw, what):
    """Parse the leading integer of a reply."""
    return int(_number(raw, what))


def _boolean(raw, what):
    """Parse the controller's ON/OFF reply."""
    text = str(raw).strip().upper()
    if text in ("ON", "1", "TRUE"):
        return True
    if text in ("OFF", "0", "FALSE"):
        return False
    raise DriverFailed("MHS.DEVICE.STATE_INVALID", f"{what} returned {text!r}, which is not ON/OFF")


def _source_channel(raw):
    """The channel letter of a loop source reply such as 'CHA', 'CH A' or 'A'."""
    text = str(raw).strip().upper()
    if text.startswith("CH"):
        text = text[2:].strip()
    if text in ("A", "B", "C", "D"):
        return text
    raise DriverFailed("MHS.DEVICE.STATE_INVALID", f"loop 1 source returned {raw!r}, which is not channel A-D")


class Cryocon34(Driver):
    device_id = "cryocon34"
    device_kind = "thermal.zone"
    mode = "hardware"
    risk = "R2"
    native = "pica.cryocon.T_Control_CC34_DirectControl_GUI:Cryocon34Backend"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCryocon34"}
    vendor, model = "Cryo-con", "Model 34"
    display_name = "Cryo-con 34 temperature controller (PICA Cryocon34Backend)"
    tags = ["cryocon", "temperature-controller", "cryostat", "gpib", "direct-control"]
    facts = [
        Fact("The backend is for the Cryo-con Model 34 and its SCPI command set is shared across the Cryo-con family",
             source="upstream_code", ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:547-551"),
        Fact("A Model 34 has four input channels, A, B, C and D", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:562"),
        Fact("Control loop 1 is the primary heater and is addressed as HEATER; loop 2 is AOUT", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:586"),
        Fact("The channel display units are K, C, F and S", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:589-594"),
        Fact("INPUT? reports in the channel's display units, not always Kelvin", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1071"),
        Fact("The suite's Cryo-con variants verify that the chosen channel is displaying Kelvin before a run starts",
             source="vendor_doc", ref="docs/User_Manual.md:895-896"),
        Fact("set_setpoint_immediate validates 0 <= value <= 1000 in the loop's display units",
             source="upstream_code", ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:845"),
        Fact("CONTROL activates every enabled control loop; STOP disengages all loops and disconnects the heaters",
             source="upstream_code", ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1200-1205"),
        Fact("control_stop writes STOP", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1204-1207"),
        Fact("get_control_status queries CONTROL? and reports ON or OFF", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1209-1211"),
        Fact("set_load accepts only 50 or 25 ohm", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:946-948"),
        Fact("The loop control types are Off, PID, Man, Table and RampP", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:597-603"),
        Fact("The loop control source is one of the input channels A, B, C and D", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:562"),
        Fact("set_display_resolution accepts FULL, 1, 2 and 3", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1225-1227"),
        Fact("The selectable display filter time constants are 0.5, 1, 2, 4, 8, 16, 32 and 64",
             source="upstream_code", ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:613"),
        Fact("set_display_time_constant sets the display filter time constant in seconds", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1239-1240"),
        Fact("set_input_name sets a custom name of at most 15 characters", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1129"),
        Fact("set_factory_sensor_index accepts an index >= 0 and 0 disables the curve", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1103-1106"),
        Fact("reset sends *RST, a ~15 s hardware reset to power-up defaults; this driver does not expose it",
             source="upstream_code", ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:1272-1275"),
        Fact("disconnect only closes the VISA resource; it sends no *RST, no STOP and no loop, heater or setpoint "
             "change", source="upstream_code",
             ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:551-556"),
        Fact("The manual's example address for a Cryo-con 34 is GPIB1::23::INSTR", source="vendor_doc",
             ref="docs/User_Manual.md:958"),
    ]
    safe_state = "control loops disengaged and heaters disconnected (the native STOP command)"

    # -- unit policy -------------------------------------------------------------------------------------------

    def setup(self):
        """Refuse a controller whose channel A or loop 1 source is not displaying Kelvin."""
        self._require_kelvin("A")
        self._setpoint_channel()

    def _require_kelvin(self, channel):
        units = str(self.native.get_units(channel)).strip().upper()
        if units not in ("K", "KELVIN"):
            raise DriverFailed(
                "MHS.DEVICE.PRECONDITION_UNMET",
                f"input channel {channel} is set to {units or 'an unknown unit'}; this driver requires Kelvin (K)")

    def _setpoint_channel(self):
        """The source channel of loop 1; the setpoint is in that channel's display unit."""
        channel = _source_channel(self.native.get_loop_source("1"))
        self._require_kelvin(channel)
        return channel

    # -- reads -------------------------------------------------------------------------------------------------

    @read("temperature", unit="K",
          description="Input channel A temperature, in the channel's display unit (Kelvin required)")
    def temperature(self):
        self._require_kelvin("A")
        return _number(self.native.get_temperature("A"), "INPUT? A")

    @read("setpoint", unit="K",
          description="Loop 1 setpoint, in the source channel's display unit (Kelvin required)")
    def setpoint(self):
        self._setpoint_channel()
        return _number(self.native.get_setpoint("1"), "HEATER:SETPT?")

    @read("control_engaged", type="boolean",
          description="True while the control loops are engaged (CONTROL? reports ON)")
    def control_engaged(self):
        return _boolean(self.native.get_control_status(), "CONTROL?")

    @read("heater_readback", type="string",
          description="Raw loop 1 heater output read-back; 'nan' when this controller answers no read-back mnemonic")
    def heater_readback(self):
        return str(self.native.get_heater_readback("1"))

    @read("loop_type", type="string", description="Loop 1 control type (Off, PID, Man, Table or RampP)")
    def loop_type(self):
        return str(self.native.get_loop_type("1"))

    @read("loop_source", type="string", description="Loop 1 controlling input channel (A, B, C or D)")
    def loop_source(self):
        return _source_channel(self.native.get_loop_source("1"))

    @read("max_power", unit="%", description="Loop 1 maximum output power, percent of full scale")
    def max_power(self):
        return _number(self.native.get_max_power("1"), "HEATER:MAXPWR?")

    @read("max_setpoint", unit="K", description="Loop 1 maximum allowed setpoint, in the source channel's unit")
    def max_setpoint(self):
        return _number(self.native.get_max_setpoint("1"), "HEATER:MAXSET?")

    @read("manual_power", unit="%", description="Loop 1 manual output power, percent of full scale")
    def manual_power(self):
        return _number(self.native.get_manual_power("1"), "HEATER:PMANUAL?")

    @read("ramp_rate", unit="K/min", description="Loop 1 setpoint ramp rate, in display units per minute")
    def ramp_rate(self):
        return _number(self.native.get_rate("1"), "HEATER:RATE?")

    @read("input_units", type="string", description="Display units of input channel A (K, C, F or S)")
    def input_units(self):
        return str(self.native.get_units("A")).strip().upper()

    @read("source_units", type="string", description="Display units of loop 1's source channel (K, C, F or S)")
    def source_units(self):
        channel = _source_channel(self.native.get_loop_source("1"))
        return str(self.native.get_units(channel)).strip().upper()

    @read("input_name", type="string", description="Custom name of input channel A")
    def input_name(self):
        return str(self.native.get_input_name("A"))

    @read("alarm_status", type="string", description="Alarm status of input channel A")
    def alarm_status(self):
        return str(self.native.get_alarm_status("A"))

    @read("alarm", type="array", items="string", length=4,
          description="Input A alarm: high setpoint, low setpoint, high enable and low enable")
    def alarm(self):
        return tuple(str(item) for item in self.native.get_alarm("A"))

    @read("ambient", type="string", description="Internal reference temperature, for example '+25C'")
    def ambient(self):
        return str(self.native.get_ambient())

    @read("idn", type="string", description="Instrument identification (*IDN?)")
    def idn(self):
        return str(self.native.get_idn())

    @read("error_queue", type="string", description="Instrument error queue (SYSTEM:ERROR?)")
    def error_queue(self):
        return str(self.native.get_error_queue())

    @read("display_resolution", type="string", description="Front-panel display resolution (FULL, 1, 2 or 3)")
    def display_resolution(self):
        return str(self.native.get_display_resolution())

    @read("display_time_constant", unit="s", description="Display filter time constant in seconds")
    def display_time_constant(self):
        return _number(self.native.get_display_time_constant(), "SYSTEM:DISTC?")

    @read("lockout", type="boolean", description="True while the front-panel keypad is locked out")
    def lockout(self):
        return _boolean(self.native.get_lockout(), "SYSTEM:LOCKOUT?")

    @read("load", type="integer", unit="Ohm", description="Loop 1 heater load resistance, 25 or 50 ohm")
    def load(self):
        return _integer(self.native.get_load(), "HEATER:LOAD?")

    @read("factory_sensor_index", type="integer", unit="1",
          description="Factory sensor curve index of input channel A; 0 disables the curve")
    def factory_sensor_index(self):
        return _integer(self.native.get_factory_sensor_index("A"), "INPUT A:ISENIX?")

    # -- writes ------------------------------------------------------------------------------------------------

    @write("setpoint", unit="K",
           description="Loop 1 setpoint (K, no ramping)",
           limit=Limit.operator_required(
               "the clone validates 0 to 1000 in the loop's display units, but the safe setpoint depends on the "
               "cryostat and the sample; the site supplies the range"))
    def set_setpoint(self, value):
        self._setpoint_channel()
        self.native.set_setpoint_immediate("1", value)
        return _number(self.native.get_setpoint("1"), "HEATER:SETPT?")

    @write("max_power", unit="%", description="Loop 1 maximum power (%)",
           limit=Limit.operator_required(
               "the clone validates 0 to 100 percent of full scale, but the safe heater power depends on the "
               "cryostat and the sample; the site supplies the range"))
    def set_max_power(self, value):
        self.native.set_max_power("1", value)
        return _number(self.native.get_max_power("1"), "HEATER:MAXPWR?")

    @write("max_setpoint", unit="K",
           description="Loop 1 maximum setpoint (K)",
           limit=Limit.operator_required(
               "the clone validates 0 to 1000 K, but the highest setpoint the cryostat may use is a site decision; "
               "the site supplies it"))
    def set_max_setpoint(self, value):
        self.native.set_max_setpoint("1", value)
        return _number(self.native.get_max_setpoint("1"), "HEATER:MAXSET?")

    @write("manual_power", unit="%", description="Loop 1 manual power (%)",
           limit=Limit.operator_required(
               "the clone validates 0 to 100 percent of full scale, but manual heater power is a site hazard bound; "
               "the site supplies the range"))
    def set_manual_power(self, value):
        self.native.set_manual_power("1", value)
        return _number(self.native.get_manual_power("1"), "HEATER:PMANUAL?")

    @write("loop_type", type="string", description="Loop 1 control type",
           limit=Limit(allowed=["Off", "PID", "Man", "Table", "RampP"], source="upstream_code",
                       ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:597-603"))
    def set_loop_type(self, value):
        self.native.set_loop_type("1", value)
        return str(self.native.get_loop_type("1"))

    @write("loop_source", type="string", description="Loop 1 input channel",
           limit=Limit(allowed=["A", "B", "C", "D"], source="upstream_code",
                       ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:562"))
    def set_loop_source(self, value):
        self._require_kelvin(value)
        self.native.set_loop_source("1", value)
        return _source_channel(self.native.get_loop_source("1"))

    @write("display_time_constant", unit="s", description="Display filter time constant (s)",
           limit=Limit(allowed=[0.5, 1, 2, 4, 8, 16, 32, 64], unit="s", source="upstream_code",
                       ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:613"))
    def set_display_time_constant(self, value):
        self.native.set_display_time_constant(f"{float(value):g}")
        return _number(self.native.get_display_time_constant(), "SYSTEM:DISTC?")

    @write("load", type="integer", unit="Ohm", description="Loop 1 heater load (ohm)",
           limit=Limit(allowed=[25, 50], unit="Ohm", source="upstream_code",
                       ref="pica/cryocon/T_Control_CC34_DirectControl_GUI.py:946-948"))
    def set_load(self, value):
        self.native.set_load(int(value))
        return _integer(self.native.get_load(), "HEATER:LOAD?")

    # -- actions -----------------------------------------------------------------------------------------------

    @action(name="x-cap.prathameshnium.control_engage.v1",
            description="Engage every enabled control loop at the configured setpoint (native CONTROL)",
            output={"engaged": Field("boolean", description="True once CONTROL? reports ON")})
    def control_engage(self):
        self._setpoint_channel()
        self.native.control_engage()
        return {"engaged": _boolean(self.native.get_control_status(), "CONTROL?")}

    @action(name="x-cap.prathameshnium.control_stop.v1", safe_state=True,
            description="Disengage all control loops and disconnect the heaters (native STOP), the safe state",
            output={"engaged": Field("boolean", description="False once CONTROL? reports OFF")})
    def control_stop(self):
        self.native.control_stop()
        return {"engaged": _boolean(self.native.get_control_status(), "CONTROL?")}

    # -- safety and lifecycle ----------------------------------------------------------------------------------

    @estop(native="control_stop")
    def stop(self):
        """The native stop: STOP disengages every loop and disconnects the heaters."""
        self.native.control_stop()

    def teardown(self):
        """Close the VISA session; the upstream disconnect is non-destructive."""
        self.native.disconnect()
