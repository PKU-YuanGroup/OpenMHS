# Facts and tags for gh.renforce-dynamics/genesislab

Every fact cites its source at commit `0f2e4d96df9b24bcce66f8bdf7a1884a1363a5bb`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Genesis-HVelocity-G1-v0 is registered with the entry point genesislab.envs:ManagerBasedRlEnv | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/g1/__init__.py:4-13 |
| ManagerBasedRlEnv subclasses ManagerBasedGenesisEnv and keeps its reset/step semantics | upstream_code | source/genesislab/genesislab/envs/manager_based_rl_env.py:28-34 |
| The environment is vectorized: is_vector_env is True and metadata declares render modes | upstream_code | source/genesislab/genesislab/envs/manager_based_genesis_env.py:48-55 |
| reset(seed=None, env_ids=None, options=None) returns (observations, info) | upstream_code | source/genesislab/genesislab/envs/manager_based_genesis_env.py:206-261 |
| step(action) returns (observations, rewards, terminations, time-outs and info) | upstream_code | source/genesislab/genesislab/envs/manager_based_genesis_env.py:263-293 |
| The scene physics timestep is dt = 0.005 s | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/components.py:31 |
| The control step is decimation 4 physics steps | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/hvelocity_env_cfg.py:32 |
| The episode length is 20.0 s | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/hvelocity_env_cfg.py:33 |
| The G1 asset is the 29-DOF MJCF g1_29dof_rev_1_0.xml with control_dofs None (all DOF) | upstream_code | source/genesis_assets/genesis_assets/robots/g1/official.py:44-49 |
| The joint position action is scaled by 0.25 and uses the default joint offset | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/components.py:92-96 |
| The policy observation terms are concatenated into one group | upstream_code | source/genesis_tasks/genesis_tasks/locomotion/hvelocity/components.py:133 |
| A reset with a seed calls seed(seed), which sets cfg.seed and seeds torch and Python random | upstream_code | source/genesislab/genesislab/envs/manager_based_genesis_env.py:106-116 |
| The observation is a dict of tensors and a step returns five signals | upstream_code | source/genesislab/genesislab/envs/common/viewer.py:54-63 |
| The environment assigns a torch zeros tensor to action_space and leaves observation_space None | upstream_code | source/genesislab/genesislab/envs/manager_based_genesis_env.py:156-165 |
| GenesisLab is built on top of the Genesis physics engine | vendor_doc | README.md:13 |

Limits: the driver declares none. The device is simulated (R0) and has no physical effect. The action term has no clip
(`components.py:92-96`), and the upstream environment exposes no Gymnasium action or observation space
(`manager_based_genesis_env.py:156-165`), so there is no sourced numeric bound to declare and no operator-required
bound either. `cap.world.step.v1` still bounds `ticks` at 1 to 10000 by the family bridge, not by this package.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `genesis`, level F1 (rigid-body dynamics with contacts in
the Genesis engine), determinism `seeded` with `seed_control` `parameter`, timestep 20 ms (`dt` 0.005 s at
`components.py:31` times decimation 4 at `hvelocity_env_cfg.py:32`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot or restore. The fake backend is a kinematic stand-in and is not the Genesis simulator; the gaps
say so and record that no upstream rollout was made.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: genesis, genesislab, gymnasium, humanoid, g1, reinforcement-learning, simulation
