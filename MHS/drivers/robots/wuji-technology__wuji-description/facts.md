# Facts and tags for gh.wuji-technology/wuji-description

Every fact cites its source at commit `829c9aa27cb12c3a49d5b8d63c9869dd8f656702`: `vendor_doc` (a text file of the
clone) or `upstream_code` (an MJCF, XML, CMake, Python or text file of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF robot model `hand/body-with-soft/mjcf/left.xml` (`models[0]`), as
a `MujocoDriver`. The model is read from the read-only clone; the package copies neither the model nor its meshes.

| fact | source | ref |
|---|---|---|
| The card's model is the MJCF robot model hand/body-with-soft/mjcf/left.xml, whose root element is `<mujoco model="wujihand-left">` | upstream_code | hand/body-with-soft/mjcf/left.xml:1 |
| The model declares `<compiler angle="radian" />` | upstream_code | hand/body-with-soft/mjcf/left.xml:2 |
| The model sets `<option jacobian="sparse" integrator="RK4" timestep="0.002" solver="Newton" iterations="50" tolerance="1e-10" />` and a default joint armature 0.0002 with damping 0.0 | upstream_code | hand/body-with-soft/mjcf/left.xml:4 |
| The model's worldbody root is the body left_palm_link | upstream_code | hand/body-with-soft/mjcf/left.xml:35 |
| The root body left_palm_link declares an inertial and two mesh geoms and no joint before its first child body left_finger1_link1 | upstream_code | hand/body-with-soft/mjcf/left.xml:35-37 |
| The first finger joint left_finger1_joint1 declares no type attribute, axis 0 1 0, range 0.0475 1.6033, actuatorfrcrange -0.4452 0.4452 and armature 0.0005 | upstream_code | hand/body-with-soft/mjcf/left.xml:39 |
| The last finger joint left_finger5_joint4 declares range -0.4683 1.5735 | upstream_code | hand/body-with-soft/mjcf/left.xml:160 |
| The actuator section declares 20 position actuators, one per finger joint, each with kp, kv, ctrlrange and forcerange; the first, left_finger1_joint1_actuator, states ctrlrange 0.0475 1.6033 | upstream_code | hand/body-with-soft/mjcf/left.xml:170-191 |
| The last position actuator, left_finger5_joint4_actuator, states ctrlrange -0.4683 1.5735 | upstream_code | hand/body-with-soft/mjcf/left.xml:190 |
| The repository describes itself as a "Robot model description package for the Wuji Hand and related accessories" providing URDF, MuJoCo (MJCF) and USD assets for simulation and visualization | vendor_doc | README.md:5 |
| The README describes hand/body-with-soft/ as the hand-body variant with a soft pad fixed to the thumb | vendor_doc | README.md:120 |
| The README's MuJoCo command loads a hand/body-with-soft model with `python -m mujoco.viewer --mjcf=hand/body-with-soft/mjcf/right.xml` | vendor_doc | README.md:124 |
| The ROS2 package wuji_description is described as a robot model description package with URDF, MJCF and USD assets for simulation and ROS2 visualization | upstream_code | hand/body/package.xml:4-6 |
| The CMake package installs the mjcf directory with the other model assets under share/wuji_description | upstream_code | hand/body/CMakeLists.txt:6-9 |
| display.launch.py returns three nodes, robot_state_publisher, joint_state_publisher_gui and rviz2, and no controller, command topic, service or action | upstream_code | hand/body/launch/display.launch.py:19-45 |

## Limits

The bridge derives one `action.ctrl` interval per actuator from the model's `actuator_ctrlrange` at run time; this
model's 20 position actuators each declare an explicit `ctrlrange` (`hand/body-with-soft/mjcf/left.xml:171-190`), so
the step input is bounded by the model itself. The package declares no `Limit` of its own; no bound was copied from a
catalogue default or invented, and no operator-required limit is needed.

## Fidelity

The fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the same MJCF for the joint
dimensions (20 joints without a type attribute; no free joint) and the 20 explicit actuator control ranges, but it
integrates a placeholder first-order motion and resolves no mesh, contact, soft-pad deformation, actuator dynamics,
equality, tendon or sensor. MuJoCo was not importable where the gate ran, so no trajectory was compared with the real
engine. The fake therefore publishes its own F0 contract (`fidelity_by_backend["fake"]`, engine
`analytic:stand-in mujoco module (no physics)`); the class-level F1 `mujoco:wujihand-left` contract describes the real
engine path, a backend that imports MuJoCo, which was not run (model review, 2026-11-05: the fake previously published
the F1 contract). The gaps of both contracts are listed in `driver.py`.

## Tags

hand, mujoco, robot, simulation, wuji, dexterous
