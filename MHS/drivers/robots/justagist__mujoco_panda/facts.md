# Facts and tags for gh.justagist/mujoco_panda

Every fact cites its source at commit `207938fbc99bd3f8a4b05d35c18dd999b7a8dd7f`: `vendor_doc` (README.md of the
clone) or `upstream_code` (a text file of the clone, `path:LINE`). The same facts are in `driver.py`; the
reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is archived, targets the deprecated mujoco_py bindings, is Panda-specific and is no longer maintained; it is superseded by mujoco_robot | vendor_doc | README.md:3-10 |
| The project provides Franka Emika Panda model definitions for MuJoCo, a MuJoCo-based robot simulator, a Python 3 API for the simulated robot, direct position and torque controllers and a task-space hybrid force motion controller | vendor_doc | README.md:12-16 |
| The robot models are in mujoco_panda/models and the API is documented in MujocoRobot and PandaArm | vendor_doc | README.md:18-40 |
| The library requires mujoco_py, numpy, scipy and quaternion and is used after sourcing set_env.sh | vendor_doc | README.md:24-32 |
| The main scene is the MJCF model named mujoco_panda_model | upstream_code | mujoco_panda/models/franka_panda.xml:2 |
| The main scene includes other/simple_scene.xml and panda/assets.xml and pulls in the arm_with_gripper body tree, the torque_with_gripper actuators and the ft_sensor sensors | upstream_code | mujoco_panda/models/franka_panda.xml:4-21 |
| The main scene selects the elliptic contact cone and enables gravity; its option element sets no timestep | upstream_code | mujoco_panda/models/franka_panda.xml:8-10 |
| The seven arm joints are hinges panda_joint1 to panda_joint7 with ranges: joints 1, 3, 5 and 7 +-2.8973, joint 2 +-1.7628, joint 4 -3.0718 to -0.4 and joint 6 -1.6573 to 2.1127 | upstream_code | mujoco_panda/models/panda/arm_with_gripper.xml:10-46 |
| The end-effector site is ee_site on panda_link7 | upstream_code | mujoco_panda/models/panda/arm_with_gripper.xml:50 |
| The hand has two slide joints, panda_finger_joint1 and panda_finger_joint2, each with range 0 to 0.04 m | upstream_code | mujoco_panda/models/panda/gripper.xml:8-14 |
| The actuator block has seven motor actuators with ctrlrange +-87 for arm joints 1 to 4 and +-12 for arm joints 5 to 7, plus two position actuators for the gripper fingers with ctrlrange 0 to 0.04 | upstream_code | mujoco_panda/models/panda/actuators/torque_with_gripper.xml:2-12 |
| The model carries a force sensor and a torque sensor at ee_site | upstream_code | mujoco_panda/models/panda/sensors/ft_sensor.xml:2-3 |
| The asset block compiles angles in radians and declares the collision and visual STL meshes | upstream_code | mujoco_panda/models/panda/assets.xml:3-25 |

## Limits

The only numeric envelope is the model's own actuator control range, derived by the bridge at run time from
`actuator_ctrlrange` in `mujoco_panda/models/panda/actuators/torque_with_gripper.xml:2-12` (seven motor channels:
+-87 for joints 1 to 4, +-12 for joints 5 to 7) and the two position channels `0 0.04` for the gripper fingers.
The driver declares no bound of its own, so there is no Limit with a hand-copied number and no
`site-limits.example.json`: the bridge publishes the derived `action.ctrl` limits and the runtime refuses an
element outside them before any native call.

## Tags

`franka`, `panda`, `mujoco`, `simulation`, `robot-arm`, `justagist`

## Mock path

The card prefers the upstream simulator, but the upstream simulator is built on the deprecated `mujoco_py`
bindings (README.md:3-6, `mujoco_panda/mujoco_robot.py:53-55`) and neither `mujoco_py` nor `mujoco` is installed
where the gate runs. `fake.py` is therefore a package-local stand-in for the `mujoco` module the MuJoCo bridge
imports. It reads the same MJCF file and its includes for the model shape but integrates a placeholder motion; the
driver's fidelity `gaps` state every difference. The real `sim` path (the official `mujoco` module loading the same
scene) was not run.
