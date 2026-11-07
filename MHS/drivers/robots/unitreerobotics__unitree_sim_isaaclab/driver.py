"""OpenMHS driver for gh.unitreerobotics/unitree_sim_isaaclab: the G1 whole-body cylinder task.

A GymnasiumDriver is configuration only: ``env_id`` names the registered Isaac Lab task and the bridge derives the
``cap.world.*`` contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the
action shaped by the action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): it has no hardware backend and no e-stop path to a machine.

The upstream task is registered as ``Isaac-Move-Cylinder-G129-Dex1-Wholebody`` with the entry point
``isaaclab.envs:ManagerBasedRLEnv`` (tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/__init__.py:10-14) and is
created with ``gym.make(task, cfg=env_cfg).unwrapped`` (sim_main.py:185).  The entry symbol of the task card is the
local configuration class ``MoveCylinderG129Dex1WholebodyEnvCfg``; ``native`` names it because the card confirmed it
by override, and the fake is checked against it (gate G7).

The gate cannot launch Isaac Sim or Isaac Lab and the USD assets are fetched separately, so the ``fake`` backend is
this package's pure Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is
served by ``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs Isaac Sim 4.5/5.x, Isaac Lab, a
GPU and the fetched assets (README.md:127) and was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as checked (spec 05-fidelity FID-002).  It describes
the kinematic fake honestly as F0, not the rigid-body Isaac Lab model that was never launched.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRATION = "tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/__init__.py"
ENV_CFG = "tasks/g1_tasks/move_cylinder_g1_29dof_dex1_wholebody/move_cylinder_g1_29dof_dex1_hw_env_cfg.py"
SIM_MAIN = "sim_main.py"
BODY_STATE = "tasks/common_observations/g1_29dof_state.py"
GRIPPER_STATE = "tasks/common_observations/gripper_state.py"
CAMERA_STATE = "tasks/common_observations/camera_state.py"
CAMERA_CONFIG = "tasks/common_config/camera_configs.py"
ROBOT_CONFIG = "robots/unitree.py"


class G1MoveCylinderWholebody(GymnasiumDriver):
    device_id = "unitree-g1-isaaclab"
    env_id = "Isaac-Move-Cylinder-G129-Dex1-Wholebody"
    native = ("tasks.g1_tasks.move_cylinder_g1_29dof_dex1_wholebody.move_cylinder_g1_29dof_dex1_hw_env_cfg:"
              "MoveCylinderG129Dex1WholebodyEnvCfg")
    backends = {"fake": ".fake:FakeMoveCylinderG129Dex1WholebodyEnv"}
    display_name = "Unitree G1 29-DOF Dex1 whole-body cylinder task (Isaac Lab)"
    vendor, model = "Unitree Robotics", "G1 29-DOF Dex1 whole-body (Isaac Lab task)"
    tags = ["unitree", "g1", "humanoid", "mobile-manipulation", "isaac-lab", "simulation", "gymnasium"]
    facts = [
        Fact("The task is registered as the Gymnasium id Isaac-Move-Cylinder-G129-Dex1-Wholebody with the entry "
             "point isaaclab.envs:ManagerBasedRLEnv and the local configuration class "
             "MoveCylinderG129Dex1WholebodyEnvCfg", source="upstream_code", ref=f"{REGISTRATION}:10-14"),
        Fact("The simulator creates the task with gym.make(task, cfg=env_cfg).unwrapped and calls env.seed(seed), "
             "so the user-facing interface is a Gymnasium environment", source="upstream_code",
             ref=f"{SIM_MAIN}:185-186"),
        Fact("The control step is 20 ms: decimation 4 at a physics timestep of 0.005 s, i.e. four physics steps per "
             "control step", source="upstream_code", ref=f"{ENV_CFG}:144-147"),
        Fact("An episode is configured to last 20.0 s of simulated time, which is 1000 control steps of 20 ms",
             source="upstream_code", ref=f"{ENV_CFG}:145"),
        Fact("The action is a joint-position target applied to every robot joint (joint_names ['.*']) with scale 1.0 "
             "relative to the default joint offset", source="upstream_code", ref=f"{ENV_CFG}:58"),
        Fact("The policy observation group contains robot_joint_state, robot_gipper_state and camera_image, with "
             "corruption disabled and concatenate_terms false", source="upstream_code", ref=f"{ENV_CFG}:74-83"),
        Fact("The robot body observation is 87 values: 29 joint positions, 29 joint velocities and 29 joint torques",
             source="upstream_code", ref=f"{BODY_STATE}:152-156"),
        Fact("The gripper observation reads the two joint indices 31 and 29, so the articulation has at least 32 "
             "joints", source="upstream_code", ref=f"{GRIPPER_STATE}:104-106"),
        Fact("The camera observation placeholder is a (1, 480, 640, 3) tensor", source="upstream_code",
             ref=f"{CAMERA_STATE}:79-81"),
        Fact("The wrist cameras render 480 x 640 RGB frames at a 0.02 s update period", source="upstream_code",
             ref=f"{CAMERA_CONFIG}:113-118"),
        Fact("The task has no termination terms: TerminationsCfg is empty", source="upstream_code",
             ref=f"{ENV_CFG}:90-94"),
        Fact("A reset samples the object pose with x in [-0.05, 0.05] and y in [0.0, 0.05] and resets the scene to "
             "its default state", source="upstream_code", ref=f"{ENV_CFG}:163-172"),
        Fact("The robot is the G1 29-DOF whole-body configuration with a Dex1 hand, loaded from the USD asset named "
             "in the articulation configuration", source="upstream_code", ref=f"{ROBOT_CONFIG}:536-538"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model the gate checks (spec 05-fidelity section 2).  The fake is kinematic, so
    #: the level is F0; the rigid-body Isaac Lab model is not launched and was not validated.
    fidelity = {
        "engine": "isaaclab:Isaac-Move-Cylinder-G129-Dex1-Wholebody (kinematic fake)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial state and the fake's update rule is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; the "
                     "fake draws with Python's random.Random and was never compared with Isaac Lab, so the upstream "
                     "physics trajectory was not validated",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a kinematic stand-in: it does not run PhysX, rigid-body dynamics, contacts, actuators or "
            "the USD robot model; it only moves two reduced joint targets",
            "the action space is a two-element joint-position vector; the deployed task applies "
            "JointPositionActionCfg to every articulation joint (joint_names ['.*']), and the joint count and the "
            "joint-position limits come from the USD asset named in robots/unitree.py:538, which is not text in the "
            "clone",
            "the observation is a reduced stand-in: the body state is the documented 87 values, but the camera image "
            "is 1x2x2x3 instead of the deployed 1x480x640x3 placeholder "
            "(tasks/common_observations/camera_state.py:81)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the upstream Isaac Sim/Isaac Lab application was not launched: it needs Isaac Sim 4.5/5.x, Isaac Lab, a "
            "GPU and fetched USD assets (README.md:127), and the sim backend was not run",
            "the fake's initial joint values, gain, reward and the truncation bookkeeping are test data, not "
            "measured device behaviour; the only sourced timing is the 20 ms control step and the 20 s episode length",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
