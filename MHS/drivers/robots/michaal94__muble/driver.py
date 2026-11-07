"""OpenMHS driver for gh.michaal94/muble: the Robotiq 2F-85 gripper MJCF of the MuBlE environment (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF model (the card's ``models[0]``,
``conda/robotiq_gripper_85.xml``) and the bridge derives the whole contract from the model it loads.  The step action
is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (two position actuators with ctrlrange
0 to 0.85); the world state is the integration state of the model (``time``, ``qpos``, ``qvel``, ``ctrl``) plus the
tick count, and ``cap.world.reset.v1`` restores the model defaults.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The gate cannot install
MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same model file for the joint count, the actuator count and the per-actuator control ranges, but its integration is a
placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit 84f1109110aeca0063b0d062d87096cc53cc0f71.  This
package is model-authored and unreviewed: it is checked on the fake backend only.

The card's ``entry_symbols`` names the robosuite environment ``environment.tabletop_env:TabletopEnv`` (verified at
``environment/tabletop_env.py:20``).  That class needs robosuite and mujoco-py and is not the model this family serves;
the card's ``decision`` is ``family-config`` with the ``MujocoDriver`` helper, and the card's ``models`` are MJCF
files, so this package serves the first model through the MuJoCo bridge.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "conda/robotiq_gripper_85.xml"
CLONE = "../../../../robots/michaal94/muble"
MODEL_PATH = CLONE + "/" + MODEL
GRIPPER_PY = "conda/robotiq_85_gripper.py"
CONDA_SCRIPT = "conda/robosuite_elements.sh"
ENV_DOC = "docs/muble/environment.md"
ENV_PY = "environment/tabletop_env.py"


class MubleGripper(MujocoDriver):
    device_id = "muble-gripper"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Robotiq 2F-85 gripper (MuBlE)"
    vendor, model = "michaal94 (MuBlE)", "Robotiq 2F-85"
    tags = ["gripper", "manipulation", "muble", "mujoco", "robotiq", "simulation", "two-finger"]
    facts = [
        Fact("The served model is the MJCF gripper model conda/robotiq_gripper_85.xml, whose root element is "
             "'<mujoco model=\"robotiq_gripper_85_model\">'", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model declares two <position> actuators, finger_1 on joint finger_joint and finger_2 on joint "
             "right_outer_knuckle_joint, each with ctrllimited true and ctrlrange 0 0.85",
             source="upstream_code", ref=f"{MODEL}:32-33"),
        Fact("finger_joint is a hinge with range 0 to 0.872664626 rad", source="upstream_code", ref=f"{MODEL}:53"),
        Fact("left_inner_finger_joint is a hinge with range -0.8757 to 0.8757 rad", source="upstream_code",
             ref=f"{MODEL}:60"),
        Fact("left_inner_knuckle_joint is a hinge with range 0 to 0.8757 rad", source="upstream_code",
             ref=f"{MODEL}:70"),
        Fact("right_outer_knuckle_joint is a hinge with range 0 to 0.872664626 rad", source="upstream_code",
             ref=f"{MODEL}:76"),
        Fact("right_inner_finger_joint is a hinge with range -0.8757 to 0.8757 rad", source="upstream_code",
             ref=f"{MODEL}:83"),
        Fact("right_inner_knuckle_joint is a hinge with range 0 to 0.8757 rad", source="upstream_code",
             ref=f"{MODEL}:93"),
        Fact("Two fixed tendons couple finger_joint with the left inner joints and right_outer_knuckle_joint with the "
             "right inner joints, with coefficients 1, -3 and 1", source="upstream_code", ref=f"{MODEL}:17-28"),
        Fact("The model declares a force sensor and a torque sensor at the site ft_frame", source="upstream_code",
             ref=f"{MODEL}:99-102"),
        Fact("The model's <asset> block declares the STL meshes of the gripper under meshes/robotiq_85_gripper/",
             source="upstream_code", ref=f"{MODEL}:3-12"),
        Fact("The conda gripper class loads the MJCF through robosuite's "
             "xml_path_completion('grippers/robotiq_gripper_85.xml')", source="upstream_code",
             ref=f"{GRIPPER_PY}:18"),
        Fact("The conda setup copies robotiq_gripper_85.xml into robosuite's models/assets/grippers directory",
             source="upstream_code", ref=f"{CONDA_SCRIPT}:6"),
        Fact("The binary gripper variant maps a continuous action to binary output: -1 means open and 1 means closed",
             source="upstream_code", ref=f"{GRIPPER_PY}:59"),
        Fact("The binary gripper variant clips current_action to -1.0 to 1.0", source="upstream_code",
             ref=f"{GRIPPER_PY}:68"),
        Fact("TabletopEnv is located in environment/tabletop_env.py and inherits robosuite's SingleArmEnv",
             source="vendor_doc", ref=f"{ENV_DOC}:15"),
        Fact("The documented primitive actions of the environment include open_gripper and close_gripper",
             source="vendor_doc", ref=f"{ENV_DOC}:30-31"),
        Fact("The environment starts the gripper at current_action [-1.0] (open)", source="upstream_code",
             ref=f"{ENV_PY}:311"),
        Fact("The environment reports the gripper closed when current_action exceeds 0.9", source="upstream_code",
             ref=f"{ENV_PY}:373"),
        Fact("MuBlE is a MuJoCo and Blender simulation environment for task planning in robotics manipulation",
             source="vendor_doc", ref="README.md:1"),
    ]
    safe_state = ("the simulation halts: the driver latches the e-stop and refuses further step and reset calls "
                  "until mhs.safety.reset clears it; the joint state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:robotiq_gripper_85_model",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and cap.world.reset.v1 restores the model defaults, so a run repeats on the same engine "
                     "but no seed selects a different state; the stand-in integrates its own placeholder motion",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model text for the joint "
            "count, the actuator count and the control ranges but integrates a placeholder first-order motion of each "
            "actuated joint toward its control target, so contacts, tendon coupling and actuator dynamics are not "
            "MuJoCo's",
            "the stand-in loads no mesh or texture and resolves no contact, equality or tendon constraint; the two "
            "fixed tendons of the model are not applied",
            "the model's <asset> block names STL meshes under meshes/robotiq_85_gripper/ that are not present in the "
            "clone, so the real mujoco backend can resolve them only from an installed robosuite asset tree; the fake "
            "needs none of them",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no rendering is offered and no physical gripper is modelled; nothing was validated against the Robotiq "
            "2F-85 hardware",
        ],
    }
