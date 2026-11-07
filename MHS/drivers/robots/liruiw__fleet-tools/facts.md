# Facts and tags for gh.liruiw/fleet-tools

Every fact cites its source at commit `ca358b149f798301beb04542ee873c45daebceb9`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is a simulation environment benchmark built with the Gym API and Drake simulations for a Franka Panda | upstream_code | README.md:5 |
| BaseDrakeRobotEnv derives from gym.Env, so every Fleet-Tools environment uses the legacy Gym API | upstream_code | env/basedrakeenv.py:23 |
| FrankaDrakeEnv derives from BaseDrakeRobotEnv and is constructed from a task_config | upstream_code | env/frankadrakeenv.py:24-25 |
| The action space is PandaTaskSpace6D(task_config.env.action_scale), a 6-element end-effector delta | upstream_code | env/frankadrakeenv.py:134 |
| PandaTaskSpace6D returns a Box of shape [6] with the first three bounds +-trans_scale and the last three +-rotation_scale | upstream_code | core/utils/utils.py:372-396 |
| The Hammer teleop task configuration sets action_scale [0.04, 0.4] and numObservations [9] | upstream_code | experiments/config/task/FrankaDrakeHammerEnvTeleop.yaml:26-29 |
| The observation space is Box(low=-1.0, high=1.0) with shape numObservations | upstream_code | env/frankadrakeenv.py:139 |
| DrakeBaseConfig sets numActions to 6 and numObservations to [10, 240, 320] | upstream_code | experiments/config/task/DrakeBaseConfig.yaml:79-80 |
| DrakeBaseConfig sets the simulation dt to 0.004 s and substep_num to 40 | upstream_code | experiments/config/task/DrakeBaseConfig.yaml:63-64 |
| The environment control period env_dt is sim_dt multiplied by substep_num | upstream_code | env/frankadrakeenv.py:71 |
| step computes the reward with _get_reward and returns the legacy four-tuple obs, reward, done, info | upstream_code | env/frankadrakeenv.py:247-250 |
| The base FrankaDrakeEnv reward is 0 | upstream_code | env/frankadrakeenv.py:415-416 |
| step sets done to sim_done, so the base environment has no separate time limit in step | upstream_code | env/frankadrakeenv.py:248 |
| reset returns the legacy four-tuple obs, reward, done, info | upstream_code | env/frankadrakeenv.py:380 |
| seed uses gym.utils.seeding.np_random and Drake's RandomGenerator and returns [seed] | upstream_code | env/frankadrakeenv.py:141-144 |
| The environment is registered under the id FrankaDrakeEnv-v0 | upstream_code | env/__init__.py:11 |

Limits: the driver declares none. The action bounds come from the environment's action space, which the bridge
derives for `action.values`; the fake uses the Hammer teleop configuration's `action_scale` (0.04, 0.4), so those
six per-element bounds are published with the bridge's `action_space` source. `ticks` is bounded by the bridge
(1 to 10000). The upstream default DrakeBaseConfig uses `action_scale` (0.08, 0.6) and the observation is an image
there, so the fake's envelope belongs to the selected Hammer teleop configuration, not to every Fleet-Tools task.
The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:FrankaDrakeEnv-v0`, level F1, determinism
`seeded` with `seed_control` `parameter`, timestep 160 ms (`sim.dt` 0.004 s times `substep_num` 40,
`experiments/config/task/DrakeBaseConfig.yaml:63-64` and `env/frankadrakeenv.py:71`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake is only a placeholder state, that the
default configuration's image observation is not carried, that the task rewards are not modelled, and that the
upstream Drake environment was never opened or compared here.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop to call); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: fleet-tools, franka, panda, drake, manipulation, simulation, gym
