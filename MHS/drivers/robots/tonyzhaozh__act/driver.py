"""OpenMHS driver for gh.tonyzhaozh/act: the ACT bimanual ViperX insertion scene (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene and the bridge derives the contract from the
model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [16 numbers]}}``; the runtime checks each ``ctrl``
value against the model's ``actuator_ctrlrange`` before writing ``data.ctrl``.  ``cap.world.reset.v1`` restores the
model defaults (``mj_resetData`` + ``mj_forward``).  The world state is ``{time_ms, qpos, qvel, ctrl, tick,
timestep_ms, seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The card lists four scene models.  This package serves ``assets/bimanual_viperx_insertion.xml`` (the joint-space
insertion scene) because the bridge drives ``data.ctrl``: that model has a position actuator for the six joints and two
finger slides of each arm.  The end-effector scenes have only the four finger actuators and move the arms through
mocap bodies (``ee_sim_env.py:63-74``), which the bridge does not expose.

The gate cannot import MuJoCo where it runs, so the ``fake`` backend is the package's own stand-in ``mujoco`` module
(fake.py).  It reads the include-expanded MJCF for the actuator control ranges and the joint dimensions, but its
integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends`` does
not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package and
never imported).  Every Fact cites a line of the clone at commit 742c753c0d4a5d87076c8f69e5628c79a8cc5488.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "assets/bimanual_viperx_insertion.xml"
SCENE = "assets/scene.xml"
SIM_ENV = "sim_env.py"
CONSTANTS = "constants.py"
EE_ENV = "ee_sim_env.py"
EE_MODEL = "assets/bimanual_viperx_ee_insertion.xml"
#: The card's scene models[2], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/tonyzhaozh/act/" + MODEL


class ActBimanualViperX(MujocoDriver):
    device_id = "act"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "ACT bimanual ViperX insertion scene (MuJoCo model)"
    vendor, model = "Tony Z. Zhao", "ACT bimanual ViperX insertion"
    tags = ["act", "aloha", "bimanual", "insertion", "manipulation", "mujoco", "simulation", "viperx"]
    facts = [
        Fact("The insertion scene is the MJCF file bimanual_viperx_insertion.xml; its root element is <mujoco> and "
             "it includes scene.xml and vx300s_dependencies.xml", source="upstream_code", ref=f"{MODEL}:1-3"),
        Fact("The scene includes the left and right ViperX arm bodies from vx300s_left.xml and vx300s_right.xml",
             source="upstream_code", ref=f"{MODEL}:5-6"),
        Fact("The scene adds a free peg body and a free socket body, each with a free joint", source="upstream_code",
             ref=f"{MODEL}:8-23"),
        Fact("The actuator section lists a position actuator for the six joints and two finger slides of each arm; "
             "the control ranges are waist +-3.14158, shoulder -1.85005 to 1.25664, elbow -1.76278 to 1.6057, "
             "forearm_roll +-3.14158, wrist_angle -1.8675 to 2.23402, wrist_rotate +-3.14158, left_finger 0.021 to "
             "0.057 and right_finger -0.057 to -0.021", source="upstream_code", ref=f"{MODEL}:27-44"),
        Fact("The keyframe stores 30 qpos values: the 16 arm and finger values, seven for the peg and seven for the "
             "socket", source="upstream_code", ref=f"{MODEL}:48-49"),
        Fact("The upstream joint-space insertion environment loads bimanual_viperx_insertion.xml", source="upstream_code",
             ref=f"{SIM_ENV}:44-46"),
        Fact("The upstream control timestep is DT = 0.02 s", source="upstream_code", ref=f"{CONSTANTS}:36"),
        Fact("The insertion environment is built with control_timestep=DT and time_limit=20", source="upstream_code",
             ref=f"{SIM_ENV}:48"),
        Fact("The upstream joint-space action is 14 values: six left arm joints, one left gripper, six right arm "
             "joints and one right gripper", source="upstream_code", ref=f"{SIM_ENV}:23-26"),
        Fact("The task expands each normalized gripper action into two finger control values before stepping the "
             "model", source="upstream_code", ref=f"{SIM_ENV}:67-70"),
        Fact("The insertion task initialises qpos[:16] to START_ARM_POSE and copies START_ARM_POSE into data.ctrl",
             source="upstream_code", ref=f"{SIM_ENV}:180-181"),
        Fact("START_ARM_POSE has 16 values, eight per arm", source="upstream_code", ref=f"{CONSTANTS}:38"),
        Fact("The only <option> in the scene is commented out, so the model sets no active integration timestep",
             source="upstream_code", ref=f"{SCENE}:2"),
        Fact("The end-effector insertion scene has only the four finger actuators", source="upstream_code",
             ref=f"{EE_MODEL}:45-50"),
        Fact("The end-effector task drives the arms through mocap positions and quaternions and writes only four "
             "gripper values to data.ctrl", source="upstream_code", ref=f"{EE_ENV}:63-74"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:bimanual_viperx_insertion",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge resets to the "
                     "model defaults and its cap.world.reset.v1 seed input is not used, so a run repeats exactly on "
                     "the same engine but no seed selects a different trajectory",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the include-expanded MJCF "
            "for the actuator control ranges and the joint dimensions but integrates a placeholder first-order "
            "motion of each actuated joint toward its control target, so contacts, mesh geometry, actuator "
            "dynamics and the free peg and socket bodies are not MuJoCo's",
            "the bridge exposes the raw 16-value actuator ctrl and the model's qpos/qvel; the upstream joint-space "
            "task takes a 14-value action and expands each gripper to two finger positions (sim_env.py:58-71), sets "
            "START_ARM_POSE and BOX_POSE on reset (sim_env.py:180-183), and adds the task reward, camera images and "
            "20 s time limit (sim_env.py:48); that task layer is not served",
            "the model sets no active <option timestep> (assets/scene.xml:2 is commented out), so the integration "
            "step is the engine's default; the fake uses a placeholder step, not a model fact",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the fake does not load the STL meshes or resolve contacts, equality constraints or tendons",
            "no physical ViperX or ALOHA robot is modelled and nothing was validated against hardware",
        ],
    }
