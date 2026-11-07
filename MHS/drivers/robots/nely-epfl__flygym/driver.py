"""OpenMHS driver for gh.nely-epfl/flygym: the fruitfly MJCF model (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``src/flygym/assets/model/flybody/fruitfly.xml``: the free-floating adult fruit fly of FlyGym/NeuroMechFly v2, with a
free joint on the thorax, 102 hinge joints and 78 actuators (70 joint- or tendon-driven general actuators and 8
adhesion actuators).  The bridge loads the model with the MuJoCo engine, derives ``cap.world.step.v1``'s
``action.ctrl`` from each actuator's ``ctrlrange``, writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves
``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state
(``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical fly is driven.  The model is read from the
read-only clone at the pinned commit and is neither copied into this package nor imported.  MuJoCo is not installed
where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py), which
reads the model shape from the same file but integrates a placeholder motion instead of the engine's physics; the
fidelity ``gaps`` below state every difference.

The card's entry symbol ``flygym_demo.muscle_imitation.env:ImitationEnv`` was confirmed at
``src/flygym_demo/muscle_imitation/env.py:83``: it is a Gymnasium environment that needs a pre-built
``flygym.Simulation``, gymnasium, numpy and the upstream package to construct.  The card's ``models`` list and the
``MujocoDriver`` helper describe the MJCF model itself, so this package serves ``models[0]`` as PLAYBOOK.md section 8
directs for MuJoCo cards.  Every Fact cites a line of the clone at commit 38c8ec61034cd59bc5ba0de20688d4a3c0000d60.
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "src/flygym/assets/model/flybody/fruitfly.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/nely-epfl/flygym/" + MODEL


class Fruitfly(MujocoDriver):
    device_id = "fruitfly"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "FlyGym fruitfly (MuJoCo model)"
    vendor, model = "NeLy-EPFL", "Drosophila melanogaster (NeuroMechFly v2)"
    tags = ["fruitfly", "neuromechfly", "drosophila", "mujoco", "simulation", "fly", "biomechanics"]
    facts = [
        Fact("FlyGym is the Python library for NeuroMechFly v2, a digital twin of the adult fruit fly Drosophila "
             "melanogaster", source="vendor_doc", ref="README.md:25"),
        Fact("The biomechanical model is based on a micro-CT scan of a real adult female fly", source="vendor_doc",
             ref="README.md:28"),
        Fact("The card's first model is the MJCF document whose root element is '<mujoco model=\"fruitfly\">'",
             source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The model compiles angles in radians and derives limits automatically (autolimits true)",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model integrates at 0.0001 s per step (0.1 ms) with gravity 0 0 -981", source="upstream_code",
             ref=f"{MODEL}:4"),
        Fact("The thorax is a free-floating body: the model declares the freejoint named free on the thorax body",
             source="upstream_code", ref=f"{MODEL}:299-300"),
        Fact("The wing default class gives its actuators a control range of -1 to 1", source="upstream_code",
             ref=f"{MODEL}:57-59"),
        Fact("The six wing actuators are wing_yaw_left, wing_roll_left, wing_pitch_left, wing_yaw_right, "
             "wing_roll_right and wing_pitch_right", source="upstream_code", ref=f"{MODEL}:957-962"),
        Fact("The adhesion default classes give the labrum and claw adhesion actuators a control range of 0 to 1",
             source="upstream_code", ref=f"{MODEL}:28-34"),
        Fact("The eight adhesion actuators are adhere_labrum_left, adhere_labrum_right and the claw actuators "
             "adhere_claw_T1, T2 and T3 for the left and right sides", source="upstream_code",
             ref=f"{MODEL}:1013-1021"),
        Fact("The leg default classes declare control ranges such as twist_coxa_T1 -0.8 to 0.8, abduct_coxa_T1 -1 to "
             "0.7, extend_coxa_T1 -0.2 to 1.7, twist_femur -1 to 1, extend_femur -0.15 to 2, extend_tibia -1.35 to "
             "1.3 and extend_tarsus -0.36 to 0.36", source="upstream_code", ref=f"{MODEL}:98-193"),
        Fact("The actuator section declares 78 actuators: 70 general actuators driving head, antenna, wing, abdomen, "
             "leg, tarsus and tendon targets, and 8 adhesion actuators attached to the labrum and the six claws",
             source="upstream_code", ref=f"{MODEL}:943-1021"),
        Fact("The model declares 15 sensors: an accelerometer, a gyro and a velocimeter on the thorax, six force "
             "sensors on the tarsi and six touch sensors on the claws", source="upstream_code",
             ref=f"{MODEL}:1023-1038"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch, and the integration state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:fruitfly",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "the model contains no random element and MuJoCo integrates it deterministically from the reset "
                     "state; the package's stand-in backend is deterministic too, but its placeholder motion is not "
                     "the engine's physics",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the served fruitfly.xml "
            "for the 102 hinge joints, the free joint, the 78 actuator ctrlranges and the 0.1 ms step, then moves "
            "each joint-driven actuator toward its control value; it computes no inertia, contact, adhesion, "
            "tendon or actuator dynamics, so no trajectory here is a MuJoCo result",
            "the stand-in loads no mesh or texture and resolves no contact, adhesion, exclusion, tendon or equality "
            "constraint: the 8 adhesion actuators, the 26 contact exclusions and the 85 mesh references of the "
            "model are not applied",
            "the model's 15 sensors (accelerometer, gyro, velocimeter, six force and six touch sites) and its nine "
            "cameras are not exposed; only the bridge's time, qpos, qvel and ctrl state is published",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the card's entry symbol flygym_demo.muscle_imitation.env:ImitationEnv is a Gymnasium wrapper that "
            "needs flygym, gymnasium, numpy and a built Simulation; this package serves the card's models[0] MJCF "
            "through the card's MujocoDriver and does not run that environment",
            "no physical fly is modelled and nothing was validated against the animal",
        ],
    }
