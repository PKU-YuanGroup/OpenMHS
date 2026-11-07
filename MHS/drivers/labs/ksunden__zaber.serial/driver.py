"""OpenMHS driver for gh.ksunden/zaber.serial: one axis of a Zaber device over the ASCII serial protocol.

A direct Driver (decorated methods) over ``zaber.serial.ascii:AsciiAxis``.  The card's entry symbols also include
the binary protocol classes, but this package binds the ASCII entry class named by ``native``; the binary
``BinaryDevice``/``BinarySerial`` classes are not covered (see RESULT.json notes).  The upstream builds each wire
command inside the class (``'/1 0 move abs 1000'``, ``zaber/serial/ascii.py:126``), so the driver calls the upstream
methods and never assembles a command line.

* reads: the current absolute position in microsteps and the axis status ("BUSY" or "IDLE");
* actions: five extensions for home, absolute, relative and continuous motion and stop.  The catalogue motion
  classes fix positions in radians (``cap.motion.joint_position.v1``, ``cap.motion.joint_velocity.v1``), while the
  serial protocol addresses the axis in integer microsteps and names no calibration from microsteps to an SI
  length.  The catalogue home and stop classes also carry optional numeric fields (``speed_scale``,
  ``deceleration``) that ``AsciiAxis`` has no method to apply; serving those classes would advertise inputs that
  can never reach the device.  The extensions keep the native unit and the native stop is the declared safe-state
  action;
* limits: the clone states no travel range, speed range or force limit.  Every numeric motion input is therefore
  ``Limit.operator_required``: every call is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range
  of the installed stage (``site-limits.example.json`` is an example overlay, not a statement about any device);
* the e-stop is the native stop command (``AsciiAxis.stop``, ``zaber/serial/ascii.py:181-197``).

Every Fact cites a line of the clone at the pinned commit 4bd9e1103f6a057fd376edcdf574251637465fba.  This package
is model-authored and unreviewed: it is checked on the fake backend only, claims no hardware run and no
MHS-Device level.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class ZaberAxis(Driver):
    device_id = "zaber-axis"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "zaber.serial.ascii:AsciiAxis"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAsciiAxis"}
    vendor, model = "Zaber Technologies", "Zaber device over the ASCII serial protocol"
    display_name = "Zaber serial axis (zaber.serial.ascii.AsciiAxis)"
    tags = ["zaber", "serial", "ascii", "motion", "axis"]
    facts = [
        Fact("The clone is a library for controlling Zaber devices over a serial port", source="vendor_doc",
             ref="README.rst:4"),
        Fact("AsciiAxis represents one axis of an ASCII device; the axis number is 1-9", source="upstream_code",
             ref="zaber/serial/ascii.py:22"),
        Fact("AsciiAxis.send sends an AsciiCommand through the parent device and checks that the reply came from "
             "this axis", source="upstream_code", ref="zaber/serial/ascii.py:82-90"),
        Fact("home() sends the 'home' command and then polls the axis until it is idle", source="upstream_code",
             ref="zaber/serial/ascii.py:92-105"),
        Fact("move_abs(position) sends 'move abs <position>' where position is an integer in microsteps, then polls "
             "until idle", source="upstream_code", ref="zaber/serial/ascii.py:107-128"),
        Fact("move_rel(distance) sends 'move rel <distance>' where distance is an integer number of microsteps, then "
             "polls until idle", source="upstream_code", ref="zaber/serial/ascii.py:130-151"),
        Fact("move_vel(speed) sends 'move vel <speed>' with an integer speed and returns immediately unless blocking "
             "is true", source="upstream_code", ref="zaber/serial/ascii.py:153-179"),
        Fact("stop() sends the 'stop' command and polls until idle; the stop command pre-empts a movement command",
             source="upstream_code", ref="zaber/serial/ascii.py:181-197"),
        Fact("get_status() returns the reply device status, which is either 'BUSY' or 'IDLE'", source="upstream_code",
             ref="zaber/serial/ascii.py:199-210"),
        Fact("get_position() sends 'get pos' and returns the reply data, described as the absolute position in "
             "microsteps", source="upstream_code", ref="zaber/serial/ascii.py:212-218"),
        Fact("poll_until_idle() blocks until the device reports that the axis is idle", source="upstream_code",
             ref="zaber/serial/ascii.py:220-231"),
        Fact("AsciiDevice.address is 1-99 and axis(number) returns a new AsciiAxis for an axis number of 1-9",
             source="upstream_code", ref="zaber/serial/ascii.py:407-434"),
        Fact("AsciiSerial(port, ...) opens the serial port when the constructor is called", source="upstream_code",
             ref="zaber/serial/ascii.py:839-855"),
        Fact("AsciiCommand.encode builds the protocol frame '/<device address> <axis number> [<message id>] <data>' "
             "terminated by CRLF", source="upstream_code", ref="zaber/serial/ascii.py:347-376"),
    ]
    safe_state = "axis motion stopped by the native stop command"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("position", type="integer", unit="1",
          description="Current absolute axis position in microsteps (the device's native position count)")
    def position(self):
        # AsciiAxis.get_position returns the reply data as text; the docstring describes it as an integer.
        return int(self.native.get_position())

    @read("status", type="string", description="Axis status reported by the device: 'BUSY' or 'IDLE'")
    def status(self):
        return self.native.get_status()

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.ksunden.home.v1",
            description="Send the native home command and wait until the axis reports idle",
            output={"homed": Field("boolean", description="True when the axis reports IDLE after homing")})
    def home_axis(self):
        self.native.home()
        return {"homed": self.native.get_status() == "IDLE"}

    @action(name="x-cap.ksunden.move_abs.v1",
            description="Move the axis to an absolute native position in microsteps and wait until idle",
            input={"position": Field(
                "integer", unit="1", description="Absolute target position in microsteps (the native count)",
                limit=Limit.operator_required(
                    "the clone states no travel range for the axis (move_abs names only integer microsteps); the "
                    "site supplies the travel of the installed stage"))},
            output={"position": Field(
                "integer", unit="1", description="Absolute position in microsteps reported after the move")})
    def move_abs(self, position):
        self.native.move_abs(position)
        return {"position": int(self.native.get_position())}

    @action(name="x-cap.ksunden.move_rel.v1",
            description="Move the axis by a relative distance in microsteps and wait until idle",
            input={"distance": Field(
                "integer", unit="1", description="Relative distance in microsteps (the native count)",
                limit=Limit.operator_required(
                    "the clone states no travel range for the axis (move_rel names only integer microsteps); the "
                    "site supplies the travel of the installed stage"))},
            output={"position": Field(
                "integer", unit="1", description="Absolute position in microsteps reported after the move")})
    def move_rel(self, distance):
        self.native.move_rel(distance)
        return {"position": int(self.native.get_position())}

    @action(name="x-cap.ksunden.move_vel.v1",
            description="Start continuous motion at a native speed; call stop to end it",
            input={"speed": Field(
                "integer", unit="1", description="Native speed value of the device; the clone names no speed unit",
                limit=Limit.operator_required(
                    "the clone states no speed range and no unit for move_vel (it names only an integer speed); the "
                    "site supplies the safe speed of the installed stage"))},
            output={
                "moving": Field("boolean", description="True when the axis reports BUSY after the command"),
                "speed": Field("integer", unit="1", description="Native speed value that was sent"),
            })
    def move_vel(self, speed):
        self.native.move_vel(speed)
        return {"moving": self.native.get_status() == "BUSY", "speed": speed}

    @action(name="x-cap.ksunden.stop.v1", safe_state=True,
            description="Stop the axis with the native stop command and wait until it reports idle",
            output={"stopped": Field("boolean", description="True when the axis reports IDLE after the stop")})
    def stop_axis(self):
        self.native.stop()
        return {"stopped": self.native.get_status() == "IDLE"}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then calls this."""
        self.native.stop()
