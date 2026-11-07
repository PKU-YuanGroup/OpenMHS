"""OpenMHS driver for gh.angelomorgado/carla-gymdrive: the carla-rl-gym-v0 Gymnasium environment.

``GymnasiumDriver`` is configuration only: the environment is registered as ``carla-rl-gym-v0`` with entry point
``src.env.environment:CarlaEnv`` (``src/env/environment.py:41-45``), so the bridge derives the whole contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``; with the upstream default ``continuous=True``
the action is ``{"values": [steering, throttle/brake]}`` bounded by the Box ``[-1, 1]`` on both elements
(``src/env/observation_action_space.py:32-33``), and with ``continuous=False`` it is ``{"index": i}`` for the
``Discrete(4)`` action space (``:35-36``).  ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
bound.  The fake backend is this package's pure-Python kinematic stand-in (fake.py): CARLA itself is an external
engine at ``localhost:2000`` (``src/config/configuration.py:17-19``) that the gate never runs.  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make("carla-rl-gym-v0")`` (``GymnasiumDriver
.open_native``); that path needs the clone on ``sys.path``, the ``carla`` package and a running CARLA server, and was
not run here.

Every Fact cites a line of the clone at the pinned commit 7d950f9d90d20b7dfbc17fa5b77e67437bde2d29.  The fidelity
contract describes the model as deployed (fake.py): a kinematic F0 model, not CARLA.  This package is model-authored
and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVIRONMENT = "src/env/environment.py"
SPACES = "src/env/observation_action_space.py"
CONFIG = "src/config/configuration.py"
WORLD = "src/carlacore/world.py"


class CarlaGymDrive(GymnasiumDriver):
    device_id = "carla-gymdrive"
    env_id = "carla-rl-gym-v0"
    native = "src.env.environment:CarlaEnv"
    backends = {"fake": ".fake:FakeCarlaEnv"}
    display_name = "CARLA GymDrive (carla-rl-gym-v0)"
    vendor, model = "angelomorgado", "carla-rl-gym-v0"
    tags = ["carla", "driving", "reinforcement-learning", "simulation", "gymnasium", "sim-env"]
    facts = [
        Fact("The environment is registered as carla-rl-gym-v0 with entry point src.env.environment:CarlaEnv and "
             "max_episode_steps config.ENV_MAX_STEPS", source="upstream_code", ref=f"{ENVIRONMENT}:41-45"),
        Fact("The default constructor starts with continuous actions, a 60-second time limit and server "
             "initialization on", source="upstream_code", ref=f"{ENVIRONMENT}:58"),
        Fact("The continuous action space is a two-element Box from -1.0 to 1.0: steering and throttle/brake",
             source="upstream_code", ref=f"{SPACES}:32-33"),
        Fact("The discrete action space is Discrete(4): accelerate, decelerate, turn left, turn right",
             source="upstream_code", ref=f"{SPACES}:35-36"),
        Fact("The observation declares the RGB image as 360 x 640 x 3 and the LiDAR array as 3 x 500",
             source="upstream_code", ref=f"{SPACES}:5-12"),
        Fact("The observation also carries position, target position, next waypoint position, speed and a situation "
             "index", source="upstream_code", ref=f"{SPACES}:22-30"),
        Fact("The situation map maps Road to 0, Roundabout to 1, Junction to 2 and Tunnel to 3",
             source="upstream_code", ref=f"{SPACES}:15-20"),
        Fact("The simulator connects to a CARLA server at localhost:2000 with a 100 s timeout",
             source="upstream_code", ref=f"{CONFIG}:17-19"),
        Fact("SIM_FPS is 30", source="upstream_code", ref=f"{CONFIG}:23"),
        Fact("The world applies its synchronous flag to the CARLA settings and, when synchronous, fixes the delta "
             "to 1.0 / SIM_FPS seconds", source="upstream_code", ref=f"{WORLD}:99-105"),
        Fact("ENV_MAX_STEPS is 430, the maximum number of steps per episode", source="upstream_code",
             ref=f"{CONFIG}:27"),
        Fact("reset returns the initial observation and an info dict with the scenario name and the waypoints",
             source="upstream_code", ref=f"{ENVIRONMENT}:162-170"),
        Fact("step ticks the world in synchronous mode, applies the vehicle control and returns observation, "
             "reward, terminated, truncated and info", source="upstream_code", ref=f"{ENVIRONMENT}:179-219"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed on the fake backend (spec 05-fidelity section 2).  The
    #: upstream timestep is 1 / SIM_FPS seconds in synchronous mode (src/carlacore/world.py:103, SIM_FPS 30 at
    #: src/config/configuration.py:23); the fake advances the same interval by an analytic rule.
    fidelity = {
        "engine": "gymnasium:carla-rl-gym-v0 (CARLA server at localhost:2000)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial position, heading and target of this "
                     "package's fake and its step rule is deterministic, so one seed and action sequence repeat a "
                     "trajectory; the upstream environment draws with numpy and the random module and runs the "
                     "CARLA engine, so a seed does not reproduce the same trajectory as CARLA",
        },
        "timestep_ms": 1000.0 / 30.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in only: positions change by an analytic rule with no vehicle dynamics, contacts, "
            "friction, sensors or noise model, so this is F0 and not the CARLA engine",
            "the fake returns a 4 x 4 x 3 RGB image and a 3 x 4 LiDAR array instead of the upstream 360 x 640 x 3 "
            "and 3 x 500 arrays; the observation keys, ranks and dtypes match, but the values are Python numbers, "
            "not numpy arrays, and the real sizes are declared in src/env/observation_action_space.py:6-7",
            "no wall-clock pacing: realtime_factor 0 and the fake truncates on a step count instead of the upstream "
            "60-second wall-clock time limit",
            "traffic, pedestrians, weather, rendering and the CARLA map are not modelled",
            "the upstream PreProcessing step (LiDAR column removal, transpose and farthest-point sampling) is not "
            "modelled: the fake returns its raw small LiDAR stand-in",
            "the fake reward and termination are test data, not the upstream Reward function (collision, lane "
            "invasion, steering/throttle jerk, speed, target and waypoint terms)",
            "the fake draws the scenario and start state with Python's random.Random; upstream draws the scenario "
            "with numpy's generator and spawns traffic with the random module, so seeds do not agree",
            "the fake was never compared with a CARLA server; neither the sim backend nor the CARLA engine was run "
            "here",
        ],
    }
