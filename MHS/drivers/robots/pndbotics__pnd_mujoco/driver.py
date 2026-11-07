"""OpenMHS driver for gh.pndbotics/pnd_mujoco: the Adam-Lite scene as a MuJoCo world (a MuJoCo family driver).

``pnd_mujoco`` is a MuJoCo-based simulator for the PNDbotics Adam humanoids: ``simulate_python`` loads an MJCF scene
from ``pnd_robots`` and steps it with ``mujoco.mj_step`` (README.md:24-26, simulate_python/pnd_mujoco.py:16 and :74).
A ``MujocoDriver`` is configuration only: ``model_path`` names the card's main scene (``models[0]``,
``pnd_robots/adam_lite/scene.xml``) and the bridge derives the whole contract from the model it loads.  The step
action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (23 motor actuators: 12 leg, 3
waist and 4 per arm), and the world state is the full integration state of the model plus the tick.  The reset
restores the model defaults (``mj_resetData`` + ``mj_forward``).

The device is simulated (R0): there is no hardware backend and no operator-supplied bound.  The gate cannot install
MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same scene and robot file for the model shape (joint dimensions, actuator count, control ranges, timestep) but its
integration is a placeholder, not MuJoCo's physics; the driver's fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not
run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of that clone.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "pnd_robots/adam_lite/scene.xml"
ROBOT = "pnd_robots/adam_lite/adam_lite.xml"
SIMULATOR = "simulate_python/pnd_mujoco.py"
CONFIG = "simulate_python/config.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/pndbotics/pnd_mujoco/" + SCENE


class AdamLite(MujocoDriver):
    device_id = "adam_lite"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "PNDbotics Adam-Lite humanoid (MuJoCo scene)"
    vendor, model = "PNDbotics", "Adam-Lite"
    tags = ["adam", "adam-lite", "humanoid", "mujoco", "pndbotics", "robot", "simulation"]
    facts = [
        Fact("The repository has a simulator in simulate_python, implemented on pnd_sdk_python and mujoco, and the "
             "MJCF description files of the supported robots in pnd_robots", source="vendor_doc", ref="README.md:24-26"),
        Fact("The simulator loads the scene named by config.ROBOT_SCENE with mujoco.MjModel.from_xml_path",
             source="upstream_code", ref=f"{SIMULATOR}:16"),
        Fact("config.py composes ROBOT_SCENE from ROBOT, whose default is adam_u_omnipicker; adam_lite, adam_pro and "
             "adam_sp are the other listed names", source="upstream_code", ref=f"{CONFIG}:1-2"),
        Fact("config.py sets SIMULATE_DT to 0.001 s", source="upstream_code", ref=f"{CONFIG}:21"),
        Fact("The simulator overwrites model.opt.timestep with config.SIMULATE_DT", source="upstream_code",
             ref=f"{SIMULATOR}:36"),
        Fact("The simulator advances the world with mujoco.mj_step in its physics loop", source="upstream_code",
             ref=f"{SIMULATOR}:74"),
        Fact("The card's main model is the MJCF scene pnd_robots/adam_lite/scene.xml, whose root element is "
             "<mujoco model=\"adam_lite scene\">", source="upstream_code", ref=f"{SCENE}:1"),
        Fact("The scene includes the robot model adam_lite.xml and sets the option timestep to 0.001 s",
             source="upstream_code", ref=f"{SCENE}:2-18"),
        Fact("The robot model is rooted at <mujoco model=\"adam_lite\">", source="upstream_code", ref=f"{ROBOT}:1"),
        Fact("The robot's base is a free joint named floating_joint, so the model has a floating base (7 qpos and 6 "
             "qvel values) before the 23 hinge joints", source="upstream_code", ref=f"{ROBOT}:100"),
        Fact("The model defines 23 <motor> actuators: 12 leg, 3 waist and 4 per arm; the two wristYaw motors are "
             "commented out", source="upstream_code", ref=f"{ROBOT}:294-319"),
        Fact("The leg motor control ranges are hipPitch and kneePitch +-230, hipRoll +-160, hipYaw +-105, "
             "anklePitch +-40 and ankleRoll +-12", source="upstream_code", ref=f"{ROBOT}:295-306"),
        Fact("The waist motor control ranges are +-110, the shoulder ranges +-65 and the elbow ranges +-30",
             source="upstream_code", ref=f"{ROBOT}:307-318"),
        Fact("The model defines joint position, joint velocity and joint actuator force sensors for the actuated "
             "joints, plus an IMU at site imu (frame quaternion, gyro, accelerometer, frame position and linear "
             "velocity)", source="upstream_code", ref=f"{ROBOT}:321-405"),
        Fact("The README advertises MuJoCo 3.2.0 and Python 3.8 or newer", source="vendor_doc",
             ref="README.md:12-13"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the timestep, the lockstep clock and the reset; the determinism note and the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:adam_lite",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state, and a reset restores "
                     "the model defaults; the bridge takes no seed that selects a different state, so equal initial "
                     "states repeat but no seed varies them",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the scene for the joint "
            "dimensions, the actuator count, the control ranges and the 1 ms timestep, but it integrates a "
            "placeholder first-order motion of each actuated hinge and applies no gravity, contact, equality, "
            "tendon or muscle model",
            "no mesh or texture of the asset directories is loaded by the stand-in, and no collision or visual "
            "geometry is resolved",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine; the upstream simulator's viewer, elastic hoist, joystick and DDS/ROS2 bridges "
            "are not modelled either",
            "no physical Adam-Lite robot is modelled by this driver and nothing was validated against the hardware",
        ],
    }
