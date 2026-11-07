"""OpenMHS driver for gh.justagist/mujoco_panda: the Franka Emika Panda MJCF scene as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model
(``mujoco_panda/models/franka_panda.xml``) and the bridge derives the whole contract from the model it loads.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``: each of the nine ``ctrl`` elements is checked
against the model's ``actuator_ctrlrange`` (per actuator) before it is written to ``data.ctrl``, then ``mj_step``
runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.
The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``,
``timestep_ms``, ``seed``).  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit; the control envelope is the model's own.

The repository is an archived MuJoCo-based Franka Panda simulator that targets the deprecated ``mujoco_py``
bindings (README.md:3-6) and keeps the MJCF scenes in ``mujoco_panda/models`` (README.md:18).  This package serves
the card's first model; the model file is read from the read-only clone in place and is never copied into the
package or imported.

MuJoCo is not installed and cannot be installed where the gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It reads the same MJCF file and its
includes for the model shape (actuator count, per-actuator control ranges, joint dimensions, option timestep) but
its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A backend
name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that
path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "mujoco_panda/models/franka_panda.xml"
ASSETS = "mujoco_panda/models/panda/assets.xml"
ARM = "mujoco_panda/models/panda/arm_with_gripper.xml"
GRIPPER = "mujoco_panda/models/panda/gripper.xml"
ACTUATORS = "mujoco_panda/models/panda/actuators/torque_with_gripper.xml"
SENSORS = "mujoco_panda/models/panda/sensors/ft_sensor.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/justagist/mujoco_panda/" + MODEL


class MujocoPanda(MujocoDriver):
    device_id = "mujoco-panda"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Franka Emika Panda MJCF scene (mujoco_panda)"
    vendor, model = "justagist", "mujoco_panda_model"
    tags = ["franka", "panda", "mujoco", "simulation", "robot-arm", "justagist"]
    facts = [
        Fact("The repository is archived, targets the deprecated mujoco_py bindings, is Panda-specific and is no "
             "longer maintained; it is superseded by mujoco_robot", source="vendor_doc", ref="README.md:3-10"),
        Fact("The project provides Franka Emika Panda robot model definitions for MuJoCo, a MuJoCo-based robot "
             "simulator, a Python 3 API for controlling and monitoring the simulated robot, direct position and "
             "torque controllers, and a task-space hybrid force motion controller", source="vendor_doc",
             ref="README.md:12-16"),
        Fact("The robot models are in mujoco_panda/models and the API is documented in MujocoRobot and PandaArm",
             source="vendor_doc", ref="README.md:18-40"),
        Fact("The library requires mujoco_py, numpy, scipy and quaternion, and it is used after sourcing set_env.sh",
             source="vendor_doc", ref="README.md:24-32"),
        Fact("The main scene is the MJCF model named mujoco_panda_model", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The main scene includes other/simple_scene.xml and panda/assets.xml and pulls in the "
             "arm_with_gripper body tree, the torque_with_gripper actuators and the ft_sensor sensors",
             source="upstream_code", ref=f"{MODEL}:4-21"),
        Fact("The main scene selects the elliptic contact cone and enables gravity; its option element sets no "
             "timestep", source="upstream_code", ref=f"{MODEL}:8-10"),
        Fact("The seven arm joints are hinges named panda_joint1 to panda_joint7 with ranges: joints 1, 3, 5 and 7 "
             "+-2.8973, joint 2 +-1.7628, joint 4 -3.0718 to -0.4 and joint 6 -1.6573 to 2.1127",
             source="upstream_code", ref=f"{ARM}:10-46"),
        Fact("The end-effector site is ee_site on panda_link7", source="upstream_code", ref=f"{ARM}:50"),
        Fact("The hand has two slide joints, panda_finger_joint1 and panda_finger_joint2, each with range 0 to "
             "0.04 m", source="upstream_code", ref=f"{GRIPPER}:8-14"),
        Fact("The actuator block has seven motor actuators with ctrlrange +-87 for arm joints 1 to 4 and +-12 for "
             "arm joints 5 to 7, plus two position actuators for the gripper fingers with ctrlrange 0 to 0.04",
             source="upstream_code", ref=f"{ACTUATORS}:2-12"),
        Fact("The model carries a force sensor and a torque sensor at ee_site", source="upstream_code",
             ref=f"{SENSORS}:2-3"),
        Fact("The asset block compiles angles in radians and declares the collision and visual STL meshes",
             source="upstream_code", ref=f"{ASSETS}:3-25"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:mujoco_panda_model",
        "fidelity_level": "F1",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF and its includes "
            "for the actuator control ranges, the joint dimensions and the option timestep but integrates a "
            "placeholder first-order motion of each actuated joint toward its control value",
            "the seven arm actuators are torque channels in the model and the two gripper actuators are position "
            "channels, while the stand-in treats every actuator as a position target, so the fake's trajectories "
            "are not the model's torque dynamics",
            "no mesh, texture, material or inertia is loaded and no contact, friction, tendon, equality or "
            "actuator constraint of the model is resolved; the force and torque sensors at ee_site are not read",
            "the model sets no timestep, so the engine default applies; the stand-in uses a placeholder library "
            "default and the published timestep_ms comes from that fake",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine or with the upstream mujoco_py simulator",
            "no viewer, rendering or camera stream is exposed: the package serves only the cap.world.* integration "
            "state and control vector",
            "only the card's first model, franka_panda.xml, is served; the no-gripper, position-actuator and "
            "block-table scenes are other models and are not part of this driver",
            "no physical Franka Emika Panda is modelled and nothing was validated against hardware",
        ],
    }
