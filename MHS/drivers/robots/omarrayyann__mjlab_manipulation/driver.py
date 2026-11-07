"""OpenMHS driver for gh.omarrayyann/mjlab_manipulation: the Droid MJCF model as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model (``models[0]``,
``src/mjlab_manipulation/robots/droid/xmls/droid.xml``) and the bridge derives the whole contract from the model it
loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; every ``ctrl`` element is checked against the
model's ``actuator_ctrlrange`` (the seven position actuators inherit their joint ranges through the ``arm`` default
class) before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores
the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state
(``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R0): there
is no hardware backend, no e-stop path to a machine and no operator-required limit; the control envelope is the
model's own.

The repository is a collection of manipulation tasks built with mjlab (README.md:3).  Its five bare-arm MJCF models
are Droid, xArm, Kuka, Gen3 and UR5e (README.md:26), each with a constants file that carries the home pose and the
tool-attach offset (README.md:50); a gripper is attached at task time and is not part of a bare-arm model
(README.md:49).  This package serves the card's first model, ``droid.xml``; the other models are other devices and are
not served here.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same MJCF file for the joint dimensions, the actuator control ranges and the option time
step, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same model
file; that path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.

Every Fact cites a line of the clone at the pinned commit 7564cd633f4e13bb20a11b0c9f2ff187231cef8a.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "src/mjlab_manipulation/robots/droid/xmls/droid.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/omarrayyann/mjlab_manipulation/" + MODEL
DROID = "src/mjlab_manipulation/robots/droid/droid_constants.py"
TOOLS = "src/mjlab_manipulation/robots/tools.py"
README = "README.md"
PYPROJECT = "pyproject.toml"


class MjlabDroid(MujocoDriver):
    device_id = "mjlab-droid"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "mjlab manipulation Droid (MuJoCo simulation)"
    vendor, model = "omarrayyann", "mjlab_manipulation Droid / franka_droid"
    tags = ["mujoco", "simulation", "manipulation", "robot-arm", "droid", "franka", "mjlab", "world-sim"]
    facts = [
        Fact("The repository is a collection of manipulation tasks built with mjlab", source="vendor_doc",
             ref=f"{README}:3"),
        Fact("The task table lists a Reach task that moves the gripper to a target and a Lift task that lifts a cube "
             "(state-based)", source="vendor_doc", ref=f"{README}:9-10"),
        Fact("The task table also lists a vision-based Lift-RGB task and a Lift-Any-RGB task over 12 objaverse "
             "objects", source="vendor_doc", ref=f"{README}:17-18"),
        Fact("The robot placeholder {Robot} is one of Droid, xArm, Kuka, Gen3 or UR5e", source="vendor_doc",
             ref=f"{README}:26"),
        Fact("Each robot is a bare-arm MJCF under robots/<name>/xmls/; no gripper is part of it because a gripper is "
             "attached at task time", source="vendor_doc", ref=f"{README}:49"),
        Fact("Each robot's constants file returns a RobotCfg with the home pose and the tool-attach offset",
             source="vendor_doc", ref=f"{README}:50"),
        Fact("The robot MJCF models are sourced from MuJoCo Menagerie", source="vendor_doc", ref=f"{README}:55"),
        Fact("The project depends on mjlab", source="upstream_code", ref=f"{PYPROJECT}:7-9"),
        Fact("The package registers the mjlab.tasks entry point named mjlab_manipulation", source="upstream_code",
             ref=f"{PYPROJECT}:51-52"),
        Fact("The MJCF model is named franka_droid", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model compiles its angles in radians", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model uses the implicitfast integrator", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The arm default class gives its joints armature 0.1 and damping 1 and gives its position actuators "
             "inheritrange 1", source="upstream_code", ref=f"{MODEL}:13-15"),
        Fact("joint_1 has the range -2.7437 to 2.7437 rad", source="upstream_code", ref=f"{MODEL}:96"),
        Fact("joint_2 has the range -1.7837 to 1.7837 rad", source="upstream_code", ref=f"{MODEL}:102"),
        Fact("joint_3 has the range -2.9007 to 2.9007 rad", source="upstream_code", ref=f"{MODEL}:108"),
        Fact("joint_4 has the range -3.0421 to -0.1518 rad", source="upstream_code", ref=f"{MODEL}:115"),
        Fact("joint_5 has the range -2.8065 to 2.8065 rad", source="upstream_code", ref=f"{MODEL}:122"),
        Fact("joint_6 has the range 0.5445 to 4.5169 rad", source="upstream_code", ref=f"{MODEL}:130"),
        Fact("joint_7 has the range -3.0159 to 3.0159 rad", source="upstream_code", ref=f"{MODEL}:143"),
        Fact("The model has seven position actuators named joint_1 to joint_7, with kp 4500 and kv 450 for joint_1 "
             "and joint_2, kp 3500 and kv 350 for joint_3 and joint_4, and kp 2000 and kv 200 for joint_5 to "
             "joint_7", source="upstream_code", ref=f"{MODEL}:160-167"),
        Fact("Droid's ARM_ACTUATORS covers joint_1 to joint_7", source="upstream_code", ref=f"{DROID}:19-21"),
        Fact("Droid's ARM_HOME places the base at (0, 0, 0.5) and sets joint_2, joint_4 and joint_6 to -1/5*pi, "
             "-4/5*pi and 3/5*pi radians", source="upstream_code", ref=f"{DROID}:23-33"),
        Fact("Droid's robot config attaches the tool to link_7 at position (0, 0, 0.107) with quaternion "
             "(0.7071068, 0, 0, 0.7071068)", source="upstream_code", ref=f"{DROID}:54-56"),
        Fact("The attached gripper actuator targets the split tendon with a position command", source="upstream_code",
             ref=f"{TOOLS}:12-16"),
        Fact("The gripper is attached at the robot's tool-attach frame with the gripper/ prefix", source="upstream_code",
             ref=f"{TOOLS}:39-51"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:franka_droid",
        "fidelity_level": "F1",
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the MJCF text for the joint "
            "dimensions, the actuator control ranges and the option time step, but it integrates a placeholder "
            "motion of each actuated joint and does not run MuJoCo's dynamics",
            "the stand-in loads no mesh, material or collision shape and resolves no contact, equality, tendon or "
            "sensor constraint; the model's meshes and the gripper that the tasks attach at task time are not "
            "simulated",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "only the card's models[0], droid.xml, is served; gen3.xml, kuka.xml, ur5e.xml and xarm/hand.xml (plus "
            "xarm/xarm.xml and the Robotiq 2f85 gripper) are other robot models and are not part of this driver",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's time step only",
            "snapshot and restore use the bridge fallback that copies the time, qpos, qvel and ctrl arrays and the "
            "tick count, because the stand-in has no integration-state snapshot; a restore reproduces those arrays "
            "but no derived MuJoCo quantity",
            "the model sets no <option timestep>; the stand-in uses MuJoCo's library default, a placeholder, and the "
            "bridge reports that value",
            "no physical robot is modelled, there is no viewer or rendering, and nothing was validated against Droid "
            "hardware",
        ],
    }
