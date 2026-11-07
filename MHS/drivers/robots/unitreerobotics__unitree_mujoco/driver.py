"""OpenMHS driver for gh.unitreerobotics/unitree_mujoco: the Unitree H2 MJCF scene (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_path`` names the MJCF scene and the bridge derives the whole contract
from the model it loads.  The step action is ``data.ctrl``, bounded per actuator by the model's ``actuator_ctrlrange``
(31 torque motors); the world state is the integration state of the model (``time``, ``qpos``, ``qvel``, ``ctrl``)
plus the tick count, and ``cap.world.reset.v1`` restores the model defaults (``mj_resetData`` + ``mj_forward``).

The package serves the card's ``unitree_robots/h2/scene.xml`` (models[2]), not models[0] ``h1/scene.xml``: the H1
model gives its ``not_use_joint`` motor no ``ctrlrange`` (``unitree_robots/h1/h1.xml:209``), so the bridge would
publish an unbounded control interval for that actuator and the gate cannot probe an envelope it cannot bound.  The
H2 scene states a ``ctrlrange`` for every one of its 31 motors and its model states the 1 ms integration step, so
both the step envelope and the fidelity timestep come from the clone.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco``
module (fake.py); it reads the scene and its include for the joint count, actuator count, control ranges and timestep,
but its integration is a placeholder, not MuJoCo's physics.  The fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads the same scene; that path was not run
here.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[2], relative to this package directory: the read-only clone under robots/ at the pinned commit.
SCENE = "unitree_robots/h2/scene.xml"
MODEL = "unitree_robots/h2/h2_mujoco.xml"
MODEL_PATH = "../../../../robots/unitreerobotics/unitree_mujoco/" + SCENE
README = "readme.md"
PY_SIM = "simulate_python/unitree_mujoco.py"
PY_CONFIG = "simulate_python/config.py"
PY_BRIDGE = "simulate_python/unitree_sdk2py_bridge.py"


class UnitreeH2(MujocoDriver):
    device_id = "unitree-h2"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Unitree H2 (MuJoCo)"
    vendor, model = "Unitree Robotics", "H2"
    tags = ["h2", "humanoid", "mujoco", "robot", "simulation", "unitree"]
    facts = [
        Fact("The package's model is the MJCF scene unitree_robots/h2/scene.xml, whose root element is "
             "'<mujoco model=\"Unitree H2\">' and which includes h2_mujoco.xml", source="upstream_code",
             ref=f"{SCENE}:1-2"),
        Fact("h2_mujoco.xml declares '<compiler angle=\"radian\" meshdir=\"meshes/\"/>', so the joint ranges and "
             "the control ranges of the model are radians and its meshes are resolved from meshes/",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The model sets the integration step to 0.001 s", source="upstream_code", ref=f"{MODEL}:8"),
        Fact("The model's floating base is the joint floating_base_joint of type free", source="upstream_code",
             ref=f"{MODEL}:47"),
        Fact("The actuator block has 31 <motor> elements, one per actuated hinge joint, and every motor states a "
             "ctrlrange", source="upstream_code", ref=f"{MODEL}:241-277"),
        Fact("The leg motors state ctrlrange +-360 for the hip pitch, hip roll, hip yaw and knee, +-19 for the "
             "ankle roll and +-66.88 for the ankle pitch", source="upstream_code", ref=f"{MODEL}:242-254"),
        Fact("The waist motors state ctrlrange +-120 for the waist yaw and +-180 for the waist roll and waist "
             "pitch", source="upstream_code", ref=f"{MODEL}:256-258"),
        Fact("The arm motors state ctrlrange +-130 for the shoulder pitch, +-60 for the shoulder roll, shoulder "
             "yaw, elbow and wrist roll, and +-10 for the wrist pitch and wrist yaw", source="upstream_code",
             ref=f"{MODEL}:260-274"),
        Fact("The head motors state ctrlrange +-50 for the head pitch and head yaw", source="upstream_code",
             ref=f"{MODEL}:276-277"),
        Fact("The left hip pitch joint has range -2.4526 to 2.77542 rad", source="upstream_code",
             ref=f"{MODEL}:52"),
        Fact("The left ankle roll joint has range -0.349066 to 0.296706 rad", source="upstream_code",
             ref=f"{MODEL}:71"),
        Fact("The left wrist pitch joint has range -0.576 to 0.576 rad", source="upstream_code",
             ref=f"{MODEL}:181"),
        Fact("The repository describes itself as a simulator developed based on Unitree sdk2 and mujoco",
             source="vendor_doc", ref=f"{README}:3"),
        Fact("The unitree_robots directory holds the MJCF description files for the robots supported by "
             "unitree_sdk2", source="vendor_doc", ref=f"{README}:9"),
        Fact("The Python simulator loads the scene with mujoco.MjModel.from_xml_path and creates the MjData",
             source="upstream_code", ref=f"{PY_SIM}:15-16"),
        Fact("The Python simulator overrides the model timestep with config.SIMULATE_DT", source="upstream_code",
             ref=f"{PY_SIM}:31"),
        Fact("config.py sets SIMULATE_DT to 0.005 s", source="upstream_code", ref=f"{PY_CONFIG}:13"),
        Fact("UnitreeSdk2Bridge reads num_motor from mj_model.nu and its step from mj_model.opt.timestep",
             source="upstream_code", ref=f"{PY_BRIDGE}:40-44"),
        Fact("UnitreeSdk2Bridge maps a Unitree LowCmd motor command to data.ctrl as tau + kp*(q - sensordata) + "
             "kd*(dq - sensordata)", source="upstream_code", ref=f"{PY_BRIDGE}:111-123"),
        Fact("The Python simulator publishes and subscribes the DDS topics rt/lowcmd, rt/lowstate and "
             "rt/sportmodestate", source="upstream_code", ref=f"{PY_BRIDGE}:25-27"),
        Fact("The Python simulator needs unitree_sdk2_python and mujoco-python, installed with pip3", source="vendor_doc",
             ref=f"{README}:97-115"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step, determinism and the lockstep clock; the values below are written out so the whole contract reads
    #: in one place.  Every gap is a difference from MuJoCo or from the upstream simulate_python loop.
    fidelity = {
        "engine": "mujoco:H2",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge's "
                     "cap.world.reset.v1 restores the model defaults (mj_resetData plus mj_forward) and takes no "
                     "seed parameter, so no seed selects a different state; this package's fake is a placeholder "
                     "integrator and was not compared with MuJoCo",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its include "
            "for the joint and actuator counts, the ctrlrange of each motor and the 1 ms model timestep, but "
            "integrates a placeholder torque response and resolves no mesh, texture, contact, constraint, gravity, "
            "inertia or sensor",
            "MuJoCo was not installed and cannot be installed where the gate ran (no network, no pip), so no "
            "trajectory of this package was compared with the real engine; the sim path (a backend name backends "
            "does not list, which imports the real mujoco module) was not run",
            "the upstream Python simulator overrides the model timestep with config.SIMULATE_DT = 0.005 s "
            "(simulate_python/unitree_mujoco.py:31, simulate_python/config.py:13) and maps Unitree LowCmd messages "
            "into data.ctrl (simulate_python/unitree_sdk2py_bridge.py:111-123); this driver loads the scene directly, "
            "keeps the model's 0.001 s step and exposes data.ctrl, so it is not the upstream DDS simulator",
            "no viewer, joystick, DDS channel or unitree_sdk2py message is modelled; the package is a local MuJoCo "
            "world, not the upstream simulate_python loop and not a physical robot",
            "snapshot and restore use the bridge's fallback state (time, qpos, qvel, ctrl) because the fake "
            "implements no mj_getState/mj_setState; the H2 scene adds no act, mocap or keyframe state beyond that",
            "the fake's free-base reset starts at the pelvis body position (0 0 1.2) and identity quaternion; it "
            "does not run MuJoCo's qpos0 or forward kinematics, and its step does not clamp the joints to their "
            "model ranges",
        ],
    }
