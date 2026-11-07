# Facts and tags for gh.roboterax/humanoid-gym

Every fact cites its source at commit `ae46e201c85a2b17e7f2cea59a441dae7ea88a8f`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository is a reinforcement-learning framework based on NVIDIA Isaac Gym for humanoid locomotion that also integrates a sim-to-sim framework from Isaac Gym to MuJoCo | vendor_doc | README.md:17 |
| The README documents the MuJoCo sim-to-sim run as python scripts/sim2sim.py --load_model /path/to/export/model.pt | vendor_doc | README.md:126-130 |
| setup.py declares isaacgym (preview4), mujoco==2.3.6 and mujoco-python-viewer in install_requires | upstream_code | setup.py:43-52 |
| run_mujoco(policy, cfg) is the MuJoCo simulation loop | upstream_code | humanoid/scripts/sim2sim.py:87 |
| run_mujoco loads the MJCF with mujoco.MjModel.from_xml_path(cfg.sim_config.mujoco_model_path), overwrites model.opt.timestep with cfg.sim_config.dt, creates MjData and calls mujoco.mj_step | upstream_code | humanoid/scripts/sim2sim.py:98-101 |
| get_obs reads the orientation sensor (reordered to x, y, z, w) and the angular-velocity sensor | upstream_code | humanoid/scripts/sim2sim.py:70-80 |
| Sim2simCfg selects resources/robots/XBot/mjcf/XBot-L-terrain.xml only with --terrain and resources/robots/XBot/mjcf/XBot-L.xml otherwise | upstream_code | humanoid/scripts/sim2sim.py:178-182 |
| Sim2simCfg sets sim_duration 60 s, dt 0.001 s and decimation 10 | upstream_code | humanoid/scripts/sim2sim.py:183-185 |
| The loop computes PD torques, clips them to cfg.robot_config.tau_limit, writes them to data.ctrl and advances the model with mujoco.mj_step | upstream_code | humanoid/scripts/sim2sim.py:155-160 |
| Sim2simCfg sets tau_limit to 200 for all twelve joints | upstream_code | humanoid/scripts/sim2sim.py:190 |
| The MJCF root element declares the model XBot-L | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:1 |
| The model uses radians, resolves its meshes from ../meshes/, and its option element sets timestep 0.001 s, 50 solver iterations, the PGS solver and gravity 0 0 -9.81 | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:2-3 |
| The world contains a plane ground and a base_link body at 0 0 0.88 that carries three slide joints and one ball joint | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:157-168 |
| The left leg chain has six limited hinge joints, left_leg_roll_joint through left_ankle_roll_joint, each with its own range | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:394-431 |
| The right leg chain has six limited hinge joints, right_leg_roll_joint through right_ankle_roll_joint, each with its own range | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:444-481 |
| The actuator section declares twelve motor actuators, one per leg hinge, each with ctrllimited true and ctrlrange -200 200 | upstream_code | resources/robots/XBot/mjcf/XBot-L.xml:497-510 |

Limits: the driver declares none of its own. `cap.world.step.v1` takes `{ticks, action: {ctrl: [12 numbers]}}`; the
bridge checks every `ctrl` element against the model's `actuator_ctrlrange` (each motor -200 to 200,
`resources/robots/XBot/mjcf/XBot-L.xml:497-510`) before writing `data.ctrl`, and refuses an out-of-range value with
`MHS.SAFETY.ENVELOPE_VIOLATION` without calling `mj_step`. `ticks` is bounded by the bridge (1 to `max_ticks`, 10000
by default). The device is simulated (R0), so no limit is `operator_required` and no `site-limits.example.json` is
needed.

Contract: `MujocoDriver` serves `cap.world.step.v1` and `cap.world.reset.v1` on the `world` resource. A step applies
the control vector and integrates `ticks` times; the state is `{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`,
with 19 qpos values (three base slides, a base ball quaternion and twelve leg hinges) and 18 qvel values (three base
slide speeds, three base angular speeds and twelve hinge speeds). A reset calls `mj_resetData` and `mj_forward`,
restoring the model defaults; a seed is accepted for the class contract but MuJoCo does not use it.

The package serves `resources/robots/XBot/mjcf/XBot-L.xml`, the model sim2sim.py selects when `--terrain` is absent
(`humanoid/scripts/sim2sim.py:178-182`). The card also lists `XBot-L-terrain.xml`; it is not served here. The
upstream `run_mujoco` loop is not run: it needs a TorchScript policy and a `Sim2simCfg` defined only under
`__main__`, and it imports `humanoid.envs` (Isaac Gym).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:XBot-L`, level F1 (rigid-body dynamics with
contacts), determinism `seeded` with `seed_control` `none`, timestep 1 ms (the MJCF's `timestep='0.001'`, line 3),
`realtime_factor` 0, clock `lockstep`, reset `full`, snapshot and restore supported by the real engine. The gaps state
that the fake is not MuJoCo, that it loads no meshes or contacts, that the upstream loop overrides the step and drives
torques, that the sensors are not modelled, and that no trajectory was compared with the real engine or a physical
robot.

Safety: simulated R0 device. The e-stop is the runtime's software latch; there is no native stop and no physical
e-stop claim. After an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state
stays readable.

Tags: humanoid, xbot-l, legged, mujoco, sim2sim, simulation, robot
