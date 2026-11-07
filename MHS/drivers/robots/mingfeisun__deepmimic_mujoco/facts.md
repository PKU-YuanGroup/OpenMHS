# Facts and tags for gh.mingfeisun/deepmimic_mujoco

Every fact cites its source at commit `36b9e211f025c216fddf599ce21af9d8f10a1b34`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HumanoidDeepMimic-v0 is registered with entry point humanoid_deepmimic.envs:HumanoidDeepMimicEnv | upstream_code | src/mujoco/humanoid_deepmimic/__init__.py:3-6 |
| The environment class HumanoidDeepMimicEnv subclasses the legacy gym MujocoEnv and utils.EzPickle | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:5 |
| The constructor loads asset/humanoid_deepmimic.xml through the legacy MuJoCo base with frame_skip 5, using the host-specific absolute path /home/mingfei/Documents/DeepMimic/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:7 |
| One environment step computes forward reward from the root body's x displacement divided by dt, subtracts a 0.5*sum(a^2) control cost and a contact cost, and adds a survive reward of 1.0 | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:14-19 |
| The episode is not done while the state is finite and state[2] is between 0.2 and 1.0 | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:21-23 |
| The observation concatenates qpos[2:], qvel and cfrc_ext clipped to [-1, 1] | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:31-36 |
| The reset model adds uniform(-0.1, 0.1) noise to the initial qpos and normal(0, 0.1) noise to the initial qvel | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_env.py:38-42 |
| The model's simulator timestep is 0.003 s | upstream_code | src/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml:9 |
| The model declares three chest motors, chest_x, chest_y and chest_z, on the chest ball joint | upstream_code | src/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml:123-125 |
| The model's default motor control range is -0.3 to 0.3 | upstream_code | src/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml:7 |
| The model's root free joint is commented out, so the model has no free root position in qpos | upstream_code | src/mujoco/humanoid_deepmimic/envs/asset/humanoid_deepmimic.xml:28-30 |
| The envs package imports HumanoidDeepMimicExtraHardEnv from the module humanoid_deepmimic_extrahard_env.envs.humanoid_deepmimic_extrahard_env, which does not exist in the clone | upstream_code | src/mujoco/humanoid_deepmimic/envs/__init__.py:2 |
| The extrahard module defines only FooEnv, whose step, reset and render methods do nothing | upstream_code | src/mujoco/humanoid_deepmimic/envs/humanoid_deepmimic_extrahard_env.py:5-15 |

Limits: the driver declares no explicit `Limit`. The only numeric bound is the action space that the Gymnasium bridge
derives from the fake environment: three `action.values` elements from -0.3 to 0.3. That is the model's stated motor
control range (`humanoid_deepmimic.xml:7`) and the three chest motors are `humanoid_deepmimic.xml:123-125`. The
bridge gives the derived rule no source and the ref `action_space of the fake backend .fake:FakeHumanoidDeepMimicEnv`;
the gate treats simulator action-space limits as derived (not as a hand-written Limit). The device is simulated R0, so
no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:HumanoidDeepMimic-v0`, level F0 (a reduced
scalar stand-in, not MuJoCo), determinism `seeded` with `seed_control` `parameter`, timestep 15 ms (frame_skip 5 times
the model's 0.003 s), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what
is not modelled: MuJoCo dynamics, contact and joint-range failures, cfrc_ext, the 81-number real observation, the
legacy gym action space, the host-specific asset path, the broken extrahard entry and rendering. The fake returns a
9-number reduced observation.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation and tick stay readable. No hardware backend and no hardware e-stop reference are claimed.

The card lists a second entry symbol, `humanoid_deepmimic.envs:HumanoidDeepMimicExtraHardEnv`. It cannot be confirmed:
`envs/__init__.py:2` imports it from a package that does not exist, and the only class in
`humanoid_deepmimic_extrahard_env.py` is the stub `FooEnv` (`:5-15`). This package implements the first confirmed
entry point only, as the authoring guide says for a card with several entry symbols.

Tags: deepmimic, humanoid, mujoco, reinforcement-learning, simulation, gym
