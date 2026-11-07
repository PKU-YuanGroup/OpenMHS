"""OpenMHS driver for gh.cxy1997/robotiq-ur5: the UR5 and Robotiq 85 MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's model, ``xmls/lab_env.xml``, and the bridge
derives the whole contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action}``; the action is
``action.ctrl``, one number per active actuator, written to ``data.ctrl`` and integrated by ``mj_step`` for each tick.
``cap.world.reset.v1`` calls ``mj_resetData`` + ``mj_forward`` and returns the model defaults.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The model declares twelve ``motor`` actuators and no ``ctrlrange`` (``xmls/lab_env.xml:232-243``),
so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.  The model's
``<option timestep="0.02">`` (``xmls/lab_env.xml:4``) gives a 20 ms lockstep time step.

The device is simulated (R0): there is no hardware backend, no physical UR5 or Robotiq gripper is driven, and there is
no operator-required bound.  MuJoCo and mujoco-py are not installed where the acceptance gate runs, so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py): it parses the same MJCF file for the joint
and actuator shape but integrates a placeholder motion, not MuJoCo's physics.  A backend name that ``backends`` does
not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  The upstream ``environment.py`` is a task environment around the model: its reset applies
``initial_pos`` and ``joint_pos``, its step maps a four-element action to three joint angles and a gripper sequence,
and its state is two cropped camera images plus a grasp/danger vector.  The MuJoCo family serves the model and its
integration state, not that task interface; the fidelity ``gaps`` say so.  Every Fact cites a line of the clone at
commit 6c6d53f6a7d525f83e103ce594f166520d9390ee.  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "xmls/lab_env.xml"
MODEL_PATH = "../../../../robots/cxy1997/robotiq-ur5/" + MODEL
ENVIRONMENT = "environment.py"
LAB = "xmls/lab_env.xml"
README = "README.md"


class RobotiqUR5(MujocoDriver):
    device_id = "robotiq-ur5"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "UR5 with Robotiq 85 gripper (MuJoCo scene)"
    vendor, model = "cxy1997", "UR5 + Robotiq 85"
    tags = ["gripper", "manipulation", "mujoco", "robot", "robotiq", "simulation", "ur5"]
    facts = [
        Fact("The README describes the repository as 'Simulator of UR5 robotic arm with Roboriq gripper, built with "
             "MuJoJo'", source="vendor_doc", ref=f"{README}:2"),
        Fact("The README requires MuJoCo 1.5.0 and mujoco-py", source="vendor_doc", ref=f"{README}:5-6"),
        Fact("The README's Python usage is 'from environment import lab_env'", source="vendor_doc",
             ref=f"{README}:9"),
        Fact("The lab_env constructor loads xmls/lab_env.xml as the real-world simulator and xmls/light_env.xml to "
             "locate the gripper", source="upstream_code", ref=f"{ENVIRONMENT}:75-79"),
        Fact("The upstream reset writes 42 qpos values from initial_pos and then overwrites the first three with the "
             "selected task's joint_pos values", source="upstream_code", ref=f"{ENVIRONMENT}:89-92"),
        Fact("The upstream step maps action[0], action[1] and action[2] to qpos[0], qpos[1] and qpos[2] over "
             "-30 to 45 degrees, -105 to -50 degrees and 0 to 180 degrees, and uses action[3] for the number of "
             "gripper closing steps", source="upstream_code", ref=f"{ENVIRONMENT}:103-111"),
        Fact("The upstream get_state renders 960 by 720 images from workbench_camera and upper_camera, crops "
             "214 by 214 windows, adds Gaussian noise, and returns the two images plus the six-element vector "
             "[x1, y1, x2, y2, grasped, danger]", source="upstream_code", ref=f"{ENVIRONMENT}:170-188"),
        Fact("The upstream safety_check steps the simulation, sums the absolute movement of the first six joints "
             "and compares it with safety_threshold", source="upstream_code", ref=f"{ENVIRONMENT}:190-198"),
        Fact("The safety_threshold is 0.01", source="upstream_code", ref=f"{ENVIRONMENT}:33"),
        Fact("The model root element is '<mujoco model=\"ur5\">' and its compiler element declares angle radian and "
             "meshdir meshes", source="upstream_code", ref=f"{LAB}:1-2"),
        Fact("The option element sets gravity 0 0 0, an elliptic cone and timestep 0.02 s", source="upstream_code",
             ref=f"{LAB}:4"),
        Fact("The global default class gives joints frictionloss 1 and damping 1 and motors gear 0.8",
             source="upstream_code", ref=f"{LAB}:12-19"),
        Fact("The arm is a chain of six hinge joints named joint1 to joint6", source="upstream_code",
             ref=f"{LAB}:74-106"),
        Fact("The right gripper finger has hinge joints joint7_1 with range 0 to 0.872664626 rad, joint8_1 and "
             "joint9_1 with range 0 to 2.967059728 rad, and joint10_1 with range 0 to 1 rad", source="upstream_code",
             ref=f"{LAB}:119-137"),
        Fact("The left gripper finger has hinge joints joint7_2 with range 0 to 0.872664626 rad, joint8_2 and "
             "joint9_2 with range 0 to 2.967059728 rad, and joint10_2 with range 0 to 1 rad", source="upstream_code",
             ref=f"{LAB}:143-161"),
        Fact("Four target bodies each declare three slide joints free_x, free_y and free_z and one ball joint "
             "free_ball", source="upstream_code", ref=f"{LAB}:173-207"),
        Fact("The actuator section declares twelve motor actuators: gravity_1 to gravity_4 on free_z_1 to free_z_4 "
             "with gear '1 0 0 0 0 0', close_1 and close_2 on joint7_1 and joint7_2 with gear '0.2 0 0 0 0 0', "
             "joint1_motor with gear 1.2, and joint2_motor to joint6_motor", source="upstream_code",
             ref=f"{LAB}:232-243"),
        Fact("No active actuator element of the model declares a ctrlrange attribute", source="upstream_code",
             ref=f"{LAB}:232-243"),
        Fact("The model declares the cameras workbench_camera and upper_camera", source="upstream_code",
             ref=f"{LAB}:42-49"),
        Fact("The model declares four touch sensors on target_site_1 to target_site_4", source="upstream_code",
             ref=f"{LAB}:247-251"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the timestep
    #: from the model and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:ur5",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "working seed input and cap.world.reset.v1 restores the model defaults, so a run repeats on the "
                     "same engine but no seed selects a different state.  The package's fake is deterministic too, "
                     "but its placeholder motion is not the engine's physics",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model for the joint "
            "dimensions, the actuator count, the control targets and the absent ctrlrange, but integrates a "
            "placeholder first-order motion and resolves no contact, equality, tendon, mesh, texture, sensor or "
            "camera",
            "the upstream environment.py task interface is NOT COVERED: its reset applies initial_pos (:16-23) and "
            "joint_pos (:24-27, :89-92), its step maps a four-element action to three joint angles and a gripper "
            "sequence (:103-141), and get_state returns two cropped noisy 214 by 214 camera images plus the "
            "grasp/danger vector (:170-188); the MuJoCo bridge instead exposes mj_resetData/mj_step and the model "
            "integration state, so the camera arrays and the task-level outputs are not served",
            "the model declares no actuator ctrlrange (xmls/lab_env.xml:232-243), "
            "so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; the values are simulated controls in the model's units and nothing was validated "
            "against a real UR5 or Robotiq gripper",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine, and the sim backend that imports mujoco was not run",
        ],
    }
