"""OpenMHS driver for gh.yitianshi/metaisaacgrasp: the AIR-v0-Data Isaac Lab environment (a Gymnasium family driver).

``AIREnvData`` extends ``AIREnvBase``, which extends Isaac Lab's ``ManagerBasedRLEnv`` (air_env_data/env.py:37,
air_env_base/env.py:44).  The environment is registered with Gymnasium as ``AIR-v0-Data`` and its entry point is
``isaac_env.air_env_data:AIREnvData`` (air_env_data/__init__.py:25-28).  A GymnasiumDriver is configuration only: the
bridge derives ``cap.world.step.v1``, ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from the environment's spaces.

The upstream stack is Isaac Sim 4.5 with Isaac Lab 2.0 (README.md:1) and the installation instructions require both
(README.md:55-57), so the ``sim`` backend (``gymnasium.make("AIR-v0-Data")``) was not run where the gate runs.
The ``fake`` backend is this package's pure Python kinematic stand-in (fake.py); its contract is checked and its
reductions are listed in ``fidelity.gaps`` below.

The device is simulated (R0): there is no hardware backend and no path to a machine.  This package is model-authored
and unreviewed; it is checked on the fake backend only, never against a hardware run.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "isaac_env/air_env_data/env.py"
BASE_ENV = "isaac_env/air_env_base/env.py"
ENV_CFG = "isaac_env/air_env_data/env_cfg.py"
BASE_CFG = "isaac_env/air_env_base/env_cfg.py"
ELEMENT_CFG = "isaac_env/air_env_base/element_cfg.py"
REGISTRATION = "isaac_env/air_env_data/__init__.py"


class AIREnvData(GymnasiumDriver):
    device_id = "metaisaacgrasp-data"
    device_kind = "world.sim"
    mode, risk = "simulated", "R0"
    env_id = "AIR-v0-Data"
    native = "isaac_env.air_env_data:AIREnvData"
    backends = {"fake": ".fake:FakeAIREnvData"}
    display_name = "MetaIsaacGrasp AIR-v0-Data (Isaac Lab manager-based environment)"
    vendor, model = "Yitian Shi", "MetaIsaacGrasp AIR-v0-Data"
    tags = ["isaac-lab", "isaac-sim", "grasp", "robot-arm", "reinforcement-learning", "simulation",
            "gymnasium"]
    facts = [
        Fact("AIREnvData extends AIREnvBase", source="upstream_code", ref=f"{ENV}:37"),
        Fact("AIREnvBase extends Isaac Lab's ManagerBasedRLEnv", source="upstream_code", ref=f"{BASE_ENV}:44"),
        Fact("AIR-v0-Data is registered with entry point isaac_env.air_env_data:AIREnvData",
             source="upstream_code", ref=f"{REGISTRATION}:25-28"),
        Fact("The project supports IsaacLab 2.0 and IsaacSim 4.5.0", source="vendor_doc", ref="README.md:1"),
        Fact("The installation instructions require Isaac-Sim and then Isaac Lab", source="vendor_doc",
             ref="README.md:55-57"),
        Fact("The action configuration has a joint-position term over the arm joints and a binary gripper term",
             source="upstream_code", ref=f"{ENV_CFG}:127-137"),
        Fact("ARM_JOINT defines six joints: shoulder_pan, shoulder_lift, elbow, wrist_1, wrist_2 and wrist_3",
             source="upstream_code", ref=f"{ELEMENT_CFG}:182-189"),
        Fact("AIREnvBase.step takes a grasp pose and an optional policy inference criteria tensor",
             source="upstream_code", ref=f"{BASE_ENV}:276"),
        Fact("The simulation advances at 1/120 s per physics step with decimation 2, so one environment step is "
             "1/60 s", source="upstream_code", ref=f"{ENV_CFG}:287-292"),
        Fact("The configured episode length is 5 s", source="upstream_code", ref=f"{ENV_CFG}:288"),
        Fact("STEP_TOTAL is 30 steps, the per-episode step total the timeout checks", source="upstream_code",
             ref=f"{ELEMENT_CFG}:43"),
        Fact("The configured camera resolution is 480 x 640 and one camera is used", source="upstream_code",
             ref=f"{ELEMENT_CFG}:60-63"),
        Fact("The observation groups are cam_pos and policy; the policy group holds rgb, normals, "
             "instance_segmentation_fast, distance_to_image_plane, pcd and gripper_pose", source="upstream_code",
             ref=f"{ENV_CFG}:144-173"),
        Fact("The reward is 1 when an object is lifted above LIFT_HEIGHT * 0.8 while the state machine is in lift",
             source="upstream_code", ref=f"{BASE_CFG}:421-426"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: determinism and clock; they are written out here so the whole contract reads in one place, and the gaps state
    #: exactly what the checked fake does not model.
    fidelity = {
        "engine": "isaaclab:AIR-v0-Data (Isaac Sim 4.5 / Isaac Lab 2.0)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 re-seeds the fake's Python random.Random and the kinematic "
                     "update is deterministic, so one implementation repeats a trajectory for the same seed and "
                     "actions; the upstream reset draws object poses with Isaac Lab's generators and the GPU "
                     "physics was not run, so agreement with the upstream stream is not claimed",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic F0 stand-in: no Isaac Sim/PhysX rigid-body dynamics, contacts, friction, gravity, "
            "actuators, sensors, noise or rendering; each tick applies a small joint-target increment and nothing "
            "moves a real robot",
            "the upstream AIREnvBase.step takes a grasp pose and loops until its policy inference criteria is met "
            "(air_env_base/env.py:276); the fake is a single-transition Gymnasium step that applies the seven "
            "action values as a kinematic target increment",
            "the action space is a seven-value unbounded Box because the clone states no action bounds; the six arm "
            "joints come from ARM_JOINT (element_cfg.py:182-189) and the seventh value is the binary gripper action "
            "term (env_cfg.py:133-137), so the fake's increment gain is test data",
            "the observation is reduced to two seven-value poses: the camera pose and the end-effector pose. "
            "NOT COVERED: the policy group's rgb, normals, instance_segmentation_fast, distance_to_image_plane and "
            "pcd image arrays, whose configured size is 480 x 640 per camera (element_cfg.py:63); the fake returns "
            "the two pose vectors only",
            "the fake truncates after STEP_TOTAL 30 transitions (element_cfg.py:43) and never terminates on grasp "
            "success; its reward is a fixed 0.0 because no object, grasp or state-machine model exists",
            "the upstream sim backend (gymnasium.make(\"AIR-v0-Data\")) needs Isaac Sim 4.5 and Isaac Lab 2.0 "
            "(README.md:1, :55-57) and was not run; only the package fake backend was checked",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep; timestep_ms is the 1/60 s environment "
            "step (sim.dt 1/120 s with decimation 2, env_cfg.py:287-292)",
            "snapshot and restore are not offered: neither the upstream environment nor the fake exposes "
            "get_state/set_state",
        ],
    }
