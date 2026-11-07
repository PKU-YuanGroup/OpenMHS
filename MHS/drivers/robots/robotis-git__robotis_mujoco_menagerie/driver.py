"""OpenMHS driver for gh.robotis-git/robotis_mujoco_menagerie: the ROBOTIS AI Worker FFW-BG2 MuJoCo scene.

A :class:`MujocoDriver` is configuration only: ``model_path`` names the card's main model (``models[0]``,
``robotis_ffw/scene_ffw_bg2.xml``) and the bridge derives the whole contract from the model it loads.  The scene
includes ``ffw_bg2.xml``.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is
checked against the model's ``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs
``ticks`` times.  The 19 position actuators have ``inheritrange="1"``, so their control ranges are the ranges of the
joints they drive (one lift slider, two head joints, seven joints per arm and one gripper actuator per hand).
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The model file is read
from the read-only clone at the pinned commit (it is never copied into this package and never imported).  MuJoCo is
not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).
It parses the same scene for the model shape but integrates a placeholder motion, not MuJoCo's physics; the
fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same file; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "robotis_ffw/scene_ffw_bg2.xml"
ROBOT = "robotis_ffw/ffw_bg2.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/robotis-git/robotis_mujoco_menagerie/" + MODEL


class FfwBg2(MujocoDriver):
    device_id = "robotis-ffw-bg2"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "ROBOTIS AI Worker FFW-BG2 (MuJoCo model)"
    vendor, model = "ROBOTIS", "FFW-BG2"
    tags = ["robotis", "ffw-bg2", "ai-worker", "dual-arm", "mobile-manipulator", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is a collection of models for the MuJoCo physics engine from ROBOTIS",
             source="vendor_doc", ref="README.md:2"),
        Fact("The models are designed for use with the MuJoCo physics engine", source="vendor_doc",
             ref="README.md:32"),
        Fact("The card's main model is the MJCF scene robotis_ffw/scene_ffw_bg2.xml, whose root element is "
             "<mujoco model=\"ffw_bg2 scene\">", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The scene includes the robot model ffw_bg2.xml", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The robot model's root element is <mujoco model=\"ffw_bg2\">", source="upstream_code",
             ref=f"{ROBOT}:1"),
        Fact("The model compiles with angles in radians and automatic limits", source="upstream_code",
             ref=f"{ROBOT}:2"),
        Fact("The <option> element sets integrator implicitfast, cone elliptic and impratio 10, and sets no "
             "timestep", source="upstream_code", ref=f"{ROBOT}:4"),
        Fact("The robot's first body is arm_base_link and its first joint is lift_joint", source="upstream_code",
             ref=f"{ROBOT}:142-144"),
        Fact("The model has 19 position actuators: one lift slider, two head joints, seven joints per arm and one "
             "gripper actuator per hand", source="upstream_code", ref=f"{ROBOT}:323-348"),
        Fact("Every position actuator declares inheritrange=\"1\" and names the joint it drives",
             source="upstream_code", ref=f"{ROBOT}:325-348"),
        Fact("The lift joint is a slide joint with range -0.5 to 0.0", source="upstream_code",
             ref=f"{ROBOT}:38-41"),
        Fact("The head joint ranges are -0.2317 to 0.6951 and -0.35 to 0.35", source="upstream_code",
             ref=f"{ROBOT}:49-52"),
        Fact("The left arm joint ranges are -3.14 to 3.14, 0 to 3.14, -3.14 to 3.14, -2.9361 to 1.0786, -3.14 to "
             "3.14, -1.57 to 1.57 and -1.8201 to 1.5804", source="upstream_code", ref=f"{ROBOT}:60-109"),
        Fact("The right arm joint ranges are -3.14 to 3.14, -3.14 to 0, -3.14 to 3.14, -2.9361 to 1.0786, -3.14 "
             "to 3.14, -1.57 to 1.57 and -1.5804 to 1.8201", source="upstream_code", ref=f"{ROBOT}:66-109"),
        Fact("The gripper joint ranges are 0 to 1.1, -1.1 to 0 and 0 to 1.1", source="upstream_code",
             ref=f"{ROBOT}:117-123"),
        Fact("The gripper fingers are coupled to the first gripper joint by six equality constraints with "
             "polycoef 0 -1 0 0 0 or 0 1 0 0 0", source="upstream_code", ref=f"{ROBOT}:375-383"),
        Fact("The model references 23 STL mesh files with scale 0.001", source="upstream_code",
             ref=f"{ROBOT}:10-32"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:ffw_bg2",
        "fidelity_level": "F1",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its include "
            "for the joint dimensions and per-actuator control ranges, but integrates a placeholder first-order "
            "motion of each actuated joint toward its control target, so trajectories, contacts, friction and "
            "actuator dynamics are not MuJoCo's",
            "no mesh or texture of the asset directory is loaded and no contact, equality, tendon or actuator "
            "constraint is resolved by the stand-in; the six gripper equality constraints are not applied",
            "the model's <option> sets no timestep (robotis_ffw/ffw_bg2.xml:4); the stand-in uses a 2 ms "
            "placeholder, and MuJoCo's library default was not read or verified here",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "only the card's models[0] scene is served; the other FFW scenes, OMX, OMY, OP3, OpenMANIPULATOR-X and "
            "TurtleBot3 models in the repository are not served by this package",
            "no physical robot is modelled and nothing was validated against the FFW-BG2 hardware",
        ],
    }
