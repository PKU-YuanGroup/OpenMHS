"""OpenMHS driver for gh.hoangtranngoc/airsim-rl: the legacy Gym AirSim car environment.

The confirmed entry symbol is ``gym_airsim.airsim_car_env:AirSimCarEnv``
(``gym_airsim/airsim_car_env.py:12``), a ``gym.Env`` subclass whose primary interface is ``reset()`` and
``step(action)``.  This package is a configuration-only :class:`GymnasiumDriver`: the bridge serves
``cap.world.step.v1`` (``{ticks, action}`` with the ``Discrete(7)`` action space read from ``config.ini``),
``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The repository's car agent is an AirSim RPC client
(``gym_airsim/car_agent.py:7``): the environment is a simulator front end, not a ROS transport, even though the
clone is often run beside AirSim/Unreal Engine 4.

The AirSim simulator and the legacy ``gym``/``airsim`` packages are not in the clone and are not installed where the
gate runs, so this package declares only the ``fake`` backend, a pure-Python analytic stand-in for the environment.
It was never compared with a live AirSim run and is not a recording of one.  A backend name that ``backends`` does
not list (``sim``) would be served by ``gym.make(env_id)``; ``env_id`` is unset because the environment is not
registered with Gymnasium and must be constructed directly as ``AirSimCarEnv()`` against a running AirSim RPC server
(``README.md:17``, ``gym_airsim/car_agent.py:10-12``), so no live backend is offered by this package.

The ``fidelity`` attribute is the complete contract of the model as deployed.  Every Fact cites a line of the clone
at the pinned commit b4700049d8c2c519476d4ee15f2504795f80df9d.  The package is model-authored and unreviewed: it is
checked on the fake backend only, and no AirSim, simulator or hardware run is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_airsim/airsim_car_env.py"
AGENT = "gym_airsim/car_agent.py"
CONFIG = "config.ini"


class AirSimCar(GymnasiumDriver):
    device_id = "airsim-car"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    #: The upstream environment is registered with neither Gymnasium nor legacy gym (no registration in the clone);
    #: ``AirSimCarEnv()`` is constructed directly against a running AirSim RPC server.  No ``sim`` backend is offered.
    env_id = None
    native = "gym_airsim.airsim_car_env:AirSimCarEnv"
    backends = {"fake": ".fake:FakeAirSimCarEnv"}
    #: The fake uses the shipped config.ini:24 count of seven actions.  The environment's Discrete expression
    #: reads that separate file; no single cited span states the resulting index range.  Keep the bridge's
    #: fake-backend provenance instead of assigning action_space_ref to that unevaluated expression.
    display_name = "AirSim-RL car environment (legacy Gym, AirSim simulator)"
    vendor, model = "hoangtranngoc", "AirSimCarEnv"
    tags = ["airsim", "unreal-engine", "car", "legacy-gym", "reinforcement-learning", "simulation", "camera"]
    facts = [
        Fact("README describes experiments with deep reinforcement learning on a car and a UAV in AirSim, an "
             "external simulator", source="vendor_doc", ref="README.md:2"),
        Fact("The setup instructions say to build AirSim and Unreal Engine 4 (UE4) on Windows",
             source="vendor_doc", ref="README.md:17"),
        Fact("The setup instructions name gym 0.17.2 as the Gym version used by the experiments",
             source="vendor_doc", ref="README.md:19"),
        Fact("AirSimCarEnv subclasses gym.Env", source="upstream_code", ref=f"{ENV}:12"),
        Fact("The environment reads config.ini from the repository root", source="upstream_code", ref=f"{ENV}:21-22"),
        Fact("The action space is Discrete(int(config['car_agent']['actions']))",
             source="upstream_code", ref=f"{ENV}:26"),
        Fact("The shipped config.ini sets actions = 7", source="upstream_code", ref=f"{CONFIG}:24"),
        Fact("The shipped config.ini sets image_height 144, image_width 256 and image_channels 3",
             source="upstream_code", ref=f"{CONFIG}:3-5"),
        Fact("The observation space is a Box of low 0, high 255 and shape (image_height, image_width, "
             "image_channels) with dtype uint8", source="upstream_code", ref=f"{ENV}:28-36"),
        Fact("The shipped config.ini sets track_width = 12", source="upstream_code", ref=f"{CONFIG}:7"),
        Fact("step moves the car with the action, reads the car state and the car controls, computes the reward "
             "and the done flag, gets the camera observation and returns the legacy four-tuple "
             "(observation, reward, done, info)", source="upstream_code", ref=f"{ENV}:40-59"),
        Fact("reset restarts the car agent, gets a camera observation and returns the observation only",
             source="upstream_code", ref=f"{ENV}:61-65"),
        Fact("close calls the car agent's AirSim reset", source="upstream_code", ref=f"{ENV}:70-72"),
        Fact("The reward is computed from the perpendicular distance between the car and the line through the two "
             "closest waypoints, using the configured track width", source="upstream_code", ref=f"{ENV}:74-85"),
        Fact("The episode is done when the reward is negative, or when the car is less than 5 m from the last "
             "waypoint", source="upstream_code", ref=f"{ENV}:87-98"),
        Fact("The reward markers are 0.1, 0.25 and 0.5 times the track width and the rewards are 1, 0.5, 0.1 and "
             "-1 outside the third marker", source="upstream_code", ref="utils.py:14-27"),
        Fact("CarAgent subclasses the AirSim CarClient", source="upstream_code", ref=f"{AGENT}:7"),
        Fact("The car agent constructor connects to the AirSim simulator, confirms the connection and enables API "
             "control", source="upstream_code", ref=f"{AGENT}:8-12"),
        Fact("The discrete steering values are built from steering_max and steering_granularity and the maximum "
             "steering value is appended", source="upstream_code", ref=f"{AGENT}:26-28"),
        Fact("restart calls the AirSim reset and then enables API control again",
             source="upstream_code", ref=f"{AGENT}:34-36"),
        Fact("observe requests the front camera scene image and reshapes the returned bytes to the configured image "
             "shape", source="upstream_code", ref=f"{AGENT}:38-48"),
        Fact("move interprets the action and sends the resulting controls with setCarControls",
             source="upstream_code", ref=f"{AGENT}:50-52"),
        Fact("In action mode 0 the throttle is the fixed configured value and the steering is "
             "steering_values[action]; action modes 1 and 2 return NotImplemented",
             source="upstream_code", ref=f"{AGENT}:54-66"),
        Fact("The car agent fetches waypoints whose names match the configured regular expression, sorts them and "
             "reads each object's pose", source="upstream_code", ref=f"{AGENT}:68-79"),
        Fact("The two closest waypoints are the endpoints of the segment with the smallest summed distance from the "
             "car", source="upstream_code", ref=f"{AGENT}:84-97"),
        Fact("train.py constructs the environment as AirSimCarEnv(), the user-facing training interface",
             source="upstream_code", ref="train.py:50"),
    ]
    safe_state = ("the fake simulated world stops advancing: the runtime refuses every step, reset and seed after an "
                  "e-stop until mhs.safety.reset clears the latch, and the fake's last observation and state stay "
                  "readable; the latch calls nothing in AirSim, and this package offers no live backend")
    #: The deployed model is an F0 analytic stand-in, not AirSim and not a recording.  The bridge derives the
    #: engine/determinism defaults; the values here describe what the fake actually does.
    fidelity = {
        "engine": "analytic:legacy-gym AirSim car-track stand-in (no AirSim, Unreal Engine, physics or camera)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the fake starts from the same fixed pose on every reset and its transition has no random "
                     "source, so the same action sequence repeats the same state hashes; the bridge still accepts "
                     "a seed for the next reset, but the fake ignores it; upstream reset() takes no seed, and "
                     "no seeded repeatability of a live AirSim trajectory is established",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic stand-in: it loads no AirSim, Unreal Engine, AirSim RPC client, car physics, "
            "sensor or camera model, and it is not a recording or transcript of a live AirSim run",
            "the upstream observation Box is 144 x 256 x 3 uint8 (config.ini:3-5, gym_airsim/airsim_car_env.py:36); "
            "the fake declares and returns an 8 x 8 x 3 placeholder image to keep receipts small, so the real "
            "camera frame is NOT COVERED and no captured image is claimed",
            "the fake's waypoint layout, start pose, step distance and steering gain are placeholders; the reward "
            "thresholds and the 5 m destination radius are the upstream rules, not measured map geometry",
            "the upstream constructor connects to a running AirSim RPC server, confirms the connection, enables "
            "API control and fetches waypoints from scene objects (gym_airsim/car_agent.py:8-32); the fake does "
            "none of that, and the clone contains no simulator engine (README.md:17)",
            "no live backend is offered: AirSimCarEnv is not registered with gymnasium or legacy gym and needs the "
            "external airsim package plus a running AirSim/UE4 simulator, so this package was never constructed "
            "against the upstream environment and makes no live-run claim",
            "upstream observe() retries images until their byte count matches the configured image size with no "
            "retry bound (gym_airsim/car_agent.py:39-48); construction also prints scene waypoint names to stdout "
            "(gym_airsim/car_agent.py:68-77), which would need isolation from an MHS stdio server",
            "there is no wall-clock pacing: realtime_factor is 0 and one step is one synthetic transition, while "
            "AirSim advances continuously between setCarControls calls",
            "the seed capability is accepted by the bridge and recorded for the next reset but does not change the "
            "deterministic fake; the upstream reset() accepts no seed and its trajectory was not checked",
            "the e-stop is the runtime's software latch; AirSimCarEnv exposes no stop method and close() only calls "
            "the AirSim client reset (gym_airsim/airsim_car_env.py:70-72), so nothing upstream is stopped",
        ],
    }
