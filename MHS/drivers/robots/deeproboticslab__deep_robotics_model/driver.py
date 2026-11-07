"""OpenMHS driver for gh.deeproboticslab/deep_robotics_model: the Lite3 quadruped MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary model, ``models[0]``
``Lite3/mjcf/Lite3.xml``, and the bridge derives the whole contract from the model it loads.  The step action is
``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange`` (12 torque motors, three per leg); the
bridge writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves ``cap.world.reset.v1`` with ``mj_resetData``
and ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): the upstream is a collection of robot description files, not a hardware SDK or a
control loop, and this package exposes only the Lite3 MJCF.  There is no hardware backend, no physical stop path and
no operator-required limit; the model file is the system of record for the control envelope.

MuJoCo is not installed where the acceptance gate runs (no network, no pip), so ``backends["fake"]`` is this
package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the integration step, the coordinate
counts and the per-actuator control ranges, but its integration is a placeholder, not MuJoCo's physics; the fidelity
``gaps`` below state every difference.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and never
imported).  Every Fact cites a line of the clone at commit 75824b516ecc8fa3f8f7ce5d6577e1e86d6b614f.  This package
is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "Lite3/mjcf/Lite3.xml"
MODEL_PATH = "../../../../robots/deeproboticslab/deep_robotics_model/" + MODEL
README = "README.md"


class Lite3(MujocoDriver):
    device_id = "lite3"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Deep Robotics Lite3 (MuJoCo)"
    vendor, model = "Deep Robotics", "Lite3"
    tags = ["mujoco", "lite3", "deep-robotics", "quadruped", "robot", "simulation"]
    facts = [
        Fact("The repository holds 3D models for eight Deep Robotics robots (Lite3, M20, M20S, X30, M20_Piper, "
             "DR02 Pro, DR02 Standard and S10) in MJCF, URDF and, where available, USD formats",
             source="vendor_doc", ref=f"{README}:3"),
        Fact("The bundled models are low-resolution; high-resolution models are distributed separately",
             source="vendor_doc", ref=f"{README}:5"),
        Fact("The Lite3 model is an MJCF document whose root element is <mujoco model=\"Lite3\">",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model's compiler settings declare radian angles and autolimits",
             source="upstream_code", ref=f"{MODEL}:18-19"),
        Fact("The torso is a body at 0 0 1 m with childclass robot and a freejoint named floating_base",
             source="upstream_code", ref=f"{MODEL}:48-49"),
        Fact("The torso inertial has mass 5.6056 kg", source="upstream_code", ref=f"{MODEL}:51"),
        Fact("The front-left leg's HipX, HipY and Knee hinges have ranges -0.523 to 0.523, -2.67 to 0.314 and "
             "0.524 to 2.792 rad", source="upstream_code", ref=f"{MODEL}:55-65"),
        Fact("The other three legs declare the same three joint ranges, so the model has four legs with three "
             "hinge joints each", source="upstream_code", ref=f"{MODEL}:78-146"),
        Fact("The actuator section declares 12 motor actuators, three per leg, named <leg>_<joint>_ctrl",
             source="upstream_code", ref=f"{MODEL}:153-166"),
        Fact("Every Lite3 actuator has gear 1 and ctrlrange -30 to 30", source="upstream_code",
             ref=f"{MODEL}:154-165"),
        Fact("The model references STL meshes for the torso, hip, thigh and shank from its meshes directory",
             source="upstream_code", ref=f"{MODEL}:27-39"),
        Fact("The model excludes contacts between the torso and each hip and between each leg's adjacent bodies",
             source="upstream_code", ref=f"{MODEL}:168-185"),
        Fact("The model declares two track cameras, front_camera and side_camera", source="upstream_code",
             ref=f"{MODEL}:148-149"),
        Fact("The sensor section declares framepos, framequat, framelinvel, frameangvel, velocimeter, "
             "accelerometer and gyro sensors", source="upstream_code", ref=f"{MODEL}:187-195"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the world state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:Lite3",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the bridge takes no "
                     "seed input and a reset restores the model defaults, so no seed selects a different state.  "
                     "The package's fake backend is deterministic too, but its placeholder motion is not the "
                     "engine's physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses Lite3/mjcf/Lite3.xml for "
            "the 19 qpos and 18 dof coordinates and the 12 motor ctrlranges, then treats each control as a direct "
            "joint acceleration; it computes no inertias, contacts, friction, joint limits, gear or actuator "
            "dynamics, so no trajectory here is a MuJoCo result",
            "the MJCF states no option timestep (Lite3.xml:18-19 carry only compiler settings), so the 0.002 s "
            "step is MuJoCo's library default; the bridge publishes the stand-in value, and no trajectory was "
            "compared with the engine",
            "the stand-in loads no STL mesh or texture: the torso, hip, thigh and shank meshes under "
            "Lite3/mjcf/meshes are not loaded and the contacts of Lite3.xml:168-185 are not resolved",
            "the bridge's reset calls mj_resetData and starts from the model defaults (zero qpos in the stand-in), "
            "not from the floating-base pose at Lite3.xml:48-49; the model declares no keyframe",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the step only",
            "no rendering, cameras or sensor publication: the front_camera and side_camera of Lite3.xml:148-149 "
            "and the seven sensors of Lite3.xml:187-195 are not exposed, only the bridge's time, qpos, qvel and "
            "ctrl state is served",
            "one package serves one device: the driver and fake use models[0], Lite3/mjcf/Lite3.xml; the clone's "
            "M20, M20S, M20_Piper, S10, X30 and two DR02 models are not served",
            "the bundled model is a low-resolution simulation asset: no physical Lite3 is modelled or controlled "
            "and nothing here was validated against the hardware",
        ],
    }
