"""OpenMHS driver for gh.tuojingai/softvtbench: the Isaac-Libero-Franka-IK-v0 environment (a Gymnasium family driver).

The card names the configuration class ``IKLiberoCameraEnvCfg`` as the entry symbol.  The registered environment is
``Isaac-Libero-Franka-IK-v0`` (entry point ``isaaclab.envs:ManagerBasedRLEnv``, env cfg entry point
``...:IKLiberoCameraEnvCfg``).  Isaac Lab and Isaac Sim are external packages and are not installed where the gate
runs, so this package is configuration plus a package fake: ``env_id`` and the environment's spaces give the
``cap.world.*`` contract, and ``fake.py`` is a kinematic stand-in for the parts of the interface the bridge consumes.
The ``sim`` backend (``gymnasium.make(env_id)``) needs Isaac Sim 4.5, Isaac Lab 2.1.1 and the external USD assets
(README.md:122, :267, :280-291); it was not run here.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The fake's action space is unbounded (no file of the clone states a numeric action bound), so the driver
declares no Limit; ``ticks`` is bounded by the family bridge
(1 to ``max_ticks``).  Every fact cites a line of the clone at the pinned commit
58056111f01e05bf1a4ae1dee75db4e3d9e7c5be.  This package is model-authored and unreviewed: it is checked on the fake
backend only.

NOT COVERED: the 512x512 RGB and distance-to-image-plane camera arrays (eye_in_hand_cam and agentview_cam), the
GelSight/FEM tactile arrays, the task-specific USD scene and object assets, and the differential-IK solver.
"""

from mhs.driver import Fact, GymnasiumDriver

FRANKA_CFG = "SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/franka_libero_env_cfg.py"
FRANKA_INIT = "SoftVTBench/source/tac_manip/tac_manip/tasks/manipulation/libero/config/franka/__init__.py"


class SoftVTBenchLibero(GymnasiumDriver):
    device_id = "softvtbench-libero-franka-ik"
    env_id = "Isaac-Libero-Franka-IK-v0"
    native = ("tac_manip.tasks.manipulation.libero.config.franka.franka_libero_env_cfg:"
              "IKLiberoCameraEnvCfg")
    backends = {"fake": ".fake:FakeSoftVTEnv"}
    display_name = "SoftVTBench Isaac-Libero-Franka-IK-v0 (Libero, Franka IK)"
    vendor, model = "TuojingAI", "SoftVTBench (Isaac-Libero-Franka-IK-v0)"
    tags = ["softvtbench", "isaac-lab", "libero", "franka", "deformable", "reinforcement-learning",
            "simulation", "gymnasium"]
    risk = "R0"
    facts = [
        Fact("The environment Isaac-Libero-Franka-IK-v0 is registered with entry_point "
             "isaaclab.envs:ManagerBasedRLEnv and env_cfg_entry_point IKLiberoCameraEnvCfg", source="upstream_code",
             ref=f"{FRANKA_INIT}:32-39"),
        Fact("IKLiberoCameraEnvCfg is defined in franka_libero_env_cfg.py and extends "
             "JointPositionLiberoCameraEnvCfg", source="upstream_code", ref=f"{FRANKA_CFG}:1065-1066"),
        Fact("The IK arm action is a differential-inverse-kinematics pose command with ik_method dls and scale 1.0",
             source="upstream_code", ref=f"{FRANKA_CFG}:1075-1086"),
        Fact("The default gripper action is a binary joint-position action whose open command is 0.04 and close "
             "command is 0.0 for the panda_finger joints", source="upstream_code", ref=f"{FRANKA_CFG}:496-501"),
        Fact("The policy observation group contains the last action, the end-effector pose in the robot base frame, "
             "the gripper position and the 7D Franka arm joint positions, with concatenate_terms False",
             source="upstream_code", ref=f"{FRANKA_CFG}:335-347"),
        Fact("The subtask observation group adds one grasp flag for every object of interest", source="upstream_code",
             ref=f"{FRANKA_CFG}:350-375"),
        Fact("The simulation advances 1/60 s of physics per simulation step with decimation 3, so one environment "
             "step is 0.05 s (20 Hz), and the libero_10 episode length is 16.0 s", source="upstream_code",
             ref=f"{FRANKA_CFG}:905-909"),
        Fact("Policy observations are synchronized at 20 Hz", source="vendor_doc", ref="README.md:67"),
        Fact("The commands, rewards and curriculum managers are None, so the configured environment has no reward "
             "function of its own", source="upstream_code", ref=f"{FRANKA_CFG}:411-417"),
        Fact("The terminations are time_out, one object_dropped term per object of interest below -0.05 m and the "
             "task goal success term", source="upstream_code", ref=f"{FRANKA_CFG}:382-401"),
        Fact("The eye-in-hand and agentview cameras are 512 by 512 with rgb and distance_to_image_plane data",
             source="upstream_code", ref=f"{FRANKA_CFG}:955-975"),
        Fact("The task JSON is selected by TASK_SUITE (default libero_10) and TASK_ID (default 0) under "
             "benchmarks/datasets/libero/config, and the USD assets come from LIBERO_ASSETS_DATA_DIR",
             source="upstream_code", ref=f"{FRANKA_CFG}:96-123"),
        Fact("The closed-loop policy client creates the environment with gym.make(env_name, cfg=env_cfg).unwrapped",
             source="upstream_code",
             ref="SoftVTBench/benchmarks/common/closedloop_policy_inference.py:97"),
        Fact("The released softvtbench-eval environment contains Isaac Sim 4.5, Isaac Lab 2.1.1 and Python 3.10",
             source="vendor_doc", ref="README.md:255-267"),
        Fact("The simulator setup installs Isaac Lab 2.1.1 from a separate checkout and then the local tac_manip "
             "extension", source="vendor_doc", ref="README.md:280-291"),
        Fact("The evaluation scene and USD assets are hosted in the external eval-assets bundle", source="vendor_doc",
             ref="README.md:122"),
        Fact("The tactile runtime assets are downloaded outside the repository and symlinked into "
             "tac_manip/assets/data", source="vendor_doc", ref="README.md:196-197"),
        Fact("The tac_manip install_requires list contains only debugpy, psutil, nvidia-ml-py and pre-commit, with "
             "no simulator or device transport package", source="upstream_code",
             ref="SoftVTBench/source/tac_manip/setup.py:14-19"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity = {
        "engine": "isaaclab:Isaac-Libero-Franka-IK-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) records the seed and the kinematic updates are deterministic, so the same actions "
                     "repeat a trajectory; the fake does not draw the initial pose from the seed, so different seeds "
                     "may start from the same state",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in only: no Isaac Sim, no rigid-body contacts, no FEM deformable objects and no "
            "actuator, sensor or noise dynamics",
            "the 512x512 RGB and distance-to-image-plane camera arrays of eye_in_hand_cam and agentview_cam are not "
            "modelled",
            "the GelSight/FEM tactile arrays and the task-specific USD scene and object assets are not modelled",
            "the differential-IK solver is not modelled: the fake adds the first three pose components to the "
            "end-effector position, ignores the three orientation components and leaves the arm joint positions at "
            "their start values",
            "goal-success and object-dropped terminations are not modelled; only the 320-step libero_10 time-out is",
            "the default libero_10 task 0 is modelled; another TASK_SUITE or TASK_ID changes the observation terms "
            "and the episode length",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by 50 ms only",
            "snapshot and restore are not offered: the upstream ManagerBasedRLEnv exposes no get_state/set_state",
            "the fake was never compared with a running Isaac Sim environment",
        ],
    }
