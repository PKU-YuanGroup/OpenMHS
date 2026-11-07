# Facts and tags for gh.agilexrobotics/piper_isaac_sim

Every fact cites its source at commit `8e1f88fdb7afca49c40e9a0c1c01cc588e86f0d2`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF, CMake, manifest, xacro or launch file of the clone). The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

The package serves the card's first model, the MJCF file
`piper_description/mujoco_model/piper_description.xml` (`models[0]`), as a `MujocoDriver`. The model file and its
meshes are read in place from the read-only clone; nothing is copied or imported. The upstream repository is a
description and asset repository, not a ROS control runtime: its README describes an Isaac Sim workflow
(`README.md:3-37`), the `piper_description` CMakeLists only installs directories and defines no executable
(`piper_description/CMakeLists.txt:1-38`), and the manifest declares no message, service or action
(`piper_description/package.xml:3-24`). The display launch starts only `robot_state_publisher`,
`joint_state_publisher` and `rviz2` (`piper_description/launch/piper_with_gripper/display_urdf.launch.py:23-60`).
The only controller reference is a `gazebo_ros2_control` plugin whose parameters are loaded from
`piper_gazebo/config/ros2_controllers.yaml`, a package and file absent from this clone
(`piper_description/urdf/piper_description.xacro:531-535`). There is no pinned ROS endpoint or type, so the
package follows the MJCF instead of the card's `family:ros` / `RosDriver` guess.

| fact | source | ref |
|---|---|---|
| The README describes an Isaac Sim workflow: install the NVIDIA driver, Omniverse and Isaac Sim, open the USD asset from the content browser, and press play to start the simulation | vendor_doc | README.md:3-37 |
| The piper_description CMakeLists is an ament_cmake description build: it installs the launch, meshes, rviz, urdf and mujoco_model directories and defines no executable target | upstream_code | piper_description/CMakeLists.txt:1-38 |
| The piper_description manifest declares ament_cmake with runtime dependencies joint_state_publisher, joint_state_publisher_gui, rviz2 and xacro; it declares no message, service or action definition | upstream_code | piper_description/package.xml:3-24 |
| The display launch starts robot_state_publisher, joint_state_publisher (or its GUI) and rviz2, and starts no controller or command node | upstream_code | piper_description/launch/piper_with_gripper/display_urdf.launch.py:23-60 |
| The xacro adds a gazebo_ros2_control plugin that loads its controller parameters from piper_gazebo/config/ros2_controllers.yaml; the piper_gazebo package and that file are not part of this clone | upstream_code | piper_description/urdf/piper_description.xacro:531-535 |
| The MJCF root declares the model name piper_description and the compiler angle in radians | upstream_code | piper_description/mujoco_model/piper_description.xml:1-2 |
| The MJCF worldbody is a fixed-base chain of six hinge joints (joint1 to joint6) followed by two slide joints (joint7 and joint8); it declares no free joint | upstream_code | piper_description/mujoco_model/piper_description.xml:16-50 |
| The hinge joint ranges are joint1 -2.618 to 2.168 rad, joint2 0 to 3.14 rad, joint3 -2.967 to 0 rad, joint4 -1.745 to 1.745 rad, joint5 -1.22 to 1.22 rad and joint6 -2.0944 to 2.0944 rad; the slide joint ranges are joint7 0 to 0.035 and joint8 -0.035 to 0 | upstream_code | piper_description/mujoco_model/piper_description.xml:20-50 |
| The actuator section declares eight position actuators, joint1 to joint8, and every actuator sets ctrllimited=true with an explicit ctrlrange; it also sets forcelimited=true and a forcerange | upstream_code | piper_description/mujoco_model/piper_description.xml:60-69 |
| The MJCF asset section names ten mesh files under ../meshes: base_link, link1 to link8 and gripper_base | upstream_code | piper_description/mujoco_model/piper_description.xml:4-15 |
| The MJCF contains no <option> element and no timestep attribute | upstream_code | piper_description/mujoco_model/piper_description.xml:1-70 |
| The actuator ctrlranges are wider than the joint ranges for joint1 (ctrlrange -2.618 to 2.618, range -2.618 to 2.168), joint4 (-1.832 to 1.832 against -1.745 to 1.745), joint6 (-3.14158 to 3.14158 against -2.0944 to 2.0944), joint7 (0 to 0.0475 against 0 to 0.035) and joint8 (-0.0475 to 0 against -0.035 to 0); joint2's ctrlrange ends at 3.14158 and its range at 3.14 | upstream_code | piper_description/mujoco_model/piper_description.xml:20-68 |
| The card's second model, piper_no_gripper_description.xml, is a six-joint MJCF with six position actuators and no gripper; it is not the model this package serves | upstream_code | piper_description/mujoco_model/piper_no_gripper_description.xml:1-54 |
| The piper_description manifest declares its licence as 'TODO: License declaration' | upstream_code | piper_description/package.xml:8 |
| The vendored realsense2_description manifest declares the Apache License 2.0 | upstream_code | realsense2_description/package.xml:8 |

