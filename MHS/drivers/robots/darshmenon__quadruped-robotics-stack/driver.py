"""OpenMHS driver for gh.darshmenon/quadruped-robotics-stack: the Go2 MuJoCo parkour scene (a MuJoCo family driver).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's first model,
``training/envs/go2_parkour_scene.xml``, a flat scene with the floating-base Go2, its five-joint arm and a two-finger
gripper, plus parkour obstacles that are parked underground by default (``go2_parkour_scene.xml:15-20``).  The bridge
derives the contract from the loaded model: ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}`` with one
``ctrl`` element per actuator, each checked against the model's ``actuator_ctrlrange`` before it is written to
``data.ctrl``, and then ``mj_step`` runs ``ticks`` times; ``cap.world.reset.v1`` restores the model defaults with
``mj_resetData`` + ``mj_forward``.  The published world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The upstream entry class ``training.envs.go2_mujoco_env:Go2MujocoEnv`` was confirmed at ``go2_mujoco_env.py:206``: it
loads the MJCF with ``mujoco.MjModel.from_xml_path`` (``go2_mujoco_env.py:215-216``), sets ``model.opt.timestep`` to
``SIM_DT`` (``go2_mujoco_env.py:217``) and advances the model with ``mujoco.mj_step`` four times per policy step
(``go2_mujoco_env.py:871-873``).  It points ``SCENE_XML`` at ``training/envs/go2_scene.xml`` (``go2_mujoco_env.py:11``),
while this package follows the card and the MuJoCo playbook by serving ``models[0]``, the parkour variant.  Both scenes
contain the same robot, arm and actuator block; the served variant adds the parked obstacles and is not the flat scene
the training environment loads.  The difference is recorded in the fidelity ``gaps`` below.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit; the model file is the system of record for the control envelope.

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (``fake.py``).  It parses the same MJCF text and takes
the actuator count, the per-actuator control ranges, the joint dimensions and the option time step from that tree, but
its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` state every difference.  A backend name
that ``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same file; that path was not
run here.

The model file is read from the read-only upstream clone at the pinned commit; it is never copied into this package and
the clone is never imported.  Every Fact cites a line of that clone at
fe3c2e7457f9caaaa30b5669daba184394173a5f.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and nothing here ran the MuJoCo engine or a physical Go2.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to the clone root.
MODEL = "training/envs/go2_parkour_scene.xml"
#: The same file through the read-only clone below the repository root (never imported, never copied).
MODEL_PATH = "../../../../robots/darshmenon/quadruped-robotics-stack/" + MODEL

ENV = "training/envs/go2_mujoco_env.py"
SCENE = "training/envs/go2_parkour_scene.xml"


class Go2ParkourScene(MujocoDriver):
    device_id = "go2_parkour"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree Go2 MuJoCo parkour scene"
    vendor, model = "Unitree Robotics", "Go2"
    tags = ["unitree", "go2", "quadruped", "mujoco", "simulation", "parkour", "robot"]
    facts = [
        Fact("The repository is a ROS2 + Gazebo + MuJoCo workspace for simulating and walking quadruped robots",
             source="vendor_doc", ref="README.md:8"),
        Fact("The README identifies Go2 as the only fully working robot", source="vendor_doc", ref="README.md:18"),
        Fact("The Python requirements include gymnasium 0.29 or newer and mujoco 3.0 or newer", source="upstream_code",
             ref="requirements.txt:4-8"),
        Fact("The MuJoCo environment points SCENE_XML at training/envs/go2_scene.xml", source="upstream_code",
             ref=f"{ENV}:11"),
        Fact("Go2MujocoEnv is the Gymnasium environment class the training code constructs", source="upstream_code",
             ref=f"{ENV}:206"),
        Fact("Go2MujocoEnv loads the MJCF with mujoco.MjModel.from_xml_path and builds the data with mujoco.MjData",
             source="upstream_code", ref=f"{ENV}:215-216"),
        Fact("Go2MujocoEnv sets model.opt.timestep to SIM_DT", source="upstream_code", ref=f"{ENV}:217"),
        Fact("SIM_DT is 0.005 s and CTRL_DECIMATION is 4, so one policy step is 0.02 s", source="upstream_code",
             ref=f"{ENV}:78-80"),
        Fact("ACT_DIM is 19", source="upstream_code", ref=f"{ENV}:74"),
        Fact("The action space is a Box from -1.0 to 1.0 with one element per action dimension", source="upstream_code",
             ref=f"{ENV}:326-327"),
        Fact("The step writes the control vector to data.ctrl and calls mujoco.mj_step once per decimation step",
             source="upstream_code", ref=f"{ENV}:871-873"),
        Fact("The parkour scene sets the integration time step to 0.005 s in its option element", source="upstream_code",
             ref=f"{SCENE}:4"),
        Fact("The floating base body starts at 0 0 0.42 and carries the root free joint", source="upstream_code",
             ref=f"{SCENE}:23-24"),
        Fact("The arm and two-finger gripper add seven joints after the twelve leg joints and must stay the last child "
             "of base", source="upstream_code", ref=f"{SCENE}:121-125"),
        Fact("The scene declares nineteen position actuators, one per leg, arm and gripper joint, each with a ctrlrange",
             source="upstream_code", ref=f"{SCENE}:164-189"),
        Fact("The four hip actuators have ctrlrange -1.0472 to 1.0472", source="upstream_code",
             ref=f"{SCENE}:166-169"),
        Fact("The front thigh actuators have ctrlrange -1.5708 to 3.4907 and the rear thigh actuators -0.5236 to "
             "4.5379", source="upstream_code", ref=f"{SCENE}:171-174"),
        Fact("The four calf actuators have ctrlrange -2.7227 to -0.83776", source="upstream_code",
             ref=f"{SCENE}:176-179"),
        Fact("The five arm joints have ctrlrange -1.5708 to 1.5708 and the two finger joints 0 to 0.025 and -0.025 "
             "to 0", source="upstream_code", ref=f"{SCENE}:183-189"),
        Fact("The parkour hurdles and platforms are parked at z -5 by default and the parkour environment rewrites "
             "their position and size at reset", source="upstream_code", ref=f"{SCENE}:15-20"),
    ]
    safe_state = ("the simulation is held: after an e-stop the runtime refuses every step and reset until "
                  "mhs.safety.reset clears the latch, and the model data stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:go2_parkour_scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the served model has no "
                     "random element, so one ctrl sequence and tick count repeat a trajectory; the bridge takes no "
                     "seed input and a reset restores the model defaults, so no seed selects a different one.  The "
                     "package's fake backend is deterministic too, but its placeholder motion is not the engine's "
                     "physics.",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene's MJCF, takes the "
            "nineteen actuator control ranges, the joint dimensions and the option time step from that tree, then "
            "moves each actuated joint toward its ctrl target at a placeholder rate; it computes no inertia, torque, "
            "contact, friction, actuator, sensor or noise dynamics, so no trajectory here is a MuJoCo result",
            "the stand-in resolves no mesh, height field, contact, equality or sensor constraint: the parkour "
            "hurdles, the floor and the Go2's collision geoms are not simulated physically, and the robot cannot "
            "stand or walk in the fake",
            "the stand-in does not apply the model's damping, armature, joint range, actuator gain or bias "
            "parameters; it treats every position actuator as a direct target for its joint",
            "the card's models[0] is served, training/envs/go2_parkour_scene.xml, while the upstream entry class "
            "loads training/envs/go2_scene.xml (go2_mujoco_env.py:11); both carry the same robot, arm and actuator "
            "block, but the flat training scene is not served",
            "the parkour obstacles are parked at z -5 in the file and the parkour environment rewrites them at reset "
            "(go2_parkour_scene.xml:15-20); this driver serves the file as written and does not rewrite the terrain",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the upstream observation vector (76 values, go2_mujoco_env.py:70), reward, curriculum, domain "
            "randomisation and rendering are not part of the cap.world.* contract served here; the state carries "
            "only time, qpos, qvel and ctrl",
            "snapshot and restore use the bridge's fallback copy of time, qpos, qvel and ctrl because the stand-in "
            "has no mj_getState or mj_setState; a restore is not the engine's full integration state",
            "no physical Go2 is modelled and nothing was validated against the hardware",
        ],
    }
