"""OpenMHS driver for gh.enactic/openarm_isaac_lab: the unimanual reach task (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
whole contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}``,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): the package drives an Isaac Lab simulation of the OpenArm robot, not the robot, so it has no hardware backend,
no e-stop path to a machine and no operator-required limit.

The gate cannot import the environment (Isaac Lab needs Isaac Sim 5.1.0, a GPU and Linux, README.md:19-23 of the
clone), so the ``fake`` backend is the package's own pure Python stand-in (``fake.py``) for the interface.  A backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native);
that path needs Isaac Sim and Isaac Lab installed and was not run here.

The upstream action and observation spaces are built by Isaac Lab outside the clone; the fake therefore exposes a
seven-value unbounded joint-position action and a 28-value observation as placeholders, and this package publishes no
action envelope.  Every Fact cites a line of the clone at the pinned commit
(cb7ff7547bdb81f290591edb9302b4845b1d49a7).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

README = "README.md"
REACH = "source/openarm/openarm/tasks/manager_based/openarm_manipulation/unimanual/reach"
REACH_CONFIG = f"{REACH}/config"
ASSETS = "source/openarm/openarm/tasks/manager_based/openarm_manipulation/assets/openarm_unimanual.py"
JOINTS = ["openarm_joint1", "openarm_joint2", "openarm_joint3", "openarm_joint4", "openarm_joint5",
          "openarm_joint6", "openarm_joint7"]


class OpenArmReach(GymnasiumDriver):
    device_id = "openarm-isaac-lab-reach"
    env_id = "Isaac-Reach-OpenArm-v0"
    native = (f"openarm.tasks.manager_based.openarm_manipulation.unimanual.reach.config.joint_pos_env_cfg:"
              f"OpenArmReachEnvCfg")
    backends = {"fake": ".fake:FakeOpenArmReachEnv"}
    display_name = "OpenArm unimanual reach (Isaac Lab)"
    vendor, model = "Enactic, Inc.", "OpenArm unimanual reach"
    tags = ["openarm", "isaac-lab", "isaac-sim", "reinforcement-learning", "simulation", "gymnasium", "reach"]
    facts = [
        Fact("The repository provides simulation and learning environments for the OpenArm robotic platform, built "
             "on NVIDIA Isaac Sim and Isaac Lab", source="vendor_doc", ref=f"{README}:11"),
        Fact("Isaac Lab training environments cover reach, lift a cube and open a drawer", source="vendor_doc",
             ref=f"{README}:16"),
        Fact("The repository has been tested with Ubuntu 22.04, Isaac Sim v5.1.0, Isaac Lab v2.3.0 and Python 3.11",
             source="vendor_doc", ref=f"{README}:19-23"),
        Fact("The package is installed with python -m pip install -e source/openarm", source="vendor_doc",
             ref=f"{README}:81"),
        Fact("Teleoperation and sim-to-sim/sim-to-real transfer pipelines are under development", source="vendor_doc",
             ref=f"{README}:17"),
        Fact("The unimanual reach task is registered with the gym id Isaac-Reach-OpenArm-v0", source="upstream_code",
             ref=f"{REACH_CONFIG}/__init__.py:21"),
        Fact("The entry_point of Isaac-Reach-OpenArm-v0 is isaaclab.envs:ManagerBasedRLEnv, a class outside this "
             "repository", source="upstream_code", ref=f"{REACH_CONFIG}/__init__.py:22"),
        Fact("The env_cfg_entry_point of Isaac-Reach-OpenArm-v0 is joint_pos_env_cfg:OpenArmReachEnvCfg",
             source="upstream_code", ref=f"{REACH_CONFIG}/__init__.py:25"),
        Fact("OpenArmReachEnvCfg subclasses ReachEnvCfg and switches the scene robot to the unimanual OpenArm "
             "configuration", source="upstream_code", ref=f"{REACH_CONFIG}/joint_pos_env_cfg.py:27-44"),
        Fact("The reach configuration sets a JointPositionActionCfg over openarm_joint.* with scale 0.5 and "
             "use_default_offset True as its arm action", source="upstream_code",
             ref=f"{REACH_CONFIG}/joint_pos_env_cfg.py:66-73"),
        Fact("The reach control step is two physics steps (decimation 2) and the physics timestep is 1/60 s",
             source="upstream_code", ref=f"{REACH}/reach_env_cfg.py:268-273"),
        Fact("The reach episode is 12.0 s long", source="upstream_code", ref=f"{REACH}/reach_env_cfg.py:270"),
        Fact("The policy observation group concatenates the joint_pos, joint_vel, pose_command and actions terms",
             source="upstream_code", ref=f"{REACH}/reach_env_cfg.py:117-154"),
        Fact("The joint_pos and joint_vel observation terms read the seven joints openarm_joint1 to openarm_joint7",
             source="upstream_code", ref=f"{REACH}/reach_env_cfg.py:117-146"),
        Fact("The pose command is sampled in pos_x 0.25 to 0.35, pos_y -0.2 to 0.2, pos_z 0.3 to 0.4, roll -pi/6 to "
             "pi/6, pitch pi/2 and yaw -pi/9 to pi/9", source="upstream_code",
             ref=f"{REACH}/reach_env_cfg.py:84-96"),
        Fact("The pose command is resampled every 4 s", source="upstream_code",
             ref=f"{REACH}/reach_env_cfg.py:87"),
        Fact("The joint_pos and joint_vel observations add uniform noise between -0.01 and 0.01",
             source="upstream_code", ref=f"{REACH}/reach_env_cfg.py:130-145"),
        Fact("The default scene holds 4096 parallel environments", source="upstream_code",
             ref=f"{REACH}/reach_env_cfg.py:254"),
        Fact("The robot asset declares velocity limits 2.175 for openarm_joint1 to openarm_joint4 and 2.61 for "
             "openarm_joint5 to openarm_joint7, and effort limits 40.0, 27.0 and 7.0 by joint group",
             source="upstream_code", ref=f"{ASSETS}:51-63"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is an interface
    #: stand-in at level F0: it repeats one seed's trajectory but models no physics, so it claims no more.
    fidelity = {
        "engine": "isaaclab:Isaac-Reach-OpenArm-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's random generator and its integration is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "fake was never compared with a run of the Isaac Lab environment",
        },
        "timestep_ms": 1000.0 * 2.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an interface stand-in, not Isaac Lab: it has no rigid-body dynamics, contacts, USD scene, "
            "sensors or reward terms, and was never compared with a run of Isaac-Reach-OpenArm-v0",
            "the action and observation spaces are placeholders: the fake exposes seven unbounded joint-position "
            "offsets and a 28-value observation, while the upstream spaces, their bounds and the observation "
            "scaling are built by Isaac Lab outside this clone; the package therefore publishes no action limit",
            "no vectorisation: the upstream scene defaults to 4096 environments (reach_env_cfg.py:254); the fake "
            "is one world",
            "the real environment needs Isaac Sim 5.1.0 and Isaac Lab 2.3.0 on Linux with a GPU (README.md:19-23); "
            "the fake backend needs neither",
            "no rendering and no snapshot or restore: the fake exposes no get_state/set_state",
        ],
    }
