# Facts and tags for gh.robotcontrolstack/duobench

Every fact cites its source at commit `29e09f916d68539d454c93266c195d2abb8a8253`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Each task is imported as duobench.tasks.<task_id> and registered as the Gymnasium environment duobench/<task_id>, with a <task_id>EnvConfig | vendor_doc | README.md:63-64 |
| DuoBench registers the ball_maze environment as duobench/ball_maze with the BallMazeEnvConfig entry point | upstream_code | src/duobench/tasks/ball_maze.py:251 |
| The ball_maze instruction is "pick up the board and tilt it so the ball rolls onto the red square" | upstream_code | src/duobench/tasks/ball_maze.py:28 |
| BallMazeStage has max_stage 4 and five stage texts, from "make contact with the maze" to "task completed; the ball has reached the goal" | upstream_code | src/duobench/tasks/ball_maze.py:85-105 |
| TaskStageWrapper.step returns the normalized stage as the reward and the stage tracker's success as terminated | upstream_code | src/duobench/tasks/__init__.py:77-80 |
| success is stage == max_stage and normalized_stage is stage / max_stage | upstream_code | src/duobench/tasks/__init__.py:36-42 |
| The info dictionary exposes success, stage, max_stage, current_subinstruction, stage_to_subinstructions and instruction | upstream_code | src/duobench/tasks/__init__.py:44-55 |
| BallMazeTask.add_task_env wraps the environment in RandomSquareObjsPos and then in BallMazeTaskWrapper | upstream_code | src/duobench/tasks/ball_maze.py:69-80 |
| RandomSquareObjsPos.reset draws the object placement from self.np_random and calls the wrapped reset with the seed only at the end | upstream_code | src/duobench/utils/helper_wrappers.py:187-204 |
| BallMazeTaskWrapper.reset spawns the ball at the start marker, resets the free-joint velocity, runs ten mj_step calls and adds the stage tracker info to the reset info | upstream_code | src/duobench/tasks/ball_maze.py:219-237 |
| The ball_maze stage tracker derives its stages from MuJoCo contacts and body positions: 4 when the ball is at the goal, 3 when it left the start area, 2 when the maze is lifted, 1 on arm contact and 0 otherwise | upstream_code | src/duobench/tasks/ball_maze.py:152-198 |
| The example action is a dict with left and right arms, each carrying a seven-number tquat and a one-number gripper | upstream_code | scripts/gym_make.py:31-34 |
| The example moves an arm 1 cm with tquat x 0.01, closes the gripper with 0 and opens it with 1 | upstream_code | scripts/gym_make.py:30-42 |
| The default config is optimized for teleoperation; the evaluation example switches to absolute joint control, async 30 Hz control and a binary gripper | vendor_doc | README.md:94-98 |
| The evaluation example sets the async control frequency to 30 | vendor_doc | README.md:112 |
| The FR3 arm model has seven joints, fr3_joint1 through fr3_joint7 | upstream_code | assets/robots/fr3/fr3.xml:44-91 |
| VentionSceneFR3Duo uses the vention world scene and the vention height offset as the root frame transform | upstream_code | src/duobench/utils/vention_config.py:8-13 |
| The upstream requires Python 3.11 or newer | upstream_code | pyproject.toml:23 |
| The upstream depends on rcs-core>=0.7.3, av, einops, scipy and tqdm | upstream_code | pyproject.toml:9-15 |
| TaskStageWrapper.step never lets the stage decrease within an episode: it restores the previous stage if the tracker reports a lower one | upstream_code | src/duobench/tasks/__init__.py:70-75 |
| The README states that the reward is the normalized task-stage progress and that terminated becomes True once the final stage is reached | vendor_doc | README.md:92 |
| DuoBench resolves its asset directory from DUOBENCH_PREFIX and defaults it to ~/.duobench | vendor_doc | README.md:51-53 |
| On import, DuoBench downloads the matching asset archive from GitHub if the asset path does not exist | vendor_doc | README.md:55 |

Limits: the driver declares none. The environment is simulated (R0): there is no physical bound to source and no
operator-required limit. `cap.world.step.v1` takes `ticks` (1 to `max_ticks`, 10000 by default) from the bridge and an
`action` whose schema the bridge derives from the environment's action space. On the fake backend that space is the
action dict of `scripts/gym_make.py:31-34` with placeholder bounds (marked in `fake.py`): the clone shows no bound for
the real space, so the fake's numeric bounds are test data, not a Limit. `cap.world.reset.v1` and
`cap.world.seed.v1` are seeded by the family bridge.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:duobench/ball_maze`, level F1 (rigid-body
dynamics with contacts), determinism `seeded` with `seed_control` `parameter`, timestep 33.333 ms (the README's 30 Hz
evaluation control period, `README.md:112`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say that the fake is kinematic, that its action bounds and observation are placeholders, that the
default teleoperation rate and the MuJoCo physics substep are not in the clone, that the seed is applied after the
object draw, and that no physical device was modelled.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the simulator has no native stop); after it
no step or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: duobench, ball-maze, bimanual, franka-research-3, mujoco, reinforcement-learning, simulation, gymnasium
