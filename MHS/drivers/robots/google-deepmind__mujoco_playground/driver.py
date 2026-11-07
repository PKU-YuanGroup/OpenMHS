"""OpenMHS driver for gh.google-deepmind/mujoco_playground: the dm_control acrobot MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the acrobot scene of the card (``models[0]``,
``mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml``) and the bridge derives the whole contract from the model
it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked against the
model's ``actuator_ctrlrange`` before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The
device is simulated (R0): there is no hardware backend and no operator-required limit; the model's control range is
derived from the MJCF file itself.

The upstream is a suite of MJX environments (README.md:7).  The acrobot environment class is
``mujoco_playground._src.dm_control_suite.acrobot:Balance`` (acrobot.py:45); it loads this MJCF into
``mujoco.MjModel`` (acrobot.py:62-67) and adds the observation, reward and episode logic of a dm_control task
(acrobot.py:104-148).  This package serves the raw MuJoCo model contract, not the JAX environment: the reset restores
the model defaults and does not reproduce the environment's random qpos draw (acrobot.py:80-85).

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same model file for the actuator count, the control range, the joint dimensions and the time
step, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that
path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/google-deepmind/mujoco_playground/" + MODEL
ACROBOT = "mujoco_playground/_src/dm_control_suite/acrobot.py"
SUITE_README = "mujoco_playground/_src/dm_control_suite/README.md"
COMMON = "mujoco_playground/_src/dm_control_suite/common.py"


class Acrobot(MujocoDriver):
    device_id = "acrobot"
    model_path = MODEL_PATH
    native = "mujoco_playground._src.dm_control_suite.acrobot:Balance"
    backends = {"fake": FakeMujoco}
    display_name = "DM Control acrobot (MuJoCo Playground)"
    vendor, model = "Google DeepMind", "acrobot"
    tags = ["acrobot", "dm-control", "mujoco", "playground", "simulation", "robot"]
    facts = [
        Fact("The repository is a suite of GPU-accelerated environments for robot learning and sim-to-real, built "
             "with MuJoCo MJX", source="vendor_doc", ref="README.md:7"),
        Fact("The suite includes the classic control environments from dm_control", source="vendor_doc",
             ref="README.md:11"),
        Fact("The dm_control suite is a re-implementation of the DeepMind Control Suite using MJX",
             source="vendor_doc", ref=f"{SUITE_README}:3"),
        Fact("acrobot-swingup is one of the implemented dm_control suite environments", source="vendor_doc",
             ref=f"{SUITE_README}:12"),
        Fact("The acrobot environment class is Balance, a subclass of mjx_env.MjxEnv", source="upstream_code",
             ref=f"{ACROBOT}:45"),
        Fact("The acrobot default config sets ctrl_dt=0.01, sim_dt=0.01, episode_length=1000 and action_repeat=1",
             source="upstream_code", ref=f"{ACROBOT}:32-42"),
        Fact("The environment reads the acrobot MJCF text, builds mujoco.MjModel.from_xml_string with the suite "
             "assets and writes sim_dt to model.opt.timestep", source="upstream_code", ref=f"{ACROBOT}:62-67"),
        Fact("The suite assets are all files of the xmls/common directory, read as bytes", source="upstream_code",
             ref=f"{COMMON}:21-29"),
        Fact("The acrobot MJCF is a model named acrobot that includes the visual, skybox and materials files",
             source="upstream_code", ref=f"{MODEL}:8-11"),
        Fact("The MJCF default sets joint damping to .05 and capsule geoms of mass 1", source="upstream_code",
             ref=f"{MODEL}:13-16"),
        Fact("The MJCF sets timestep 0.01 s, iterations 2 and ls_iterations 4, with constraint and eulerdamp disabled",
             source="upstream_code", ref=f"{MODEL}:18-20"),
        Fact("The model has a floor plane, a target site at z=4 and fixed and lookat cameras", source="upstream_code",
             ref=f"{MODEL}:22-27"),
        Fact("The model has two hinge joints named shoulder and elbow, a capsule arm for each, and a tip site at the "
             "far end of the lower arm", source="upstream_code", ref=f"{MODEL}:28-37"),
        Fact("The model has one motor actuator on the elbow joint with gear 2 and ctrlrange -1 to 1",
             source="upstream_code", ref=f"{MODEL}:41"),
        Fact("The environment's reset draws every qpos value uniformly from -pi to pi",
             source="upstream_code", ref=f"{ACROBOT}:80-85"),
        Fact("The environment steps through mjx_env.step with n_substeps and reports done when qpos or qvel contains "
             "NaN", source="upstream_code", ref=f"{ACROBOT}:104-110"),
        Fact("The observation concatenates the orientation vector and the joint velocities", source="upstream_code",
             ref=f"{ACROBOT}:112-116"),
        Fact("The orientation vector is the horizontal and vertical components of the two arm body z-axes",
             source="upstream_code", ref=f"{ACROBOT}:132-148"),
        Fact("The reward is a tolerance of the tip-to-target distance with bounds 0 to target_radius",
             source="upstream_code", ref=f"{ACROBOT}:118-130"),
        Fact("The reward margin is 0.0 for the sparse variant and 1.0 for the dense variant", source="upstream_code",
             ref=f"{ACROBOT}:60"),
        Fact("The action size is the model's number of actuators nu", source="upstream_code", ref=f"{ACROBOT}:154-156"),
        Fact("The package requires Python 3.11 or newer", source="vendor_doc", ref="pyproject.toml:12"),
        Fact("The runtime dependencies include mujoco-mjx>=3.6.0 and mujoco>=3.6.0", source="vendor_doc",
             ref="pyproject.toml:24-38"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step, the lockstep clock and the snapshot support; the gaps below are this
    #: package's.  The time step 10 ms is the model's <option timestep="0.01"> (acrobot.xml:18).
    fidelity = {
        "engine": "mujoco:acrobot",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates a fixed model and control sequence deterministically, and the bridge reset "
                     "restores the model defaults (mj_resetData + mj_forward), so a run can repeat exactly on the "
                     "same engine; no seed controls the reset. The upstream environment's reset draws a random qpos "
                     "(acrobot.py:80-85); this driver serves the raw model and does not reproduce that draw.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "actuator control range and the joint dimensions but integrates a placeholder motion of the actuated "
            "joint, so trajectories, contacts, friction and actuator dynamics are not MuJoCo's",
            "the stand-in loads no mesh or texture and resolves no contact, constraint or tendon; it does not apply "
            "the elbow motor's gear ratio (acrobot.xml:41) and only exposes its ctrl range",
            "MuJoCo itself and the JAX/MJX environment were not importable where the gate ran, so no trajectory of "
            "this package was compared with the real engine or with the Balance environment",
            "the upstream environment adds an observation, a tolerance reward and a NaN episode terminator "
            "(acrobot.py:104-148) and resets qpos from a random draw (acrobot.py:80-85); this driver exposes only "
            "the raw cap.world.step/reset contract and not those environment features",
            "no physical acrobot is modelled and nothing was validated against hardware",
        ],
    }
