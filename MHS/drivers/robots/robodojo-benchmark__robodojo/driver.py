"""OpenMHS driver for gh.robodojo-benchmark/robodojo: the RoboDojo task environment (a Gymnasium family driver).

RoboDojo is an eval-only Isaac Sim benchmark.  ``env.environment.base_env:BaseEnv`` subclasses ``gymnasium.Env`` and
launches the registered ``IsaacRLEnv-V0``, and ``env.environment.task_env:TaskEnv`` composes the robot, scene and
camera managers for one benchmark task.  A policy drives it through a dict of joint targets named
``left_arm_joint_state``, ``left_ee_joint_state``, ``right_arm_joint_state`` and ``right_ee_joint_state`` for the
common ``dual_x5`` embodiment.

A GymnasiumDriver is configuration only: the bridge derives the whole ``cap.world.*`` contract from the environment's
spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action shaped by those four spaces,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0):
there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import Isaac Sim, Isaac Lab or gymnasium (see fake.py), so the ``fake`` backend is the package's own
pure Python joint-space stand-in.  The upstream ``TaskEnv`` is not a registered Gymnasium ID and needs the Isaac Sim
application and its downloaded assets, so this package offers no ``sim`` backend: only the fake backend is served.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit (09bd5f5e762b949f5858ece31347ce62057b3a5e).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
BASE_ENV = "env/environment/base_env.py"
TASK_ENV = "env/environment/task_env.py"
ISAAC_REG = "env/environment/isaac/__init__.py"
ROBOT_MANAGER = "env/robot_manager/robot_manager.py"
CONTROL_MANAGER = "env/robot_manager/control_manager.py"
OBS_MANAGER = "env/observation_manager/obs_manager.py"
EVAL_ENV = "src/eval_client/eval_env.py"
SIM_CONFIG = "env_cfg/sim/sim_config.yml"
TASK_CONFIG = "task/RoboDojo/config/_task.yml"
ROBOT_INFO = "env_cfg/robot/_robot_info.json"
X5_ROBOT = "env/robot_manager/robot_config/x5.py"
STACK_BLOCKS = "task/RoboDojo/tasks/stack_blocks.py"


class RoboDojoTaskEnv(GymnasiumDriver):
    device_id = "robodojo-dual-x5"
    #: TaskEnv is not registered with gymnasium.make; the one registered ID, IsaacRLEnv-V0, is the inner simulator
    #: and needs the Isaac Sim application and a task config.  Only the fake backend is served (see the module doc).
    env_id = None
    native = "env.environment.task_env:TaskEnv"
    backends = {"fake": ".fake:FakeTaskEnv"}
    display_name = "RoboDojo task environment (dual X5)"
    vendor, model = "RoboDojo Contributors", "RoboDojo TaskEnv"
    tags = ["robodojo", "manipulation", "dual-arm", "isaac-sim", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("RoboDojo is an eval-only release that provides the simulator client, benchmark tasks, asset and "
             "config validation and result artifacts, and it lists 42 simulation tasks", source="vendor_doc",
             ref=f"{README}:29-31"),
        Fact("BaseEnv subclasses gymnasium.Env", source="upstream_code", ref=f"{BASE_ENV}:93"),
        Fact("TaskEnv extends BaseEnv and composes the robot, scene, camera and capture managers", source="upstream_code",
             ref=f"{TASK_ENV}:10-58"),
        Fact("BaseEnv launches the simulator with gym.make('IsaacRLEnv-V0', ...)", source="upstream_code",
             ref=f"{BASE_ENV}:141-145"),
        Fact("IsaacRLEnv-V0 is registered with entry point env.environment.isaac.isaac_rl_env:IsaacRLEnv",
             source="upstream_code", ref=f"{ISAAC_REG}:3-9"),
        Fact("The simulation timestep is dt 0.004 s with decimation 1", source="upstream_code",
             ref=f"{SIM_CONFIG}:1-2"),
        Fact("The common task configuration selects the dual_x5 robot", source="upstream_code",
             ref=f"{TASK_CONFIG}:1-4"),
        Fact("The dual_x5 embodiment has two six-joint arms and one end-effector dimension per arm",
             source="upstream_code", ref=f"{ROBOT_INFO}:2-5"),
        Fact("With two target arms the observation and action names are left_arm, left_ee, right_arm and right_ee",
             source="upstream_code", ref=f"{ROBOT_MANAGER}:563-573"),
        Fact("The eval client assigns the policy's arm_joint_state values directly as the joint position target",
             source="upstream_code", ref=f"{EVAL_ENV}:381-384"),
        Fact("The robot, object, material and layout assets are downloaded separately under Assets/",
             source="vendor_doc", ref=f"{README}:63"),
        Fact("The policy gripper command is clipped to 0 to 1 before it is mapped to the gripper scale",
             source="upstream_code", ref=f"{EVAL_ENV}:386-395"),
        Fact("ObsManager publishes each target arm's joint state and each gripper's normalized state",
             source="upstream_code", ref=f"{OBS_MANAGER}:168-207"),
        Fact("TaskEnv.reset reloads the scene, resets the robot, advances 300 render-disabled steps and resets the "
             "cameras", source="upstream_code", ref=f"{TASK_ENV}:83-90"),
        Fact("TaskEnv.step forwards a ControlSeq list to RobotManager.control_robot", source="upstream_code",
             ref=f"{TASK_ENV}:92-93"),
        Fact("The control queue holds MetaControl entries and pops one per environment step", source="upstream_code",
             ref=f"{CONTROL_MANAGER}:58-71"),
        Fact("Each task sets its own step limit; stack_blocks uses 550", source="upstream_code",
             ref=f"{STACK_BLOCKS}:19"),
        Fact("Seed updates call seed_everywhere with the global seed", source="upstream_code",
             ref=f"{BASE_ENV}:225-228"),
        Fact("The X5 initial joint positions are 0 for joints 1 to 6 and 0.044 for the gripper joints",
             source="upstream_code", ref=f"{X5_ROBOT}:23-33"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "robodojo:TaskEnv/dual-x5",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial joint offsets and its dynamics are "
                     "deterministic, so the fake repeats a trajectory for the same seed and actions; upstream seeds "
                     "the scene layouts and Isaac Sim physics, so a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 4.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic joint-space stand-in: no Isaac Sim, no rigid-body dynamics, contacts, "
            "friction, deformable objects, actuators, sensors or domain randomization",
            "the 42 task scenes and their task-specific rewards and success checks are not modelled; the fake "
            "exposes only the common dual-X5 joint command and state convention, returns a placeholder reward and "
            "never terminates or truncates",
            "upstream TaskEnv.step takes a list of ControlSeq/MetaControl objects built by the eval client; the "
            "Gymnasium bridge passes the policy action dict straight to the fake, so the fake interprets that dict "
            "as joint positions instead of queueing control sequences",
            "the fake observation is the 14-number joint/gripper state vector; the upstream observation is a dict "
            "with vision, state, action and instruction, and the camera RGB/depth arrays are not modelled",
            "the arm joint position limits live in the downloaded USD asset, which is not in the clone; the fake "
            "leaves the arm command unbounded and bounds only the normalized gripper command to 0 to 1",
            "the fake was not compared with the upstream environment (Isaac Sim, Isaac Lab and the assets were "
            "not available where the gate ran), and no snapshot or restore is offered",
        ],
    }
