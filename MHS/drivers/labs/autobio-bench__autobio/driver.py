"""OpenMHS driver for gh.autobio-bench/autobio: the DexHand021 right hand MJCF (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's first model
(``autobio/model/hand/dexhand021_right.xml``, ``models[0]``) and the bridge derives the contract from the model it
loads.  The step action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (twelve position
actuators); the world state is the integration state of the model (``time``, ``qpos``, ``qvel``, ``ctrl``) plus the
tick count, and ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.

The device is simulated (R0): the model is a MuJoCo simulation asset, there is no hardware backend, and no
operator-required limit is declared.  MuJoCo is not installed and cannot be installed where the acceptance gate runs
(no network, no pip), so the ``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It reads the
same model file for the joint shape, the twelve actuators, their explicit control ranges and the 10 ms option step,
but its integration is a placeholder first-order motion, not MuJoCo's physics; the fidelity ``gaps`` say so.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file;
that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line or line range of the clone at commit
08504213356cbfe9a82bcd33a43cd282945a45df.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under labs/ at the pinned commit.
MODEL = "autobio/model/hand/dexhand021_right.xml"
MODEL_PATH = "../../../../labs/autobio-bench/autobio/" + MODEL
README = "README.md"
AUTOBIO_README = "autobio/README.md"


class AutobioDexhand(MujocoDriver):
    device_id = "autobio-dexhand021-right"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "AutoBio DexHand021 right hand (MuJoCo model)"
    vendor, model = "AutoBio", "DexHand021 right"
    tags = ["autobio", "dexhand", "dexhand021", "hand", "mujoco", "robot", "simulation"]
    facts = [
        Fact("AutoBio is a simulation and benchmark for robotic automation in a digital biology laboratory",
             source="vendor_doc", ref=f"{README}:3"),
        Fact("The autobio package installs mujoco==3.3.0 and its model/ folder holds simulation-ready lab assets and "
             "scenes in the MJCF language", source="vendor_doc", ref=f"{AUTOBIO_README}:12-20"),
        Fact("The served model is 'dexhand021_right_sim'", source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model uses radian angles, resolves its meshes from ../../assets and uses autolimits; its option "
             "element sets the implicitfast integrator, a 0.01 s timestep, an elliptic cone and impratio 10",
             source="upstream_code", ref=f"{MODEL}:3-5"),
        Fact("The base body rh_base carries no joint, so the hand is fixed to the world frame",
             source="upstream_code", ref=f"{MODEL}:37-40"),
        Fact("The hand has 19 hinge joints: four for the thumb, index, ring and little finger and three for the "
             "middle finger", source="upstream_code", ref=f"{MODEL}:42-144"),
        Fact("Every joint range starts at zero; for example rh_thj1 is 0 to 2.2 rad and rh_ffj1 is 0 to 0.3 rad",
             source="upstream_code", ref=f"{MODEL}:42-65"),
        Fact("Seven equality constraints couple joint pairs; the ring and little finger base joints are tied to the "
             "index base joint with polycoef '0 1' and '0 2'", source="upstream_code", ref=f"{MODEL}:201-205"),
        Fact("The model has twelve position actuators: seven act on joints and five act on tendon transmissions",
             source="upstream_code", ref=f"{MODEL}:208-220"),
        Fact("Each actuator has an explicit ctrlrange; rh_thj1 is 0 to 2.2, rh_fft1 is 0 to 0.3, and the other "
             "actuators are 0 to 1.3", source="upstream_code", ref=f"{MODEL}:209-220"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:dexhand021_right_sim",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge "
                     "accepts a seed in cap.world.reset.v1 but does not use it, and a reset restores the model "
                     "defaults, so one ctrl sequence repeats a trajectory on the same engine.  The package's fake "
                     "is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model for the 19 hinge "
            "joints, the twelve position actuators, their explicit ctrlranges and the 0.01 s option step, then moves "
            "each directly actuated joint by a placeholder fraction of the remaining distance to its control target; "
            "it computes no inertia, torque, contact, friction, equality or actuator dynamics and so produces no "
            "MuJoCo trajectory",
            "the stand-in has no transmission model: the five tendon actuators keep their ctrl values but move no "
            "joint, and the seven equality constraints, joint damping, armature and frictionloss defaults, joint "
            "ranges and actuator force ranges are not applied",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; the hand base is fixed "
            "and the model has no free joint",
            "the fake reset restores zeros and ignores the reset seed; a real MjData reset restores the model's own "
            "qpos0, which this package did not inspect",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the stand-in does not implement mj_getState/mj_setState, so a snapshot on the fake uses the bridge's "
            "time/qpos/qvel/ctrl fallback rather than MuJoCo's full integration-state snapshot",
            "no physical DexHand021 is modelled and nothing was validated against hardware; only the right hand is "
            "served, not the card's other hand models or the vortex mixer model",
        ],
    }
