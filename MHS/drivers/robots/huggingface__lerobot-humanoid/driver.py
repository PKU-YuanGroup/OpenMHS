"""OpenMHS driver for gh.huggingface/lerobot-humanoid: the LeRobot humanoid MJCF scene as a MuJoCo world.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's primary model (``models[0]``,
``lerobot-humanoid-model/models/bipedal_plateform/mjcf/scene.xml``) and the bridge derives the whole contract from
the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; every ``ctrl`` element is
checked against the model's ``actuator_ctrlrange`` (one element per position actuator) before it is written to
``data.ctrl``, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults with
``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit; the control envelope is the model's own.

The repository is a workspace of five independent Git repositories (README.md:11): design, hardware, model,
runtime and identification.  This package serves the model repository's primary MJCF scene (README.md:40); the
runtime and identification stacks that consume those assets (README.md:41-42) are not part of it.  The model
directory is a git submodule: the pinned superproject commit records ``lerobot-humanoid-model`` as a gitlink
(``160000 commit ea23cbac9b79833eff974d9196a7edb8043effb6``), so no Fact cites a line inside it (gate G4 reads
the superproject tree and would report REF_MISSING).  The driver still loads the model from the read-only clone.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the same MJCF file for the actuator control ranges, the joint dimensions and the option time
step, but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` list every difference.  A
backend name that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same model
file; that path was not run here.  This package is model-authored and unreviewed: it is checked on the fake backend
only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "lerobot-humanoid-model/models/bipedal_plateform/mjcf/scene.xml"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/huggingface/lerobot-humanoid/" + MODEL


class LerobotHumanoid(MujocoDriver):
    device_id = "lerobot-humanoid"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "LeRobot humanoid bipedal platform (MuJoCo simulation)"
    vendor, model = "Hugging Face LeRobot", "bipedal_plateform"
    tags = ["huggingface", "lerobot", "humanoid", "bipedal", "mujoco", "simulation", "robot"]
    facts = [
        Fact("The workspace groups the full LeRobot humanoid project from design to deployment, including "
             "mechanical/control co-design, hardware build assets, robot model assets, the runtime and "
             "deployment stack, and simulation-based identification", source="vendor_doc", ref="README.md:3-9"),
        Fact("Each folder of the workspace is an independent Git repository with its own history and remotes",
             source="vendor_doc", ref="README.md:11"),
        Fact("The project aims to build an open and practical low-cost humanoid robot that people can reproduce",
             source="vendor_doc", ref="README.md:15"),
        Fact("The hardware cost target is less than USD 5,000, depending on sourcing, shipping and taxes",
             source="vendor_doc", ref="README.md:19"),
        Fact("The design prioritizes 3D-printed custom mechanical parts that are printable and documented",
             source="vendor_doc", ref="README.md:21"),
        Fact("The lerobot-humanoid-model repository provides versioned MJCF/URDF robot model assets and Python "
             "helpers (lerobot_humanoid_models) that the runtime and identification repositories consume",
             source="vendor_doc", ref="README.md:40"),
        Fact("The lerobot-humanoid-runtime repository makes the robot move in simulation and on real hardware, "
             "with controllers, calibration, policy execution and deployment", source="vendor_doc",
             ref="README.md:41"),
        Fact("The lerobot-humanoid-identification repository replays real logs and tunes simulator parameters with "
             "batched replay and CMA-ES identification", source="vendor_doc", ref="README.md:42"),
        Fact("The workspace was initially developed by Virgile Batto during his time at Hugging Face LeRobot",
             source="vendor_doc", ref="README.md:97"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine
    #: name, the determinism kind, the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:bipedal_plateform_scene",
        "fidelity_level": "F1",
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the scene for the actuator "
            "control ranges and the qpos/qvel dimensions but integrates a placeholder velocity proportional to each "
            "control value, so trajectories, contacts, friction and actuator dynamics are not MuJoCo's",
            "the scene includes robot.xml and the model's meshes, materials and collision shapes are not loaded by "
            "the stand-in; no contact, equality, tendon or actuator constraint of the model is resolved",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared with "
            "the real engine",
            "only the first card model, the bipedal_plateform scene, is served; the no-arms and lerobot_humanoide "
            "variants and the identification copies are other devices and are not part of this driver",
            "the upstream runtime, identification and hardware stacks are not part of this driver; it exposes only "
            "the MuJoCo ctrl vector and integration state, with no viewer or rendering",
            "no physical robot is modelled and nothing was validated against the LeRobot humanoid hardware",
        ],
    }
