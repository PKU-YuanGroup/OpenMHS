"""OpenMHS driver for gh.mcleu/pyapt: a Thorlabs APT motion controller through its vendor DLL.

A direct Driver (decorated methods) over the upstream class PyAPT.PyAPT:APTMotor.  The upstream class is a ctypes
wrapper of Thorlabs' APT.dll (README.md:5, PyAPT/PyAPT.py:48-50); it is Python 2 syntax (PyAPT/PyAPT.py:20-21) and
uses ctypes.windll (PyAPT/PyAPT.py:18), so the clone cannot be imported under Python 3 and the hardware factory in
native.py is an independent Python 3 port of the same DLL calls.  The clone is parsed, never imported, by the gate.

* reads: position, connection flag, stage axis information (minimum, maximum, units, pitch), velocity parameters,
  the controller's velocity parameter limits, and the two hardware limit switch modes;
* writes: absolute position (the native mAbs), maximum velocity (setVel) and acceleration (setVelocityParameters).
  The travel range and the velocity limits are read from the controller at run time and no text file of the clone
  states a fixed number, so every numeric write is Limit.operator_required and the site supplies the bound;
* actions: a relative move, homing, and the native profiled stop as the safe-state action.  The e-stop reaches
  APT.dll MOT_StopProfiled through the upstream object's ``aptdll`` handle (PyAPT/PyAPT.py:48) and then reads the
  position.

Every Fact cites a line of the clone at the pinned commit (2d5c4c64350d70daa60c0bd49c9afd03f85bc412).  This package
is model-authored and unreviewed; it is checked on the fake backend only and claims no hardware run.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_UNIT = "1"  # the controller's stage unit: 1 is mm and 2 is degrees (APTDLLPack/APTDLLClient/APTAPI.h:82-84)

_OPERATOR_POSITION = (
    "the travel range belongs to the installed stage: getStageAxisInformation reads the minimum and maximum from the "
    "controller at run time (PyAPT/PyAPT.py:114-121) and no text file of the clone states a fixed range; the operator "
    "supplies the range in the stage unit")
_OPERATOR_VELOCITY = (
    "the maximum velocity belongs to the installed stage: getVelocityParameterLimits reads the controller's own "
    "limit at run time (PyAPT/PyAPT.py:167-172) and no text file of the clone states a fixed number; the operator "
    "supplies the ceiling in the stage unit per second")
_OPERATOR_ACCELERATION = (
    "the maximum acceleration belongs to the installed stage: getVelocityParameterLimits reads the controller's own "
    "limit at run time (PyAPT/PyAPT.py:167-172) and no text file of the clone states a fixed number; the operator "
    "supplies the ceiling in the stage unit per second squared")
_OPERATOR_DISTANCE = (
    "a relative move is bounded by the current position and the travel range of the installed stage, which the "
    "clone reads from the controller at run time (PyAPT/PyAPT.py:114-121); the operator supplies the distance range "
    "in the stage unit")


class PyAPT(Driver):
    device_id = "pyapt"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "PyAPT.PyAPT:APTMotor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAPTMotor"}
    vendor, model = "Thorlabs", "APT motion controller (PyAPT)"
    display_name = "Thorlabs APT motion controller (PyAPT)"
    tags = ["thorlabs", "apt", "motion", "stage", "ctypes", "windows"]
    facts = [
        Fact("PyAPT controls Thorlabs APT hardware from Python through APT.dll and APT.lib",
             source="vendor_doc", ref="README.md:5"),
        Fact("The README tells the user to obtain the x86 or x64 APT.dll and APT.lib and to install the Thorlabs APT "
             "software", source="vendor_doc", ref="README.md:10-12"),
        Fact("The README lists Thorlabs APT controllers including the BSC001, TDC001, LTSXXX and BBD10X",
             source="vendor_doc", ref="README.md:29-46"),
        Fact("The module imports ctypes.windll and uses Python 2 print statements, so it is Windows-only and does not "
             "parse as Python 3", source="upstream_code", ref="PyAPT/PyAPT.py:18-21"),
        Fact("The constructor loads APT.dll into self.aptdll, calls EnableEventDlg(True) and APTInit, and keeps the "
             "serial number as a c_long", source="upstream_code", ref="PyAPT/PyAPT.py:44-57"),
        Fact("initializeHardwareDevice calls InitHWDevice(serial) and sets Connected only when it returns zero",
             source="upstream_code", ref="PyAPT/PyAPT.py:89-103"),
        Fact("getPos calls MOT_GetPosition and refuses to read when the object is not Connected",
             source="upstream_code", ref="PyAPT/PyAPT.py:183-194"),
        Fact("mRel calls MOT_MoveRelativeEx with the wait flag True, and mAbs calls MOT_MoveAbsoluteEx with the wait "
             "flag True", source="upstream_code", ref="PyAPT/PyAPT.py:196-221"),
        Fact("go_home calls MOT_MoveHome with the serial number; the upstream call passes no other argument",
             source="upstream_code", ref="PyAPT/PyAPT.py:289-298"),
        Fact("getVelocityParameters reads MOT_GetVelParams and setVelocityParameters writes MOT_SetVelParams",
             source="upstream_code", ref="PyAPT/PyAPT.py:139-159"),
        Fact("getVelocityParameterLimits reads the controller's maximum acceleration and maximum velocity at run "
             "time through MOT_GetVelParamLimits", source="upstream_code", ref="PyAPT/PyAPT.py:167-172"),
        Fact("getStageAxisInformation returns the minimum position, maximum position, unit code and pitch from "
             "MOT_GetStageAxisInfo", source="upstream_code", ref="PyAPT/PyAPT.py:114-121"),
        Fact("The stage unit code is 1 for millimetres and 2 for degrees",
             source="upstream_code", ref="APTDLLPack/APTDLLClient/APTAPI.h:82-84"),
        Fact("APT.dll declares MOT_StopProfiled(long lSerialNum)",
             source="upstream_code", ref="APTDLLPack/APTDLLClient/APTAPI.h:148"),
        Fact("The vendor APT client calls MOT_StopProfiled from its StopProfiled button handler",
             source="upstream_code", ref="APTDLLPack/APTDLLClient/APTDLLClientDlg.cpp:593-599"),
        Fact("MOT_MoveHome, MOT_MoveRelativeEx and MOT_MoveAbsoluteEx take the serial number and a wait flag",
             source="upstream_code", ref="APTDLLPack/APTDLLClient/APTAPI.h:144-146"),
        Fact("cleanUpAPT calls APTCleanUp and sets Connected to False", source="upstream_code",
             ref="PyAPT/PyAPT.py:309-316"),
    ]
    safe_state = "stage motion stopped with the native APT profiled stop (MOT_StopProfiled)"

    # -- reads --------------------------------------------------------------------------------------------------
    @read("position", unit=_UNIT,
          description="Stage position in the controller's stage unit: millimetres when stage_units is 1 and "
                      "degrees when it is 2")
    def position(self):
        return float(self.native.getPos())

    @read("connected", type="boolean", description="True while the APT controller is initialised")
    def connected(self):
        return bool(self.native.Connected)

    @read("stage_minimum", unit=_UNIT,
          description="Minimum position of the configured stage, read from the controller")
    def stage_minimum(self):
        return float(self.native.getStageAxisInformation()[0])

    @read("stage_maximum", unit=_UNIT,
          description="Maximum position of the configured stage, read from the controller")
    def stage_maximum(self):
        return float(self.native.getStageAxisInformation()[1])

    @read("stage_units", type="integer",
          description="Stage unit code reported by the controller: 1 for millimetres, 2 for degrees")
    def stage_units(self):
        return int(self.native.getStageAxisInformation()[2])

    @read("pitch", unit=_UNIT,
          description="Lead-screw pitch reported by the controller, in the stage unit")
    def pitch(self):
        return float(self.native.getStageAxisInformation()[3])

    @read("minimum_velocity", unit=_UNIT,
          description="Configured minimum velocity in stage units per second")
    def minimum_velocity(self):
        return float(self.native.getVelocityParameters()[0])

    @read("acceleration", unit=_UNIT,
          description="Configured acceleration in stage units per second squared")
    def acceleration(self):
        return float(self.native.getVelocityParameters()[1])

    @read("maximum_velocity", unit=_UNIT,
          description="Configured maximum velocity in stage units per second")
    def maximum_velocity(self):
        return float(self.native.getVelocityParameters()[2])

    @read("maximum_acceleration_limit", unit=_UNIT,
          description="Maximum acceleration the controller accepts, read from the controller")
    def maximum_acceleration_limit(self):
        return float(self.native.getVelocityParameterLimits()[0])

    @read("maximum_velocity_limit", unit=_UNIT,
          description="Maximum velocity the controller accepts, read from the controller")
    def maximum_velocity_limit(self):
        return float(self.native.getVelocityParameterLimits()[1])

    @read("reverse_limit_switch", type="integer",
          description="Reverse hardware limit-switch mode reported by the controller")
    def reverse_limit_switch(self):
        return int(self.native.getHardwareLimitSwitches()[0])

    @read("forward_limit_switch", type="integer",
          description="Forward hardware limit-switch mode reported by the controller")
    def forward_limit_switch(self):
        return int(self.native.getHardwareLimitSwitches()[1])

    # -- writes -------------------------------------------------------------------------------------------------
    @write("position", unit=_UNIT,
           description="Absolute position target in the stage unit; mAbs waits for the move and the driver returns "
                       "the position the controller reports afterwards",
           limit=Limit.operator_required(_OPERATOR_POSITION))
    def set_position(self, value):
        self.native.mAbs(value)
        return float(self.native.getPos())

    @write("maximum_velocity", unit=_UNIT,
           description="Maximum velocity in stage units per second; the configured acceleration is kept",
           limit=Limit.operator_required(_OPERATOR_VELOCITY))
    def set_maximum_velocity(self, value):
        self.native.setVel(value)
        return float(self.native.getVelocityParameters()[2])

    @write("acceleration", unit=_UNIT,
           description="Acceleration in stage units per second squared; the configured maximum velocity is kept",
           limit=Limit.operator_required(_OPERATOR_ACCELERATION))
    def set_acceleration(self, value):
        minimum_velocity, _acceleration, maximum_velocity = self.native.getVelocityParameters()
        self.native.setVelocityParameters(minimum_velocity, value, maximum_velocity)
        return float(self.native.getVelocityParameters()[1])

    # -- actions ------------------------------------------------------------------------------------------------
    @action(name="x-cap.mcleu.move_relative.v1",
            description="Move the stage relative to its current position; mRel waits for the move and the driver "
                        "returns the position the controller reports afterwards",
            input={"distance": Field("number", unit=_UNIT,
                                     description="Relative travel in the controller's stage unit; positive is "
                                                 "forward",
                                     limit=Limit.operator_required(_OPERATOR_DISTANCE))},
            output={"position": Field("number", unit=_UNIT,
                                      description="Position the controller reports after the move")})
    def move_relative(self, distance):
        self.native.mRel(distance)
        return {"position": float(self.native.getPos())}

    @action(name="x-cap.mcleu.home.v1",
            description="Home the stage with the controller's configured homing parameters; go_home waits for the "
                        "move and the driver returns the position the controller reports afterwards",
            output={"position": Field("number", unit=_UNIT,
                                      description="Position the controller reports after homing")})
    def home(self):
        self.native.go_home()
        return {"position": float(self.native.getPos())}

    @action(name="x-cap.mcleu.stop.v1", safe_state=True,
            description="Stop stage motion with the native APT profiled stop (MOT_StopProfiled); it takes no input",
            output={"stopped": Field("boolean", description="True once the native profiled stop was sent"),
                    "position": Field("number", unit=_UNIT,
                                      description="Position the controller reports after the stop")})
    def stop_stage(self):
        return {"stopped": True, "position": self._native_stop()}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="MOT_StopProfiled")
    def emergency_stop(self):
        """The native stop: MOT_StopProfiled through the upstream object's APT.dll handle, then read the position."""
        self._native_stop()

    def _native_stop(self):
        self.native.aptdll.MOT_StopProfiled(self.native.SerialNum)
        return float(self.native.getPos())

    def teardown(self):
        """Release the APT object with the upstream cleanUpAPT (PyAPT/PyAPT.py:309-316)."""
        self.native.cleanUpAPT()
