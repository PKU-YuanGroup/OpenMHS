"""OpenMHS driver for gh.jasapp/rigol: a RIGOL DP832A triple-channel DC power supply.

A direct Driver (decorated methods) over the upstream class rigol:RigolDP832A.  The upstream class speaks to the
instrument through a USB TMC device file: command() writes one line plus a newline and query() reads one reply line
(rigol.py:41-59).  The driver is therefore a plain synchronous object driver and each method calls self.native.

DEVIATION FROM THE CARD'S HELPER: the card names helper PythonObjectDriver (family python-object) with decision
direct-driver.  The upstream getters and setters take a channel number (rigol.py:62-103), while a PythonObjectDriver
read map has no arguments, and the driver needs one state field per channel; the package is therefore a decorated
direct Driver over the upstream class, and the native.py factory opens the USB TMC device.  No wire syntax is
changed.

* reads: the output state, voltage set point, current set point, measured voltage, measured current and measured
  power of channels 1, 2 and 3;
* writes through cap.device.configure.v1: the output state of each channel and the voltage and current set points of
  each channel.  No text file of the clone states a voltage or current range, so every numeric write is
  Limit.operator_required: it is refused MHS.SAFETY.LIMITS_UNSET until the operator supplies the range of the
  installed unit in site-limits.json (site-limits.example.json shows a deliberately narrow example);
* actions: set_ovp and set_ocp write the protection threshold and enable it (rigol.py:105-114); the upstream has no
  readback for a protection threshold, so they are x-cap actions whose output reports the channel and the value sent
  rather than a state write with an invented readback;
* the native stop is all_off() (rigol.py:129-132): @estop turns channels 1, 2 and 3 off.  This package declares no
  independent hardware e-stop, so it does not claim one.

Every Fact cites a line of the clone at the pinned commit 602b8623f820f6b4db4d225b1d66f11b3bbb6d6a.  This package
is model-authored and unreviewed (driver.lock.json reviewed_by is null); the hardware backend was never opened and
the fake is an in-memory stand-in, not a recording.  The loader refuses the hardware backend of an unreviewed
model-written package only at R2 and R3; this driver is R1, so nothing mechanical prevents a hardware run and an
operator must not pass --allow-hardware until a human has reviewed the package.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

#: The upstream module of the native class, relative to the clone root.
UPSTREAM = "rigol.py"

#: The channels the upstream all_off() loop and the REPL status display name (rigol.py:131, repl.py:28).
CHANNEL_LIMIT = Limit(min=1, max=3, source="upstream_code", ref=f"{UPSTREAM}:131",
                      reason="all_off() turns channels 1, 2 and 3 off; the REPL prints the same three channels")

#: The reason shared by the six numeric set-point bounds: the clone has no range statement at all.
SETPOINT_BOUND = (
    "the clone states no voltage or current range for the DP832A: its numeric command lines interpolate the "
    "caller's value (rigol.py:77, 90), and the clone has no README or other text manual; the site supplies the "
    "range of the installed unit from its nameplate")

#: The reason shared by the two protection-threshold bounds: the clone has no range statement for them either.
PROTECTION_BOUND = (
    "the clone states no range for an over-voltage or over-current protection threshold: set_ovp() and set_ocp() "
    "interpolate the caller's value and enable the protection (rigol.py:106-114), and the clone has no README or "
    "other text manual; the site supplies the threshold range of the installed unit")


class RigolDP832A(Driver):
    device_id = "rigol-dp832a"
    device_kind = "instrument"
    mode = "hardware"
    risk = "R1"
    native = "rigol:RigolDP832A"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRigolDP832A"}
    vendor, model = "RIGOL", "DP832A"
    display_name = "RIGOL DP832A triple-channel DC power supply"
    tags = ["power-supply", "dc-source", "triple-channel", "usb-tmc"]
    facts = [
        Fact("The class is a control interface for the RIGOL DP832A power supply over USB TMC",
             source="upstream_code", ref=f"{UPSTREAM}:1-4"),
        Fact("DEFAULT_DEVICE is /dev/usbtmc2", source="upstream_code", ref=f"{UPSTREAM}:13"),
        Fact("command() opens the device file, writes the command plus a newline, waits 50 ms and closes the file",
             source="upstream_code", ref=f"{UPSTREAM}:41-48"),
        Fact("query() writes the command plus a newline, waits 100 ms, reads up to 4096 bytes and strips the reply",
             source="upstream_code", ref=f"{UPSTREAM}:50-59"),
        Fact("output_on() sends :OUTP CH{channel},ON, output_off() sends :OUTP CH{channel},OFF, and get_output() "
             "reads :OUTP? CH{channel} and compares the reply with ON", source="upstream_code",
             ref=f"{UPSTREAM}:62-72"),
        Fact("set_voltage() writes :SOUR{channel}:VOLT and get_voltage_setpoint() reads :SOUR{channel}:VOLT?; "
             "measure_voltage() reads :MEAS:VOLT? CH{channel}", source="upstream_code", ref=f"{UPSTREAM}:75-85"),
        Fact("set_current() writes :SOUR{channel}:CURR and get_current_setpoint() reads :SOUR{channel}:CURR?; "
             "measure_current() reads :MEAS:CURR? CH{channel}", source="upstream_code", ref=f"{UPSTREAM}:88-98"),
        Fact("measure_power() reads :MEAS:POWE? CH{channel}", source="upstream_code", ref=f"{UPSTREAM}:100-103"),
        Fact("set_ovp() writes :OUTP:OVP:VAL CH{channel},{voltage} and enables :OUTP:OVP CH{channel},ON; set_ocp() "
             "does the same with :OUTP:OCP:VAL and :OUTP:OCP", source="upstream_code", ref=f"{UPSTREAM}:105-114"),
        Fact("status() returns one ChannelStatus with output, voltage_set, current_set, voltage, current and power",
             source="upstream_code", ref=f"{UPSTREAM}:117-127"),
        Fact("all_off() turns the outputs of channels 1, 2 and 3 off", source="upstream_code",
             ref=f"{UPSTREAM}:129-132"),
        Fact("configure() sets the voltage, then the current, then optionally turns the output on",
             source="upstream_code", ref=f"{UPSTREAM}:134-140"),
        Fact("The REPL prints the status of channels 1, 2 and 3", source="upstream_code", ref="repl.py:26-28"),
    ]
    safe_state = "all three channel outputs off (:OUTP CH1,OFF, :OUTP CH2,OFF and :OUTP CH3,OFF)"

    # -- reads: channel 1 -----------------------------------------------------------------------------------------
    @read("output_ch1", type="boolean", description="True while the channel 1 output is on (:OUTP? CH1)")
    def output_ch1(self):
        return bool(self.native.get_output(1))

    @read("voltage_setpoint_ch1", unit="V", description="Channel 1 voltage set point (:SOUR1:VOLT?)")
    def voltage_setpoint_ch1(self):
        return float(self.native.get_voltage_setpoint(1))

    @read("current_setpoint_ch1", unit="A", description="Channel 1 current set point (:SOUR1:CURR?)")
    def current_setpoint_ch1(self):
        return float(self.native.get_current_setpoint(1))

    @read("voltage_ch1", unit="V", description="Channel 1 measured voltage (:MEAS:VOLT? CH1)")
    def voltage_ch1(self):
        return float(self.native.measure_voltage(1))

    @read("current_ch1", unit="A", description="Channel 1 measured current (:MEAS:CURR? CH1)")
    def current_ch1(self):
        return float(self.native.measure_current(1))

    @read("power_ch1", unit="W", description="Channel 1 measured power (:MEAS:POWE? CH1)")
    def power_ch1(self):
        return float(self.native.measure_power(1))

    # -- reads: channel 2 -----------------------------------------------------------------------------------------
    @read("output_ch2", type="boolean", description="True while the channel 2 output is on (:OUTP? CH2)")
    def output_ch2(self):
        return bool(self.native.get_output(2))

    @read("voltage_setpoint_ch2", unit="V", description="Channel 2 voltage set point (:SOUR2:VOLT?)")
    def voltage_setpoint_ch2(self):
        return float(self.native.get_voltage_setpoint(2))

    @read("current_setpoint_ch2", unit="A", description="Channel 2 current set point (:SOUR2:CURR?)")
    def current_setpoint_ch2(self):
        return float(self.native.get_current_setpoint(2))

    @read("voltage_ch2", unit="V", description="Channel 2 measured voltage (:MEAS:VOLT? CH2)")
    def voltage_ch2(self):
        return float(self.native.measure_voltage(2))

    @read("current_ch2", unit="A", description="Channel 2 measured current (:MEAS:CURR? CH2)")
    def current_ch2(self):
        return float(self.native.measure_current(2))

    @read("power_ch2", unit="W", description="Channel 2 measured power (:MEAS:POWE? CH2)")
    def power_ch2(self):
        return float(self.native.measure_power(2))

    # -- reads: channel 3 -----------------------------------------------------------------------------------------
    @read("output_ch3", type="boolean", description="True while the channel 3 output is on (:OUTP? CH3)")
    def output_ch3(self):
        return bool(self.native.get_output(3))

    @read("voltage_setpoint_ch3", unit="V", description="Channel 3 voltage set point (:SOUR3:VOLT?)")
    def voltage_setpoint_ch3(self):
        return float(self.native.get_voltage_setpoint(3))

    @read("current_setpoint_ch3", unit="A", description="Channel 3 current set point (:SOUR3:CURR?)")
    def current_setpoint_ch3(self):
        return float(self.native.get_current_setpoint(3))

    @read("voltage_ch3", unit="V", description="Channel 3 measured voltage (:MEAS:VOLT? CH3)")
    def voltage_ch3(self):
        return float(self.native.measure_voltage(3))

    @read("current_ch3", unit="A", description="Channel 3 measured current (:MEAS:CURR? CH3)")
    def current_ch3(self):
        return float(self.native.measure_current(3))

    @read("power_ch3", unit="W", description="Channel 3 measured power (:MEAS:POWE? CH3)")
    def power_ch3(self):
        return float(self.native.measure_power(3))

    # -- writes: channel 1 ----------------------------------------------------------------------------------------
    @write("output_ch1", type="boolean", risk="R1", description="CH1 output enabled")
    def set_output_ch1(self, value):
        if value:
            self.native.output_on(1)
        else:
            self.native.output_off(1)
        return bool(self.native.get_output(1))

    @write("voltage_setpoint_ch1", unit="V", risk="R1",
           description="CH1 voltage set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_voltage_setpoint_ch1(self, value):
        self.native.set_voltage(1, value)
        return float(self.native.get_voltage_setpoint(1))

    @write("current_setpoint_ch1", unit="A", risk="R1",
           description="CH1 current set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_current_setpoint_ch1(self, value):
        self.native.set_current(1, value)
        return float(self.native.get_current_setpoint(1))

    # -- writes: channel 2 ----------------------------------------------------------------------------------------
    @write("output_ch2", type="boolean", risk="R1", description="CH2 output enabled")
    def set_output_ch2(self, value):
        if value:
            self.native.output_on(2)
        else:
            self.native.output_off(2)
        return bool(self.native.get_output(2))

    @write("voltage_setpoint_ch2", unit="V", risk="R1",
           description="CH2 voltage set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_voltage_setpoint_ch2(self, value):
        self.native.set_voltage(2, value)
        return float(self.native.get_voltage_setpoint(2))

    @write("current_setpoint_ch2", unit="A", risk="R1",
           description="CH2 current set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_current_setpoint_ch2(self, value):
        self.native.set_current(2, value)
        return float(self.native.get_current_setpoint(2))

    # -- writes: channel 3 ----------------------------------------------------------------------------------------
    @write("output_ch3", type="boolean", risk="R1", description="CH3 output enabled")
    def set_output_ch3(self, value):
        if value:
            self.native.output_on(3)
        else:
            self.native.output_off(3)
        return bool(self.native.get_output(3))

    @write("voltage_setpoint_ch3", unit="V", risk="R1",
           description="CH3 voltage set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_voltage_setpoint_ch3(self, value):
        self.native.set_voltage(3, value)
        return float(self.native.get_voltage_setpoint(3))

    @write("current_setpoint_ch3", unit="A", risk="R1",
           description="CH3 current set point",
           limit=Limit.operator_required(SETPOINT_BOUND))
    def set_current_setpoint_ch3(self, value):
        self.native.set_current(3, value)
        return float(self.native.get_current_setpoint(3))

    # -- protection actions ---------------------------------------------------------------------------------------
    @action(name="x-cap.jasapp.set_ovp.v1", risk="R1",
            description="Set the over-voltage protection threshold of one channel and enable it (:OUTP:OVP)",
            input={"channel": Field("integer", unit="1", description="Channel number (1 to 3)",
                                    limit=CHANNEL_LIMIT),
                   "voltage": Field("number", unit="V", description="Over-voltage protection threshold",
                                    limit=Limit.operator_required(PROTECTION_BOUND))},
            output={"channel": Field("integer", unit="1", description="Channel whose protection was set"),
                    "voltage": Field("number", unit="V",
                                     description="Over-voltage threshold written to the channel")})
    def set_ovp(self, channel, voltage):
        self.native.set_ovp(channel, voltage)
        return {"channel": int(channel), "voltage": float(voltage)}

    @action(name="x-cap.jasapp.set_ocp.v1", risk="R1",
            description="Set the over-current protection threshold of one channel and enable it (:OUTP:OCP)",
            input={"channel": Field("integer", unit="1", description="Channel number (1 to 3)",
                                    limit=CHANNEL_LIMIT),
                   "current": Field("number", unit="A", description="Over-current protection threshold",
                                    limit=Limit.operator_required(PROTECTION_BOUND))},
            output={"channel": Field("integer", unit="1", description="Channel whose protection was set"),
                    "current": Field("number", unit="A",
                                     description="Over-current threshold written to the channel")})
    def set_ocp(self, channel, current):
        self.native.set_ocp(channel, current)
        return {"channel": int(channel), "current": float(current)}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="all_off")
    def stop(self):
        """The native stop: the runtime latches first, then all_off() turns channels 1, 2 and 3 off."""
        self.native.all_off()
