# Facts and tags for gh.embomaster/polysim

Every fact cites its source at commit `0fdb349785479b5c0c30d3c676fae67025b8d34a`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| PolySim is a whole-body-control training platform that integrates multiple heterogeneous simulators | vendor_doc | README.md:15 |
| The TODO list marks sim2sim in MuJoCo released and sim2real videos with the Unitree SDK on G1 still unchecked | vendor_doc | README.md:48-49 |
| The MuJoCo environment section installs mujoco and torch with pip | vendor_doc | README.md:219 |
| The MuJoCo simulator config sets _target_ to humanoidverse.simulator.mujoco.mujoco.MuJoCo, the simulator name to mujoco, fps 200, control_decimation 4, substeps 1 and gravity 0 0 -9.81 | upstream_code | humanoidverse/config/simulator/mujoco.yaml:5-18 |
| The class MuJoCo extends BaseSimulator | upstream_code | humanoidverse/simulator/mujoco/mujoco.py:15 |
| setup derives sim_dt as 1 / sim.fps and sim_substeps from sim.substeps | upstream_code | humanoidverse/simulator/mujoco/mujoco.py:57-58 |
| load_assets loads the MJCF with mujoco.MjModel.from_xml_path, overwrites opt.timestep with 0.005 s and constructs an MjData | upstream_code | humanoidverse/simulator/mujoco/mujoco.py:147-150 |
| The simulation loop writes the PD torques to data.ctrl and calls mujoco.mj_step | upstream_code | humanoidverse/simulator/mujoco/mujoco.py:524-526 |
| The scene declares the model g1_29dof scene and includes g1_29dof_old.xml | upstream_code | humanoidverse/data/robots/g1/scene_29dof.xml:1-2 |
| The included model declares g1_29dof and the compiler angle unit radian with meshdir meshes | upstream_code | humanoidverse/data/robots/g1/g1_29dof_old.xml:1-2 |
| The world body pelvis starts at 0 0 0.793 and carries the free joint floating_base_joint | upstream_code | humanoidverse/data/robots/g1/g1_29dof_old.xml:63-66 |
| The actuator section has 29 motor actuators, one per hinge joint, each with an explicit ctrlrange | upstream_code | humanoidverse/data/robots/g1/g1_29dof_old.xml:386-420 |
| The control ranges are -88 88 for the hips and waist yaw, -139 139 for the knees, -50 50 for the ankles and waist roll/pitch, -25 25 for the shoulders, elbows and wrist rolls, and -5 5 for wrist pitch/yaw | upstream_code | humanoidverse/data/robots/g1/g1_29dof_old.xml:387-419 |
| The Sim2Sim config points ROBOT_SCENE at ../humanoidverse/data/robots/g1/scene_29dof.xml | upstream_code | sim2real/config/g1_29dof_hist.yaml:2 |

## Limits

The driver declares no Limit of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [29 numbers]}}`; the
bridge reads the per-actuator control envelope from the loaded model's `ctrlrange`
(`humanoidverse/data/robots/g1/g1_29dof_old.xml:387-419`: hips and waist yaw -88 to 88, knees -139 to 139, ankles and
waist roll/pitch -50 to 50, shoulders, elbows and wrist rolls -25 to 25, wrist pitch/yaw -5 to 5) and refuses an
out-of-range element with `MHS.SAFETY.ENVELOPE_VIOLATION` before calling `mj_step`. `ticks` is bounded by the bridge
(1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`, no
`site-limits.example.json` is needed, and the control envelope cannot be widened by an operator overlay.

## Contract

`MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step writes the control
vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`. The served
scene has a free base (7 qpos, 6 qvel) and 29 hinge joints (29 qpos, 29 qvel), so the world state carries 36 qpos and
35 qvel values and 29 control values. The initial pelvis position in `qpos0` is 0 0 0.793 with the identity
quaternion. A reset calls `mj_resetData` and `mj_forward`, restoring the model defaults; a seed is accepted for the
class contract but MuJoCo does not use it.

## Fidelity

`driver.py` publishes engine `mujoco:g1_29dof`, level F1, determinism `seeded` with `seed_control` `none`,
`realtime_factor` 0, clock `lockstep`, reset `full` and snapshot/restore available (the bridge's qpos/qvel/ctrl/time
fallback; the stand-in implements no `mj_getState`/`mj_setState`). The time step is derived from the loaded model: the
scene and the included model declare no `<option timestep>`, the stand-in reports MuJoCo's default, and the upstream
simulator overwrites `model.opt.timestep` with 0.005 s (`mujoco.py:148`). The `gaps` in `driver.py` list every
difference between the stand-in and MuJoCo, and no trajectory was compared with the real engine.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch; the stand-in has no native stop and the package
claims no physical e-stop. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch,
and the model state stays readable. Hardware is never attached.

Tags: unitree, g1, humanoid, 29dof, mujoco, simulation, polysim
