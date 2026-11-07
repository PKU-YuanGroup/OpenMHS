"""OpenMHS driver for gh.kzhao1228/pystage_apt: a Thorlabs APT single-channel stage controller.

A direct Driver (decorated methods) over the upstream device class stage.motor_ctrl:MotorCtrl.  The upstream class
talks to one controller channel through a `stage.motor_ini.port` port object (stage/motor_ctrl/__init__.py:9-21); the
hardware factory in native.py opens that port and returns the MotorCtrl for the channel.  The clone never runs in this
package on the fake backend.

* reads: stage position, motion state, homed state, channel state, limit-switch state, stage model and serial number,
  the configured velocity/acceleration and homing parameters;
* writes: absolute position, maximum velocity, acceleration, homing direction and homing limit switch.  The position
  and velocity/acceleration bounds depend on the stage mounted on the controller (stage/motor_ctrl/__init__.py:37-50),
  so those writes are `Limit.operator_required`; the site supplies its range in site-limits.json
  (site-limits.example.json is an example overlay);
* actions: home the axis (`cap.motion.home.v1`), move relative to the current position
  (`x-cap.kzhao1228.move_relative.v1`) and stop motion (`cap.motion.stop.v1`, the safe state);
* the upstream class has no stop method, so native.py wraps its port with a small object whose stop() sends the
  documented APT `MGMSG_MOT_MOVE_STOP` message (stage/ctrl_msg/motorcontrol.py:691-703).  The e-stop and the
  safe-state action both send that message; the e-stop also writes the documented default minimum velocity 0 so that
  the APT stop is preceded by a valid controller write.

Every Fact cites a line of the clone at the pinned commit (34bf8886ae996f30469338be3b02c42455ffea65).  This package
is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

_UNIT = "1"  # the stage unit: mm for linear stages, degrees for rotational stages
_OPERATOR_POSITION = (
    "the travel range depends on the mounted stage: MotorCtrl.set_pos compares the target with the per-stage Min Pos "
    "and Max Pos read from MG17APTServer.ini (stage/motor_ctrl/__init__.py:281-285), so the operator supplies the "
    "range of the installed stage")
_OPERATOR_VELOCITY = (
    "the velocity limit depends on the mounted stage: MotorCtrl.set_vel_params compares against the per-stage Def "
    "Min Vel and Max Vel read from MG17APTServer.ini (stage/motor_ctrl/__init__.py:1053-1063), so the operator "
    "supplies the limit of the installed stage")
_OPERATOR_ACCELERATION = (
    "the acceleration limit depends on the mounted stage: MotorCtrl.set_vel_params compares against the per-stage "
    "Max Accn read from MG17APTServer.ini (stage/motor_ctrl/__init__.py:1073), so the operator supplies the limit of "
    "the installed stage")
_OPERATOR_RELATIVE = (
    "a relative move is bounded by the current position and the per-stage Min Pos and Max Pos that MotorCtrl.move_by "
    "checks (stage/motor_ctrl/__init__.py:398-403), so the operator supplies the travel range of the installed stage")
_OPERATOR_SPEED_SCALE = (
    "the upstream homing call takes no speed argument and the class's 0 to 1 scale is a catalogue bound, not a bound "
    "of the installed stage; the operator supplies the fraction of the configured homing velocity this site allows")


class AptStage(Driver):
    device_id = "apt-stage"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "stage.motor_ctrl:MotorCtrl"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMotorCtrl"}
    vendor, model = "Thorlabs", "APT single-channel stage controller"
    display_name = "Thorlabs APT stage controller (pystage-apt)"
    tags = ["thorlabs", "apt", "motion", "stage", "serial", "usb"]
    facts = [
        Fact("pystage-apt is a library to communicate with various Thorlabs APT single-channel controllers and "
             "control different types of Thorlabs actuator motors", source="vendor_doc", ref="README.rst:7"),
        Fact("MotorCtrl manipulates an APT controller channel identified by chan_ident (0x01 for a single-channel "
             "controller)", source="upstream_code", ref="stage/motor_ctrl/__init__.py:9-21"),
        Fact("MotorCtrl reads the per-stage Min Pos, Max Pos, Def Min Vel, Def Max Vel, Max Accn, Max Vel and homing "
             "parameters from the MG17APTServer.ini section of the detected stage", source="upstream_code",
             ref="stage/motor_ctrl/__init__.py:41-59"),
        Fact("set_pos refuses (prints and keeps the current position) a target outside the stage configuration Min "
             "Pos and Max Pos before sending an absolute move", source="upstream_code",
             ref="stage/motor_ctrl/__init__.py:281-297"),
        Fact("move_by refuses (prints and sends nothing) a relative distance that would leave the stage configuration "
             "Min Pos and Max Pos", source="upstream_code", ref="stage/motor_ctrl/__init__.py:398-403"),
        Fact("set_vel_params requires Def Min Vel <= min_vel < max_vel <= Max Vel and 0 < accn <= Max Accn",
             source="upstream_code", ref="stage/motor_ctrl/__init__.py:1053-1073"),
        Fact("The stage unit index is 1 for mm and 2 for degrees; the units property returns 'mm' or the degree sign",
             source="upstream_code", ref="stage/motor_ctrl/__init__.py:1518"),
        Fact("Homing direction 1 is forward and 2 is reverse", source="upstream_code",
             ref="stage/motor_ctrl/__init__.py:1263-1264"),
        Fact("The homing limit switch is 4 for the forward switch and 1 for the reverse switch", source="upstream_code",
             ref="stage/motor_ctrl/__init__.py:1277-1278"),
        Fact("set_home_params requires Def Min Vel < home_velocity < Max Vel", source="upstream_code",
             ref="stage/motor_ctrl/__init__.py:1307"),
        Fact("MGMSG_MOT_MOVE_STOP stops any type of motor move on a channel; stop_mode 0x01 stops immediately and "
             "0x02 stops in a controlled (profiled) manner", source="upstream_code",
             ref="stage/ctrl_msg/motorcontrol.py:691-703"),
        Fact("The upstream serial port opens at 115200 baud, 8 data bits, no parity, one stop bit and RTS/CTS flow "
             "control", source="upstream_code", ref="stage/motor_ini/port.py:40-44"),
    ]
    safe_state = "stage motion stopped by the APT MOVE_STOP message (stop mode immediate)"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", unit=_UNIT,
          description="Stage position in the stage unit: mm for a linear stage, degrees for a rotational stage")
    def position(self):
        return float(self.native.pos)

    @read("in_motion", type="boolean", description="True while the controller reports motion on this channel")
    def in_motion(self):
        return bool(self.native.is_in_motion)

    @read("homed", type="boolean", description="True when the stage reports that homing is complete")
    def homed(self):
        return bool(self.native.status_homed)

    @read("channel_enabled", type="boolean", description="True when the controller channel is enabled")
    def channel_enabled(self):
        return bool(self.native.status_channel_enabled)

    @read("forward_limit_active", type="boolean",
          description="True when the forward hardware limit switch of the stage is active")
    def forward_limit_active(self):
        return bool(self.native.status_forward_hardware_limit_switch_active)

    @read("reverse_limit_active", type="boolean",
          description="True when the reverse hardware limit switch of the stage is active")
    def reverse_limit_active(self):
        return bool(self.native.status_reverse_hardware_limit_switch_active)

    @read("stage_model", type="string", description="Stage model name detected by the upstream library")
    def stage_model(self):
        return str(self.native.stage_model)

    @read("serial_number", type="integer", description="Serial number of the APT controller")
    def serial_number(self):
        return int(self.native.ser_no)

    @read("units", type="string", description="Stage unit: 'mm' for a linear stage or 'deg' for a rotational stage")
    def units(self):
        return "deg" if self.native.units == "\u00b0" else str(self.native.units)

    @read("minimum_velocity", unit=_UNIT, description="Configured minimum velocity in stage units per second")
    def minimum_velocity(self):
        return float(self.native.min_vel)

    @read("maximum_velocity", unit=_UNIT, description="Configured maximum velocity in stage units per second")
    def maximum_velocity(self):
        return float(self.native.max_vel)

    @read("acceleration", unit=_UNIT, description="Configured acceleration in stage units per second squared")
    def acceleration(self):
        return float(self.native.accn)

    @read("home_velocity", unit=_UNIT, description="Configured homing velocity in stage units per second")
    def home_velocity(self):
        return float(self.native.home_vel)

    @read("home_direction", type="integer", unit="1",
          description="Configured homing direction: 1 forward, 2 reverse")
    def home_direction(self):
        return int(self.native.home_dir)

    @read("home_limit_switch", type="integer", unit="1",
          description="Configured homing limit switch: 4 forward, 1 reverse")
    def home_limit_switch(self):
        return int(self.native.home_limit_switch)

    # -- writes -------------------------------------------------------------------------------------------------
    @write("position", unit=_UNIT,
           description="Absolute position target in the stage unit; the driver sends an absolute move and returns "
                       "the position the controller reports afterwards",
           limit=Limit.operator_required(_OPERATOR_POSITION))
    def set_position(self, value):
        self.native.set_pos(value, blocking=True)
        return float(self.native.pos)

    @write("maximum_velocity", unit=_UNIT,
           description="Maximum velocity in stage units per second; 0 < value and the configured minimum velocity "
                       "must stay below it",
           limit=Limit.operator_required(_OPERATOR_VELOCITY))
    def set_maximum_velocity(self, value):
        self.native.set_max_vel(value)
        return float(self.native.max_vel)

    @write("acceleration", unit=_UNIT,
           description="Acceleration in stage units per second squared; it must stay above zero",
           limit=Limit.operator_required(_OPERATOR_ACCELERATION))
    def set_acceleration(self, value):
        self.native.set_accn(value)
        return float(self.native.accn)

    @write("home_direction", type="integer", unit="1", description="Homing direction: 1 forward, 2 reverse",
           limit=Limit(allowed=[1, 2], source="upstream_code",
                       ref="stage/motor_ctrl/__init__.py:1263-1264"))
    def set_home_direction(self, value):
        self.native.set_home_dir(int(value))
        return int(self.native.home_dir)

    @write("home_limit_switch", type="integer", unit="1",
           description="Homing limit switch: 4 forward, 1 reverse",
           limit=Limit(allowed=[1, 4], source="upstream_code",
                       ref="stage/motor_ctrl/__init__.py:1277-1278"))
    def set_home_limit_switch(self, value):
        self.native.set_limit_switch(int(value))
        return int(self.native.home_limit_switch)

    # -- actions -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.home.v1",
            description="Home the stage with the configured homing direction and limit switch; speed_scale scales "
                        "the configured homing velocity for this move and the old value is restored afterwards",
            input={"speed_scale": Field("number", unit=_UNIT,
                                        description="Fraction of the configured homing velocity used for this move",
                                        limit=Limit.operator_required(_OPERATOR_SPEED_SCALE))})
    def home(self, speed_scale=1.0):
        original = float(self.native.home_vel)
        changed = False
        if abs(float(speed_scale) - 1.0) > 1e-9:
            scaled = original * float(speed_scale)
            if scaled <= 0.0:
                raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                                   "speed_scale must leave a positive homing velocity")
            self.native.set_home_vel(scaled)
            changed = True
        try:
            self.native.move_home(blocking=True)
        finally:
            if changed:
                self.native.set_home_vel(original)
        return {"homed": bool(self.native.status_homed)}

    @action(name="x-cap.kzhao1228.move_relative.v1", description="Move the stage relative to its current position",
            input={"distance": Field("number", unit=_UNIT,
                                     description="Relative travel in the stage unit; positive is forward",
                                     limit=Limit.operator_required(_OPERATOR_RELATIVE))},
            output={"position": Field("number", unit=_UNIT,
                                      description="Position the stage reports after the command is sent")})
    def move_relative(self, distance):
        self.native.move_by(distance, blocking=True)
        return {"position": float(self.native.pos)}

    @action(cap="cap.motion.stop.v1", safe_state=True,
            description="Stop every motor move on the channel; a supplied deceleration asks for the APT profiled "
                        "stop mode, otherwise the stop is immediate",
            input={"deceleration": Field("number", unit="m/s2",
                                         description="Deceleration requested for a profiled stop; omit it for an "
                                                     "immediate stop (the APT message has no deceleration field)")})
    def stop_motion(self, deceleration=None):
        stop_mode = 0x02 if deceleration is not None and float(deceleration) > 0.0 else 0x01
        self._native_stop(stop_mode)
        return {"stopped": not bool(self.native.is_in_motion),
                "stopped_position": {"position": float(self.native.pos)}}

    # -- safety -------------------------------------------------------------------------------------------------
    def _native_stop(self, stop_mode=0x01):
        """Write the documented default minimum velocity, then send the APT stop message through the port."""
        self.native.set_min_vel(0)
        self.native._port.stop(stop_mode)

    @estop
    def stop(self):
        """The runtime latches first, then this sends the APT MOVE_STOP message on the channel."""
        self._native_stop(0x01)
