"""OpenMHS driver for gh.vikashplus/unitree_sim: the Unitree A1 quadruped as a MuJoCo model (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene of the card (``models[0]``, ``a1.xml``)
and the bridge derives the whole contract from the model it loads.  The step action is ``data.ctrl``, bounded per
actuator by the model's ``actuator_ctrlrange`` (12 position actuators, one per hinge joint), and the state is the
integration state of the model (``time_ms``, ``qpos``, ``qvel``, ``ctrl``) plus the tick count;
``cap.world.reset.v1`` resets the data to the model defaults (``mj_resetData``, which restores ``qpos0``).

The device is simulated (R0): there is no hardware backend and no path to a physical robot.  The gate cannot install
MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same model file for the model shape (12 actuators, their control ranges, 19 qpos and 18 qvel values of the floating
base and the 12 hinges) but its integration is a placeholder, not MuJoCo's physics; the ``fidelity`` gaps say so.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of it at commit 21b5524e7c5586565de5e789e94bb69efd36db69.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "a1.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/vikashplus/unitree_sim/" + MODEL


class UnitreeA1(MujocoDriver):
    device_id = "unitree_a1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree A1 quadruped (MuJoCo model)"
    vendor, model = "Vikash Kumar", "Unitree A1"
    tags = ["unitree", "a1", "quadruped", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository describes itself as 'MuJoCo models for Unitree Robots'", source="vendor_doc",
             ref="README.md:2"),
        Fact("The card's main model is the MJCF scene a1.xml, whose root element is '<mujoco model=\"unitree_a1\">'",
             source="upstream_code", ref="a1.xml:10"),
        Fact("The model uses radian angles (<compiler angle=\"radian\"/>) and sets size njmax 500 and nconmax 100",
             source="upstream_code", ref="a1.xml:11-12"),
        Fact("The model header states that it is under the Apache License, Version 2.0", source="upstream_code",
             ref="a1.xml:7"),
        Fact("The torso body a1_torso has a free joint (<freejoint/>), so the model has a floating base",
             source="upstream_code", ref="a1.xml:36-42"),
        Fact("The robot has 12 hinge joints, three per leg (hip, thigh and calf): FR_hip, FR_thigh, FR_calf, then "
             "the same for FL, RR and RL", source="upstream_code", ref="a1.xml:43-123"),
        Fact("The joint ranges are hip -0.802851 to 0.802851, thigh -1.0472 to 4.18879 and calf -2.69653 to "
             "-0.916298", source="upstream_code", ref="a1.xml:45-55"),
        Fact("The model has 12 position actuators, one per hinge joint, with kp 60 on hip and thigh and kp 93.3 on "
             "calf", source="upstream_code", ref="a1.xml:126-139"),
        Fact("Every actuator sets ctrlrange to its joint range", source="upstream_code",
             ref="a1.xml:127-138"),
        Fact("The unitree default class sets ctrllimited true for position actuators", source="upstream_code",
             ref="a1.xml:26"),
        Fact("a1.xml includes basic_scene.xml", source="upstream_code", ref="a1.xml:33"),
        Fact("basic_scene.xml has a <mujocoinclude> root", source="upstream_code", ref="basic_scene.xml:1"),
        Fact("basic_scene.xml defines a ground plane geom of size 5 5 10", source="upstream_code",
             ref="basic_scene.xml:20"),
        Fact("The five mesh assets are STL files under meshes/a1", source="upstream_code", ref="a1.xml:14-18"),
        Fact("The repository also contains aliengo.xml, whose root is '<mujoco model=\"unitree_aliengo\">'",
             source="upstream_code", ref="aliengo.xml:9"),
        Fact("The repository also contains laikago.xml, whose root is '<mujoco model=\"unitree_laikago\">'",
             source="upstream_code", ref="laikago.xml:9"),
    ]
    safe_state = ("the simulation holds its state: after an e-stop no step or reset runs until mhs.safety.reset "
                  "clears the latch; the last integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:unitree_a1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge's reset "
                     "restores the model defaults and takes no seed, so a run repeats exactly on the same engine but "
                     "no seed selects a different start state",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control ranges, the joint dimensions and the free-joint start pose, but it integrates a "
            "placeholder first-order motion of each actuated hinge and resolves no contact, actuator, equality or "
            "tendon dynamics",
            "the free base is not integrated by the stand-in: gravity, the ground plane and contacts do not move it",
            "no mesh or texture of meshes/a1 is loaded and no contact geometry is resolved",
            "the model sets no <option timestep>, so the stand-in uses MuJoCo's library default 2 ms as a placeholder; "
            "a real MuJoCo load would use that same default",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the package serves the card's models[0] a1.xml only; aliengo.xml and laikago.xml are not served",
            "no physical Unitree A1 is modelled and nothing was validated against the hardware",
        ],
    }
