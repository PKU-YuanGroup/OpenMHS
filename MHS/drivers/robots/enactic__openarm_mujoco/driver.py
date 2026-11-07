"""OpenMHS driver for gh.enactic/openarm_mujoco: the OpenArm v1 bimanual MJCF scene as a simulated MuJoCo world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary scene, ``v1/scene.xml``, which
includes the two-arm model ``v1/openarm_bimanual.xml``.  The bridge loads the scene with the MuJoCo engine, derives
``cap.world.step.v1``'s ``action.ctrl`` from the model's ``actuator_ctrlrange`` (16 position actuators: seven arm
joints and one finger per arm), writes ``data.ctrl``, runs ``mj_step`` for ``ticks``, and serves
``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state
(``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical OpenArm is driven.  The scene and its
includes are read from the read-only clone at the pinned commit and are not copied into this package.  MuJoCo is not
installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py), which reads the model shape from the same scene but integrates a placeholder motion instead of the
engine's physics; the fidelity ``gaps`` below state every difference.

Every Fact cites a line of the clone at commit 0e050bb5d3472b75c6bfa00b310a77c7c2c5be79.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical arm.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

SCENE = "v1/scene.xml"
ROBOT = "v1/openarm_bimanual.xml"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/enactic/openarm_mujoco/" + SCENE


class OpenArm(MujocoDriver):
    device_id = "openarm-bimanual"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "OpenArm v1 bimanual scene (MuJoCo)"
    vendor, model = "Enactic, Inc.", "OpenArm v1 bimanual MJCF"
    tags = ["mujoco", "openarm", "bimanual", "robot arm", "manipulation", "simulation"]
    facts = [
        Fact("The repository holds MJCF description files for OpenArm v2, Cell, v1 and v0.3 simulation in MuJoCo",
             source="vendor_doc", ref="README.md:1-4"),
        Fact("The README's v1 bimanual launch command opens v1/scene.xml with the home keyframe", source="vendor_doc",
             ref="README.md:64"),
        Fact("The v1 scene is the MJCF model 'openarm_bimanual scene' and includes openarm_bimanual.xml from the same "
             "directory", source="upstream_code", ref=f"{SCENE}:17-18"),
        Fact("The included bimanual model sets the integration step to 0.001 s and the implicitfast integrator",
             source="upstream_code", ref=f"{ROBOT}:19"),
        Fact("The actuator section declares 16 position actuators: eight per arm (seven arm joints and one finger)",
             source="upstream_code", ref=f"{ROBOT}:547-563"),
        Fact("The left arm control ranges are joint1 -3.490659 to 1.396263 rad, joint2 -3.3161253267948965 to "
             "0.17453267320510335, joint3 -1.570796 to 1.570796, joint4 0 to 2.443461, joint5 -1.570796 to "
             "1.570796, joint6 -0.785398 to 0.785398 and joint7 -1.570796 to 1.570796", source="upstream_code",
             ref=f"{ROBOT}:548-554"),
        Fact("The right arm control ranges are joint1 -1.396263 to 3.490659 rad, joint2 -0.17453267320510335 to "
             "3.3161253267948965, joint3 -1.570796 to 1.570796, joint4 0 to 2.443461, joint5 -1.570796 to "
             "1.570796, joint6 -0.785398 to 0.785398 and joint7 -1.570796 to 1.570796", source="upstream_code",
             ref=f"{ROBOT}:556-562"),
        Fact("The motor_finger default class gives the finger position actuators the control range -0.005 to 0.044 m",
             source="upstream_code", ref=f"{ROBOT}:41-45"),
        Fact("The left arm's first joint is the hinge openarm_left_joint1 with the range -3.490659 to 1.396263 rad",
             source="upstream_code", ref=f"{ROBOT}:170-171"),
        Fact("The right arm's first joint is the hinge openarm_right_joint1 with the range -1.396263 to 3.490659 rad",
             source="upstream_code", ref=f"{ROBOT}:349-350"),
        Fact("The left hand has two slide finger joints, openarm_left_finger_joint1 and openarm_left_finger_joint2, "
             "with the range 0 to 0.044 m", source="upstream_code", ref=f"{ROBOT}:297-315"),
        Fact("The right hand has the matching pair of slide finger joints, openarm_right_finger_joint1 and "
             "openarm_right_finger_joint2, also with the range 0 to 0.044 m", source="upstream_code",
             ref=f"{ROBOT}:476-495"),
        Fact("The two fingers of each hand are coupled by an equality constraint", source="upstream_code",
             ref=f"{ROBOT}:540-543"),
        Fact("The model provides a home keyframe with 18 qpos values (nine per arm) and 16 ctrl values (eight per "
             "arm)", source="upstream_code", ref=f"{ROBOT}:566-572"),
        Fact("The package requires Python 3.10 or newer and depends on mujoco 3.6.0 or newer and numpy",
             source="upstream_code", ref="pyproject.toml:27-30"),
        Fact("The upstream launcher loads a model with mujoco.MjModel.from_xml_path and creates its data with "
             "mujoco.MjData", source="upstream_code", ref="src/openarm_mujoco/v2/launch.py:72-73"),
        Fact("The launcher hands the model to mujoco.viewer.launch unless --static is given; static mode calls "
             "mj_forward without stepping", source="upstream_code", ref="src/openarm_mujoco/v2/launch.py:114-128"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:openarm_bimanual",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so the same ctrl sequence and tick count repeat the trajectory.  The package's "
                     "fake backend is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses v1/scene.xml and its "
            "included v1/openarm_bimanual.xml for the 1 ms step, the 18 qpos and 18 dof coordinates and the 16 "
            "actuator ctrlranges, then moves each actuated joint toward its control target; it computes no "
            "inertias, contacts, tendons, finger equalities or actuator dynamics, so no trajectory here is a "
            "MuJoCo result",
            "the meshes and textures under v1/meshes are not loaded by the stand-in; a real engine load needs them "
            "beside the scene, which the pinned clone provides",
            "the bridge's reset calls mj_resetData and starts from the model defaults (zero qpos in the stand-in), "
            "not from the home keyframe of v1/openarm_bimanual.xml:566-572; a client that wants that pose must send "
            "the keyframe ctrl and step",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 1 ms step only; "
            "the upstream launcher's non-static viewer owns real-time pacing "
            "(src/openarm_mujoco/v2/launch.py:114-116), which this package does not use",
            "no rendering, cameras or sensor publication: the model's sensor section is not exposed as an "
            "observation, only the bridge's time, qpos, qvel and ctrl state is",
            "the model is a simulation asset for OpenArm: no physical arm is modelled or controlled and nothing "
            "here was validated against the hardware",
        ],
    }
