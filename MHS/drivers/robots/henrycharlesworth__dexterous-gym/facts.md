# Facts and tags for gh.henrycharlesworth/dexterous-gym

Every fact cites its source at commit `dd047ad7f47ba78e2a4e2642e39bc0c0b778e594`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| EggHandOver-v0 is registered with entry point dexterous_gym.envs.egg_hand_over:EggHandOver, max_episode_steps 75 and reward_type 'dense' | upstream_code | dexterous_gym/__init__.py:6-11 |
| The EggHandOver model file is dexterous_gym/envs/hand/egg_handover.xml | upstream_code | dexterous_gym/envs/egg_hand_over.py:6-7 |
| EggHandOver constructs TwoHandsEnv with moving_hands False, two_objects False and target_rotation 'xyz' | upstream_code | dexterous_gym/envs/egg_hand_over.py:17-20 |
| TwoHandsEnv has 40 actions when moving_hands is False and 52 when it is True | upstream_code | dexterous_gym/core/two_hands_env.py:54-57 |
| The action space is Box(-1.0, 1.0, shape=(n_actions,), dtype float32) | upstream_code | dexterous_gym/core/two_hand_robot_env.py:45 |
| Each action component is mapped to the actuator control range as centre + action*range and clipped to the range | upstream_code | dexterous_gym/core/two_hands_env.py:67-73 |
| step clips the action, applies it, advances the simulator and returns (observation, reward, done, info) with done hard-coded False | upstream_code | dexterous_gym/core/two_hand_robot_env.py:76-88 |
| The observation dictionary carries observation, achieved_goal and desired_goal | upstream_code | dexterous_gym/core/two_hands_env.py:261-263 |
| The achieved goal is the object's 7-element joint position and quaternion | upstream_code | dexterous_gym/core/two_hands_env.py:75-82 |
| The observation and both goal spaces are unbounded Box spaces | upstream_code | dexterous_gym/core/two_hand_robot_env.py:59-63 |
| A reset restores the initial simulator state, randomises the object's orientation and runs 10 zero-action simulation steps | upstream_code | dexterous_gym/core/two_hands_env.py:133-165 |
| RobotEnv.reset samples a new goal and returns the observation | upstream_code | dexterous_gym/core/two_hand_robot_env.py:90-102 |
| The default goal position ranges are x 0.96-1.04, y 0.81-0.89 (hand 1) or 0.60-0.68 (hand 2) and z 0.20-0.26 | upstream_code | dexterous_gym/envs/egg_hand_over.py:8-9 |
| The target rotation is a uniformly random axis-angle with angle in [-pi, pi] and axis components in [-1, 1] | upstream_code | dexterous_gym/core/two_hands_env.py:206-209 |
| The EggHandOver default success thresholds are 0.01 m for position and 0.1 rad for rotation | upstream_code | dexterous_gym/envs/egg_hand_over.py:13-14 |
| The dense reward is exp(-(dist_multiplier*d_pos + d_rot)); the sparse reward is success - 1.0 | upstream_code | dexterous_gym/envs/egg_hand_over.py:22-29 |
| The default dist_multiplier is 20.0 | upstream_code | dexterous_gym/envs/egg_hand_over.py:14 |
| The simulator timestep is 0.002 s | upstream_code | dexterous_gym/envs/hand/egg_handover.xml:4 |
| n_substeps defaults to 20 simulation steps per call to step | upstream_code | dexterous_gym/core/two_hands_env.py:20 |
| dt is the model timestep times the number of substeps | upstream_code | dexterous_gym/core/two_hand_robot_env.py:65-67 |
| The seed is drawn with gym.utils.seeding.np_random | upstream_code | dexterous_gym/core/two_hand_robot_env.py:72-74 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1, shape=(40,))`: `action.values` has 40 elements, each from -1 to 1, with no source and the ref
`action_space of the fake backend .fake:FakeEggHandOver`), and `ticks` (1 to `max_ticks`, 10000 by default). The device
is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:EggHandOver-v0`, level F0 (an analytic kinematic
stand-in, no rigid-body dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 40 ms (model timestep
0.002 s at `egg_handover.xml:4` times the default 20 substeps at `two_hands_env.py:20`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled (no MuJoCo, no contacts, no
actuators or noise, the fake was not compared with upstream, the legacy Gym API difference and the list observations).

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Coverage: this package serves the first card entry symbol, `EggHandOver-v0` only. The other card entry symbols
(`BlockHandOver`, `PenHandOver`, `EggCatchUnderarm` and `BlockCatchUnderarm`) are NOT COVERED; each needs a package
with its own `env_id`, `native` and fake.

Tags: dexterous-gym, hand-manipulation, mujoco, reinforcement-learning, simulation, gym.
