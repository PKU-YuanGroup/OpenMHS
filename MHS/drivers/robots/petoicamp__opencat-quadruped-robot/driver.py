"""OpenMHS driver for gh.petoicamp/opencat-quadruped-robot: Petoi OpenCat quadruped telemetry.

The upstream repository is an Arduino sketch for the NyBoard (ATmega328P) plus a Python serial API.  This package
uses the card's entry class, ``serialMaster.SerialCommunication.Communication``, as the hardware backend: a direct
:class:`~mhs.driver.Driver` opens that class and sends the firmware's own ASCII serial tokens.  The card's
``SerialDriver`` helper cannot express the protocol, because the upstream Python layer assembles each command from a
token and arguments (and some tokens are binary frames), so this is a deliberate deviation from the card's
``family: serial`` helper.

Covered here:

* reads: the model and firmware identity (``?``), the pitch and roll reported by the IMU (``v``), and the current
  joint angles in degrees (``j``);
* one action: ``x-cap.petoicamp.rest.v1``, the ``d`` rest command, which puts the robot down and shuts its servos
  down; it is also the safe-state action of the e-stop;
* the e-stop (``d``) sends the same rest command.

Not covered: locomotion skills, joint commands, calibration, the buzzer and the optional sensor pack.  The device is
a mobile quadruped, so the risk is R2 although this driver only reads telemetry and can stop the robot.

Every Fact cites a line of the clone at the pinned commit
24563ca2e0218150f6299d013cd3a20c45433467.  This package is model-authored and unreviewed; no hardware was attached.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, action, estop, read

#: Lines read from the serial port while waiting for the firmware's echo of one command.  A bound, not a device
#: fact: a real reply ends with the echoed token, and a verbose firmware prints extra gyro lines.
_REPLY_LINES = 64


class OpencatQuadruped(Driver):
    device_id = "opencat-quadruped"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    risk = "R2"
    native = "serialMaster.SerialCommunication:Communication"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeCommunication"}
    vendor, model = "Petoi", "OpenCat (Bittle / Nybble on NyBoard)"
    display_name = "Petoi OpenCat quadruped"
    tags = ["quadruped", "robot", "opencat", "bittle", "nybble", "serial", "telemetry"]
    facts = [
        Fact("The firmware defines 16 degrees of freedom (DOF 16)", source="upstream_code",
             ref="src/OpenCat.h:13"),
        Fact("The sketch drives up to 16 PWM servos", source="upstream_code", ref="OpenCat.ino:4"),
        Fact("The serial query token '?' prints the model name and the software version, one per line",
             source="upstream_code", ref="src/reaction.h:91-95"),
        Fact("The firmware converts the IMU yaw, pitch and roll from radians to degrees before printing",
             source="upstream_code", ref="src/imu.h:204-208"),
        Fact("print6Axis prints ypr[1] and ypr[2] as two tab-separated columns followed by a newline",
             source="upstream_code", ref="src/imu.h:168-188"),
        Fact("The 'v' token prints the gyro data once", source="upstream_code", ref="src/OpenCat.h:236"),
        Fact("The 'j' handler prints the current joint angles with printTable", source="upstream_code",
             ref="src/reaction.h:173-179"),
        Fact("printTable prints the joint indices 0 to DOF-1 and then the values separated by a comma and a tab",
             source="upstream_code", ref="src/tools.h:33-46"),
        Fact("The joint angle unit of the serial commands is degree", source="vendor_doc",
             ref="serialMaster/README.md:71"),
        Fact("The 'd' token puts the robot down and shuts down the servos", source="vendor_doc",
             ref="serialMaster/README.md:84-86"),
        Fact("The rest handler in the firmware calls pwm.shutServos() and the firmware then echoes the command "
             "token", source="upstream_code", ref="src/reaction.h:498-512"),
        Fact("Lowercase serial commands are terminated by a newline", source="upstream_code", ref="src/io.h:21"),
        Fact("The firmware echoes the command token after the reply (postures and other tokens confirm completion "
             "that way)", source="upstream_code", ref="src/reaction.h:511-512"),
        Fact("The serial monitor is set to no line ending at 115200 baud", source="vendor_doc", ref="README.md:149"),
        Fact("The Python API opens the serial port with Communication(p, 115200, 1)", source="upstream_code",
             ref="serialMaster/ardSerial.py:725"),
    ]
    safe_state = "the robot is put down and its servos are shut down by the 'd' rest command"

    @read("identity", type="object",
          properties={"model": Field("string", description="Model name printed by the firmware"),
                      "firmware": Field("string", description="Firmware version string printed by the firmware")},
          description="Model and firmware identity read with the '?' serial query")
    def identity(self):
        lines = self._exchange("?", "?")
        if len(lines) < 2:
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the '?' reply has fewer than two lines (model and firmware)")
        return {"model": lines[-2], "firmware": lines[-1]}

    @read("orientation", type="object",
          properties={"pitch_deg": Field("number", unit="deg", description="Pitch angle in degrees"),
                      "roll_deg": Field("number", unit="deg", description="Roll angle in degrees")},
          description="Pitch and roll read with the 'v' serial query")
    def orientation(self):
        lines = self._exchange("v", "v")
        for line in reversed(lines):
            columns = line.replace(",", " ").split()
            if len(columns) < 2:
                continue
            try:
                pitch, roll = float(columns[0]), float(columns[1])
            except ValueError:
                continue
            return {"pitch_deg": pitch, "roll_deg": roll}
        raise DriverFailed("MHS.DEVICE.FAULTED", "the 'v' reply has no line with pitch and roll")

    @read("joint_angles_deg", type="array", items="integer", length=16, unit="deg",
          description="Current joint angles in degrees, read with the 'j' serial query")
    def joint_angles_deg(self):
        lines = self._exchange("j", "j")
        for line in reversed(lines):
            columns = [item.strip() for item in line.split(",")]
            if len(columns) < 16 or not all(item for item in columns[:16]):
                continue
            try:
                angles = [int(item) for item in columns[:16]]
            except ValueError:
                continue
            return angles
        raise DriverFailed("MHS.DEVICE.FAULTED", "the 'j' reply has no line with 16 joint angles")

    @action(name="x-cap.petoicamp.rest.v1", safe_state=True,
            description="Put the robot down and shut its servos down (the 'd' serial command)",
            output={"resting": Field("boolean", description="True once the rest command was sent")})
    def rest(self):
        self.native.Send_data(b"d\n")
        return {"resting": True}

    @estop
    def stop(self):
        self.native.Send_data(b"d\n")

    def teardown(self) -> None:
        if self.native is not None:
            self.native.Close_Engine()

    def _exchange(self, command: str, echo: str) -> list[str]:
        """Send one newline-terminated token and collect the reply lines up to the firmware's echo."""
        self.native.Send_data((command + "\n").encode("ascii"))
        lines: list[str] = []
        for _ in range(_REPLY_LINES):
            raw = self.native.Read_Line()
            if not raw:
                raise DriverFailed("MHS.DEVICE.FAULTED", f"the robot did not answer the {command!r} command")
            line = raw.decode("iso-8859-1").strip()
            if line == echo:
                return lines
            if line:
                lines.append(line)
        raise DriverFailed("MHS.DEVICE.FAULTED",
                           f"the robot did not echo {echo!r} within {_REPLY_LINES} reply lines")
