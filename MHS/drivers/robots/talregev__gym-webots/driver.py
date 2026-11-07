"""OpenMHS Gymnasium driver for the gym-webots pioneer3at camera environment.

The card named a ROS helper, but the device this package serves is a legacy
``gym.Env``: ``WebotsCircuit2cPionner3atCameraNnEnv`` exposes ``reset()`` and
``step(action)`` and uses ROS only internally, to reach the Webots supervisor,
wheel, camera and LaserScan services and topics.  The SDK's ``GymnasiumDriver``
is the family that expresses that environment interface (``cap.world.step.v1``,
``cap.world.reset.v1``, ``cap.world.seed.v1``); the bridge also accepts the
legacy gym 4-tuple step and the bare state reset.  This is a deliberate
deviation from the card's ``helper`` and ``family``; the card's entry symbol is
kept as ``native``.

The package is simulated R0.  The fake backend is a pure-Python stand-in; no
Webots, ROS or gym installation is imported or run.  The package is
model-authored and unreviewed: ``driver.lock.json`` keeps ``reviewed_by`` null,
and a passing fake gate is contract evidence only, never a hardware or live
simulation run.
"""

from mhs.driver import Fact, GymnasiumDriver

_ENTRY = "gym_webots/envs/pioneer/webots_circuit2c_pioneer_camera_nn.py"
_BASE = "gym_webots/envs/webots_env.py"


