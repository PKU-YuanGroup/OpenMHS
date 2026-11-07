# Facts and tags for gh.zhefan-xu/isaac-go2-ros2

The package follows the card at commit `f201692a5519e6e6ed058637ce93a2f603f016f2`. Every fact below is copied from
`driver.py` `facts = [...]`; the reference file is generated from the driver, not from this page. `vendor_doc` is a
text file of the clone (only `README.md` here); `upstream_code` is a code line or comment.

| fact | source | ref |
|---|---|---|
| The repository provides a Unitree Go2 quadruped robot simulation on Isaac Sim / Isaac Lab with a ROS 2 interface | vendor_doc | README.md:14 |
| Isaac Sim 4.5, Isaac Lab 2.1.0 and ROS 2 Humble must be installed before the simulation runs | vendor_doc | README.md:26-30 |
| The ROS 2 interface subscribes to /unitree_go2/cmd_vel and publishes front-camera, LIDAR, odometry and pose topics | vendor_doc | README.md:64-80 |
| The Go2 is an Isaac Lab articulation spawned at {ENV_REGEX_NS}/Go2 | upstream_code | go2/go2_env.py:47 |
| The height scanner is a grid at 0.1 resolution over a size of 1.6 x 1.0 attached to the Go2 base | upstream_code | go2/go2_env.py:52-58 |
| The Go2RSLEnvCfg default scene uses 2 environments with an env_spacing of 2.0 | upstream_code | go2/go2_env.py:142 |
| The action term is a JointPositionActionCfg over all joints matched by the regular expression .* | upstream_code | go2/go2_env.py:64 |
| The observation group contains base linear velocity, base angular velocity, projected gravity, the base velocity command, joint positions, joint velocities, the last action and a height scan clipped to -1..1 | upstream_code | go2/go2_env.py:75-94 |
| The velocity command ranges are all zero: lin_vel_x, lin_vel_y, ang_vel_z and heading | upstream_code | go2/go2_env.py:110-111 |
| The environment config sets decimation to 8, sim.dt to 0.005 s and the render interval to the decimation | upstream_code | go2/go2_env.py:161-165 |
| The episode length is 20.0 s and the finite-horizon flag is False, so the environment does not truncate on time | upstream_code | go2/go2_env.py:171-172 |
| Joint position actions are scaled by 0.25 | upstream_code | go2/go2_env.py:173 |
| The height scanner update period is decimation * sim.dt | upstream_code | go2/go2_env.py:175-176 |
| The environment is created with gym.make('Isaac-Velocity-Rough-Unitree-Go2-v0', cfg=cfg) and wrapped in RslRlVecEnvWrapper | upstream_code | go2/go2_ctrl.py:81-82 |
| The command input is a float32 tensor of shape (num_envs, 3) | upstream_code | go2/go2_ctrl.py:14-16 |
| The ROS 2 cmd_vel callback writes Twist.linear.x, linear.y and angular.z into the three command columns | upstream_code | ros2/go2_ros2_bridge.py:320-323 |
| The launcher overrides decimation with ceil(1/sim.dt/cfg.freq) | upstream_code | isaac_go2_ros2.py:41 |
| The sim.yaml default is 1 environment and a control frequency of 40 | upstream_code | cfg/sim.yaml:4-5 |

## Limits

The driver declares none. The only bound of `cap.world.step.v1` is the environment action space, which the bridge
derives from the fake (`action.values` from -1.0 to 1.0 per element here); `ticks` is bounded by the catalogue class
(1 to 10000) and `max_ticks` of the family driver. Both are test data or class defaults, not a source of a physical
bound. The device is simulated (R0), so no limit is `operator_required` and no operator overlay is needed.

## Fidelity contract

`engine` `isaaclab:Isaac-Velocity-Rough-Unitree-Go2-v0`, level `F0` (the deployed fake is kinematic; it models no
rigid-body, contact, actuator or sensor dynamics), determinism `seeded` with `seed_control` `parameter`, timestep
40 ms (decimation 8 x sim.dt 0.005 s, `go2/go2_env.py:161,164`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot or restore. The `gaps` in `driver.py` name the fake dimensions that are placeholders, the absent
wall-clock pacing and the fact that the fake was never compared with the upstream environment.

## Safety

The device is simulated (R0). The e-stop is the runtime's software latch: after it, no step, reset or seed is
accepted until `mhs.safety.reset` clears the latch, and the last state stays readable. There is no hardware backend,
no physical stop and no claim that any hardware path was tested. The package is model-authored and unreviewed.

Tags: unitree-go2, quadruped, isaac-sim, isaac-lab, reinforcement-learning, ros2, simulation, gymnasium
