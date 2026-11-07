"""OpenMHS driver for gh.opengalaxea/galaxeamanipsim: the R1Base-v0 Sapien environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment (``R1Base-v0``) and the
bridge derives the contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
the action derived from the joint-position controller's unbounded ``Box``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream environment needs Sapien, a CUDA machine and the robot assets (``pyproject.toml:18-35``), and package
code never imports the clone.  The ``fake`` backend is therefore this package's kinematic stand-in (``fake.py``); a
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id, **env_kwargs)``
(GymnasiumDriver.open_native), which needs the upstream package and was not run here.  The driver configures
``obs_mode="state"`` so both backends serve the same state-only observation.

The ``fidelity`` attribute is the model as deployed (spec 05-fidelity FID-002): a kinematic F0 stand-in, not the
Sapien rigid-body environment, with every omission listed in ``gaps``.  All facts cite the clone at the pinned commit
``abe7f5161eeaa150e6eaffdf443af5df7f23f356``.  This package is model-authored and unreviewed; it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASE_ENV = "galaxea_sim/envs/base/bimanual_manipulation.py"
BASE_CLASS = "galaxea_sim/envs/base/base.py"
R1_ROBOT = "galaxea_sim/robots/r1.py"
JOINT_CONTROLLER = "galaxea_sim/controllers/bimanual_joint_position.py"
R1_URDF = "galaxea_sim/assets/r1/robot.urdf"


class GalaxeaR1Base(GymnasiumDriver):
    device_id = "galaxea_r1_base"
    env_id = "R1Base-v0"
    env_kwargs = {"obs_mode": "state"}
    native = "galaxea_sim.envs.base.bimanual_manipulation:BimanualManipulationEnv"
    backends = {"fake": ".fake:FakeBimanualManipulationEnv"}
    display_name = "Galaxea R1Base-v0 bimanual manipulation (Sapien)"
    vendor, model = "OpenGalaxea", "R1Base-v0"
    tags = ["bimanual-manipulation", "galaxea", "r1", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("R1Base-v0 is registered to galaxea_sim.envs.base.bimanual_manipulation:BimanualManipulationEnv "
             "with robot_class=R1Robot", source="upstream_code", ref="galaxea_sim/envs/base/__init__.py:7-15"),
        Fact("BimanualManipulationEnv defaults to control_freq 15, timestep 0.01 s and obs_mode 'image', with "
             "obs_mode Literal['state', 'image']", source="upstream_code", ref=f"{BASE_ENV}:14-24"),
        Fact("SapienEnv stores the timestep and sets it on the Sapien scene", source="upstream_code",
             ref=f"{BASE_CLASS}:17-22"),
        Fact("The action space is the joint-position controller's Box(low=-inf, high=inf, shape=(action_dim,)), "
             "and action_dim is the number of left and right arm joints plus two gripper commands",
             source="upstream_code", ref=f"{JOINT_CONTROLLER}:37-42"),
        Fact("The joint-position controller takes the action as left arm targets, one left gripper target, right "
             "arm targets and one right gripper target, in that order", source="upstream_code",
             ref=f"{JOINT_CONTROLLER}:25-35"),
        Fact("step() sets the joint drive targets, runs decimation scene steps and returns observation, reward, "
             "terminated, truncated and info", source="upstream_code", ref=f"{BASE_ENV}:113-145"),
        Fact("The state observation contains upper-body joint positions and velocities, gripper positions, "
             "end-effector poses, the last joint-position commands, chassis and torso positions, the language "
             "instruction and the object dict", source="upstream_code", ref=f"{BASE_ENV}:169-223"),
        Fact("In image mode the observation adds an rgb_<camera> and a depth_<camera> array for every camera",
             source="upstream_code", ref=f"{BASE_ENV}:210-213"),
        Fact("The base environment returns empty info and reset info and never terminates or truncates",
             source="upstream_code", ref=f"{BASE_ENV}:147-157"),
        Fact("The base environment's reward is 0", source="upstream_code", ref=f"{BASE_ENV}:232-233"),
        Fact("reset(seed, options) sets the robot qpos to init_qpos, resets the controller and the world, and "
             "returns the observation and reset info; seed and options are accepted but unused",
             source="upstream_code", ref=f"{BASE_ENV}:159-164"),
        Fact("R1Robot's default init_qpos is 20 zeros", source="upstream_code", ref=f"{R1_ROBOT}:18-26"),
        Fact("The R1 URDF defines a four-joint torso, six joints per arm and two gripper finger joints per hand as "
             "non-fixed joints", source="upstream_code", ref=f"{R1_URDF}:420-1782"),
        Fact("The environment's dt is 1/control_freq and decimation is int(dt/timestep)", source="upstream_code",
             ref=f"{BASE_CLASS}:119-125"),
        Fact("R1's cameras are a 1280x720 head camera and two 320x240 wrist cameras", source="upstream_code",
             ref=f"{R1_ROBOT}:55-90"),
        Fact("SapienEnv.close releases only the viewer when one exists", source="upstream_code",
             ref=f"{BASE_CLASS}:60-62"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so the
    #: level is F0 and the gaps say what is not modelled; the bridge derives the engine, clock and determinism.
    fidelity = {
        "engine": "sapien:BimanualManipulationEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 accept a seed, but the upstream reset does not use it "
                     "(galaxea_sim/envs/base/bimanual_manipulation.py:159-164); the fake starts from a fixed "
                     "placeholder state, so a rerun with the same actions repeats the same state hashes",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in only: no Sapien rigid-body dynamics, contacts, friction, gravity, actuator, "
            "sensor, controller or noise model; the commanded joint targets are copied into the observation and "
            "the robot never moves through physics",
            "the upstream default obs_mode is 'image' and would add rgb_ and depth_ arrays for the head and wrist "
            "cameras (1280x720 and 320x240 for R1); the driver configures obs_mode='state' and the fake models no "
            "cameras, so NOT COVERED: the camera rgb_* and depth_* image arrays",
            "the fake was never compared with the upstream Sapien environment, so trajectories and end-effector "
            "poses can differ from an upstream run",
            "no wall-clock pacing: realtime_factor 0; a tick advances simulated time only",
            "one cap.world.step tick is one environment control step. The upstream step() runs decimation = "
            "int((1/control_freq)/timestep) = 6 scene steps of 10 ms, i.e. 60 ms per tick, while timestep_ms names "
            "the physics step (10 ms); the Gymnasium bridge carries no separate control-period field (FID-015)",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
