"""OpenMHS driver for gh.vikashplus/adroit: the Adroit hand MJCF as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model
(``models[0]``, ``Adroit_hand.xml``) and the bridge derives the whole contract from the model it loads.
``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked against the
model's ``actuator_ctrlrange`` (one element per position actuator) before it is written to ``data.ctrl``, then
``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with ``mj_resetData`` +
``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``,
``tick``, ``timestep_ms``, ``seed``).

The repository is a set of MuJoCo models, not a Python SDK: the README describes the 28-DOF Adroit platform
(24-DOF ShadowHand plus a 4-DOF arm) and this package serves the hand model ``Adroit_hand.xml``.  The model's
chain has 24 hinge joints and 24 position actuators; the forearm is bolted to the world through the ``hand
mount`` body (the base free joint of ``resources/chain.xml`` is commented out) and the only free body is a
small ball.  The 4-DOF arm of the README is therefore not part of this model.

The device is simulated (R0): there is no hardware backend and no operator-required limit.  MuJoCo is not
installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).
It reads the same model file for the model shape (joint dimensions, actuator count and per-actuator control
ranges) but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend
name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that
path was not run here.

The model file is read from the read-only clone at the pinned commit (it is never copied into this package and
never imported).  Every Fact cites a line of the clone at commit c98c9c92fc9729e92a10c8db79588348897d8fe3.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/vikashplus/adroit/Adroit_hand.xml"
SCENE = "Adroit_hand.xml"
ASSETS = "resources/assets.xml"
ACTUATORS = "resources/joint_position_actuation.xml"
CHAIN = "resources/chain.xml"
README = "README.md"


class AdroitHand(MujocoDriver):
    device_id = "adroit"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Adroit 24-DOF hand (MuJoCo model)"
    vendor, model = "Vikash Kumar (Adroit)", "Adroit_hand"
    tags = ["adroit", "dexterous-hand", "mujoco", "robot", "shadow-hand", "simulation", "tendon-driven"]
    facts = [
        Fact("Adroit is a 28 degree of freedom system: a 24 degree of freedom ShadowHand and a 4 degree of "
             "freedom arm", source="vendor_doc", ref=f"{README}:6"),
        Fact("The Adroit platform is tendon-driven and pneumatically actuated; the README describes the hand "
             "as a system with 24 degrees of freedom and 40 tendons", source="vendor_doc", ref=f"{README}:3"),
        Fact("Adroit_hand.xml includes resources/assets.xml and resources/joint_position_actuation.xml; the "
             "tendon torque actuation include is commented out", source="upstream_code", ref=f"{SCENE}:12-14"),
        Fact("The model declares <compiler angle=\"radian\"/>", source="upstream_code", ref=f"{ASSETS}:11"),
        Fact("The model's <option> element sets the physics timestep to 0.002 s", source="upstream_code",
             ref=f"{ASSETS}:22"),
        Fact("The hand mount body at the world origin includes resources/chain.xml and declares no joint of "
             "its own", source="upstream_code", ref=f"{SCENE}:32-36"),
        Fact("The chain's base free joint is commented out, so the forearm and hand are fixed to the hand "
             "mount", source="upstream_code", ref=f"{CHAIN}:14"),
        Fact("The only free joint of the scene belongs to the ball body at pos .1 -.1 .25",
             source="upstream_code", ref=f"{SCENE}:38-41"),
        Fact("A weld equality connects the mocap1 body to the forearm body", source="upstream_code",
             ref=f"{SCENE}:46"),
        Fact("The position actuators name one joint and an explicit ctrlrange each; A_WRJ1 has ctrlrange "
             "-0.52 to 0.17 and kp 50, and A_WRJ0 has ctrlrange -0.79 to 0.61 and kp 50",
             source="upstream_code", ref=f"{ACTUATORS}:14-37"),
        Fact("The Adroit default class sets general actuators to ctrllimited=\"true\" with ctrlrange -1 1",
             source="upstream_code", ref=f"{ASSETS}:88"),
        Fact("WRJ1 is a hinge joint with range -0.524 to 0.175 rad", source="upstream_code",
             ref=f"{CHAIN}:26"),
        Fact("THJ0 is a hinge joint with range -1.571 to 0 rad", source="upstream_code",
             ref=f"{CHAIN}:219"),
        Fact("The tendon section declares fixed tendons from T_WRJ1r to T_THJ0l with ranges",
             source="upstream_code", ref=f"{ASSETS}:132-290"),
        Fact("The mesh assets are named with the file paths ../Adroit/resources/meshes/*.stl",
             source="upstream_code", ref=f"{ASSETS}:34-44"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the
    #: engine, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:Adroit_hand",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed input and cap.world.reset.v1 restores the model defaults, so a run repeats exactly on "
                     "the same engine but no seed selects a different state",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "joint dimensions, the actuator count and the control ranges but integrates a placeholder motion of "
            "each actuated hinge toward its control value, so trajectories, contacts, tendons, the weld equality "
            "and actuator dynamics are not MuJoCo's",
            "the model comments out its base free joint (resources/chain.xml:14), so the 4-DOF arm described in "
            "README.md:6 is not present in this scene: the hand is fixed to the world and the only free body is "
            "the ball, whose free-joint dynamics the fake does not integrate",
            "the mesh file paths in resources/assets.xml:34-44 point at ../Adroit/resources/meshes, which does not "
            "resolve inside this clone; the fake loads no mesh and the real MuJoCo load of the clone was not run",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "snapshot and restore use the bridge's fallback copy of time, qpos, qvel and ctrl (the stand-in has no "
            "mj_getState), so they are not exact for the contact, tendon and warm-start state of the real engine",
            "no physical Adroit hand or arm is modelled and nothing was validated against hardware",
        ],
    }
