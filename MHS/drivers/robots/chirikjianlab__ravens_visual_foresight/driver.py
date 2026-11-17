"""OpenMHS driver for gh.chirikjianlab/ravens_visual_foresight: the PyBullet rearrangement benchmark (simulated).

The card's family is ``gymnasium`` and the task is a sim-env.  The entry is ``EnvironmentMCTS``, the class the data
collection script drives (``ravens/demos_tvf.py:27-33``): a legacy Gym-style ``Environment`` subclass whose
``step(action)`` applies ``pose0`` as a pick and ``pose1`` as a place and returns
``([pick_obs, place_obs], reward, done, info)`` (``ravens/environments/environment_mcts.py:58-116``), and whose
``reset()`` returns a 6-tuple (``:123-166``).  The SDK's ``GymnasiumBridge`` reads the action space and applies its
legacy 4-tuple/6-tuple paths.  ``env_id`` is not set because the clone registers no Gym environment; the ``fake``
backend is the package's analytic model of the demo's default ``put-block-base`` task.

The upstream simulator needs ``pybullet``, ``gym==0.17.3`` and the ``ravens/environments/assets`` tree
(``requirements.txt``).  None is importable where this package is checked, and package code never imports the clone:
only the fake backend was run.  The fake is a pure-Python kinematic model, so the deployed fidelity is F0 and the
gaps below say what it omits.  This package is model-authored and unreviewed; the fake evidence does not establish a
PyBullet or hardware run.
"""

from mhs.driver import Fact, GymnasiumDriver

from .adapter import RavensPoseBridge

ENVIRONMENT = "ravens/environments/environment.py"
ENVIRONMENT_MCTS = "ravens/environments/environment_mcts.py"
CAMERAS = "ravens/tasks/cameras.py"
DEMOS = "ravens/demos_tvf.py"
TASK = "ravens/tasks/put_block_base_mcts.py"
TASK_BASE = "ravens/tasks/task_mcts.py"
TASK_REGISTRY = "ravens/tasks/__init__.py"


