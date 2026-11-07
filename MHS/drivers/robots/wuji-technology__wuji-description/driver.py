"""OpenMHS driver for gh.wuji-technology/wuji-description: the left Wuji Hand with soft pad as a MuJoCo model.

The upstream repository is a robot *description* package: it ships URDF, MJCF and USD model assets plus a ROS2
``display.launch.py`` that starts only ``robot_state_publisher``, ``joint_state_publisher_gui`` and ``rviz2``.
It declares no ROS topic, service or action that would command the hand, so the card's RosDriver helper cannot
express an interface here.  The concrete interface the repository does ship is a MuJoCo model with position
actuators (``hand/body-with-soft/mjcf/left.xml``), which ``MujocoDriver`` serves as a simulated world: the model's
joints and actuator control ranges are the contract, and ``cap.world.step.v1`` / ``cap.world.reset.v1`` are the
operations.  This is a deliberate deviation from the card's family/helper, recorded in RESULT.json.

The package serves the card's ``models[0]`` only.  It reads that MJCF and its mesh references from the read-only
clone at the pinned commit; it copies neither the model nor the meshes.  The model is simulated (R0): no hardware
backend, no physical motion and no operator-required limit.  The bridge derives one ``action.ctrl`` interval per
position actuator from the model's own ``ctrlrange``, so this package declares no Limit of its own.

MuJoCo is not installed and cannot be installed where the acceptance gate runs, so ``backends["fake"]`` names the
package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the joint dimensions, actuator list and
actuator control ranges but integrates a placeholder first-order motion; it is not MuJoCo and its trajectories are
not MuJoCo results.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and
loads the same file; that path was not run here.  This package is model-authored and unreviewed: the fake backend is
checked only for contract evidence.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "hand/body-with-soft/mjcf/left.xml"
MODEL_PATH = "../../../../robots/wuji-technology/wuji-description/" + MODEL
README = "README.md"
PACKAGE_XML = "hand/body/package.xml"
CMAKE = "hand/body/CMakeLists.txt"
LAUNCH = "hand/body/launch/display.launch.py"


class WujiHandLeft(MujocoDriver):
    device_id = "wujihand-left"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Wuji Hand left with soft pad (MuJoCo)"
    vendor, model = "Wuji Technology", "Wuji Hand"
    tags = ["hand", "mujoco", "robot", "simulation", "wuji", "dexterous"]
    facts = [
        Fact("The card's model is the MJCF robot model hand/body-with-soft/mjcf/left.xml, whose root element is "
             "<mujoco model=\"wujihand-left\">", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model declares '<compiler angle=\"radian\" />'",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model sets '<option jacobian=\"sparse\" integrator=\"RK4\" timestep=\"0.002\" solver=\"Newton\" "
             "iterations=\"50\" tolerance=\"1e-10\" />' and a default joint armature 0.0002 with damping 0.0",
             source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The model's worldbody root is the body left_palm_link", source="upstream_code", ref=f"{MODEL}:35"),
        Fact("The root body left_palm_link declares an inertial and two mesh geoms and no joint before its first "
             "child body left_finger1_link1", source="upstream_code", ref=f"{MODEL}:35-37"),
        Fact("The first finger joint left_finger1_joint1 declares no type attribute, axis 0 1 0, range 0.0475 1.6033, "
             "actuatorfrcrange -0.4452 0.4452 and armature 0.0005", source="upstream_code", ref=f"{MODEL}:39"),
        Fact("The last finger joint left_finger5_joint4 declares range -0.4683 1.5735",
             source="upstream_code", ref=f"{MODEL}:160"),
        Fact("The actuator section declares 20 position actuators, one per finger joint, each with kp, kv, ctrlrange "
             "and forcerange; the first, left_finger1_joint1_actuator, states ctrlrange 0.0475 1.6033",
             source="upstream_code", ref=f"{MODEL}:170-191"),
        Fact("The last position actuator, left_finger5_joint4_actuator, states ctrlrange -0.4683 1.5735",
             source="upstream_code", ref=f"{MODEL}:190"),
        Fact("The repository describes itself as a 'Robot model description package for the Wuji Hand and related "
             "accessories' providing URDF, MuJoCo (MJCF) and USD assets for simulation and visualization",
             source="vendor_doc", ref=f"{README}:5"),
        Fact("The README describes hand/body-with-soft/ as the hand-body variant with a soft pad fixed to the thumb",
             source="vendor_doc", ref=f"{README}:120"),
        Fact("The README's MuJoCo command loads a hand/body-with-soft model with 'python -m mujoco.viewer "
             "--mjcf=hand/body-with-soft/mjcf/right.xml'", source="vendor_doc", ref=f"{README}:124"),
        Fact("The ROS2 package wuji_description is described as a robot model description package with URDF, MJCF "
             "and USD assets for simulation and ROS2 visualization", source="upstream_code",
             ref=f"{PACKAGE_XML}:4-6"),
        Fact("The CMake package installs the mjcf directory with the other model assets under share/wuji_description",
             source="upstream_code", ref=f"{CMAKE}:6-9"),
        Fact("display.launch.py returns three nodes, robot_state_publisher, joint_state_publisher_gui and rviz2, and "
             "no controller, command topic, service or action", source="upstream_code",
             ref=f"{LAUNCH}:19-45"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The real MuJoCo engine contract, used by a backend that imports mujoco (an unlisted name such as ``sim``;
    #: not run here).  The gate exercises the package's stand-in module, whose F0 contract is selected by
    #: ``fidelity_by_backend`` below (reviewer change: the stand-in previously published this F1 contract).
    fidelity = {
        "engine": "mujoco:wujihand-left",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state, but the bridge takes no "
                     "seed and cap.world.reset.v1 restores the model defaults, so this package claims no seeded or "
                     "exact continuation.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "MuJoCo itself was not importable where the gate ran, so this real-engine contract was never "
            "exercised: no trajectory of this package was compared with MuJoCo and no state hash was validated",
            "the palm body declares no joint, so the hand is fixed to the world frame; no wrist, arm or base "
            "motion is modelled",
            "the package serves only the card's first model, the left hand with soft pad; the right hand, the "
            "simplified collision variants, the hand/body model and the hand2 models are other models and are not "
            "served here",
            "no rendering, camera or sensor stream is offered and no physical Wuji Hand is modelled or driven; "
            "nothing was validated against hardware",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo and not a recording: F0.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "seeded",
                "seed_control": "none",
                "notes": "The stand-in integrates the same placeholder response for the same controls from the "
                         "model defaults; it has no seed input and its motion is not MuJoCo's physics.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF for the "
                "joint dimensions (20 hinges) and the 20 explicit actuator ctrlranges but integrates a placeholder "
                "first-order motion of each actuated joint toward its control target, so trajectories, contacts, "
                "soft-pad deformation, actuator kp/kv and forcerange dynamics and self-collision are not MuJoCo's",
                "no STL mesh is loaded and no collision pair, equality, tendon or sensor of the model is resolved "
                "by the stand-in; the thumb soft-pad geometry is not simulated",
                "the stand-in's snapshot and restore copy its placeholder arrays only; they say nothing about "
                "restoring a real MuJoCo state",
                "the package serves only the card's first model, the left hand with soft pad; the right hand, the "
                "simplified collision variants, the hand/body model and the hand2 models are not served here",
                "no rendering, camera or sensor stream is offered and no physical Wuji Hand is modelled or driven; "
                "nothing was validated against hardware",
            ],
        },
    }
