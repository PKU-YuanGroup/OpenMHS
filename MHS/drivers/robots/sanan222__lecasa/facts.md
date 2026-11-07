# Facts and tags for gh.sanan222/lecasa

Every fact cites its source at commit `7dc0f63c0fc1519226262f0cc8cf48c6343043c0`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF or Python file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Model served

The package serves the card's robot model, `src/robot/so101_simplified.xml` (`models[1]`), the MJCF file that
`src/main.py:231` resolves and passes to the task controller as `robot_xml_path`. It is a self-contained model: its
`<compiler meshdir="assets">` resolves the meshes under `src/robot/assets`, which are in the clone.

The card's scene model `configs/kitchen_configs/kitchen_robot_scene.xml` (`models[0]`) is a RoboCasa kitchen export.
Its `<asset>` block names mesh and texture files by absolute Windows paths such as
`C:\Users\sanan\...\robocasa\models\assets\...` (line 7), and those files are not part of the clone, so the scene is
not self-contained. It is therefore not served; changing `model_path` serves it only with the RoboCasa asset tree
present. The scene embeds the same six SO101 position actuators (scene line 344), so the control contract of the two
models agrees.

## Facts

| fact | source | ref |
|---|---|---|
| The LeCasa README describes the project as a Real2Sim2Real platform for joint-level teleoperation, dataset collection, Vision-Language-Action policy training and evaluation in both simulation and real robots | vendor_doc | README.md:3 |
| The README says the work focuses on single- and multi-stage tasks in RoboCasa kitchen environments using the SO101 arm, with policies trained through the LeRobot framework | vendor_doc | README.md:4 |
| main.py resolves the robot model from src/robot/so101_simplified.xml and passes it to the task controller as robot_xml_path | upstream_code | src/main.py:231-247 |
| The model file declares '<mujoco model="so101_simplified">' | upstream_code | src/robot/so101_simplified.xml:2 |
| The model compiler declares angle='radian' and meshdir='assets' with autolimits='true', so its joint ranges are radians, its meshes resolve under src/robot/assets and a range implies the limit | upstream_code | src/robot/so101_simplified.xml:3 |
| The default joint class sets damping 0.60, frictionloss 0.052 and armature 0.028 | upstream_code | src/robot/so101_simplified.xml:6 |
| The default geom class sets contype 0, conaffinity 0 and friction '2.0 0.8 0.3' | upstream_code | src/robot/so101_simplified.xml:7 |
| The base body is at the origin with quat '1 0 0 0' | upstream_code | src/robot/so101_simplified.xml:13 |
| shoulder_pan is a hinge joint with range -1.9198621771937616 to 1.9198621771937634 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:29 |
| shoulder_lift is a hinge joint with range -1.7453292519943224 to 1.7453292519943366 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:47 |
| elbow_flex is a hinge joint with range -1.69 to 1.69 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:59 |
| wrist_flex is a hinge joint with range -1.6580628494556928 to 1.6580627293335335 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:77 |
| wrist_roll is a hinge joint with range -2.7438472969992493 to 2.841206309382605 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:93 |
| gripper is a hinge joint with range -0.17453297762778586 to 1.7453291995659765 rad and damping 0.60 | upstream_code | src/robot/so101_simplified.xml:111 |
| The model has six position actuators named shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper; each sets kp 17.8, forcerange -3.35 to 3.35 and a ctrlrange that rounds its joint range to five decimals | upstream_code | src/robot/so101_simplified.xml:157-162 |
| The model's equality section is empty | upstream_code | src/robot/so101_simplified.xml:165 |

## Limits

The bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself: one interval per actuator from
`actuator_ctrlrange` (`src/robot/so101_simplified.xml:157-162`). With `autolimits="true"` (`:3`) the explicit
`ctrlrange` of each position actuator is limited, and the six intervals are:

| actuator | ctrlrange (rad) |
|---|---|
| shoulder_pan | -1.91986 .. 1.91986 |
| shoulder_lift | -1.74533 .. 1.74533 |
| elbow_flex | -1.69 .. 1.69 |
| wrist_flex | -1.65806 .. 1.65806 |
| wrist_roll | -2.74385 .. 2.84121 |
| gripper | -0.17453 .. 1.74533 |

The class source is `upstream_code` and the reference is the model file, so no driver-declared or
`operator_required` bound is needed; there is no `site-limits.example.json`.

## Fidelity and the fake

The fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It parses the model file for the joint
count, the actuator count and the control ranges, but its integration is a placeholder first-order motion and it
resolves no mesh, contact, equality or tendon constraint. The model sets no `<option timestep>`, so the stand-in uses
MuJoCo's 2 ms library default; that number is test data in `fake.py` (marked `placeholder`), not a device bound.
MuJoCo was not importable where the gate ran, so no trajectory was compared with the real engine. The gaps are listed
in the `fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that
imports MuJoCo (`sim`), which would load this self-contained model and its `src/robot/assets` meshes.

Tags: arm, lecasa, manipulator, mujoco, robot, robocasa, simulation, so101
