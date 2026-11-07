"""OpenMHS driver for gh.isri-aist/jvrc_mj_description: the JVRC1 humanoid MJCF model (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene (the card's ``models[0]``,
``xml/scene.xml``) and the bridge derives the whole contract from the model it loads.  The step action is
``data.ctrl``, one value per actuator, checked against the model's ``actuator_ctrlrange`` when the model limits the
control; this model's ``jvrc1`` motor class sets ``ctrllimited="false"`` (``xml/jvrc1.xml:13``) and its motors
state no control interval, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.
The world state is the integration state of the model (``time``,
``qpos``, ``qvel``, ``ctrl``) plus the tick count, and ``cap.world.reset.v1`` restores the model defaults with
``mj_resetData``/``mj_forward``.

The device is simulated (R0): there is no hardware backend, no physical motion and no operator-required limit.  The
gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the joint dimensions and the actuator list (the scene includes
``jvrc1.xml``) but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend
name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path
was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit 8cfc65f5c5793582b55e0d5eb4726dfb3094a224.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "xml/scene.xml"
MODEL_PATH = "../../../../robots/isri-aist/jvrc_mj_description/" + MODEL
SCENE = "xml/scene.xml"
ROBOT = "xml/jvrc1.xml"
README = "README.md"
CMAKE = "CMakeLists.txt"
MM_CONFIG = "mc_mujoco/jvrc1.in.yaml"


class Jvrc1(MujocoDriver):
    device_id = "jvrc1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "JVRC1 humanoid (MuJoCo)"
    vendor, model = "ISRI-AIST", "JVRC1"
    tags = ["humanoid", "jvrc1", "mujoco", "robot", "simulation", "whole-body"]
    facts = [
        Fact("The package's model is the MJCF scene xml/scene.xml, whose root element is '<mujoco "
             "model=\"jvrc1 scene\">' and which includes jvrc1.xml", source="upstream_code",
             ref=f"{SCENE}:1-3"),
        Fact("jvrc1.xml declares '<compiler angle=\"radian\" meshdir=\"../meshes\" texturedir=\"../meshes\"/>', so "
             "the joint ranges are radians and its meshes and textures resolve from ../meshes", source="upstream_code",
             ref=f"{ROBOT}:4"),
        Fact("The model sets '<option timestep=\"0.001\" iterations=\"50\" tolerance=\"1e-10\" solver=\"Newton\" "
             "jacobian=\"dense\" cone=\"pyramidal\"/>', so its integration step is 0.001 s", source="upstream_code",
             ref=f"{ROBOT}:8"),
        Fact("The model sets '<size njmax=\"500\" nconmax=\"100\"/>'", source="upstream_code", ref=f"{ROBOT}:6"),
        Fact("The jvrc1 default class gives its joints limited=\"true\" and damping=\"0.2\" and its motors "
             "ctrllimited=\"false\" forcelimited=\"false\"", source="upstream_code", ref=f"{ROBOT}:11-13"),
        Fact("The robot's root body PELVIS_S is placed at pos=\"0 0 1.4\" and has a freejoint named root",
             source="upstream_code", ref=f"{ROBOT}:206-207"),
        Fact("The R_HIP_P joint is a hinge with range -2.0944 to 0.785398 rad and armature 0.1925",
             source="upstream_code", ref=f"{ROBOT}:216"),
        Fact("The L_KNEE joint is a hinge with range 0 to 2.61799 rad and armature 0.1305", source="upstream_code",
             ref=f"{ROBOT}:265"),
        Fact("The contact section excludes adjacent pelvis, knee, waist, neck, shoulder, elbow and gripper body "
             "pairs from collision", source="upstream_code", ref=f"{ROBOT}:143-200"),
        Fact("Ten equality constraints couple the five distal finger joints of each hand to its thumb with "
             "polycoef values", source="upstream_code", ref=f"{ROBOT}:480-492"),
        Fact("The actuator section has one motor for each leg, waist, neck, shoulder, elbow, wrist and thumb joint, "
             "and no motor for the distal finger joints", source="upstream_code", ref=f"{ROBOT}:495-536"),
        Fact("The sensor section reads force and torque at both feet and both hands and a gyro and accelerometer "
             "at the imu site", source="upstream_code", ref=f"{ROBOT}:538-554"),
        Fact("The repository provides JVRC1 model files for MuJoCo and installs the files in the directory so that "
             "mc_mujoco can pick them up automatically", source="vendor_doc", ref=f"{README}:5"),
        Fact("The CMake build sets JVRC1_XML_MODEL_PATH to xml/jvrc1.xml and JVRC1_PDGAINS_PATH to "
             "pdgains/PDgains_sim.dat", source="upstream_code", ref=f"{CMAKE}:14-15"),
        Fact("The mc_mujoco configuration template sets xmlModelPath and pdGainsPath to the installed model and "
             "PD-gains paths", source="upstream_code", ref=f"{MM_CONFIG}:1-2"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:jvrc1 scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input and cap.world.reset.v1 restores the model defaults, so a run repeats exactly on the "
                     "same engine but no seed selects a different state.  The stand-in fake is deterministic in the "
                     "same sense but is not MuJoCo.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF (scene.xml includes "
            "jvrc1.xml) for the joint dimensions and the actuator list but integrates a placeholder first-order "
            "motion of each actuated joint toward its control target, so trajectories, contacts, actuator dynamics "
            "and the free-base dynamics are not MuJoCo's",
            "the model's motors set ctrllimited=false and forcelimited=false (xml/jvrc1.xml:11-13), "
            "so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound",
            "no mesh or texture is loaded and no contact, equality, tendon or sensor is resolved by the stand-in; "
            "the ten finger equality constraints of xml/jvrc1.xml:480-492 are not applied",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering is offered and no physical JVRC1 robot is modelled; nothing was validated against "
            "hardware",
        ],
    }
