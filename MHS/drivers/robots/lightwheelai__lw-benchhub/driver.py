"""OpenMHS driver for gh.lightwheelai/lw-benchhub: the Robocasa-Rl-G1LiftObjStateRL Gymnasium environment.

LW-BenchHub is a robotics simulation benchmark built on Isaac Lab-Arena (README.md:7, pyproject.toml:11).
This package serves one of its registered Gymnasium environments, the Unitree G1 lift-a-cube task
(``Robocasa-Rl-G1LiftObjStateRL``, registered at ``lw_benchhub_rl/__init__.py:18-27``).  The card names the
simulator's task layer as its entry symbols; the environment class the registration points at is
``isaaclab.envs:ManagerBasedRLEnv``, which is not a card entry symbol.  ``native`` is therefore the card's
``LiftObj`` task class, the object that defines what the episode does (the cube, the success check and the
object placement), while the fake stands in for the single environment that ``gym.make`` builds from it.

A GymnasiumDriver is configuration only.  The bridge derives ``cap.world.step.v1`` from the action space and
``cap.world.reset.v1`` / ``cap.world.seed.v1`` from the environment's reset.  The environment's action space is an
unbounded Box in the Isaac Lab submodule's manager_based_rl_env.py:343, so no numeric action bound is declared
here; a wrong action is the environment's own business, not an MHS limit.  The device is simulated at R0 (the
catalogue ``cap.world.*`` classes are R0, and no physical effect is claimed).

Backends: ``fake`` is the package's pure-Python stand-in in ``fake.py``.  ``sim`` (a backend name ``backends``
does not list) is served by ``gymnasium.make("Robocasa-Rl-G1LiftObjStateRL")`` and needs the Isaac Sim 5.0 /
Isaac Lab GPU stack installed by the upstream ``install.sh``; that path was not run here.

Every Fact cites a line of the clone at the pinned commit b2bcb2d00edef691f9fcc49039cbf0bcc7464605.  The package is
model-authored and unreviewed (``driver.lock.json`` ``reviewed_by`` is null); only the fake backend was exercised.
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
PYPROJECT = "pyproject.toml"
ENV_BUILDER = "lw_benchhub/core/env_builder/env_builder.py"
TASK_BASE = "lw_benchhub/core/tasks/base.py"
LIFT_OBJ_TASK = "lw_benchhub_tasks/lightwheel_robocasa_tasks/single_stage/lift_obj.py"
RL_REGISTRATION = "lw_benchhub_rl/__init__.py"
RL_LIFT_OBJ = "lw_benchhub_rl/lift_obj/lift_obj.py"
G1_ROBOT = "lw_benchhub/core/robots/unitree/g1.py"
DEX3_GRIPPER = "lw_benchhub/core/models/grippers/dex3.py"


class LwBenchHubLiftObj(GymnasiumDriver):
    """The registered Gymnasium environment ``Robocasa-Rl-G1LiftObjStateRL`` of LW-BenchHub."""

    device_id = "lw-benchhub-g1-liftobj"
    env_id = "Robocasa-Rl-G1LiftObjStateRL"
    native = "lw_benchhub_tasks.lightwheel_robocasa_tasks.single_stage.lift_obj:LiftObj"
    backends = {"fake": ".fake:FakeG1LiftObjEnv"}
    display_name = "LW-BenchHub Robocasa-Rl-G1LiftObjStateRL (Unitree G1 cube lift)"
    vendor, model = "Lightwheel AI", "LW-BenchHub"
    tags = ["lw-benchhub", "robocasa", "unitree-g1", "manipulation", "isaac-lab-arena",
            "reinforcement-learning", "simulation", "gymnasium"]
    fidelity_level = "F1"
    facts = [
        Fact("LW-BenchHub describes itself as a unified benchmark hub built on Isaac Lab-Arena for embodied AI",
             source="vendor_doc", ref=f"{README}:7"),
        Fact("The package description is 'Isaac Lab based Benchmark for Robotics'", source="vendor_doc",
             ref=f"{PYPROJECT}:11"),
        Fact("The Gymnasium id Robocasa-Rl-G1LiftObjStateRL is registered with entry_point "
             "isaaclab.envs:ManagerBasedRLEnv and an env_cfg_entry_point in lw_benchhub_rl.lift_obj.lift_obj",
             source="upstream_code", ref=f"{RL_REGISTRATION}:18-27"),
        Fact("LwEnvBuilder takes the arena environment, the parsed arguments and the RL config, and lets the RL "
             "config modify the environment config", source="upstream_code", ref=f"{ENV_BUILDER}:29-45"),
        Fact("LwTaskBase is the base class of the package's task definitions", source="upstream_code",
             ref=f"{TASK_BASE}:163"),
        Fact("LwTaskBase.modify_env_cfg sets an 8.0 s episode, a 1/100 s physics step (100 Hz) and decimation 2",
             source="upstream_code", ref=f"{TASK_BASE}:241-249"),
        Fact("The task termination config binds success to the task's check_success_caller", source="upstream_code",
             ref=f"{TASK_BASE}:204-205"),
        Fact("The LiftObj task is named LiftObj", source="upstream_code", ref=f"{LIFT_OBJ_TASK}:40"),
        Fact("The LiftObj task fixes the object pose at (2.94, -4.08, 0.95)", source="upstream_code",
             ref=f"{LIFT_OBJ_TASK}:44"),
        Fact("The LiftObj object is sampled from the cube group and marked graspable", source="upstream_code",
             ref=f"{LIFT_OBJ_TASK}:58-66"),
        Fact("LiftObj success requires the object root height to be at least 0.965 m", source="upstream_code",
             ref=f"{LIFT_OBJ_TASK}:88-89"),
        Fact("The G1 RL right-arm action is a joint-position action over right_shoulder.*, right_wrist.* and "
             "right_elbow.*", source="upstream_code", ref=f"{G1_ROBOT}:194-197"),
        Fact("The Dex3 right hand uses a BinaryJointPositionActionCfg in the rl hand mode", source="upstream_code",
             ref=f"{DEX3_GRIPPER}:72-79"),
        Fact("The state-based G1 policy observation group concatenates joint position, joint velocity, the object "
             "pose command, the last action and the object position", source="upstream_code",
             ref=f"{RL_LIFT_OBJ}:63-79"),
        Fact("The RL task resets the object with x and y offsets in (-0.08, 0.08) and a yaw in (0, 90) degrees",
             source="upstream_code", ref=f"{RL_LIFT_OBJ}:139-146"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the deployed model (spec 05-fidelity section 2).  The upstream environment is an
    #: Isaac Lab GPU scene with rigid bodies and contacts (F1); the bridge runs it in lockstep and does not pace it.
    fidelity = {
        "engine": "isaaclab",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the task's object and robot randomization (LwTaskBase builds its rng from "
                     "the context seed); this package's fake repeats a trajectory for a seed, but no upstream GPU "
                     "run was made and bit-identical contact solving across machines is not claimed",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "Isaac Sim physics, PhysX contacts, the kitchen scene, the G1 USD articulation and the Dex3 hand are "
            "not modelled by this package's fake: it is a pure-Python analytic stand-in, not the upstream engine",
            "the fake steps 20 ms of control time per tick (the environment period from an 8.0 s episode, a "
            "1/100 s physics step and decimation 2 in LwTaskBase.modify_env_cfg); the underlying 10 ms physics "
            "substep is not integrated separately",
            "the fake's action effects and reward are placeholder test data; only the task name, the fixed object "
            "height 0.95 m and the success threshold 0.965 m come from the clone",
            "the real policy observation group dimension is computed at run time by the observation manager "
            "(ManagerBasedRLEnv._configure_gym_env_spaces); the fake publishes a reduced policy stand-in whose "
            "length is named in RESULT.json notes",
            "no rendering, no cameras, no image observations and no wall-clock pacing: realtime_factor 0",
            "snapshot and restore are not offered by the upstream ManagerBasedRLEnv, so snapshot_restore is false",
            "the upstream environment needs the Isaac Sim 5.0 and Isaac Lab GPU stack installed by install.sh; "
            "that path was not installed or run here",
        ],
    }
