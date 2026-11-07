"""OpenMHS driver for gh.ebim-benchmark/benchmark: the Task 1 cable-routing MuJoCo scene as a simulated world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's ``models[0]``,
``task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml``, and the bridge derives the contract
from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is
checked against the model's ``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs
``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world
state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``,
``seed``).  The device is simulated (R0): there is no hardware backend and no operator-required limit.

The upstream is the EBiM Benchmark Task 1 practice environment: a mobile dual-arm Franka FR3 platform with Robotiq
2F-85 grippers that routes a deformable cable across a fixture board (README.md:38-42).  ``teleop.session:
TeleopSession`` loads this MJCF into ``mujoco.MjModel`` (session.py:47-52) and advances it with ``mujoco.mj_step``
(session.py:153); the package serves the raw MuJoCo world, not the teleoperation stack, the task scoring or the
environment's home-keyframe setup.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the explicit joint and actuator shape, the control ranges and the time
step, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.  The model file is read from the read-only clone at the pinned commit and is never copied
into this package or imported as code.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml"
SESSION = "task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/session.py"
SCENE = "task1_mujoco/robotiq_duo_full_scene_minimal_core/teleop/scene.py"
README = "task1_mujoco/README.md"
ENVIRONMENT = "task1_mujoco/robotiq_duo_full_scene_minimal_core/environment.yml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/ebim-benchmark/benchmark/" + MODEL


class CableRoutingWorld(MujocoDriver):
    device_id = "ebim-task1-cable-routing"
    model_path = MODEL_PATH
    native = "teleop.session:TeleopSession"
    backends = {"fake": FakeMujoco}
    display_name = "EBiM Benchmark Task 1 cable routing (MuJoCo)"
    vendor, model = "EBiM Benchmark", "full_robot_board_cable_routing"
    tags = ["benchmark", "cable-routing", "dual-arm", "fr3", "manipulation", "mobile-base", "mujoco", "robot",
            "simulation"]
    facts = [
        Fact("Task 1 teleoperates a mobile dual-arm Franka FR3 platform with Robotiq 2F-85 grippers on a planar-drive "
             "base with a vertical spine to route a deformable cable across a fixture board", source="vendor_doc",
             ref=f"{README}:38-42"),
        Fact("Everything runs in a single MuJoCo process (main.py): robot, cable, board and physics live in one "
             "simulation", source="vendor_doc", ref=f"{README}:53-54"),
        Fact("The task environment pins mujoco==3.9.0", source="vendor_doc", ref=f"{ENVIRONMENT}:20"),
        Fact("The scene is the MuJoCo model full_robot_board_cable_routing", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model uses the implicitfast integrator with timestep 0.0005 s", source="upstream_code",
             ref=f"{MODEL}:7"),
        Fact("The scene activates the mujoco.elasticity.cable plugin", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The scene contains a cable composite with count 71 1 1 and initial none, described by its comment as 71 "
             "segments", source="upstream_code", ref=f"{MODEL}:947-949"),
        Fact("The cable initialization writes four qpos values at each cable segment's ball joint",
             source="upstream_code", ref=f"{SCENE}:113-121"),
        Fact("The actuator block declares a spine position actuator with ctrlrange 0 to 0.85, three base velocity "
             "actuators with ctrlrange -2.0 to 2.0 and -4.0 to 4.0, seven velocity actuators per FR3 arm with "
             "ctrlrange -8 to 8, -10 to 10 and -12 to 12, a position actuator per Robotiq gripper with ctrlrange 0 to "
             "0.8, caster and TMRV steer actuators with ctrlrange -3.14159 to 3.14159, and roll and drive actuators "
             "with ctrlrange -80 to 80", source="upstream_code", ref=f"{MODEL}:1030-1060"),
        Fact("The model has a home keyframe named home", source="upstream_code", ref=f"{MODEL}:1063"),
        Fact("TeleopSession is described as everything the input methods share and it owns the model and data",
             source="upstream_code", ref=f"{SESSION}:1-7"),
        Fact("TeleopSession loads the scene with scene.load_model and constructs mujoco.MjData from the model",
             source="upstream_code", ref=f"{SESSION}:47-52"),
        Fact("TeleopSession resets to the home keyframe when that key exists with mj_resetDataKeyframe and then calls "
             "mj_forward", source="upstream_code", ref=f"{SESSION}:53-56"),
        Fact("TeleopSession.step_once advances the physics with mujoco.mj_step", source="upstream_code",
             ref=f"{SESSION}:153"),
        Fact("scene.load_model loads the scene XML with mujoco.MjModel.from_xml_path", source="upstream_code",
             ref=f"{SCENE}:29"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the time step, the lockstep clock and the snapshot support; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:full_robot_board_cable_routing",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no seed "
                     "input and cap.world.reset.v1 restores model defaults, so a run repeats exactly on the same "
                     "engine but no seed selects a different state",
        },
        "timestep_ms": 0.5,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the scene's explicitly "
            "declared joints, actuators, ctrlranges and timestep but integrates a placeholder motion (a velocity "
            "actuator sets its joint velocity to the control value and a position actuator moves a fixed fraction "
            "toward it); it resolves no contact, friction, equality, tendon, actuator gain, sensor or noise model",
            "the 71-count composite cable with initial none is counted but not expanded; MuJoCo generates its 70 "
            "segment bodies and 69 ball joints at compile time (4 qpos and 3 qvel each, scene.py:113-121), so the "
            "real model's arrays are 315 qpos and 246 qvel, while the fake exposes only the 39 explicitly declared "
            "joints",
            "cap.world.reset.v1 runs mj_resetData + mj_forward (the bridge contract), not the upstream home keyframe, "
            "cable layout, arm ready pose or spawn placement (session.py:53-57); the fake also zeroes the arrays "
            "instead of resolving qpos0",
            "the upstream grasp servo, clip guide, cable speed cap and cable plugin applied by step_once are not "
            "applied; only the bridge's mj_step loop is served",
            "no rendering, camera or image stream is exposed, and the keyboard, gamepad, VR and ROS 2 teleoperation "
            "layers of the benchmark are not served",
            "snapshot and restore use the bridge's fallback copy of time/qpos/qvel/act/ctrl; the stand-in has no "
            "mj_getState/mj_setState, so this is not an exact integration-state snapshot",
            "MuJoCo itself was not importable where the gate ran, so no trajectory was compared with the real engine "
            "and the real-engine backend (sim) was not run",
            "no physical robot is modelled or driven and no hardware run is claimed",
        ],
    }
