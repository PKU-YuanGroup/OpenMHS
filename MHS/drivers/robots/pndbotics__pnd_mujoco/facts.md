# Facts and tags for gh.pndbotics/pnd_mujoco

Every fact cites its source at commit `84873eb3c4afd584d468864ba41527a1c14fb688`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE` or `path/in/clone.xml:LINE`). The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's main model, the MJCF scene `pnd_robots/adam_lite/scene.xml` (`models[0]`), as a
`MujocoDriver`. It reads the scene and the robot file it includes from the read-only clone; the package copies
neither the model nor its assets. The scene includes `adam_lite.xml` (`scene.xml:2`), a floating-base humanoid with
one free joint (`adam_lite.xml:100`), 23 hinge joints and 23 `<motor>` actuators (`adam_lite.xml:294-319`), and a
joint/IMU sensor block (`adam_lite.xml:321-405`).

| fact | source | ref |
|---|---|---|
| The repository has a simulator in simulate_python, implemented on pnd_sdk_python and mujoco, and the MJCF description files of the supported robots in pnd_robots | vendor_doc | README.md:24-26 |
| The simulator loads the scene named by config.ROBOT_SCENE with mujoco.MjModel.from_xml_path | upstream_code | simulate_python/pnd_mujoco.py:16 |
| config.py composes ROBOT_SCENE from ROBOT, whose default is adam_u_omnipicker; adam_lite, adam_pro and adam_sp are the other listed names | upstream_code | simulate_python/config.py:1-2 |
| config.py sets SIMULATE_DT to 0.001 s | upstream_code | simulate_python/config.py:21 |
| The simulator overwrites model.opt.timestep with config.SIMULATE_DT | upstream_code | simulate_python/pnd_mujoco.py:36 |
| The simulator advances the world with mujoco.mj_step in its physics loop | upstream_code | simulate_python/pnd_mujoco.py:74 |
| The card's main model is the MJCF scene pnd_robots/adam_lite/scene.xml, whose root element is '<mujoco model="adam_lite scene">' | upstream_code | pnd_robots/adam_lite/scene.xml:1 |
| The scene includes the robot model adam_lite.xml and sets the option timestep to 0.001 s | upstream_code | pnd_robots/adam_lite/scene.xml:2-18 |
| The robot model is rooted at '<mujoco model="adam_lite">' | upstream_code | pnd_robots/adam_lite/adam_lite.xml:1 |
| The robot's base is a free joint named floating_joint, so the model has a floating base (7 qpos and 6 qvel values) before the 23 hinge joints | upstream_code | pnd_robots/adam_lite/adam_lite.xml:100 |
| The model defines 23 <motor> actuators: 12 leg, 3 waist and 4 per arm; the two wristYaw motors are commented out | upstream_code | pnd_robots/adam_lite/adam_lite.xml:294-319 |
| The leg motor control ranges are hipPitch and kneePitch +-230, hipRoll +-160, hipYaw +-105, anklePitch +-40 and ankleRoll +-12 | upstream_code | pnd_robots/adam_lite/adam_lite.xml:295-306 |
| The waist motor control ranges are +-110, the shoulder ranges +-65 and the elbow ranges +-30 | upstream_code | pnd_robots/adam_lite/adam_lite.xml:307-318 |
| The model defines joint position, joint velocity and joint actuator force sensors for the actuated joints, plus an IMU at site imu (frame quaternion, gyro, accelerometer, frame position and linear velocity) | upstream_code | pnd_robots/adam_lite/adam_lite.xml:321-405 |
| The README advertises MuJoCo 3.2.0 and Python 3.8 or newer | vendor_doc | README.md:12-13 |

Limits: the bridge derives the `cap.world.step.v1` input `action.ctrl` from the model itself, one interval per
actuator from `actuator_ctrlrange` (`adam_lite.xml:294-319`; the class source is `upstream_code` and the bridge's
reference is the model file). No `operator_required` bound is needed: the model's own control ranges bound every
actuator, and this package declares no writable state of its own.

Units: the MJCF `ctrlrange` values are the simulator's actuator command units, which the model does not name; the
bridge publishes them as the numeric `action.ctrl` interval without a unit, and the `ticks` count is dimensionless.

Fidelity: the fake backend is a stand-in for the MuJoCo library (fake.py), not MuJoCo. It reads the scene and the
included robot file for the joint dimensions (30 qpos, 29 qvel), the 23 actuator ranges and the 1 ms timestep, but
its integration is a placeholder first-order motion, and it resolves no mesh, contact, equality, tendon or muscle
model. MuJoCo was not importable where the gate ran (no network, no pip), so no trajectory was compared with the real
engine; the upstream viewer, elastic hoist, joystick and DDS/ROS2 bridges are not modelled. The gaps are listed in
the `fidelity` attribute of `driver.py`; a site that needs MuJoCo's physics runs the driver with a backend that
imports MuJoCo.

The package is model-authored (`driver.lock.json` `authored_by` kind model) and unreviewed (`reviewed_by` null); it
was checked on the fake backend only, and no hardware was attached.

Tags: adam, adam-lite, humanoid, mujoco, pndbotics, robot, simulation
