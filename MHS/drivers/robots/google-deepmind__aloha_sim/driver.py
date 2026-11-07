"""OpenMHS driver for gh.google-deepmind/aloha_sim: the ALOHA bimanual arm as a MuJoCo model (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene of the card (``models[0]``,
``aloha_sim/assets/aloha/aloha_pbr.xml``) and the bridge derives the whole contract from the model it loads.  The
step action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (14 position actuators,
seven per arm), and the state is the integration state of the model (``time``, ``qpos``, ``qvel``) plus the tick
count; ``cap.world.reset.v1`` resets the data to the model defaults.

The device is simulated (R0): there is no hardware backend.  The gate cannot install MuJoCo where it runs, so the
``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the same model file for the model
shape (actuator count, control ranges, joint count) but its integration is a placeholder, not MuJoCo's physics; the
driver's fidelity ``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of it at commit d02904607cca1bf6dfb72f30b522506ac7ca0f91.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "aloha_sim/assets/aloha/aloha_pbr.xml"
ACTUATORS = "aloha_sim/assets/aloha/joint_position_actuators.xml"
SCENE = "aloha_sim/assets/aloha/scene_pbr.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/google-deepmind/aloha_sim/" + MODEL


class Aloha(MujocoDriver):
    device_id = "aloha"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "ALOHA bimanual arm (MuJoCo model)"
    vendor, model = "Google DeepMind", "ALOHA bimanual arm"
    tags = ["aloha", "bimanual", "manipulation", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The card's main model is the MJCF scene aloha_pbr.xml, whose root element is '<mujoco model=\"aloha\">'",
             source="upstream_code", ref=f"{MODEL}:17"),
        Fact("The scene_pbr.xml scene includes aloha_pbr.xml", source="upstream_code", ref=f"{SCENE}:26"),
        Fact("aloha_pbr.xml includes the actuator definitions of joint_position_actuators.xml", source="upstream_code",
             ref=f"{MODEL}:304"),
        Fact("The model has 14 position actuators, seven per arm: waist, shoulder, elbow, forearm_roll, wrist_angle, "
             "wrist_rotate and finger", source="upstream_code", ref=f"{ACTUATORS}:19-33"),
        Fact("The control range of an actuator comes from the default class of its element: waist, forearm_roll and "
             "wrist_rotate +-3.14158, shoulder -1.85005 to 1.25664, elbow -1.76278 to 1.6057, wrist_angle -1.8675 to "
             "2.23402, finger 0.002 to 0.037", source="upstream_code", ref=f"{MODEL}:50-96"),
        Fact("The finger control range 0.002 to 0.037 m is described as the limits the real robot enforces in "
             "software on its gripper travel", source="upstream_code", ref=f"{MODEL}:75-96"),
        Fact("The model sets no option timestep: its <option> element carries only cone and impratio",
             source="upstream_code", ref=f"{MODEL}:20"),
        Fact("The two fingers of one gripper are coupled by an equality constraint", source="upstream_code",
             ref=f"{MODEL}:299-301"),
        Fact("The model has a neutral_pose keyframe with one qpos value per joint and one ctrl value per actuator",
             source="upstream_code", ref=f"{ACTUATORS}:36-43"),
        Fact("The 16 qpos values are the eight joints of each arm (six hinges and two finger slides); the 14 ctrl "
             "values are the seven actuators of each arm", source="upstream_code", ref=f"{ACTUATORS}:37-42"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:aloha",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input and a reset restores the model defaults, so a run repeats exactly on the same "
                     "engine but no seed selects a different one",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control ranges and the joint count but integrates a placeholder first-order motion of each "
            "actuated joint toward its control target, so trajectories, contacts and actuator dynamics are not "
            "MuJoCo's",
            "no mesh or texture of the asset directory is loaded and no contact, equality or tendon constraint is "
            "resolved by the stand-in; the finger equality of the model is not applied",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no physical robot is modelled and nothing was validated against the ALOHA hardware",
        ],
    }
