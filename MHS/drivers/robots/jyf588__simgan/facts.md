# Facts and tags for gh.jyf588/simgan

Every fact cites its source at commit `23283d7b5629f1653567b2437bb28aac1cc17169`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (a code file or comment of the clone). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HopperURDFEnvV3 subclasses gym.Env | upstream_code | my_pybullet_envs/hopper_env_v3.py:32 |
| HopperURDFEnv-v3 is registered with entry point my_pybullet_envs:HopperURDFEnvV3 and max_episode_steps=500 | upstream_code | my_pybullet_envs/__init__.py:34-38 |
| The physics timestep is 1/500 s per Bullet substep | upstream_code | my_pybullet_envs/hopper_env_v3.py:60 |
| An environment step advances the simulation for range(control_skip) physics substeps and increments the timer at each substep | upstream_code | my_pybullet_envs/hopper_env_v3.py:243-250 |
| control_skip has constructor default 10 | upstream_code | my_pybullet_envs/hopper_env_v3.py:40 |
| The action space is Box(low=-1, high=+1) with one element per controlled joint | upstream_code | my_pybullet_envs/hopper_env_v3.py:100-103 |
| The robot has three controlled joints, ctrl_dofs [3, 4, 5] | upstream_code | my_pybullet_envs/hopper.py:53 |
| The action is compressed with tanh before it is used as the joint command | upstream_code | my_pybullet_envs/hopper_env_v3.py:221 |
| apply_action scales the action by max_forces and writes it as the torque of the controlled joints | upstream_code | my_pybullet_envs/hopper.py:124-132 |
| max_forces starts as nominal_max_forces, [200.0] * 3 | upstream_code | my_pybullet_envs/hopper.py:48-49 |
| The observation is the five joint positions a_q[1:] followed by the six joint velocities a_dq | upstream_code | my_pybullet_envs/hopper.py:167-175 |
| obs_scaling is [1.0] * 5 + [1.0] * 2 + [0.1] * 4: the last four velocities are scaled by 0.1 | upstream_code | my_pybullet_envs/hopper.py:51 |
| The observation space is Box(-inf, +inf) with one bound per observation value | upstream_code | my_pybullet_envs/hopper_env_v3.py:104-106 |
| The episode is not done only while every controlled joint speed is below 50 and the height is between 0.6 and 1.8 | upstream_code | my_pybullet_envs/hopper_env_v3.py:281 |
| step returns (observation, reward, not not_done, {'sas_window': ...}) | upstream_code | my_pybullet_envs/hopper_env_v3.py:283 |
| The reward is a 3.0 alive bonus, plus the average forward speed, minus 0.5 times the squared action sum, minus 3.0 per joint at its limit and minus an acceleration penalty capped at 5.0 | upstream_code | my_pybullet_envs/hopper_env_v3.py:255-272 |
| The acceleration penalty weight acc_pen_weight defaults to 0.05 | upstream_code | my_pybullet_envs/hopper_env_v3.py:53 |
| reset restarts the simulation, applies the timestep _ts and sets gravity (0, 0, -10) | upstream_code | my_pybullet_envs/hopper_env_v3.py:108-121 |
| The robot starts at base_init_pos [0, 0, 1.3] with zero orientation | upstream_code | my_pybullet_envs/hopper.py:45-46 |
| With init_noise the reset perturbs the initial joint positions by 0.02 and velocities by 0.1 | upstream_code | my_pybullet_envs/hopper.py:91-96 |
| reset() takes no seed argument | upstream_code | my_pybullet_envs/hopper_env_v3.py:108 |
| seed(seed) replaces np_random with gym.utils.seeding.np_random(seed) | upstream_code | my_pybullet_envs/hopper_env_v3.py:312-315 |
| render defaults to True and opens a PyBullet GUI connection; render=False uses a headless client | upstream_code | my_pybullet_envs/hopper_env_v3.py:77-80 |
| The constructor selects the soft-floor, deformable-floor, low-power, EMF-power, heavy-head and randomization variants with boolean options | upstream_code | my_pybullet_envs/hopper_env_v3.py:44-51 |
| The model loads assets/hopper_my.urdf, or assets/hopper_my_heavyhead.urdf when heavy_head is set | upstream_code | my_pybullet_envs/hopper.py:79-83 |
| The README creates a Python 3.6 conda environment and installs requirements.txt | vendor_doc | README.md:21-29 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, +1)` for each of the three controlled joints, with no source and the ref
`action_space of the fake backend .fake:FakeHopperURDFEnvV3`), plus the catalogue's `ticks` bound (1 to `max_ticks`,
10000 by default). The device is simulated (R0), so no limit is `operator_required` and there is no
site-limits.example.json.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `custom:simgan-hopper-kinematic`, level F0, because the
deployed backend is the package's kinematic fake, not the upstream PyBullet rigid-body model. Determinism `seeded`
with `seed_control` `parameter`, timestep 20 ms (the upstream default control_skip=10 at 1/500 s; `hopper_env_v3.py:40`
and `:60`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not
modelled, that the fake was never compared with the upstream environment, and that the registration
`max_episode_steps=500` is a `gym.make` wrapper, not the environment class.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the fake
state stays readable.

Tags: simgan, hopper, pybullet, reinforcement-learning, simulation, gym

## Other entry symbols of the card

The card lists four entry symbols. This package serves the first, `HopperURDFEnvV3` (`my_pybullet_envs/hopper_env_v3.py:32`).
The other three are separate environments and are not covered by this package:

- `HopperCombinedEnv` (`my_pybullet_envs/hopper_env_combined_policy.py:32`) loads a PyTorch behaviour policy and a
  dynamics model; it is the hybrid-simulator training environment, not the source environment.
- `LaikagoBulletEnvV4` (`my_pybullet_envs/laikago_env_v4.py:31`) is the Laikago quadruped source environment.
- `LaikagoCombinedEnv` (`my_pybullet_envs/laikago_env_combined_policy.py:32`) is its combined-policy counterpart.

One package per repository: a card with several entry symbols is implemented as one device class, the first confirmed.

