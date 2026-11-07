# Facts and tags for gh.telehuman/humanoidgen

Every fact cites its source at commit `015b808fd316629f499a903b5968f5b37fcd7573`: `vendor_doc` (a text file of the
clone such as README.md or requirements.txt) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The clone is
read-only; nothing in this package imports or runs it, and no hardware or simulator run is claimed.

| fact | source | ref |
|---|---|---|
| ManiSkill is the simulation platform named by the repository | vendor_doc | README.md:211 |
| The table_scene module imports BaseEnv from mani_skill.envs.sapien_env | upstream_code | humanoidgen/envs/example/table_scene.py:17 |
| TableEnv subclasses ManiSkill's BaseEnv | upstream_code | humanoidgen/envs/example/table_scene.py:83 |
| TableSetting subclasses TableEnv | upstream_code | humanoidgen/envs/example/table_scene.py:392 |
| BlocksStackEasyEnv subclasses TableSetting | upstream_code | humanoidgen/envs/example/blocks_stack_easy.py:4 |
| blocks_stack_easy is registered with max_episode_steps=200 | upstream_code | humanoidgen/envs/example/blocks_stack_easy.py:3 |
| The task adds two cube objects, one per object id | upstream_code | humanoidgen/envs/example/blocks_stack_easy.py:9-10 |
| The success test compares cube 0 with [-0.3, 0, 0.02] and cube 1 with [-0.3, 0, 0.06] using eps [0.03, 0.03, 0.01] | upstream_code | humanoidgen/envs/example/blocks_stack_easy.py:44-52 |
| TableSetting.reset takes seed and options and returns the (observation, info) tuple of BaseEnv.reset | upstream_code | humanoidgen/envs/example/table_scene.py:249-251 |
| TableSetting.step records the action and forwards it to BaseEnv.step | upstream_code | humanoidgen/envs/example/table_scene.py:909-922 |
| The run configuration selects env_id blocks_stack_easy, control_mode pd_joint_pos, num_envs 1, env_seed 0 and random_scene true | vendor_doc | humanoidgen/config/config_run_scene.yml:2-30 |
| The H1_2 upper body has 14 arm joints and the inspire hand has 24 finger joints | upstream_code | humanoidgen/agents/robots/unitree_h1_2/h1_2_upper_body.py:106-195 |
| The arm and finger controllers are PDJointPosControllerConfig with lower=None, upper=None and normalize_action=False, combined in the pd_joint_pos controller | upstream_code | humanoidgen/agents/robots/unitree_h1_2/h1_2_upper_body.py:213-245 |
| The table environment's simulation config sets control_freq=100 | upstream_code | humanoidgen/envs/example/table_scene.py:266 |
| The run loop creates the environment with gym.make(env_id) | upstream_code | humanoidgen/process/run_scene.py:54 |
| The run loop reads the robot's first 38 joint positions and passes them to env.step | upstream_code | humanoidgen/process/run_scene.py:61-63 |
| TableSetting.evaluate returns an empty dict | upstream_code | humanoidgen/envs/example/table_scene.py:1398-1399 |
| compute_dense_reward returns 1 and compute_normalized_dense_reward returns that value divided by 10 | upstream_code | humanoidgen/envs/example/table_scene.py:1408-1414 |
| The default sensor configuration adds a base_camera at 512 by 512 pixels | upstream_code | humanoidgen/envs/example/table_scene.py:278 |
| The H1_2 URDF is loaded from the assets directory of the clone | upstream_code | humanoidgen/agents/robots/unitree_h1_2/h1_2_upper_body.py:27 |
| The repository asks the user to download assets.zip and table_assets.zip into the assets directories | vendor_doc | README.md:90 |
| The pinned ManiSkill dependency is mani_skill==3.0.0b21 | vendor_doc | requirements.txt:1 |
| The codebase is under CC BY-NC 4.0 | vendor_doc | README.md:206 |

The concrete task is `BlocksStackEasyEnv` (blocks_stack_easy.py:4). The driver names the card's other entry symbol,
`TableSetting` (table_scene.py:392), as `native` because the concrete class reaches that base through
`from humanoidgen.envs.example.task_env import *` (blocks_stack_easy.py:1), a star import the gate's AST reader cannot
follow; `TableSetting` declares the `reset` and `step` the fake implements. The package is configuration only: the
Gymnasium bridge derives `cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1` from the fake's spaces and
methods.

Limits: the driver declares none. The default `pd_joint_pos` controllers pass `lower=None` and `upper=None`
(h1_2_upper_body.py:213-230), so the action envelope comes from the robot model in the external assets, which are not
in the clone; the package does not invent a bound. The fake's 38-element `Box` is therefore unbounded, the bridge
derives no action limit, and no input is `operator_required`. The 38 action elements are the 14 arm joints plus the 24
inspire-hand finger joints (h1_2_upper_body.py:106-195 and :245), which the run loop reads as the robot's first 38
joint positions (run_scene.py:61-63).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:humanoidgen blocks_stack_easy fake`, level F0
(the deployed fake is kinematic and echoes positions; the upstream class builds a SAPIEN rigid-body scene), determinism
`seeded` with `seed_control` `parameter`, timestep 10 ms (one control step at `control_freq=100`,
table_scene.py:266), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or restore. The gaps name the
missing physics and assets, the 38-float observation surrogate against the state observation and the 512 by 512
base camera, the absent success/reward model, the unbounded action envelope, the different random stream and the unrun
sim backend.

Safety: simulated R0 device. There is no hardware backend and no native stop. The runtime's software latch is the
independent stop: after an e-stop no step or reset is accepted until `mhs.safety.reset` clears the latch, and the
last observation stays readable. No operator is needed to clear a simulator latch.

Tags: humanoidgen, blocks-stack, manipulation, table, maniskill, sapien, simulation, gymnasium
