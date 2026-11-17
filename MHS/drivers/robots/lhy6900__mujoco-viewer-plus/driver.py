"""OpenMHS driver for gh.lhy6900/mujoco-viewer-plus: the Unitree G1 MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's model (``models[0]``,
``deploy_robot/assets/mjcf/g1.xml``) and the bridge derives the whole contract from the model it loads.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``: the control vector is checked against the model's
``actuator_ctrlrange`` before ``data.ctrl`` is written, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1``
restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration
state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit of a physical device.

The model declares one ``motor`` actuator per actuated joint and no ``ctrlrange`` (``g1.xml:386-416``), so the
bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets it
(``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the deployment's ``site-limits.json`` bounds it.
``site-limits.example.json`` is operator example data, not a bound of the model.

MuJoCo is not installed where the acceptance gate runs and cannot be installed here (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (``fake.py``).  It parses the same MJCF file for
the joint dimensions, the actuator count, the actuator joint targets, the absent control ranges and the option
time step, but its integration is a placeholder motion, not MuJoCo's physics; the fidelity ``gaps`` list every
difference, including that the bridge writes ``data.ctrl`` directly while the upstream computes a PD torque from
joint commands and runs ten physics steps per control step.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.  The model file
is read from the read-only clone at the pinned commit and is never copied into this package or imported.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "deploy_robot/assets/mjcf/g1.xml"
MODEL_PATH = "../../../../robots/lhy6900/mujoco-viewer-plus/" + MODEL
README = "README.md"
SIMULATOR = "deploy_robot/sim/mujoco_simulator.py"
ENV = "deploy_robot/sim/mujoco_env.py"
CONFIG = "deploy_robot/sim/config/g1.py"
CONSTANTS = "deploy_robot/g1/constants.py"
SCRIPT = "scripts/run_robot_sim.py"
HARDWARE = "deploy_robot/g1/g1.py"


class MujocoViewerPlus(MujocoDriver):
    device_id = "unitree-g1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 humanoid (MuJoCo simulation)"
    vendor, model = "lhy6900", "g1"
    tags = ["g1", "humanoid", "mujoco", "simulation", "unitree", "viewer"]
    facts = [
        Fact("The README starts model simulation with scripts/run_robot_sim.py", source="vendor_doc",
             ref=f"{README}:25-27"),
        Fact("The project requires Python 3.8 or newer and is installed with pip install -e .", source="vendor_doc",
             ref=f"{README}:11-17"),
        Fact("MujocoSimulator is the MuJoCo environment class that is independent from ROS", source="upstream_code",
             ref=f"{SIMULATOR}:59-60"),
        Fact("The simulator loads its scene with mujoco.MjModel.from_xml_path on the configured xml_path and creates "
             "mujoco.MjData from that model", source="upstream_code", ref=f"{SIMULATOR}:81-83"),
        Fact("The simulator overwrites the model's integration step with cfg.dt", source="upstream_code",
             ref=f"{SIMULATOR}:82"),
        Fact("MujocoSimulator.step runs cfg.decimation physics iterations; each iteration computes a torque, writes "
             "it to data.ctrl and calls mujoco.mj_step", source="upstream_code", ref=f"{SIMULATOR}:275-283"),
        Fact("The simulator computes its joint torque as target_trq + kp * (q_target - q) + kd * (dq_target - dq)",
             source="upstream_code", ref=f"{SIMULATOR}:321-322"),
        Fact("set_joint_commands converts q, dq, trq, kp and kd to flattened float32 arrays",
             source="upstream_code", ref=f"{SIMULATOR}:339-346"),
        Fact("The simulator reset zeroes qvel, optionally writes the base pose and joint positions, and calls "
             "mujoco.mj_forward", source="upstream_code", ref=f"{SIMULATOR}:392-428"),
        Fact("MujocoEnv wraps MujocoSimulator with a fixed-Hz stepping thread and DDS publishing to mimic hardware",
             source="upstream_code", ref=f"{ENV}:15-24"),
        Fact("When step_hz is omitted, MujocoEnv sets its period to max(1e-6, dt * max(1, decimation)); "
             "otherwise it uses the supplied step_hz", source="upstream_code", ref=f"{ENV}:36-43"),
        Fact("G1MujocoConfig selects deploy_robot/assets/mjcf/g1.xml as the scene and the pelvis as its root body",
             source="upstream_code", ref=f"{CONFIG}:4-11"),
        Fact("G1MujocoConfig uses decimation 10 and dt 0.002 s", source="upstream_code", ref=f"{CONFIG}:8-10"),
        Fact("G1_NUM_MOTOR is defined as 29", source="upstream_code",
             ref=f"{CONSTANTS}:3"),
        Fact("G1JointNames lists the 29 joint names in controller order from left_hip_pitch_joint to "
             "right_wrist_yaw_joint", source="upstream_code", ref=f"{CONSTANTS}:42-72"),
        Fact("The shipped simulation script builds MujocoEnv(G1MujocoConfig)", source="upstream_code",
             ref=f"{SCRIPT}:68"),
        Fact("The model root element is '<mujoco model=\"g1\">' and its compiler element declares angle radian and "
             "meshdir ../meshes/g1", source="upstream_code", ref=f"{MODEL}:1-2"),
        Fact("The robot body is pelvis at 0 0 0.793 with a free joint named floating_base_joint", source="upstream_code",
             ref=f"{MODEL}:133-136"),
        Fact("The actuator block declares one motor per actuated joint, named after the joint, and no motor element "
             "declares a ctrlrange", source="upstream_code", ref=f"{MODEL}:386-416"),
        Fact("G1.__init__ calls ChannelFactoryInitialize in the real branch, but its function-local import and "
             "self.factory assignment occur in the sim branch", source="upstream_code", ref=f"{HARDWARE}:58-69"),
    ]
    safe_state = ("bridge-owned lockstep integration stops; no step or world reset is accepted while latched. "
                  "The integration state, velocities and controls are retained and readable. mhs.safety.reset "
                  "only clears the latch; a new step is required and a step without action reuses retained controls")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine
    #: name, the timestep and the lockstep clock; the values are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:g1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state, but this package offers "
                     "no working seed: cap.world.reset.v1 restores the model defaults and the seed input is recorded "
                     "only.  The stand-in is deterministic too, yet its placeholder motion is not the engine's "
                     "physics",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model for the joint "
            "dimensions, the actuator count, the actuator joint targets, the absent ctrlrange and the option "
            "timestep, then integrates a placeholder velocity proportional to each control value; it resolves no "
            "contact, friction, gravity, equality, tendon, actuator or free-base dynamics and loads no mesh, "
            "texture, sensor or camera",
            "the upstream control layer is NOT COVERED: MujocoSimulator.step computes a PD torque from q, dq, trq, "
            "kp and kd joint commands and runs cfg.decimation (10) physics steps per control step "
            "(mujoco_simulator.py:275-283, :321-322, :339-346); the MuJoCo bridge writes data.ctrl directly and "
            "mj_step runs once per requested tick, so the PD law, the decimation and the controller-order joint "
            "remapping are not reproduced",
            "the upstream MujocoEnv fixed-Hz thread and the DDS lowcmd/lowstate topic layer are not part of this "
            "driver (mujoco_env.py:15-24, :36-43); the bridge advances only on a step command, and there is no "
            "viewer, rendering or camera stream",
            "the model declares no actuator ctrlrange (g1.xml:386-416), so the bridge publishes action.ctrl "
            "operator_required: a step that sets it is refused until the deployment's site-limits.json bounds it, "
            "and site-limits.example.json is operator example data, not a model bound",
            "the model sets no <option timestep>, so the bridge uses the engine default; the deployed upstream "
            "simulator overwrites it with G1MujocoConfig.dt = 0.002 s (mujoco_simulator.py:82, config/g1.py:10) and "
            "the stand-in uses the same 0.002 s placeholder; the real engine was not run to confirm the value",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine or with the upstream simulator, and the sim backend that imports mujoco was not "
            "run",
            "no physical G1 robot is modelled or driven; the upstream real branch of the G1 robot is a hardware "
            "path this simulated package never opens",
            "the excluded G1 real constructor is broken at the pin: ChannelFactoryInitialize is imported locally "
            "only in the sim branch but called first in the real branch, and self.factory is assigned only in sim "
            "(deploy_robot/g1/g1.py:58-69); the raw MJCF bridge does not instantiate this class",
            "the fake resets to the MJCF pelvis pose (0, 0, 0.793) and identity free-joint quaternion, not the "
            "upstream wrapper's configured joint pose; it omits the full MuJoCo integration checkpoint API, uses "
            "mujoco_basic_v1, and declares snapshot_restore false for this backend",
        ],
    }
    fidelity_by_backend = {
        "fake": {"engine": "analytic:g1", "fidelity_level": "F0", "snapshot_restore": False},
    }
