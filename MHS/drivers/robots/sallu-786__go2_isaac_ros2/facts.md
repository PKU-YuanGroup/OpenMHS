# Facts and tags for gh.sallu-786/go2_isaac_ros2

Every fact cites its source at commit `839097f1be8931086671c8cafb670aee97144221`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository targets Isaac Sim 4.5.0 and Isaac Lab 2.1.0 or 2.1.1 on Ubuntu 22.04 | vendor_doc | README.md:4-8 |
| Isaac Sim 4.5.0, Isaac Lab 2.1.0 or 2.1.1 and ROS2 Humble are installed externally before the repository is used | vendor_doc | README.md:41-43 |
| The documented run command is python main.py from the repository root | vendor_doc | README.md:63-68 |
| The Go2 robot is the UNITREE_GO2_CFG articulation spawned at prim path {ENV_REGEX_NS}/Go2 | upstream_code | quadruped/go2/go2_env.py:47 |
| Go2RSLEnvCfg subclasses ManagerBasedRLEnvCfg and is the environment configuration | upstream_code | quadruped/go2/go2_env.py:139 |
| The action term is a JointPositionActionCfg for asset unitree_go2 over joint_names ['.*'] | upstream_code | quadruped/go2/go2_env.py:61-64 |
| The policy observation concatenates base_lin_vel, base_ang_vel, projected_gravity, base_vel_cmd, joint_pos, joint_vel, actions and height_scan | upstream_code | quadruped/go2/go2_env.py:74-94 |
| Projected gravity carries UniformNoiseCfg(n_min=-0.05, n_max=0.05) | upstream_code | quadruped/go2/go2_env.py:79-81 |
| The height_scan observation is clipped to (-1.0, 1.0) | upstream_code | quadruped/go2/go2_env.py:92-94 |
| The policy observation group sets enable_corruption=False and concatenate_terms=True | upstream_code | quadruped/go2/go2_env.py:96-98 |
| The height scanner uses a GridPatternCfg with resolution 0.1 and size [1.6, 1.0], offset 20 m above the base | upstream_code | quadruped/go2/go2_env.py:52-56 |
| The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading are (0, 0) | upstream_code | quadruped/go2/go2_env.py:106-113 |
| RewardsCfg and TerminationsCfg are empty pass classes, so the configuration declares no reward or termination terms | upstream_code | quadruped/go2/go2_env.py:120-129 |
| The environment uses decimation 8 and a simulation timestep of 0.005 s | upstream_code | quadruped/go2/go2_env.py:161-164 |
| The run loop derives its step period as sim.dt * decimation, 0.04 s for decimation 8 and sim.dt 0.005 s | upstream_code | main.py:93 |
| The configured episode length is 20.0 s and is_finite_horizon is False | upstream_code | quadruped/go2/go2_env.py:171-172 |
| The joint position action scale is 0.25 | upstream_code | quadruped/go2/go2_env.py:173 |
| The application instantiates Go2RSLEnvCfg() | upstream_code | main.py:51 |
| The run loop resets the environment with env.reset() and advances it with env.step(actions) | upstream_code | main.py:94-104 |
| get_rsl_flat_policy builds the environment with gym.make('Isaac-Velocity-Flat-Unitree-Go2-v0', cfg=cfg) | upstream_code | quadruped/go2/go2_ctrl.py:70-73 |

Limits: the driver declares none. The only bound is the fake environment's action space, which the gymnasium bridge
derives at run time (`Box` per-element bounds). Its width and bounds are placeholders, not a claim about the device:
the joint count comes from the external `UNITREE_GO2_CFG` articulation (quadruped/go2/go2_env.py:2,47), which the
clone does not state. The `ticks` bound (1 to 10000) is the bridge's `max_ticks`, not a device limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaaclab:Isaac-Velocity-Flat-Unitree-Go2-v0`, level F0
(kinematic stand-in, no dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 40 ms (decimation 8
times sim.dt 0.005 s, quadruped/go2/go2_env.py:161-164 and main.py:93), `realtime_factor` 0, clock `lockstep`,
reset `full`, no snapshot and restore, and `gaps` that name what is not modelled, including the placeholder space
widths and the fact that the upstream Isaac Sim/Isaac Lab environment was never run. The sim backend
(`gymnasium.make` of the registered task) was not exercised; it would use the task's registered default config, since
this family driver cannot pass a `Go2RSLEnvCfg` built from the clone without importing the clone.

Safety: simulated R0 device. It spawns a simulated articulation (quadruped/go2/go2_env.py:47) and has no hardware
backend, so it has no physical effect. The only stop is the runtime's software latch: after an e-stop no step or reset
is served until `mhs.safety.reset` clears the latch, and the last observation stays readable. No independent hardware
e-stop exists or is claimed.

Coverage: the card lists two entry symbols. This package covers the Go2 config only, `Go2RSLEnvCfg`
(`quadruped/go2/go2_env.py:139`); `SpotRSLEnvCfg` (`quadruped/spot/spot_env.py:139`) is the Spot variant and is not
served by this package.

Tags: isaac-sim, isaac-lab, unitree-go2, quadruped, reinforcement-learning, simulation, gymnasium
