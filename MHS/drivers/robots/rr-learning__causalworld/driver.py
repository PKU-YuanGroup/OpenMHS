"""OpenMHS driver for gh.rr-learning/causalworld: the CausalWorld TriFinger manipulation environment.

A GymnasiumDriver is configuration only: the bridge derives ``cap.world.step.v1`` (``{ticks, action}``),
``cap.world.reset.v1`` (``{seed, options}``) and ``cap.world.seed.v1`` (``{seed}``) from the environment's spaces.
``CausalWorld`` is an old-style ``gym.Env``: ``reset()`` takes no seed and returns the observation, ``step(action)``
returns the four-value ``(observation, reward, done, info)`` and ``seed(seed)`` reseeds the generator.  The Gymnasium
bridge has explicit fallbacks for both shapes (``mhs/bridge/gymnasium.py``), so the family shape expresses the real
interface.  The device is simulated (R0): there is no hardware backend and no stop path to a machine.

CausalWorld registers no ``gym.make`` id; the documented construction is ``CausalWorld(task=generate_task(...))``
(README.md:215).  ``env_id`` is therefore unset, and a backend name that ``backends`` does not list (``sim``) would
make the bridge call ``gymnasium.make(None)`` and fail with ``MHS.DEVICE.NOT_READY``.  The clone also needs pybullet,
gym and numpy, and package code never imports or runs the clone, so the only served backend is the package's own pure
Python fake.  This package covers the default reaching task with structured observations.

The ``fidelity`` block describes the model as deployed on the checked fake backend (spec 05-fidelity FID-002): the
fake is an analytic kinematic stand-in, level F0, seeded, 40 ms control step, lockstep clock, full reset, no
snapshot.  The upstream PyBullet model, its contacts and its 4 ms physics substeps are not modelled and are named in
the gaps.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "causal_world/envs/causalworld.py"
ACTION = "causal_world/envs/robot/action.py"
OBSERVATIONS = "causal_world/envs/robot/observations.py"
REACHING = "causal_world/task_generators/reaching.py"
BASE = "causal_world/task_generators/base_task.py"
SILHOUETTE = "causal_world/envs/scene/silhouette.py"
SPACES = "causal_world/utils/env_utils.py"


class CausalWorld(GymnasiumDriver):
    device_id = "causalworld"
    #: CausalWorld registers no gym.make id; the documented factory is CausalWorld(task=generate_task(...)).
    env_id = None
    native = "causal_world.envs.causalworld:CausalWorld"
    backends = {"fake": ".fake:FakeCausalWorld"}
    display_name = "rr-learning CausalWorld TriFinger benchmark (PyBullet)"
    vendor, model = "rr-learning", "CausalWorld"
    tags = ["causalworld", "trifinger", "robotic-manipulation", "pybullet", "reinforcement-learning", "simulation",
            "gym"]
    facts = [
        Fact("CausalWorld subclasses gym.Env, the legacy OpenAI Gym environment API", source="upstream_code",
             ref=f"{ENV}:18"),
        Fact("With visualization disabled the structured observation mode uses an in-process PyBullet client "
             "connected with pybullet.DIRECT", source="upstream_code", ref=f"{ENV}:962-967"),
        Fact("The documented use constructs the environment as CausalWorld(task=task, enable_visualization=True)",
             source="vendor_doc", ref="README.md:215"),
        Fact("The constructor defaults to structured observations, joint_positions actions and normalized actions "
             "and observations", source="upstream_code", ref=f"{ENV}:29-32"),
        Fact("One environment step multiplies a 1/250 s simulation step by skip_frame", source="upstream_code",
             ref=f"{ENV}:93-96"),
        Fact("skip_frame defaults to 10", source="upstream_code", ref=f"{ENV}:26"),
        Fact("The reaching task's default episode length is 5 seconds", source="upstream_code",
             ref=f"{BASE}:1198-1202"),
        Fact("The constructor converts the task's default episode length to int(length / dt)", source="upstream_code",
             ref=f"{ENV}:167-170"),
        Fact("The joint-position action bounds are [-1.57, -1.2, -3.0] repeated for three fingers to "
             "[1.0, 1.57, 3.0] repeated", source="upstream_code", ref=f"{ACTION}:21-24"),
        Fact("When actions are normalized the action space is Box(low=-1, high=1), one element per joint-position "
             "bound", source="upstream_code", ref=f"{ACTION}:61-64"),
        Fact("The reaching task's robot observation keys are time_left_for_task, joint_positions, joint_velocities "
             "and end_effector_positions", source="upstream_code", ref=f"{REACHING}:47-51"),
        Fact("The reaching task's stage observation keys are the three goal cartesian positions",
             source="upstream_code", ref=f"{REACHING}:85-89"),
        Fact("A goal silhouette's cartesian position is bounded from [-0.5, -0.5, 0] to [0.5, 0.5, 0.5]",
             source="upstream_code", ref=f"{SILHOUETTE}:41-56"),
        Fact("The structured observation space concatenates the robot and stage spaces into one Box",
             source="upstream_code", ref=f"{SPACES}:31-40"),
        Fact("Normalized observations use the bounds -1 and 1", source="upstream_code",
             ref=f"{OBSERVATIONS}:73-74"),
        Fact("A step returns observation, reward, done and info, and scales the reward by dt", source="upstream_code",
             ref=f"{ENV}:274-290"),
        Fact("reset takes no seed and returns the task's structured observation", source="upstream_code",
             ref=f"{ENV}:346-372"),
        Fact("seed reseeds gym's np_random and numpy and returns the seed in a list", source="upstream_code",
             ref=f"{ENV}:333-344"),
        Fact("An episode is done when the episode length is greater than the maximum episode length",
             source="upstream_code", ref=f"{ENV}:422-430"),
        Fact("The info dictionary carries desired_goal, achieved_goal, success and fractional_success",
             source="upstream_code", ref=f"{BASE}:312-340"),
        Fact("The environment exposes get_state and set_state for pybullet_state and control_index",
             source="upstream_code", ref=f"{ENV}:492-521"),
        Fact("close saves an attached data recorder and closes the robot", source="upstream_code",
             ref=f"{ENV}:401-410"),
        Fact("The reaching task's default goals are [0, 0, 0.10], [0, 0, 0.13] and [0, 0, 0.16]",
             source="upstream_code", ref=f"{REACHING}:10-12"),
    ]
    safe_state = ("the simulation stops advancing: the runtime latch refuses step and reset after an e-stop until "
                  "mhs.safety.reset clears it, and the fake keeps its state readable")
    #: The fidelity contract of the model as deployed on the checked fake backend.  The fake is analytic, so the
    #: level is F0; the upstream PyBullet model and what it would add are named in the gaps.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws the start joints from Python's random.Random seeded by the bridge and has no "
                     "other randomness; upstream seeds numpy (causalworld.py:342-343) and was not run, so one seed "
                     "does not reproduce upstream's trajectory",
        },
        # One environment step is 1/250 s * skip_frame; skip_frame defaults to 10, so the control step is 40 ms.
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the checked fake is a kinematic stand-in: joint positions are set directly, with no PyBullet "
            "rigid-body dynamics, contacts, friction, PD controller, actuator, sensor or noise model; the upstream "
            "is a PyBullet TriFinger simulation (causalworld.py:962-967) and was never compared with the fake",
            "the fake models only the default reaching task with structured observations; the other task "
            "generators, pixel camera observations, interventions and the real TriFinger are not modelled",
            "the fake draws the initial joint offsets from Python's random.Random while upstream seeds numpy "
            "(causalworld.py:342-343), so one seed does not give the same trajectory on the two",
            "no wall-clock pacing: realtime_factor 0 and only cap.world.step.v1 advances simulated time; one 40 ms "
            "control step stands for 10 PyBullet substeps of 4 ms (causalworld.py:93-96)",
            "snapshot and restore are not offered by this package even though the upstream class has get_state and "
            "set_state (causalworld.py:492-521); the fake does not implement them, so determinism is declared "
            "seeded rather than exact",
        ],
    }
