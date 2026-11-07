"""OpenMHS driver for gh.freespace/pyapt: a Thorlabs APT stage controller over pylibftdi.

A direct Driver (decorated methods) over the upstream class pyAPT.controller:Controller.  Controller owns the FTDI
transport and speaks the binary APT messages; MTS50, PRM1 and LTS300 are thin subclasses that set only the stage
scales and the travel range of that stage (pyAPT/mts50.py:4-31, pyAPT/prm1.py:4-35, pyAPT/lts300.py:4-31).  The
hardware factory in native.py builds the subclass selected by the deployment option ``stage`` and returns it as a
Controller; the fake backend never imports the clone.

* reads: position, velocity, moving/homed/limit-switch flags, the short status line, raw status bits, the software
  travel-limit switch, and the configured minimum velocity, maximum velocity and acceleration;
* writes: absolute position (the native goto), maximum velocity, acceleration, and the software travel-limit switch.
  A write's unit is the stage unit: millimetres for MTS50 and LTS300, degrees for PRM1.  The clone states a range per
  model (pyAPT/mts50.py:31, pyAPT/lts300.py:31, pyAPT/prm1.py:35) but not one range for the generic Controller, and its
  README warns that the quoted stage limits often differ from reality (README.md:15-19); position, velocity,
  acceleration and relative distance are therefore ``Limit.operator_required`` and the site supplies the bounds of
  the installed stage (site-limits.example.json is an example overlay);
* actions: home the axis (cap.motion.home.v1), move relative to the current position
  (x-cap.freespace.move_relative.v1), and stop motion (cap.motion.stop.v1, the safe-state action).  The @estop also
  sends the native stop.

Every Fact cites a line of the clone at the pinned commit (914a6f618cacce6aa9ce42d371a895989e092b59).  This package
is model-authored and unreviewed; it is checked on the fake backend only and no hardware was attached or run.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

_UNIT = "1"  # the stage unit: mm for MTS50 and LTS300, degrees for PRM1

_OPERATOR_POSITION = (
    "the travel range depends on the stage model: MTS50 0 to 50 mm (pyAPT/mts50.py:31), LTS300 0 to 300 mm "
    "(pyAPT/lts300.py:31) and PRM1 -180 to 180 degrees (pyAPT/prm1.py:35); the operator supplies the range of the "
    "installed stage in its own unit")
_OPERATOR_VELOCITY = (
    "the velocity limit depends on the stage model and the upstream README warns that limits quoted by Thorlabs "
    "often do not agree with reality (README.md:15-19); the operator supplies the velocity ceiling of the installed "
    "stage in its own unit per second")
_OPERATOR_ACCELERATION = (
    "the acceleration limit depends on the stage model and the upstream README warns that limits quoted by Thorlabs "
    "often do not agree with reality (README.md:15-19); the operator supplies the acceleration ceiling of the "
    "installed stage in its own unit per second squared")
_OPERATOR_RELATIVE = (
    "a relative move is bounded by the current position and the travel range of the installed stage, which the "
    "native goto checks when soft limits are enabled (pyAPT/controller.py:325-326); the operator supplies the "
    "distance range in the stage unit")
_OPERATOR_SPEED_SCALE = (
    "the native home() takes a velocity and clamps it to the controller's max_velocity (pyAPT/controller.py:262-264), "
    "while the class's 0 to 1 speed_scale is a catalogue bound and not a bound of the installed stage; the operator "
    "supplies the fraction of the configured maximum velocity this site allows")


class PyAPTStage(Driver):
    device_id = "pyapt-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "pyAPT.controller:Controller"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakePyapt"}
    vendor, model = "Thorlabs", "APT motion controller (MTS50, PRM1 or LTS300 stage)"
    display_name = "Thorlabs APT stage controller (pyapt)"
    tags = ["thorlabs", "apt", "motion", "stage", "usb", "ftdi"]
    facts = [
        Fact("The Controller opens the FTDI device and sets its baud rate to 115200", source="upstream_code",
             ref="pyAPT/controller.py:26-28"),
        Fact("The FTDI line is configured for 8 data bits, 1 stop bit and no parity", source="upstream_code",
             ref="pyAPT/controller.py:34-37"),
        Fact("MTS50, PRM1 and LTS300 are subclasses of Controller that set the stage scales and travel range",
             source="upstream_code", ref="pyAPT/mts50.py:4-31"),
        Fact("The base Controller defines linear_range as the linear distance range in mm with a conservative "
             "(0, 50) default", source="upstream_code", ref="pyAPT/controller.py:71-73"),
        Fact("LTS300 sets its linear range to 0 to 300 mm", source="upstream_code", ref="pyAPT/lts300.py:31"),
        Fact("PRM1 sets its linear range to -180 to 180, the rotation range in degrees", source="upstream_code",
             ref="pyAPT/prm1.py:35"),
        Fact("status() returns the position and velocity of the controller, and its docstring says those are in mm "
             "and mm/s", source="upstream_code", ref="pyAPT/controller.py:163-169"),
        Fact("position() converts the raw encoder count with position_scale and returns the real-world position",
             source="upstream_code", ref="pyAPT/controller.py:285-303"),
        Fact("goto() raises OutOfRangeError when soft limits are enabled and the target is outside linear_range",
             source="upstream_code", ref="pyAPT/controller.py:325-326"),
        Fact("move() reads the current position and calls goto() with the relative target", source="upstream_code",
             ref="pyAPT/controller.py:358-381"),
        Fact("home() reuses the current homing parameters, changes the velocity and offset, sends SET_HOMEPARAMS and "
             "MOVE_HOME, and waits for MOVE_HOMED when wait is true", source="upstream_code",
             ref="pyAPT/controller.py:245-282"),
        Fact("set_soft_limits() sets whether the controller observes range limits in software",
             source="upstream_code", ref="pyAPT/controller.py:383-387"),
        Fact("set_velocity_parameters() clamps acceleration and maximum velocity to the controller attributes and "
             "sends SET_VELPARAMS", source="upstream_code", ref="pyAPT/controller.py:398-420"),
        Fact("velocity_parameters() returns minimum velocity, acceleration and maximum velocity in real-world units",
             source="upstream_code", ref="pyAPT/controller.py:422-455"),
        Fact("stop() sends MOVE_STOP; immediate true stops immediately, otherwise it stops in a profiled manner, and "
             "wait false returns after sending", source="upstream_code", ref="pyAPT/controller.py:499-530"),
        Fact("The upstream README warns that stage limits quoted on the Thorlabs website or user manuals often do "
             "not agree with reality and recommends the APT User software limits", source="vendor_doc",
             ref="README.md:15-19"),
        Fact("reset_parameters() restores the EEPROM defaults and only the BPC30x series appears to support it",
             source="upstream_code", ref="pyAPT/controller.py:183-191"),
        Fact("keepalive() sends the server-alive message, which must be sent at least once a second over USB",
             source="upstream_code", ref="pyAPT/controller.py:532-543"),
    ]
    safe_state = "stage motion stopped by the native stop with the immediate flag"

    # -- reads -------------------------------------------------------------------------------------------------
    @read("position", unit=_UNIT,
          description="Stage position in the stage unit: mm for MTS50 and LTS300, degrees for PRM1")
    def position(self):
        return float(self.native.position())

    @read("velocity", unit=_UNIT, description="Actual stage velocity in stage units per second")
    def velocity(self):
        return float(self.native.status().velocity)

    @read("moving", type="boolean", description="True while the controller reports motion")
    def moving(self):
        return bool(self.native.status().moving)

    @read("homed", type="boolean", description="True when the controller reports that the stage is homed")
    def homed(self):
        return bool(self.native.status().homed)

    @read("forward_limit_active", type="boolean",
          description="True when the forward hardware limit switch is active")
    def forward_limit_active(self):
        return bool(self.native.status().forward_hardware_limit_switch_active)

    @read("reverse_limit_active", type="boolean",
          description="True when the reverse hardware limit switch is active")
    def reverse_limit_active(self):
        return bool(self.native.status().reverse_hardware_limit_switch_active)

    @read("status", type="string", description="Short status line: homed, moving/tracking/settled and limit flags")
    def status(self):
        return str(self.native.status().shortstatus)

    @read("status_bits", type="integer", unit=_UNIT, description="Raw controller status word")
    def status_bits(self):
        return int(self.native.status().statusbits)

    @read("soft_limits", type="boolean",
          description="True when the controller refuses a target outside its software travel range")
    def soft_limits(self):
        return bool(self.native.soft_limits)

    @read("minimum_velocity", unit=_UNIT,
          description="Configured minimum velocity in stage units per second (the APT protocol keeps it at zero)")
    def minimum_velocity(self):
        return float(self.native.velocity_parameters()[0])

    @read("maximum_velocity", unit=_UNIT,
          description="Configured maximum velocity in stage units per second")
    def maximum_velocity(self):
        return float(self.native.velocity_parameters()[2])

    @read("acceleration", unit=_UNIT,
          description="Configured acceleration in stage units per second squared")
    def acceleration(self):
        return float(self.native.velocity_parameters()[1])

    # -- writes ------------------------------------------------------------------------------------------------
    @write("position", unit=_UNIT,
           description="Absolute position target in stage units; the driver sends an absolute move and returns the "
                       "position the controller reports afterwards",
           limit=Limit.operator_required(_OPERATOR_POSITION))
    def set_position(self, value):
        self.native.goto(value, wait=True)
        return float(self.native.position())

    @write("maximum_velocity", unit=_UNIT,
           description="Maximum velocity in stage units per second; the configured acceleration is kept",
           limit=Limit.operator_required(_OPERATOR_VELOCITY))
    def set_maximum_velocity(self, value):
        acceleration = float(self.native.velocity_parameters()[1])
        self.native.set_velocity_parameters(acceleration=acceleration, max_velocity=value)
        return float(self.native.velocity_parameters()[2])

    @write("acceleration", unit=_UNIT,
           description="Acceleration in stage units per second squared; the configured maximum velocity is kept",
           limit=Limit.operator_required(_OPERATOR_ACCELERATION))
    def set_acceleration(self, value):
        maximum_velocity = float(self.native.velocity_parameters()[2])
        self.native.set_velocity_parameters(acceleration=value, max_velocity=maximum_velocity)
        return float(self.native.velocity_parameters()[1])

    @write("soft_limits", type="boolean",
           description="Enable or disable the controller's software travel-limit check")
    def set_soft_limits(self, value):
        self.native.set_soft_limits(bool(value))
        return bool(self.native.soft_limits)

    # -- actions -----------------------------------------------------------------------------------------------
    @action(cap="cap.motion.home.v1",
            description="Home the stage with the controller's configured homing direction and limit switch; "
                        "speed_scale scales the configured maximum velocity for this move and the driver waits for "
                        "the move to finish",
            input={"speed_scale": Field("number", unit=_UNIT,
                                        description="Fraction of the controller's configured maximum velocity used "
                                                    "for this homing move",
                                        limit=Limit.operator_required(_OPERATOR_SPEED_SCALE))})
    def home(self, speed_scale=1.0):
        if speed_scale is not None and float(speed_scale) > 0.0:
            self.native.home(wait=True, velocity=float(self.native.max_velocity) * float(speed_scale))
        else:
            self.native.home(wait=True)
        return {"homed": bool(self.native.status().homed)}

    @action(name="x-cap.freespace.move_relative.v1",
            description="Move the stage relative to its current position; the driver waits for the move to finish",
            input={"distance": Field("number", unit=_UNIT,
                                     description="Relative travel in the stage unit; positive is forward",
                                     limit=Limit.operator_required(_OPERATOR_RELATIVE))},
            output={"position": Field("number", unit=_UNIT,
                                      description="Position the controller reports after the move")})
    def move_relative(self, distance):
        self.native.move(distance, wait=True)
        return {"position": float(self.native.position())}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop stage motion with the native stop; the APT message has no deceleration value, so a "
                        "supplied deceleration selects the profiled stop and zero or no input selects the immediate "
                        "stop",
            input={"deceleration": Field("number", unit="m/s2",
                                         description="Requested deceleration; any positive value selects the "
                                                     "controller's profiled stop, zero or no value the immediate "
                                                     "stop (the APT stop message carries no deceleration value)")})
    def stop_motion(self, deceleration=None):
        immediate = deceleration is None or float(deceleration) <= 0.0
        self.native.stop(immediate=immediate, wait=False)
        return {"stopped": True, "stopped_position": {"position": float(self.native.position())}}

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then the immediate stop is sent."""
        self.native.stop(immediate=True, wait=False)

    def teardown(self):
        self.native.close()     # pyAPT/controller.py:92-97 stops with wait=False and closes the FTDI device
