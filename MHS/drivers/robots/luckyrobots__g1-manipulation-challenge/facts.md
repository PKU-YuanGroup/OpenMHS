# Facts and tags for gh.luckyrobots/g1-manipulation-challenge

Every fact cites its source at commit `0e9d1f9b61772905c9f7997b527f221dc7800fc9`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (an MJCF or Python file of the clone).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, `scene.xml` (the scene), which includes `g1.xml` (the robot).  Both files
are read from the read-only clone in place; the package copies neither the model nor its mesh assets.

| fact | source | ref |
|---|---|---|
| The scene is a MuJoCo scene named g1_table_red_block with the G1 robot, a ground plane, a brown table, a target table, a red cylindrical block on a free joint, and head, wrist and fixed cameras | upstream_code | scene.xml:1-5 |
| The scene includes g1.xml | upstream_code | scene.xml:8 |
| The robot model is g1_29dof_rev_1_0, which compiles angles in radians, resolves meshes from assets and uses autolimits | upstream_code | g1.xml:1-2 |
| The model integrates with the implicitfast scheme at a 0.005 s timestep, with a pyramidal cone and gravity 0 0 -9.81 | upstream_code | g1.xml:4-6 |
| The upstream runner also sets model.opt.timestep to 0.005, which it says must match training | upstream_code | run.py:527 |
| The robot base body pelvis is at -0.6 0 0.79 and carries the freejoint floating_base_joint | upstream_code | g1.xml:81-85 |
| The G1 has 29 actuated body degrees of freedom: 12 leg, 3 waist and 14 arm joints | vendor_doc | README.md:66-69 |
| The position actuator default class g1 sets inheritrange 1, so an actuator of that class takes its control range from the matching joint range | upstream_code | g1.xml:9-10 |
| The joint ranges are explicit, for example the left hip pitch joint is -2.5307 to 2.8798 rad | upstream_code | g1.xml:93 |
| The actuator section has 29 position actuators of class g1 for the body joints and then 14 position actuators for the finger joints | upstream_code | g1.xml:400-449 |
| The 14 finger actuators have a joint but no class, ctrlrange or inheritrange | upstream_code | g1.xml:435-449 |
| The right finger joints have explicit ranges: thumb 0 is -1.0472 to 1.0472, thumb 1 -1.0472 to 0.724312, index 0 0 to 1.5708 and index 1 0 to 1.74533 | upstream_code | g1.xml:347-382 |
| The red block is a free body at 0.0 0.026 0.85 with the freejoint red_block_joint and a cylinder of radius 0.02 and half-height 0.035 | upstream_code | scene.xml:80-84 |
| The source table top is a 0.8 by 0.5 m box at z 0.713 and the target table top is a 0.7 by 0.5 m box at z 0.613 | upstream_code | scene.xml:49-65 |
| The head camera head_cam is on the torso | upstream_code | g1.xml:207 |
| The wrist camera wrist_cam is on the right palm | upstream_code | g1.xml:344 |
| The upstream runner loads scene.xml, sets the 0.005 s timestep and initializes qpos x -0.6, z 0.76 and the default joint positions before stepping with mj_step | upstream_code | run.py:524-538 |
| The upstream runner writes the 29 body actuator targets and the right finger targets into data.ctrl, closing the grip to 0.8, -0.9, -1.5, 1.4, 1.5, 1.4 and 1.5 and opening it to 0.0 | upstream_code | run.py:442-462 |

## Limits

The bridge derives `cap.world.step.v1`'s `action.ctrl` from the model.  The 29 body position actuators are in default
class `g1`, which sets `inheritrange` 1 (`g1.xml:9-10`), so each of their control ranges is the matching joint range
(`g1.xml:93-382`).  The 14 finger position actuators have no class, no `ctrlrange` and no `inheritrange`
(`g1.xml:435-449`), so the real MJCF states no control bound for them and MuJoCo leaves their control unclamped.
The bridge therefore publishes one rule per channel: `action.ctrl[0]` to `action.ctrl[28]` the inherited joint ranges
(`upstream_code`, ref `scene.xml:actuator_ctrlrange`) and `action.ctrl[29]` to `action.ctrl[42]` `operator_required`,
so the endpoint refuses a step that sets a finger control (`MHS.SAFETY.LIMITS_UNSET`, before any native call) until
the site's `site-limits.json` bounds it.  `site-limits.example.json` is the operator example the gate serves: the
matching finger joint ranges (`g1.xml:254-289,347-382`), operator data, not bounds the model states.  (Model review
2026-11-05: the author's stand-in gave the finger actuators those joint ranges as an envelope published as the
model's ctrlrange, and a `FiniteCtrlLimitsBridge` subclass left them unbounded on a real model; the SDK's treatment
of actuators without a control range made both unnecessary.)  The joint `range` and `actuatorfrcrange` values are
model facts, not limits declared by this driver.

## Fidelity and safety

The fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo.  It reads the scene and its `g1.xml`
include for the two free joints, the 43 hinge joints, the 43 position actuators and the 29 inherited control ranges
(the 14 finger actuators have none), and the 0.005 s option step, but its integration is a placeholder first-order
motion and it resolves no contact, gravity, damping, joint limit, force limit, sensor or camera.  MuJoCo was not importable where the gate ran, so no trajectory
was compared with the real engine.  The gaps are listed in the `fidelity` attribute of `driver.py`.

The device is simulated (R0): there is no hardware backend and no e-stop path to a machine.  The e-stop is the runtime's software latch; after it no step or reset is accepted until `mhs.safety.reset`
clears the latch, and the state stays readable.

Tags: g1, humanoid, luckyrobots, manipulation, mujoco, pick-and-place, simulation, world
