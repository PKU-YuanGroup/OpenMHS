# Facts and tags for gh.adipandas/gym_multirotor

Every fact cites its source at commit `c13535254b6f6ecc84a32e49320cd989b54304d5`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

This package serves the QuadrotorPlusHoverEnv-v0 variant named by the first entry symbol of the task card.  The
repository also registers TiltrotorPlus8DofHoverEnv-v0 and QuadrotorXHoverEnv-v0 (`gym_multirotor/__init__.py:14-25`);
they need separate driver packages with their own model files and observation sizes.

| fact | source | ref |
|---|---|---|
| QuadrotorPlusHoverEnv-v0 is registered with frame_skip=5, env_bounding_box=1.2 and randomize_reset=True | upstream_code | gym_multirotor/__init__.py:8-12 |
| The QuadrotorPlusHoverEnv constructor defaults are xml_name quadrotor_plus.xml, frame_skip 5, env_bounding_box 1.2 and randomize_reset False | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:17-18 |
| The policy action range is -1.0 to 1.0 and the safe policy range is -0.8 to 0.8 | upstream_code | gym_multirotor/envs/mujoco/base_env.py:197-203 |
| step clips the action to the policy range and maps it to motor inputs hover_force + action * 2.0 / (policy_range[1] - policy_range[0]) | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:40-41 |
| step updates the time counter and clips the action to the policy range before the motor input is computed | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:59-61 |
| hover_force is mass * gravity_mag * 0.25 | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:28 |
| The observation is an 18-value vector: the position error (3), the flattened 3x3 rotation matrix, linear velocity (3) and angular velocity (3), concatenated in that order | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:87-116 |
| The reward sums a position term (position error norm times -position_reward_constant), an orientation term, linear and angular velocity terms, an action term, the alive bonus, the goal bonus, the bound penalty and a velocity-towards-goal term, all times reward_scaling_coefficient | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:132-153 |
| The reward constants default to bonus_to_reach_goal 15.0, max_reward_for_velocity_towards_goal 2.0, position 5.0, orientation 0.02, linear velocity 0.01, angular velocity 0.001, action 0.0025, reward_for_staying_alive 5.0 and reward_scaling_coefficient 1.0 | upstream_code | gym_multirotor/envs/mujoco/base_env.py:103-111 |
| defaults are error_tolerance 0.05 and max_time_steps 1000 | upstream_code | gym_multirotor/envs/mujoco/base_env.py:92-93 |
| done is True when the observation is not finite, the position error norm is not below env_bounding_box_norm, or _time is not below max_time_steps | upstream_code | gym_multirotor/envs/mujoco/base_env.py:493-505 |
| env_bounding_box defaults to 1.2 and is the per-axis initial position error bound | upstream_code | gym_multirotor/envs/mujoco/base_env.py:99 |
| The desired hover position is [0, 0, 3.0] | upstream_code | gym_multirotor/envs/mujoco/base_env.py:234 |
| With randomize=False the reset starts at the desired position with zero velocity; with randomize=True it draws a position offset within env_bounding_box - 0.2 of the desired position and velocities within init_max_vel and init_max_angular_vel | upstream_code | gym_multirotor/envs/mujoco/quadrotor_plus_hover.py:183-210 |
| The model timestep is 0.01 s and gravity is -9.81 in z | upstream_code | gym_multirotor/envs/mujoco/assets/quadrotor_plus.xml:8 |
| The four motors are ctrl-limited to the range 0 to 1 | upstream_code | gym_multirotor/envs/mujoco/assets/quadrotor_plus.xml:73-76 |
| The README names QuadrotorPlusHoverEnv-v0, TiltrotorPlus8DofHoverEnv-v0 and QuadrotorXHoverEnv-v0 as the available environments | vendor_doc | README.md:35-37 |

Limits: the driver declares none.  The only bound is the action space, which the bridge derives from the environment
(`Box` with four elements 0 to 1, from the model's `actuator_ctrlrange` at `quadrotor_plus.xml:73-76`) and `ticks`
(1 to `max_ticks`, 10000 by default).  The device is simulated (R0), so no limit is `operator_required`.

The action space of the real environment is inherited from gym 0.21's `mujoco_env.MujocoEnv`
(`base_env.py:41` imports it, `requirements.txt:4` pins gym==0.21.0); that base class is outside the clone and was not
available where the gate ran.  The fake therefore publishes the 0..1 ctrlrange of the model as a stand-in and the
fidelity `gaps` say it was not compared with the inherited space.  The step method's own clip range is -1..1
(`quadrotor_plus_hover.py:60`); a caller on the `sim` backend would use the inherited space instead.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym_multirotor:QuadrotorPlusHoverEnv-v0`, level F1, the
determinism is `seeded` with `seed_control` `parameter`, timestep 50 ms (the model timestep 0.01 s at
`quadrotor_plus.xml:8` times the registered frame_skip 5 at `gym_multirotor/__init__.py:11`), `realtime_factor` 0,
clock `lockstep`, reset `full`, no snapshot and restore.  The gaps say what is not modelled (MuJoCo rigid-body
integration, contacts, thrust vectoring, rotor dynamics, non-identity attitude) and that the fake was not compared
with the upstream environment.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.  Nothing in this package claims or performs a hardware run.

Tags: quadrotor, uav, mujoco, hover, reinforcement-learning, simulation, gym
