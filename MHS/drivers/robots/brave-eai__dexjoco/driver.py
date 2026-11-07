"""OpenMHS driver for gh.brave-eai/dexjoco: the DexJoCo bimanual-assembly MuJoCo scene.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary MJCF scene
(``models[0]``, ``arena_arm_hand_bimanual_assembly.xml``) and the bridge derives the whole contract from the model
it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked against
the model's ``actuator_ctrlrange`` before it is written to ``data.ctrl`` and ``mj_step`` runs ``ticks`` times.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no operator-required limit.  The scene is the
bimanual Panda + Allegro arena the assembly task is built on: the assembly environment loads exactly this file
(``panda_bimanual_assembly_env.py:17`` and ``:52-53``) through ``MujocoGymEnv``, which loads it with
``mujoco.MjModel.from_xml_path`` and creates ``mujoco.MjData`` (``mujoco_gym_env.py:30-33``).  This package serves
that MJCF scene, not the task wrapper's sampled reset, pose-plus-hand action mapping, success predicate or camera
observations (the fidelity ``gaps`` say so).

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  Every Fact cites a line of the clone at commit ``8d23b0fab23b17a58c4b55f3942e17013aaf8267``.  MuJoCo is
not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py): it
reads the same MJCF text for the actuator control ranges and the qpos/qvel dimensions, but its integration is a
placeholder, not MuJoCo's physics.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same file; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "dexjoco/dexjoco/sim/envs/xmls/arena_arm_hand_bimanual_assembly.xml"
BIMANUAL = "dexjoco/dexjoco/sim/envs/xmls/panda_allegro_bimanual.xml"
RIGHT = "dexjoco/dexjoco/sim/envs/xmls/panda_allegro_right.xml"
LEFT = "dexjoco/dexjoco/sim/envs/xmls/panda_allegro_left.xml"
PEG = "dexjoco/dexjoco/sim/envs/xmls/industreal_round_peg_8mm.xml"
TRAY = "dexjoco/dexjoco/sim/envs/xmls/industreal_tray_insert_round_peg_8mm.xml"
ENV = "dexjoco/dexjoco/sim/envs/panda_bimanual_assembly_env.py"
BASE_ENV = "dexjoco/dexjoco/sim/mujoco_gym_env.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/brave-eai/dexjoco/" + MODEL


class DexJoCoAssembly(MujocoDriver):
    device_id = "dexjoco-bimanual-assembly"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "DexJoCo bimanual assembly (MuJoCo scene)"
    vendor, model = "Brave EAI", "Arena_Allegro_Bimanual_Assembly"
    tags = ["dexjoco", "bimanual", "dexterous-manipulation", "panda", "allegro", "mujoco", "simulation"]
    facts = [
        Fact("DexJoCo is a MuJoCo-based simulation benchmark and toolkit for task-oriented dexterous manipulation "
             "with 11 functionally grounded tasks", source="vendor_doc", ref="README.md:16-17"),
        Fact("The card's main model is the MJCF scene arena_arm_hand_bimanual_assembly.xml, whose root element is "
             "'<mujoco model=\"Arena_Allegro_Bimanual_Assembly\">'", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The assembly scene includes panda_allegro_bimanual.xml, industri_round_peg_8mm.xml and "
             "industreal_tray_insert_round_peg_8mm.xml", source="upstream_code", ref=f"{MODEL}:3-5"),
        Fact("panda_allegro_bimanual.xml includes panda_allegro_right.xml and panda_allegro_left.xml",
             source="upstream_code", ref=f"{BIMANUAL}:3-4"),
        Fact("The assembly scene sets the physics timestep to 0.002 s", source="upstream_code", ref=f"{MODEL}:7"),
        Fact("The assembly environment defines _XML_PATH as xmls/arena_arm_hand_bimanual_assembly.xml",
             source="upstream_code", ref=f"{ENV}:17"),
        Fact("The assembly environment passes _XML_PATH as xml_path to MujocoGymEnv", source="upstream_code",
             ref=f"{ENV}:52-53"),
        Fact("MujocoGymEnv loads the MJCF with mujoco.MjModel.from_xml_path and creates the data with mujoco.MjData",
             source="upstream_code", ref=f"{BASE_ENV}:30-33"),
        Fact("MujocoGymEnv sets the model time step from its physics_dt argument", source="upstream_code",
             ref=f"{BASE_ENV}:34"),
        Fact("The right arm has seven motor actuators: joints 1 to 4 have ctrlrange -87 to 87 and joints 5 to 7 "
             "have ctrlrange -12 to 12", source="upstream_code", ref=f"{RIGHT}:480-486"),
        Fact("The right hand has sixteen position actuators, four per finger, whose control ranges come from their "
             "default classes", source="upstream_code", ref=f"{RIGHT}:488-503"),
        Fact("The right hand control ranges are base -0.47 to 0.47, proximal -0.196 to 1.61, medial -0.174 to "
             "1.709, distal -0.227 to 1.618, thumb base 0.263 to 1.396, thumb proximal -0.105 to 1.163, thumb "
             "medial -0.189 to 1.644 and thumb distal -0.162 to 1.719", source="upstream_code",
             ref=f"{RIGHT}:117-148"),
        Fact("The left model declares the same seven motor actuators and sixteen position actuators",
             source="upstream_code", ref=f"{LEFT}:530-557"),
        Fact("The left hand control ranges are base -0.47 to 0.47, proximal -0.196 to 1.61, medial -0.174 to "
             "1.709, distal -0.227 to 1.618, thumb base 0.263 to 1.396, thumb proximal -0.105 to 1.163, thumb "
             "medial -0.189 to 1.644 and thumb distal -0.162 to 1.719", source="upstream_code",
             ref=f"{LEFT}:120-151"),
        Fact("The peg is a free body: its body element contains a freejoint", source="upstream_code",
             ref=f"{PEG}:13-16"),
        Fact("The tray insert is a free body: its body element contains a freejoint", source="upstream_code",
             ref=f"{TRAY}:13-14"),
        Fact("The scene has two mocap target bodies, target_right and target_left", source="upstream_code",
             ref=f"{MODEL}:126-131"),
        Fact("The assembly environment's reset samples the peg and socket positions, rotates their yaw and sets the "
             "Panda and Allegro home poses instead of the model defaults", source="upstream_code",
             ref=f"{ENV}:359-391"),
        Fact("The assembly environment's step takes a right and a left 23-value vector, a 7-value pose plus 16 hand "
             "commands per arm", source="upstream_code", ref=f"{ENV}:432-455"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the scene as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:Arena_Allegro_Bimanual_Assembly",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from the model defaults; the driver takes no "
                     "seed, so a reset always returns to the same model state and a run repeats on the same engine. "
                     "The fake backend is a deterministic stand-in, not MuJoCo.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the scene's MJCF text for "
            "the actuator control ranges, the free-joint layout and the qpos/qvel dimensions, but integrates a "
            "placeholder first-order motion of each actuated joint toward its control target; it loads no mesh, "
            "texture, camera or sensor and resolves no contact, equality, tendon or actuator constraint",
            "the driver serves the MJCF scene directly; the upstream task environment wraps it with a sampled "
            "reset (random peg and socket poses and table height), a 23-value pose-plus-hand vector per arm "
            "converted to actuator controls, a success predicate and camera observations "
            "(panda_bimanual_assembly_env.py:359-391, :432-455, :214-238); that task layer is not served",
            "a reset restores the model defaults with mj_resetData and takes no seed, so it does not reproduce the "
            "environment's sampled start state or its domain randomization",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the fake module does not implement mj_getState/mj_setState, so on the fake backend the bridge uses "
            "its time/qpos/qvel/ctrl snapshot rather than MuJoCo's full integration-state snapshot",
            "no physical Panda or Allegro hardware is modelled and nothing was validated against it",
        ],
    }
