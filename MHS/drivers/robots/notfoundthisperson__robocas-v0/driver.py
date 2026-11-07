"""OpenMHS driver for gh.notfoundthisperson/robocas-v0: the RoboCAS-v0 manipulation benchmark environment.

``robot_sim.envs.basic_env:TaskBaseEnv`` is a ManiSkill2 ``BaseEnv`` (a Gymnasium environment) whose default control
mode combines a mobile base, an absolute end-effector pose controller and a gripper.  A ``GymnasiumDriver`` is
configuration only: ``env_id`` names the environment, the bridge derives ``cap.world.step.v1``,
``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment's spaces, and the driver adds the facts and the
fidelity contract.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The gate cannot import SAPIEN, ManiSkill2, the submodule assets or the clone, so the ``fake`` backend is this
package's pure Python kinematic stand-in (fake.py).  The ``env_id`` is the class entry point, which a gymnasium
installation resolves as ``module:Class``; a backend name that ``backends`` does not list (``sim``) would therefore
be served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native).  That path needs the upstream stack, the
initialised ManiSkill2 submodule and the PartNet-Mobility / GraspNet assets (README.md:17-24); it was not run here.

The ``fidelity`` attribute describes the model as deployed (spec 05-fidelity FID-002): the kinematic fake, not the
SAPIEN engine the upstream class would build.  The gaps say what the fake omits.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BASIC = "robot_sim/envs/basic_env.py"
DEFAULTS = "robot_sim/agents/configs/mobile_franka_panda/defaults.py"
URDF = "assets/urdf/mobile_franka_panda.urdf"
COMMON = "robot_sim/config/env/common.yaml"


class RoboCAS(GymnasiumDriver):
    device_id = "robocas"
    #: gymnasium resolves "module:Class" as an entry point; the class is not registered under a Gymnasium id.
    env_id = "robot_sim.envs.basic_env:TaskBaseEnv"
    native = "robot_sim.envs.basic_env:TaskBaseEnv"
    backends = {"fake": ".fake:FakeTaskBaseEnv"}
    #: TaskBaseEnv.evaluate is a stub that reports success on every step (basic_env.py:322-324); without autoreset
    #: the bridge would refuse every step after the first one.
    autoreset = True
    display_name = "RoboCAS-v0 (ManiSkill2/SAPIEN mobile Franka arrangement benchmark)"
    vendor, model = "notfoundthisperson", "RoboCAS-v0"
    tags = ["robocas", "manipulation", "benchmark", "sapien", "maniskill", "mobile-franka", "simulation", "gymnasium"]
    facts = [
        Fact("RoboCAS is a benchmark for robotic manipulation in complex object arrangement scenarios, run in a "
             "physical simulation environment", source="vendor_doc", ref="README.md:1-7"),
        Fact("The benchmark needs the PartNet-Mobility and GraspNet-1Billion assets in the assets directory",
             source="vendor_doc", ref="README.md:24"),
        Fact("TaskBaseEnv imports BaseEnv from mani_skill2.envs.sapien_env", source="upstream_code", ref=f"{BASIC}:11"),
        Fact("The entry class TaskBaseEnv subclasses BaseEnv and supports the simulated mobile Franka Panda robot",
             source="upstream_code", ref=f"{BASIC}:22-23"),
        Fact("TaskBaseEnv fixes robot_uid to mobile_franka_panda", source="upstream_code", ref=f"{BASIC}:49"),
        Fact("TaskBaseEnv's default control mode is base_pd_pos_arm_pd_ee_abs_pose_wrt_arm_base", source="upstream_code",
             ref=f"{BASIC}:28"),
        Fact("TaskBaseEnv defaults to sim_freq 240 and control_freq 10", source="upstream_code",
             ref=f"{BASIC}:30-31"),
        Fact("The benchmark configuration sets obs_mode image and control_freq 5", source="vendor_doc",
             ref=f"{COMMON}:20-22"),
        Fact("The arm controller for the default mode is the absolute end-effector pose controller relative to the "
             "arm base", source="upstream_code", ref=f"{DEFAULTS}:235-245"),
        Fact("The base joint-position controller takes its limits from the model", source="upstream_code",
             ref=f"{DEFAULTS}:88-96"),
        Fact("The absolute end-effector pose controller uses position bounds [-1, -1, 0] to [1, 1, 1.5]",
             source="upstream_code", ref=f"{DEFAULTS}:58-59"),
        Fact("The rotation bound of the absolute end-effector pose controller is pi", source="upstream_code",
             ref=f"{DEFAULTS}:239"),
        Fact("The gripper controller bounds each finger joint from -0.01 to 0.04", source="upstream_code",
             ref=f"{DEFAULTS}:288-297"),
        Fact("controller_configs composes each control mode from a base, an arm and a gripper controller",
             source="upstream_code", ref=f"{DEFAULTS}:300-307"),
        Fact("The base, gripper and static cameras are configured at 640 x 480", source="upstream_code",
             ref=f"{DEFAULTS}:372-408"),
        Fact("The mobile base joint limits are x -0.2 to 0.8, y -0.8 to 0.8 and rotation z -3.1415926 to 1.5707",
             source="upstream_code", ref=f"{URDF}:35-58"),
        Fact("The gripper finger joints are limited 0 to 0.04 in the URDF", source="upstream_code",
             ref=f"{URDF}:350-363"),
        Fact("TaskBaseEnv.reset delegates to its superclass reset", source="upstream_code", ref=f"{BASIC}:264-270"),
        Fact("TaskBaseEnv.evaluate is marked Not Implemented and returns {'success': True}", source="upstream_code",
             ref=f"{BASIC}:322-324"),
        Fact("TaskBaseEnv.compute_normalized_dense_reward returns 0", source="upstream_code",
             ref=f"{BASIC}:326-328"),
        Fact("TaskBaseEnv.set_main_rng ignores its seed argument and draws a random seed", source="upstream_code",
             ref=f"{BASIC}:69-70"),
        Fact("The upstream dependencies include gymnasium>=0.28.1, sapien==2.2.2 and mplib==0.1.0",
             source="vendor_doc", ref="requirements.txt:3-5"),
        Fact("TaskBaseEnv.get_images converts the camera colours, positions and segmentations for all cameras",
             source="upstream_code", ref=f"{BASIC}:379-390"),
        Fact("The agent's initial joint positions are the 12 values in init_qpos", source="upstream_code",
             ref=f"{DEFAULTS}:69"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fake is kinematic (F0), not the SAPIEN rigid-body model the upstream class builds: the contract describes
    #: the model this package actually serves (spec 05-fidelity FID-002).
    fidelity = {
        "engine": "analytic:RoboCAS-v0 fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake seeds its initial end-effector jitter from reset(seed) or cap.world.seed.v1 and its "
                     "transitions are deterministic; upstream BaseEnv.reset uses the seed for the episode RNG, but "
                     "TaskBaseEnv.set_main_rng discards it (basic_env.py:69-70) and object placement draws from "
                     "numpy's global RNG, so upstream is not exactly reproducible either",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no dynamics: the fake echoes the commanded base joint positions, end-effector pose and gripper width and "
            "derives velocities by finite difference; SAPIEN rigid-body integration, contacts, friction, inverse "
            "kinematics and the PartNet-Mobility / GraspNet scene are not modelled (the upstream engine would be "
            "F1, the deployed fake is F0)",
            "observation surrogate: 22 floats (11 state values and 11 velocities), while the upstream state "
            "observation is a richer robot/controller state vector and the benchmark configuration observes "
            "640 x 480 x 3 RGB images from three cameras (robot_sim/config/env/common.yaml:20 and "
            "robot_sim/agents/configs/mobile_franka_panda/defaults.py:372-408)",
            "termination: upstream TaskBaseEnv.evaluate is a stub returning success True (basic_env.py:322-324), so "
            "every upstream step terminates; the fake mirrors terminated=True and the driver sets autoreset=True so "
            "the bridge starts the next episode before stepping again",
            "seeding is partial upstream: TaskBaseEnv.set_main_rng discards the seed (basic_env.py:69-70) and object "
            "placement draws from numpy's global RNG; the fake's deterministic stream is Python random.Random(seed), "
            "not numpy's",
            "no rendering, no assets, no GPU and no ManiSkill2 submodule: the fake returns plain Python floats where "
            "upstream returns numpy arrays",
            "the sim backend (gymnasium.make on the class entry point) needs SAPIEN, ManiSkill2, the initialised "
            "submodule and the PartNet-Mobility / GraspNet data; it was not installed or run, only the fake backend "
            "was",
            "snapshot and restore are not offered: TaskBaseEnv exposes no get_state/set_state pair the bridge could "
            "use",
        ],
    }
