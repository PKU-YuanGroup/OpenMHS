"""OpenMHS driver for gh.rohanpsingh/learninghumanoidwalking: the JVRC1 scene as a MuJoCo world.

The upstream repository is a reinforcement-learning package for humanoid locomotion.  Its environments are built on
``envs.common.mujoco_env.MujocoEnv`` (``envs/common/mujoco_env.py:13``), which compiles an MJCF scene with
``mujoco.MjSpec.from_file`` and owns the ``mujoco.MjData`` that every environment steps
(``envs/common/mujoco_env.py:24-26``).  The JVRC walking environment builds its own reduced XML from the card's first
model, ``models/jvrc_mj_description/xml/scene.xml`` (``envs/jvrc/gen_xml.py:8``), so this package serves that scene
through :class:`mhs.driver.MujocoDriver`: the bridge loads the MJCF, exposes ``cap.world.step.v1`` over
``data.ctrl`` and ``cap.world.reset.v1``, and publishes the integration state (``time_ms``, ``qpos``, ``qvel``,
``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The scene's ``jvrc1`` default motor class sets ``ctrllimited="false"`` and ``forcelimited="false"``
(``xml/jvrc1.xml:13``) and no motor declares a ``ctrlrange`` (``xml/jvrc1.xml:451-492``), so the model states no
actuator control interval.  The bridge therefore publishes ``action.ctrl`` as ``operator_required``: a step that
sets a control is refused with ``MHS.SAFETY.LIMITS_UNSET`` before the native step until the deployment's
``site-limits.json`` supplies a bound, and ``site-limits.example.json`` is operator example data, not a model
value.

The device is simulated (R0): there is no hardware backend, no physical stop and no hardware run.  MuJoCo is not
installed where the gate runs and package code never imports the clone, so ``backends["fake"]`` is this package's
stand-in ``mujoco`` module (``fake.py``).  It reads the same MJCF for the joint layout, the actuator targets and the
option timestep, but its integration is a placeholder motor-driven acceleration, not MuJoCo's physics; the fidelity
``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and
loads the same file; that path was not run here.

The environment task layer of ``JvrcWalkEnv`` (action smoothing, PD control, clock and mode observations, rewards,
termination and the reduced generated XML) is NOT COVERED by this world driver; the notes and fidelity gaps say so.
Every Fact cites a text file of the clone at commit cd8c6557beadb9d25045624fb50eeb487b0e8fdd.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "models/jvrc_mj_description/xml/scene.xml"
MODEL_PATH = "../../../../robots/rohanpsingh/learninghumanoidwalking/" + MODEL
SCENE = "models/jvrc_mj_description/xml/scene.xml"
ROBOT = "models/jvrc_mj_description/xml/jvrc1.xml"
GEN_XML = "envs/jvrc/gen_xml.py"
ENV = "envs/jvrc/jvrc_walk.py"
BASE_ENV = "envs/common/base_humanoid_env.py"
MUJOCO_ENV = "envs/common/mujoco_env.py"


class Jvrc1Scene(MujocoDriver):
    device_id = "jvrc1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "JVRC1 humanoid scene (MuJoCo world)"
    vendor, model = "rohanpsingh", "jvrc_mj_description scene"
    tags = ["humanoid", "jvrc1", "mujoco", "simulation", "reinforcement-learning", "world"]
    facts = [
        Fact("The project description is training a humanoid robot for locomotion using reinforcement learning",
             source="vendor_doc", ref="pyproject.toml:4"),
        Fact("The declared simulation dependencies are dm-control>=1.0.24 and mujoco==3.4.0", source="upstream_code",
             ref="pyproject.toml:9-12"),
        Fact("The repository layout labels envs/common/mujoco_env.py as the MuJoCo simulation wrapper and models/ as "
             "the MuJoCo model files", source="vendor_doc", ref="README.md:25-32"),
        Fact("MujocoEnv is the superclass for all MuJoCo environments", source="upstream_code",
             ref=f"{MUJOCO_ENV}:13-14"),
        Fact("MujocoEnv refuses a relative model path, opens the model with mujoco.MjSpec.from_file, compiles it and "
             "creates the mujoco.MjData it owns", source="upstream_code", ref=f"{MUJOCO_ENV}:16-26"),
        Fact("MujocoEnv.reset restores the data with mujoco.mj_resetData and returns the subclass's reset_model "
             "observation", source="upstream_code", ref=f"{MUJOCO_ENV}:113-116"),
        Fact("BaseHumanoidEnv is the shared humanoid environment base on top of MujocoEnv", source="upstream_code",
             ref=f"{BASE_ENV}:19"),
        Fact("BaseHumanoidEnv.step smooths the policy action, runs robot.step and returns the observation, the "
             "summed reward, done and the reward dictionary", source="upstream_code", ref=f"{BASE_ENV}:199-227"),
        Fact("JvrcWalkEnv is the concrete JVRC walking environment and builds its XML through the jvrc builder",
             source="upstream_code", ref=f"{ENV}:13-21"),
        Fact("The jvrc builder loads its MJCF from models/jvrc_mj_description/xml/scene.xml", source="upstream_code",
             ref=f"{GEN_XML}:8"),
        Fact("The jvrc builder removes every motor whose joint is not listed in LEG_JOINTS", source="upstream_code",
             ref=f"{GEN_XML}:79-82"),
        Fact("The served MJCF scene is named 'jvrc1 scene' and includes jvrc1.xml", source="upstream_code",
             ref=f"{SCENE}:1-3"),
        Fact("The model compiles angles in radians and resolves meshes from ../meshes", source="upstream_code",
             ref=f"{ROBOT}:4"),
        Fact("The model sets option timestep 0.001 s, 50 iterations, the Newton solver, a dense Jacobian and "
             "pyramidal friction cones", source="upstream_code", ref=f"{ROBOT}:8"),
        Fact("The default motor class sets ctrllimited=\"false\" and forcelimited=\"false\"", source="upstream_code",
             ref=f"{ROBOT}:10-13"),
        Fact("The root body PELVIS_S is placed at 0 0 1.4 and carries the free joint root", source="upstream_code",
             ref=f"{ROBOT}:162-163"),
        Fact("The R_HIP_P hinge has range -2.0944 to 0.785398 rad and armature 0.1925", source="upstream_code",
             ref=f"{ROBOT}:172"),
        Fact("The L_KNEE hinge has range 0 to 2.61799 rad and armature 0.1305", source="upstream_code",
             ref=f"{ROBOT}:221"),
        Fact("The actuator section has one motor for each leg, waist, neck, arm and thumb joint and no motor for "
             "the distal finger joints", source="upstream_code", ref=f"{ROBOT}:451-492"),
        Fact("Ten equality constraints couple the five distal finger joints of each hand to its thumb",
             source="upstream_code", ref=f"{ROBOT}:436-448"),
        Fact("The sensor section reads force and torque at both feet and both hands and a gyro and accelerometer "
             "at the imu site", source="upstream_code", ref=f"{ROBOT}:494-510"),
        Fact("H1Env is a Unitree H1 standing environment", source="upstream_code", ref="envs/h1/h1_env.py:11-12"),
        Fact("The JVRC model submodule's LICENSE states BSD 2-Clause", source="vendor_doc",
             ref="models/jvrc_mj_description/LICENSE:1"),
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
            "jvrc1.xml) for the joint layout, the actuator targets and the option timestep, but integrates a "
            "placeholder acceleration from each motor control, using distinct qpos/qvel addresses and the model's "
            "default floating-base pose; it has no mass matrix, damping or coupled dynamics, so trajectories, "
            "contacts, actuator dynamics and the free-base dynamics are not MuJoCo's",
            "the model's motors set ctrllimited=false and forcelimited=false (xml/jvrc1.xml:13) and declare no "
            "ctrlrange (xml/jvrc1.xml:451-492), so the bridge publishes action.ctrl operator_required: a step that "
            "sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator "
            "example data, not a model bound",
            "no mesh or texture is loaded and no contact, equality, tendon or sensor is resolved by the stand-in; "
            "the ten finger equality constraints of xml/jvrc1.xml:436-448 are not applied",
            "the upstream environment layer is NOT COVERED: JvrcWalkEnv's reduced XML (built by envs/jvrc/gen_xml.py "
            "from this scene), its action smoothing, PD control, clock and mode observations, rewards and termination "
            "are not modelled; this driver serves the raw MJCF control vector of the card's models[0], not the "
            "environment's policy action",
            "H1Env (envs/h1/h1_env.py:11-12) and the other environment tasks are not served; the selected device "
            "is only the raw JVRC1 scene, whose model submodule has its own BSD-2-Clause LICENSE",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine or with the upstream environment",
            "no rendering is offered and no physical JVRC1 robot is modelled; nothing was validated against "
            "hardware",
        ],
    }
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:jvrc1-motor-fake",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "exact",
                "seed_control": "none",
                "notes": "the fake uses fixed model defaults and deterministic placeholder updates; no RNG or "
                         "MuJoCo trajectory comparison is involved",
            },
        },
    }
