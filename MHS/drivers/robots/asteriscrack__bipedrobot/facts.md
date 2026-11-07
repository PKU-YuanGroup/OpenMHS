# Facts and tags for gh.asteriscrack/bipedrobot

Every fact cites its source at commit `bdaa21ee73c9cfa60a7fe76caf5082fc67329891`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BipedEnvV2 is the MuJoCo V2 environment class | upstream_code | envs/mujoco/biped_env_v2.py:130 |
| MujocoV2-v0 is registered with entry_point envs.mujoco.biped_env_v2:BipedEnvV2 and max_episode_steps=1000 | upstream_code | envs/mujoco/__init__.py:9-13 |
| BaseEnv, the base class of BipedEnvV2, extends gymnasium.Env | upstream_code | envs/mujoco/base_env.py:8 |
| BaseEnv loads the MuJoCo model with mujoco.MjModel.from_xml_path | upstream_code | envs/mujoco/base_env.py:13 |
| The default V2 model path is envs/assets/robotV2/robot_v2.xml | upstream_code | envs/mujoco/biped_env_v2.py:100-103 |
| The action space is Box(-1.0, 1.0, shape=(12,)): twelve normalized joint targets | upstream_code | envs/mujoco/biped_env_v2.py:285 |
| The observation space is a Dict of an actor Box and a critic Box | upstream_code | envs/mujoco/biped_env_v2.py:281-284 |
| The actor observation has 50 values and the privileged critic observation 60 values | upstream_code | envs/mujoco/biped_env_v2.py:251-252 |
| The actor observation is lin_acc_b(3), ang_vel_b(3), projected_gravity(3), commands(3), joint_pos_rel(12), joint_vel(12), prev_actions(12) and gait_phase(2) | upstream_code | envs/mujoco/biped_env_v2.py:3-5 |
| The critic observation is the 50-value actor observation plus base_lin_vel_b(3), height(1) and feet_forces(6) | upstream_code | envs/mujoco/biped_env_v2.py:7-8 |
| The physics step is 0.005 s at 200 Hz, decimation is 4 and the control step is 0.02 s at 50 Hz | upstream_code | envs/mujoco/biped_env_v2.py:77-79 |
| reset reseeds numpy's generator when a seed is given and resets the MuJoCo data | upstream_code | envs/mujoco/biped_env_v2.py:692-698 |
| reset returns the observation and an empty info dict | upstream_code | envs/mujoco/biped_env_v2.py:730 |
| step clips each action to the [-1, 1] range before applying it | upstream_code | envs/mujoco/biped_env_v2.py:733 |
| step returns the five-tuple (observation, reward, terminated, False, {}) and never truncates itself | upstream_code | envs/mujoco/biped_env_v2.py:773 |
| The episode terminates when the torso tilt exceeds 0.784 rad or both feet have been airborne for more than 1/STEP_DT steps | upstream_code | envs/mujoco/biped_env_v2.py:654-661 |
| The environment metadata declares human and rgb_array render modes at 50 fps | upstream_code | envs/mujoco/biped_env_v2.py:133 |

The first card entry symbol, `envs.mujoco_env:MujocoEnv`, names a module that is absent from the clone: the
registration at `envs/mujoco/__init__.py:5` still refers to it, while the class is actually defined in
`envs/mujoco/mujoco_env.py:19`. This package therefore uses the card's second entry symbol,
`envs.mujoco.biped_env_v2:BipedEnvV2`, whose registration is correct and whose model is the V2 XML listed in the card.

The third card entry symbol, `envs.isaaclab.biped_env:BipedEnv`, imports Isaac Lab and a GPU stack (card
`install.gpu` is true); it is not usable where the gate runs and the driver does not install it.

Limits: the driver declares none. The action bound is derived by the bridge from the environment's action space
(`Box(-1.0, 1.0, shape=(12,))`: every one of the twelve `action.values` elements is bounded to [-1, 1] with no source
and the ref `action_space of the fake backend .fake:FakeBipedEnvV2`), and the class bounds `ticks` (1 to 10000). The
device is simulated (R0), so no limit is `operator_required` and there is no site-limits overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:MujocoV2-v0`, level F1 (MuJoCo rigid-body
physics, no actuator/servo model in this fake), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms
(`STEP_DT = PHYSICS_DT * DECIMATION = 0.005 * 4` s, `envs/mujoco/biped_env_v2.py:77-79`), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say that the fake is a pure Python kinematic stand-in, that
its observation values are placeholders, that its RNG differs from upstream's numpy generator, and that the 1000-step
truncation comes from the registered TimeLimit rather than from the environment class.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: biped, locomotion, mujoco, gymnasium, reinforcement-learning, simulation
