"""OpenMHS driver for gh.embomaster/polysim: the Unitree G1 29-DoF MuJoCo scene (a MuJoCo family driver).

The card's entry symbol ``humanoidverse.simulator.mujoco.mujoco:MuJoCo`` exists at line 15 of the clone: a
``BaseSimulator`` wrapper that needs a Hydra config, Torch, ``mujoco`` and (unless headless) a viewer, and whose
``load_assets`` reads ``config.robot.asset``.  It is not imported or run here.  This package serves the card's
``models[0]``, ``humanoidverse/data/robots/g1/scene_29dof.xml``, through ``MujocoDriver``: the bridge loads the MJCF,
takes the step action from ``data.ctrl`` (29 motors, bounded per actuator by the model's ``ctrlrange``) and derives
the world state from the model and data arrays.  The scene includes ``g1_29dof_old.xml``, the 29-DoF G1 model with a
floating base.

The device is simulated (R0, ``world.sim``): there is no hardware backend, no physical stop and no operator-required
limit.  MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so the
``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It parses the same MJCF for the joint shape,
the 29 actuators, their explicit control ranges, the free base pose and the option step, but its integration is a
placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line or line range of the clone at commit
0fdb349785479b5c0c30d3c676fae67025b8d34a.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "humanoidverse/data/robots/g1/scene_29dof.xml"
ROBOT = "humanoidverse/data/robots/g1/g1_29dof_old.xml"
CONFIG = "humanoidverse/config/simulator/mujoco.yaml"
SIM2SIM = "sim2real/config/g1_29dof_hist.yaml"
SIMULATOR = "humanoidverse/simulator/mujoco/mujoco.py"
README = "README.md"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/embomaster/polysim/" + MODEL


class G1Sim(MujocoDriver):
    device_id = "g1_mujoco"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 29-DoF (PolySim MuJoCo scene)"
    vendor, model = "Embodied Master (PolySim)", "Unitree G1 29-DoF"
    tags = ["unitree", "g1", "humanoid", "29dof", "mujoco", "simulation", "polysim"]
    facts = [
        Fact("PolySim is a whole-body-control training platform that integrates multiple heterogeneous simulators",
             source="vendor_doc", ref=f"{README}:15"),
        Fact("The TODO list marks sim2sim in MuJoCo released and sim2real videos with the Unitree SDK on G1 still "
             "unchecked", source="vendor_doc", ref=f"{README}:48-49"),
        Fact("The MuJoCo environment section installs mujoco and torch with pip", source="vendor_doc",
             ref=f"{README}:219"),
        Fact("The MuJoCo simulator config sets _target_ to humanoidverse.simulator.mujoco.mujoco.MuJoCo, the "
             "simulator name to mujoco, fps 200, control_decimation 4, substeps 1 and gravity 0 0 -9.81",
             source="upstream_code", ref=f"{CONFIG}:5-18"),
        Fact("The class MuJoCo extends BaseSimulator", source="upstream_code", ref=f"{SIMULATOR}:15"),
        Fact("setup derives sim_dt as 1 / sim.fps and sim_substeps from sim.substeps", source="upstream_code",
             ref=f"{SIMULATOR}:57-58"),
        Fact("load_assets loads the MJCF with mujoco.MjModel.from_xml_path, overwrites opt.timestep with 0.005 s and "
             "constructs an MjData", source="upstream_code", ref=f"{SIMULATOR}:147-150"),
        Fact("The simulation loop writes the PD torques to data.ctrl and calls mujoco.mj_step", source="upstream_code",
             ref=f"{SIMULATOR}:524-526"),
        Fact("The scene declares the model g1_29dof scene and includes g1_29dof_old.xml", source="upstream_code",
             ref=f"{MODEL}:1-2"),
        Fact("The included model declares g1_29dof and the compiler angle unit radian with meshdir meshes",
             source="upstream_code", ref=f"{ROBOT}:1-2"),
        Fact("The world body pelvis starts at 0 0 0.793 and carries the free joint floating_base_joint",
             source="upstream_code", ref=f"{ROBOT}:63-66"),
        Fact("The actuator section has 29 motor actuators, one per hinge joint, each with an explicit ctrlrange",
             source="upstream_code", ref=f"{ROBOT}:386-420"),
        Fact("The control ranges are -88 88 for the hips and waist yaw, -139 139 for the knees, -50 50 for the "
             "ankles and waist roll/pitch, -25 25 for the shoulders, elbows and wrist rolls, and -5 5 for wrist "
             "pitch/yaw", source="upstream_code", ref=f"{ROBOT}:387-419"),
        Fact("The Sim2Sim config points ROBOT_SCENE at ../humanoidverse/data/robots/g1/scene_29dof.xml",
             source="upstream_code", ref=f"{SIM2SIM}:2"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the model state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, time step, determinism kind
    #: and the lockstep clock; the members below make the whole contract readable in one place.
    fidelity = {
        "engine": "mujoco:g1_29dof",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge accepts "
                     "a seed in cap.world.reset.v1 but a MuJoCo reset restores the model defaults and does not use it, "
                     "so one control sequence repeats a trajectory on the same engine.  The package's stand-in is "
                     "deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the free base, "
            "the 29 hinge joints, the 29 motor actuators, their explicit ctrlranges and the included model file, then "
            "gives each actuated hinge a placeholder velocity proportional to its control value and holds the free "
            "base where the model puts it; it computes no inertia, torque, gravity, contact, friction, constraint, "
            "damping or actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; the model's floor, "
            "collision geoms, sites, sensors and default classes are parsed only for the joint and actuator shape",
            "the scene and the included robot model declare no <option timestep>; the stand-in therefore reports a "
            "placeholder default step, while the upstream simulator overwrites model.opt.timestep with 0.005 s after "
            "loading (mujoco.py:148) and its own setup uses 1/fps (mujoco.py:57, fps 200 in mujoco.yaml:15); this "
            "package loads the MJCF directly and does not run that loop",
            "the upstream class humanoidverse.simulator.mujoco.mujoco:MuJoCo needs Hydra, Torch and a viewer and is "
            "not imported or run by this package; its control loop, terrain setup and sensors are not exposed here",
            "the fake reset restores the parsed model qpos0 and zeros; a real MjData reset also restores the full "
            "integration state, which this package did not inspect",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no physical G1 is modelled and nothing was validated against the Unitree hardware",
        ],
    }
