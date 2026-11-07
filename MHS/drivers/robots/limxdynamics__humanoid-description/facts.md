# Facts and tags for gh.limxdynamics/humanoid-description

Every fact cites its source at commit `80fbd2d650c43c38916979c2a6eab7a4c79e38de`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (an MJCF, CMake or manifest file of the clone). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF file `HU_D03_description/xml/HU_D03_03.xml` (`models[0]`), as a
`MujocoDriver`. It reads the model file from the read-only clone; neither the model nor its meshes are copied into
the package. The upstream repository is a description package: its CMakeLists installs `meshes`, `urdf`, `xml` and
`world` and builds no executable (`HU_D03_description/CMakeLists.txt:11-41`), and its manifest declares no message,
service or action definition (`HU_D03_description/package.xml:3-24`). There is no ROS endpoint or type to bind, so
the package follows the MJCF instead of the card's static ROS family. The card's second model, the HU_D04 MJCF, is
not served.

| fact | source | ref |
|---|---|---|
| The repository provides URDF, MuJoCo MJCF and USD robot descriptions for the LimX HU_D03 and HU_D04 humanoids, for ROS, MuJoCo and NVIDIA Isaac Sim | vendor_doc | README.md:5 |
| The README's available-models table names HU_D03_03.xml and HU_D04_01.xml as the MuJoCo MJCF files for HU_D03 and HU_D04 | vendor_doc | README.md:9-12 |
| The README marks HU_D03 as discontinued and says to use HU_D04 instead | vendor_doc | README.md:18 |
| The MuJoCo quick start runs python -m mujoco.viewer with HU_D04_description/xml/HU_D04_01.xml | vendor_doc | README.md:50-51 |
| The HU_D03 package README names HU_D03_description/xml/HU_D03_03.xml as its MJCF | vendor_doc | HU_D03_description/README:5 |
| The HU_D04 package README names HU_D04_description/xml/HU_D04_01.xml as its MJCF | vendor_doc | HU_D04_description/README:5 |
| The HU_D03 CMakeLists installs the meshes, urdf, xml and world directories into the ROS package share for ROS 1 and ROS 2, or into etc/ when only AMENT_PREFIX_PATH is set; it defines no executable target | upstream_code | HU_D03_description/CMakeLists.txt:11-41 |
| The HU_D03 CMakeLists header reads '© [2025] LimX Dynamics Technology Co., Ltd. All rights reserved.' | upstream_code | HU_D03_description/CMakeLists.txt:1-3 |
| The HU_D03 package manifest names HU_D03_description, leaves its licence field as TODO, declares catkin/ament build types with roscpp/rclcpp dependencies, and declares no message, service or action definition | upstream_code | HU_D03_description/package.xml:3-24 |
| The README's licence section names the Apache License 2.0 and the LICENSE file | vendor_doc | README.md:58-60 |
| The HU_D03 MJCF root element declares the model name HU_D03_03 | upstream_code | HU_D03_description/xml/HU_D03_03.xml:1 |
| The HU_D03 MJCF compiler sets angle='radian' and meshdir='../meshes/HU_D03_03/' | upstream_code | HU_D03_description/xml/HU_D03_03.xml:2 |
| The HU_D03 MJCF sets its integration timestep to 0.001 s | upstream_code | HU_D03_description/xml/HU_D03_03.xml:16 |
| The HU_D03 base body base_link is placed at pos='0 0 1.0' and carries the free joint floating_base_joint | upstream_code | HU_D03_description/xml/HU_D03_03.xml:90-92 |
| The left_hip_pitch_joint is a hinge joint limited to -3.1415 to 3.1415 rad with armature 0.15257125 | upstream_code | HU_D03_description/xml/HU_D03_03.xml:102 |
| The actuator section declares motors for the legs, waist, head, arms and hands, and every motor sets ctrllimited='true' with an explicit ctrlrange | upstream_code | HU_D03_description/xml/HU_D03_03.xml:406-443 |
| The hip and knee motor ctrlranges are -120 to 120 and the ankle motor ctrlranges are -45 to 45 | upstream_code | HU_D03_description/xml/HU_D03_03.xml:407-419 |
| The waist motor ctrlranges are -45 to 45 and the head motor ctrlranges are -18 to 18 | upstream_code | HU_D03_description/xml/HU_D03_03.xml:421-426 |
| The left arm motor ctrlranges are -30 to 30 for the shoulder and elbow motors and -18 to 18 for the wrist and hand motors | upstream_code | HU_D03_description/xml/HU_D03_03.xml:428-434 |
| The right arm motor ctrlranges are -30 to 30 for the shoulder and elbow motors and -18 to 18 for the wrist and hand motors | upstream_code | HU_D03_description/xml/HU_D03_03.xml:436-442 |

Limits: the package declares no Limit of its own. The bridge derives `cap.world.step.v1` input `action.ctrl` from
the model itself, one interval per motor from `actuator_ctrlrange`: the model sets `ctrllimited="true"` and an
explicit `ctrlrange` on every motor (`HU_D03_description/xml/HU_D03_03.xml:406-443`). The derived reference is the
model file, and the bridge refuses an out-of-range element before writing `data.ctrl`. The derived per-actuator
length is the model's actuator count, not a safety bound; no bound was copied from a catalogue default or invented.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo, and publishes its own F0
contract (`fidelity_by_backend`); `fidelity` (F1) describes the real-engine backend. The stand-in reads the model
file for the joint dimensions (a free root joint, 37 hinges and six ball joints in this model), qpos0, the 31 motors
and their ctrlranges. The model's `<motor>` entries are torque actuators, so the stand-in's placeholder integration
lets each control value accelerate its joint against a placeholder damping; it resolves no mesh, inertia, gravity,
contact, equality (the ankle and waist rod linkages), tendon or sensor. The fake exposes no
`mj_getState`/`mj_setState`/`mj_stateSize`, so the bridge uses its basic checkpoint profile. MuJoCo was not
importable where the gate ran, so no trajectory was compared with the real engine. The gaps are listed in the
fidelity attributes of `driver.py`.

Model review (2026-11-05): the fake was published with the real engine's F1 contract and treated the torque motors'
control values as position targets, and it reset qpos to zeros (a zero free-joint quaternion); it now publishes F0,
integrates a torque-like placeholder and restores qpos0. The CMakeLists fact cites the whole conditional (11-41), the
manifest fact records its TODO licence, and two facts were added (the CMakeLists copyright header and the README's
Apache-2.0 licence section).

Tags: limx, hu-d03, humanoid, mujoco, description, simulation, robot
