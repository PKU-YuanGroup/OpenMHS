"""OpenMHS driver for gh.allenneuraldynamics/runze-control: a Runze ZSB-SY01B syringe pump.

A direct Driver (decorated methods) over the upstream device class
``runze_control.multichannel_syringe_pump:SY01B``.  The card's family is a plain Python object, but every upstream
command is a binary Runze protocol frame assembled at run time from the address, a command byte, two parameter bytes
and a checksum (``runze_control/runze_device.py:290-321``), so the package uses a native factory
(``driver-authoring.md``, "Choosing the shape") instead of the declarative PythonObjectDriver.  DEVIATION FROM THE
CARD: direct Driver with native.py; recorded in RESULT.json.

* reads: plunger position in steps, percent and microliters, firmware version, bus address, RS-232 baud rate, motor
  status and the busy flag;
* actions: absolute move in percent, aspirate and dispense a volume, select a valve port, reset the syringe, set the
  plunger speed, and the native stop as the safe-state action;
* the native stop (``ForceStop``) is the e-stop and the safe-state action.  No line of the clone documents an
  independent hardware e-stop, so ``estop_physical_ref`` is not set.

The device's syringe volume and valve port count are deployment configuration, not library defaults: the native
factory takes ``syringe_volume_ul`` and the volume and port inputs use ``Limit.operator_required`` until the site
overlay supplies their envelope (``site-limits.example.json`` shows the overlay).

Every Fact cites a line of the clone at the pinned commit (34392b3d9bc0d60c0c46f69908fec7f108cef230).  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: Paths in the clone, kept together so every Fact and Limit cites the pinned commit.
PUMP = "src/runze_control/syringe_pump.py"
MULTI = "src/runze_control/multichannel_syringe_pump.py"
DEVICE = "src/runze_control/runze_device.py"
PROTOCOL = "src/runze_control/runze_protocol.py"


class RunzeSY01B(Driver):
    device_id = "runze-sy01b"
    device_kind = "actuation.pump"
    mode = "hardware"
    risk = "R2"
    native = "runze_control.multichannel_syringe_pump:SY01B"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSY01B"}
    vendor, model = "Runze Fluid", "ZSB-SY01B"
    display_name = "Runze ZSB-SY01B multichannel syringe pump"
    tags = ["syringe pump", "fluid", "serial", "multichannel", "valve"]
    facts = [
        Fact("SY01B is the ZSB-SY01B multichannel syringe pump with an integrated rotary valve",
             source="upstream_code", ref=f"{MULTI}:80-81"),
        Fact("SY01B supports 6, 9 and 12 valve ports", source="upstream_code", ref=f"{MULTI}:82"),
        Fact("SY01B supports syringe volumes of 25, 50, 125, 500, 1250, 2500 and 5000 uL, all with 6000 position "
             "steps", source="upstream_code", ref=f"{MULTI}:87-90"),
        Fact("get_position_steps queries GetSyringePosition and returns the reply parameter in encoder steps",
             source="upstream_code", ref=f"{PUMP}:56-64"),
        Fact("get_position_ul converts the step count with the configured syringe volume and max_position_steps",
             source="upstream_code", ref=f"{PUMP}:66-68"),
        Fact("get_position_percent scales the step count by max_position_steps", source="upstream_code",
             ref=f"{PUMP}:70-71"),
        Fact("aspirate converts microliters to steps with max_position_steps / syringe_volume_ul and sends RunInCCW",
             source="upstream_code", ref=f"{PUMP}:73-77"),
        Fact("dispense converts microliters to steps and sends RunInCW", source="upstream_code",
             ref=f"{PUMP}:83-87"),
        Fact("reset_syringe_position sets the default speed, sends ResetSyringePosition and "
             "SynchronizeSyringePosition, and zeroes the local step count", source="upstream_code",
             ref=f"{PUMP}:41-54"),
        Fact("force_stop sends ForceStop and then reads the position", source="upstream_code",
             ref=f"{PUMP}:104-115"),
        Fact("set_speed_percent rejects a plunger speed outside 0 to 100 percent", source="upstream_code",
             ref=f"{PUMP}:138-150"),
        Fact("get_speed_percent returns the locally stored value, not a device reading", source="upstream_code",
             ref=f"{PUMP}:152-155"),
        Fact("get_motor_status returns the reply parameter of GetMotorStatus", source="upstream_code",
             ref=f"{PUMP}:120-123"),
        Fact("get_address queries GetAddress and returns the reply parameter", source="upstream_code",
             ref=f"{DEVICE}:170-178"),
        Fact("get_rs232_baudrate maps the reply parameter through RS232BaudrateReply, whose codes are 9600, 19200, "
             "38400, 57600 and 115200 bps", source="upstream_code", ref=f"{PROTOCOL}:45-53"),
        Fact("get_firmware_version returns the major and minor reply bytes as a float", source="upstream_code",
             ref=f"{DEVICE}:145-151"),
        Fact("Runze protocol frames use STX 0xCC and ETX 0xDD", source="upstream_code", ref=f"{PROTOCOL}:20-23"),
        Fact("The default communication timeout is 0.5 s and the long timeout used for syringe moves is 60 s",
             source="upstream_code", ref=f"{DEVICE}:38-42"),
        Fact("move_absolute_in_percent rejects a target outside 0 to 100 percent", source="upstream_code",
             ref=f"{MULTI}:70-74"),
        Fact("move_valve_to_position sends MoveValveToPort with the requested port", source="upstream_code",
             ref=f"{MULTI}:38-40"),
    ]
    safe_state = "syringe movement stopped with the native ForceStop command; the valve stays where it is"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position_steps", type="integer", description="Syringe plunger position in encoder steps")
    def position_steps(self):
        return self.native.get_position_steps()

    @read("position_percent", unit="%", description="Syringe plunger position as percent of full travel")
    def position_percent(self):
        return self.native.get_position_percent()

    @read("position_ul", unit="uL",
          description="Syringe plunger position in microliters, converted with the configured syringe volume")
    def position_ul(self):
        return self.native.get_position_ul()

    @read("firmware_version", type="number",
          description="Firmware version reported as major.minor (for example 1.2)")
    def firmware_version(self):
        return self.native.get_firmware_version()

    @read("address", type="integer", description="Address of this device on the serial bus")
    def address(self):
        return self.native.get_address()

    @read("rs232_baudrate", type="integer", description="RS-232 baud rate reported by the device")
    def rs232_baudrate(self):
        return self.native.get_rs232_baudrate()

    @read("motor_status", type="integer", description="Motor status code reported by the device")
    def motor_status(self):
        return self.native.get_motor_status()

    @read("busy", type="boolean", description="True while the device still owes a reply to a command")
    def busy(self):
        return self.native.is_busy()

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.allenneuraldynamics.runze_move_to_percent.v1",
            description="Move the plunger to an absolute position in percent of full travel",
            input={"position": Field(
                "number", unit="%", description="Target plunger position in percent of full travel",
                limit=Limit(min=0, max=100, source="upstream_code", ref=f"{MULTI}:70-74"))},
            output={"position_percent": Field(
                "number", unit="%", description="Plunger position reported after the move")})
    def move_to_percent(self, position):
        self.native.move_absolute_in_percent(position)
        return {"position_percent": self.native.get_position_percent()}

    @action(name="x-cap.allenneuraldynamics.runze_aspirate.v1",
            description="Withdraw a volume from the current liquid path by moving the plunger",
            input={"volume": Field(
                "number", unit="uL", description="Volume to withdraw",
                limit=Limit.operator_required(
                    "the usable volume depends on the syringe fitted to the pump and on the liquid path; the "
                    "configured syringe volume is a deployment setting, so the site supplies the volume envelope"))},
            output={"aspirated_volume": Field(
                "number", unit="uL", description="Volume the plunger actually withdrew"),
                "position_ul": Field("number", unit="uL",
                                     description="Plunger position in microliters after the move")})
    def aspirate(self, volume):
        before = self.native.get_position_ul()
        self.native.aspirate(volume)
        after = self.native.get_position_ul()
        return {"aspirated_volume": after - before, "position_ul": after}

    @action(name="x-cap.allenneuraldynamics.runze_dispense.v1",
            description="Dispense a volume into the current liquid path by moving the plunger",
            input={"volume": Field(
                "number", unit="uL", description="Volume to dispense",
                limit=Limit.operator_required(
                    "the usable volume depends on the syringe fitted to the pump and on the liquid path; the "
                    "configured syringe volume is a deployment setting, so the site supplies the volume envelope"))},
            output={"dispensed_volume": Field(
                "number", unit="uL", description="Volume the plunger actually dispensed"),
                "position_ul": Field("number", unit="uL",
                                     description="Plunger position in microliters after the move")})
    def dispense(self, volume):
        before = self.native.get_position_ul()
        self.native.dispense(volume)
        after = self.native.get_position_ul()
        return {"dispensed_volume": before - after, "position_ul": after}

    @action(name="x-cap.allenneuraldynamics.runze_select_valve_port.v1",
            description="Move the integrated rotary valve to one port",
            input={"port": Field(
                "integer", unit="1", description="Valve port number",
                limit=Limit.operator_required(
                    "the number of ports fitted to the valve is a deployment setting (the model supports 6, 9 or "
                    "12 ports), so the site supplies the valid port range"))},
            output={"port": Field("integer", unit="1",
                                  description="Valve port requested; the device does not report the achieved port")})
    def select_valve_port(self, port):
        self.native.move_valve_to_position(port)
        return {"port": port}

    @action(name="x-cap.allenneuraldynamics.runze_reset_syringe.v1",
            description="Home the syringe at the optocoupler position and synchronize the step count to zero",
            output={"position_steps": Field(
                "integer", description="Plunger position in encoder steps after the reset")})
    def reset_syringe(self):
        self.native.reset_syringe_position()
        return {"position_steps": self.native.get_position_steps()}

    @action(name="x-cap.allenneuraldynamics.runze_set_speed.v1",
            description="Set the plunger speed as a percentage of the maximum speed for the fitted syringe",
            input={"percent": Field(
                "number", unit="%", description="Plunger speed in percent of the maximum speed",
                limit=Limit(min=0, max=100, source="upstream_code", ref=f"{PUMP}:138-150"))},
            output={"speed_percent": Field(
                "number", unit="%", description="Plunger speed the device accepted")})
    def set_speed(self, percent):
        self.native.set_speed_percent(percent)
        return {"speed_percent": self.native.get_speed_percent()}

    @action(name="x-cap.allenneuraldynamics.runze_stop.v1", safe_state=True,
            description="Stop the plunger with the native ForceStop command; it takes no input",
            output={"stopped": Field("boolean", description="True once the stop command completed"),
                    "position_steps": Field("integer",
                                            description="Plunger position in encoder steps after the stop")})
    def stop_pump(self):
        self.native.force_stop()
        return {"stopped": True, "position_steps": self.native.get_position_steps()}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then sends ForceStop."""
        self.native.force_stop()

    def teardown(self):
        if self.native.ser is not None:
            self.native.ser.close()
