"""OpenMHS driver for gh.mattgbiz/velmex-xyz-stagecontrol-python: a Velmex VXM XYZ stage.

The clone is one module, ``XYZMotion.py``, whose ``VXM`` class (line 27) drives a Velmex VXM controller over a serial
line.  The card proposes a ``SerialDriver`` (family ``serial``, decision ``family-config``), but every command is
assembled from a prefix and a run-time number (``'E,C,S1M' + str(Speed) + ',R'``, lines 156-167, 171-195, 201-215),
so a command table cannot reproduce the bytes.  This package is a direct Driver over ``XYZMotion:VXM``
(DEVIATION FROM THE CARD, recorded in RESULT.json).

* reads: the X/Y/Z position in millimetres (``getPosition``, lines 84-94) and the last velocity this driver commanded
  on each axis; the clone has no velocity query, so the velocity state is the value the driver wrote, not a read-back;
* write: each axis velocity in steps/s (``setVelocity``, lines 152-167), bounded by the range the clone states on
  line 155;
* actions: home the requested axes, all three by default (``home``, lines 37-44), and move to an absolute X/Y/Z
  position in millimetres (``cap.motion.cartesian_pose.v1``), which the driver performs by reading the current
  position and issuing the upstream relative ``move_mm`` move (lines 185-199);
* BLOCKED on the stop path: the whole class (lines 27-220) has no stop, abort, halt or disable method, and the module
  performs serial and motion I/O at import (lines 224-236).  No honest ``@estop`` can be written and the package
  cannot pass the acceptance gate at hardware R1 (DRV-012); RESULT.json records the block.

Every Fact cites a line of the clone at the pinned commit (2e60447742855950c701d5627ee4c232407d633c).  This package
is model-authored and unreviewed: it is checked on the fake backend only and never ran on hardware.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read, write

SOURCE = "XYZMotion.py"

#: The three axes the class accepts (lines 85, 154, 172, 186, 202).
AXES = ("X", "Y", "Z")

#: One motor step is 0.0050 mm: stepsTomm = 0.0050 and mmToSteps = 1/0.0050 (lines 20-21).
STEPS_TO_MM = 0.0050

#: The constructor writes defaultVelocity = 2000 steps/s to every axis (lines 19 and 33-35).
DEFAULT_VELOCITY = 2000


class VelmexVxm(Driver):
    device_id = "velmex-vxm"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R1"
    native = "XYZMotion:VXM"
    backends = {"fake": ".fake:FakeVxm"}
    vendor, model = "Velmex", "VXM controller with an XYZ stage"
    display_name = "Velmex VXM XYZ stage"
    tags = ["velmex", "vxm", "xyz stage", "stepper", "serial", "motion", "positioner"]
    facts = [
        Fact("XYZMotion.py is a VXM controller driver for a Velmex XYZ stage",
             source="upstream_code", ref=f"{SOURCE}:1-8"),
        Fact("The module fixes port = 'COM4' and baud = 9600 and gives the serial read a maxWaitTime timeout",
             source="upstream_code", ref=f"{SOURCE}:13-15"),
        Fact("defaultVelocity is 2000 steps/s (the comment says the manual calls 2000 steps/second good)",
             source="upstream_code", ref=f"{SOURCE}:19"),
        Fact("One motor step is 0.0050 mm: stepsTomm = 0.0050 and mmToSteps = 1/0.0050",
             source="upstream_code", ref=f"{SOURCE}:20-21"),
        Fact("The constructor opens Serial(port, baud, timeout=maxWaitTime) and writes defaultVelocity to the X, Y "
             "and Z axes with setVelocity", source="upstream_code", ref=f"{SOURCE}:29-35"),
        Fact("home() calls moveToZero for X, Y and Z with a one-second sleep between them and then reads all "
             "positions", source="upstream_code", ref=f"{SOURCE}:37-44"),
        Fact("sendcmd appends a carriage return and writes the bytes; getresp reads one line and decodes it",
             source="upstream_code", ref=f"{SOURCE}:48-64"),
        Fact("waitReady sends 'V' and repeats until the reply is 'R'; the comment says B is busy, R is ready, J is "
             "jog/slew mode and b is jogging", source="upstream_code", ref=f"{SOURCE}:66-79"),
        Fact("getPosition asserts the axis is X, Y or Z, reads the reply as [axis, sign, seven digits], applies the "
             "sign and converts the steps to millimetres with 0.0050", source="upstream_code", ref=f"{SOURCE}:84-94"),
        Fact("getAllPositions reads X, Y and Z in sequence and converts each reply by 0.0050 mm per step; the English "
             "Y value divides by 24.4 while getPosition divides by 25.4", source="upstream_code",
             ref=f"{SOURCE}:116-141"),
        Fact("setVelocity asserts Speed > 0 and Speed <= 6000 and comments that the motor speed must be in range "
             "1-6000", source="upstream_code", ref=f"{SOURCE}:155"),
        Fact("setVelocity builds 'E,C,S1M<speed>,R', 'E,C,S2M<speed>,R' or 'E,C,S3M<speed>,R' for X, Y or Z",
             source="upstream_code", ref=f"{SOURCE}:156-167"),
        Fact("moveToZero builds 'E,C,IA1M0,R', 'E,C,IA2M0,R' or 'E,C,IA3M0,R' and then waits for ready",
             source="upstream_code", ref=f"{SOURCE}:171-183"),
        Fact("move_mm converts millimetres to steps with mmToSteps, builds 'E,C,I1M<steps>,R', 'E,C,I2M<steps>,R' or "
             "'E,C,I3M<steps>,R' and then waits for ready", source="upstream_code", ref=f"{SOURCE}:185-199"),
        Fact("move_in converts inches to steps with inTomm * mmToSteps and builds the same I1M/I2M/I3M command",
             source="upstream_code", ref=f"{SOURCE}:201-215"),
        Fact("The VXM class defines __init__, home, sendcmd, getresp, waitReady, getPosition, getAllPositions, "
             "setVelocity, moveToZero, move_mm, move_in and __del__ (which closes the port), and no stop, abort, "
             "halt or disable method", source="upstream_code", ref=f"{SOURCE}:27-220"),
        Fact("The module creates XYZ = VXM(port, baud, maxWaitTime), homes it, moves each axis and deletes it, so "
             "importing XYZMotion performs serial and motion I/O", source="upstream_code", ref=f"{SOURCE}:224-236"),
        Fact("The README says the repository has the early coding used to communicate with the VXM controller from "
             "Velmex", source="vendor_doc", ref="README.md:2"),
    ]
    safe_state = ("unreachable through this library: XYZMotion.py defines no stop, abort, halt or disable method, "
                  "so a latched e-stop cannot stop a move in flight (RESULT.json)")

    # -- reads ---------------------------------------------------------------------------------------------------
    @read("position", type="object",
          properties={"x": Field("number", unit="mm", description="Current X-axis position in millimetres"),
                      "y": Field("number", unit="mm", description="Current Y-axis position in millimetres"),
                      "z": Field("number", unit="mm", description="Current Z-axis position in millimetres")},
          description="Current X/Y/Z position in millimetres, read with getPosition (0.0050 mm per step)")
    def position(self):
        return {axis.lower(): float(self.native.getPosition(axis)) for axis in AXES}

    @read("velocity_x", unit="steps/s",
          description="Velocity this driver last commanded on the X axis; the clone has no velocity query")
    def velocity_x(self):
        return self._velocity["X"]

    @read("velocity_y", unit="steps/s",
          description="Velocity this driver last commanded on the Y axis; the clone has no velocity query")
    def velocity_y(self):
        return self._velocity["Y"]

    @read("velocity_z", unit="steps/s",
          description="Velocity this driver last commanded on the Z axis; the clone has no velocity query")
    def velocity_z(self):
        return self._velocity["Z"]

    # -- writes: the velocity of each axis -----------------------------------------------------------------------
    @write("velocity_x", unit="steps/s", description="Velocity of the X axis in steps per second (setVelocity)",
           limit=Limit(min=1, max=6000, source="upstream_code", ref=f"{SOURCE}:155",
                       reason="setVelocity asserts Speed > 0 and Speed <= 6000; the comment states the motor speed "
                              "range 1-6000"))
    def set_velocity_x(self, value):
        self.native.setVelocity("X", value)
        self._velocity["X"] = float(value)
        return self._velocity["X"]

    @write("velocity_y", unit="steps/s", description="Velocity of the Y axis in steps per second (setVelocity)",
           limit=Limit(min=1, max=6000, source="upstream_code", ref=f"{SOURCE}:155",
                       reason="setVelocity asserts Speed > 0 and Speed <= 6000; the comment states the motor speed "
                              "range 1-6000"))
    def set_velocity_y(self, value):
        self.native.setVelocity("Y", value)
        self._velocity["Y"] = float(value)
        return self._velocity["Y"]

    @write("velocity_z", unit="steps/s", description="Velocity of the Z axis in steps per second (setVelocity)",
           limit=Limit(min=1, max=6000, source="upstream_code", ref=f"{SOURCE}:155",
                       reason="setVelocity asserts Speed > 0 and Speed <= 6000; the comment states the motor speed "
                              "range 1-6000"))
    def set_velocity_z(self, value):
        self.native.setVelocity("Z", value)
        self._velocity["Z"] = float(value)
        return self._velocity["Z"]

    # -- actions -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.home.v1",
            input={"axes": Field("array", description="Axes to home, X, Y or Z; an omitted list homes all three",
                                 items=Field("string", description="Axis name: X, Y or Z", enum=list(AXES)))},
            description="Home the requested axes (all three when the list is omitted) with the native home() or, "
                        "for a subset, with moveToZero on each axis; both wait for the controller to report ready")
    def home(self, axes=None):
        if axes is None:
            self.native.home()
            wanted = list(AXES)
        else:
            requested = {str(axis).upper() for axis in axes}
            wanted = [axis for axis in AXES if axis in requested]
            if not wanted:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "no axis selected: name X, Y or Z, or omit the list to home all three")
            for axis in wanted:
                self.check_cancelled()
                self.native.moveToZero(axis)
        return {"homed": True, "axes": wanted}

    @action(cap="cap.motion.cartesian_pose.v1",
            input={"position": Field("object",
                                     description="Target X/Y/Z position in millimetres; home the stage first")},
            limits={
                "position.x": Limit.operator_required(
                    "the clone states no X-axis travel or soft limit: it only converts steps to millimetres "
                    f"({SOURCE}:20-21), so the site supplies the envelope"),
                "position.y": Limit.operator_required(
                    "the clone states no Y-axis travel or soft limit: it only converts steps to millimetres "
                    f"({SOURCE}:20-21), so the site supplies the envelope"),
                "position.z": Limit.operator_required(
                    "the clone states no Z-axis travel or soft limit: it only converts steps to millimetres "
                    f"({SOURCE}:20-21), so the site supplies the envelope"),
            },
            description="Move to an absolute X/Y/Z position in millimetres: read each current position, issue the "
                        "upstream relative move_mm for the difference and read the positions back")
    def move_to_position(self, position):
        target = {"X": float(position["x"]), "Y": float(position["y"]), "Z": float(position["z"])}
        for axis in AXES:
            self.check_cancelled()
            current = float(self.native.getPosition(axis))
            delta = target[axis] - current
            if delta:
                self.native.move_mm(axis, delta)
        final = {axis: float(self.native.getPosition(axis)) for axis in AXES}
        reached = all(abs(final[axis] - target[axis]) <= STEPS_TO_MM for axis in AXES)
        return {"reached": reached,
                "position": {"x": final["X"], "y": final["Y"], "z": final["Z"]},
                "tolerance_mm": STEPS_TO_MM}

    # -- lifecycle -----------------------------------------------------------------------------------------------
    def setup(self):
        """The constructor of the upstream class writes defaultVelocity to every axis (lines 19, 33-35)."""
        self._velocity = {axis: float(DEFAULT_VELOCITY) for axis in AXES}
