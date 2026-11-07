# Facts and tags for gh.ll7/robot_sf_ll7

Every fact cites its source at commit `53721be3248600e08641a9816d094b605e3c93e4`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Robot SF registers the single-robot environment under the env id "robot" with RobotEnv as its class, and calls it the primary supported training/evaluation environment | upstream_code | robot_sf/gym_env/env_registry.py:165-174 |
| RobotEnv is the Gymnasium environment facade and the public environment API for simulation episodes | upstream_code | robot_sf/gym_env/robot_env.py:526-531 |
| The default DifferentialDriveSettings sets max_linear_speed 2.0, max_angular_speed 1.0, max_linear_accel 1.0 and max_angular_accel 1.0 | upstream_code | robot_sf/robot/differential_drive.py:29-44 |
| The linear speed is clipped to min_linear_speed, which is 0.0 when allow_backwards is false | upstream_code | robot_sf/robot/differential_drive.py:103-108 |
| The action space is a Box over commanded linear and angular accelerations, with low [-max_linear_decel, -max_angular_accel] and high [max_linear_accel, max_angular_accel] | upstream_code | robot_sf/robot/differential_drive.py:335-343 |
| The robot observation space is a Box with low [min_linear_speed, -max_angular_speed] and high [max_linear_speed, max_angular_speed]: the linear and angular speed | upstream_code | robot_sf/robot/differential_drive.py:315-323 |
| Commanded accelerations are clipped to the acceleration bounds, integrated over the timestep, and the resulting speeds are clipped to min_linear_speed..max_linear_speed and -max_angular_speed..max_angular_speed | upstream_code | robot_sf/robot/differential_drive.py:181-193 |
| The default simulation timestep is time_per_step_in_secs 0.1 s and the default simulation duration is sim_time_in_secs 200.0 s | upstream_code | robot_sf/sim/sim_config.py:257-261 |
| max_sim_steps is the ceiling of sim_time_limit divided by the timestep | upstream_code | robot_sf/robot/robot_state.py:63-68 |
| A simulation step increments the timestep, adds the timestep to the elapsed time and sets is_timeout at max_sim_steps | upstream_code | robot_sf/robot/robot_state.py:120-130 |
| is_terminal is true when the route is complete, the time limit expired or the robot collided with a pedestrian, obstacle or robot | upstream_code | robot_sf/robot/robot_state.py:70-82 |
| RobotEnv.step returns (observation, reward, terminated, truncated, info) and always reports truncated False | upstream_code | robot_sf/gym_env/robot_env.py:1264-1270 |
| RobotEnv.reset applies the seed through global_reset_seed and _apply_reset_seed and forwards seed and options to gymnasium Env.reset | upstream_code | robot_sf/gym_env/robot_env.py:1272-1284 |
| The environment action space is the robot factory's action space, and its observation space is fused_sensor_space of the robot observation, a target sensor and a LiDAR sensor | upstream_code | robot_sf/gym_env/env_util.py:363-378 |
| The default LiDAR scanner has max_scan_dist 10.0 and num_rays 272 | upstream_code | robot_sf/sensor/range_sensor.py:146-148 |
| The fused observation space is a Dict of drive_state and rays Box members | upstream_code | robot_sf/sensor/sensor_fusion.py:71-89 |

## Limits

The driver declares no `Limit`. The only step bound is the action space, which `GymnasiumDriver` derives from the
backend environment at load time: the fake's action space is a `Box` over two commanded accelerations. The four
`DifferentialDriveSettings` defaults in the table are configuration defaults, not a device bound: a deployment may
configure different acceleration, speed and reverse-driving settings, and the published envelope then comes from that
configured environment's action space. No catalogue class or safety limit is narrowed by this package, and the device
is simulated (R0), so no limit is `operator_required`.

## Fidelity contract

`fidelity` in `driver.py`: engine `robot_sf:RobotEnv-kinematic`, level `F0`, determinism `seeded` with `seed_control`
`parameter`, timestep 100 ms (`time_per_step_in_secs` 0.1 s, `robot_sf/sim/sim_config.py:260`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled: no pedestrians, obstacles,
contacts or collisions, a reduced observation (8 constant rays instead of the default 272), a simple unicycle Euler
integration instead of wheel-speed odometry, no reward model, no wall-clock pacing and no rendering, recording or
telemetry. The fake was never compared with the upstream environment.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch (a simulator has no native stop to engage); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch, and the world state stays readable. No
hardware backend, stop path or operator bound is claimed.

Tags: social-navigation, robot, pedestrian, gymnasium, simulation
