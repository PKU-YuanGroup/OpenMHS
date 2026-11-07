"""OpenMHS driver for gh.robotcontrolstack/duobench: the registered ``duobench/ball_maze`` environment.

DuoBench is the FR3 Duo bimanual-manipulation benchmark.  Each task module registers one Gymnasium environment as
``duobench/<task_id>`` (``src/duobench/tasks/ball_maze.py:251``).  This package targets ``duobench/ball_maze``, whose
task wrapper returns the normalized stage as reward and the final stage as ``terminated``
(``src/duobench/tasks/__init__.py:77-80``), with the task instruction and four stage texts in the clone
(``src/duobench/tasks/ball_maze.py:28`` and ``:85-105``).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``, where the action is the dict the
clone's example sends (``left`` and ``right`` arms, each with a seven-number ``tquat`` and a one-number ``gripper``;
``scripts/gym_make.py:31-34``); ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The clone states no bounds for that action space, so the space the bridge reads on the fake backend uses
placeholder bounds ("test data", see ``fake.py``), and the fake's 8-element observation is a placeholder too: the RCS
observation is not described in the clone.

The gate cannot import RCS, MuJoCo or numpy (``pyproject.toml:9-15`` and ``:23``), and package code never imports the
clone, so the ``fake`` backend is the package's own pure Python stand-in.  A backend name that ``backends`` does not
list (``sim``) would be served by ``gymnasium.make("duobench/ball_maze")`` (GymnasiumDriver.open_native), but the task
module must first be imported and a config object passed as ``cfg``; this configuration-only driver does neither, so
that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the MuJoCo FR3 Duo
simulation with the README's 30 Hz evaluation control period, its seeded reset and honest ``gaps`` for what the fake
does not model.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BALL_MAZE = "src/duobench/tasks/ball_maze.py"
TASKS = "src/duobench/tasks/__init__.py"
HELPERS = "src/duobench/utils/helper_wrappers.py"
VENTION = "src/duobench/utils/vention_config.py"
EXAMPLE = "scripts/gym_make.py"
FR3 = "assets/robots/fr3/fr3.xml"
README = "README.md"
PYPROJECT = "pyproject.toml"


class DuoBenchBallMaze(GymnasiumDriver):
    device_id = "duobench-ball-maze"
    env_id = "duobench/ball_maze"
    native = "duobench.tasks.ball_maze:BallMazeTaskWrapper"
    backends = {"fake": ".fake:FakeBallMazeEnv"}
    display_name = "DuoBench ball_maze (FR3 Duo bimanual manipulation)"
    vendor, model = "RobotControlStack", "DuoBench ball_maze"
    tags = ["duobench", "ball-maze", "bimanual", "franka-research-3", "mujoco", "reinforcement-learning",
            "simulation", "gymnasium"]
    facts = [
        Fact("Each task is imported as duobench.tasks.<task_id> and registered as the Gymnasium environment "
             "duobench/<task_id>, with a <task_id>EnvConfig", source="vendor_doc", ref=f"{README}:63-64"),
        Fact("DuoBench registers the ball_maze environment as duobench/ball_maze with the BallMazeEnvConfig entry "
             "point", source="upstream_code", ref=f"{BALL_MAZE}:251"),
        Fact("The ball_maze instruction is \"pick up the board and tilt it so the ball rolls onto the red square\"",
             source="upstream_code", ref=f"{BALL_MAZE}:28"),
        Fact("BallMazeStage has max_stage 4 and five stage texts, from \"make contact with the maze\" to "
             "\"task completed; the ball has reached the goal\"", source="upstream_code",
             ref=f"{BALL_MAZE}:85-105"),
        Fact("TaskStageWrapper.step returns the normalized stage as the reward and the stage tracker's success as "
             "terminated", source="upstream_code", ref=f"{TASKS}:77-80"),
        Fact("success is stage == max_stage and normalized_stage is stage / max_stage", source="upstream_code",
             ref=f"{TASKS}:36-42"),
        Fact("The info dictionary exposes success, stage, max_stage, current_subinstruction, "
             "stage_to_subinstructions and instruction", source="upstream_code", ref=f"{TASKS}:44-55"),
        Fact("BallMazeTask.add_task_env wraps the environment in RandomSquareObjsPos and then in "
             "BallMazeTaskWrapper", source="upstream_code", ref=f"{BALL_MAZE}:69-80"),
        Fact("RandomSquareObjsPos.reset draws the object placement from self.np_random and calls the wrapped reset "
             "with the seed only at the end", source="upstream_code", ref=f"{HELPERS}:187-204"),
        Fact("BallMazeTaskWrapper.reset spawns the ball at the start marker, resets the free-joint velocity, runs "
             "ten mj_step calls and adds the stage tracker info to the reset info", source="upstream_code",
             ref=f"{BALL_MAZE}:219-237"),
        Fact("The ball_maze stage tracker derives its stages from MuJoCo contacts and body positions: 4 when the "
             "ball is at the goal, 3 when it left the start area, 2 when the maze is lifted, 1 on arm contact and "
             "0 otherwise", source="upstream_code", ref=f"{BALL_MAZE}:152-198"),
        Fact("The example action is a dict with left and right arms, each carrying a seven-number tquat and a "
             "one-number gripper", source="upstream_code", ref=f"{EXAMPLE}:31-34"),
        Fact("The example moves an arm 1 cm with tquat x 0.01, closes the gripper with 0 and opens it with 1",
             source="upstream_code", ref=f"{EXAMPLE}:30-42"),
        Fact("The default config is optimized for teleoperation; the evaluation example switches to absolute joint "
             "control, async 30 Hz control and a binary gripper", source="vendor_doc", ref=f"{README}:94-98"),
        Fact("The evaluation example sets the async control frequency to 30", source="vendor_doc",
             ref=f"{README}:112"),
        Fact("The FR3 arm model has seven joints, fr3_joint1 through fr3_joint7", source="upstream_code",
             ref=f"{FR3}:44-91"),
        Fact("VentionSceneFR3Duo uses the vention world scene and the vention height offset as the root frame "
             "transform", source="upstream_code", ref=f"{VENTION}:8-13"),
        Fact("The upstream requires Python 3.11 or newer", source="upstream_code", ref=f"{PYPROJECT}:23"),
        Fact("The upstream depends on rcs-core>=0.7.3, av, einops, scipy and tqdm", source="upstream_code",
             ref=f"{PYPROJECT}:9-15"),
        Fact("TaskStageWrapper.step never lets the stage decrease within an episode: it restores the previous stage "
             "if the tracker reports a lower one", source="upstream_code", ref=f"{TASKS}:70-75"),
        Fact("The README states that the reward is the normalized task-stage progress and that terminated becomes "
             "True once the final stage is reached", source="vendor_doc", ref=f"{README}:92"),
        Fact("DuoBench resolves its asset directory from DUOBENCH_PREFIX and defaults it to ~/.duobench",
             source="vendor_doc", ref=f"{README}:51-53"),
        Fact("On import, DuoBench downloads the matching asset archive from GitHub if the asset path does not exist",
             source="vendor_doc", ref=f"{README}:55"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable; the simulator has no "
                  "native stop")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:duobench/ball_maze",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds gymnasium's np_random and the MuJoCo dynamics are deterministic for a "
                     "fixed state and action; RandomSquareObjsPos.reset draws the object placement from "
                     "self.np_random before the wrapped reset applies the seed (helper_wrappers.py:187-204), so a "
                     "new seed reaches the placement on the next reset. The package fake seeds random.Random "
                     "directly and is deterministic, but it is not the upstream model.",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic: it models no MuJoCo contacts, rigid-body dynamics, ball, board, "
            "cameras or robot state, its arm positions and stage thresholds are placeholders, and it ignores the "
            "quaternion part of tquat",
            "the action Box bounds and the 8-element observation are placeholders: the clone shows the action "
            "dict shape (left/right, tquat and gripper) but states no bounds, and it does not describe the RCS "
            "observation; the real environment's spaces are derived by the sim backend, which was not run",
            "the 33.333 ms timestep is the README's 30 Hz evaluation control period (README.md:112); the default "
            "teleoperation rate and the MuJoCo physics substep are set by RCS and are not stated in the clone",
            "RandomSquareObjsPos.reset draws the object placement before the wrapped reset applies the seed "
            "(helper_wrappers.py:187-204), so the first reset with a new seed may not repeat; the fake seeds "
            "random.Random directly instead",
            "reset options are accepted but not modelled: the fake ignores them",
            "the fake returns truncated=False and models no episode time limit; the clone states none for the "
            "task wrapper",
            "no rendering and no recording are offered; the real environment imports RCS and downloads the asset "
            "archive on first use (README.md:55), neither of which this package does",
            "no physical device is modelled and the benchmark was never validated against a device",
        ],
    }
