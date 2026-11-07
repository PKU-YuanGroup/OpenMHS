"""OpenMHS driver for gh.rwb27/openflexure_nano_motor_controller: a three-axis OpenFlexure stage.

A direct Driver (decorated methods) over the upstream class openflexure_stage.stage:OpenFlexureStage
(openflexure_stage/stage.py:19).  The upstream class is a Python wrapper around the Sangaboard v0.2 firmware's
newline-terminated serial protocol, so the driver translates each capability into one upstream method call and never
builds a wire command itself.

* reads: the firmware string, the stage position in integer motor steps, the minimum step delay and the ramp time in
  microseconds, and the optional endstop state and maximum positions;
* actions: relative move, absolute move, relative focus move, homing and releasing the motor coils;
* the hardware stop path: the firmware has no separate stop command.  The native stop and the safe-state action both
  send the firmware's ``release`` command, which de-energises every stepper coil (stage.py:198-200, firmware:680-683).

No text file of the clone states a travel range, a step delay range or a ramp time range: the maximum positions are
stored on the board and set by the operator (stage.py:397-399), so every motion input is ``Limit.operator_required``.
The package's site-limits.example.json shows the overlay that supplies example bounds; without one every motion call
is refused ``MHS.SAFETY.LIMITS_UNSET``.

Every Fact cites a line of the clone at the pinned commit 18a19977dde0cd78f14154c41073a857e2332e54.  This package is
model-authored and unreviewed; the acceptance gate checks the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

_TRAVEL_LIMIT = Limit.operator_required(
    "no text file of the clone states the travel range of the stage: the maximum positions are stored on the board "
    "(stage.py:397-399) and the firmware's own search distances are not a device bound, so the operator supplies the "
    "envelope in site-limits.json"
)


class OpenFlexureStage(Driver):
    device_id = "openflexure-stage"
    device_kind = "optics.stage"
    mode = "hardware"
    risk = "R1"
    native = "openflexure_stage.stage:OpenFlexureStage"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOpenFlexureStage"}
    vendor = "OpenFlexure"
    model = "Motor Board (Sangaboard v0.2)"
    display_name = "OpenFlexure Motor Board stage"
    tags = ["microscope", "stage", "stepper", "serial", "openflexure"]
    facts = [
        Fact("The board reports its position as three integers with the p? query",
             source="upstream_code", ref="openflexure_stage/stage.py:45-46"),
        Fact("step_time is read with dt? and written with dt <int>, in microseconds",
             source="upstream_code", ref="openflexure_stage/stage.py:47-50"),
        Fact("ramp_time is read with ramp_time? and written with ramp_time <int>, in microseconds",
             source="upstream_code", ref="openflexure_stage/stage.py:51-57"),
        Fact("move_rel sends mr <dx> <dy> <dz> for a three-axis relative move, or mr<axis> <n> for one axis",
             source="upstream_code", ref="openflexure_stage/stage.py:186-196"),
        Fact("move_abs queries position and then calls move_rel with the difference, because the stage only accepts "
             "relative moves", source="upstream_code", ref="openflexure_stage/stage.py:202-211"),
        Fact("focus_rel moves the stage in Z by the given number of micro steps",
             source="upstream_code", ref="openflexure_stage/stage.py:213-215"),
        Fact("release_motors sends release, which de-energises the stepper motor coils",
             source="upstream_code", ref="openflexure_stage/stage.py:198-200"),
        Fact("Endstops.status reads endstops? as -1, 0 or 1 per axis; maxima reads max_p? and writes max <d> <d> <d>",
             source="upstream_code", ref="openflexure_stage/stage.py:395-399"),
        Fact("Endstops.home sends home_min or home_max with the axis bitmap built from the axes list and the "
             "direction min, max or both", source="upstream_code", ref="openflexure_stage/stage.py:401-424"),
        Fact("The default serial port settings are 115200 baud, 8 data bits, no parity and one stop bit",
             source="upstream_code", ref="openflexure_stage/stage.py:41"),
        Fact("The Python module reads the version string at construction and requires firmware v0.4",
             source="upstream_code", ref="openflexure_stage/stage.py:77-87"),
        Fact("The firmware defines three stepper motors for X, Y and Z",
             source="upstream_code",
             ref="arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:77-78"),
        Fact("The firmware's release command de-energises every motor coil",
             source="upstream_code",
             ref="arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:680-683"),
        Fact("The maximum endstop positions are stored on the board and set with max <d> <d> <d>",
             source="upstream_code",
             ref="arduino_code/openflexure_nano_motor_controller/openflexure_nano_motor_controller.ino:771-784"),
    ]
    safe_state = "stepper motor coils de-energised by the firmware release command"

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("firmware", type="string",
          description="Firmware version string reported by the board at construction")
    def firmware(self):
        return self.native.board

    @read("position", type="array", items="integer", length=3, unit="step",
          description="Stage position in integer motor steps, ordered x, y, z")
    def position(self):
        return list(self.native.position)

    @read("step_time", type="integer", unit="us",
          description="Minimum time between steps of the motors in microseconds")
    def step_time(self):
        return int(self.native.step_time)

    @read("ramp_time", type="integer", unit="us",
          description="Time over which the stage accelerates and decelerates, in microseconds")
    def ramp_time(self):
        return int(self.native.ramp_time)

    @read("endstop_status", type=Field("array", items="integer", length=3, nullable=True,
                                       description="Endstop state per axis: -1 min triggered, 0 none, 1 max "
                                                   "triggered; null when the firmware has no endstop module"))
    def endstop_status(self):
        endstops = getattr(self.native, "endstops", None)
        return None if endstops is None else list(endstops.status)

    @read("endstop_maxima", type=Field("array", items="integer", length=3, unit="step", nullable=True,
                                       description="Maximum position of each axis in motor steps as stored on the "
                                                   "board; null when the firmware has no endstop module"))
    def endstop_maxima(self):
        endstops = getattr(self.native, "endstops", None)
        return None if endstops is None else list(endstops.maxima)

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.rwb27.move_relative.v1",
            description="Move the stage by a relative displacement in integer motor steps",
            input={"displacement": Field("array", items="integer", length=3, unit="step",
                                         description="Relative displacement (x, y, z) in integer motor steps",
                                         limit=_TRAVEL_LIMIT)},
            output={"position": Field("array", items="integer", length=3, unit="step",
                                      description="Stage position after the move, in integer motor steps")})
    def move_relative(self, displacement):
        self.native.move_rel(displacement)
        return {"position": list(self.native.position)}

    @action(name="x-cap.rwb27.move_absolute.v1",
            description="Move the stage to an absolute position in integer motor steps",
            input={"target_position": Field("array", items="integer", length=3, unit="step",
                                            description="Target position (x, y, z) in integer motor steps",
                                            limit=_TRAVEL_LIMIT)},
            output={"position": Field("array", items="integer", length=3, unit="step",
                                      description="Stage position after the move, in integer motor steps")})
    def move_absolute(self, target_position):
        self.native.move_abs(target_position)
        return {"position": list(self.native.position)}

    @action(name="x-cap.rwb27.focus_relative.v1",
            description="Move the focus axis (Z) by a relative displacement in integer motor steps",
            input={"z": Field("integer", unit="step",
                              description="Relative Z displacement in integer motor steps",
                              limit=_TRAVEL_LIMIT)},
            output={"position": Field("array", items="integer", length=3, unit="step",
                                      description="Stage position after the move, in integer motor steps")})
    def focus_relative(self, z):
        self.native.focus_rel(z)
        return {"position": list(self.native.position)}

    @action(name="x-cap.rwb27.home.v1",
            description="Home the selected axes to their minimum, maximum or both endstops",
            input={"direction": Field("string", enum=["min", "max", "both"],
                                      description="Endstop direction to home to: min, max or both"),
                   "axes": Field("array", items=Field("string", enum=["x", "y", "z"]),
                                 min_items=1, max_items=3,
                                 description="Axes to home, chosen from x, y and z")},
            output={"homed": Field("boolean", description="True when the homing command returned"),
                    "position": Field("array", items="integer", length=3, unit="step",
                                      description="Stage position after homing, in integer motor steps")})
    def home(self, direction, axes):
        endstops = getattr(self.native, "endstops", None)
        if endstops is None:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the board reports no endstop module, so it cannot home")
        endstops.home(direction=direction, axes=list(axes))
        return {"homed": True, "position": list(self.native.position)}

    @action(name="x-cap.rwb27.release_motors.v1", safe_state=True,
            description="De-energise the stepper motor coils with the firmware release command",
            output={"released": Field("boolean", description="True when the release command returned")})
    def release_motors(self):
        self.native.release_motors()
        return {"released": True}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="release_motors")
    def stop(self):
        """The only native stop path: the firmware release command de-energises the coils."""
        self.native.release_motors()

    def teardown(self):
        self.native.close()
