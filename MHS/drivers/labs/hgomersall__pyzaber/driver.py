"""OpenMHS driver for gh.hgomersall/pyzaber: Zaber multiaxis linear slides over a framed serial protocol.

The card proposes a ``SerialDriver`` (family ``serial``, decision ``family-config``), but the clone does not send
text lines: ``serial_connection.send_command`` writes a ``(device_id, command, data)`` frame through ``struct``
(``pyzaber/serial_connection.py:144-150``) and ``async_serial.write`` packs it (``pyzaber/serial_connection.py:507-510``).
The commands are numbers looked up in the clone's tables (home 1, return_current_position 60, absolute 20 and stop 23;
``pyzaber/zaber_device.py:10-29``).  A command table cannot reproduce those frames, so this package is a direct
``Driver`` over the card's entry symbol ``pyzaber.linear_slides:multiaxis_linear_slides`` (DEVIATION FROM THE CARD,
recorded in RESULT.json).

* reads: the x, y and z positions in millimetres (``get_current_position``, ``pyzaber/zaber_multidevice.py:199-210``);
* action ``cap.motion.cartesian_pose.v1``: an absolute X/Y/Z move in millimetres, using the upstream blocking
  ``move_absolute`` (``pyzaber/zaber_multidevice.py:169-178``), then reading the positions back;
* action ``x-cap.hgomersall.home_axes.v1``: the native home command to all three axes (command 1); it is an
  extension because ``cap.motion.home.v1`` advertises a numeric ``speed_scale`` the native home cannot honour;
* action ``x-cap.hgomersall.stop_motion.v1``: the native e-stop, also the safe-state action; it is an extension
  because ``cap.motion.stop.v1`` advertises a numeric ``deceleration`` the native stop cannot honour;
* the e-stop is the upstream ``emergency_stop``, which broadcasts command 23 to device 0 without waiting
  (``pyzaber/zaber_device.py:389-405`` and ``932-935``).

No text file of the clone states the travel of an axis, so every numeric position input is
``Limit.operator_required``: the site supplies the workspace in ``site-limits.example.json`` and, until it does,
every move is refused ``MHS.SAFETY.LIMITS_UNSET``.

The upstream modules are Python 2 (``from Queue import Queue`` and ``print`` statements), so this package ships no
hardware backend; it is checked on the fake backend only.  Every Fact cites a line of the clone at the pinned commit
``1a3f1e712f3d5bb3dab8512cdfeda9d21244b374``.  This package is model-authored and unreviewed: ``reviewed_by`` is
null, no hardware was attached, and no MHS-Device level is claimed.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The clone files the Facts cite (paths from the clone root).
LINEAR = "pyzaber/linear_slides.py"
DEVICE = "pyzaber/zaber_device.py"
MULTI = "pyzaber/zaber_multidevice.py"
SERIAL = "pyzaber/serial_connection.py"
DUMMY = "pyzaber/dummy_linear_slides.py"

#: The axis names of the clone's multiaxis example (linear_slides.py:123); this package serves that configuration.
AXES = ("x", "y", "z")

#: The same reason on each axis: the clone states no travel, so only the site can bound it.
NO_TRAVEL = ("no text file of the clone states the travel of a linear axis; the stage mechanics, its end stops and "
             "the process set the envelope, so the site supplies it")


class Pyzaber(Driver):
    device_id = "pyzaber"
    device_kind = "robot.arm"
    mode = "hardware"
    #: The device moves a three-axis gantry: real mechanical motion is at least R2 (MHS/spec/04-safety.md:68),
    #: above the card's R1 floor.  The safe-state action below is the independent stop SAFE-045 asks for.
    risk = "R2"
    native = "pyzaber.linear_slides:multiaxis_linear_slides"
    backends = {"fake": ".fake:FakePyzaber"}
    vendor, model = "Zaber Technologies", "multiaxis linear slides"
    display_name = "Zaber multiaxis linear slides (pyzaber)"
    tags = ["zaber", "linear slide", "gantry", "multiaxis", "serial", "motion", "positioner"]
    facts = [
        Fact("The clone's linear units are all with respect to 1 mm: mm = 1, um = 1e-3 and inches = 25.4",
             source="upstream_code", ref=f"{LINEAR}:4-10"),
        Fact("multiaxis_linear_slides is the module's multiaxis linear-slide class",
             source="upstream_code", ref=f"{LINEAR}:53"),
        Fact("The class takes a connection and a devices mapping and gives zaber_multidevice units_per_step = "
             "mm_per_rev / steps_per_rev with move_units = the units argument",
             source="upstream_code", ref=f"{LINEAR}:73-92"),
        Fact("The clone's multiaxis example names the axes x, y and z on device numbers 1, 2 and 3",
             source="upstream_code", ref=f"{LINEAR}:121-125"),
        Fact("Commands are looked up by name in the base_commands and move_commands tables: home is 1, "
             "return_current_position is 60, absolute is 20 and stop is 23",
             source="upstream_code", ref=f"{DEVICE}:10-29"),
        Fact("The class exposes commands dynamically through __getattr__: a base command name calls "
             "enqueue_base_command, move_<name> calls move() and get_<setting> calls get()",
             source="upstream_code", ref=f"{DEVICE}:163-196"),
        Fact("get_current_position returns each device's current position divided by its microsteps_per_unit",
             source="upstream_code", ref=f"{MULTI}:199-210"),
        Fact("A blocking move converts each axis position to microsteps with microsteps_per_unit and calls that "
             "device's move() with blocking=True",
             source="upstream_code", ref=f"{MULTI}:169-178"),
        Fact("emergency_stop broadcasts the stop command to every device immediately",
             source="upstream_code", ref=f"{DEVICE}:389-405"),
        Fact("The emergency branch of do_now sends (0, command, data) through the connection without waiting for "
             "a reply",
             source="upstream_code", ref=f"{DEVICE}:932-935"),
        Fact("A command is a (device_id, command, data) frame written through serial_connection.send_command",
             source="upstream_code", ref=f"{SERIAL}:144-150"),
        Fact("The clone's dummy simulator implements get_current_position and move_absolute but no home or "
             "emergency_stop, so it cannot serve this driver's stop path",
             source="upstream_code", ref=f"{DUMMY}:9-29"),
    ]
    safe_state = ("all axes stopped by the native emergency-stop broadcast (command 23 sent to device 0); no motion "
                  "restarts until a new command")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("x_mm", unit="mm", description="X-axis position reported by the stage")
    def x_mm(self):
        return float(self.native.get_current_position()["x"])

    @read("y_mm", unit="mm", description="Y-axis position reported by the stage")
    def y_mm(self):
        return float(self.native.get_current_position()["y"])

    @read("z_mm", unit="mm", description="Z-axis position reported by the stage")
    def z_mm(self):
        return float(self.native.get_current_position()["z"])

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.hgomersall.home_axes.v1",
            description="Home all three axes with the native home command (command 1); the clone's example homes "
                        "x, y and z in turn",
            output={"homed": Field("boolean", description="True once the native home command was sent"),
                    "axes": Field("array", items=Field("string", description="Axis name"),
                                  description="Axes homed, x, y and z")})
    def home(self):
        self.native.home()
        return {"homed": True, "axes": list(AXES)}

    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field(
                "object", description="Target X/Y/Z position in millimetres; home the stage first",
                properties={
                    "x": Field("number", unit="mm", description="Absolute target of the x axis",
                               limit=Limit.operator_required(NO_TRAVEL)),
                    "y": Field("number", unit="mm", description="Absolute target of the y axis",
                               limit=Limit.operator_required(NO_TRAVEL)),
                    "z": Field("number", unit="mm", description="Absolute target of the z axis",
                               limit=Limit.operator_required(NO_TRAVEL)),
                })},
            description="Move the stage to absolute X/Y/Z positions in millimetres: the upstream blocking move "
                        "waits for each axis, then the driver reads the positions back")
    def move_to_position(self, position):
        target = {axis: float(position[axis]) for axis in AXES}
        self.native.move_absolute(target, blocking=True)
        current = self.native.get_current_position()
        return {"reached": True, "position": {axis: float(current[axis]) for axis in AXES}}

    @action(name="x-cap.hgomersall.stop_motion.v1", safe_state=True,
            description="Stop every axis with the native emergency-stop broadcast (command 23 to device 0); the "
                        "safe state, and it takes no input",
            output={"stopped": Field("boolean",
                                     description="True once the native emergency-stop broadcast was sent")})
    def stop_motion(self):
        self.native.emergency_stop()
        return {"stopped": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop
    def emergency_stop(self):
        """The native stop: the runtime latches first, then broadcasts command 23 to every device."""
        self.native.emergency_stop()
