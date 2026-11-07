# Facts and tags for gh.healthcare-robotics/assistive-gym

Every fact cites its source at commit `fb799c377e1f144ff96044fb9096725f7f9cfc61`: `vendor_doc` (README.md) or
`upstream_code` (a path in the clone and its line). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Assistive Gym is a physics-based simulation framework for physical human-robot interaction and robotic assistance | vendor_doc | README.md:7 |
| Assistive Gym is integrated into the OpenAI Gym interface | vendor_doc | README.md:9 |
| HumanTestingEnv subclasses AssistiveEnv and builds a robot-free world with a controllable human | upstream_code | assistive_gym/envs/human_testing.py:11-13 |
| The controllable human joints are human.right_arm_joints + human.left_arm_joints | upstream_code | assistive_gym/envs/human_testing.py:10 |
| right_arm_joints are 0 through 9 and left_arm_joints are 10 through 19 | upstream_code | assistive_gym/envs/agents/human.py:5-6 |
| AssistiveEnv builds the action space as a Box with one element per controllable robot and human joint, with every element bounded -1 to 1 | upstream_code | assistive_gym/envs/env.py:40-42 |
| HumanTestingEnv passes obs_robot_len=0 and obs_human_len=0 and _get_obs returns an empty list | upstream_code | assistive_gym/envs/human_testing.py:13-20 |
| HumanTestingEnv.step calls take_step with gains 0.05 and forces 1.0 and returns an empty observation, reward 0, done False and an empty info dict | upstream_code | assistive_gym/envs/human_testing.py:15-17 |
| AssistiveEnv defaults time_step to 0.02 s and frame_skip to 5 | upstream_code | assistive_gym/envs/env.py:21 |
| AssistiveEnv.reset calls p.resetSimulation, disconnects the client and reconnects a DIRECT physics client | upstream_code | assistive_gym/envs/env.py:91-97 |
| AssistiveEnv.reset sets the PyBullet time step to time_step, disables real-time simulation and sets gravity | upstream_code | assistive_gym/envs/env.py:104-107 |
| AssistiveEnv.take_step clips the action to the action space bounds | upstream_code | assistive_gym/envs/env.py:187 |
| AssistiveEnv.take_step calls p.stepSimulation frame_skip times per environment step | upstream_code | assistive_gym/envs/env.py:224-226 |
| AssistiveEnv.seed uses gym's seeding.np_random and returns the seed | upstream_code | assistive_gym/envs/env.py:78-80 |
| HumanTestingEnv.reset sets gravity to 0, 0, 0 | upstream_code | assistive_gym/envs/human_testing.py:35 |
| AssistiveEnv loads realistic_arm_limits_model.h5 from the bundled assets directory | upstream_code | assistive_gym/envs/env.py:37-39 |
| HumanTesting-v1 is registered with max_episode_steps=200 | upstream_code | assistive_gym/__init__.py:22-26 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` with one element per controllable human arm joint, `-1` to `1`, with the source `upstream_code` and the ref
`assistive_gym/envs/env.py:42`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `pybullet:assistive_gym:HumanTesting-v1`, level F1
(PyBullet rigid-body contacts, no sensor/latency/noise model), determinism `seeded` with `seed_control` `parameter`,
timestep 100 ms (one environment step runs frame_skip=5 physics steps of time_step=0.02 s, env.py:21 and :224-226),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled and that
this package's fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: assistive-gym, pybullet, human-robot-interaction, simulation, gym, testing
