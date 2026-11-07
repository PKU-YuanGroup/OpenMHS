"""OpenMHS driver for gh.ml-lab/home-platform: the HoME ``Home-v0`` household simulator (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action = {values: [moving, looking]}``,
both components 0-4 (``home_env_basic.py:17-30``); ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend and no e-stop path to a
machine.

The upstream environment is Python 2 code over Panda3D and the SUNCG data set (``home_env_basic.py:5-10``); it is
neither importable nor installable where the gate runs, and package code never imports the clone.  The ``fake`` backend
is therefore this package's pure Python re-implementation of ``HomeEnv`` (see ``fake.py``).  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make("Home-v0")`` (``GymnasiumDriver.open_native``); that
path needs the upstream package, which was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002).  Every fact and constant cites a
line of the clone at the pinned commit (cbd373f270faaf19f21ed88f0e3bd272a1cbdaa6).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

HOME_ENV = "home_platform/gym/envs/home_env_basic.py"
BASIC_ENV = "home_platform/env.py"
REGISTRATION = "home_platform/gym/__init__.py"


class HomePlatform(GymnasiumDriver):
    device_id = "home-platform"
    env_id = "Home-v0"
    native = "home_platform.gym.envs:HomeEnv"
    backends = {"fake": ".fake:FakeHomeEnv"}
    display_name = "HoME Home-v0 household simulator"
    vendor, model = "ml-lab / HoME Platform", "Home-v0"
    tags = ["household", "multimodal", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Home-v0 is registered with entry point home_platform.gym.envs:HomeEnv, max_episode_steps 1000 and "
             "reward_threshold 0.0", source="upstream_code", ref=f"{REGISTRATION}:3-8"),
        Fact("HomeEnv subclasses gym.Env", source="upstream_code", ref=f"{HOME_ENV}:13"),
        Fact("The action has two components, moving and looking, each a Discrete 5 action 0 to 4 (NOOP, UP, RIGHT, "
             "DOWN, LEFT)", source="upstream_code", ref=f"{HOME_ENV}:17-30"),
        Fact("The constructor defaults turning_speed to 0.1 and moving_speed to 100", source="upstream_code",
             ref=f"{HOME_ENV}:34"),
        Fact("The action space is constructed as spaces.MultiDiscrete([[0, 4], [0, 4]])", source="upstream_code",
             ref=f"{HOME_ENV}:47"),
        Fact("The observation is a Dict: position and orientation of 3 values each in -100 to 100, an image of "
             "500 x 500 x 3 values in 0 to 255, and a collision flag of 0 or 1", source="upstream_code",
             ref=f"{HOME_ENV}:48-61"),
        Fact("Each step applies moving then looking, advances the environment one step, and returns the observation "
             "with reward 0, done False and misc None", source="upstream_code", ref=f"{HOME_ENV}:130-144"),
        Fact("Looking action 1 subtracts turning_speed from heading, 2 adds it to roll, 3 adds it to heading and 4 "
             "subtracts it from roll", source="upstream_code", ref=f"{HOME_ENV}:91-108"),
        Fact("Moving action 1 applies a +moving_speed impulse on y, 2 +x on x, 3 -y on y and 4 -x on x",
             source="upstream_code", ref=f"{HOME_ENV}:110-128"),
        Fact("A reset places the agent at (42, -39, 1) with orientation (0, 0, 0), advances the environment once, "
             "increments the house index and wraps it at the end of the list", source="upstream_code",
             ref=f"{HOME_ENV}:146-168"),
        Fact("The clone ships one house id (list_of_houses) and _seed asserts seed < len(list_of_houses), so the only "
             "valid house index is 0", source="upstream_code", ref=f"{HOME_ENV}:68-89"),
        Fact("BasicEnvironment defaults its integration interval dt to 0.1 seconds", source="upstream_code",
             ref=f"{BASIC_ENV}:93"),
        Fact("BasicEnvironment.step advances the physics and render worlds by dt, which is the configured 0.1 s "
             "unless realtime is set", source="upstream_code", ref=f"{BASIC_ENV}:225-234"),
        Fact("The agent is a Bullet capsule of radius 0.1, height 1.6 and mass 60.0", source="upstream_code",
             ref=f"{BASIC_ENV}:100-107"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity = {
        "engine": "home-platform:Home-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the simulation has no random source: a reset returns the fixed start pose and a seed selects "
                     "the house index; the clone ships one house, so upstream only accepts seed 0",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no rigid-body dynamics: the fake moves the agent kinematically on the horizontal plane, with no Bullet "
            "contacts, friction, gravity, collision detection, renderer or sensor/noise model",
            "the collision flag is always 0 and the image is a constant 4 x 4 x 3 frame; the upstream image is "
            "500 x 500 x 3 (home_env_basic.py:57)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (dt 0.1 s) only",
            "the fake does not add the 1000-step TimeLimit that gym.make('Home-v0') adds from the registration "
            "(home_platform/gym/__init__.py:6); done is always False as in HomeEnv._step",
            "snapshot and restore are not offered: HomeEnv exposes no get_state/set_state",
            "the upstream package is Python 2 / Panda3D and was not imported or run; the fake was not compared with "
            "the upstream environment",
            "the upstream action-space constructor spaces.MultiDiscrete([[0, 4], [0, 4]]) does not match the "
            "documented two 0-4 components; the fake implements the documented two-component action",
            "the upstream _seed asserts seed < len(list_of_houses) (home_env_basic.py:85); the fake maps any "
            "non-negative seed to the only house so the generic cap.world.seed.v1 and cap.world.reset.v1 contract "
            "stays usable, and the upstream path would refuse a seed above 0",
        ],
    }
