# Facts and tags for gh.yueruyin/robot-unitree-g1

Every fact cites its source at commit `5de811e5ef85407d99f59ca605f90df6f51df601`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project describes itself as a control-system implementation for the Unitree G1 humanoid simulated with the MuJoCo physics engine, covering whole-body control, walking, squatting, arms and fingers | vendor_doc | README.md:5 |
| The project advertises full 53-degree-of-freedom whole-body control of the G1 | vendor_doc | README.md:12 |
| The documented way to run the simulation is `python deploy/deploy_mujoco53.py` | vendor_doc | README.md:65 |
| The deployment script imports mujoco and mujoco.viewer | upstream_code | deploy/deploy_mujoco53.py:6-7 |
| main() requires a positional config_file argument for the deployment config | upstream_code | deploy/deploy_mujoco53.py:1919 |
| main loads the MJCF named by the config with mujoco.MjModel.from_xml_path(xml_path), builds MjData, and overwrites model.opt.timestep with config.simulation_dt | upstream_code | deploy/deploy_mujoco53.py:1937-1939 |
| main opens a passive MuJoCo viewer over the model and data | upstream_code | deploy/deploy_mujoco53.py:1993 |
| The simulation loop advances the model with mujoco.mj_step(model, data) | upstream_code | deploy/deploy_mujoco53.py:2044 |
| The config points xml_path at resources/g1/scene53.xml | upstream_code | deploy/config/g1_53.yaml:3 |
| The config sets simulation_dt to 0.002 s | upstream_code | deploy/config/g1_53.yaml:8 |
| The scene model is named g1_53dof scene and includes g1_53dof.xml | upstream_code | resources/g1/scene53.xml:1-2 |
| The scene worldbody contains a plane floor named floor | upstream_code | resources/g1/scene53.xml:35-37 |
| The scene adds free-floating box1 and box2 bodies to the included robot | upstream_code | resources/g1/scene53.xml:39-58 |
| The scene adds two drawer slide joints with range -0.8 to 0 | upstream_code | resources/g1/scene53.xml:114-126 |
| The scene adds a free-floating glass_panel body | upstream_code | resources/g1/scene53.xml:132-133 |
| The included robot model is named g1_53dof and its compiler uses radians with meshes under meshes/ | upstream_code | resources/g1/g1_53dof.xml:1-2 |
| The robot pelvis body sits at 0.80 -1.55 0.763 and carries a free joint named floating_base_joint | upstream_code | resources/g1/g1_53dof.xml:96-100 |
| The actuator section declares one motor actuator per robot joint (53 motors) and none of them carries a ctrlrange attribute | upstream_code | resources/g1/g1_53dof.xml:812-887 |

Limits: the driver declares none.  The only bounds are those the catalogue and the bridge derive: `ticks` is bounded
from 1 to `max_ticks` (10000 by default) by the bridge input schema, and the scene's 53 motors declare no `ctrlrange`,
so the bridge publishes `action.ctrl` as `operator_required`: the endpoint refuses a step that sets it
(`MHS.SAFETY.LIMITS_UNSET`, before any native call) until the site's `site-limits.json` bounds it, and a
step without `action` keeps the controls as they are. `site-limits.example.json` is operator example data
(-10 to 10 for every control), not a bound of the model; the package invents none.  The model's joint ranges and `actuatorfrcrange` values constrain joint positions and torques in MuJoCo,
not the `data.ctrl` value that `cap.world.step.v1` writes.

Model shape as served: the scene has 83 qpos and 79 qvel values (three scene free bodies, two drawer slide joints, the
robot free base and 53 robot hinges) and 53 motor actuators.  The world state carries the full arrays.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:g1_53dof scene`, level F1, determinism `seeded`
with `seed_control` `none`, timestep 2 ms (the deployed `simulation_dt` 0.002 s of `deploy/config/g1_53.yaml:8`),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore available through the bridge's fallback copy
of time, qpos, qvel, act and ctrl.  The gaps say what is not modelled and that this package's fake was not compared
with the real engine.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (the MuJoCo model has no stop command); after
it no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: unitree, g1, humanoid, mujoco, simulation, whole-body, legged
