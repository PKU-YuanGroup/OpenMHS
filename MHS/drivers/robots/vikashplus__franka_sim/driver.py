"""OpenMHS driver for gh.vikashplus/franka_sim: the bimanual Franka Panda MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``bi-franka_panda.xml``: a fixed torso with a left arm from assets/chain0.xml and a right arm from
assets/chain1.xml (bi-franka_panda.xml:23-35), 18 one-DOF joints in all and 16 position actuators.  The bridge loads
the model with the MuJoCo engine, derives ``cap.world.step.v1``'s ``action.ctrl`` from each actuator's
``ctrlrange``, writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves ``cap.world.reset.v1`` with
``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): it advances a model, drives no physical Franka and has no hardware backend.  The
model is read from the read-only clone at the pinned commit and is neither copied into this package nor imported.
MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py), which reads the model shape from the same MJCF text but integrates a placeholder motion
instead of the engine's physics; the fidelity ``gaps`` below state every difference.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not
run here.

Every Fact cites a line of the clone at commit b54d271388cf9b179d3fb6cff7a430040afca33f.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "bi-franka_panda.xml"
MODEL_PATH = "../../../../robots/vikashplus/franka_sim/" + MODEL
SCENE = "bi-franka_panda.xml"
CHAIN0 = "assets/chain0.xml"
CHAIN1 = "assets/chain1.xml"
ASSETS = "assets/assets.xml"
ACTUATOR0 = "assets/actuator0.xml"
ACTUATOR1 = "assets/actuator1.xml"
README = "README.md"


class FrankaSim(MujocoDriver):
    device_id = "franka-sim"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Franka Panda bimanual MuJoCo scene"
    vendor, model = "Vikash Kumar", "Franka Panda (bi-franka_panda v200)"
    tags = ["arm", "bimanual", "franka", "manipulator", "mujoco", "panda", "robot", "simulation"]
    facts = [
        Fact("The repository is a collection of MuJoCo models of the Franka Panda ('Franka panda mujoco models')",
             source="vendor_doc", ref=f"{README}:2"),
        Fact("The README says the models adjust the default joint positions, with an offset of -pi/2 on joint6 and "
             "-pi/4 on joint7", source="vendor_doc", ref=f"{README}:10"),
        Fact("The README says the joint4 range was reduced to avoid the gimbal-lock configuration",
             source="vendor_doc", ref=f"{README}:11"),
        Fact("The README says the joint limits were adjusted to avoid hitting the limits during operation with the "
             "hardware", source="vendor_doc", ref=f"{README}:12"),
        Fact("The README credits the robot meshes and specs to franka_ros and the Franka control_parameters page",
             source="vendor_doc", ref=f"{README}:17-21"),
        Fact("The card's first model is the MJCF scene whose root element is "
             "'<mujoco model=\"bi-franka_panda v200\">'", source="upstream_code", ref=f"{SCENE}:1"),
        Fact("The bi-franka scene includes assets/basic_scene.xml, assets/assets.xml and assets/gripper_assets.xml, "
             "and sets an empty compiler meshdir", source="upstream_code", ref=f"{SCENE}:10-13"),
        Fact("The bi-franka scene is a torso with a leftarm that includes assets/chain0.xml and a rightarm that "
             "includes assets/chain1.xml", source="upstream_code", ref=f"{SCENE}:23-35"),
        Fact("The bi-franka scene includes the left arm actuator set assets/actuator0.xml and the two-arm actuator "
             "set assets/actuator1.xml", source="upstream_code", ref=f"{SCENE}:41-42"),
        Fact("The compiler angle is radian, so the joint ranges of the model are radians", source="upstream_code",
             ref=f"{ASSETS}:10"),
        Fact("The model sets an explicit option timestep of 0.002 s", source="upstream_code", ref=f"{ASSETS}:12"),
        Fact("The panda default class gives its position actuators ctrllimited true and forcelimited true, and the "
             "joint default is limited true with axis 0 0 1", source="upstream_code", ref=f"{ASSETS}:42-44"),
        Fact("The finger default class gives its joints damping 100 and armature 5, and its position actuators a "
             "user tuple", source="upstream_code", ref=f"{ASSETS}:61-64"),
        Fact("The left arm is seven hinge joints with ranges -2.8973 to 2.8973 (panda0_joint1), -1.7628 to 1.7628 "
             "(panda0_joint2), -2.8973 to 2.8973 (panda0_joint3), -3.0718 to -0.4 (panda0_joint4), -2.8973 to "
             "2.8973 (panda0_joint5), -1.6573 to 2.1127 (panda0_joint6) and -2.8973 to 2.8973 (panda0_joint7)",
             source="upstream_code", ref=f"{CHAIN0}:16-46"),
        Fact("The right arm is seven hinge joints with ranges -2.9671 to 2.9671 (panda1_joint1), -1.8326 to 1.8326 "
             "(panda1_joint2), -2.9671 to 2.9671 (panda1_joint3), -3.0718 to -0.4 (panda1_joint4), -2.9671 to "
             "2.9671 (panda1_joint5), -1.6573 to 2.1127 (panda1_joint6) and -2.8973 to 2.8973 (panda1_joint7)",
             source="upstream_code", ref=f"{CHAIN1}:14-46"),
        Fact("panda0_finger_joint1 and panda0_finger_joint2 are slide joints with range 0 to 0.04 m",
             source="upstream_code", ref=f"{CHAIN0}:62-88"),
        Fact("panda1_finger_joint1 and panda1_finger_joint2 are slide joints with range 0 to 0.04 m",
             source="upstream_code", ref=f"{CHAIN1}:60-84"),
        Fact("The left arm has seven position actuators, panda0_joint1 to panda0_joint7, with ctrlranges -2.9671 to "
             "2.9671, -1.8326 to 1.8326, -2.9671 to 2.9671, -3.1416 to 0.0, -2.9671 to 2.9671, -1.66 to 2.1817 and "
             "-2.9671 to 2.9671", source="upstream_code", ref=f"{ACTUATOR0}:11-17"),
        Fact("The right arm has seven position actuators, panda1_joint1 to panda1_joint7, with ctrlranges -2.9671 to "
             "2.9671, -1.8326 to 1.8326, -2.9671 to 2.9671, -3.1416 to 0.0, -2.9671 to 2.9671, -0.0873 to 3.8223 "
             "and -0.0873 to 3.8223", source="upstream_code", ref=f"{ACTUATOR1}:10-16"),
        Fact("The right arm's two finger joints have position actuators panda1_leftfinger and panda1_rightfinger "
             "with ctrlrange 0 to 0.04", source="upstream_code", ref=f"{ACTUATOR1}:17-18"),
        Fact("The model declares a Franka_wrist_cam camera and an end_effector site on panda0_link7",
             source="upstream_code", ref=f"{CHAIN0}:52-53"),
        Fact("The model's mesh assets are STL files under meshes/collision and meshes/visual, with a 1.01 scale on "
             "the dark visual meshes", source="upstream_code", ref=f"{ASSETS}:16-38"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:bi-franka_panda v200",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the bridge takes no "
                     "seed input and cap.world.reset.v1 restores the model defaults.  The package's fake backend "
                     "is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served scene for "
            "18 one-DOF joints, 16 actuator ctrlranges and the 2 ms time step, then moves each actuated joint "
            "toward its control value; it computes no inertia, torque, contact, equality or actuator dynamics, so "
            "no trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact: the STL meshes of assets/assets.xml:16-38 "
            "are not read, and no collision, friction or contact force is modelled",
            "the bridge bounds ctrl by each actuator's ctrlrange, and several ctrlranges are wider than the joint "
            "range (for example panda0_joint1 at assets/actuator0.xml:11 against assets/chain0.xml:16); the fake "
            "does not enforce joint limits, while MuJoCo stops a joint at its range",
            "the left gripper has no actuator: assets/actuator0.xml declares only the seven left arm actuators, so "
            "the two left finger joints (assets/chain0.xml:62-88) are unactuated; only the right finger joints have "
            "the two position actuators of assets/actuator1.xml:17-18",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine; the sim path that imports the real mujoco was not run",
            "snapshot and restore use the stand-in's own integration state (time, qpos, qvel, ctrl), not "
            "mjSTATE_INTEGRATION of the engine, so a snapshot is exact only inside the stand-in",
            "no rendering, cameras or sensor publication: the Franka_wrist_cam camera and the joint sensors of "
            "assets/assets.xml are not exposed, and only the bridge's time, qpos, qvel and ctrl state is published",
            "no physical Franka robot is modelled and nothing was validated against the hardware",
        ],
    }
