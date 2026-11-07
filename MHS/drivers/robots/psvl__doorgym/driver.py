"""OpenMHS driver for gh.psvl/doorgym: the DoorGym ``blue-doorenv-v1`` MuJoCo environment.

DoorGym is a MuJoCo/Gym benchmark in which a simulated robot arm opens a door (``README.md:24-28``).  The
card's AST-confirmed entry class is ``doorenv2.envs:DoorEnvBlueV1`` (``doorenv2/doorenv2/envs/doorenv_blue.py:12``);
``blue-doorenv-v1`` registers it with ``max_episode_steps=512`` (``doorenv2/doorenv2/__init__.py:3-7``).

A GymnasiumDriver is configuration only: the bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and
``cap.world.seed.v1`` from the environment's spaces.  ``DoorEnv`` installs an action ``Box`` only for a world whose
file name contains ``gripper``: it takes ``model.actuator_ctrlrange`` and removes the last ``gripper_space`` bounds
(``doorenv2/doorenv2/envs/doorenv.py:76-83``).  For the ``pull_blue_right_v2_gripper_motor`` world this package's
fake models, that is seven motor values in [-1, 1] and the gripper value in [0, 1.05]
(``world_generator/robot/blue_right_v2_gripper_motor.xml:4-10,18``).  The environment publishes no
``observation_space``; its observation is the first ``nn`` qpos and qvel values (``nn`` is 8 for this world) followed
by the three-value finger-to-knob distance (``doorenv2/doorenv2/envs/doorenv.py:36-62,256-273,404-405``), i.e. 19
values, the size the training utility installs as ``nn*2+3`` (``util.py:61``).

The device is simulated (R0): the upstream code is a MuJoCo simulator with no hardware transport, so there is no
hardware backend, no hardware e-stop path and no operator-required limit.  The gate cannot import the upstream stack
(gym 0.14, mujoco-py, mjremote and torch are not installed and must not be installed here), so the ``fake`` backend is
this package's pure-Python analytic stand-in (``fake.py``), not MuJoCo; the fidelity ``gaps`` state that and the other
differences.  A backend name ``backends`` does not list (``sim``) would go through ``gym.make(env_id)``, which needs
``doorenv2`` to be imported and installed; that path was not run.

Every fact cites a line of the clone at commit 903493a6bd518bed5452c683c3857f1bfc5a209d.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and its evidence is ``contract_checked``,
never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTER = "doorenv2/doorenv2/__init__.py"
BLUE = "doorenv2/doorenv2/envs/doorenv_blue.py"
ENV = "doorenv2/doorenv2/envs/doorenv.py"
UTIL = "util.py"
ROBOT = "world_generator/robot/blue_right_v2_gripper_motor.xml"
WORLD = ("world_generator/world/pull_blue_right_v2_gripper_motor/"
         "1555111990_pull_blue_right_v2_gripper_motor.xml")


class DoorGymBlueV1(GymnasiumDriver):
    device_id = "doorgym-blue-v1"
    env_id = "blue-doorenv-v1"
    native = "doorenv2.envs:DoorEnvBlueV1"
    backends = {"fake": ".fake:FakeDoorEnvBlueV1"}
    display_name = "DoorGym BLUE door opening (blue-doorenv-v1)"
    vendor, model = "PSVL", "DoorGym DoorEnvBlueV1"
    tags = ["doorgym", "door-opening", "mujoco", "gym", "reinforcement-learning", "simulation",
            "robot-arm", "blue"]
    facts = [
        Fact("blue-doorenv-v1 is registered with entry point doorenv2.envs:DoorEnvBlueV1 and "
             "max_episode_steps=512", source="upstream_code", ref=f"{REGISTER}:3-7"),
        Fact("DoorEnvBlueV1 is defined in doorenv_blue.py as a DoorEnv subclass", source="upstream_code",
             ref=f"{BLUE}:12"),
        Fact("DoorEnvBlueV1 passes world_path to DoorEnv; the constructor default is "
             "/home/demo/DoorGym/world_generator/world/pull_floatinghook", source="upstream_code",
             ref=f"{BLUE}:13-26"),
        Fact("DoorEnv sets self.xml_path = self.random_world(world_path)", source="upstream_code", ref=f"{ENV}:36"),
        Fact("random_world chooses one entry of world_path with random.choice(os.listdir(world_path))",
             source="upstream_code", ref=f"{ENV}:314-318"),
        Fact("For a world file whose name contains gripper and not float or mobile, DoorEnv sets nn to 8",
             source="upstream_code", ref=f"{ENV}:58-62"),
        Fact("frame_skip is 20", source="upstream_code", ref=f"{ENV}:73"),
        Fact("DoorEnv.step advances the simulation with do_simulation(a, self.frame_skip)", source="upstream_code",
             ref=f"{ENV}:128"),
        Fact("The pull_blue_right_v2_gripper_motor world includes the gripper-motor robot and sets the MuJoCo "
             "timestep to 0.001 s", source="upstream_code", ref=f"{WORLD}:4-5"),
        Fact("The gripper-motor robot has seven joint motors with ctrlrange -1.0 to 1.0", source="upstream_code",
             ref=f"{ROBOT}:4-10"),
        Fact("The right_gripper_joint position actuator of that robot has ctrlrange 0 to 1.05",
             source="upstream_code", ref=f"{ROBOT}:18"),
        Fact("The gripper-motor robot defines twelve actuators: seven joint motors and five position actuators",
             source="upstream_code", ref=f"{ROBOT}:3-22"),
        Fact("DoorEnv initialises gripper_action with four zeros", source="upstream_code", ref=f"{ENV}:35"),
        Fact("For a gripper world DoorEnv builds the action Box from model.actuator_ctrlrange with the last "
             "gripper_space bounds removed", source="upstream_code", ref=f"{ENV}:76-83"),
        Fact("DoorEnvBlueV1.gripper_action_gen builds four finger commands from the last action value",
             source="upstream_code", ref=f"{BLUE}:29-31"),
        Fact("DoorEnv._get_obs concatenates get_robot_joints and get_dist_vec when vision is off",
             source="upstream_code", ref=f"{ENV}:268-273"),
        Fact("DoorEnvBlueV1.get_robot_joints returns the first nn qpos and qvel values", source="upstream_code",
             ref=f"{BLUE}:133-136"),
        Fact("get_dist_vec is get_finger_target minus get_knob_target", source="upstream_code",
             ref=f"{ENV}:404-405"),
        Fact("get_finger_target averages the positions of the fingerleft2 and fingerright2 geoms for a gripper "
             "world", source="upstream_code", ref=f"{BLUE}:138-143"),
        Fact("get_knob_target averages the positions of door_knob_2 and door_knob_3 for a pull world",
             source="upstream_code", ref=f"{ENV}:391-394"),
        Fact("DoorEnv.step returns (observation, reward, done, info) with done False", source="upstream_code",
             ref=f"{ENV}:130-135"),
        Fact("For gripper worlds the control penalty is -mean(square(a[:-2]))", source="upstream_code",
             ref=f"{ENV}:110-111"),
        Fact("reset_model draws the hooked and untucked chances with np.random.randint(100)",
             source="upstream_code", ref=f"{ENV}:165-172"),
        Fact("The non-float, non-mobile reset sets the first seven joint qpos from uniform(-0.1, 0.1) and draws "
             "the two-value pull goal from np_random.uniform(-0.15, 0.15)",
             source="upstream_code", ref=f"{BLUE}:57-74"),
        Fact("The training utility installs an observation Box of nn*2+3 values", source="upstream_code",
             ref=f"{UTIL}:61"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step and reset until "
                  "mhs.safety.reset clears the latch, and the last world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:blue-doorenv-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the upstream reset draws from numpy's global generator (np.random) and the environment's "
                     "np_random; gym's Env.seed sets that generator.  This package's fake draws from Python's "
                     "random.Random, so one seed repeats on the fake but gives a different trajectory than "
                     "upstream's numpy stream",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure-Python analytic stand-in, not MuJoCo: it has no rigid-body dynamics, "
            "contacts, actuator forces, sensors or noise; its integration, start values and reward are "
            "placeholders, not the model's",
            "the fake models the generated world world_generator/world/pull_blue_right_v2_gripper_motor, whose "
            "robot has an eight-value action Box; upstream random_world chooses a random XML from world_path, "
            "and DoorEnv installs an action space only when that file name contains gripper, so another world "
            "directory gives another action dimension or no action space at all",
            "the upstream environment publishes no observation_space; gym's training utility replaces it with a "
            "zero-width Box of nn*2+3 values, so the bridge derives no observation schema and the fake returns "
            "19 values with no observation bounds",
            "the fake reproduces the registered max_episode_steps=512 as a legacy four-tuple done flag at tick "
            "512; the environment itself never sets done True, gym's TimeLimit wrapper applies the limit",
            "the fake was never compared with the upstream environment: gym 0.14, mujoco-py and mjremote are "
            "not installed where the gate runs, and the sim backend was not run",
            "the env constructor's default world_path is an absolute placeholder (/home/demo/DoorGym/...) that "
            "does not exist in the clone; a deployment must supply a generated world directory",
            "no physical robot or door is modelled and the simulator was never validated against hardware",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
