# Facts and tags for gh.auturbo/stridesim

Every fact cites its source at commit `d941ee93cec051c9455cf0c699384fd5410d4d3f`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The flat task inherits the rough task and changes the terrain to a plane, removes the height scanner and the height_scan observation and disables the terrain-level curriculum | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/flat_env_cfg.py:7-23 |
| The rough task sets the scene robot to ANYMAL_D_CFG | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/rough_env_cfg.py:17 |
| The velocity commands are sampled from -1.0 to 1.0 for linear x, linear y and angular z, with heading from -pi to pi | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py:99 |
| The policy action is a joint-position action over all joints with scale 0.5 and the default joint offset | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py:108 |
| The ANYmal-D articulation sample uses 12 joint positions, 12 joint velocities and 12 previous-action values, and its policy observation is a 235-value vector that includes a height scan | upstream_code | exts/StrideSim/StrideSim/anymal_articulation.py:88-159 |
| The flat task removes the height_scan observation term | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/flat_env_cfg.py:21 |
| In the base configuration, the policy observation terms are base linear velocity, base angular velocity, projected gravity, velocity commands, joint positions, joint velocities, the last action and the height scan | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py:120-133 |
| The policy observation terms are concatenated into one array and observation corruption is enabled in the base configuration | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py:138-139 |
| The simulation advances by 0.005 s per physics step, the control decimation is 4 and an episode is 20.0 s long | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/velocity_env_cfg.py:295-298 |
| The flat task is registered as Template-Isaac-Velocity-Flat-Anymal-D-v0 with the external entry point omni.isaac.lab.envs:ManagerBasedRLEnv and the AnymalDFlatEnvCfg config | upstream_code | rl/StrideSim_RL/tasks/locomotion/velocity/config/anymal_d/__init__.py:9-15 |
| The upstream project requires Isaac Sim 4.0.0 and Isaac Lab v1.0.0 | vendor_doc | README.md:30-32 |

Limits: the driver declares none. The action space comes from the environment; on the fake it is an unbounded
Box of 12 elements (the ANYmal-D joint count of `anymal_articulation.py:88` and `:211`), because the real
`ANYMAL_D_CFG` action bound is defined by `omni.isaac.lab` outside this clone. `ticks` is bounded by the bridge
(1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine
`isaac:Template-Isaac-Velocity-Flat-Anymal-D-v0`, level F0 (kinematic placeholder; no rigid-body dynamics, contacts,
actuators, sensors or noise), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (decimation 4 times
sim.dt 0.005 s, `velocity_env_cfg.py:295-298`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled and that the fake was not compared with the upstream Isaac Sim environment.
The fake publishes the flat task's 12 action values and 48 observation values: the ANYmal-D sample's 235-value
observation (`anymal_articulation.py:144`) without its height scan, which the flat task removes
(`flat_env_cfg.py:21`). The values are synthetic and the real bounds are outside the clone.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable. No hardware backend is
declared, so a hardware run is impossible from this package.

Tags: anymal, anymal-d, isaac-lab, isaac-sim, locomotion, velocity-tracking, reinforcement-learning, simulation,
gymnasium
