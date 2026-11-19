# Facts and tags for gh.ferrolho/rotary-inverted-pendulum

Every fact cites its source at commit `bd911756ec8d14947a29ae582721f067b47d8847`, with the path from the clone
root. The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver,
not from this page.

| fact | source | ref |
|---|---|---|
| The simulation class RotaryInvertedPendulumEnv subclasses gym.Env | upstream_code | policy/pendulum_env.py:387 |
| The action space is a Box with low -1.0 and high 1.0 and one element | upstream_code | policy/pendulum_env.py:731-733 |
| The constructor defaults action_mode to accel, max_accel_rad_s2 to MAX_ACCEL_RAD_S2 and max_velocity_rad_s to MAX_VELOCITY_RAD_S | upstream_code | policy/pendulum_env.py:397-406 |
| MAX_ACTION_DELTA_RAD is 0.10, CONTROL_FREQ_HZ is 50.0, MAX_VELOCITY_RAD_S is 3.5 and MAX_ACCEL_RAD_S2 is 150.0 | upstream_code | policy/pendulum_env.py:146-155 |
| MOTOR_LIMIT_RAD is math.radians(135.0) and MOTOR_SAFE_LIMIT_RAD is math.radians(125.0) | upstream_code | policy/pendulum_env.py:66-67 |
| The MJCF option sets a 0.001 s timestep and the implicitfast integrator | upstream_code | policy/pendulum_env.py:343 |
| GRAVITY is 9.81 | upstream_code | policy/pendulum_env.py:79 |
| The pendulum URDF inertial origin is xyz 0 0 -0.051 and its mass value is 0.014 | upstream_code | model/model.urdf:119-121 |
| In accel mode the action is scaled by max_accel_rad_s2, the integrated command is clipped to max_velocity_rad_s and the position target is clipped to MOTOR_SAFE_LIMIT_RAD | upstream_code | policy/pendulum_env.py:1050-1077 |
| With obs_include_velocities enabled, the non-firmware observation frame is [motor_pos, sin(theta), cos(theta), motor_vel, pen_vel, prev_action] | upstream_code | policy/pendulum_env.py:1248-1254 |
| The default observation stacks obs_history_len = 4 frames | upstream_code | policy/pendulum_env.py:426 |
| theta = phi - pi, so theta = 0 is upright and the joint angle phi = 0 is hanging down | upstream_code | policy/pendulum_env.py:1180-1185 |
| A reset draws the motor position uniformly from plus or minus 0.7 times MOTOR_SAFE_LIMIT_RAD and, for a hanging start, the pendulum angle uniformly from -0.05 to 0.05 rad | upstream_code | policy/pendulum_env.py:808-817 |
| episode_length_s defaults to 8.0 s | upstream_code | policy/pendulum_env.py:406 |
| _max_steps is int(episode_length_s * control_freq_hz) | upstream_code | policy/pendulum_env.py:681 |
| An episode is truncated when _step_count >= _max_steps | upstream_code | policy/pendulum_env.py:1148 |
| The step terminates when terminate_on_hard_stop is true and abs(motor_pos) is at least MOTOR_LIMIT_RAD, subtracting hard_stop_penalty from the reward | upstream_code | policy/pendulum_env.py:1144-1146 |
| The reward weights are k_pen_vel 0.001, k_motor_pos 0.5, k_motor_vel 0.005 and k_action 0.20 | upstream_code | policy/reward.py:27-30 |
| The quadratic cost sums theta, pendulum velocity, motor position, motor velocity, action, action_delta and motor_vel_delta squared terms, with weights on all except theta | upstream_code | policy/reward.py:94-102 |
| compute_reward returns float(alive + bonus - cost) | upstream_code | policy/reward.py:116 |
| The environment declares render_fps 50 in its metadata | upstream_code | policy/pendulum_env.py:395 |

## Limits

The driver declares no `Limit` of its own. The only input bound is the environment's action space, which the
Gymnasium bridge derives from the fake's copied `Box`: `action.values` is one element, minimum -1.0 and maximum 1.0,
with source `upstream_code` and the ref `policy/pendulum_env.py:731-733` (`action_space_ref`). The bridge additionally
bounds `ticks` by 20 to 10000 physics ticks in multiples of 20 from `timing_by_backend` (decimation 20); those are
bridge schema bounds, not driver `Limit` rules. The device is simulated (R0), so no bound is `operator_required` and
there is no operator overlay.

## Fidelity contract

The contract is in `driver.py` `fidelity` and describes the model as deployed, which is the package's pure Python
reduced model, not the upstream MuJoCo engine: engine `analytic:rotary-inverted-pendulum`, level F0, determinism
`seeded` with seed control `parameter`, physics timestep 1 ms and control decimation 20 (20 ms control period),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps list the missing MuJoCo
rigid-body dynamics and contacts, PD actuator, friction, firmware measurement model, boxcar smoothing and
randomisation, the unexercised 135 degree hard-stop termination, the absent wall-clock pacing, the fact that the
fake was not compared with the upstream environment, and the absent snapshot/restore.

## Safety

Simulated R0 device. The e-stop is the runtime's software latch; the upstream environment and the fake expose no
native stop, so after an e-stop every step, reset and seed is refused until `mhs.safety.reset` clears the latch.
The state stays readable and the simulation does not advance. No physical device, no hardware backend and no
e-stop path to a machine are claimed.

Tags: rotary-inverted-pendulum, furuta-pendulum, reinforcement-learning, simulation, gymnasium, mujoco.

The analytic fake's toy acceleration transition is not a sourced Furuta equation and does not meet the F1 contact
requirement. RealRotaryInvertedPendulumEnv (policy/real_env.py:76) and its LowLevelClient binary serial path are
outside this package; no physical-rig stop is offered.
