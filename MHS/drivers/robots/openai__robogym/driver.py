"""OpenMHS driver for gh.openai/robogym: the ShadowHand MJCF scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``robogym/assets/xmls/robot/shadowhand/main.xml``: a free base (the hand mount), a 24-hinge ShadowHand chain and 20
joint-position actuators whose control ranges are written in the included ``joint_position_actuation.xml``.  The
bridge derives ``cap.world.step.v1``'s ``action.ctrl`` per actuator from those ranges, writes ``data.ctrl``, runs
``mj_step`` for ``ticks`` and serves ``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state
is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The model is read from the read-only clone at the pinned commit and is neither copied into this package nor
imported.  MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is this package's
stand-in ``mujoco`` module (fake.py), which reads the model shape from the same file but integrates a placeholder
motion instead of the engine's physics; the fidelity ``gaps`` below state every difference.  The upstream simulator
(a backend name that ``backends`` does not list, ``sim``) imports the real ``mujoco`` module and loads the same
file; that path was not run here.

Every Fact cites a line of the clone at commit 9ff1111fd557b1a01911d7d8c9d59a453071c96e.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical ShadowHand.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

MODEL = "robogym/assets/xmls/robot/shadowhand/main.xml"
ASSETS = "robogym/assets/xmls/robot/shadowhand/assets.xml"
ACTUATION = "robogym/assets/xmls/robot/shadowhand/joint_position_actuation.xml"
CHAIN = "robogym/assets/xmls/robot/shadowhand/chain.xml"
REACH = "robogym/envs/dactyl/reach.py"
CUBE_ENV = "robogym/envs/dactyl/common/cube_env.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/openai/robogym/" + MODEL


class ShadowHand(MujocoDriver):
    device_id = "robogym-shadowhand"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "OpenAI Robogym ShadowHand (MuJoCo model)"
    vendor, model = "OpenAI", "ShadowHand"
    tags = ["shadowhand", "dexterous-hand", "manipulation", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The card's first model is the MJCF scene main.xml, whose root element is '<mujoco>'",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The scene includes assets.xml", source="upstream_code",
             ref=f"{MODEL}:4"),
        Fact("The scene includes joint_position_actuation.xml, the joint position servos", source="upstream_code",
             ref=f"{MODEL}:6"),
        Fact("The hand mount carries the free joint hand_base", source="upstream_code", ref=f"{MODEL}:19"),
        Fact("The scene includes chain.xml", source="upstream_code",
             ref=f"{MODEL}:20"),
        Fact("The model sets the MuJoCo integration step to 0.008 s in its option element", source="upstream_code",
             ref=f"{ASSETS}:14"),
        Fact("The asset_class default sets ctrllimited and forcelimited on its actuators", source="upstream_code",
             ref=f"{ASSETS}:78"),
        Fact("The actuator section declares 20 general actuators, each with an explicit ctrlrange",
             source="upstream_code", ref=f"{ACTUATION}:72-96"),
        Fact("The actuator comment says the ctrlranges follow Shadow's technical specification, page 8, except "
             "THJ0 whose sign is reversed in this config", source="upstream_code", ref=f"{ACTUATION}:68-70"),
        Fact("The first actuator A_WRJ1 has ctrlrange -0.4887 to 0.1396 rad", source="upstream_code",
             ref=f"{ACTUATION}:72"),
        Fact("The actuator A_FFJ2 has ctrlrange 0.0 to 1.5708 rad", source="upstream_code", ref=f"{ACTUATION}:76"),
        Fact("The actuator A_THJ0 has ctrlrange -1.5708 to 0.0 rad", source="upstream_code", ref=f"{ACTUATION}:96"),
        Fact("The hand chain is a tree of 24 hinge joints: WRJ1/WRJ0, FFJ0-FFJ3, MFJ0-MFJ3, RFJ0-RFJ3, "
             "LFJ0-LFJ4 and THJ0-THJ4", source="upstream_code", ref=f"{CHAIN}:15-239"),
        Fact("The wrist joint WRJ1 is a hinge with range -0.4887 to 0.218757 rad", source="upstream_code",
             ref=f"{CHAIN}:15"),
        Fact("The wrist joint WRJ0 is a hinge with range -0.8 to 0.4887 rad", source="upstream_code",
             ref=f"{CHAIN}:21"),
        Fact("The thumb joint THJ0 is a hinge with range -1.78625 to 0.104035 rad", source="upstream_code",
             ref=f"{CHAIN}:239"),
        Fact("ReachEnv loads the card's model as robot/shadowhand/main.xml", source="upstream_code", ref=f"{REACH}:69"),
        Fact("CubeEnv, the base of the dactyl cube environments, loads robot/shadowhand/main.xml",
             source="upstream_code", ref=f"{CUBE_ENV}:151"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:shadowhand",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the package's fake "
                     "backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 8.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served main.xml and "
            "its includes for the joint dimensions, the 20 actuator ctrlranges and the 0.008 s step, then moves "
            "each actuated hinge toward its control value; it computes no inertia, torque, contact, equality, "
            "tendon or actuator dynamics, so no trajectory here is a MuJoCo result",
            "the four tendon-driven actuators (A_FFJ1, A_MFJ1, A_RFJ1 and A_LFJ1) name a fixed tendon rather than "
            "a joint; the stand-in moves no joint for them and resolves no tendon",
            "the stand-in loads no mesh or texture and does not resolve the mesh paths of assets.xml (for example "
            "robot/shadowhand/forearm_electric.stl relative to the robogym asset root), so nothing is rendered",
            "the hand base is a free joint; the stand-in resets qpos to zero instead of MuJoCo's qpos0 and does "
            "not integrate a free body",
            "the dactyl environments compose this hand model with a cube, target and table scene "
            "(cube_env.py:151); the driver serves the card's hand scene alone, not an environment scene",
            "MuJoCo itself was not importable where the gate ran, so the engine path (backend sim) and the "
            "robogym asset search path were never exercised",
            "no physical ShadowHand is modelled and nothing was validated against the hardware",
        ],
    }
