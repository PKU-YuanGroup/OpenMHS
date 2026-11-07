# Facts and tags for gh.mcarfagno/gym-panda-reach

Every fact cites its source at commit `928d1e6b779b52d25bbef2a9f717bcf64991f6fb`, either `upstream_code`
(`path/in/clone.py:LINE`) or the text files of the clone.  The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| panda-reach-v0 is registered with the entry point gym_panda_reach.envs:PandaEnv | upstream_code | gym_panda_reach/__init__.py:3-6 |
| gym_panda_reach.envs re-exports PandaEnv from panda_env | upstream_code | gym_panda_reach/envs/__init__.py:1 |
| PandaEnv is a gym.Env | upstream_code | gym_panda_reach/envs/panda_env.py:20 |
| The constructor connects to PyBullet in GUI mode, so creating the environment needs pybullet and a display | upstream_code | gym_panda_reach/envs/panda_env.py:26-29 |
| The action space is Box([-1, -1, -1, -1], [1, 1, 1, 1]): four continuous values from -1 to 1 | upstream_code | gym_panda_reach/envs/panda_env.py:36 |
| The observation space is declared as Box([-1] * 24, [1] * 24) | upstream_code | gym_panda_reach/envs/panda_env.py:37 |
| Each step moves the end effector by action[0], action[1] and action[2] times dv = 0.05 in x, y and z and takes action[3] as the finger command | upstream_code | gym_panda_reach/envs/panda_env.py:51-55 |
| The end effector is link 11 and its target pose is solved with calculateInverseKinematics for the incremented position with a fixed orientation | upstream_code | gym_panda_reach/envs/panda_env.py:57-66 |
| Joints 0 to 6 are position-controlled at the inverse-kinematics solution and joints 9 and 10 at action[3] | upstream_code | gym_panda_reach/envs/panda_env.py:68-73 |
| One step advances the simulation once with p.stepSimulation() | upstream_code | gym_panda_reach/envs/panda_env.py:75 |
| The reach threshold is distance 0.05 between the end effector and the object; the episode is done when the distance is below it | upstream_code | gym_panda_reach/envs/panda_env.py:88-95 |
| The dense reward is minus the distance; the sparse reward is -1 when the distance is above 0.05 and 0 otherwise | upstream_code | gym_panda_reach/envs/panda_env.py:39-45 |
| MAX_EPISODE_LEN is 20 * 100 = 2000 steps | upstream_code | gym_panda_reach/envs/panda_env.py:13 |
| The episode is also done when step_counter is greater than MAX_EPISODE_LEN, so a run stops on the 2001st step | upstream_code | gym_panda_reach/envs/panda_env.py:97-101 |
| The observation has 24 values: grip position, object position, their difference, mean finger position, object orientation, object linear and angular velocity, commanded xyz velocity and finger velocity | upstream_code | gym_panda_reach/envs/panda_env.py:120-132 |
| reset loads the Panda at base z 0.65 with the rest pose [0, -0.215, 0, -2.57, 0, 2.356, pi/4, 0, 0, 0] | upstream_code | gym_panda_reach/envs/panda_env.py:153-159 |
| The object starts uniformly at x in [0.5, 0.8], y in [-0.2, 0.2] and z in [0.65, 0.85] | upstream_code | gym_panda_reach/envs/panda_env.py:201-205 |
| The goal object is loaded with useFixedBase=True, so it does not move during an episode | upstream_code | gym_panda_reach/envs/panda_env.py:207-211 |
| The step result is the legacy 4-tuple (observation, reward, done, info) | upstream_code | gym_panda_reach/envs/panda_env.py:134 |
| reset takes no seed or options argument | upstream_code | gym_panda_reach/envs/panda_env.py:136 |
| reset returns the observation alone, not an (observation, info) pair | upstream_code | gym_panda_reach/envs/panda_env.py:247 |
| The object position is reported in info as object_position | upstream_code | gym_panda_reach/envs/panda_env.py:103 |
| render returns a 720 by 960 RGB array from getCameraImage | upstream_code | gym_panda_reach/envs/panda_env.py:249-273 |
| close disconnects the PyBullet client | upstream_code | gym_panda_reach/envs/panda_env.py:278-279 |

Limits: the driver declares none.  The action bound is the environment's own action space (`Box([-1]*4, [1]*4)`,
`panda_env.py:36`), which the Gymnasium bridge derives and publishes as `action.values` with source `upstream_code`
and ref `gym_panda_reach/envs/panda_env.py:36`; `ticks` is bounded by the class and the bridge (1 to 10000).  The
device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:gym-panda-reach-fake`, level F0 (the fake is
kinematic: positions are applied directly, there is no dynamics), determinism `seeded` with `seed_control`
`parameter` (the fake's object start comes from Python's `random.Random(seed)`; the upstream reset takes no seed and
uses the module-level random generator, `panda_env.py:136,202-204`), `timestep_ms` 0 (one step call is one control
event and no simulated time is modelled), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or
restore.  The gaps say what is not modelled and that the upstream PyBullet environment was never opened or compared
with the fake.

Safety: simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: panda, robot-arm, reach, reinforcement-learning, simulation, gymnasium, pybullet
