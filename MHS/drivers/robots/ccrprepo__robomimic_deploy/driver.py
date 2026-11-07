"""OpenMHS driver for gh.ccrprepo/robomimic_deploy: the Unitree G1 29-DoF MuJoCo scene as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's first model (``models[0]``,
``g1_description/scene.xml``) and the bridge derives the whole contract from the model it loads.  The scene includes
``g1_description/g1_29dof_rev_1_0.xml`` (scene.xml:2), which declares one free joint and 29 hinge joints driven by 29
``<motor>`` elements (g1_29dof_rev_1_0.xml:52, :246-274).  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl:
[...]}}``: the bridge writes the 29-element ``data.ctrl`` vector and runs ``mj_step`` for ``ticks`` steps.
``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The model's ``<motor>`` elements carry no ``ctrlrange``, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.  The joint ``range`` and
``actuatorfrcrange`` values of the MJCF stay model facts, not limits of this driver.  The device is simulated
(R0): there is no hardware backend and no e-stop path to a machine.
The upstream real-robot deployment (``deploy_real/deploy_real.py``) is not part of this package.

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It reads the same scene for the joint
dimensions, the actuator list and the option time step, but its integration is a placeholder, not MuJoCo's physics;
the fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not list (``sim``) imports the
real ``mujoco`` module and loads the same scene; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only.

Every Fact cites a line of the clone at commit 3a72ec1a55dcf155be88c9dcc4a32ecb5c11e313.  The upstream simulator
also overrides the model step with ``simulation_dt`` 0.003 from ``deploy_mujoco/config/mujoco.yaml:2``
(``deploy_mujoco/deploy_mujoco.py:30, :35``); this package serves the MJCF's own 0.002 s step instead, and the gap
says so.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "g1_description/scene.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/ccrprepo/robomimic_deploy/" + MODEL


class RoboMimicG1(MujocoDriver):
    device_id = "robomimic-g1"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "RoboMimic Deploy Unitree G1 29-DoF (MuJoCo scene)"
    vendor, model = "ccrprepo", "Unitree G1 29-DoF"
    tags = ["robomimic", "unitree-g1", "g1", "humanoid", "29-dof", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is a multi-policy robot deployment framework based on a state-switching mechanism, "
             "with the included policies designed for the Unitree G1 robot (29-DoF)", source="vendor_doc",
             ref="README.md:9"),
        Fact("The deployment framework applies only to G1 robots with a 3-DOF waist, and a waist fixing bracket "
             "must be unlocked before the framework can be used normally", source="vendor_doc", ref="README.md:14"),
        Fact("The MuJoCo simulation is started with python deploy_mujoco/deploy_mujoco.py", source="vendor_doc",
             ref="README.md:79-82"),
        Fact("The simulation configuration selects g1_description/scene.xml as the model, sets simulation_dt to "
             "0.003 s and sets control_decimation to 7", source="upstream_code",
             ref="deploy_mujoco/config/mujoco.yaml:1-3"),
        Fact("The scene MJCF includes the robot model g1_29dof_rev_1_0.xml", source="upstream_code",
             ref="g1_description/scene.xml:1-2"),
        Fact("The robot MJCF is model g1_29dof_rev_1_0, uses radian angles and keeps its meshes in meshes/",
             source="upstream_code", ref="g1_description/g1_29dof_rev_1_0.xml:1-2"),
        Fact("The robot MJCF sets its integration step to 0.002 s and selects the implicit integrator",
             source="upstream_code", ref="g1_description/g1_29dof_rev_1_0.xml:8-9"),
        Fact("The pelvis body starts at z 0.793 m and carries the free joint floating_base_joint",
             source="upstream_code", ref="g1_description/g1_29dof_rev_1_0.xml:50-52"),
        Fact("The left hip pitch joint has a range of -2.5307 to 2.8798 rad and an actuator force range of "
             "-88 to 88", source="upstream_code", ref="g1_description/g1_29dof_rev_1_0.xml:59"),
        Fact("The robot MJCF declares 29 motor actuators, one per joint from left_hip_pitch_joint to "
             "right_wrist_yaw_joint, and every motor element carries only name and joint attributes (no ctrlrange)",
             source="upstream_code", ref="g1_description/g1_29dof_rev_1_0.xml:245-275"),
        Fact("The robot MJCF defines four IMU sensors: a gyro and an accelerometer at imu_in_torso and "
             "imu_in_pelvis, each with a noise and cutoff value", source="upstream_code",
             ref="g1_description/g1_29dof_rev_1_0.xml:277-282"),
        Fact("The MuJoCo loop loads the scene with mujoco.MjModel.from_xml_path, creates MjData, overrides "
             "m.opt.timestep with simulation_dt and takes the actuator count from m.nu", source="upstream_code",
             ref="deploy_mujoco/deploy_mujoco.py:33-37"),
        Fact("The MuJoCo loop computes a PD torque from the policy output and writes it to d.ctrl before every "
             "mujoco.mj_step(m, d)", source="upstream_code", ref="deploy_mujoco/deploy_mujoco.py:80-82"),
        Fact("The MuJoCo loop runs control_decimation physics steps per policy update and reads qpos[7:], "
             "qvel[6:], qpos[3:7] and qvel[3:6] as joint positions, joint velocities, base quaternion and base "
             "angular velocity", source="upstream_code", ref="deploy_mujoco/deploy_mujoco.py:84-90"),
        Fact("The real robot configuration expects 29 joints and a control_dt of 0.02 s", source="upstream_code",
             ref="deploy_real/config/real.yaml:2-7"),
        Fact("The README reports that only the Charleston dance policy is verified stable on physical robots and "
             "that all other movements are not recommended for physical deployment", source="vendor_doc",
             ref="README.md:143-154"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:g1_scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the model defaults; the bridge accepts a "
                     "seed in the reset input but does not use it, and a reset restores the model defaults, so one "
                     "ctrl sequence repeats a trajectory on the same engine.  The package's fake is deterministic "
                     "too, but its placeholder motion is not the engine's physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and the included "
            "robot MJCF for the 29 motor actuators, the joint dimensions and the 0.002 s model step, then moves each "
            "actuated joint by a placeholder velocity proportional to its control value; it computes no inertia, "
            "torque, contact, friction, equality or actuator dynamics, leaves the free base fixed and so produces no "
            "MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; it does not apply the "
            "joint damping, armature or frictionloss defaults, the joint ranges or the actuator force ranges of "
            "the model",
            "the upstream simulation overrides the model step with simulation_dt 0.003 from "
            "deploy_mujoco/config/mujoco.yaml:2 (deploy_mujoco/deploy_mujoco.py:30, :35), while this package serves "
            "the MJCF's own 0.002 s step; the control decimation 7, the PD gains and the policy layer are not part "
            "of this driver",
            "the upstream simulation also runs the FSM, policy inference, joystick and viewer "
            "(deploy_mujoco/deploy_mujoco.py:43-106); this driver exposes only the MuJoCo ctrl vector and "
            "integration state, with no viewer, joystick or policy",
            "the upstream real-robot deployment (deploy_real/deploy_real.py, unitree_sdk2) is not part of this "
            "simulated driver; no physical G1 is modelled or driven",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
        ],
    }
