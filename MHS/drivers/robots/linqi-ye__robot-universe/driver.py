"""OpenMHS driver for gh.linqi-ye/robot-universe: the go_bdx MuJoCo scene as a simulated world.

The pinned repository is a collection of robot description files (README.md:1-2).  Its ROS content is
description packages whose launch files display or spawn models, and one ROS 1 visualisation node
(``panda5_test/src/panda5.cpp`` receives UDP state and publishes joint states); none accepts a command, and the
go_bdx directory has no ROS file at all, so the card's ``family:ros`` / ``RosDriver`` scan has no pinned command
endpoint or type to bind.  This package follows the card's first model, the MJCF scene
``go_bdx/scene.xml`` (``models[0]``), as a configuration-only ``MujocoDriver``: the bridge loads the model and
serves ``cap.world.step.v1`` and ``cap.world.reset.v1``.

``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``.  Each ``ctrl`` element is checked against that
actuator's ``ctrlrange`` (the model declares 16 position actuators with explicit ranges, ``go_bdx.xml:163-179``)
before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the
model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state.

MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in
``mujoco`` module (fake.py).  It parses the same MJCF for the joint dimensions, the actuator count and the control
ranges, but its integration is a placeholder, not MuJoCo's physics: it publishes its own F0 contract through
``fidelity_by_backend`` (model review, 2026-11-05), and the class-level F1 contract describes the real engine path,
which was not run.  The ``sim``
backend (a backend that ``backends`` does not name) imports the real ``mujoco`` module and loads the same file; that
path was not run here.  The model file is read from the read-only clone at the pinned commit and is never copied
into the package or imported as Python.

This package is model-authored and unreviewed: it is checked on the fake backend only, no MuJoCo engine run and no
hardware run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "go_bdx/scene.xml"
MODEL_PATH = "../../../../robots/linqi-ye/robot-universe/" + MODEL
SCENE = "go_bdx/scene.xml"
BDX = "go_bdx/go_bdx.xml"
README = "README.md"


class GoBdxScene(MujocoDriver):
    """The bdx scene of the pinned robot-universe collection, served as a MuJoCo world."""

    device_id = "go-bdx"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "bdx scene (robot-universe)"
    vendor = "linqi-ye"
    model = "bdx"
    tags = ["bdx", "go-bdx", "mujoco", "robot-universe", "simulation", "model"]
    facts = [
        Fact("The repository describes itself as a comprehensive collection of robot URDF models.",
             source="vendor_doc", ref=f"{README}:1-2"),
        Fact("The package's model is the MJCF scene go_bdx/scene.xml, whose root element is "
             "'<mujoco model=\"bdx scene\">' and which includes go_bdx.xml on line 2.",
             source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The scene adds a gradient skybox, a checkered groundplane and a floor plane body to the "
             "included robot model.", source="upstream_code", ref=f"{SCENE}:13-22"),
        Fact("The included model's root element is '<mujoco model=\"bdx\">' and its compiler sets "
             "angle='radian', meshdir='meshes' and autolimits='true'.", source="upstream_code", ref=f"{BDX}:1-2"),
        Fact("The model's option line selects the implicitfast integrator; the timestep option on line 4 is "
             "commented out.", source="upstream_code", ref=f"{BDX}:4-5"),
        Fact("The bdx default class sets joint limited='true', and its six joint-parameter classes set "
             "range='-0.785398 0.785398'.", source="upstream_code", ref=f"{BDX}:8-35"),
        Fact("The bdx body declares a freejoint, and its pelvis body sets childclass 'bdx'.",
             source="upstream_code", ref=f"{BDX}:62-65"),
        Fact("The actuator section declares 16 position actuators with gear 1 and explicit ctrlrange values: "
             "the hip, knee, ankle and neck actuators use -30 to 30, the head actuators -5.55 to 5.55, and the "
             "antenna actuators -13.62 to 13.62.", source="upstream_code", ref=f"{BDX}:163-179"),
        Fact("The same actuator lines set forcerange -23.7 to 23.7 for the hip, knee, ankle and neck actuators, "
             "-7.3 to 7.3 for the head actuators and -0.2943 to 0.2943 for the antenna actuators.",
             source="upstream_code", ref=f"{BDX}:163-179"),
        Fact("The model declares six sensors on the imu site: orientation, position, angular velocity, linear "
             "velocity, linear acceleration and a magnetometer.", source="upstream_code", ref=f"{BDX}:181-188"),
        Fact("The mesh assets declare scale='0.001 0.001 0.001' for every STL mesh.",
             source="upstream_code", ref=f"{BDX}:42-58"),
        Fact("panda5_test/src/panda5.cpp initialises the ROS 1 node panda_visual and advertises joint_states and "
             "CPU-sample, mode and leg-end topics.", source="upstream_code",
             ref="panda5_test/src/panda5.cpp:233-253"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The bridge derives engine timing, lockstep clock and snapshot profile from the model; the members below are this
    #: package's.  The model states no timestep, so the bridge reports MuJoCo's library default (a library default, not
    #: a sourced device bound).  This class-level F1 contract describes the real MuJoCo path, which was not run; the
    #: fake backend publishes its own F0 contract through ``fidelity_by_backend`` below (model review, 2026-11-05: the
    #: stand-in previously published this F1 contract).
    fidelity = {
        "engine": "mujoco:bdx scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism 'none': cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state, "
                     "contact or RNG completeness.",
        },
        "gaps": [
            "MuJoCo itself was not importable where the gate ran, so this real-engine contract was never "
            "exercised: no trajectory of this package was compared with MuJoCo and no state hash was validated",
            "the model states no timestep (go_bdx.xml:4 is commented out); the bridge reports MuJoCo's library "
            "default, not a bound from the clone",
            "the hip, knee, ankle and neck position actuators accept ctrl -30..30 and the head and antenna actuators "
            "-5.55..5.55 and -13.62..13.62, while every hinge joint is limited to -0.785398..0.785398 "
            "(go_bdx.xml:8-35, 163-179): the step envelope bounds the control target, not the joint, and a target "
            "outside the joint range drives the joint into its limit",
            "no mesh-based rendering, camera or sensor sample (orientation, position, gyro, velocimeter, "
            "accelerometer, magnetometer) is exposed",
            "the package serves the card's models[0] only; the card's other models "
            "(birdy_v1/mujoco/scene_birdy_v1.xml, birdy_v1/mujoco/scene_birdy_v1_L.xml, PF_P441A/xml/robot.xml "
            "and PF_TRON1A/xml/robot.xml) are not served",
            "the upstream is a description collection whose ROS files display or spawn models and receive "
            "visualisation state; this package drives the MJCF model, not a deployed robot and not a ROS graph",
            "no physical robot is modelled or driven; this simulated package has no hardware backend, and nothing "
            "was validated against hardware",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no physics)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in integrates the same placeholder response for the same controls from the "
                         "model defaults; it has no seed input and its motion is not MuJoCo's physics, so no "
                         "trajectory or state-hash replay is claimed.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF for the joint "
                "dimensions, the actuator count and the per-actuator ctrlranges but integrates a placeholder "
                "first-order motion of each actuated hinge toward its control value, so trajectories, contacts, "
                "actuator kp/kv and forcerange dynamics and the floating base are not MuJoCo's",
                "the stand-in ignores the joint ranges (-0.785398..0.785398) and moves a hinge toward any target "
                "inside the ctrlrange, where MuJoCo's joint limit would stop it",
                "the freejoint is reset to zero qpos, not MuJoCo's model qpos0 (which would include an identity "
                "quaternion), and the stand-in resolves no contact, equality, tendon or sensor",
                "no mesh or texture of the meshes/ directory is loaded and no sensor sample is exposed",
                "the fake's 0.002 s timestep is a placeholder for MuJoCo's library default, not a bound from the "
                "clone; the stand-in offers no mj_getState/mj_setState, so its checkpoints copy placeholder arrays",
                "the package serves the card's models[0] only, and no physical robot is modelled or driven",
            ],
        },
    }
