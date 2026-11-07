"""OpenMHS driver for gh.angel-ayala/gym-webots-drone: the Webots drone fire-scenario environment.

A GymnasiumDriver is configuration only: ``env_id`` names the upstream Gym environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [roll, pitch, yaw, altitude]}`` bounded by the simulator's control ranges, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The gate cannot import the clone (it imports ``gym``, ``numpy``, ``cv2`` and the Webots ``controller`` binding), so the
``fake`` backend is the package's own pure-Python kinematic stand-in for ``webots_drone.envs:DroneEnvContinuous``
(fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` from the
GymnasiumDriver; that path needs the upstream package, Webots R2023b and ``WEBOTS_HOME`` and was not run here
(README.md:220-224).  The package serves the 22-element vector observation configuration (``is_pixels=False``); the
default 3x84x84 camera observation is not covered.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every fact cites a line of the clone at the pinned commit (24eb199041403d108bc94fac0f522cb33a544c9c).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "webots_drone/envs/drone_continuous.py"
SIM = "webots_drone/webots_simulation.py"
PREPROCESSOR = "webots_drone/envs/preprocessor.py"
REWARD = "webots_drone/reward.py"
WORLD = "worlds/forest_fire.wbt"


class WebotsDrone(GymnasiumDriver):
    device_id = "webots-drone"
    env_id = "webots_drone/DroneEnvContinuous-v0"
    env_kwargs = {"is_pixels": False}
    native = "webots_drone.envs:DroneEnvContinuous"
    backends = {"fake": ".fake:FakeDroneEnv"}
    display_name = "Webots drone fire-scenario environment (vector observation)"
    vendor, model = "Angel Ayala", "webots_drone/DroneEnvContinuous-v0"
    risk = "R0"
    tags = ["webots", "drone", "uav", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("webots_drone registers webots_drone/DroneEnvContinuous-v0 with entry point "
             "webots_drone.envs:DroneEnvContinuous", source="upstream_code",
             ref="webots_drone/__init__.py:23-26"),
        Fact("DroneEnvContinuous is a gym.Env whose action space is a Box built from the simulation's control ranges",
             source="upstream_code", ref=f"{ENV}:56-59"),
        Fact("The Mavic control ranges are pi/12 rad for roll, pi/12 rad for pitch, pi rad for yaw and 5 for "
             "altitude, returned as symmetric low and high limits", source="upstream_code", ref=f"{SIM}:78-87"),
        Fact("The 22-element vector observation is orientation and angular velocity, position and speed, north_rad "
             "and nine distance sensors", source="upstream_code", ref=f"{PREPROCESSOR}:26-88"),
        Fact("With is_pixels=False the observation space is a 22-element float32 Box with infinite bounds",
             source="upstream_code", ref=f"{ENV}:70-76"),
        Fact("The default observation configuration is a 3x84x84 uint8 camera image",
             source="upstream_code", ref=f"{ENV}:61-69"),
        Fact("The forest_fire world's basic time step is 8 ms", source="upstream_code", ref=f"{WORLD}:14"),
        Fact("The forest_fire world's FlightArea is 100 by 100", source="upstream_code", ref=f"{WORLD}:33-37"),
        Fact("The constructor defaults are time_limit_seconds=60, max_no_action_seconds=5, frame_skip=125 "
             "(commented 1 s), goal_threshold=5, init_altitude=25, altitude_limits=[11,75], target_pos=2, "
             "target_dim=[7,3.5] and is_pixels=True", source="upstream_code", ref=f"{ENV}:43-52"),
        Fact("set_reaction_intervals sets the frame interval to frame_skip - 5 to frame_skip + 5",
             source="upstream_code", ref=f"{ENV}:119-120"),
        Fact("step draws the number of Webots steps from the frame interval with the environment's numpy generator",
             source="upstream_code", ref=f"{ENV}:461-463"),
        Fact("The time limit and no-action limit are converted to Webots steps from the simulation's basic time step",
             source="upstream_code", ref=f"{ENV}:79-82"),
        Fact("get_flight_area halves the world's FlightArea size and appends the altitude limits",
             source="upstream_code", ref=f"{SIM}:89-95"),
        Fact("reset calls seed, sim.reset, play_fast, sync, set_target and lift_uav, then returns the state and info",
             source="upstream_code", ref=f"{ENV}:442-454"),
        Fact("step returns observation, reward, terminated, truncated and info",
             source="upstream_code", ref=f"{ENV}:498"),
        Fact("The reward combines orientation, distance, velocity and elevation terms",
             source="upstream_code", ref=f"{REWARD}:62-66"),
        Fact("A goal adds 10 to the reward and truncates the episode, and a terminal state subtracts 2",
             source="upstream_code", ref=f"{ENV}:482-491"),
        Fact("The final states are no action, flipped, max distance, inside risk zone and out of flight area",
             source="upstream_code", ref=f"{ENV}:264-289"),
        Fact("The seed method seeds the environment generator, the simulation and the virtual target",
             source="upstream_code", ref=f"{ENV}:151-161"),
        Fact("The environment is an interface for Webots R2023b and needs WEBOTS_HOME and LD_LIBRARY_PATH set",
             source="vendor_doc", ref="README.md:220-224"),
        Fact("The dependencies are gym==0.26.0, simple_pid==2.0.0 and opencv-python==4.8.1.*",
             source="upstream_code", ref="setup.py:25-27"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "webots",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the fake's random generator and its step-length draws, so one implementation "
                     "repeats a trajectory for the same seed and actions; upstream seeds numpy's generator, the "
                     "Webots world and the virtual target, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 1000.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in: no rigid-body dynamics, contacts, collisions, aerodynamics, actuator dynamics or "
            "sensor noise; the attitude-to-speed gain and the initial pose are model data, and the fake was never "
            "compared with a Webots run",
            "NOT COVERED: the default 3x84x84 RGB uint8 camera observation (is_pixels=True, "
            "drone_continuous.py:61-69); this package serves the 22-element vector observation (is_pixels=False)",
            "one cap.world.step.v1 tick is one upstream env.step, which applies the action over a random 120-130 "
            "Webots base steps of 8 ms (nominally 1000 ms, 960-1040 ms); timestep_ms is the nominal macro-step, not "
            "the 8 ms physics step, and the fake uses one integration step per environment step",
            "the Webots supervisor, world and drone controllers are not imported or run; the sim backend "
            "(gym.make) was not run",
            "no rendering and no snapshot/restore: the environment exposes no set_state",
        ],
    }
