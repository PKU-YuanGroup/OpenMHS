"""OpenMHS driver for gh.farama-foundation/highwayenv: the highway-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``highway-v0`` registers ``HighwayEnv`` (highway_env/__init__.py:46-49); its action
space is ``DiscreteMetaAction`` with five meta-actions and its observation space is a Kinematics Box of shape
(5, 5).  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by 0 to 4,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import highway_env (the environment needs gymnasium, numpy, pandas, pygame-ce and noise), so the
``fake`` backend is the package's own pure Python kinematic stand-in (fake.py): it reproduces the interface of
``HighwayEnv``, the spaces of the default configuration, the five meta-actions, the reward structure and the 40 s
truncation, but it is kinematic (fidelity F0) and does not model the road network or the other vehicles' dynamics;
the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream package and was not run.

The card lists five entry symbols: this package implements ``HighwayEnv`` (``highway-v0``), the base environment of
the repository; ``ExitEnv``/``ConnectedLaneExitEnv`` (``exit-v0``/``exit-v1``), ``HighwayEnvFast``
(``highway-fast-v0``) and ``IntersectionEnv`` (``intersection-v0``) are the other registered environments of the
clone and are not implemented here.

Every Fact cites a line of the clone at the pinned commit (2a268f348f10f4d1ac83f96bc8a53d2fa50dd3b0).  This package
is model-authored and unreviewed: it is checked on the fake backend only, and nothing here was validated against a
device.
"""

from mhs.driver import Fact, GymnasiumDriver

INIT = "highway_env/__init__.py"
HIGHWAY = "highway_env/envs/highway_env.py"
ABSTRACT = "highway_env/envs/common/abstract.py"
ACTION = "highway_env/envs/common/action.py"
OBSERVATION = "highway_env/envs/common/observation.py"


class HighwayEnv(GymnasiumDriver):
    device_id = "highway"
    env_id = "highway-v0"
    native = "highway_env.envs.highway_env:HighwayEnv"
    backends = {"fake": ".fake:FakeHighwayEnv"}
    display_name = "HighwayEnv highway-v0 (farama-foundation/highwayenv)"
    vendor, model = "Farama Foundation", "highway-v0"
    tags = ["highway", "autonomous-driving", "traffic-simulation", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("highway-v0 registers highway_env.envs.highway_env:HighwayEnv", source="upstream_code",
             ref=f"{INIT}:46-49"),
        Fact("The action space is DiscreteMetaAction with five meta-actions: 0 LANE_LEFT, 1 IDLE, 2 LANE_RIGHT, "
             "3 FASTER and 4 SLOWER", source="upstream_code", ref=f"{ACTION}:204"),
        Fact("The action space is Discrete(len(actions)), five when both lateral and longitudinal actions are "
             "enabled", source="upstream_code", ref=f"{ACTION}:252-253"),
        Fact("The Kinematics observation has the features presence, x, y, vx and vy and observes five vehicles by "
             "default", source="upstream_code", ref=f"{OBSERVATION}:166-172"),
        Fact("The Kinematics observation space is Box(-inf, inf, shape=(vehicles_count, len(features))), a "
             "(5, 5) array in the default configuration", source="upstream_code", ref=f"{OBSERVATION}:207-213"),
        Fact("The default configuration has 4 lanes, 50 vehicles, 1 controlled vehicle and an episode duration of "
             "40 s", source="upstream_code", ref=f"{HIGHWAY}:35-39"),
        Fact("The simulation runs at 15 Hz and the policy at 1 Hz", source="upstream_code", ref=f"{ABSTRACT}:114-115"),
        Fact("Each policy step adds 1 / policy_frequency to the simulated time", source="upstream_code",
             ref=f"{ABSTRACT}:276"),
        Fact("The episode terminates when the ego vehicle has crashed, or when offroad_terminal is set and the "
             "vehicle is off the road", source="upstream_code", ref=f"{HIGHWAY}:141-147"),
        Fact("The episode is truncated when the simulated time reaches the configured duration",
             source="upstream_code", ref=f"{HIGHWAY}:149-151"),
        Fact("The reward weights are collision_reward -1, right_lane_reward 0.1 and high_speed_reward 0.4, with "
             "reward_speed_range [20, 30] and normalize_reward set", source="upstream_code", ref=f"{HIGHWAY}:42-49"),
        Fact("With normalize_reward the weighted reward is mapped from [collision_reward, high_speed_reward + "
             "right_lane_reward] to [0, 1] and multiplied by the on-road term", source="upstream_code",
             ref=f"{HIGHWAY}:110-120"),
        Fact("Vehicles of the default configuration are created at 25 m/s", source="upstream_code",
             ref=f"{HIGHWAY}:81-86"),
        Fact("The straight road network is built with speed_limit 30 m/s", source="upstream_code",
             ref=f"{HIGHWAY}:61-64"),
        Fact("The environment resets itself in AbstractEnv.__init__", source="upstream_code", ref=f"{ABSTRACT}:91"),
        Fact("reset(seed, options) forwards the seed to gym.Env.reset and rebuilds the spaces and the scene",
             source="upstream_code", ref=f"{ABSTRACT}:234-249"),
        Fact("highway-fast-v0 is the same environment with simulation_frequency 5, 3 lanes, 20 vehicles and a "
             "duration of 30 s", source="upstream_code", ref=f"{HIGHWAY}:162-175"),
        Fact("The repository registers exit-v0 and exit-v1 (ExitEnv and ConnectedLaneExitEnv) before highway-v0",
             source="upstream_code", ref=f"{INIT}:36-43"),
        Fact("The repository registers intersection-v0, intersection-v1 and intersection-v2 around IntersectionEnv",
             source="upstream_code", ref=f"{INIT}:55-67"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic (F0): it
    #: reproduces the interface and the spaces, not the road scene and the vehicle dynamics of the clone.
    fidelity = {
        "engine": "highway_env:highway-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) reseeds the clone's numpy generator; the fake seeds Python's random.Random, so one "
                     "seed gives different scenes and trajectories on the two",
        },
        "timestep_ms": 1000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no vehicle dynamics: the fake is kinematic (F0), the ego vehicle keeps its speed for one policy step "
            "and the other vehicles drift at fixed speeds; the clone integrates kinematic and IDM vehicles over 15 "
            "simulation substeps per policy step (abstract.py:288-309)",
            "no road network or lane geometry: a lane is an index 0 to 3, a collision is a distance check on the "
            "target lane when the ego changes lane, and the (5, 5) Kinematics observation is a flat 25-number "
            "stand-in (observation.py:166-172, 207-213)",
            "the reward applies the default weights to the stand-in's speed and lane (highway_env.py:42-49) but "
            "the values of any particular episode are not the clone's",
            "the fake returns the Kinematics observation as a flat 25-number list, the clone returns a (5, 5) "
            "float32 numpy array",
            "no rendering, no pygame viewer, no record-video wrapper and no manual control",
            "one tick is one policy step: it advances the simulated time by 1 s (policy_frequency 1 Hz), not by "
            "the 1/15 s simulation substep",
            "the sim backend (gymnasium.make('highway-v0')) was not run: gymnasium, numpy, pandas, pygame-ce and "
            "noise are not installed where the gate runs",
        ],
    }