class RavensVisualForesight(GymnasiumDriver):
    """The Ravens-Visual-Foresight rearrangement environment, served through the Gymnasium bridge."""

    device_id = "ravens_visual_foresight"
    native = "ravens.environments.environment_mcts:EnvironmentMCTS"
    backends = {"fake": ".fake:FakeEnvironmentMCTS"}
    action_space_ref = f"{ENVIRONMENT}:89-102"
    display_name = "Ravens Visual Foresight (PyBullet rearrangement benchmark)"
    vendor, model = "Chirikjian Lab", "Ravens-Visual-Foresight"
    tags = ["ravens", "visual-foresight", "pick-place", "rearrangement", "pybullet", "simulation", "gymnasium"]

    def make_bridge(self, native):
        return RavensPoseBridge(env=native, device_id=self.device_id, seed=self.seed,
                                autoreset=self.autoreset, max_ticks=self.max_ticks,
                                env_origin="the fake backend .fake:FakeEnvironmentMCTS",
                                action_space_ref=self.action_space_ref)

    facts = [
        Fact("Environment is a gym.Env subclass and its docstring calls it an OpenAI Gym-style environment class",
             source="upstream_code", ref=f"{ENVIRONMENT}:42-43"),
        Fact("The constructor's default control frequency is hz=240 and p.setTimeStep(1. / hz) sets the simulation "
             "timestep from it", source="upstream_code", ref=f"{ENVIRONMENT}:50-138"),
        Fact("The action space is a Dict with pose0 and pose1; each is a Tuple of a 3-vector position bounded low "
             "[0.25, -0.5, 0.] and high [0.75, 0.5, 0.28] and a 4-vector orientation bounded -1.0 to 1.0",
             source="upstream_code", ref=f"{ENVIRONMENT}:89-102"),
        Fact("The observation space is a Dict of color and depth Tuples, one entry per camera; color is 0..255 "
             "uint8 and depth is 0.0..20.0 float32", source="upstream_code", ref=f"{ENVIRONMENT}:77-88"),
        Fact("The environment uses three RealSense D415 cameras declared with image_size (480, 640)",
             source="upstream_code", ref=f"{CAMERAS}:22-26"),
        Fact("EnvironmentMCTS.step treats pose0 as the PICK pose and pose1 as the PLACE pose and returns "
             "[pick_obs, place_obs], reward, done, info", source="upstream_code", ref=f"{ENVIRONMENT_MCTS}:58-116"),
        Fact("EnvironmentMCTS.reset resets the task, calls step() with no action, and returns the 6-tuple "
             "(init_obs, base_urdf, base_size, base_id, objs_id, info)",
             source="upstream_code", ref=f"{ENVIRONMENT_MCTS}:159-166"),
        Fact("demos_tvf.py defaults --task to put-block-base, builds tasks.names[task + '-mcts'], and runs "
             "EnvironmentMCTS with hz=480", source="upstream_code", ref=f"{DEMOS}:12-33"),
        Fact("The task registry maps 'put-block-base-mcts' to PutBlockBaseMCTS", source="upstream_code",
             ref=f"{TASK_REGISTRY}:70"),
        Fact("PutBlockBaseMCTS has 3 blocks, a stand base of size (0.05, 0.15, 0.005), three place positions on "
             "the base, and max_steps = num_blocks + 2", source="upstream_code", ref=f"{TASK}:27-57"),
        Fact("PutBlockBaseMCTS appends one goal with its object list and max_reward 1", source="upstream_code",
             ref=f"{TASK}:81-82"),
        Fact("TaskMCTS.reward adds max_reward / len(objs) to step_reward", source="upstream_code",
             ref=f"{TASK_BASE}:240"),
        Fact("TaskMCTS.done returns true when no goals remain or the accumulated reward exceeds 0.99",
             source="upstream_code", ref=f"{TASK_BASE}:316"),
        Fact("Environment.seed sets a numpy RandomState for the environment's random generator and returns the seed",
             source="upstream_code", ref=f"{ENVIRONMENT}:175-177"),
        Fact("The reset loads a UR5 arm with a suction end effector and moves its joints to the home configuration",
             source="upstream_code", ref=f"{ENVIRONMENT_MCTS}:140-154"),
        Fact("The put-block-base task's workspace bounds are x 0.25..0.75, y -0.25..0.25 and z 0..0.28",
             source="upstream_code", ref=f"{TASK}:44"),
        Fact("The task sets block_size to (0.04, 0.04, 0.04)", source="upstream_code", ref=f"{TASK}:25"),
    ]
    safe_state = ("the analytic world stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the last observation and block layout stay readable")
    #: The fidelity contract of the fake as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism and lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial block layout and every transition is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "fake draws with Python's random.Random while upstream Environment.seed uses numpy's "
                     "RandomState, so the two do not produce the same scene for one seed",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic kinematic pick-and-place: block poses are updated directly, with no rigid-body dynamics, "
            "contacts, friction, suction, actuator, sensor or noise model, and the UR5 arm is not simulated",
            "the fake models only the demo's default put-block-base-mcts task (3 blocks, 3 target positions) and "
            "not the other 13 MCTS task classes in the registry",
            "the fake's observation is an 8x8 placeholder colour/depth image per camera, not the upstream 480x640 "
            "(cameras.py:26) RGB-D render, and its values are test data, not sensor measurements",
            "the fake samples block poses uniformly inside the task bounds instead of upstream's collision-free "
            "get_random_pose over the rendered free-space mask, and it ignores pose orientation when matching",
            "the fake uses Python random.Random, upstream Environment.seed uses numpy RandomState and the demo "
            "script seeds the global np.random (demos_tvf.py:50), so one seed gives different scenes on the two",
            "the SDK's legacy reset path serves only the first element of the native 6-tuple: base_urdf, "
            "base_size, base_id and objs_id are not carried in the reset receipt",
            "cap.world.reset.v1 advertises an options object, but the native reset(self) accepts neither options "
            "nor a seed keyword; the bridge's legacy fallback calls env.seed(seed) and then reset() and drops "
            "options",
            "the action space is the base Environment space (y -0.5..0.5) because EnvironmentMCTS overrides "
            "position_bounds after the base __init__ without rebuilding action_space; the task's own workspace "
            "bounds are y -0.25..0.25 (put_block_base_mcts.py:44)",
            "the package's pose adapter supplies numeric tuple schemas and source-backed coordinate and "
            "quaternion bounds that the generic bridge does not derive; an out-of-envelope pose is refused "
            "before native dispatch, rather than treated as a fake timeout",
            "a live EnvironmentMCTS requires assets_root and a configured task, opens a PyBullet client and "
            "loads plugins during construction; step waits without a deadline for objects to settle; no live "
            "backend is declared or validated",
            "no wall-clock pacing: realtime_factor 0, ticks advance the analytic step count only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
