# Facts and tags for gh.asig-x/jeplo

Every fact cites its source at commit `460e2272907af053d6e66b57fec71fdbe6ca1774`: `upstream_code` (a code file of
the clone) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository targets a quadrupedal Unitree Go2 with a single Mid-360 LiDAR | vendor_doc | README.md:9 |
| Unitree-Go2-Locomotion is registered with entry point go2_parkour.tasks.go2_loco_env:Go2LocoEnv and disable_env_checker=True | upstream_code | training/go2_parkour/go2_parkour/tasks/__init__.py:6-9 |
| Go2LocoEnv extends DirectRLEnv and is constructed from a Go2LocoEnvCfg and an optional render_mode | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env.py:78-82 |
| The config sets action_space to 12, action_scale to 0.25 and action_target_clip to (-100.0, 100.0) | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py:178-180 |
| Each action is applied as action * action_scale plus the default joint positions plus the motor zero offset, and the resulting joint position target is clamped to action_target_clip | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env.py:469-473 |
| An episode lasts 25.0 s; the physics timestep is 1/200 s and decimation is 4 | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py:161-165 |
| The default scene has 4096 environments with 10 m spacing | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py:185 |
| The observation config defines a 10-step history of 45 proprioception values, 300 height-scan values, 50 privileged values and 45 critic proprioception values | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env_cfg.py:248-262 |
| _get_observations returns a dict with a policy tensor and a depth tensor of num_depth_stack frames | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env.py:665-671 |
| The Mid-360 ray pattern defaults to 25 vertical and 60 horizontal rays | upstream_code | training/go2_parkour/go2_parkour/sensor/lidar_pattern.py:86-88 |
| An episode ends when roll or pitch exceeds 1.5 rad, base height is below -5.0, or the episode timestep reaches max_episode_length - 1 | upstream_code | training/go2_parkour/go2_parkour/tasks/go2_loco_env.py:835-847 |
| The play script launches AppLauncher before any environment is created | upstream_code | training/scripts/play.py:63-64 |
| The play script creates the environment with gym.make(task_name, cfg=env_cfg, render_mode=...) | upstream_code | training/scripts/play.py:110 |
| The install instructions create a Python 3.11 environment and install isaaclab[isaacsim,all]==2.3.2.post1 and torch 2.7.0 | vendor_doc | README.md:28-32 |
| The README notes that a decent computer with an Nvidia GPU is needed for simulation and control | vendor_doc | README.md:75 |

## Limits

The driver declares no numeric limit of its own. The action width is 12 (`go2_loco_env_cfg.py:178`), but the
action-space bounds belong to Isaac Lab's `DirectRLEnv`, which is outside the clone, so the fake's action `Box` is
unbounded and the bridge publishes no finite action limit. The clone's `action_scale` 0.25 and
`action_target_clip` (-100.0, 100.0) (`go2_loco_env_cfg.py:179-180`) are used in the fake's kinematic update but are
not presented as input bounds. The catalogue bounds `cap.world.step.v1`'s `ticks` (1 to the bridge's `max_ticks`,
10000) and `cap.world.seed.v1`'s `seed` (non-negative), enforced by the runtime. No field is `operator_required`: the
device is simulated R0 and the operator has no device bound to supply.

## Fidelity

The deployed model is F0 (kinematic/analytic): engine `isaaclab:Unitree-Go2-Locomotion`, determinism `seeded` with
`seed_control` `parameter`, `timestep_ms` 20.0 (one control step; the physics timestep is 5 ms with decimation 4),
`realtime_factor` 0, clock `lockstep`, reset `full`, `snapshot_restore` false. The fake keeps the policy width (845)
and depth shape (2 x 25 x 60) but not the values. The `gaps` in `driver.py` state the missing dynamics, contacts,
sensors, rewards, terminations and the fact that the upstream stack was never started.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch: after it, no step or reset is accepted until
`mhs.safety.reset` clears the latch, the fake is not advanced, and the state stays readable. No physical stop exists
and none is claimed.

Tags: unitree-go2, quadruped, isaac-lab, isaac-sim, lidar, locomotion, reinforcement-learning, simulation, gymnasium
