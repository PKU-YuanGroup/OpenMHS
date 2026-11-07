"""OpenMHS driver for gh.openretriever/stanford-robotics-kitchen: the kitchen's Panda MJCF model as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model (``models[0]``,
``src/retriever_src_kitchen/_scene/output/robots/panda.xml``) and the bridge derives the whole contract from the
model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; each ``ctrl`` element is checked
against the model's ``actuator_ctrlrange`` (nine actuators: seven arm torque motors and two gripper position
actuators) before it is written to ``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1``
restores the model defaults with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration
state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): the repository's own documentation says it has no real-device or hardware access
(README.md:104) and no physical robot is driven.  The scene metadata names Panda as the controlled robot
(scene.json:9), and the README calls it a controllable Franka Panda (README.md:13).

MuJoCo is not installed and cannot be installed where the gate runs (no network, no pip), so ``backends["fake"]``
is this package's stand-in ``mujoco`` module (fake.py).  It reads the same MJCF file for the actuator control ranges
and the qpos/qvel dimensions, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps``
list every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module
and loads the same model file; that path was not run here.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "src/retriever_src_kitchen/_scene/output/robots/panda.xml"
SCENE = "src/retriever_src_kitchen/_scene/scene.json"
MANIFEST = "src/retriever_src_kitchen/_scene/output/robots/manifest.json"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/openretriever/stanford-robotics-kitchen/" + MODEL


class StanfordRoboticsKitchen(MujocoDriver):
    device_id = "stanford-robotics-kitchen"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "Stanford Robotics Kitchen Panda (MuJoCo model)"
    vendor, model = "OpenRetriever", "Franka Panda"
    tags = ["stanford", "kitchen", "panda", "franka", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The repository is an installable reconstruction of the Stanford Robotics Center kitchen for MuJoCo "
             "and Retriever, with the scene, portable robot assets, scripted simulation tasks and a five-Flow "
             "Retriever pipeline", source="vendor_doc", ref="README.md:3-5"),
        Fact("The reconstruction is an estimated visual reconstruction, not a surveyed digital twin",
             source="vendor_doc", ref="README.md:9"),
        Fact("The controllable robot is a Franka Panda; the Mobile ALOHA is visual-only staging", source="vendor_doc",
             ref="README.md:13"),
        Fact("The scene metadata names Panda as the controlled robot", source="vendor_doc", ref=f"{SCENE}:9"),
        Fact("The scene metadata records that the scene has no hardware access", source="vendor_doc",
             ref=f"{SCENE}:14"),
        Fact("The Panda manifest entry names panda.xml as its MJCF file", source="vendor_doc",
             ref=f"{MANIFEST}:2-4"),
        Fact("panda.xml is an MJCF model named 'panda' and interprets angles in radians", source="upstream_code",
             ref=f"{MODEL}:1-2"),
        Fact("panda.xml declares seven torque motor actuators for the seven arm joints: joints 1 to 5 have "
             "ctrlrange -80 to 80 and joints 6 and 7 have ctrlrange -12 to 12", source="upstream_code",
             ref=f"{MODEL}:3-10"),
        Fact("panda.xml declares two position actuators for the gripper fingers: one ctrlrange is 0 to 0.04 and "
             "the other is -0.04 to 0", source="upstream_code", ref=f"{MODEL}:11-12"),
        Fact("The seven arm joints are hinges with ranges joint1 +-2.8973, joint2 +-1.7628, joint3 +-2.8973, "
             "joint4 -3.0718 to -0.0698, joint5 +-2.8973, joint6 -0.0175 to 3.7525 and joint7 +-2.8973",
             source="upstream_code", ref=f"{MODEL}:151-205"),
        Fact("The two gripper finger joints are slides with ranges 0 to 0.04 and -0.04 to 0", source="upstream_code",
             ref=f"{MODEL}:232-242"),
        Fact("create_scene constructs native MuJoCo state but starts no clock, policy or server", source="vendor_doc",
             ref="README.md:85-86"),
        Fact("The tested stack pins MuJoCo 3.3.1 and Retriever Core 0.0.4", source="vendor_doc",
             ref="README.md:112-113"),
        Fact("The repository documents no real-device or hardware access and no implicit simulator, viewer, socket "
             "or network startup during import", source="vendor_doc", ref="README.md:104-106"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:panda",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from the model defaults, and the driver's reset "
                     "restores those defaults; the driver takes no seed, so a reset always returns to the same model "
                     "state and a run repeats on the same engine. The fake backend is a deterministic stand-in, "
                     "not MuJoCo.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model's MJCF text for "
            "the actuator control ranges and the qpos/qvel dimensions, but integrates a placeholder velocity "
            "proportional to each control value; it loads no mesh, texture, camera or sensor and resolves no "
            "contact, equality, tendon or actuator constraint",
            "panda.xml sets no <option timestep>; the 2 ms step is MuJoCo's library default used by the stand-in, "
            "and this package did not verify the engine default because the engine was never imported",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "only the card's first model, the fixed-base Panda arm panda.xml, is served; the tiago.xml and "
            "ur5e.xml robot models, the kitchen scene files and the Mobile ALOHA staging are other models and are "
            "not part of this driver",
            "the upstream scripted demonstrations and the five-Flow Retriever pipeline are not served; this driver "
            "exposes only the model's ctrl vector and integration state",
            "there is no viewer, rendering, camera or sensor output",
            "no physical Franka Panda or Mobile ALOHA is modelled and nothing here was validated against hardware",
        ],
    }