class GymWebotsPioneer(GymnasiumDriver):
    """The pioneer3at camera environment served through the Gymnasium bridge."""

    device_id = "webots-pioneer3at-camera"
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    native = "gym_webots.envs.pioneer:WebotsCircuit2cPionner3atCameraNnEnv"
    backends = {"fake": ".fake:FakeWebotsPioneerEnv"}
    display_name = "gym-webots pioneer3at camera environment"
    vendor = "talregev"
    model = "gym-webots (WebotsCircuit2cPioneerCameraNnEnv-v0)"
    tags = ["webots", "ros", "pioneer3at", "camera", "reinforcement-learning", "simulation", "gym"]

    facts = [
        Fact("WebotsCircuit2cPionner3atCameraNnEnv is defined in the pioneer package and extends "
             "webots_env.WebotsEnv.", source="upstream_code", ref=f"{_ENTRY}:28"),
        Fact("The package registers the environment id WebotsCircuit2cPioneerCameraNnEnv-v0.",
             source="upstream_code", ref="gym_webots/__init__.py:10"),
        Fact("The registered entry point is gym_webots.envs.pioneer:WebotsCircuit2cPionner3atCameraNnEnv.",
             source="upstream_code", ref="gym_webots/__init__.py:11"),
        Fact("WebotsEnv subclasses gym.Env.", source="upstream_code", ref=f"{_BASE}:13"),
        Fact("WebotsEnv.__init__ starts roscore and Webots with subprocess.Popen and initializes a ROS node "
             "named gym.", source="upstream_code", ref=f"{_BASE}:58-70"),
        Fact("A relative world file is resolved under gym_webots/envs/assets/worlds.",
             source="upstream_code", ref=f"{_BASE}:50-56"),
        Fact("The pioneer environment passes pioneer3at-circle.wbt to WebotsEnv.",
             source="upstream_code", ref=f"{_ENTRY}:32"),
        Fact("The environment holds the wheel motor names front_left_wheel, front_right_wheel, back_left_wheel "
             "and back_right_wheel.", source="upstream_code", ref=f"{_ENTRY}:34"),
        Fact("The environment creates ROS service proxies for simulation_reset, robot/time_step, "
             "simulation_set_mode, camera/enable and Sick_LMS_291/enable.",
             source="upstream_code", ref=f"{_ENTRY}:36-41"),
        Fact("For every wheel the environment creates set_velocity and set_position service proxies of type "
             "set_float.", source="upstream_code", ref=f"{_ENTRY}:45-56"),
        Fact("The environment switches Webots to run mode by calling the simulation_set_mode proxy with 1.",
             source="upstream_code", ref=f"{_ENTRY}:59"),
        Fact("The basic time step is read from the robot/get_basic_time_step service and stored in TIME_STEP.",
             source="upstream_code", ref=f"{_ENTRY}:62-65"),
        Fact("The camera observation parameters are img_rows 32, img_cols 32 and img_channels 1.",
             source="upstream_code", ref=f"{_ENTRY}:73-75"),
        Fact("calculate_observation marks done when a LaserScan range is greater than 0 and less than 0.21.",
             source="upstream_code", ref=f"{_ENTRY}:77-83"),
        Fact("enable_sensors calls the camera and lidar enable proxies with TIME_STEP.",
             source="upstream_code", ref=f"{_ENTRY}:89-97"),
        Fact("enable_motors calls every set_position proxy with float infinity.",
             source="upstream_code", ref=f"{_ENTRY}:99-103"),
        Fact("stop_robot calls every set_velocity proxy with 0.",
             source="upstream_code", ref=f"{_ENTRY}:105-109"),
        Fact("step implements three actions: 0 forward, 1 right and 2 left; forward calls all four velocity "
             "proxies with 6, a right turn calls the left wheels with 6 and the right wheels with 0.3, and a "
             "left turn calls the left wheels with 0.3 and the right wheels with 6.",
             source="upstream_code", ref=f"{_ENTRY}:123-139"),
        Fact("step does not advance the simulation itself: the step_sim call is commented out and step waits "
             "for a LaserScan on /pioneer3at/Sick_LMS_291/laser_scan/layer0 and a camera Image on "
             "/pioneer3at/camera/image with a timeout of 5 seconds.",
             source="upstream_code", ref=f"{_ENTRY}:141-169"),
        Fact("step updates a 50-entry last50actions history with 0 for forward and 1 otherwise.",
             source="upstream_code", ref=f"{_ENTRY}:172-178"),
        Fact("The reward is computed from left and right sums of the LaserScan ranges and a center-detour "
             "term, and is -1 when the observation marks done.", source="upstream_code",
             ref=f"{_ENTRY}:196-212"),
        Fact("step converts the camera frame to grayscale, resizes it to img_rows by img_cols, reshapes it to "
             "(1, 1, rows, cols) and returns (state, reward, done, {}).", source="upstream_code",
             ref=f"{_ENTRY}:220-227"),
        Fact("reset calls the simulation_reset proxy with 1, sleeps 1 second, then enables the sensors, stops "
             "the robot and enables the motors.", source="upstream_code", ref=f"{_ENTRY}:239-247"),
        Fact("reset returns the resized camera state alone, not an observation/info pair.",
             source="upstream_code", ref=f"{_ENTRY}:273-279"),
    ]

    safe_state = ("The simulated world stops advancing: after an e-stop the runtime refuses step and reset "
                  "until mhs.safety.reset clears the latch, and the last observation stays readable.")
    #: The deployed backend here is the package's analytic fake, not Webots.  The
    #: upstream TIME_STEP is read at run time, so the fake declares no timestep.
    fidelity = {
        "engine": "analytic:gym_webots pioneer3at fake (no Webots physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake is deterministic given its reset seed; the seed changes a placeholder lane "
                     "offset. Upstream seeds gym.utils.seeding.np_random in _seed(), but its camera and "
                     "LaserScan stream comes from Webots, so the fake trajectory is not the upstream stream.",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python stand-in: it does not launch roscore or Webots, does not import rospy, "
            "cv2 or skimage, and exchanges no ROS topics or services",
            "the real observation is a grayscale camera frame resized to 32 x 32 and reshaped to "
            "(1, 1, 32, 32); the fake synthesizes a 32 x 32 pattern of placeholder pixels, so its values and "
            "scene content are not renderings",
            "wheel commands, laser ranges, collision detection and reward are analytic placeholders; the fake "
            "does not model the Webots pioneer3at wheels, the Sick LMS 291 scan, the 0.21 collision test or the "
            "laser-window reward",
            "the upstream class defines no action_space or observation_space; the fake declares Discrete(3) "
            "from the three actions implemented in step and Box(0..255) at the real frame shape, both as "
            "placeholders. No action_space_ref is set because no upstream line defines the space",
            "the Webots basic time step is read at run time from /pioneer3at/robot/get_basic_time_step "
            "(webots_circuit2c_pioneer_camera_nn.py:62-65); the fake declares timestep_ms 0 and does not pace "
            "or step the Webots engine",
            "the upstream step returns a legacy gym 4-tuple and reset returns a bare state; the bridge accepts "
            "both, and the fake mirrors that shape",
            "the upstream reward slices LaserScan lists with laser_len/5 and laser_len/10 "
            "(webots_circuit2c_pioneer_camera_nn.py:197-198), which are float indices under Python 3; the fake "
            "does not run that code",
            "no real Webots, ROS or gym/gymnasium run is claimed; gate evidence stays contract_checked (F0)",
        ],
    }
