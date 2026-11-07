"""OpenMHS driver for gh.qpit/thorlabs_apt: a Thorlabs APT motor through the upstream Motor class.

A direct Driver (decorated methods) over thorlabs_apt.core:Motor, the ctypes wrapper of Thorlabs' APT.dll.  The
upstream object is synchronous: every read and write here is a plain ``def`` that calls ``self.native``.  The clone
is Windows-only because it loads APT.dll at import time (README.md:7), so the package is checked on the fake backend
and no hardware run is claimed.

* reads: position and the controller's status bits (motion, homing, settling, motion error, channel enabled, the two
  hardware limit switches), the active channel, the stage axis information and the velocity / limit-switch / homing
  parameters;
* writes: maximum velocity and acceleration (``Limit.operator_required``: the clone returns the real limits from the
  controller at run time and states no fixed number), plus the hardware limit-switch modes and the homing direction and
  limit switch (closed sets taken from the constants in thorlabs_apt/core.py);
* actions: absolute and relative moves, homing, constant-velocity motion, enable and disable (extension classes in
  native stage units, because the catalogue's joint-position class fixes radians while an APT stage is configured in
  mm or degrees), and the native profiled stop as an extension safe-state action (the catalogue stop class declares a
  deceleration input that MOT_StopProfiled does not take).

Every Fact cites a line of the clone at the pinned commit (7b5c84607c22684cc896e3c337045b9358ee7c47).  This package
is model-authored and unreviewed.  The loader refuses an unreviewed model-written hardware backend only at R2 and R3;
this driver is R1 and does not claim that protection, so an operator must review it before hardware use.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write


class ThorlabsAPT(Driver):
    device_id = "thorlabs-apt-motor"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R1"
    native = "thorlabs_apt.core:Motor"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeMotor"}
    vendor, model = "Thorlabs", "APT motor (Thorlabs APT.dll)"
    display_name = "Thorlabs APT motor (thorlabs_apt.Motor)"
    tags = ["thorlabs", "apt", "motor", "stage", "motion", "windows"]
    facts = [
        Fact("The package wraps Thorlabs' APT.dll shared library", source="vendor_doc", ref="README.md:3"),
        Fact("The package only works on Windows because it is based on APT.dll", source="vendor_doc",
             ref="README.md:7"),
        Fact("The README lists K10CR1, LTS150 and other motors as reported working devices and says the package "
             "should work with all motors supported by APT", source="vendor_doc", ref="README.md:18-29"),
        Fact("Motor(serial_number) stores the serial number and calls InitHWDevice(serial_number) in its constructor",
             source="upstream_code", ref="thorlabs_apt/core.py:144-151"),
        Fact("move_to(value, blocking=False) sends MOT_MoveAbsoluteEx and move_by(value, blocking=False) sends "
             "MOT_MoveRelativeEx", source="upstream_code", ref="thorlabs_apt/core.py:763-796"),
        Fact("move_home(blocking=False) sends MOT_MoveHome", source="upstream_code",
             ref="thorlabs_apt/core.py:817-830"),
        Fact("move_velocity(direction) sends MOT_MoveVelocity", source="upstream_code",
             ref="thorlabs_apt/core.py:832-843"),
        Fact("MOVE_FWD is 1 and MOVE_REV is 2", source="upstream_code", ref="thorlabs_apt/core.py:43-47"),
        Fact("stop_profiled() sends MOT_StopProfiled", source="upstream_code", ref="thorlabs_apt/core.py:845-852"),
        Fact("position reads MOT_GetPosition", source="upstream_code", ref="thorlabs_apt/core.py:799-812"),
        Fact("get_stage_axis_info returns (minimum position, maximum position, stage units, pitch); the stage units "
             "are STAGE_UNITS_MM = 1 and STAGE_UNITS_DEG = 2", source="upstream_code",
             ref="thorlabs_apt/core.py:574-597"),
        Fact("get_hardware_limit_switches returns reverse and forward modes; HWLIMSWITCH_IGNORE = 1, "
             "HWLIMSWITCH_MAKES = 2, HWLIMSWITCH_BREAKS = 3, HWLIMSWITCH_MAKES_HOMEONLY = 4 and "
             "HWLIMSWITCH_BREAKS_HOMEONLY = 5", source="upstream_code", ref="thorlabs_apt/core.py:636-664"),
        Fact("set_hardware_limit_switches(rev, fwd) sends MOT_SetHWLimSwitches", source="upstream_code",
             ref="thorlabs_apt/core.py:670-706"),
        Fact("get_move_home_parameters returns (direction, limiting switch, velocity, zero offset)",
             source="upstream_code", ref="thorlabs_apt/core.py:444-466"),
        Fact("HOME_FWD is 1, HOME_REV is 2, HOMELIMSW_FWD is 4 and HOMELIMSW_REV is 1", source="upstream_code",
             ref="thorlabs_apt/core.py:9-20"),
        Fact("get_velocity_parameters returns (minimum velocity, acceleration, maximum velocity)",
             source="upstream_code", ref="thorlabs_apt/core.py:344-363"),
        Fact("set_velocity_parameters(min_vel, accn, max_vel) sends MOT_SetVelParams; the docstring says the minimum "
             "velocity is always 0 and is ignored", source="upstream_code", ref="thorlabs_apt/core.py:365-393"),
        Fact("get_velocity_parameter_limits returns the maximum acceleration and the maximum velocity of the motor",
             source="upstream_code", ref="thorlabs_apt/core.py:395-418"),
        Fact("is_in_motion is derived from status bits 0x00000010, 0x00000020, 0x00000040, 0x00000080 and "
             "0x00000200", source="upstream_code", ref="thorlabs_apt/core.py:232-239"),
        Fact("is_channel_enabled uses status bit 0x80000000; enable() and disable() send MOT_EnableHWChannel and "
             "MOT_DisableHWChannel", source="upstream_code", ref="thorlabs_apt/core.py:286-333"),
        Fact("has_homing_been_completed uses status bit 0x00000400, is_settled uses 0x00002000 and motion_error uses "
             "0x00004000", source="upstream_code", ref="thorlabs_apt/core.py:241-284"),
        Fact("active_channel is 0 for channel 1 and 1 for channel 2", source="upstream_code",
             ref="thorlabs_apt/core.py:299-307"),
    ]
    safe_state = ("motor stopped with the native profiled stop (MOT_StopProfiled); the channel stays enabled unless "
                  "disable is called")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("position", unit="1",
          description="Motor position in the native stage unit reported by stage_units (mm or degrees)")
    def position(self):
        return float(self.native.position)

    @read("serial_number", type="integer", description="Serial number identifying the motor")
    def serial_number(self):
        return int(self.native.serial_number)

    @read("in_motion", type="boolean", description="True while the controller reports motion")
    def in_motion(self):
        return bool(self.native.is_in_motion)

    @read("homing_completed", type="boolean", description="True once homing has been completed at some point")
    def homing_completed(self):
        return bool(self.native.has_homing_been_completed)

    @read("settled", type="boolean", description="True when the controller reports the motor settled")
    def settled(self):
        return bool(self.native.is_settled)

    @read("motion_error", type="boolean", description="True when the controller reports an excessive position error")
    def motion_error(self):
        return bool(self.native.motion_error)

    @read("enabled", type="boolean", description="True while the active channel is enabled")
    def enabled(self):
        return bool(self.native.is_channel_enabled)

    @read("forward_limit_active", type="boolean", description="True while the forward hardware limit switch is active")
    def forward_limit_active(self):
        return bool(self.native.is_forward_hardware_limit_switch_active)

    @read("reverse_limit_active", type="boolean", description="True while the reverse hardware limit switch is active")
    def reverse_limit_active(self):
        return bool(self.native.is_reverse_hardware_limit_switch_active)

    @read("active_channel", type="integer", description="Active channel index: 0 for channel 1, 1 for channel 2")
    def active_channel(self):
        return int(self.native.active_channel)

    @read("stage_minimum", unit="1", description="Minimum position of the configured stage, in native stage units")
    def stage_minimum(self):
        return float(self.native.get_stage_axis_info()[0])

    @read("stage_maximum", unit="1", description="Maximum position of the configured stage, in native stage units")
    def stage_maximum(self):
        return float(self.native.get_stage_axis_info()[1])

    @read("stage_units", type="integer", description="Stage unit code: 1 for mm, 2 for degrees")
    def stage_units(self):
        return int(self.native.get_stage_axis_info()[2])

    @read("velocity_maximum", unit="1", description="Maximum velocity in native stage units per second")
    def velocity_maximum(self):
        return float(self.native.get_velocity_parameters()[2])

    @read("acceleration", unit="1", description="Acceleration in native stage units per second squared")
    def acceleration(self):
        return float(self.native.get_velocity_parameters()[1])

    @read("reverse_limit_switch", type="integer", unit="1",
          description="Reverse hardware limit-switch mode: 1 ignore, 2 makes, 3 breaks, 4 makes home-only, "
                      "5 breaks home-only")
    def reverse_limit_switch(self):
        return int(self.native.get_hardware_limit_switches()[0])

    @read("forward_limit_switch", type="integer", unit="1",
          description="Forward hardware limit-switch mode: 1 ignore, 2 makes, 3 breaks, 4 makes home-only, "
                      "5 breaks home-only")
    def forward_limit_switch(self):
        return int(self.native.get_hardware_limit_switches()[1])

    @read("move_home_direction", type="integer", unit="1",
          description="Homing direction: 1 forward, 2 reverse")
    def move_home_direction(self):
        return int(self.native.get_move_home_parameters()[0])

    @read("move_home_lim_switch", type="integer", unit="1",
          description="Homing limit switch: 1 reverse, 4 forward")
    def move_home_lim_switch(self):
        return int(self.native.get_move_home_parameters()[1])

    # -- writes -----------------------------------------------------------------------------------------------
    @write("velocity_maximum", unit="1", description="Maximum velocity in native stage units per second",
           limit=Limit.operator_required(
               "the maximum velocity depends on the motor and stage: the clone returns it at run time from "
               "MOT_GetVelParamLimits (thorlabs_apt/core.py:395-418) and states no fixed number; the operator "
               "supplies the site limit"))
    def set_velocity_maximum(self, value):
        min_vel, acceleration, _maximum = self.native.get_velocity_parameters()
        self.native.set_velocity_parameters(min_vel, acceleration, value)

    @write("acceleration", unit="1", description="Acceleration in native stage units per second squared",
           limit=Limit.operator_required(
               "the maximum acceleration depends on the motor and stage: the clone returns it at run time from "
               "MOT_GetVelParamLimits (thorlabs_apt/core.py:395-418) and states no fixed number; the operator "
               "supplies the site limit"))
    def set_acceleration(self, value):
        min_vel, _acceleration, maximum = self.native.get_velocity_parameters()
        self.native.set_velocity_parameters(min_vel, value, maximum)

    @write("reverse_limit_switch", type="integer", unit="1",
           description="Reverse hardware limit-switch mode (1 to 5)",
           limit=Limit(allowed=[1, 2, 3, 4, 5], source="upstream_code",
                       ref="thorlabs_apt/core.py:28-41"))
    def set_reverse_limit_switch(self, value):
        _reverse, forward = self.native.get_hardware_limit_switches()
        self.native.set_hardware_limit_switches(value, forward)

    @write("forward_limit_switch", type="integer", unit="1",
           description="Forward hardware limit-switch mode (1 to 5)",
           limit=Limit(allowed=[1, 2, 3, 4, 5], source="upstream_code",
                       ref="thorlabs_apt/core.py:28-41"))
    def set_forward_limit_switch(self, value):
        reverse, _forward = self.native.get_hardware_limit_switches()
        self.native.set_hardware_limit_switches(reverse, value)

    @write("move_home_direction", type="integer", unit="1",
           description="Homing direction: 1 forward, 2 reverse",
           limit=Limit(allowed=[1, 2], source="upstream_code", ref="thorlabs_apt/core.py:9-14"))
    def set_move_home_direction(self, value):
        _direction, lim_switch, velocity, zero_offset = self.native.get_move_home_parameters()
        self.native.set_move_home_parameters(value, lim_switch, velocity, zero_offset)

    @write("move_home_lim_switch", type="integer", unit="1",
           description="Homing limit switch: 1 reverse, 4 forward",
           limit=Limit(allowed=[1, 4], source="upstream_code", ref="thorlabs_apt/core.py:16-20"))
    def set_move_home_lim_switch(self, value):
        direction, _lim_switch, velocity, zero_offset = self.native.get_move_home_parameters()
        self.native.set_move_home_parameters(direction, value, velocity, zero_offset)

    # -- actions ----------------------------------------------------------------------------------------------
    @action(name="x-cap.qpit.move_to.v1",
            description="Move to an absolute position in the native stage units (mm or degrees)",
            input={"position": Field("number", unit="1",
                                     description="Absolute target in the native stage units",
                                     limit=Limit.operator_required(
                                         "the travel range of the installed stage is not stated in the clone; "
                                         "get_stage_axis_info reads it from the controller at run time "
                                         "(thorlabs_apt/core.py:574-597), so the operator supplies the range"))},
            output={"position": Field("number", unit="1", description="Position read back after the command"),
                    "in_motion": Field("boolean", description="True while the controller reports motion")})
    def move_to(self, position):
        self.native.move_to(position, False)
        return {"position": float(self.native.position), "in_motion": bool(self.native.is_in_motion)}

    @action(name="x-cap.qpit.move_by.v1",
            description="Move by a relative distance in the native stage units (mm or degrees)",
            input={"distance": Field("number", unit="1",
                                     description="Relative distance in the native stage units",
                                     limit=Limit.operator_required(
                                         "the travel range of the installed stage is not stated in the clone; "
                                         "get_stage_axis_info reads it from the controller at run time "
                                         "(thorlabs_apt/core.py:574-597), so the operator supplies the range"))},
            output={"position": Field("number", unit="1", description="Position read back after the command"),
                    "in_motion": Field("boolean", description="True while the controller reports motion")})
    def move_by(self, distance):
        self.native.move_by(distance, False)
        return {"position": float(self.native.position), "in_motion": bool(self.native.is_in_motion)}

    @action(name="x-cap.qpit.move_home.v1",
            description="Home the axis with the native homing move",
            output={"homed": Field("boolean", description="True once the controller reports homing completed"),
                    "position": Field("number", unit="1", description="Position read back after the command"),
                    "in_motion": Field("boolean", description="True while the controller reports motion")})
    def move_home(self):
        self.native.move_home(False)
        return {"homed": bool(self.native.has_homing_been_completed),
                "position": float(self.native.position),
                "in_motion": bool(self.native.is_in_motion)}

    @action(name="x-cap.qpit.move_velocity.v1",
            description="Move at constant velocity in the given direction",
            input={"direction": Field("integer", unit="1", description="1 for forward, 2 for reverse",
                                      limit=Limit(allowed=[1, 2], source="upstream_code",
                                                  ref="thorlabs_apt/core.py:43-47"))},
            output={"direction": Field("integer", unit="1", description="Direction that was commanded"),
                    "in_motion": Field("boolean", description="True while the controller reports motion")})
    def move_velocity(self, direction):
        self.native.move_velocity(direction)
        return {"direction": int(direction), "in_motion": bool(self.native.is_in_motion)}

    @action(name="x-cap.qpit.enable.v1",
            description="Enable the active motor channel",
            output={"enabled": Field("boolean", description="True once the active channel is enabled")})
    def enable(self):
        self.native.enable()
        return {"enabled": bool(self.native.is_channel_enabled)}

    @action(name="x-cap.qpit.disable.v1",
            description="Disable the active motor channel",
            output={"enabled": Field("boolean", description="False once the active channel is disabled")})
    def disable(self):
        self.native.disable()
        return {"enabled": bool(self.native.is_channel_enabled)}

    @action(name="x-cap.qpit.stop.v1", safe_state=True,
            description="Stop the motor with the native profiled stop",
            output={"stopped": Field("boolean", description="True once the controller reports no motion")})
    def stop_profiled(self):
        self.native.stop_profiled()
        return {"stopped": not bool(self.native.is_in_motion)}

    # -- safety -----------------------------------------------------------------------------------------------
    @estop(native="stop_profiled")
    def stop(self):
        """The native profiled stop: the runtime latches first, then calls MOT_StopProfiled."""
        self.native.stop_profiled()
