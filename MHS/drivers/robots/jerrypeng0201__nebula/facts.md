# Facts and tags for gh.jerrypeng0201/nebula

Every fact cites its source at commit `2d16ad04e9825b4a6212847ba847e5ae910feed4`: `upstream_code` for a file of the
clone (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

The environment is `SceneManipulation-v1` of the Nebula repository, served by the package with the default Fetch robot
and the first Fetch controller config (`pd_joint_delta_pos`). The fake backend is a pure Python kinematic stand-in for
the default configuration; it is not the SAPIEN PhysX environment.

| fact | source | ref |
|---|---|---|
| SceneManipulation-v1 is registered with max_episode_steps=200 | upstream_code | nebula/core/simulation/scenes/base_env.py:19 |
| The environment supports the panda and fetch robots and creates a fetch agent by default | upstream_code | nebula/core/simulation/scenes/base_env.py:40-46 |
| The environment is for explorations and visualization and has no success/failure metrics or rewards | upstream_code | nebula/core/simulation/scenes/base_env.py:21-23 |
| evaluate() returns an empty dict, compute_dense_reward() returns 0, and the normalized dense reward divides that 0 by 1 | upstream_code | nebula/core/simulation/scenes/base_env.py:142-151 |
| reset accepts seed and options, including reconfigure and build or init config indices | upstream_code | nebula/core/simulation/scenes/base_env.py:85-105 |
| The default scene builder is ReplicaCAD | upstream_code | nebula/core/simulation/scenes/base_env.py:47 |
| The first supported observation mode is state | upstream_code | nebula/core/simulation/engine.py:127 |
| A None obs_mode selects the first supported observation mode, state | upstream_code | nebula/core/simulation/engine.py:280-281 |
| A state observation is the dict {agent, extra}; get_obs flattens it to one tensor | upstream_code | nebula/core/simulation/engine.py:529-544 |
| The agent's proprioception is its qpos and qvel, plus controller state only when the controller returns one | upstream_code | nebula/core/embodiment/manipulator.py:333-341 |
| Fetch has 7 arm, 2 gripper, 3 body and 3 base joints | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:78-114 |
| A None control_mode selects the first supported control mode, the first controller config key | upstream_code | nebula/core/embodiment/manipulator.py:105-111 |
| The first Fetch controller config key is pd_joint_delta_pos with arm, gripper, body and base controllers | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:258-264 |
| The Fetch arm delta controller is configured with raw joint bounds -0.1 to 0.1 for the 7 arm joints | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:132-140 |
| The Fetch gripper is a mimic controller with one mimic entry mapping r_gripper_finger_joint to l_gripper_finger_joint and raw bounds -0.01 to 0.05 | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:213-221 |
| A mimic controller deduplicates its control joints and reads the joint limits at those indices, so this gripper has one action dimension | upstream_code | nebula/core/embodiment/actuators/joint_position_control.py:193-205 |
| The Fetch body delta controller is configured with raw joint bounds -0.1 to 0.1 for the 3 body joints | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:226-234 |
| The Fetch base forward velocity controller is configured with lower [-1, -3.14] and upper [1, 3.14] | upstream_code | nebula/core/embodiment/robots/fetch/fetch.py:250-256 |
| The base forward velocity controller broadcasts its configured bounds to two action elements, forward velocity and rotation velocity | upstream_code | nebula/core/embodiment/actuators/base_velocity_control.py:42-46 |
| The joint position controller config defaults normalize_action to True | upstream_code | nebula/core/embodiment/actuators/joint_position_control.py:113-126 |
| The joint velocity controller config defaults normalize_action to True | upstream_code | nebula/core/embodiment/actuators/joint_velocity_control.py:46-54 |
| When a controller config enables normalize_action, ActuatorController.__init__ calls _clip_and_scale_action_space | upstream_code | nebula/core/embodiment/actuators/base_actuator.py:67-72 |
| _clip_and_scale_action_space replaces the configured Box with normalize_action_space(...) and keeps the raw low and high bounds for clipping and scaling | upstream_code | nebula/core/embodiment/actuators/base_actuator.py:159-169 |
| normalize_action_space returns Box(-1, 1) with the original shape | upstream_code | nebula/utils/gym_utils.py:108-110 |
| The combined controller flattens the named Box spaces into one Box with per-element low and high bounds | upstream_code | nebula/core/embodiment/utils.py:28-56 |
| The simulation runs at 100 Hz and the control loop at 20 Hz, so every control step contains five simulation steps | upstream_code | nebula/utils/structs/types.py:80-83 |
| A seeded reset sets the main RNG and the episode RNG to the seed; an unseeded reset samples the episode seed from the main RNG | upstream_code | nebula/core/simulation/engine.py:884-887 |
| step returns (observation, reward, terminated, truncated, info); without success or fail in info, terminated is a zero tensor | upstream_code | nebula/core/simulation/engine.py:1036-1053 |
| A floating-point observation is converted to a Box with bounds -inf to inf | upstream_code | nebula/utils/gym_utils.py:145-154 |
| The observation space is the single observation space batched over num_envs | upstream_code | nebula/core/simulation/engine.py:365-373 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment.
The flattened Fetch `pd_joint_delta_pos` action has 13 elements in the order arm 7, gripper 1, body 3 and base 2. The
four controller configs leave `normalize_action` at its True default, so every element is bounded `-1..1`; the raw
bounds (arm `-0.1..0.1`, gripper `-0.01..0.05`, body `-0.1..0.1`, base lower `[-1, -3.14]` and upper `[1, 3.14]`) are
what those normalized values are clipped and scaled to. The facts above cite each of them. `ticks` is bounded
`1..10000` by the bridge (`max_ticks`). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sapien:SceneManipulation-v1`, level F1 (the upstream model
is a SAPIEN PhysX rigid-body scene with contacts), determinism `seeded` with `seed_control` `parameter`, timestep 50 ms
(five 20 Hz control steps of the 100 Hz simulation, `nebula/utils/structs/types.py:80-83`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot. The gaps say that the fake is kinematic, that it serves the default Fetch
configuration only, and that it was never compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable.

Tags: gymnasium, manipulation, fetch, sapien, reinforcement-learning, simulation, scene
