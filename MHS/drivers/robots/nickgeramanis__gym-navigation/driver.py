"""OpenMHS driver for gh.nickgeramanis/gym-navigation: the NavigationTrack-v0 environment (Gymnasium family).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action = {index}`` bounded by the
environment's ``Discrete(3)``, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.
The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.

The upstream package imports gymnasium, numpy and pygame (requirements.txt:1-3) and package code never imports the
clone, so the ``fake`` backend is the package's own pure Python NavigationTrack (fake.py).  A backend name that
``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path
needs the upstream package installed and was not run here.

The sibling environment registered as NavigationGoal-v0 (gym_navigation/__init__.py:7-9) extends NavigationTrack
with a goal and is not served by this package.  The ``fidelity`` attribute is the complete contract of the model as
deployed (spec 05-fidelity FID-002); every constant and rule cites a line of the clone at the pinned commit
(98be757c6aa2b2834cecbb7dde3c2c05e5f1b57b).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

TRACK = "gym_navigation/envs/navigation_track.py"
NAVIGATION = "gym_navigation/envs/navigation.py"
ACTION = "gym_navigation/enums/action.py"
TRACKS = "gym_navigation/enums/track.py"
POSE = "gym_navigation/geometry/pose.py"


class NavigationTrack(GymnasiumDriver):
    device_id = "navigation-track"
    env_id = "NavigationTrack-v0"
    native = "gym_navigation.envs.navigation_track:NavigationTrack"
    backends = {"fake": ".fake:FakeNavigationTrack"}
    display_name = "gym-navigation NavigationTrack-v0 (2-D navigation simulation)"
    vendor, model = "Nick Geramanis", "gym-navigation"
    tags = ["navigation", "2d", "ray-casting", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("NavigationTrack-v0 is registered with entry point "
             "gym_navigation.envs.navigation_track:NavigationTrack", source="upstream_code",
             ref="gym_navigation/__init__.py:4-6"),
        Fact("The action space is Discrete(3): one integer per Action enum member", source="upstream_code",
             ref=f"{TRACK}:46"),
        Fact("The three actions are FORWARD (0, linear shift 0.2 m, angular 0), ROTATE_RIGHT (1, 0.04 m, 0.2 rad) "
             "and ROTATE_LEFT (2, 0.04 m, -0.2 rad)", source="upstream_code", ref=f"{ACTION}:21-23"),
        Fact("The observation is five range measurements at -pi/2, -pi/4, 0, pi/4 and pi/2 from the heading",
             source="upstream_code", ref=f"{TRACK}:30-34"),
        Fact("The scan range constants are 30.0 maximum and 0.2 minimum", source="upstream_code",
             ref=f"{TRACK}:31-32"),
        Fact("The observation space is a Box of N_OBSERVATIONS = N_MEASUREMENTS (5) elements whose high and low "
             "are the scan range constants", source="upstream_code", ref=f"{TRACK}:48-51"),
        Fact("The shift and sensor noise standard deviations are 0.02", source="upstream_code", ref=f"{TRACK}:21-22"),
        Fact("Each action draws Gaussian noise N(0, 0.02) for the angular and the linear shift, moves the pose and "
             "then rotates it", source="upstream_code", ref=f"{TRACK}:53-60"),
        Fact("Positions and ranges are in metres: the renderer maps 1 m to 20 pixels", source="upstream_code",
             ref=f"{NAVIGATION}:25-26"),
        Fact("The yaw is measured from the y axis in [-pi, pi], positive clockwise", source="upstream_code",
             ref=f"{POSE}:74-81"),
        Fact("The collision threshold is 0.4 m", source="upstream_code", ref=f"{TRACK}:24"),
        Fact("The episode terminates when any scan range is below the collision threshold", source="upstream_code",
             ref=f"{TRACK}:102-106"),
        Fact("The collision reward is -200.0, the forward reward +5.0 and the rotation reward -0.5",
             source="upstream_code", ref=f"{TRACK}:26-28"),
        Fact("The reward is the collision reward on a collision, the forward reward for FORWARD and the rotation "
             "reward otherwise", source="upstream_code", ref=f"{TRACK}:108-116"),
        Fact("A reset restores the world from the track walls and returns the observation and an info dict",
             source="upstream_code", ref=f"{NAVIGATION}:89-102"),
        Fact("A reset draws one spawn area, x and y uniformly inside it and the yaw uniformly in [-pi, pi]",
             source="upstream_code", ref=f"{TRACK}:125-131"),
        Fact("step always returns truncated False", source="upstream_code", ref=f"{NAVIGATION}:60"),
        Fact("NavigationTrack reports an empty info dict", source="upstream_code", ref=f"{TRACK}:122-123"),
        Fact("The track model is TRACK1, twelve wall segments and six spawn areas", source="upstream_code",
             ref=f"{TRACKS}:26-49"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:NavigationTrack-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the spawn pose and every Gaussian draw of the following steps, so one "
                     "implementation repeats a trajectory for the same seed and actions; this package's fake draws "
                     "with Python's random.Random and upstream with numpy's generator, so a seed gives different "
                     "trajectories on the two.  timestep_ms is 0: the analytic model declares no step interval.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic model: no forces, contacts, friction or actuator dynamics; a step moves the pose "
            "by the action's fixed distance and angle plus Gaussian noise",
            "no wall-clock pacing and no declared time step: timestep_ms 0, ticks count transitions and simulated "
            "time is not defined",
            "five ideal ray-cast ranges with additive Gaussian sensor noise: no beam width, occlusion or "
            "reflectance model, and the scan is not clamped to its declared observation bounds",
            "no rendering: upstream draws a pygame window only with render_mode='human'",
            "no physical device is modelled and the model was never validated against one",
            "the fake backend restates track 1 in pure Python with random.Random and was not compared with the "
            "upstream environment (gymnasium, numpy and pygame were not importable where the gate ran); trajectories "
            "can differ from upstream's numpy random stream",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