Limits: the package declares no `Limit` of its own. The bridge derives `cap.world.step.v1` input `action.ctrl` from
the model itself, one interval per actuator from `actuator_ctrlrange`. Every position actuator sets
`ctrllimited="true"` with an explicit `ctrlrange`
(`piper_description/mujoco_model/piper_description.xml:61-68`), so the model is the source of the derived intervals:
joint1 -2.618..2.618, joint2 0..3.14158, joint3 -2.697..0, joint4 -1.832..1.832, joint5 -1.22..1.22,
joint6 -3.14158..3.14158, joint7 0..0.0475 and joint8 -0.0475..0. The bridge refuses an out-of-range element before
writing `data.ctrl`. The derived per-actuator length is the model's actuator count, not a safety bound; no bound was
copied from a catalogue default or invented. Note that the model's joint1 joint range ends at 2.168 while its
actuator ctrlrange ends at 2.618; the driver publishes the actuator ctrlrange exactly as the MJCF states it and does
not widen or narrow it.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the pinned MJCF
for the eight joints (eight qpos and eight qvel) and eight position actuators with their ctrlranges, but its
integration is a placeholder first-order motion toward the control target and it loads no mesh, contact, equality,
tendon, actuator dynamics or sensor. The model's `<position>` actuators are position servos with kp and forcerange;
the stand-in's first-order step is not that servo and ignores forcerange, damping, inertia and joint limits. The
fake exposes no `mj_getState`/`mj_setState`/`mj_stateSize`, so the bridge uses its basic checkpoint profile. The
model declares no `<option timestep>`, so the fake uses MuJoCo's library default 0.002 s as a placeholder; the
reported 2.0 ms comes from the fake, not from a line of the clone. MuJoCo was not importable where the gate ran, so
no trajectory was compared with the real engine and no Isaac Sim or USD asset was opened. Reviewer change: the fake
now publishes its own F0 contract (`analytic:stand-in mujoco module (no physics)`) through `fidelity_by_backend`,
with the stand-in gaps; the class-level `fidelity` keeps the F1 `mujoco:piper_description` contract and the gaps of
the real engine path, which was not run. Both gap lists now also say that the ctrlranges are wider than the joint
ranges of joint1, joint4, joint6, joint7 and joint8, so the bridge's step envelope admits targets that drive those
position servos against their joint ranges.

Safety: the device is simulated (`mode: simulated`) and the package has no hardware backend. `cap.world.step.v1`
and `cap.world.reset.v1` are R0 simulation-state actions, so the package's risk is R0, the card's floor. An e-stop
latches in software and refuses step and reset until an operator reset; the integration state is kept readable. No
physical emergency stop, hardware interlock or safety certification is claimed. The upstream licence is NOASSERTION
and the manifest leaves it as a TODO, so the card needs the owner's publication decision.

Tags: agilex, piper, isaac-sim, mujoco, robot, arm, description, simulation.
