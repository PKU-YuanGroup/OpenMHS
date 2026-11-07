"""OpenMHS driver for gh.cram2/semantic_digital_twin: the panda single-cube MJCF scene in MuJoCo.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's model,
``resources/mjcf/mjx_single_cube_no_mesh.xml``, in the read-only clone.  The MuJoCo bridge loads the model with the
engine, derives ``cap.world.step.v1``'s ``action.ctrl`` from the model's ``actuator_ctrlrange``, writes ``data.ctrl``,
runs ``mj_step`` for ``ticks`` and serves ``cap.world.reset.v1`` with ``mj_resetData`` plus ``mj_forward``.  The world
state is the bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``,
``seed``).

The scene is a seven-joint panda arm with a two-finger hand and a free-floating box on a plane.  It has 16 qpos values
and 15 degrees of freedom (seven arm hinges, two finger slides and the box's free joint) and 8 actuators: seven
position actuators for joint1 to joint7 and one general actuator for finger_joint1.  The two finger joints are coupled
by an equality constraint.  The integration step is 0.005 s with the implicitfast integrator.

The device is simulated (R0): there is no hardware backend and no physical robot is driven.  MuJoCo is not installed
where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py), which
reads the model shape and actuator control ranges from the same MJCF text but integrates a placeholder motion instead
of the engine's physics; the fidelity ``gaps`` below state every difference.

Every Fact cites a line of the clone at commit 40a35e7e481b358cd7f9d939c7ff4e0c23826098.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

MODEL = "resources/mjcf/mjx_single_cube_no_mesh.xml"
TEST = "test/test_adapters/test_multi_sim.py"
MJCF_ADAPTER = "src/semantic_digital_twin/adapters/mjcf.py"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/cram2/semantic_digital_twin/" + MODEL


class SemanticDigitalTwin(MujocoDriver):
    device_id = "semantic-digital-twin"
    model_path = MODEL_PATH
    #: A MuJoCo fake is the stand-in ``mujoco`` module itself, so the backend is the factory callable; G7 has no
    #: class surface to compare and reports its family warning.  The lock keeps the same entry as a string.
    backends = {"fake": fake_mujoco}
    display_name = "Semantic Digital Twin panda single-cube scene (MuJoCo)"
    vendor, model = "CRAM2", "panda scene (mjx_single_cube_no_mesh)"
    tags = ["mujoco", "mjcf", "semantic-digital-twin", "panda", "single-cube", "simulation"]
    facts = [
        Fact("The package is a world model that unifies kinematic information and semantic meaning for robotic "
             "world representations", source="upstream_code", ref="pyproject.toml:15"),
        Fact("The package's adapters import scenes in formats including URDF, USD and MJCF", source="vendor_doc",
             ref="README.md:44"),
        Fact("The scene is the MuJoCo MJCF model named 'panda scene'", source="upstream_code", ref=f"{MODEL}:1"),
        Fact("The scene compiles angles in radians and derives limits automatically (autolimits true)",
             source="upstream_code", ref=f"{MODEL}:2"),
        Fact("The panda default class gives its joints the range -2.8973 to 2.8973 rad, armature 0.1 and damping 1",
             source="upstream_code", ref=f"{MODEL}:7"),
        Fact("The panda default class gives general actuators the control range -2.8973 to 2.8973 and force range "
             "-87 to 87", source="upstream_code", ref=f"{MODEL}:8"),
        Fact("The panda default class gives position actuators the force range -100 to 100", source="upstream_code",
             ref=f"{MODEL}:9"),
        Fact("The finger default class gives finger joints the slide type on axis 0 1 0 and the range 0 to 0.04 m",
             source="upstream_code", ref=f"{MODEL}:10-11"),
        Fact("The arm is the body chain link0 to link7 with the hinge joints joint1 to joint7", source="upstream_code",
             ref=f"{MODEL}:41-71"),
        Fact("joint2 has the range -1.7628 to 1.7628 rad", source="upstream_code", ref=f"{MODEL}:51"),
        Fact("joint4 has the range -3.0718 to -0.0698 rad", source="upstream_code", ref=f"{MODEL}:59"),
        Fact("joint6 has the range -0.0175 to 3.7525 rad", source="upstream_code", ref=f"{MODEL}:67"),
        Fact("The hand carries the two slide joints finger_joint1 and finger_joint2, both of the finger class",
             source="upstream_code", ref=f"{MODEL}:78-83"),
        Fact("An equality constraint couples finger_joint1 and finger_joint2", source="upstream_code",
             ref=f"{MODEL}:97"),
        Fact("The actuator section declares seven position actuators for joint1 to joint7 and one general actuator "
             "for finger_joint1", source="upstream_code", ref=f"{MODEL}:101-115"),
        Fact("actuator1 and actuator3 have the control range -2.8973 to 2.8973 rad and actuator2 has -1.7628 to "
             "1.7628 rad", source="upstream_code", ref=f"{MODEL}:101-106"),
        Fact("actuator4 has the control range -3.0718 to -0.0698 rad and actuator5 has -2.8973 to 2.8973 rad",
             source="upstream_code", ref=f"{MODEL}:107-110"),
        Fact("actuator6 has the control range -0.0175 to 3.7525 rad", source="upstream_code", ref=f"{MODEL}:111-112"),
        Fact("actuator7 is the position actuator for joint7 and states no control range of its own",
             source="upstream_code", ref=f"{MODEL}:113"),
        Fact("actuator8 is the general actuator for finger_joint1 with the control range 0 to 0.04 m",
             source="upstream_code", ref=f"{MODEL}:114-115"),
        Fact("The integration step is 0.005 s and the integrator is implicitfast with 5 iterations and 8 line-search "
             "iterations", source="upstream_code", ref=f"{MODEL}:118"),
        Fact("The custom numeric max_contact_points is 12", source="upstream_code", ref=f"{MODEL}:122-123"),
        Fact("The scene has a static plane floor and a free-floating box body of size 0.02 0.02 0.03 m",
             source="upstream_code", ref=f"{MODEL}:143-153"),
        Fact("The keyframes home, pickup and pickup1 each give 16 qpos values and 8 ctrl values", source="upstream_code",
             ref=f"{MODEL}:156-165"),
        Fact("The upstream test suite loads this exact MJCF file", source="upstream_code", ref=f"{TEST}:41"),
        Fact("The upstream MJCF adapter parses a scene with mujoco.MjSpec.from_file", source="upstream_code",
             ref=f"{MJCF_ADAPTER}:61"),
        Fact("The upstream MJCF adapter iterates the spec's actuators when building its world", source="upstream_code",
             ref=f"{MJCF_ADAPTER}:82"),
        Fact("The package requires Python 3.10 or newer", source="upstream_code", ref="pyproject.toml:17"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:mjx_single_cube_no_mesh",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from mj_resetData and the model has no random "
                     "element, so a fixed ctrl sequence and tick count repeat the trajectory.  The package's fake "
                     "backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the model's integration "
            "step, joint dimensions and actuator control ranges and moves each actuated joint toward its control "
            "target; it computes no inertias, contacts, equality constraints or actuator dynamics, so no trajectory "
            "here is an engine result",
            "the box's free joint and the finger equality constraint are not simulated: the box qpos values stay "
            "at zero, and only finger_joint1 is actuated, so finger_joint2 stays at zero instead of following it",
            "the bridge reset calls mj_resetData and starts from the model defaults (zero qpos in the stand-in), "
            "not from the home, pickup or pickup1 keyframes of the model",
            "the upstream simulation adapter uses the external Multiverse connector (mujoco_connector) in "
            "src/semantic_digital_twin/adapters/multi_sim.py, which this package neither installs nor runs; the "
            "package serves the MJCF model directly through the MujocoBridge",
            "no rendering, cameras or sensor publication: only the bridge's time, qpos, qvel and ctrl state is "
            "exposed",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 5 ms step only",
            "the model is a simulation asset: no physical robot is modelled or controlled and nothing here was "
            "validated against hardware",
            "MuJoCo is not installed where the acceptance gate runs, so the stand-in was not compared with an "
            "engine load of this model",
        ],
    }
