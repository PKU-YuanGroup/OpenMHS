"""OpenMHS driver for gh.ethanjli/liquid-handling-robotics: the x-axis of a liquid-handling robot.

A direct Driver over the upstream high-level axis class ``lhrhost.robot.x_axis:Axis``.  The upstream class is an
asyncio object: its position properties are coroutines and its motion methods are coroutines, so every method here is
``async def`` and awaits ``self.native``.  The class talks to the robot's Arduino through a linear-actuator protocol
and a messaging stack; the hardware factory in ``native.py`` takes that stack from the integrator.

* reads: the physical position (cm) and the raw sensor position (unitless);
* one action: move by a relative physical displacement, in the physical unit of the x-axis (cm);
* the safe-state action and the e-stop both set every motor duty limit to zero, which makes the feedback controller
  brake instead of drive the axis.

No text of the clone states a travel range for the x-axis: the calibration and the position limits come from the
configuration of the assembled robot, so the move input is ``Limit.operator_required`` and every move is refused
``MHS.SAFETY.LIMITS_UNSET`` until the site's ``site-limits.json`` supplies the allowed relative travel.  This
package is model-authored and unreviewed; it is checked on the fake backend only.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read


class LiquidHandlingXAxis(Driver):
    device_id = "lhr-x-axis"
    device_kind = "motion.axis"
    mode = "hardware"
    risk = "R2"
    native = "lhrhost.robot.x_axis:Axis"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeXAxis"}
    vendor, model = "ethanjli", "liquid-handling-robotics x-axis"
    display_name = "Liquid-handling robot x-axis (sample stage)"
    tags = ["liquid handling", "robot", "linear actuator", "x-axis", "arduino", "asyncio"]
    facts = [
        Fact("The x-axis reports its physical position in centimetres", source="upstream_code",
             ref="lhrhost/robot/x_axis.py:100"),
        Fact("The x-axis constructs a linear-actuator protocol named XAxis on channel x", source="upstream_code",
             ref="lhrhost/robot/x_axis.py:86"),
        Fact("A physical position is converted from the sensor position with the slope and intercept of a linear "
             "calibration", source="upstream_code", ref="lhrhost/robot/axes.py:344-356"),
        Fact("Reading the physical position requests the Position channel and converts the last sensor position",
             source="upstream_code", ref="lhrhost/robot/axes.py:202-211"),
        Fact("move_by_physical_delta reads the current physical position, adds the delta and returns the final "
             "physical displacement", source="upstream_code", ref="lhrhost/robot/axes.py:158-166"),
        Fact("The feedback controller clamps its target position to the position limits Low and High",
             source="vendor_doc", ref="docs/source/messages/linearactuator.rst:240"),
        Fact("Actuator effort, roughly the signed motor duty cycle, must be between -255 and 255 inclusive",
             source="vendor_doc", ref="docs/source/messages/linearactuator.rst:174"),
        Fact("An actuator effort of 0 puts the motor in brake mode", source="vendor_doc",
             ref="docs/source/messages/linearactuator.rst:540"),
        Fact("A forwards actuator effort below the Low limit is set to 0 to brake the motor", source="vendor_doc",
             ref="docs/source/messages/linearactuator.rst:300"),
        Fact("The robot's Arduino exposes a USB serial command interface for positioning commands", source="vendor_doc",
             ref="README.rst:20"),
    ]
    safe_state = "motor duty cycle limits all zero, so the feedback controller brakes the axis instead of driving it"

    @read("physical_position", unit="cm",
          description="Physical position of the x-axis in the calibrated physical unit of the robot")
    async def physical_position(self):
        """Return the current physical position of the x-axis."""
        return await self.native.physical_position

    @read("sensor_position", unit="1",
          description="Raw sensor position of the x-axis before the physical calibration (unitless)")
    async def sensor_position(self):
        """Return the current raw sensor position of the x-axis."""
        return await self.native.sensor_position

    @action(
        name="x-cap.ethanjli.axis_move.v1",
        description="Move the x-axis by a relative physical displacement along its travel",
        input={
            "delta_cm": Field(
                "number", unit="cm",
                description="Signed displacement in centimetres; positive moves towards higher positions",
                limit=Limit.operator_required(
                    "no text file of the clone states the x-axis travel range: the calibration and the position "
                    "limits belong to the assembled robot, so the site supplies the allowed relative travel")),
        },
        output={
            "moved_cm": Field("number", unit="cm",
                              description="Physical displacement the axis reported after the move"),
            "physical_position": Field("number", unit="cm",
                                       description="Physical position of the x-axis after the move"),
        },
    )
    async def move_by_physical_delta(self, delta_cm):
        """Move the x-axis by a relative physical displacement and report the resulting position."""
        moved_cm = await self.native.move_by_physical_delta(delta_cm)
        return {"moved_cm": moved_cm, "physical_position": await self.native.physical_position}

    @action(
        name="x-cap.ethanjli.axis_stop.v1", safe_state=True,
        description="Brake the x-axis by setting every motor duty limit to zero",
        output={"stopped": Field("boolean", description="True once the zero motor duty limits were sent")},
    )
    async def stop_axis(self):
        """Set all motor duty limits to zero, the safe state of the axis."""
        await self.native.set_motor_limits(0, 0, 0, 0)
        return {"stopped": True}

    @estop
    async def stop(self):
        """The native safe state: all motor duty limits set to zero."""
        await self.native.set_motor_limits(0, 0, 0, 0)
