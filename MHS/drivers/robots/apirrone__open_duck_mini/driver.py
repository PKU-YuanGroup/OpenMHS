"""OpenMHS driver for gh.apirrone/open_duck_mini: the BDX_env humanoid MuJoCo environment.

The card's first AST-confirmed entry symbol is ``env_humanoid:BDXEnv`` (``experiments/RL/env_humanoid.py:18``),
one of the several ``BDXEnv`` classes of the repository; this package implements that one and names the others
in ``facts.md``.  The driver is a Gymnasium family driver: configuration only.  The bridge derives the whole
contract from the environment's spaces, so ``cap.world.step.v1`` takes ``{ticks, action}`` (``action.values`` is
the flattened action box), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The environment is simulated (R0, ``world.sim``): the package serves the model, never the robot.  The card's
``safety.risk_floor`` is R0 and the driver declares no device limit: the action box is the bridge's view of the
simulator's action space, and the ``ticks`` and ``seed`` bounds are class-schema bounds, not device limits.  There
is no hardware stop and no operator-required bound.

The gate cannot open the upstream environment (it imports ``placo`` and builds its scene from the absolute path
``/home/antoine/MISC/mini_BDX/mini_bdx/robots/bdx/scene.xml``, ``experiments/RL/env_humanoid.py:4`` and ``:105``),
so the ``fake`` backend is ``fake.py``, a pure Python stand-in for ``BDXEnv``.  The ``sim`` backend is not listed
in ``backends``; ``GymnasiumDriver.open_native`` would serve it with ``gymnasium.make(env_id)`` after an upstream
script registers ``BDX_env`` (``experiments/RL/train.py:129-134``), and that path was not run here.

Every Fact cites a line of the clone at commit b23317a485b3cec7d8417f352478778b3475173c.  This package is
model-authored and unreviewed (``driver.lock.json``: ``authored_by.kind`` is ``model``, ``reviewed_by`` is null).
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "experiments/RL/env_humanoid.py"
ROBOT = "mini_bdx/robots/bdx/robot.xml"
SCENE = "mini_bdx/robots/bdx/scene.xml"


class OpenDuckMini(GymnasiumDriver):
    device_id = "open_duck_mini"
    env_id = "BDX_env"
    native = "env_humanoid:BDXEnv"
    backends = {"fake": ".fake:FakeBDXEnv"}
    display_name = "Open Duck Mini v2 (BDX_env humanoid MuJoCo environment)"
    vendor, model = "apirrone", "Open Duck Mini v2"
    risk = "R0"
    tags = ["bdx", "gymnasium", "legged-robot", "mujoco", "open-duck-mini", "reinforcement-learning",
            "simulation"]
    facts = [
        Fact("BDX_env is registered with entry point env_humanoid:BDXEnv, max_episode_steps=None (formerly 500) "
             "and autoreset=True", source="upstream_code", ref="experiments/RL/train.py:129-134"),
        Fact("The observation space is a Box of 41 float64 values with no finite lower or upper bound",
             source="upstream_code", ref=f"{ENV}:92"),
        Fact("The healthy base height range is 0.1 to 0.2 metres", source="upstream_code", ref=f"{ENV}:97"),
        Fact("The episode terminates when the base is unhealthy or its local z-axis is not upright",
             source="upstream_code", ref=f"{ENV}:140-145"),
        Fact("The reward weights are forward_reward_weight 1.25, ctrl_cost_weight 0.3 and healthy_reward 5.0",
             source="upstream_code", ref=f"{ENV}:99-101"),
        Fact("The environment runs 5 MuJoCo physics steps per environment step (frame_skip 5)",
             source="upstream_code", ref=f"{ENV}:103-109"),
        Fact("The reward is healthy_reward minus ctrl_cost (0.3 times the sum of squared controls) minus "
             "moving_cost (twice the absolute x velocity)", source="upstream_code", ref=f"{ENV}:157-165"),
        Fact("The observation concatenates the joint positions, the joint velocities and the left then right "
             "foot contact flags", source="upstream_code", ref=f"{ENV}:210-216"),
        Fact("A reset adds uniform noise between -0.01 and 0.01 to the initial positions and velocities",
             source="upstream_code", ref=f"{ENV}:181-189"),
        Fact("The BDX model defines 15 position actuators: five per leg plus neck_pitch, head_pitch, head_yaw and "
             "the two antennas", source="upstream_code", ref=f"{ROBOT}:284-298"),
        Fact("The base body starts at height z=0.17 metres", source="upstream_code", ref=f"{ROBOT}:69"),
        Fact("The scene's timestep option is commented out (the comment says 100 Hz), so the clone states no "
             "active physics timestep", source="upstream_code", ref=f"{SCENE}:2-3"),
        Fact("The environment declares render_fps 100 in its metadata", source="upstream_code", ref=f"{ENV}:81-88"),
        Fact("Open Duck Mini is about 42 centimetres tall with its legs extended", source="vendor_doc",
             ref="README.md:11"),
    ]
    safe_state = ("the simulation stops advancing: an e-stop latches and every step or reset is refused until "
                  "mhs.safety.reset clears it, while the fake environment keeps its state and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives engine,
    #: determinism, realtime factor, clock, reset and snapshot support; every member is written out so the whole
    #: contract reads in one place.  The fake is kinematic (F0) and declares no fixed physics timestep.
    fidelity = {
        "engine": "gymnasium:BDX_env",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial noise and the fake dynamics are "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "the fake draws with Python's random.Random and upstream draws with numpy's generator, so "
                     "one seed gives different trajectories on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in, not MuJoCo: an action sets the 13 joint positions directly and the joint "
            "velocities are their per-tick differences; there are no rigid-body dynamics, contacts, friction, "
            "actuator, sensor or noise model, the two foot contact flags are constants and termination never "
            "fires in the fake",
            "the action table of env_humanoid.py:24-36 has 13 rows with a duplicated index 9, while "
            "mini_bdx/robots/bdx/robot.xml:284-298 defines 15 position actuators; the declared 41-value "
            "observation corresponds to 13 joints (20 qpos + 19 qvel + 2 contacts), whereas the 15-joint model "
            "would give 45 values; the fake follows the declared 41-value space, so the neck_pitch and antenna "
            "channels are NOT COVERED and the upstream environment's declared space and its model disagree",
            "the upstream environment was not run: it imports placo (env_humanoid.py:4) and builds its scene "
            "from the absolute path /home/antoine/MISC/mini_BDX/mini_bdx/robots/bdx/scene.xml "
            "(env_humanoid.py:105), outside the clone",
            "the reset noise comes from Python's random.Random, upstream from numpy's generator; states and "
            "observations are Python floats, upstream returns a float64 NumPy array",
            "the real action space is built by gymnasium's external MujocoEnv and is not stated in the clone; "
            "the fake's Box boundaries are placeholder test data (not a sourced device bound) and the derived "
            "action.values limits are only the bridge's view of that stand-in",
            "no rendering and no snapshot/restore: the environment exposes no get_state/set_state in the clone, "
            "so snapshot_restore is false and the render_modes metadata is not served by cap.world.*",
            "timestep_ms is 0 because the clone states no active physics timestep (scene.xml:2-3 comments the "
            "100 Hz option out) and the fake is event-driven: one tick is one environment step, not a fixed "
            "duration",
            "no physical device is modelled and the fake was never validated against the upstream environment",
        ],
    }
