"""OpenMHS driver for gh.nvlabs/humanoidmimicgen: the Unitree G1 loco-manipulation MJCF as a simulated MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model, ``models[0]``
(``humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml``), and the bridge loads
it with the MuJoCo engine, derives ``cap.world.step.v1``'s ``action.ctrl`` from the model's ``actuator_ctrlrange``
(29 motor actuators), writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves ``cap.world.reset.v1`` with
``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical G1 is driven.  The card's five entry
symbols are RoboSuite environments of the upstream package; this family serves the MJCF robot model the card lists
as ``models[0]``, not the environments' task, object or randomization logic.  The model file and its meshes are
read in place from the read-only clone at the pinned commit and are never copied, imported or installed.

MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py), which reads the same MJCF for the model shape and integrates a placeholder motion
instead of the engine's physics; the fidelity ``gaps`` below state every difference.  Every Fact cites a line of
the clone at commit d82844dcec242c82d6b82628ccc45933c3ad5cbd.  This package is model-authored and unreviewed: it is
checked on the fake backend only, and nothing here ran the MuJoCo engine or a physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_29dof_rev_1_0.xml"
LEFT_HAND = "humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_left_hand.xml"
RIGHT_HAND = "humanoidmimicgen/locomanipulation/models/assets/robots/unitree_g1/g1_threefinger_right_hand.xml"
ARENA = "humanoidmimicgen/locomanipulation/models/assets/arenas/ground_arena.xml"
G1_ROBOT = "humanoidmimicgen/locomanipulation/models/robots/manipulators/g1_robot.py"
HANDS = "humanoidmimicgen/locomanipulation/models/grippers/g1_threefinger_hands.py"
ENVS = "humanoidmimicgen/locomanipulation/envs"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/nvlabs/humanoidmimicgen/" + MODEL


class G1Locomanip(MujocoDriver):
    device_id = "g1-locomanip"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 29-DOF loco-manipulation model (MuJoCo)"
    vendor, model = "NVIDIA / Unitree Robotics", "G1 29-DOF MJCF"
    tags = ["mujoco", "unitree", "g1", "humanoid", "loco-manipulation", "simulation", "robot"]
    facts = [
        Fact("The release packages nine G1 simulation environments and MuJoCo assets", source="vendor_doc",
             ref="README.md:21-22"),
        Fact("The project requires Linux and Python 3.10; an NVIDIA GPU and CUDA are needed only for WBC execution "
             "or EGL rendering, and recorded playback can run CPU-only", source="vendor_doc",
             ref="README.md:40-42"),
        Fact("MuJoCo is pinned to 3.2.6 and RoboSuite to 1.5.1", source="vendor_doc", ref="README.md:46"),
        Fact("The package requires Python 3.10 or newer and declares mujoco==3.2.6, numpy==1.26.4, "
             "robosuite==1.5.1 and robosuite-models==1.0.0 as dependencies", source="upstream_code",
             ref="pyproject.toml:10-25"),
        Fact("The card's primary model is the MJCF robot named g1_29dof_with_hand_rev_1_0 with angle unit radian",
             source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The robot is attached to the world by a free joint named base on the root body", source="upstream_code",
             ref=f"{MODEL}:59-61"),
        Fact("The actuator block declares 29 motor actuators", source="upstream_code", ref=f"{MODEL}:390-419"),
        Fact("The twelve leg motors have control ranges -88 to 88 for hip pitch and hip yaw, -139 to 139 for hip roll "
             "and knee, and -50 to 50 for ankle pitch and ankle roll", source="upstream_code",
             ref=f"{MODEL}:391-402"),
        Fact("The three waist motors have control ranges -88 to 88 (yaw), -50 to 50 (roll) and -50 to 50 (pitch)",
             source="upstream_code", ref=f"{MODEL}:403-405"),
        Fact("The fourteen arm motors have control ranges -25 to 25 for shoulder pitch, shoulder roll, shoulder yaw "
             "and elbow, -30 to 30 for wrist roll, and -10 to 10 for wrist pitch and wrist yaw",
             source="upstream_code", ref=f"{MODEL}:406-419"),
        Fact("The model declares four IMU sensors: a gyroscope and an accelerometer on the torso site and another "
             "pair on the pelvis site", source="upstream_code", ref=f"{MODEL}:422-427"),
        Fact("The asset section references 33 mesh STL files under meshes/", source="upstream_code",
             ref=f"{MODEL}:23-57"),
        Fact("The G1 robot class is a RoboSuite LeggedManipulatorModel", source="upstream_code",
             ref=f"{G1_ROBOT}:14-15"),
        Fact("The G1 constructor loads robots/unitree_g1/g1_29dof_rev_1_0.xml", source="upstream_code",
             ref=f"{G1_ROBOT}:25-32"),
        Fact("The left three-finger hand is a separate MJCF model named g1_threefinger_left_hand",
             source="upstream_code", ref=f"{LEFT_HAND}:1"),
        Fact("The left hand MJCF declares seven position actuators", source="upstream_code",
             ref=f"{LEFT_HAND}:122-140"),
        Fact("The right three-finger hand is a separate MJCF model named g1_threefinger_right_hand",
             source="upstream_code", ref=f"{RIGHT_HAND}:1"),
        Fact("The right hand MJCF declares seven position actuators", source="upstream_code",
             ref=f"{RIGHT_HAND}:122-142"),
        Fact("The left hand gripper loads g1_threefinger_left_hand.xml", source="upstream_code",
             ref=f"{HANDS}:26-33"),
        Fact("The right hand gripper loads g1_threefinger_right_hand.xml", source="upstream_code",
             ref=f"{HANDS}:106-113"),
        Fact("LocoManipulationEnv is a RoboSuite ManipulationEnv", source="upstream_code",
             ref=f"{ENVS}/base.py:122-123"),
        Fact("GroundOnly is a pass-through subclass of LocoManipulationEnv", source="upstream_code",
             ref=f"{ENVS}/base.py:420-421"),
        Fact("LMSimpleEnv selects GroundArena as its arena", source="upstream_code",
             ref=f"{ENVS}/locomanip.py:92-93"),
        Fact("GroundArena loads arenas/ground_arena.xml", source="upstream_code",
             ref="humanoidmimicgen/locomanipulation/models/scenes/ground_arena.py:33-36"),
        Fact("The ground arena MJCF holds the floor plane and four fixed cameras (frontview, birdview, agentview, "
             "sideview)", source="upstream_code", ref=f"{ARENA}:14-27"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine
    #: timestep, the determinism kind and the lockstep clock from the loaded model; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:g1_29dof_with_hand_rev_1_0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the loaded MJCF deterministically from the reset state and the model has no "
                     "random element; the bridge takes no seed and a reset restores the model defaults.  The "
                     "package's fake is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the card's MJCF for one "
            "free joint and 29 hinge joints (36 qpos, 35 dof), the 29 motor actuators and their ctrlranges, then "
            "moves each actuated hinge a placeholder fraction toward its control value; it computes no inertias, "
            "contacts, friction, actuator or sensor dynamics and was never compared with the engine",
            "the model file sets no <option timestep>; the published timestep_ms is MuJoCo's library default "
            "(0.002 s) supplied by the fake's fallback, not a value stated by the model",
            "models[0] is a robot asset, not a full scene: it has one free-floating base and no floor, arena or "
            "camera.  The upstream environments compose it with a separate ground arena (GroundArena loads "
            "arenas/ground_arena.xml), so the bare model falls under gravity in the real engine",
            "the three-finger hands are separate MJCF fragments attached by the upstream environment as grippers; "
            "the loaded model has 29 body actuators and no hand joints, so the seven position actuators of each "
            "hand are not part of this world",
            "the stand-in loads no mesh or texture (the model's asset section names 33 STL files) and resolves no "
            "contact, tendon or equality constraint; a real engine load needs the meshes beside the model, which "
            "the pinned clone provides",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model step only",
            "no rendering, cameras or sensor publication: the four IMU sensors of the model are not exposed; the "
            "observation is only the bridge's time, qpos, qvel and ctrl",
            "the card's five entry symbols are RoboSuite environments; they are not imported or run, and their "
            "task, object, randomization and success logic is not modelled",
            "MuJoCo itself was not installed where the gate ran, so no trajectory of this package was compared "
            "with the real engine; no physical G1 is modelled and nothing was validated against the robot",
        ],
    }
