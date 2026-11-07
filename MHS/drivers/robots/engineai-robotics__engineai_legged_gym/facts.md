# Facts and tags for gh.engineai-robotics/engineai_legged_gym

Every fact cites its source at commit `1a659aa0aa77445766ecea6d95708a5812e9f290`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository provides the environments used to train engineai robots to walk on rough terrain with NVIDIA's Isaac Gym and includes sim2sim and sim2real components | vendor_doc | README.md:2-4 |
| The package declares mujoco and mujoco-python-viewer in install_requires | upstream_code | setup.py:22-23 |
| run_mujoco loads the model with mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path) | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:116 |
| Sim2simCfg points mujoco_model_path at resources/robots/zq_humanoid/urdf/zq_sa01.xml below the clone root | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:294 |
| The MJCF root element declares the model zqsa01 | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:1 |
| The model uses radians, resolves its meshes from ../meshes/, and its option element sets timestep 0.002 s, 50 Newton iterations, gravity 0 0 -9.81 and the RK4 integrator | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:2-3 |
| The world contains a plane floor and a base_link body at 0 0 1.5 that carries the free joint root | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:38-43 |
| The left leg has six limited hinge joints from leg_l1_joint to leg_l6_joint, each with its own range | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:54-88 |
| The right leg has six limited hinge joints from leg_r1_joint to leg_r6_joint, each with its own range | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:101-135 |
| The actuator section has twelve motor actuators, one per leg hinge, each with ctrllimited true and ctrlrange -200 200 | upstream_code | resources/robots/zq_humanoid/urdf/zq_sa01.xml:147-168 |
| run_mujoco computes PD torques, clips them to cfg.robot_config.tau_limit and writes the result to data.ctrl | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:193-197 |
| Sim2simCfg sets tau_limit to 200 for all 12 joints | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:302 |
| Sim2simCfg sets dt to 0.001 s and decimation to 10 | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:296-297 |
| run_mujoco overwrites model.opt.timestep with cfg.sim_config.dt before creating MjData | upstream_code | legged_gym/scripts/sim2sim_zqsa01.py:118 |

Limits: the driver declares none of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`; the
bridge checks every `ctrl` element against the model's `actuator_ctrlrange` (`resources/robots/zq_humanoid/urdf/
zq_sa01.xml:147-168`, each motor -200 to 200) before writing `data.ctrl`, and refuses an out-of-range value with
`MHS.SAFETY.ENVELOPE_VIOLATION` without calling `mj_step`. `ticks` is bounded by the bridge (1 to `max_ticks`,
10000 by default). The device is simulated (R0), so no limit is `operator_required` and no
`site-limits.example.json` is needed.

Contract: `MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step applies
the control vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`,
with 19 qpos values (a free base of 7 plus 12 hinges) and 18 qvel values (a free base of 6 plus 12 hinges). A reset
calls `mj_resetData` and `mj_forward`, restoring the model defaults; a seed is accepted for the class contract but
MuJoCo does not use it.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:zqsa01`, level F1, determinism `seeded` with
`seed_control` `none`, timestep 2 ms (the MJCF's `timestep='0.002'`, line 3), `realtime_factor` 0, clock `lockstep`,
reset `full`, snapshot and restore available. The gaps state that the fake is not MuJoCo, that it loads no meshes or
contacts, that the upstream sim2sim loop overrides the model step to 0.001 s and drives torques, and that no
trajectory was compared with the real engine or with a physical robot.

Safety: simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no physical
e-stop claim. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state
stays readable.

Tags: engineai, zqsa01, humanoid, legged, mujoco, simulation, robot
