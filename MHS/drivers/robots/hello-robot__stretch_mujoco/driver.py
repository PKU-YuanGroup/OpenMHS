"""OpenMHS driver for gh.hello-robot/stretch_mujoco: the Stretch SE3 MJCF scene (a MuJoCo family driver).

A MujocoDriver is configuration only.  ``model_path`` names the card's first model,
``stretch_mujoco/models/scene.xml``, which includes the robot model ``stretch.xml`` and the docking station
(``scene.xml:2-3``); the bridge derives the contract from the model it loads.  ``cap.world.step.v1`` takes
``{ticks, action: {ctrl: [...]}}``; each of the ten ``ctrl`` elements is checked against the model's
``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): the upstream is a MuJoCo simulation stack for Stretch, not a hardware interface, and
this package exposes only the MJCF model.  There is no hardware backend, no e-stop path to a machine and no
operator-required limit; the model file is the system of record for the control envelope.

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF text with its
includes expanded and takes the actuator count, the per-actuator control ranges, the joint dimensions and the option
time step from that tree, but its integration is a placeholder, not MuJoCo's physics; the driver's fidelity ``gaps``
state every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module
and loads the same file; that path was not run here.

The model files are read from the read-only upstream clone at the pinned commit (they are never copied into this
package and never imported).  Every Fact cites a line of that clone.  This package is model-authored and
unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a physical Stretch.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "stretch_mujoco/models/scene.xml"
ROBOT = "stretch_mujoco/models/stretch.xml"
ROBOT_330 = "stretch_mujoco/models/stretch_mj_3.3.0.xml"
DOCK = "stretch_mujoco/models/docking_station.xml"
SERVER = "stretch_mujoco/mujoco_server.py"
UTILS = "stretch_mujoco/utils.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/hello-robot/stretch_mujoco/" + MODEL


class Stretch(MujocoDriver):
    device_id = "stretch"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Hello Robot Stretch (MuJoCo simulation)"
    vendor, model = "Hello Robot", "Stretch SE3"
    tags = ["stretch", "hello-robot", "mobile-manipulator", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository provides a MuJoCo simulation stack for Stretch with position control for the arm, "
             "head and gripper joints, velocity control for the mobile base, RGB and depth camera imagery and 2D "
             "lidar scans", source="vendor_doc", ref="README.md:11"),
        Fact("The StretchMujocoSimulator class is documented to start the simulation, position-control the robot's "
             "ranged joints, velocity-control its mobile base, and read joint states and camera imagery",
             source="vendor_doc", ref="README.md:101-107"),
        Fact("The upstream default scene is models/scene.xml and the default robot model is models/stretch.xml",
             source="upstream_code", ref=f"{UTILS}:33-34"),
        Fact("The upstream URDF model name defaults to SE3", source="upstream_code", ref=f"{UTILS}:37"),
        Fact("The simulator loads the scene MJCF with MjModel.from_xml_path(scene_xml_path) and creates the MjData "
             "from that model", source="upstream_code", ref=f"{SERVER}:248-258"),
        Fact("The upstream reads every joint's range from mjmodel.jnt_range for njnt joints and records it as a "
             "joint limit", source="upstream_code", ref=f"{SERVER}:281-291"),
        Fact("The upstream writes a move_to command to data.actuator(name).ctrl and a keyframe command to "
             "mjmodel.keyframe(name).ctrl", source="upstream_code", ref=f"{SERVER}:539-574"),
        Fact("The scene includes stretch.xml and docking_station.xml", source="upstream_code", ref=f"{MODEL}:2-3"),
        Fact("The Stretch body is a free base: base_link carries <freejoint/>", source="upstream_code",
             ref=f"{ROBOT}:228-230"),
        Fact("The actuator defaults set the wheel control range to -6 to 6 and the lift control range to 0 to 1.1",
             source="upstream_code", ref=f"{ROBOT}:16-22"),
        Fact("The actuator defaults set the telescope control range to 0 to 0.52, head_pan to -4.04 to 1.73 and "
             "head_tilt to -1.53 to 0.79", source="upstream_code", ref=f"{ROBOT}:24-37"),
        Fact("The actuator defaults set wrist_yaw to -1.39 to 4.42, wrist_pitch to -1.57 to 0.56, wrist_roll to "
             "-3.14 to 3.14 and the gripper slide to -0.02 to 0.04", source="upstream_code", ref=f"{ROBOT}:44-62"),
        Fact("The actuator block declares ten actuators: two velocity actuators for the wheels and eight position "
             "actuators for lift, arm, wrist_yaw, wrist_pitch, wrist_roll, gripper, head_pan and head_tilt",
             source="upstream_code", ref=f"{ROBOT}:524-535"),
        Fact("The arm position actuator drives the fixed tendon extend, which sums the four arm slide joints "
             "joint_arm_l0, joint_arm_l1, joint_arm_l2 and joint_arm_l3", source="upstream_code",
             ref=f"{ROBOT}:507-514"),
        Fact("The robot declares two wheel hinge joints, a lift slide joint and four arm telescope slide joints",
             source="upstream_code", ref=f"{ROBOT}:284-339"),
        Fact("The head declares pan and tilt hinge joints and a nav-camera hinge joint", source="upstream_code",
             ref=f"{ROBOT}:448-465"),
        Fact("The model declares the cameras d405_rgb and d405_depth, d435i_camera_rgb and d435i_camera_depth, and "
             "nav_camera_rgb", source="upstream_code", ref=f"{ROBOT}:383-468"),
        Fact("The model declares a gyro, an accelerometer and a rangefinder lidar sensor on base_imu and lidar "
             "sites", source="upstream_code", ref=f"{ROBOT}:537-541"),
        Fact("The model declares home and stow keyframes, each with a ten-element ctrl vector", source="upstream_code",
             ref=f"{ROBOT}:543-546"),
        Fact("The model sets no option timestep: its option element carries integrator implicitfast, impratio 20 "
             "and cone elliptic", source="upstream_code", ref=f"{ROBOT}:7-9"),
        Fact("A second Stretch robot model, stretch_mj_3.3.0.xml, declares the same ten actuators",
             source="upstream_code", ref=f"{ROBOT_330}:519-530"),
        Fact("The docking station is a free body: link_docking_station carries <freejoint/>", source="upstream_code",
             ref=f"{DOCK}:43-45"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock from the model; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:stretch",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the served model has "
                     "no random element, so one ctrl sequence and tick count repeat a trajectory; the bridge takes "
                     "no seed input and a reset restores the model defaults, so no seed selects a different one. "
                     "The package's fake backend is deterministic too, but its placeholder motion is not the "
                     "engine's physics and it offers no snapshot state.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served scene.xml "
            "with its includes, takes the ten actuator control ranges, the joint dimensions and the option time "
            "step from the tree, then moves each actuated joint toward its control value; it computes no inertia, "
            "torque, contact, equality, tendon or actuator dynamics, so no trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact: the scene's table, free objects and "
            "docking station are not simulated physically, and the arm equality and tendon constraints only "
            "distribute a control target in the placeholder",
            "the model states no option timestep (stretch.xml:7-9); the stand-in uses a placeholder library "
            "default, and the bridge publishes that stand-in value from the stand-in",
            "the stand-in does not apply the model's gear, gain, bias, damping, friction, armature or force "
            "ranges, and a wheel velocity actuator is treated as a direct joint velocity target",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering, cameras, lidar scans or gripper range mapping are published: the upstream "
            "StretchMujocoSimulator camera, sensor and joint-status API (README.md:101-107) is not part of this "
            "driver, which exposes only the bridge's time, qpos, qvel and ctrl state",
            "the card's other robot model, stretch_mj_3.3.0.xml, is not served: one package serves one device, "
            "and the driver and fake use models[0], the default scene",
            "no physical Stretch is modelled and nothing was validated against the hardware",
        ],
    }
