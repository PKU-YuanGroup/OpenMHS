"""OpenMHS driver for gh.nimazareian/quadruped-rl-locomotion: the Unitree Go1 torque MJCF scene (MuJoCo family).

A ``MujocoDriver`` is configuration only: ``model_path`` names the MJCF scene and the bridge derives the whole
contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [12 numbers]}}``; every
``ctrl`` element is checked against the model's ``actuator_ctrlrange`` (the torque motors state ``-1.0 1.0``) before
``data.ctrl`` is written, then ``mj_step`` runs ``ticks`` times.  ``cap.world.reset.v1`` restores the model defaults
with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).  The device is simulated (R0): there is no hardware backend,
no e-stop path to a machine and no operator-required limit.

The package serves the card's ``unitree_go1/scene_torque.xml`` (models[1]), not models[0]: the upstream
``Go1MujocoEnv`` constructor defaults ``ctrl_type`` to ``"torque"`` and builds ``scene_{ctrl_type}.xml`` from it
(go1_mujoco_env.py:32-33), so the torque scene is the model the upstream environment loads by default.  Both scenes
state a control range for every actuator; this package keeps the default one.

MuJoCo is not installed where the gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py).  It reads the scene and its include for the 12 motors, their control ranges, the free base, the 12 hinge
joints and the 2 ms step, but its integration is a placeholder torque response, not MuJoCo's physics; the fidelity
``gaps`` list every difference.  A backend name that ``backends`` does not list (``sim``) imports the real ``mujoco``
module and loads the same scene; that path was not run here.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[1], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "unitree_go1/scene_torque.xml"
MODEL_PATH = "../../../../robots/nimazareian/quadruped-rl-locomotion/" + MODEL
SCENE = "unitree_go1/scene_torque.xml"
ROBOT = "unitree_go1/go1_torque.xml"
ENV = "go1_mujoco_env.py"
README = "README.md"
MODEL_README = "unitree_go1/README.md"


class QuadrupedRl(MujocoDriver):
    device_id = "quadruped-rl-locomotion"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    mode, risk = "simulated", "R0"
    display_name = "Unitree Go1 quadruped (MuJoCo torque scene)"
    vendor, model = "nimazareian/quadruped-rl-locomotion", "Unitree Go1"
    tags = ["go1", "mujoco", "quadruped", "reinforcement-learning", "robot", "simulation", "unitree"]
    facts = [
        Fact("The repository is a custom Gymnasium environment for training quadruped locomotion with "
             "reinforcement learning in the MuJoCo simulator, set up for the Unitree Go1 robot", source="vendor_doc",
             ref=f"{README}:3"),
        Fact("The repository provides two MJCF models for the Go1: one tuned for position control with a "
             "proportional controller and one that directly takes torque values", source="vendor_doc",
             ref=f"{README}:5"),
        Fact("The environment imports MujocoEnv from gymnasium.envs.mujoco", source="upstream_code", ref=f"{ENV}:2"),
        Fact("The class Go1MujocoEnv subclasses that MujocoEnv", source="upstream_code", ref=f"{ENV}:21"),
        Fact("The Go1MujocoEnv constructor defaults ctrl_type to 'torque' and builds ./unitree_go1/scene_{ctrl_type}.xml, "
             "so its default model is unitree_go1/scene_torque.xml", source="upstream_code", ref=f"{ENV}:32-33"),
        Fact("The environment performs an action every 10 frames and its comment states dt 0.002 s, so one action "
             "covers 0.02 s (50 Hz)", source="upstream_code", ref=f"{ENV}:37"),
        Fact("The environment limits an episode to 15.0 s", source="upstream_code", ref=f"{ENV}:53"),
        Fact("The desired velocity is vx 0.5 m/s, vy 0 and wz 0 rad/s", source="upstream_code", ref=f"{ENV}:80-82"),
        Fact("An episode is healthy while the trunk height is between 0.22 and 0.65 m", source="upstream_code",
             ref=f"{ENV}:93"),
        Fact("The healthy roll and pitch ranges are +-10 degrees", source="upstream_code", ref=f"{ENV}:94-95"),
        Fact("The action is 12 torque values", source="upstream_code", ref=f"{ENV}:119"),
        Fact("The scene root is '<mujoco model=\"go1 scene\">' and it includes go1_torque.xml", source="upstream_code",
             ref=f"{SCENE}:1-2"),
        Fact("The robot model declares '<compiler angle=\"radian\" meshdir=\"assets\" autolimits=\"true\"/>', so its "
             "joint ranges are radians and its meshes are resolved from assets/", source="upstream_code",
             ref=f"{ROBOT}:2"),
        Fact("The model selects an elliptic friction cone with impratio 100", source="upstream_code",
             ref=f"{ROBOT}:4"),
        Fact("The global default sets a motor with ctrllimited true and ctrlrange -1.0 to 1.0", source="upstream_code",
             ref=f"{ROBOT}:7"),
        Fact("The robot trunk is a body at 0 0 0.445 with a free joint and mass 5.204 kg", source="upstream_code",
             ref=f"{ROBOT}:83-88"),
        Fact("The joint default classes give the abduction joints range -0.863 to 0.863, the hip joints -0.686 to "
             "4.501 and the knee joints -2.818 to -0.888 rad", source="upstream_code", ref=f"{ROBOT}:14-23"),
        Fact("The actuator block has 12 <motor> elements, one per leg joint; the hip and thigh motors state gear 23 "
             "and the calf motors gear 35", source="upstream_code", ref=f"{ROBOT}:212-228"),
        Fact("The home keyframe states qpos '0 0 0.30 1 0 0 0 0 0.9 -1.8 0 0.9 -1.8 0 0.9 -1.8 0 0.9 -1.8' and ctrl "
             "all zeros", source="upstream_code", ref=f"{ROBOT}:230-233"),
        Fact("The scene adds a plane geom named floor with a checker groundplane material", source="upstream_code",
             ref=f"{SCENE}:14-21"),
        Fact("The MJCF description is a simplified robot description of the Go1 derived from the publicly available "
             "Unitree URDF description", source="vendor_doc", ref=f"{MODEL_README}:7-11"),
        Fact("The model package requires MuJoCo 2.2.2 or later and is released under a BSD-3-Clause License",
             source="vendor_doc", ref=f"{MODEL_README}:3-27"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the time step, determinism and the lockstep clock; the values below are written out so the whole contract reads
    #: in one place.
    fidelity = {
        "engine": "mujoco:go1 scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge's "
                     "cap.world.reset.v1 restores the model defaults (mj_resetData plus mj_forward) and accepts a "
                     "seed input only for the class contract, so no seed selects a different state; this package's "
                     "fake is a placeholder integrator and was not compared with MuJoCo",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the torque scene and its "
            "include for the 12 motors, the -1.0 to 1.0 ctrlrange, the free base and 12 hinge joints and the 2 ms "
            "step, but integrates a placeholder torque response and resolves no mesh, texture, contact, constraint, "
            "gravity, inertia or sensor",
            "MuJoCo was not installed and cannot be installed where the gate ran (no network, no pip), so no "
            "trajectory of this package was compared with the real engine; the sim path (a backend name backends "
            "does not list, which imports the real mujoco module) was not run",
            "the upstream Go1MujocoEnv wraps the scene in gymnasium.envs.mujoco.MujocoEnv with frame_skip=10, a 15 s "
            "episode limit, a reset to the home keyframe with 0.1 noise and a 50 Hz action rate; this driver loads "
            "the scene directly through the MuJoCo bridge and exposes data.ctrl and the integration state instead",
            "the torque model commands the motors through gear 23 (hip and thigh) or 35 (calf); the bridge writes "
            "data.ctrl and the fake applies a placeholder torque scale, so actuator dynamics, the gearbox and the "
            "1:34 motor gearing are not modelled",
            "snapshot and restore use the bridge's fallback state (time, qpos, qvel, act, ctrl) because the fake "
            "implements no mj_getState/mj_setState; the scene has no act, mocap or integration plugin state beyond "
            "that",
            "no rendering, viewer, joystick or training loop is modelled; the package is a local MuJoCo world, not "
            "the upstream reinforcement-learning environment or a physical Go1",
        ],
    }
