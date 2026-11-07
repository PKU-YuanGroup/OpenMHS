OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and is not a reimplementation or compatible dialect of an Anthropic research preview.

# Facts and tags for gh.geo-jtao/unitree_robot_sim

Every fact cites the pinned clone at commit `49fb7fa50e0c3b65dd2a07ac4df370ba781858b8`.
`upstream_code` refs name `path/in/clone:LINE`; `vendor_doc` refs name text
files of the clone. The same facts are declared in `driver.py`; the reference
files are generated from the driver, not from this page.

## Shape and scope

The repository is a ROS 1 Gazebo simulation and robot-description collection
for Unitree quadruped robots. It also ships MJCF models, and the B2 MuJoCo
subdirectory says to open `./xml/scene.xml` with the MuJoCo `simulate` program
(`src/unitree_ros/robots/b2_description_mujoco/README.md:4-6`).

DEVIATION FROM THE CARD: the card names `RosDriver` (family `ros`), but its own
candidate classes are `cap.world.reset.v1`, `cap.world.step.v1` and
`cap.world.seed.v1`, its `models` list is a set of MJCF scenes, and its mock
strategy prefers the upstream simulator. The clone's ROS 1 side is a Gazebo
runtime with joint command/state topics (`unitree_guide`, `unitree_controller`,
`unitree_legged_control`), not a world reset/step service owned by this clone,
and it has no Python environment object. This package therefore serves the
card's B2 MJCF scene through `MujocoDriver`. The production path would be the
official MuJoCo engine loading the same file; the ROS graph, the
`unitree_guide` controller, mapping, navigation and SLAM are NOT COVERED.

The selected model is `src/unitree_ros/robots/b2_description_mujoco/xml/scene.xml`
(`scene.xml:1-2`), which includes `b2.xml`. It is read from the read-only clone
in place; the package does not copy or modify it. The model's sensor definitions
are not read or published by the world-step package.

## Facts

| fact | source | ref |
|---|---|---|
| The project provides a mapping and navigation package for Unitree quadruped robots in Gazebo. | vendor_doc | README.md:2 |
| The B2 MuJoCo README instructs the user to install mujoco, enter the b2_description_mujoco directory and run 'simulate ./xml/scene.xml' to open the model. | vendor_doc | src/unitree_ros/robots/b2_description_mujoco/README.md:4-6 |
| The unitree_ros README says its ROS simulation packages load robots and joint controllers in Gazebo for low-level torque, position and angular-velocity control, and that the Gazebo simulation cannot do high-level walking. | vendor_doc | src/unitree_ros/README.md:2 |
| The selected file is an MJCF scene named 'b2 scene' that includes b2.xml. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/scene.xml:1-2 |
| The scene adds a directional light and a plane floor geom named floor. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/scene.xml:19-22 |
| The included B2 model root is named b2 and its compiler element declares radian angles, meshdir ../meshes and autolimits true. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:1-2 |
| The B2 default class gives joints damping 1 and armature 0.1. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:7 |
| The base_link body starts at pos 0 0 0.8 and carries the free joint floating_base_joint. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:52-54 |
| The FL leg has a hip joint range -0.87 to 0.87 rad, a thigh joint range -0.94 to 4.69 rad and a calf joint range -2.82 to -0.43 rad; the FR, RL and RR legs declare the same ranges. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:73-156 |
| The actuator block declares twelve motor actuators: the hip and thigh motors have ctrlrange -200 to 200 and the calf motors have ctrlrange -300 to 300. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:170-182 |
| The model declares joint position and velocity sensors for the twelve leg joints plus body quaternion, gyro, accelerometer and frame-position sensors. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:185-216 |
| The keyframe named home sets a 19-value qpos with the base at 0 0 0.5 and the identity quaternion, and a 12-value ctrl. | upstream_code | src/unitree_ros/robots/b2_description_mujoco/xml/b2.xml:218-220 |
| unitree_guide's CMakeLists sets ROBOT_TYPE Go1 (Go1 and A1 supported), SIMULATION ON and REAL_ROBOT OFF. | upstream_code | src/unitree_guide/unitree_guide/CMakeLists.txt:4-9 |
| With REAL_ROBOT on, unitree_guide defines COMPILE_WITH_REAL_ROBOT and, for A1, uses the unitree_legged_sdk_3.2 headers and libraries. | upstream_code | src/unitree_guide/unitree_guide/CMakeLists.txt:87-95 |
| The vendored unitree_ros directory carries the BSD 3-Clause License of HangZhou YuShu Technology (Unitree Robotics). | upstream_code | src/unitree_ros/LICENSE:1-3 |

## Contract

`cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`. The bridge
derives the per-actuator bounds from the model's `actuator_ctrlrange`; the
driver does not add or widen a bound. `cap.world.reset.v1` takes the class's
optional `seed` metadata and runs `mj_resetData` + `mj_forward`. The bridge
reports `determinism: none` and `seed_control: none`; the reset seed is not used
by `mj_resetData`, and `cap.world.seed.v1` is not served.

The device is simulated (`world.sim`) at R0: direct world stepping is isolated
simulated state and no physical robot, actuator torque, sensor stream or
hardware command is exposed. The e-stop is a software latch that blocks step
and reset until `mhs.safety.reset`; it is not a hardware e-stop and makes no
physical-safety claim. No `estop_physical_ref` is claimed.

## Fidelity and fake limits

The real sim path would use the official `mujoco` module. It was not installed
or run here, so no trajectory, timing or determinism claim is made for it. The
B2 scene declares no `<option>` timestep; the 2 ms value in the fidelity
contract is the package fake's placeholder step (also the MuJoCo library
default), not a bound sourced from the clone.

`backends["fake"]` is a package-local stand-in for the `mujoco` module. It
parses the same MJCF scene and its include for the joint shape, qpos0, the twelve
actuators and their ctrlranges, and the option timestep. It loads no mesh,
texture or inertia, resolves no contact, friction, tendon, equality or
actuator-force constraint, and its `mj_step` is a torque-like placeholder: each
motor's control value accelerates its joint through a placeholder gain against a
placeholder damping, while the free base stays at qpos0. Reset restores qpos0 as
`mj_resetData` does (base at 0 0 0.8, identity quaternion, hinges at 0; reviewer
r20: the author's stand-in reset everything to zero, including the base
quaternion, and copied the control value into the joint velocity). It is an
analytic stand-in, not a recording, and replays no captured traffic. The bridge
uses its basic snapshot profile (time, qpos, qvel, act and ctrl), not the full
MuJoCo integration state.

With the real engine, reset leaves the robot 0.8 m above the floor with zero
torque, so it falls under gravity; the keyframe `home` (base at 0.5 m, a standing
pose) is not applied. The repository's primary runtime, `unitree_guide` (Go1 or
A1 in Gazebo by default, or a real robot when `REAL_ROBOT` is compiled on), and
the other vendored robot descriptions are NOT COVERED.

## Tags

`unitree`, `b2`, `quadruped`, `mujoco`, `mjcf`, `simulation`, `ros`, `gazebo`,
`world.sim`, `step`, `reset`
