# Facts and tags for gh.emb-ai/robobenchmart

Every fact cites its source at commit `33ca547ffeb4e4aac9af53bd685b17c05b971fc8`: `upstream_code` is a line of the
clone's Python code, and `vendor_doc` is a text file of the clone (README.md). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository describes dsynth as specialized ManiSkill environments for retail setups, with scene generation, motion planning and policy evaluation | vendor_doc | README.md:7 |
| The ManiSkill simulator requires the Vulkan API | vendor_doc | README.md:15 |
| The README instructs downloading RoboCasa assets and the RoboBenchMart assets from separate sources | vendor_doc | README.md:45-55 |
| MoveFromBoardToBoardVanishContEnv is registered with max_episode_steps=200000 | upstream_code | dsynth/envs/move_from_board_to_board.py:459-460 |
| MoveFromBoardToBoardContEnv documents the task as picking the target item and placing it one board higher, with the robot spawned near the shelf | upstream_code | dsynth/envs/move_from_board_to_board.py:335-336 |
| DarkstoreCellBaseEnv derives from ManiSkill's BaseEnv | upstream_code | dsynth/envs/darkstore_cell_base.py:29 |
| The environment constructor requires config_dir_path, the scene directory | upstream_code | dsynth/envs/darkstore_cell_base.py:33-41 |
| reset accepts seed and options and reads reconfigure and robot_init_pose_seed from the options | upstream_code | dsynth/envs/darkstore_cell_base.py:79-85 |
| The policy client builds the environment with gym.make(env_id, config_dir_path=<scene dir>, num_envs=1, control_mode=..., ...) | upstream_code | scripts/eval_policy_client.py:100-110 |
| The policy client resets the environment with a seed and an options dictionary | upstream_code | scripts/eval_policy_client.py:161 |
| The policy client calls env.step(action) and receives obs, reward, done, trunc and info | upstream_code | scripts/eval_policy_client.py:175 |
| The policy client zeroes action[8] and action[9], so its action vectors have at least ten float components | upstream_code | scripts/eval_policy_client.py:171-174 |
| The policy client reads three RGB camera images and the agent qpos from the observation | upstream_code | scripts/eval_policy_client.py:32-44 |
| The target size is 0.3 m on each axis | upstream_code | dsynth/envs/move_from_board_to_board.py:26 |
| The placement tolerance is half of target_sizes on each axis | upstream_code | dsynth/envs/move_from_board_to_board.py:263 |
| The robot is static when its q velocity is below 0.2 | upstream_code | dsynth/envs/move_from_board_to_board.py:285 |
| A non-target product counts as displaced when its pose leaves the initial pose by more than rtol/atol 0.1 | upstream_code | dsynth/envs/move_from_board_to_board.py:300 |
| The success condition is object placed and robot static and no non-target product displaced | upstream_code | dsynth/envs/move_from_board_to_board.py:314-320 |
| The interboard height is 0.397 m | upstream_code | dsynth/envs/move_from_board_to_board.py:368-370 |
| The task docstring says the target item must be within TARGET_POS_THRESH of the goal, other items move by no more than 0.1 m and the robot q velocity stays below 0.2 | upstream_code | dsynth/envs/move_from_board_to_board.py:452-455 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` of ten values in [-1, 1] in the package fake, with no source and the ref
`action_space of the fake backend .fake:FakeMoveFromBoardToBoardVanishContEnv`); those values are test
data of the fake and are not a stated upstream bound. `ticks` (1 to 10000) is the bridge's own limit. The device is
simulated (R0), so no limit is `operator_required` and there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:dsynth-fake`, level F0 (kinematic joint
updates, no dynamics, contacts, actuators, sensors or cameras), determinism `seeded` with `seed_control` `parameter`,
timestep 0 ms (the clone states no fixed timestep), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot or
restore. The gaps say what is not modelled, that the real observation also contains three RGB camera streams, and that
the fake was never compared with the upstream ManiSkill environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: robobenchmart, retail, manipulation, reinforcement-learning, simulation, gymnasium, mani-skill
