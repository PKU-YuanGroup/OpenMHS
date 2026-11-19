"""OpenMHS driver for gh.araffin/robotics-rl-srl: the OmniRobot Gym environment (a Gymnasium family driver).

``OmnirobotEnv-v0`` is registered to ``environments.omnirobot_gym.omnirobot_env:OmniRobotEnv``
(``environments/registry.py:52,66-72``).  The default configuration is the in-process simulator
(``real_robots/constants.py:14``): ``is_discrete=True`` selects ``spaces.Discrete(4)``
(``environments/omnirobot_gym/omnirobot_env.py:73-75,105-106``) and the observation is a 224 x 224 x 3 uint8 image
(``environments/omnirobot_gym/omnirobot_env.py:29-30,120-122``).  A GymnasiumDriver is configuration only: the bridge
derives ``cap.world.step.v1`` (``{ticks, action}`` with ``action.index`` 0 to 3), ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's spaces and the legacy Gym API.

The device is simulated (R0).  There is no hardware backend, no independent physical stop and no operator-required
limit; the runtime's software latch is the only stop and the environment state stays readable after it.

Why a package fake: the upstream simulator imports numpy, OpenCV, PyTorch, SciPy, ZMQ and seaborn, and its ROS path is
Python 2 only (``real_robots/README.md:27``); package code never imports the clone.  ``fake.py`` is an analytic stand-in
for the discrete simulator control, not a recording.  A backend name that ``backends`` does not list (``sim``) is served
by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the upstream dependencies and the
registry import and was not run here.

Every fact cites a line of the clone at the pinned commit eae7c1ab310c79662f6e68c0d255e08641037ffa.  The package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "environments/omnirobot_gym/omnirobot_env.py"
REGISTRY = "environments/registry.py"
CONSTANTS = "real_robots/constants.py"
MANAGER = "real_robots/omnirobot_utils/omnirobot_manager_base.py"
SIMULATOR = "real_robots/omnirobot_simulator_server.py"
SRL_ENV = "environments/srl_env.py"


class OmniRobot(GymnasiumDriver):
    device_id = "omnirobot"
    env_id = "OmnirobotEnv-v0"
    native = "environments.omnirobot_gym.omnirobot_env:OmniRobotEnv"
    backends = {"fake": ".fake:FakeOmniRobotEnv"}
    # Keep truthful fake-backend provenance: the symbolic cardinality is not resolved by G4.
    # The matching upstream space/count and movement codes are separate, checked facts below.
    display_name = "OmniRobot Gym environment (in-process simulator)"
    vendor, model = "araffin", "OmnirobotEnv-v0"
    tags = ["omnirobot", "robotics", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("OmnirobotEnv-v0 is registered to the OmniRobotEnv class", source="upstream_code",
             ref=f"{REGISTRY}:52"),
        Fact("The registry builds the entry point from env_class.__module__ + ':' + env_class.__name__",
             source="upstream_code", ref=f"{REGISTRY}:66-72"),
        Fact("USING_OMNIROBOT_SIMULATOR defaults to True", source="upstream_code", ref=f"{CONSTANTS}:14"),
        Fact("When USING_OMNIROBOT_SIMULATOR is true the environment constructs OmniRobotSimulatorSocket with "
             "output_size [RENDER_WIDTH, RENDER_HEIGHT] and random_target; otherwise it connects a ZMQ PAIR socket "
             "to HOSTNAME:self.server_port", source="upstream_code", ref=f"{ENV}:130-138"),
        Fact("The separate ROS server creates publishers for /position_commands, /stop, /wheel_speeds_commands and "
             "/velocity_commands", source="upstream_code", ref="real_robots/omnirobot_server.py:71-83"),
        Fact("The separate ROS server publishes True to both position and velocity controller switches during "
             "construction", source="upstream_code", ref="real_robots/omnirobot_server.py:88-92"),
        Fact("is_discrete defaults to True", source="upstream_code", ref=f"{ENV}:73-75"),
        Fact("The default action space is spaces.Discrete(N_DISCRETE_ACTIONS)", source="upstream_code",
             ref=f"{ENV}:105-106"),
        Fact("N_DISCRETE_ACTIONS is 4", source="upstream_code", ref=f"{ENV}:35"),
        Fact("The discrete action values are FORWARD 0, BACKWARD 1, LEFT 2, RIGHT 3 and STOP 4",
             source="upstream_code", ref=f"{CONSTANTS}:114-119"),
        Fact("A step sends the action to the simulator socket, reads the state, receives and resizes the camera "
             "frame, and returns a 4-tuple (observation, reward, done, {})", source="upstream_code",
             ref=f"{ENV}:193-214"),
        Fact("A reset clears the episode flag and the step and contact counters, sends the reset command, reads the "
             "state and observation, and returns the observation without an info dictionary", source="upstream_code",
             ref=f"{ENV}:267-288"),
        Fact("The native reset signature takes no arguments besides self", source="upstream_code", ref=f"{ENV}:267"),
        Fact("RENDER_WIDTH and RENDER_HEIGHT are 224", source="upstream_code", ref=f"{ENV}:29-30"),
        Fact("The observation space is Box(0, 255, shape=(RENDER_WIDTH, RENDER_HEIGHT, 3), dtype=np.uint8)",
             source="upstream_code", ref=f"{ENV}:120-122"),
        Fact("The simulator samples the robot's initial x and y with numpy's random_sample from the INIT_MIN/MAX "
             "bounds", source="upstream_code", ref=f"{MANAGER}:88-89"),
        Fact("INIT_MIN_X = -0.7, INIT_MAX_X = 0.7, INIT_MIN_Y = -0.7 and INIT_MAX_Y = 0.7", source="upstream_code",
             ref=f"{CONSTANTS}:96-97"),
        Fact("On a reset the simulator draws a target in x and y with numpy's random_sample from the TARGET_MIN/MAX "
             "bounds when random_target is true or on the first episode", source="upstream_code",
             ref=f"{SIMULATOR}:413-419"),
        Fact("TARGET_MIN_X = -0.7, TARGET_MAX_X = 0.7, TARGET_MIN_Y = -0.7 and TARGET_MAX_Y = 0.7",
             source="upstream_code", ref=f"{CONSTANTS}:100-101"),
        Fact("MIN_X = -0.85, MAX_X = 0.85, MIN_Y = -0.85 and MAX_Y = 0.85", source="upstream_code",
             ref=f"{CONSTANTS}:92-93"),
        Fact("STEP_DISTANCE is 0.1 m", source="upstream_code", ref=f"{CONSTANTS}:121"),
        Fact("A forward move is refused when robot_pos[0] + STEP_DISTANCE is not below MAX_X and the manager "
             "reports a bump; backward, left and right use MIN_X, MAX_Y and MIN_Y analogously", source="upstream_code",
             ref=f"{MANAGER}:27-68"),
        Fact("The reward is REWARD_TARGET_REACH when the robot-target distance is below DIST_TO_TARGET_THRESHOLD, "
             "REWARD_BUMP_WALL for a wall bump and REWARD_NOTHING otherwise", source="upstream_code",
             ref=f"{MANAGER}:152-158"),
        Fact("REWARD_TARGET_REACH is 1, REWARD_NOTHING is 0 and REWARD_BUMP_WALL is -1", source="upstream_code",
             ref=f"{CONSTANTS}:81-83"),
        Fact("DIST_TO_TARGET_THRESHOLD is 0.2 m", source="upstream_code", ref=f"{CONSTANTS}:110"),
        Fact("MAX_STEPS is 250", source="upstream_code", ref=f"{CONSTANTS}:90"),
        Fact("_hasEpisodeTerminated returns True when episode_terminated is set or the step counter is greater than "
             "MAX_STEPS", source="upstream_code", ref=f"{ENV}:290-301"),
        Fact("SRLGymEnv.seed sets np_random and returns [seed]", source="upstream_code", ref=f"{SRL_ENV}:71-78"),
        Fact("The simulator samples positions with numpy's random_sample()", source="upstream_code",
             ref=f"{MANAGER}:88-89"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the deployed fake (spec 05-fidelity section 2).  The bridge derives the engine and
    #: the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:OmnirobotEnv-v0 (analytic fake of the in-process simulator)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's legacy seed() controls the fake's own generator, so the fake repeats a trajectory "
                     "for one seed and action sequence; upstream SRLGymEnv.seed sets np_random only and the "
                     "simulator draws from numpy's global generator (environments/srl_env.py:71-78, "
                     "real_robots/omnirobot_utils/omnirobot_manager_base.py:88-89), so the upstream simulator is "
                     "not seeded by this path",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "action.index 0..3 is derived from the declared fake's Discrete(4), with fake-backend provenance; "
            "there is no action_space_ref claiming that the symbolic native space declaration by itself shows "
            "the maximum index. Native Discrete(N_DISCRETE_ACTIONS), N_DISCRETE_ACTIONS=4 and movement codes "
            "0..3 are cited separately in the facts",
            "the fake is an analytic stand-in for the discrete simulator, not a recording: it models the 0.1 m "
            "moves, the 0.85 wall bumps, the 0.2 m target reward and the 251-step termination from "
            "real_robots/omnirobot_utils/omnirobot_manager_base.py:22-158 and real_robots/constants.py:78-121",
            "no rendering: the background image, marker sprites, camera projection, 480 x 480 crop and 224 x 224 "
            "resize are not modelled; the fake returns a 16 x 16 x 3 placeholder marker image while the device "
            "returns a 224 x 224 x 3 image (environments/omnirobot_gym/omnirobot_env.py:29-30,120-122,229-239)",
            "no noise: the robot position (0.01 m), yaw, marker size and image luminosity noise of "
            "real_robots/omnirobot_simulator_server.py:16-22 are not modelled, and positions are exact",
            "the fake's seed() controls its own generator; the upstream simulator's random draws use numpy's "
            "global generator and are not controlled by SRLGymEnv.np_random",
            "the Gymnasium family advertises reset options, but the native reset takes no arguments; the bridge's "
            "legacy fallback calls seed() and reset() without them, so an options value is not used",
            "one step is one discrete command of 0.1 m, not a physics integration interval: no physics timestep "
            "is declared, hence timestep_ms 0 and no wall-clock pacing",
            "the PyBullet, Gazebo and ROS paths are not modelled; the fake runs in the package and the upstream "
            "simulator or ROS bridge was not run",
            "the non-simulator ZMQ route can reach the separate real-robot ROS server, whose construction enables "
            "both position and velocity controllers (real_robots/omnirobot_server.py:71-92); the R0 contract and "
            "the software latch cover only the declared fake and the default in-process simulator, not that route",
            "the fake was not compared with the upstream simulator; shape_reward is stored but unused, as in the "
            "clone, and the image is a placeholder rather than a camera frame",
        ],
    }
