"""OpenMHS driver for gh.isri-aist/robomanipbaselines: the MuJoCo UR5e cable-passing task.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{"values": [...]}``
bounded per element by the seven actuator control ranges of the UR5e model, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream environment: the upstream package depends on ``mujoco``, ``numpy``, ``pin`` and
the rest of the training stack (pyproject.toml:25-47), and package code never imports the clone.  The ``fake``
backend is therefore the package's own pure Python kinematic stand-in (fake.py) for ``MujocoUR5eCableEnv``: it
reproduces the spaces, the seven-value action, the fixed start pose restored by ``reset_model``, the step semantics
and the timestep, but it has no MuJoCo dynamics, contacts, cable geometry, camera images or reward geometry.  A
backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package with gymnasium 1.0.0 and mujoco 3.1.6 and was
not run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): a kinematic
F0 stand-in with the upstream 32 ms control period and a fixed start pose.  Every constant and rule cites a line of
the clone at the pinned commit (8535948420f8f9bc979fdb31ed049d1c82b906b2).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV_INIT = "robo_manip_baselines/envs/__init__.py"
CLASS_FILE = "robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eCableEnv.py"
BASE_FILE = "robo_manip_baselines/envs/mujoco/MujocoEnvBase.py"
UR5E_BASE = "robo_manip_baselines/envs/mujoco/ur5e/MujocoUR5eEnvBase.py"
SCENE = "robo_manip_baselines/envs/assets/mujoco/envs/ur5e/env_ur5e_cable.xml"
COMMON_SCENE = "robo_manip_baselines/envs/assets/mujoco/envs/ur5e/env_ur5e_common.xml"
SHARED_CONFIG = "robo_manip_baselines/envs/assets/mujoco/robots/ur5e/ur5e_integrated_shared_config.xml"
SPECIFIC_CONFIG = "robo_manip_baselines/envs/assets/mujoco/robots/ur5e/ur5e_integrated_specific_config.xml"


class RoboManipMujocoUR5eCable(GymnasiumDriver):
    device_id = "robomanip-ur5e-cable"
    env_id = "robo_manip_baselines/MujocoUR5eCableEnv-v0"
    native = "robo_manip_baselines.envs.mujoco:MujocoUR5eCableEnv"
    backends = {"fake": ".fake:FakeMujocoUR5eCableEnv"}
    display_name = "RoboManipBaselines MuJoCo UR5e cable passing"
    vendor, model = "isri-aist", "MujocoUR5eCableEnv-v0"
    tags = ["ur5e", "cable", "manipulation", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("MujocoUR5eCableEnv is registered as robo_manip_baselines/MujocoUR5eCableEnv-v0 with entry point "
             "robo_manip_baselines.envs.mujoco:MujocoUR5eCableEnv", source="upstream_code", ref=f"{ENV_INIT}:5-8"),
        Fact("The class subclasses MujocoUR5eEnvBase and passes the scene env_ur5e_cable.xml and the init qpos "
             "[pi, -pi/2, -0.75*pi, -0.25*pi, pi/2, pi/2] followed by eight zeros",
             source="upstream_code", ref=f"{CLASS_FILE}:9-32"),
        Fact("MujocoEnvBase subclasses gymnasium.envs.mujoco:MujocoEnv and calls it with the model path, frame_skip "
             "8, the observation space, 640x480 rendering and the default camera config",
             source="upstream_code", ref=f"{BASE_FILE}:11-38"),
        Fact("The scene sets the MuJoCo timestep to 0.004 s", source="upstream_code",
             ref=f"{COMMON_SCENE}:3"),
        Fact("MujocoEnvBase sets sim_timestep to 0.004 s and frame_skip to 8, so one environment step advances "
             "0.032 s", source="upstream_code", ref=f"{BASE_FILE}:12-13"),
        Fact("The observation space is a Dict of three Box spaces: joint_pos (7), joint_vel (7) and wrench (6), each "
             "unbounded (-inf, inf)", source="upstream_code", ref=f"{UR5E_BASE}:25-31"),
        Fact("The observation concatenates six arm joint positions and velocities with one normalized gripper value "
             "(rad2deg of the mean gripper qpos, divided by 45 and multiplied by 255), a three-axis force and a "
             "three-axis torque", source="upstream_code", ref=f"{UR5E_BASE}:84-125"),
        Fact("step runs do_simulation(action, frame_skip) and returns (observation, reward, terminated=False, "
             "truncated=False, info); a TimeLimit wrapper would be the only truncation",
             source="upstream_code", ref=f"{BASE_FILE}:82-97"),
        Fact("reset_model restores init_qpos and init_qvel and returns the observation, so the environment reset has "
             "a fixed start pose and does not draw a random one",
             source="upstream_code", ref=f"{BASE_FILE}:163-165"),
        Fact("The cable reward is 1 only when the cable stays below the pole tops, its end is past the second pole "
             "and the cable crosses the two poles; otherwise it is 0",
             source="upstream_code", ref=f"{CLASS_FILE}:48-105"),
        Fact("The UR5e model defines six arm joint actuators and one gripper tendon actuator",
             source="upstream_code", ref=f"{SPECIFIC_CONFIG}:4-14"),
        Fact("The arm actuator ctrlrange is -6.2831 to 6.2831 and the limited elbow ctrlrange is -3.1415 to "
             "3.1415", source="upstream_code", ref=f"{SHARED_CONFIG}:6-11"),
        Fact("The gripper actuator ctrlrange is 0 to 255", source="upstream_code", ref=f"{SPECIFIC_CONFIG}:13"),
        Fact("The scene includes the UR5e shared and specific configurations and the cable configuration",
             source="upstream_code", ref=f"{SCENE}:9-12"),
        Fact("The upstream pins gymnasium 1.0.0 and mujoco 3.1.6", source="upstream_code",
             ref="pyproject.toml:33-34"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The contract of the model as deployed (spec 05-fidelity section 2).  The fake is kinematic, so F0; the
    #: timestep is the upstream 0.004 s * 8 substeps, and the gaps say what the fake does not model.
    fidelity = {
        "engine": "mujoco:robo_manip_baselines/MujocoUR5eCableEnv-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the bridge accepts a seed and echoes it, but the upstream reset_model restores init_qpos and "
                     "init_qvel and does not draw a random start, so the start state is the same for every seed; the "
                     "fake keeps the same fixed start pose, and its kinematic step is deterministic for the same "
                     "actions.  modify_world can add np.random noise when world_random_scale is set, but the "
                     "environment reset does not call it",
        },
        "timestep_ms": 32.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in, not MuJoCo: it moves each of the six arm joint positions toward the "
            "action value by a placeholder fraction and moves the normalized gripper value toward the gripper "
            "action; it has no rigid-body dynamics, contacts, cable or pole collision, actuator forces, sensors, "
            "noise or physics integration",
            "the reward is a placeholder 0.0 and the episode never terminates; the upstream reward is 0 or 1 from "
            "the cable geometry in MujocoUR5eCableEnv._get_reward",
            "NOT COVERED: the camera RGB and depth images of the three 640x480 cameras (front, left, right) and "
            "any tactile intensity maps that the upstream info dictionary carries; the bridge serves no image "
            "array and the fake returns an empty info",
            "the fake returns Python lists of floats; upstream returns numpy float64 arrays, and no rendering is "
            "implemented",
            "upstream needs gymnasium 1.0.0 and mujoco 3.1.6; neither is installed where the gate runs and the sim "
            "backend was not run, so no fake trajectory was compared with the real environment",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
