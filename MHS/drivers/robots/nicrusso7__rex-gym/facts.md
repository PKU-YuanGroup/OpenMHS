# Facts and tags for gh.nicrusso7/rex-gym

Every fact cites its source at commit `26663048bd3c3da307714da4458b1a2a9dc81824`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| RexWalk-v0 is registered with entry point rex_gym.envs.gym.walk_env:RexWalkEnv and max_episode_steps=2500 | upstream_code | rex_gym/playground/__init__.py:24-29 |
| RexWalkEnv is the alternating-leg locomotion environment for the quadruped Rex | upstream_code | rex_gym/envs/gym/walk_env.py:17-24 |
| With the default signal_type 'ik' the action space is a Box of two elements bounded by -0.4 and 0.4; the 'ol' signal mode has eight elements bounded by -0.01 and 0.01 | upstream_code | rex_gym/envs/gym/walk_env.py:104-114 |
| An observation is [roll, pitch, roll_rate, pitch_rate] of the robot base | upstream_code | rex_gym/envs/gym/walk_env.py:356-362 |
| The observation upper bound is 2*pi for roll and pitch and 2*pi/time_step for the two rates, and the lower bound is its negation | upstream_code | rex_gym/envs/gym/walk_env.py:364-378 |
| The default control_time_step is 0.005 s and the default action_repeat is 5 | upstream_code | rex_gym/envs/gym/walk_env.py:34-35 |
| The base environment computes its simulation step as control_time_step/action_repeat, which is 0.001 s with the RexWalk defaults | upstream_code | rex_gym/envs/rex_gym_env.py:170-173 |
| The base reset sets the pybullet time step to that simulation step | upstream_code | rex_gym/envs/rex_gym_env.py:308 |
| The base constructor builds the observation space as a Box from the lower bound minus OBSERVATION_EPS to the upper bound plus OBSERVATION_EPS | upstream_code | rex_gym/envs/rex_gym_env.py:277-282 |
| RexWalkEnv.reset resets its flags, draws the backwards flag and the target position from Python's global random module and returns _get_observation() | upstream_code | rex_gym/envs/gym/walk_env.py:125-154 |
| RexWalkEnv.reset passes the stand initial pose and a 0.5 s reset duration to the base reset | upstream_code | rex_gym/envs/gym/walk_env.py:125-129 |
| seed(seed) replaces the environment's numpy generator with gym.utils.seeding.np_random and returns [seed] | upstream_code | rex_gym/envs/rex_gym_env.py:359-361 |
| step applies the action through rex.Step, computes the reward and termination, increments the step counter and returns (observation, reward, done, info) | upstream_code | rex_gym/envs/rex_gym_env.py:403-414 |
| The walk environment considers Rex fallen when the dot product of the world up vector and the base up vector is below 0.85 | upstream_code | rex_gym/envs/gym/walk_env.py:326-338 |
| The base termination is is_fallen() or env_goal_reached or _out_of_trajectory() | upstream_code | rex_gym/envs/rex_gym_env.py:490-499 |
| RexWalkEnv sets goal_reached and is_terminating when the base x is within 0.15 of the target position | upstream_code | rex_gym/envs/gym/walk_env.py:207-215 |
| The reward weights default to distance 1.0, energy 0.0005, drift 2.0 and shake 0.005 | upstream_code | rex_gym/envs/rex_gym_env.py:56-59 |
| The base reward is the sum of the weighted forward, energy, drift and shake terms | upstream_code | rex_gym/envs/rex_gym_env.py:538-542 |
| RexWalkEnv declares the render modes human and rgb_array at 66 frames per second | upstream_code | rex_gym/envs/gym/walk_env.py:27 |
| The clone pins numpy 1.17.3, pybullet 2.8.3, gym 0.17.1, tensorflow 1.15.5 and tensorflow-probability 0.8 in requirements.txt | upstream_code | requirements.txt:1-7 |
| The README instructs users to create a Python 3.7 environment | vendor_doc | README.md:22-26 |
| The README documents Rex as a 12-joint robot with 3 motors for each leg and imports the model into pyBullet | vendor_doc | README.md:87-89 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-0.4, 0.4)` of two elements, `action.values`) and `ticks` (1 to `max_ticks`, 10000 by default). The device is
simulated (R0), so no limit is `operator_required` and the package needs no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:RexWalk-v0`, level F1 (rigid-body dynamics with
contacts, not validated), determinism `statistical` with `seed_control` `parameter` because reset draws the backwards
flag and target from Python's global `random` module, `timestep_ms` 1 ms (the physics step; one environment step
applies five of them, a 5 ms control period), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what the fake omits and that it was not compared with the pybullet environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last world state stays readable.

Tags: rex-gym, quadruped, locomotion, pybullet, reinforcement-learning, simulation, gym
