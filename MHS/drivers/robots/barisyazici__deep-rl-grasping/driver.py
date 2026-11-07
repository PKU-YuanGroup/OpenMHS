"""OpenMHS driver for gh.barisyazici/deep-rl-grasping: the gripper-env-v0 grasping environment.

``RobotEnv`` is a legacy-gym environment registered as ``gripper-env-v0`` (``manipulation_main/__init__.py:3-6``).
The published contract is the continuous, non-simplified, depth-observation configuration used by the clone's own
simulator tests: ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` a five-element normalized
vector ``[-1, 1]`` (translation xyz, yaw, gripper open/close), ``cap.world.reset.v1`` takes ``{seed}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no hardware
e-stop path and no operator-required limit.

The upstream environment needs gym 0.19.0, pybullet 3.2.5 and tensorflow 1.14.0 (``setup.py:6-24``) and never runs in
the gate; the ``fake`` backend is this package's kinematic stand-in (``fake.py``).  It models the declared action
space and the real 64 x 64 x 2 depth observation space, but returns a smaller 8 x 8 x 2 observation stand-in (the
fidelity ``gaps`` and ``RESULT.json`` name the real size).  The upstream simulator path is not offered: a backend
name that ``backends`` does not list would need the upstream package installed and was not run here.

The fidelity contract below is the model as deployed (spec 05-fidelity FID-002).  This package is model-authored and
unreviewed: it is checked on the fake backend only, and no hardware or human review is claimed.
"""

from mhs.driver import Fact, GymnasiumDriver

ROBOT = "manipulation_main/gripperEnv/robot.py"
ACTUATOR = "manipulation_main/gripperEnv/actuator.py"
WORLD = "manipulation_main/simulation/simulation.py"
TESTS = "tests_gripper/test_sim.py"


class GripperEnv(GymnasiumDriver):
    device_id = "gripper-env"
    env_id = "gripper-env-v0"
    native = "manipulation_main.gripperEnv.robot:RobotEnv"
    backends = {"fake": ".fake:FakeRobotEnv"}
    action_space_ref = f"{ACTUATOR}:72-73"
    display_name = "deep-rl-grasping gripper-env-v0 (simulated grasping)"
    vendor, model = "Baris Yazici", "gripper-env-v0"
    tags = ["grasping", "robot", "reinforcement-learning", "simulation", "gym", "pybullet"]
    facts = [
        Fact("The environment is registered as gripper-env-v0 with entry point "
             "manipulation_main.gripperEnv.robot:RobotEnv", source="upstream_code",
             ref="manipulation_main/__init__.py:3-6"),
        Fact("RobotEnv requires a config argument; a path is loaded as YAML before World is constructed",
             source="upstream_code", ref=f"{ROBOT}:46-50"),
        Fact("The continuous, non-simplified action space is Box(-1, 1, shape=(5,))",
             source="upstream_code", ref=f"{ACTUATOR}:71-73"),
        Fact("The five action components are translation xyz, yaw rotation and the gripper open/close signal",
             source="upstream_code", ref=f"{ACTUATOR}:101-105"),
        Fact("The full action clips the translation norm to max_translation and the yaw to max_yaw_rotation, both "
             "taken from the config", source="upstream_code", ref=f"{ACTUATOR}:91-98"),
        Fact("A positive fifth action value opens the gripper when it is closed, a negative one closes it when it is "
             "open, and otherwise the robot moves", source="upstream_code", ref=f"{ACTUATOR}:116-124"),
        Fact("In non-simplified depth mode _observe stacks the depth image with a zero pad whose [0][0] carries the "
             "actuator state", source="upstream_code", ref=f"{ROBOT}:199-205"),
        Fact("The non-simplified depth observation space is Box(0, 255, shape=(height, width, 2))",
             source="upstream_code", ref=f"{ROBOT}:226-228"),
        Fact("The upstream tests expect Box(-1, 1, shape=(5,)) for the continuous case and a (64, 64, 2) "
             "observation for the non-simplified depth case", source="upstream_code", ref=f"{TESTS}:30-40"),
        Fact("step returns (obs, reward, done, info) and reports done when episode_step equals time_horizon - 1",
             source="upstream_code", ref=f"{ROBOT}:152-171"),
        Fact("World advances the physics by 1/240 s in every step_sim call", source="upstream_code",
             ref=f"{WORLD}:37"),
        Fact("World.seed seeds the random generator with gym.utils.seeding.np_random and evaluate mode fixes "
             "RandomState(1)", source="upstream_code", ref=f"{WORLD}:91-100"),
        Fact("RobotEnv.reset() takes no arguments", source="upstream_code", ref=f"{ROBOT}:115"),
        Fact("World.close disconnects the physics client", source="upstream_code", ref=f"{WORLD}:88-89"),
        Fact("The gripper width is measured from 0.05 per finger, so a fully open gripper is 0.1 wide",
             source="upstream_code", ref=f"{ROBOT}:288-293"),
        Fact("The upstream dependencies include gym 0.19.0, pybullet 3.2.5, tensorflow 1.14.0 and numpy 1.18",
             source="upstream_code", ref="setup.py:6-24"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The only reset input the bridge can honour for this legacy environment: World.seed() fixes the RNG, while
    #: RobotEnv.reset() itself takes no arguments (robot.py:115) and has no options or named scenarios.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed for World.seed(); RobotEnv.reset() itself takes no arguments"},
    }
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the rest.
    fidelity = {
        "engine": "analytic",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the random object position of the fake's next reset "
                     "and the kinematic update is deterministic, so the same seed and actions repeat a trajectory; "
                     "upstream seeds numpy's generator through World.seed (simulation.py:91-100), the fake uses "
                     "Python's random.Random, so one seed does not give the same trajectory on the two",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed fake is kinematic: it has no pybullet rigid-body scene, contacts, friction, gravity, "
            "actuator or sensor model (simulation.py:43-44); the upstream RobotEnv.step also runs an actuator "
            "settling loop and one 1/240 s physics step (robot.py:159-180), while the fake advances one tick",
            "the fake returns an 8 x 8 x 2 depth-plus-actuator stand-in; the real observation space is 64 x 64 x 2 "
            "(tests_gripper/test_sim.py:39-40, config/camera_info.yaml:1-2) and there is no rendered depth image",
            "there is no TensorFlow encoder and no camera model; the depth channel is an analytic placeholder, not "
            "the upstream RGBDSensor output (sensor.py:36-41, robot.py:190-205)",
            "the reward is a constant 0.0 and the episode ends at a stand-in horizon of 150 ticks; the upstream "
            "reward functions and the config's time_horizon are not modelled (rewards.py:25-52)",
            "reset starts one fixed kinematic scene; it does not retry until an object is inside the camera field "
            "of view (robot.py:19-30) and the scene objects are not modelled",
            "no wall-clock pacing: realtime_factor 0, and the fake's timestep is nominally the upstream 1/240 s "
            "physics step, not the duration of one RobotEnv.step call",
            "the fake was not compared with the upstream environment: the upstream package needs gym 0.19.0, "
            "pybullet 3.2.5 and tensorflow 1.14.0 (setup.py:6-24) and was neither installed nor imported",
            "snapshot and restore are not offered: RobotEnv exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
