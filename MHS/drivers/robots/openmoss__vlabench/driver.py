"""OpenMHS driver for gh.openmoss/vlabench: the xArm7 MuJoCo scene of the VLABench clone (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names an MJCF scene of the card and the bridge derives the
whole contract from the model it loads.  The card lists two robot scenes (``models[0]`` the Franka panda scene and
``models[1]`` the xArm7 scene); this package serves ``models[1]`` because every one of its eight actuators states a
``ctrlrange`` (``xarm7.xml:33`` and ``:173-179``), while the panda model leaves its seven arm actuators without a
control range.  The step action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange``, and the
state is the integration state of the model plus the tick count; ``cap.world.reset.v1`` resets the data to the model
defaults.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The card's entry symbol is an environment wrapper, ``VLABench.envs.dm_env:LM4ManipDMEnv`` (a dm_control composer
Environment), not a model file: the MuJoCo family serves the listed MJCF scene, so the bridge's native object is the
``mujoco`` library and the package does not load the upstream environment or its task scene.  The model file is read
from the read-only clone at the pinned commit; neither the model nor its mesh assets are copied into this package and
the clone is never imported or run.

The gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the model shape (actuator count, control ranges, joint count, time step)
but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run
here.  Every Fact cites a line of the clone at commit cf588fe60c0c7282174fe979f5913170cfe69017.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "VLABench/assets/robots/xarm7/xarm7.xml"
SCENE = "VLABench/assets/robots/xarm7/scene.xml"
CONFIG = "VLABench/configs/robot_config.json"
DM_ENV = "VLABench/envs/dm_env.py"
ENV_FACTORY = "VLABench/envs/__init__.py"
#: The card's models[1], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/openmoss/vlabench/" + SCENE


class VLABenchXArm7(MujocoDriver):
    device_id = "vlabench-xarm7"
    model_path = MODEL_PATH
    native = "VLABench.envs.dm_env:LM4ManipDMEnv"
    backends = {"fake": FakeMujoco}
    display_name = "VLABench xArm7 (MuJoCo scene)"
    vendor, model = "OpenMoss", "VLABench xArm7"
    tags = ["vlabench", "xarm7", "manipulation", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The card's entry symbol LM4ManipDMEnv is a dm_control composer.Environment subclass that overrides "
             "reset and step", source="upstream_code", ref=f"{DM_ENV}:7-41"),
        Fact("The card lists the xarm7 scene as models[1]: its root is '<mujoco model=\"xarm7 scene\">' and it "
             "includes xarm7.xml", source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The xarm7 model root is '<mujoco model=\"xarm7\">' and its compiler sets autolimits=true",
             source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The robot config maps the xarm robot to xarm7/xarm7.xml and gives it 8 default_qpos values",
             source="upstream_code", ref=f"{CONFIG}:8-12"),
        Fact("The model sets no option timestep: its <option> element carries only integrator=implicitfast",
             source="upstream_code", ref=f"{MODEL}:4"),
        Fact("The model has 8 actuators: act1 to act7 on the seven arm joints and a gripper actuator on the split "
             "tendon", source="upstream_code", ref=f"{MODEL}:171-180"),
        Fact("The default class xarm7 states a general ctrlrange of -6.28319 to 6.28319 for the arm actuators",
             source="upstream_code", ref=f"{MODEL}:30-33"),
        Fact("act2 states ctrlrange -2.059 to 2.0944, act4 -0.19198 to 3.927, act6 -1.69297 to 3.14159 and the "
             "gripper 0 to 255", source="upstream_code", ref=f"{MODEL}:173-179"),
        Fact("The model has 13 hinge joints: joint1 to joint7, the left and right driver, finger and inner-knuckle "
             "joints", source="upstream_code", ref=f"{MODEL}:64-136"),
        Fact("The gripper tendon couples the left and right driver joints with coef 0.5", source="upstream_code",
             ref=f"{MODEL}:158-161"),
        Fact("The scene adds a floor plane and a cylindrical pad to the xarm7 model", source="upstream_code",
             ref=f"{SCENE}:19-22"),
        Fact("The env factory loads the robot from robot_config and constructs LM4ManipDMEnv(task, time_limit, "
             "reset_wait_step)", source="upstream_code", ref=f"{ENV_FACTORY}:42-54"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the model integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:xarm7",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state, but the bridge takes no "
                     "seed input and a reset restores the model defaults, so no seed selects a different initial "
                     "state; the fake's placeholder integration was not compared with the engine",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF text for the "
            "actuator control ranges, the joint count and the time step, but integrates a placeholder first-order "
            "motion of each actuated joint toward its control target; no contact, tendon, equality or actuator "
            "dynamics and no mesh or texture is loaded",
            "the model sets no option timestep (xarm7.xml:4); the stand-in uses 0.002 s as a placeholder for the "
            "library default, so the reference's timestep_ms is a stand-in value, not a measurement",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the package serves the xarm7 MuJoCo model, not the dm_control environment LM4ManipDMEnv or a task "
            "scene: rendering, the environment's rgb/depth/segmentation/point-cloud observations, the reset wait "
            "steps and the random layout of the environment are not modelled",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical robot is modelled and nothing was validated against the xArm hardware",
        ],
    }
