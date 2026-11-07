"""OpenMHS driver for gh.dexrobot/dexrobot_isaac: the DexHand Isaac Gym environment (a Gymnasium family driver).

The card's decision is ``family-config`` with the ``GymnasiumDriver`` helper, which fits the card's main entry point:
``make_env`` builds a ``DexHandBase`` whose ``action_space`` and ``observation_space`` are Gym-style ``Box`` spaces,
so the Gymnasium bridge can derive ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the
environment object.  ``DexHandBase`` itself is a custom ``VecTask``, not ``gymnasium.Env``, and it imports
``isaacgym`` and ``torch`` at module import time (dexhand_base.py:17-21); the gate never imports the clone.

Only the ``fake`` backend is declared.  The card names ``upstream-sim`` (Isaac Gym), but Isaac Gym Preview 4 is a
manual download from NVIDIA (README.md:22-24) and cannot be imported where the gate runs, so the package serves a
pure Python stand-in for one environment (fake.py).  The fake is kinematic and has no contacts or rigid-body
dynamics; the fidelity contract says F0 and the gaps say what is absent.  No hardware backend exists: the device is
simulated (R0) and its only stop is the runtime's software latch.  This package is model-authored and unreviewed;
it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE = "dexhand_env/tasks/dexhand_base.py"
VEC_TASK = "dexhand_env/tasks/base/vec_task.py"
CONFIG = "dexhand_env/cfg/task/BaseTask.yaml"
PHYSICS = "dexhand_env/cfg/physics/default.yaml"
CONSTANTS = "dexhand_env/constants.py"
FACTORY = "dexhand_env/factory.py"
TERMINATION = "dexhand_env/components/termination/termination_manager.py"
INITIALIZATION = "dexhand_env/components/initialization/initialization_manager.py"
OBSERVATION = "dexhand_env/components/observation/observation_encoder.py"
PHYSICS_MANAGER = "dexhand_env/components/physics/physics_manager.py"


class DexHand(GymnasiumDriver):
    """The DexHand environment served through the Gymnasium bridge on the package's fake backend."""

    device_id = "dexhand021"
    native = "dexhand_env.tasks.dexhand_base:DexHandBase"
    backends = {"fake": ".fake:FakeDexHandBase"}
    action_space_ref = f"{BASE}:1167-1169"
    display_name = "DexRobot DexHand021 (Isaac Gym environment)"
    vendor, model = "DexRobot", "DexHand021"
    tags = ["dexhand", "dexterous-manipulation", "isaac-gym", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The repository provides reinforcement learning environments for training dexterous manipulation "
             "policies with robotic hands using NVIDIA's Isaac Gym simulator",
             source="upstream_code", ref="README.md:3"),
        Fact("The installation instructions require downloading Isaac Gym Preview 4 from NVIDIA before the "
             "package is installed", source="upstream_code", ref="README.md:22-24"),
        Fact("The package pins the legacy Gym API, gym 0.23.1", source="upstream_code", ref="setup.py:17"),
        Fact("DexHandBase imports isaacgym and torch at module import time", source="upstream_code",
             ref=f"{BASE}:17-21"),
        Fact("DexHandBase is the dexterous-hand environment class and extends VecTask", source="upstream_code",
             ref=f"{BASE}:61"),
        Fact("The custom Env base declares step, reset, render and close, each raising NotImplementedError",
             source="upstream_code", ref=f"{VEC_TASK}:155-169"),
        Fact("VecTask extends Env and parses the simulation parameters, setting dt from the configured physics "
             "timestep", source="upstream_code", ref=f"{VEC_TASK}:172-205"),
        Fact("The default hand asset is "
             "dexrobot_mujoco/dexrobot_mujoco/models/dexhand021_right_simplified_floating.xml",
             source="upstream_code", ref=f"{BASE}:170-171"),
        Fact("The hand has 6 base DOFs and 12 active finger DOFs", source="upstream_code",
             ref=f"{CONSTANTS}:8-9"),
        Fact("The BaseTask configuration enables policy control of the hand base (6 DOFs) and the fingers "
             "(12 controls)", source="upstream_code", ref=f"{CONFIG}:32-33"),
        Fact("The action dimension is the sum of the base DOFs and the active finger DOFs that the policy "
             "controls", source="upstream_code", ref=f"{INITIALIZATION}:54-62"),
        Fact("The action space is a Box with low -1.0, high 1.0 and dtype float32, one element per action",
             source="upstream_code", ref=f"{BASE}:1162-1169"),
        Fact("The observation space is a Box from -inf to +inf with dtype float32, one element per observation",
             source="upstream_code", ref=f"{BASE}:1150-1160"),
        Fact("episodeLength is 300 steps", source="upstream_code", ref=f"{CONFIG}:19"),
        Fact("Timeout termination is raised when episode_step_count is at least episodeLength - 1",
             source="upstream_code", ref=f"{TERMINATION}:229-237"),
        Fact("The simulation timestep is 0.005 s (200 Hz)", source="upstream_code", ref=f"{CONFIG}:10"),
        Fact("The default physics configuration uses 4 substeps and gravity [0.0, 0.0, -9.81]",
             source="upstream_code", ref=f"{PHYSICS}:3-4"),
        Fact("The default position_delta scaling uses a maximum finger joint velocity of 1.0 rad/s, a maximum "
             "base linear velocity of 0.5 m/s and a maximum base angular velocity of 1.5 rad/s",
             source="upstream_code", ref=f"{CONFIG}:41-45"),
        Fact("The BaseTask reward has an alive term of 0.1 per step", source="upstream_code", ref=f"{CONFIG}:62"),
        Fact("The BaseTask policy observation lists 13 components: base positions and velocities, active finger "
             "positions and velocities, hand pose, five contact indicators, previous actions, base and finger "
             "targets, and four 35-value fingertip and fingerpad pose blocks", source="upstream_code",
             ref=f"{CONFIG}:103-116"),
        Fact("The observation dimension is computed at initialization from the concatenated selected components",
             source="upstream_code", ref=f"{OBSERVATION}:215-234"),
        Fact("reset resets all environments and returns the observation buffer", source="upstream_code",
             ref=f"{BASE}:805-838"),
        Fact("step applies the actions, steps physics and returns (observation, reward, done, info)",
             source="upstream_code", ref=f"{BASE}:893-921"),
        Fact("seed seeds Python's random module, numpy and torch", source="upstream_code",
             ref=f"{VEC_TASK}:145-153"),
        Fact("make_env is the main entry point for creating environments compatible with RL libraries such as "
             "rl_games", source="upstream_code", ref=f"{FACTORY}:93-107"),
        Fact("make_env loads dexhand_env/cfg/task/<task_name>.yaml when no configuration is supplied",
             source="upstream_code", ref=f"{FACTORY}:122-127"),
        Fact("The control timestep is measured as physics_dt times the measured number of physics steps per "
             "control step", source="upstream_code", ref=f"{PHYSICS_MANAGER}:243-259"),
        Fact("The initial hand position is [0.0, 0.0, 0.5] and the initial hand rotation is [0.0, 0.0, 0.0, 1.0]",
             source="upstream_code", ref=f"{CONFIG}:17-18"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step, reset and seed until "
                  "mhs.safety.reset clears the latch, while the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2): the package serves the
    #: kinematic fake, so the level is F0 and the gaps name everything the fake does not model.
    fidelity = {
        "engine": "analytic:dexhand021-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset and dynamics are deterministic, so one seed and command sequence repeat a "
                     "trajectory; upstream seeds Python random, numpy and torch (vec_task.py:145-153), while the "
                     "fake keeps its own seed and does not reproduce those generators",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a single-environment kinematic stand-in, not Isaac Gym: no rigid-body dynamics, contacts, "
            "contact forces, actuator PD control, tendon coupling or sensor noise; the five contact indicators "
            "stay zero",
            "no rendering and no camera, video or streaming path is offered",
            "no wall-clock pacing: realtime_factor 0, so ticks advance simulated time by timestep_ms only",
            "the upstream control period is measured at start-up as physics_dt times the measured physics steps "
            "per control step (physics_manager.py:243-259); the fake uses one 5 ms physics step per tick and does "
            "not reproduce that measurement",
            "upstream step and reset return a batched (num_envs, num_observations) buffer; the bridge serves one "
            "environment, so the fake returns that row as a flat list",
            "the fingertip and fingerpad poses are fixed hand-frame offsets in the fake; upstream derives them from "
            "the simulated hand",
            "upstream reports the episode timeout through done without a truncated flag; the bridge exposes it as "
            "terminated",
            "snapshot and restore are not offered: DexHandBase exposes no get_state or set_state",
            "no physical DexHand is modelled and the model was never validated against one",
        ],
    }
