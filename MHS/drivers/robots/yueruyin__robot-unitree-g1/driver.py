"""OpenMHS driver for gh.yueruyin/robot-unitree-g1: the G1 humanoid MJCF scene (a MuJoCo family driver).

The card's entry symbol is ``deploy.deploy_mujoco53:main`` (``deploy/deploy_mujoco53.py:1915``).  That function is a
viewer-coupled script: it takes a positional config argument, loads the MJCF named by
``deploy/config/g1_53.yaml`` with ``mujoco.MjModel.from_xml_path``, assigns ``model.opt.timestep`` from the config,
opens ``mujoco.viewer.launch_passive`` and runs its own policy and controller loop.  It exposes no reset, step or seed
function of its own.  This package therefore serves the card's ``models[0]``, ``resources/g1/scene53.xml``, through
``MujocoDriver``: the bridge loads the scene, takes the step action from ``data.ctrl`` (53 motor actuators, none of
which declares a ``ctrlrange``) and derives the world state from the model and data arrays.

The motors declare no ``ctrlrange``, so the bridge publishes ``action.ctrl`` as ``operator_required``: the endpoint refuses a step that sets
it (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it;
``site-limits.example.json`` is operator example data, not a bound of the model.

The device is simulated (R0, ``world.sim``): there is no hardware backend and no physical stop.  MuJoCo is not
installed and cannot be installed where the acceptance gate runs (no network, no pip), so the
``fake`` backend is this package's stand-in ``mujoco`` module (fake.py).  It parses the same scene and its include for
the joint shape, the 53 actuators, the free bodies, the drawer slides and the deployed 0.002 s step, but its integration
is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list
(``sim``) imports the real ``mujoco`` module and loads the same scene; that path was not run here.

The model files are read from the read-only upstream clone at the pinned commit (they are never copied into this
package and never imported).  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/yueruyin/robot-unitree-g1/resources/g1/scene53.xml"

README = "README.md"
SCRIPT = "deploy/deploy_mujoco53.py"
CONFIG = "deploy/config/g1_53.yaml"
SCENE = "resources/g1/scene53.xml"
ROBOT = "resources/g1/g1_53dof.xml"


class UnitreeG1(MujocoDriver):
    device_id = "g1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree G1 humanoid (MuJoCo scene g1_53dof)"
    vendor, model = "Yueruyin", "Unitree G1 (53 DOF, MuJoCo scene)"
    tags = ["unitree", "g1", "humanoid", "mujoco", "simulation", "whole-body", "legged"]
    facts = [
        Fact("The project describes itself as a control-system implementation for the Unitree G1 humanoid simulated "
             "with the MuJoCo physics engine, covering whole-body control, walking, squatting, arms and fingers",
             source="vendor_doc", ref=f"{README}:5"),
        Fact("The project advertises full 53-degree-of-freedom whole-body control of the G1", source="vendor_doc",
             ref=f"{README}:12"),
        Fact("The documented way to run the simulation is `python deploy/deploy_mujoco53.py`", source="vendor_doc",
             ref=f"{README}:65"),
        Fact("The deployment script imports mujoco and mujoco.viewer", source="upstream_code", ref=f"{SCRIPT}:6-7"),
        Fact("main() requires a positional config_file argument for the deployment config", source="upstream_code",
             ref=f"{SCRIPT}:1919"),
        Fact("main loads the MJCF named by the config with mujoco.MjModel.from_xml_path(xml_path), builds MjData, and "
             "overwrites model.opt.timestep with config.simulation_dt", source="upstream_code",
             ref=f"{SCRIPT}:1937-1939"),
        Fact("main opens a passive MuJoCo viewer over the model and data", source="upstream_code",
             ref=f"{SCRIPT}:1993"),
        Fact("The simulation loop advances the model with mujoco.mj_step(model, data)", source="upstream_code",
             ref=f"{SCRIPT}:2044"),
        Fact("The config points xml_path at resources/g1/scene53.xml", source="upstream_code", ref=f"{CONFIG}:3"),
        Fact("The config sets simulation_dt to 0.002 s", source="upstream_code", ref=f"{CONFIG}:8"),
        Fact("The scene model is named g1_53dof scene and includes g1_53dof.xml", source="upstream_code",
             ref=f"{SCENE}:1-2"),
        Fact("The scene worldbody contains a plane floor named floor", source="upstream_code", ref=f"{SCENE}:35-37"),
        Fact("The scene adds free-floating box1 and box2 bodies to the included robot", source="upstream_code",
             ref=f"{SCENE}:39-58"),
        Fact("The scene adds two drawer slide joints with range -0.8 to 0", source="upstream_code",
             ref=f"{SCENE}:114-126"),
        Fact("The scene adds a free-floating glass_panel body", source="upstream_code", ref=f"{SCENE}:132-133"),
        Fact("The included robot model is named g1_53dof and its compiler uses radians with meshes under meshes/",
             source="upstream_code", ref=f"{ROBOT}:1-2"),
        Fact("The robot pelvis body sits at 0.80 -1.55 0.763 and carries a free joint named floating_base_joint",
             source="upstream_code", ref=f"{ROBOT}:96-100"),
        Fact("The actuator section declares one motor actuator per robot joint (53 motors) and none of them carries a "
             "ctrlrange attribute", source="upstream_code", ref=f"{ROBOT}:812-887"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, time step, determinism kind and
    #: lockstep clock; the members below make the whole contract readable in one place.
    fidelity = {
        "engine": "mujoco:g1_53dof scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge accepts "
                     "a seed in cap.world.reset.v1 but a MuJoCo reset restores the model defaults and does not use it, "
                     "so one control sequence repeats a trajectory on the same engine.  The package's stand-in is "
                     "deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its include "
            "for the free joints, the 53 hinge joints, the 53 motor actuators, their (absent) ctrlranges and the "
            "0.002 s deployed step, then gives each actuated hinge or slide a placeholder velocity proportional to "
            "its control value and holds every other joint where the model puts it; it computes no inertia, torque, "
            "gravity, contact, friction, constraint, damping or actuator dynamics and produces no MuJoCo trajectory",
            "the stand-in loads no STL mesh or texture and resolves no collision or contact; the scene's boxes, cup, "
            "cabinets, glass panel and table geometry, the floor and the robot's collision geoms are not applied",
            "the scene declares no ctrlrange on any of the 53 motors, "
            "so the bridge publishes action.ctrl operator_required: a step that sets it is refused until the site's site-limits.json bounds it, and site-limits.example.json is operator example data, not a model bound; the model constrains joint positions and torques, not the motor control value",
            "the world state carries the full 83 qpos and 79 qvel values of the scene (3 scene free bodies, 2 drawer "
            "slides, the robot free base and 53 robot hinges); the stand-in holds the three scene free bodies and the "
            "two drawer slides fixed, while MuJoCo would simulate them",
            "the upstream deployment script overwrites the model time step with its config value 0.002 s and runs a "
            "policy and arm/finger controller in a passive viewer; this package loads the scene directly, serves the "
            "step of the model and takes the caller's 53-element control vector",
            "the fake reset restores the parsed model qpos0 and zeros; a real MjData reset also restores the full "
            "integration state, which this package did not inspect",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "no physical humanoid is modelled and nothing was validated against Unitree G1 hardware",
        ],
    }
