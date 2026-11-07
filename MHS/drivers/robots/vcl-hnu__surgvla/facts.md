# Facts and tags for gh.vcl-hnu/surgvla — ECMReach-v0

Every fact cites its source at commit `9446d6544757830c8ad184a5faadcde5cd2e4905` in the clone
`robots/vcl-hnu/surgvla`.  The same facts are written into `driver.py` (`facts = [...]`); `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.  The upstream clone carries no LICENSE file and the
task card records `NOASSERTION` / `unknown`; the package is model-authored, unreviewed and checked on the fake backend
only.

| fact | source | ref |
|---|---|---|
| ECMReach-v0 is registered with entry point surrol.tasks.ecm_reach:ECMReach and max_episode_steps=50 | upstream_code | surrol/gym/__init__.py:43-47 |
| The ECM action size is 3 | upstream_code | surrol/tasks/ecm_env.py:25 |
| The action space is a Box from -1.0 to 1.0 with one bound per action element | upstream_code | surrol/gym/surrol_env.py:77 |
| ECMReach selects the dmove action mode | upstream_code | surrol/tasks/ecm_reach.py:11 |
| In dmove mode the action is scaled by 0.01 and added to the RCM position, then sent through the ECM inverse kinematics | upstream_code | surrol/tasks/ecm_env.py:138-145 |
| The ECMReach workspace limits are ((0.45, 0.55), (-0.05, 0.05), (0.60, 0.70)) | upstream_code | surrol/tasks/ecm_reach.py:12 |
| A reset draws the goal uniformly from the workspace limits | upstream_code | surrol/tasks/ecm_reach.py:29-34 |
| The ECM starts at (0.45, 0.05, 0.70): the workspace lower x, upper y and upper z | upstream_code | surrol/tasks/ecm_reach.py:12-22 |
| The success threshold is 0.005 m: DISTANCE_THRESHOLD is 0.005 and SCALING is 1.0 | upstream_code | surrol/tasks/ecm_env.py:27-31 |
| The sparse reward is 0 on success and -1 otherwise: compute_reward is _is_success - 1 | upstream_code | surrol/tasks/ecm_env.py:73-77 |
| The observation is a Dict with the keys observation, achieved_goal and desired_goal | upstream_code | surrol/tasks/ecm_env.py:118-122 |
| ECMReach sets has_object to False, so object_pos is empty and the observation vector is the 6-value robot state | upstream_code | surrol/tasks/ecm_env.py:42-116 |
| The step returns (observation, reward, done, info) and done is always False | upstream_code | surrol/gym/surrol_env.py:109-119 |
| A reset rebuilds the scene, resamples the goal and returns the observation | upstream_code | surrol/gym/surrol_env.py:121-141 |
| EcmEnv sets the step duration to 0.1 s | upstream_code | surrol/tasks/ecm_env.py:48 |
| SurRoLEnv.step advances the simulation by step(self._duration) | upstream_code | surrol/gym/surrol_env.py:102 |
| The simulation loop calls p.stepSimulation() int(duration * 240) times, i.e. 240 physics steps per simulated second | upstream_code | surrol/utils/pybullet_utils.py:18-20 |
| The environment's seed() stores numpy's generator and returns [seed] | upstream_code | surrol/gym/surrol_env.py:160-162 |
| The goal draw uses numpy's global random generator (np.random.rand) | upstream_code | surrol/tasks/ecm_reach.py:32 |
| The ECM has 4 degrees of freedom and its end-effector link index is 4 | upstream_code | surrol/robots/ecm.py:60-62 |

## Limits

The driver declares no limit of its own.  The only bound is the environment's action space, which the Gymnasium bridge
derives from `gym.spaces.Box(-1., 1., shape=(3,))` and publishes as `action.values` with per-element limits -1.0 to
1.0; its source is `upstream_code` and its reference the clone line `surrol/gym/surrol_env.py:77`, which G4 checks.
`ticks` is bounded by the class schema at 1 to 10000 and by the bridge's `max_ticks`; `seed` is a non-negative integer.
No value is `operator_required`: this is a simulated R0 device and the action space is the complete bound.

## Fidelity contract

`engine` is `pybullet`, level **F1** (the upstream scene is rigid-body dynamics with contacts and ECM inverse
kinematics), determinism `seeded` with `seed_control` `parameter`, physics timestep 1000/240 ms
(`surrol/utils/pybullet_utils.py:18-20`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot/restore.
The control period is 100 ms: one `env.step` advances `_duration = 0.1` s, i.e. 24 physics steps
(`surrol/tasks/ecm_env.py:48`, `surrol/gym/surrol_env.py:102`), and one bridge tick is one `env.step`.  The gaps say
that the checked backend is the package's kinematic fake (action * 0.01 m, zero orientation, no URDF or rendering), that
the seed path is a stand-in because upstream's `seed()` generator is not the one `_sample_goal` uses, and that the sim
backend (`gym.make("ECMReach-v0")`) was not run where the gate ran.

## Safety

Simulated R0 device.  The e-stop is the runtime's software latch (no native stop exists); after it no step or reset is
accepted until `mhs.safety.reset` clears the latch, and the last observation and tick stay readable.

## Tags

surgical-robotics, laparoscopy, ecm, reach, reinforcement-learning, simulation, gymnasium, pybullet, surrol, surgvla
