"""OpenMHS driver for gh.nvidia-isaac/video_to_data: the pinned G1 29dof MuJoCo scene.

The repository is an end-to-end pipeline that turns human demonstration
videos into simulation-ready assets and robot training data (README.md:3).
Its executable MuJoCo artifact is the G1 whole-body planner scene
``planner/assets/mujoco/scene_29dof.xml``: the planner builds a
``mujoco.MjModel`` from that file and runs forward kinematics on it
(g1_planner.py:104-110, 406-411).  This package serves that scene through
:class:`MujocoDriver`; the real backend is the official ``mujoco`` engine
loading the same file, and the package does not copy or modify it.

DEVIATION FROM THE CARD/RECON: the card names
``flash_chord.envs.rl:RLEnv`` as its entry symbol.  That class consumes a Scene
and Reference and returns Warp buffers; its scene uses Newton's SolverMuJoCo,
whose Warp model may live on CPU or CUDA (flash_chord/runtime/sim.py:5-6).
It is not the official ``mujoco`` module API that ``MujocoDriver`` serves.
Its configured reference/scene and Newton/Warp runtime are not integrated here.
The card's ``models`` list names MuJoCo XML files; ``scene_29dof.xml``
is the only ``scene`` and is the file the planner loads, so this package
serves that MuJoCo world and does NOT cover ``RLEnv``, the FlashCHORD training
loop or the Isaac Lab tasks.  No GPU, Newton, Isaac Lab, FlashCHORD or robot
run is claimed; MuJoCo itself was not installed here.

The fake backend (fake.py) is a package-local stand-in for the ``mujoco``
module: it parses the same scene and its include for shape, qpos0 and
ctrlranges and advances a placeholder joint state.  It is F0, not the engine.
This package is model-authored and unreviewed; every gate run is on the fake
backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's only "scene" model, relative to the pinned clone root.
MODEL = ("robotic_grounding/source/robotic_grounding/robotic_grounding/"
         "planner/assets/mujoco/scene_29dof.xml")
#: The same file from this package directory, read in place from the clone.
MODEL_PATH = "../../../../robots/nvidia-isaac/video_to_data/" + MODEL

#: The included G1 robot model (one free joint + 29 hinge joints, 29 motors).
ROBOT = ("robotic_grounding/source/robotic_grounding/robotic_grounding/"
         "planner/assets/mujoco/g1_29dof.xml")
#: The planner that loads the scene for its forward-kinematics step.
_PLANNER = "robotic_grounding/source/robotic_grounding/robotic_grounding/planner/g1_planner.py"
_FLASH = "robotic_grounding/flash_chord/src/flash_chord"


class VideoToDataG1(MujocoDriver):
    device_id = "video_to_data_g1"
    device_kind = "world.sim"
    mode = "simulated"
    # Isolated simulated state only (MHS-004 SAFE-006): no physical actuator,
    # robot or hardware command is exposed by this package.
    risk = "R0"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Video to Data G1 29dof MuJoCo scene"
    vendor = "NVIDIA Isaac"
    model = "scene_29dof"
    tags = ["mujoco", "mjcf", "simulation", "g1", "humanoid", "whole-body", "planner"]
    facts = [
        Fact("The repository describes itself as an end-to-end pipeline that converts human demonstration videos "
             "into simulation-ready assets and physics-grounded robot training data.",
             source="vendor_doc", ref="README.md:3"),
        Fact("The robotic-grounding stage retargets human motion onto a robot embodiment and drives Isaac Lab "
             "environments trained with RSL-RL PPO.", source="vendor_doc", ref="README.md:33"),
        Fact("The G1 whole-body planner loads its MuJoCo scene from planner/assets/mujoco/scene_29dof.xml.",
             source="upstream_code", ref=f"{_PLANNER}:406-411"),
        Fact("The planner constructs a MuJoCo model from that XML path with mujoco.MjModel.from_xml_path, then a "
             "mujoco.MjData and mujoco.mj_forward.", source="upstream_code", ref=f"{_PLANNER}:104-110"),
        Fact("The scene is a MuJoCo model named 'g1_29dof scene' that includes g1_29dof.xml.",
             source="upstream_code", ref=MODEL + ":1-2"),
        Fact("The scene's worldbody adds a directional light and a floor plane to the included robot model.",
             source="upstream_code", ref=MODEL + ":19-21"),
        Fact("The G1 model compiles angles in radians and resolves its meshes from ../../../assets/meshes/g1.",
             source="upstream_code", ref=ROBOT + ":2"),
        Fact("The pelvis body starts at pos 0 0 0.793 and carries the free joint floating_base_joint.",
             source="upstream_code", ref=ROBOT + ":63-67"),
        Fact("The actuator block declares 29 <motor> actuators, one per actuated G1 joint, each with an "
             "explicit ctrlrange.", source="upstream_code", ref=ROBOT + ":386-419"),
        Fact("The hip motors state ctrlrange -88 88, the knee motors -139 139 and the ankle motors -50 50.",
             source="upstream_code", ref=ROBOT + ":387-399"),
        Fact("The waist yaw motor states ctrlrange -88 88 and the waist roll and pitch motors -50 50.",
             source="upstream_code", ref=ROBOT + ":401-403"),
        Fact("The shoulder, elbow and wrist-roll motors state ctrlrange -25 25; the wrist pitch and yaw motors "
             "state -5 5.", source="upstream_code", ref=ROBOT + ":405-419"),
        Fact("The model asset directory's NOTICE says the G1 and Dex3 robot descriptions are from or derived "
             "from Unitree G1 Description assets and are licensed under the BSD 3-Clause License.",
             source="vendor_doc", ref="robotic_grounding/source/robotic_grounding/robotic_grounding/planner/"
                                        "assets/mujoco/NOTICE:3-6"),
        Fact("The model asset directory's LICENSE is the BSD 3-Clause License of Unitree Robotics.",
             source="vendor_doc", ref="robotic_grounding/source/robotic_grounding/robotic_grounding/planner/"
                                        "assets/mujoco/LICENSE:1-3"),
        Fact("The robotic_grounding package setup declares license 'Apache 2.0'.",
             source="upstream_code", ref="robotic_grounding/source/robotic_grounding/setup.py:36"),
        Fact("FlashCHORD's RLEnv constructor requires a Scene and Reference and accepts an optional RLEnvConfig.",
             source="upstream_code", ref=f"{_FLASH}/envs/rl.py:198-213"),
        Fact("RLEnv.step accepts an optional Warp action array and returns observation, reward, done and "
             "truncation buffers.", source="upstream_code", ref=f"{_FLASH}/envs/rl.py:472-485"),
        Fact("The FlashCHORD runtime describes MuJoCo-Warp through Newton's SolverMuJoCo, with CPU or CUDA "
             "selected by where the model's Warp arrays live.", source="upstream_code",
             ref=f"{_FLASH}/runtime/sim.py:3-9"),
    ]
    safe_state = (
        "The simulation stops advancing: after an e-stop no cap.world.step.v1 or cap.world.reset.v1 call is "
        "accepted until mhs.safety.reset clears the latch, while the integration state and stored ctrl remain "
        "readable. Safety reset advances no ticks and does not clear ctrl; a later explicit step without an "
        "action reuses it. This stops only this in-process model, not FlashCHORD or an external Isaac application."
    )
    #: The real path is the official MuJoCo engine loading the same scene.  It
    #: was not installed or run here, so this is a description, not a run.
    fidelity = {
        "engine": "mujoco:scene_29dof",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "MuJoCo determinism depends on the engine version, the compiled model, the options and any "
                     "callbacks or plugins; the bridge derives no seed and the class's reset has no seed effect.",
        },
        # The model states no <option timestep>.  MuJoCo's library default is 0.002 s; the fake uses that as a
        # placeholder (fake.py) and the fake gaps disclose it.  The real engine path was not run.
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the real sim backend (the official mujoco engine loading scene_29dof.xml) was not installed or run: "
            "the scene and its mesh directory were never compiled and no trajectory was compared with the engine",
            "the model states no <option timestep>; 0.002 s is MuJoCo's library default and the fake's placeholder, "
            "not a value written in the clone",
            "the scene is the planner's forward-kinematics world: the pelvis starts at 0 0 0.793 with every hinge "
            "at ref 0, the model has no keyframe or controller and the 29 motors take raw torques, so under "
            "gravity the legs are not held unless a caller supplies controls",
            "the package does not serve flash_chord.envs.rl:RLEnv (Scene/Reference construction, Warp-array "
            "actions and four-buffer returns), the Isaac Lab Sharpa-V2D-v0 tasks or the "
            "FlashCHORD/Newton/Warp/JAX training and replay stack; NOT COVERED",
            "contact, friction, inertia, actuator force limits and joint limits are those of the model file and "
            "were not validated against a physical G1 or against the engine",
            "the model loads meshes from the clone's assets/meshes/g1 directory; the package neither copies nor "
            "modifies them",
            "the bridge derives the control bounds from the model's actuator_ctrlrange; those are simulation "
            "model values, not a physical torque or safety certification",
            "the scene's sensors are not read or published by this package",
        ],
    }
    #: The deployed fake is a package-local stand-in for the mujoco module.
    #: It parses the same scene for shape, qpos0 and ctrlranges but runs no
    #: MuJoCo physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:MuJoCo API stand-in (no MuJoCo engine)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "Event-driven placeholder integration with no contact, constraint or force solver; the "
                         "same control input reproduces the same placeholder state hash, but this is a stand-in "
                         "digest, not a MuJoCo trajectory or state-hash replay.",
            },
            "timestep_ms": 2.0,
            "realtime_factor": 0,
            "clock": "lockstep",
            "reset": "full",
            "snapshot_restore": True,
            "gaps": [
                "the fake is a package-local stand-in for the mujoco module: it parses the MJCF and its include "
                "for shape, qpos0 and ctrlranges, but it loads no meshes, textures, inertias or contacts and runs "
                "no MuJoCo physics",
                "each motor's force (gear * ctrl) accelerates only its own hinge against a placeholder unit "
                "inertia with a placeholder damping; the free base, gravity, contacts, friction, joint limits, "
                "force limits and sensor physics are not integrated",
                "the model states no <option timestep>; the fake's 2 ms tick is a placeholder matching MuJoCo's "
                "library default, not a model value",
                "reset restores qpos0 from the MJCF (pelvis at 0 0 0.793 with an identity quaternion, the 29 "
                "hinges at ref 0), as mj_resetData does",
                "the snapshot uses the bridge's basic profile (time, qpos, qvel, act and ctrl) because the "
                "stand-in exposes no mj_getState/mj_setState; warm-start and derived quantities are not preserved",
                "flash_chord.envs.rl:RLEnv, the Isaac Lab tasks and the FlashCHORD/Newton/Warp/JAX stack are NOT "
                "COVERED",
            ],
        },
    }
