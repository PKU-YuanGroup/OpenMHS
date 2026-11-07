"""OpenMHS driver for gh.google-deepmind/mujoco_menagerie: the AgileX PiPER model (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene (the card's ``models[0]``,
``agilex_piper/scene.xml``) and the bridge derives the whole contract from the model it loads.  The step action is
``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (seven position actuators); the world state
is the integration state of the model (``time``, ``qpos``, ``qvel``, ``ctrl``) plus the tick count, and
``cap.world.reset.v1`` restores the model defaults.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The gate cannot install
MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same model file for the model shape (joint count, actuator count, per-actuator control ranges) but its integration is
a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit 0059d4335f8156206f63a35662313385f7ad6d74.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "agilex_piper/scene.xml"
MODEL_PATH = "../../../../robots/google-deepmind/mujoco_menagerie/" + MODEL
SCENE = "agilex_piper/scene.xml"
PIPER = "agilex_piper/piper.xml"
README = "agilex_piper/README.md"


class MenageriePiper(MujocoDriver):
    device_id = "menagerie-piper"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "AgileX PiPER (MuJoCo Menagerie)"
    vendor, model = "Google DeepMind (MuJoCo Menagerie)", "AgileX PiPER"
    tags = ["agilex", "arm", "manipulator", "menagerie", "mujoco", "piper", "robot", "simulation"]
    facts = [
        Fact("The package's model is the MJCF scene agilex_piper/scene.xml, whose root element is "
             "'<mujoco model=\"piper_scene\">' and which includes piper.xml", source="upstream_code",
             ref=f"{SCENE}:1-2"),
        Fact("piper.xml declares '<compiler angle=\"radian\" meshdir=\"assets\"/>', so the joint ranges of the model "
             "are radians and its meshes are resolved from assets/", source="upstream_code", ref=f"{PIPER}:2"),
        Fact("The model uses the implicitfast integrator with an elliptic friction cone and impratio 10, and its "
             "<option> element sets no timestep", source="upstream_code", ref=f"{PIPER}:4"),
        Fact("The piper default class sets frictionloss 0.3 and armature 0.005 on its joints and gives its position "
             "actuators inheritrange 1 and forcerange -100 to 100", source="upstream_code", ref=f"{PIPER}:8-9"),
        Fact("The finger default class inherits the piper class and overrides the joints to type slide with "
             "frictionloss 0 and the position actuators to forcerange -10 to 10", source="upstream_code",
             ref=f"{PIPER}:10-13"),
        Fact("The body base_link sets childclass piper, so the joints and geoms below it use the piper defaults",
             source="upstream_code", ref=f"{PIPER}:120"),
        Fact("joint1 is a hinge with range -2.618 to 2.618 rad", source="upstream_code", ref=f"{PIPER}:128"),
        Fact("joint2 is a hinge with range 0 to 3.14 rad", source="upstream_code", ref=f"{PIPER}:134"),
        Fact("joint3 is a hinge with range -2.697 to 0 rad", source="upstream_code", ref=f"{PIPER}:171"),
        Fact("joint4 is a hinge with range -1.832 to 1.832 rad", source="upstream_code", ref=f"{PIPER}:204"),
        Fact("joint5 is a hinge with range -1.22 to 1.22 rad", source="upstream_code", ref=f"{PIPER}:214"),
        Fact("joint6 is a hinge with range -3.14 to 3.14 rad", source="upstream_code", ref=f"{PIPER}:226"),
        Fact("joint7 is a slide joint with range 0 to 0.035 m", source="upstream_code", ref=f"{PIPER}:232"),
        Fact("joint8 is a slide joint with range -0.035 to 0 m", source="upstream_code", ref=f"{PIPER}:240"),
        Fact("The model has seven position actuators: joint1 to joint6, and a gripper actuator on joint7",
             source="upstream_code", ref=f"{PIPER}:262-269"),
        Fact("The gripper actuator of joint7 has kp 40 and kv 5; joint1 to joint3 have kp 80 and kv 5, joint4 has "
             "kp 40 and kv 5, and joint5 and joint6 have kp 10 and kv 1.5", source="upstream_code",
             ref=f"{PIPER}:263-269"),
        Fact("joint7 and joint8 are coupled by an equality constraint with polycoef '0 -1 0 0 0', so the right "
             "finger mimics the left", source="upstream_code", ref=f"{PIPER}:258-259"),
        Fact("The model has a home keyframe with qpos '0 1.57 -1.3485 0 0 0 0 0' and ctrl '0 1.57 -1.3485 0 0 0 0'",
             source="upstream_code", ref=f"{PIPER}:272-273"),
        Fact("The package's description is a simplified MJCF of the AgileX PiPER, derived from the publicly "
             "available PiPER ROS model", source="vendor_doc", ref=f"{README}:12"),
        Fact("The model adds position controlled actuators", source="vendor_doc", ref=f"{README}:29"),
        Fact("The scene adds a textured groundplane, a skybox and haze", source="vendor_doc", ref=f"{README}:31"),
        Fact("The model requires MuJoCo 2.3.4 or later", source="vendor_doc", ref=f"{README}:4"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:piper_scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input and cap.world.reset.v1 restores the model defaults, so a run repeats exactly on the "
                     "same engine but no seed selects a different state",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control ranges and the joint count but integrates a placeholder first-order motion of each "
            "actuated joint toward its control target, so trajectories, contacts and actuator dynamics are not "
            "MuJoCo's",
            "no mesh or texture of the asset directory is loaded and no contact, equality or tendon constraint is "
            "resolved by the stand-in; the joint7/joint8 finger equality of the model is not applied",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering is offered and no physical PiPER robot is modelled; nothing was validated against the "
            "AgileX hardware",
        ],
    }
