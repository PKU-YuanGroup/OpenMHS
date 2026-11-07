# Facts and tags for gh.ccrprepo/robomimic_deploy

Every fact cites its source at commit `3a72ec1a55dcf155be88c9dcc4a32ecb5c11e313`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

The package serves the card's first model, the MJCF scene `g1_description/scene.xml` (`models[0]`), as a
`MujocoDriver`. The scene includes the robot model `g1_description/g1_29dof_rev_1_0.xml`, which declares one free
joint, 29 hinge joints and 29 `<motor>` actuators, so the served integration state has 36 qpos and 35 qvel values and
the step action carries 29 ctrl values. The bridge reads the model from the read-only clone in place; neither the
model nor its STL meshes are copied into the package.

| fact | source | ref |
|---|---|---|
| The repository is a multi-policy robot deployment framework based on a state-switching mechanism, with the included policies designed for the Unitree G1 robot (29-DoF) | vendor_doc | README.md:9 |
| The deployment framework applies only to G1 robots with a 3-DOF waist, and a waist fixing bracket must be unlocked before the framework can be used normally | vendor_doc | README.md:14 |
| The MuJoCo simulation is started with python deploy_mujoco/deploy_mujoco.py | vendor_doc | README.md:79-82 |
| The simulation configuration selects g1_description/scene.xml as the model, sets simulation_dt to 0.003 s and sets control_decimation to 7 | upstream_code | deploy_mujoco/config/mujoco.yaml:1-3 |
| The scene MJCF includes the robot model g1_29dof_rev_1_0.xml | upstream_code | g1_description/scene.xml:1-2 |
| The robot MJCF is model g1_29dof_rev_1_0, uses radian angles and keeps its meshes in meshes/ | upstream_code | g1_description/g1_29dof_rev_1_0.xml:1-2 |
| The robot MJCF sets its integration step to 0.002 s and selects the implicit integrator | upstream_code | g1_description/g1_29dof_rev_1_0.xml:8-9 |
| The pelvis body starts at z 0.793 m and carries the free joint floating_base_joint | upstream_code | g1_description/g1_29dof_rev_1_0.xml:50-52 |
| The left hip pitch joint has a range of -2.5307 to 2.8798 rad and an actuator force range of -88 to 88 | upstream_code | g1_description/g1_29dof_rev_1_0.xml:59 |
| The robot MJCF declares 29 motor actuators, one per joint from left_hip_pitch_joint to right_wrist_yaw_joint, and every motor element carries only name and joint attributes (no ctrlrange) | upstream_code | g1_description/g1_29dof_rev_1_0.xml:245-275 |
| The robot MJCF defines four IMU sensors: a gyro and an accelerometer at imu_in_torso and imu_in_pelvis, each with a noise and cutoff value | upstream_code | g1_description/g1_29dof_rev_1_0.xml:277-282 |
| The MuJoCo loop loads the scene with mujoco.MjModel.from_xml_path, creates MjData, overrides m.opt.timestep with simulation_dt and takes the actuator count from m.nu | upstream_code | deploy_mujoco/deploy_mujoco.py:33-37 |
| The MuJoCo loop computes a PD torque from the policy output and writes it to d.ctrl before every mujoco.mj_step(m, d) | upstream_code | deploy_mujoco/deploy_mujoco.py:80-82 |
| The MuJoCo loop runs control_decimation physics steps per policy update and reads qpos[7:], qvel[6:], qpos[3:7] and qvel[3:6] as joint positions, joint velocities, base quaternion and base angular velocity | upstream_code | deploy_mujoco/deploy_mujoco.py:84-90 |
| The real robot configuration expects 29 joints and a control_dt of 0.02 s | upstream_code | deploy_real/config/real.yaml:2-7 |
| The README reports that only the Charleston dance policy is verified stable on physical robots and that all other movements are not recommended for physical deployment | vendor_doc | README.md:143-154 |

Limits: the bridge derives `cap.world.step.v1`'s `action.ctrl` from each actuator's `ctrlrange`
(`mhs.bridge.mujoco.MujocoBridge.action_limits`). This MJCF's 29 `<motor>` elements have no `ctrlrange`
(`g1_29dof_rev_1_0.xml:246-274`), so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none. The joint `range` and `actuatorfrcrange` values
(`g1_29dof_rev_1_0.xml:59` and following joints) are model facts, not limits of this driver: the upstream
writes the PD torque to `d.ctrl` without clipping it.

Fidelity: the fake backend is a stand-in for the MuJoCo library (`fake.py`), not MuJoCo. It reads the scene and the
included robot MJCF for the joint dimensions, the 29 actuators and the 0.002 s option step, but its integration is a
placeholder motion of each actuated joint, it leaves the free base fixed, and it resolves no mesh, contact, equality,
tendon or actuator constraint. The upstream simulation overrides the model step with `simulation_dt` 0.003 from
`mujoco.yaml:2` (`deploy_mujoco.py:30,35`); this package serves the MJCF's own 0.002 s step. MuJoCo itself was not
importable where the gate ran (no network, no pip), so no trajectory was compared with the real engine. The gaps are
listed in the `fidelity` attribute of `driver.py`.

Tags: robomimic, unitree-g1, g1, humanoid, 29-dof, mujoco, simulation, robot
