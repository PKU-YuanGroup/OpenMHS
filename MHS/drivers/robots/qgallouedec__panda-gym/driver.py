"""OpenMHS driver for gh.qgallouedec/panda-gym: the PandaReach-v3 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values}`` bounded
element by element by ``Box(-1.0, 1.0, shape=(3,))`` (the end-effector displacement), ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

PandaReach-v3 is a PyBullet simulation of a Franka Panda arm that must move its end-effector to a sampled goal.  The
gate cannot import panda-gym (it needs gymnasium, pybullet, numpy and scipy, setup.py:23), so the ``fake`` backend is
the package's own pure Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served
by ``gymnasium.make("PandaReach-v3")`` (GymnasiumDriver.open_native); that path needs the upstream package and was not
run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (10c4d8adaab07d8a29b2f8dc0aa85f8edd8532ae).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "panda_gym/__init__.py"
TASKS = "panda_gym/envs/panda_tasks.py"
CORE = "panda_gym/envs/core.py"
PANDA = "panda_gym/envs/robots/panda.py"
REACH = "panda_gym/envs/tasks/reach.py"
UTILS = "panda_gym/utils.py"
PYBULLET = "panda_gym/pybullet.py"


class PandaReach(GymnasiumDriver):
    device_id = "panda-reach"
    env_id = "PandaReach-v3"
    native = "panda_gym.envs.panda_tasks:PandaReachEnv"
    backends = {"fake": ".fake:FakePandaReachEnv"}
    action_space_ref = f"{PANDA}:31-33"
    display_name = "panda-gym PandaReach-v3 (PyBullet)"
    vendor, model = "Quentin Gallouedec", "PandaReach-v3"
    tags = ["panda", "franka", "reach", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("panda-gym is a set of robotic environments based on the PyBullet physics engine and gymnasium",
             source="vendor_doc", ref="README.md:3"),
        Fact("The documented use is gym.make('PandaReach-v3', render_mode='human') followed by reset() and "
             "step(action)", source="vendor_doc", ref="docs/guide/quick_start.rst:6-19"),
        Fact("PandaReach-v3 is registered with entry point panda_gym.envs:PandaReachEnv, kwargs reward_type='sparse' "
             "and control_type='ee', and max_episode_steps=50 (100 only for Stack)",
             source="upstream_code", ref=f"{INIT}:10-21"),
        Fact("PandaReachEnv builds the Panda robot with block_gripper=True, so the gripper is not part of the action",
             source="upstream_code", ref=f"{TASKS}:202"),
        Fact("Panda's action space is Box(-1.0, 1.0, shape=(n_action,)) in float32, with n_action 3 for end-effector "
             "control and 7 for joint control, plus one for the gripper when it is not blocked",
             source="upstream_code", ref=f"{PANDA}:31-33"),
        Fact("An end-effector action moves the target by at most 0.05 per step and the target height is clipped to "
             "0 or above", source="upstream_code", ref=f"{PANDA}:81-86"),
        Fact("The Reach distance_threshold defaults to 0.05 and goal_range to 0.3",
             source="upstream_code", ref=f"{REACH}:15-16"),
        Fact("The Reach goal is drawn uniformly from goal_range_low [-0.15, -0.15, 0] to goal_range_high "
             "[0.15, 0.15, 0.3]", source="upstream_code", ref=f"{REACH}:22-23"),
        Fact("distance is the Euclidean norm rounded to 6 decimals", source="upstream_code",
             ref=f"{UTILS}:15-17"),
        Fact("Reach.is_success returns True when the distance is below the threshold", source="upstream_code",
             ref=f"{REACH}:55-57"),
        Fact("The sparse Reach reward is -1 outside the threshold and 0 inside it; the dense reward is minus the "
             "distance", source="upstream_code", ref=f"{REACH}:59-64"),
        Fact("Panda.get_obs returns the end-effector position and velocity, and omits the finger width when the "
             "gripper is blocked", source="upstream_code", ref=f"{PANDA}:109-119"),
        Fact("Reach has no task-specific observation and its achieved goal is the end-effector position",
             source="upstream_code", ref=f"{REACH}:39-44"),
        Fact("RobotTaskEnv concatenates the robot and task observations and adds the achieved and desired goals",
             source="upstream_code", ref=f"{CORE}:265-274"),
        Fact("The RobotTaskEnv observation space is a Dict of three Box(-10.0, 10.0) members",
             source="upstream_code", ref=f"{CORE}:237-243"),
        Fact("RobotTaskEnv.reset seeds gym.Env, gives the task the same generator, resets the robot and the task, and "
             "returns is_success", source="upstream_code", ref=f"{CORE}:276-286"),
        Fact("Panda.reset sets the neutral joint values", source="upstream_code", ref=f"{PANDA}:121-126"),
        Fact("Reach.reset samples a new goal and places the target there", source="upstream_code",
             ref=f"{REACH}:46-53"),
        Fact("RobotTaskEnv.step applies the action, advances the simulation once, terminates on task success, sets "
             "truncated=False and computes the reward", source="upstream_code", ref=f"{CORE}:316-325"),
        Fact("PyBullet sets the physics timestep to 1/500 s and exposes dt as timestep * n_substeps",
             source="upstream_code", ref=f"{PYBULLET}:53-64"),
        Fact("n_substeps defaults to 20", source="upstream_code", ref=f"{PYBULLET}:28"),
        Fact("PyBullet.step advances n_substeps physics steps per call", source="upstream_code",
             ref=f"{PYBULLET}:66-70"),
        Fact("The runtime dependencies are gymnasium>=0.26, pybullet, numpy<2 and scipy", source="upstream_code",
             ref="setup.py:23"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:PandaReach-v3",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds gym.Env and the task shares that generator (core.py:276-286), so one "
                     "implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "samples goals with Python's random.Random and upstream with numpy's generator, so one seed "
                     "gives different goals on the two",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body PyBullet model of a Franka Panda arm, a table and a target sphere; the fake moves the "
            "end-effector by the clipped action times 0.05 and models neither inverse kinematics nor contacts, "
            "friction, actuators or sensor noise",
            "no rendering: render_mode is not served and the fake has no renderer",
            "the fake samples goals with Python's random.Random while upstream draws them from numpy's generator, "
            "so one seed can give different goals and trajectories",
            "the fake applies the 50-step TimeLimit that gymnasium.make adds to PandaReach-v3; RobotTaskEnv.step "
            "itself never truncates",
            "no snapshot and restore through get_state/set_state; the upstream environment has save_state, "
            "restore_state and remove_state, which the bridge does not use",
            "the fake's start end-effector position is test data, not a calibrated model, so its trajectories were "
            "not compared with a PyBullet run",
            "observations are Python float lists; upstream returns float32 numpy arrays of the same six (robot) and "
            "three (goal) values",
        ],
    }
