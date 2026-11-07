# Facts and tags for gh.abmorobotics/rlroverlab

Every fact cites its source at commit `578906ad5c3383087aeec038be82b87e05d4ee2c`; all facts below are
`upstream_code`. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from
the driver, not from this page.

| fact | source | ref |
|---|---|---|
| AAURoverEnv-v0 is registered with entry_point 'rover_envs.envs.navigation.entrypoints:RoverEnv' and disable_env_checker=True | upstream_code | rover_envs/envs/navigation/robots/aau_rover/__init__.py:7-10 |
| RoverEnv extends Isaac Lab's ManagerBasedRLEnv | upstream_code | rover_envs/envs/navigation/entrypoints/rover_env.py:12 |
| RoverEnv.step delegates to ManagerBasedRLEnv.step | upstream_code | rover_envs/envs/navigation/entrypoints/rover_env.py:47-49 |
| The navigation task is configured with sim.dt 1/30 s, decimation 6 and episode_length_s 150 | upstream_code | rover_envs/envs/navigation/rover_env_cfg.py:352-356 |
| The action term has action_dim 2, commented as a linear velocity and an angular velocity | upstream_code | rover_envs/mdp/actions/ackermann_actions.py:70-72 |
| AckermannAction.process_actions computes the processed action as raw action times scale plus offset | upstream_code | rover_envs/mdp/actions/ackermann_actions.py:86-89 |
| The AAU rover task sets wheelbase_length 0.849, middle_wheel_distance 0.894, rear_and_front_wheel_distance 0.77, wheel_radius 0.1, min_steering_radius 0.8 and offset -0.0135 | upstream_code | rover_envs/envs/navigation/robots/aau_rover/env_cfg.py:24-34 |
| The observation group concatenates the last action, distance to target (scale 0.11), heading (scale 1/pi), angle difference (scale 1/pi) and the height scan (scale 1) | upstream_code | rover_envs/envs/navigation/rover_env_cfg.py:171-190 |
| The height scanner uses GridPatternCfg(resolution=0.05, size=[5.0, 5.0]) with max_distance=100.0 | upstream_code | rover_envs/envs/navigation/rover_env_cfg.py:106-114 |
| The height scan is the sensor height minus the ray hit height minus 0.26878, the distance between the sensor and the rover's base | upstream_code | rover_envs/envs/navigation/mdp/observations.py:35-45 |
| The terrain importer sets target_distance 9.0 | upstream_code | rover_envs/envs/navigation/utils/terrains/terrain_importer.py:167 |
| Targets are sampled on a circle of that radius around the environment origin with a uniformly random angle | upstream_code | rover_envs/envs/navigation/utils/terrains/terrain_importer.py:198-214 |
| The position command resamples every 150.0 s and its heading command is uniform in (-pi, pi) | upstream_code | rover_envs/envs/navigation/rover_env_cfg.py:269-276 |
| The task terminates on timeout, on success with a distance threshold of 0.18 and a contact force threshold of 1.0 | upstream_code | rover_envs/envs/navigation/rover_env_cfg.py:244-261 |
| The success test requires the distance to be below the configured threshold and the absolute heading error to be below 0.1 rad | upstream_code | rover_envs/envs/navigation/mdp/terminations.py:14-31 |

Limits: the driver declares none. The clone states no numeric action bounds: the space is supplied by the Isaac Lab
base outside this repository. The fake therefore publishes an unbounded two-element Box and the bridge derives no
action-value limit; the fidelity contract names this gap. The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:AAURoverEnv-v0 (analytic fake)`, level F0
(kinematic/analytic: positions are integrated directly from the two action values, with no dynamics), determinism
`seeded` with `seed_control` `parameter`, timestep 200 ms (`sim.dt = 1/30` s times `decimation = 6`,
`rover_env_cfg.py:352-353`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
what is not modelled: rigid-body dynamics and contacts, the wheel-level Ackermann mapping, the height scan, the
reward terms and terminations, the action-space bounds outside the clone, the terrain, spawn sampling and reset
options, and the fact that the fake was never compared with the upstream Isaac Sim environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: aau-rover, navigation, reinforcement-learning, isaac-lab, simulation, gymnasium
