# Facts and tags for gh.barisyazici/libfranka-sim

Every fact cites its source at commit `d893e17dc77a338a92a1673a8e616c8b251cc5a9`: `vendor_doc` is a text file of the
clone and `upstream_code` is code of the clone. The same facts are in `driver.py` (`facts = [...]`); the reference file
is generated from the driver, not from this page. The package covers the simulated Franka Hand
(`franka_sim.gripper.physics:FrankaHandPhysics`); the FCI arm bridge and the mobile-duo scene are not bound here.

| fact | source | ref |
|---|---|---|
| The simulator reports max_width as a constant 0.08 m, matching the real Franka Hand's 8 cm stroke | vendor_doc | docs/robot-state.md:202 |
| A grasp succeeds only when the stall distance d satisfies width - epsilon_inner < d < width + epsilon_outer | vendor_doc | docs/robot-state.md:203 |
| Neither gripper backend reads a real grip force, and the commanded force is not applied as a limit | vendor_doc | docs/robot-state.md:203 |
| A grasp drives the fingers fully closed and saturates the physics servo at FINGER_FORCE_LIMIT (100 N) whatever force the client asked for; force limiting is not implemented | vendor_doc | docs/robot-state.md:251-259 |
| stop() drives the fingers fully open and reuses the homing path; the real Franka Hand halts in place, so a client that stops mid-grasp sees the object released in the simulator | vendor_doc | docs/robot-state.md:271-276 |
| The kinematic backend ignores the commanded speed entirely | vendor_doc | docs/robot-state.md:201 |
| The physics move accepts speed for protocol compatibility but does not use it to pace the motion | upstream_code | franka_sim/gripper/physics.py:159-160 |
| The physics grasp accepts speed and force for protocol compatibility but does not use them | upstream_code | franka_sim/gripper/physics.py:189-190 |
| The reported temperature is a stub, constant 30 Cel | vendor_doc | docs/robot-state.md:204 |
| The shipped scene contains no graspable body, so by default every grasp closes on nothing and answers false | vendor_doc | docs/robot-state.md:209-211 |
| homing drives the fingers fully open, blocks until they settle, clears the grasp and stuck state and always reports success | upstream_code | franka_sim/gripper/physics.py:145-154 |
| move validates the width, drives the fingers and blocks until they settle or the timeout elapses, then sets is_stuck if they did not settle | upstream_code | franka_sim/gripper/physics.py:156-168 |
| get_state returns the summed width, maximum width, grasp flag and temperature from a lock-free snapshot | upstream_code | franka_sim/gripper/physics.py:222-231 |
| A width outside 0..max_width raises ValueError, which the gripper server turns into kFail | upstream_code | franka_sim/gripper/backend.py:37-38 |
| The upstream physics-hand tests call grasp with epsilon_inner 0.005 m and epsilon_outer 0.005 m | upstream_code | tests/test_gripper_physics.py:124 |
| The gripper command methods block until the fingers settle or the settle timeout elapses | vendor_doc | docs/robot-state.md:280-285 |

Limits (each `Limit` in `driver.py` cites its line; the value is the published `width_mm` / `open_width` in mm):

| capability | path | bound | source | ref |
|---|---|---|---|---|
| cap.manipulation.grasp.v1 | width (mm) | 0 .. 80 | vendor_doc | docs/robot-state.md:202 |
| cap.manipulation.release.v1 | open_width (mm) | 0 .. 80 | vendor_doc | docs/robot-state.md:202 |
| x-cap.barisyazici.hand_move.v1 | width (mm) | 0 .. 80 | vendor_doc | docs/robot-state.md:202 |

The source line states the stroke as 0.08 m and 8 cm; the catalogue class publishes the width in mm, so the driver
declares the same stroke as 80 mm. G4 reports a `REF_VALUE` warning because it compares the literal 80 with the
literal 0.08 on the cited line; the number is the same bound converted to the class's unit, not an invented one.

Safety: there is no hardware backend. The simulator is served as `mode = "simulated"`; every command blocks only in
the fake. The native stop is `FrankaHandPhysics.stop()`, which drives the fingers fully open (docs/robot-state.md
:271-276); `@estop` calls it and `x-cap.barisyazici.hand_stop.v1` is the `safe_state=True` action. The package
declares R2 because the simulated device is a robot gripper that closes under force and can pinch; the catalogue
class floor is R1. This package is model-authored and unreviewed and nothing here ran on a real hand.

Extension ids: `x-cap.barisyazici.hand_home.v1`, `x-cap.barisyazici.hand_move.v1` and
`x-cap.barisyazici.hand_stop.v1`. The catalogue has no class binding `robot.gripper` for homing, a width move or
stop (`cap.motion.home.v1`, `cap.motion.stop.v1` and `cap.motion.joint_position.v1` bind `robot.arm` or
`motion.axis`), so these are recorded in RESULT.json `catalogue_requests`.

Tags: franka, gripper, franka hand, grasp, manipulation, simulation
