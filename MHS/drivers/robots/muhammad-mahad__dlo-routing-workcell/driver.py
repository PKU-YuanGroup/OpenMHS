"""OpenMHS driver for gh.muhammad-mahad/dlo-routing-workcell: the dual-arm DLO routing workcell MJCF scene.

A MujocoDriver is configuration only: ``model_path`` names the card's model (``models[0]``, scene.xml) and the bridge
derives the whole contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{ctrl}``, one control value per actuator, bounded by the model's ``actuator_ctrlrange``; the state is the model's
integration state (``time``, ``qpos``, ``qvel``) plus the control vector and tick count, and ``cap.world.reset.v1``
restores the model defaults (``mj_resetData`` + ``mj_forward``).  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate cannot install MuJoCo (no network, no pip), and this scene additionally needs a patched MuJoCo 3.3.2 build
with the Chen ``wire`` plugin (README.md:93); the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the model shape (actuator count, control ranges, qpos/qvel dimensions)
but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run
here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of that clone at commit 2c4c322ad14edf521deceba3048e3844e0bf61d5.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/muhammad-mahad/dlo-routing-workcell/scene.xml"
SCENE = "scene.xml"
README = "README.md"


class DloRoutingWorkcell(MujocoDriver):
    device_id = "dlo-routing-workcell"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Dual-arm DLO cable-routing workcell (MuJoCo scene)"
    vendor, model = "muhammad-mahad", "Dual-arm cable-routing workcell"
    tags = ["mujoco", "simulation", "deformable-linear-object", "cable-routing", "dual-arm", "franka-panda"]
    facts = [
        Fact("The card's main model is the MJCF scene scene.xml, whose root element is "
             "'<mujoco model=\"dlo_workcell_template\">'", source="upstream_code", ref=f"{SCENE}:16"),
        Fact("The scene compiler reads angles in radians and resolves mesh files under meshes/", source="upstream_code",
             ref=f"{SCENE}:17"),
        Fact("The scene's <option> element sets impratio, the implicitfast integrator and the elliptic cone, and sets "
             "no timestep", source="upstream_code", ref=f"{SCENE}:19"),
        Fact("The actuator section lists 19 actuators: paL_actuator1 through paL_actuator8, paR_actuator1 through "
             "paR_actuator8, panda_L_rail_pos, panda_R_rail_pos and slider_pos", source="upstream_code",
             ref=f"{SCENE}:1470-1489"),
        Fact("The Panda actuator default class sets ctrlrange -2.8973 to 2.8973 and forcerange -87 to 87",
             source="upstream_code", ref=f"{SCENE}:48-52"),
        Fact("The joint2, joint4, joint6 and gripper actuators of each arm override the default control range with "
             "-1.7628 to 1.7628, -3.0718 to -0.0698, -0.0175 to 3.7525 and 0 to 255", source="upstream_code",
             ref=f"{SCENE}:1472-1486"),
        Fact("Each arm has seven arm-joint position servos plus one gripper actuator, and each wrist carries a 6-axis "
             "force/torque sensor", source="vendor_doc", ref=f"{README}:173-176"),
        Fact("The two rail actuators accept ctrlrange -0.6 to 0.6 and the obstacle slider accepts -0.4 to 0.4",
             source="upstream_code", ref=f"{SCENE}:1487-1489"),
        Fact("The cable is a capsule chain named cableB_first to cableB_last: 120 segments, 3.5 m total, about 29 mm "
             "per segment", source="vendor_doc", ref=f"{README}:379"),
        Fact("The cable's first body is held to the tension anchor by an equality connect constraint named "
             "cable_to_tension_anchor", source="upstream_code", ref=f"{SCENE}:1456"),
        Fact("The scene declares the mujoco.elasticity.wire plugin with an instance named compositecable",
             source="upstream_code", ref=f"{SCENE}:113-119"),
        Fact("The Chen wire DER cable plugin requires a patched MuJoCo 3.3.2 build, and stock MuJoCo wheels do not "
             "include these plugins", source="vendor_doc", ref=f"{README}:93"),
        Fact("The wire plugin build recipe is documented for a patched MuJoCo 3.3.2 and is not part of a stock wheel",
             source="vendor_doc", ref=f"{README}:93"),
        Fact("The Franka Panda model and the clip and peg STL meshes are fetched, not shipped with the repository",
             source="vendor_doc", ref=f"{README}:121-122"),
        Fact("Two Franka Emika Panda arms ride linear rails, one on each long edge of the board, and each rail "
             "translates along the board's long axis by +-0.60 m", source="vendor_doc", ref=f"{README}:153-166"),
        Fact("Force and torque sensors are registered at the left and right wrist sites ft_L_site and ft_R_site",
             source="upstream_code", ref=f"{SCENE}:1493-1496"),
        Fact("The model stores the home and pre_route keyframes with one qpos vector each", source="upstream_code",
             ref=f"{SCENE}:1499-1501"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the notes and gaps below are this package's.
    fidelity = {
        "engine": "mujoco:dlo_workcell_template",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "and a reset restores the model defaults, so a run repeats exactly on the same engine but no "
                     "seed selects a different one",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses scene.xml for the actuator "
            "count, the per-actuator ctrlrange and the joint dimensions, but integrates a placeholder first-order "
            "motion of each actuated scalar joint toward its control target, so trajectories, contacts and actuator "
            "dynamics are not MuJoCo's",
            "the stand-in loads no mesh or texture and resolves no contact, equality, tendon or plugin constraint; the "
            "118 ball joints of the wire cable stay at zero and the finger equality is not applied",
            "the scene needs the Chen wire DER plugin and a patched MuJoCo 3.3.2 build (README.md:93), and the Panda "
            "model and clip and peg STLs are fetched, not shipped (README.md:121-122); the real engine path was not "
            "run here",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no physical routing cell is modelled and nothing was validated against hardware",
        ],
    }
