"""OpenMHS driver for gh.hshi74/toddlerbot: the ToddlerBot 2XC MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's ``models[0]``, the MJCF scene
``toddlerbot/descriptions/toddlerbot_2xc/scene.xml``, and the bridge derives the whole contract from the model it
loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [nu numbers]}}``; each ``ctrl`` element is checked against
the model's per-actuator ``actuator_ctrlrange`` before it is written to ``data.ctrl`` and ``mj_step`` runs ``ticks``
times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is
the bridge's ``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms`` and ``seed``.

The card's entry symbols are MJX training environments (the first is ``CartwheelEnv``, ``cartwheel_env.py:18``); this
package serves the raw MuJoCo scene those environments are built from, not the JAX environment, its motion reference,
its observation, reward or episode logic.  The device is simulated (R0): there is no hardware backend, no e-stop path
to a machine and no operator-required limit.  The model file is the system of record for the control envelope.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same scene and its included robot model for the free joint, the hinge joints, the actuator
count, the control range and the option time step, but its integration is a placeholder, not MuJoCo's physics; the
fidelity ``gaps`` list every difference.  A backend name that ``backends`` does not list (``sim``) imports the real
``mujoco`` module and loads the same file; that path was not run here.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "toddlerbot/descriptions/toddlerbot_2xc/scene.xml"
ROBOT = "toddlerbot/descriptions/toddlerbot_2xc/toddlerbot_2xc.xml"
ENV = "toddlerbot/locomotion/mjx_env.py"
CARTWHEEL = "toddlerbot/locomotion/cartwheel_env.py"
CONFIG = "toddlerbot/locomotion/mjx_config.py"

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/hshi74/toddlerbot/" + SCENE


class ToddlerBot2XC(MujocoDriver):
    device_id = "toddlerbot_2xc"
    model_path = MODEL_PATH
    native = "toddlerbot.locomotion.cartwheel_env:CartwheelEnv"
    backends = {"fake": FakeMujoco}
    display_name = "ToddlerBot 2XC scene (MuJoCo)"
    vendor, model = "Haochen Shi", "ToddlerBot 2XC"
    tags = ["humanoid", "locomotion", "mujoco", "simulation", "toddlerbot", "world", "scene"]
    facts = [
        Fact("ToddlerBot is a low-cost, open-source humanoid robot platform built for scalable policy learning and "
             "research in robotics and AI", source="vendor_doc", ref="README.md:12"),
        Fact("The upstream package is fully pip-installable on Python 3.10 or newer", source="vendor_doc",
             ref="README.md:16"),
        Fact("The upstream requires Python 3.10 or newer", source="vendor_doc", ref="pyproject.toml:14"),
        Fact("The upstream pins mujoco 3.3.4 and mujoco-mjx 3.3.4", source="vendor_doc",
             ref="pyproject.toml:36-37"),
        Fact("The card's primary scene is the MJCF model toddlerbot_2xc_scene and includes the robot model "
             "toddlerbot_2xc.xml", source="upstream_code", ref=f"{SCENE}:2-3"),
        Fact("The scene sets a statistic center and extent for the camera and adds a floor plane, four trackcom "
             "cameras and explicit floor contact pairs for the torso, head, pelvis and limb collision geoms",
             source="upstream_code", ref=f"{SCENE}:4-50"),
        Fact("The robot model compiles in radians with the mesh directory assets and autolimits enabled",
             source="upstream_code", ref=f"{ROBOT}:3"),
        Fact("The main default class sets the motor ctrlrange to -10 10", source="upstream_code",
             ref=f"{ROBOT}:31"),
        Fact("The actuator block declares 30 motors, from neck_yaw_drive through right_wrist_roll, one per actuated "
             "joint, and none of them overrides the main default class", source="upstream_code",
             ref=f"{ROBOT}:562-593"),
        Fact("The torso body carries the free joint torso_freejoint, so the robot base is not actuated",
             source="upstream_code", ref=f"{ROBOT}:34-35"),
        Fact("The environment base class is MJXEnv, a brax PipelineEnv subclass", source="upstream_code",
             ref=f"{ENV}:315"),
        Fact("The environment loads its MJCF with brax.io.mjcf and replaces the model's opt.timestep and opt.solver "
             "with cfg.sim.timestep and cfg.sim.solver", source="upstream_code", ref=f"{ENV}:484-491"),
        Fact("The card's first entry symbol is CartwheelEnv, registered with env_name cartwheel",
             source="upstream_code", ref=f"{CARTWHEEL}:18"),
        Fact("The cartwheel environment samples a zero command because the motion reference supplies the motion",
             source="upstream_code", ref=f"{CARTWHEEL}:44-48"),
        Fact("The default simulation config sets a 0.005 s time step and the Newton solver", source="upstream_code",
             ref=f"{CONFIG}:21-22"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step, the determinism kind and the lockstep clock from the loaded model; the members below override
    #: the derived text, and the gaps say what this package does not model.
    fidelity = {
        "engine": "mujoco:toddlerbot_2xc_scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model and one control sequence deterministically, and the bridge reset "
                     "restores the model defaults (mj_resetData + mj_forward), so a run repeats on the same engine; "
                     "no seed controls the reset because the scene declares no random state",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the free "
            "joint, the hinge joints, the actuator count, the per-actuator control range and the option time step "
            "but integrates placeholder joint motion, so trajectories, contacts, friction, equality constraints, "
            "actuator dynamics and the mesh visuals are not MuJoCo's",
            "the stand-in loads no mesh, texture or height field and resolves no contact, equality, tendon or sensor",
            "the upstream MJXEnv training environment (cartwheel_env.py:18) is not exposed: its motion reference, "
            "command sampling, observation, reward, domain randomization and episode terms remain upstream, and "
            "this package serves the raw cap.world.step.v1/cap.world.reset.v1 contract of the scene",
            "the upstream environment overrides opt.timestep with cfg.sim.timestep (mjx_env.py:487); this package "
            "loads the scene file as it is, so the time step is the one the loaded model states, not the gin config",
            "MuJoCo itself and the JAX/MJX stack were not importable where the gate ran, so no trajectory of this "
            "package was compared with the real engine and the sim backend was not run",
            "no physical ToddlerBot is modelled by this package and nothing was validated against hardware",
        ],
    }
