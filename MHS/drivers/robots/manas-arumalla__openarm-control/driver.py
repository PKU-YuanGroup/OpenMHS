"""OpenMHS driver for gh.manas-arumalla/openarm-control: the OpenArm v2 unscrew scene (a MuJoCo world).

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary model,
``v2/openarm_mujoco_v2/unscrew_scene.xml``, which attaches ``openarm_pedestal.xml`` and, through it,
``openarm_v20_bimanual.xml``.  The bridge loads the flattened scene with the MuJoCo engine, derives
``cap.world.step.v1``'s ``action.ctrl`` from each actuator's ``ctrlrange`` (the 16 arm position actuators plus the cap
lift actuator), writes ``data.ctrl``, runs ``mj_step`` for ``ticks`` and serves ``cap.world.reset.v1`` with
``mj_resetData`` + ``mj_forward``.  The world state is the bridge's integration state (``time_ms``, ``qpos``,
``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical arm is driven.  The scene and its attached
models are read from the read-only clone at the pinned commit and are not copied into this package.  MuJoCo is not
installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py), which reads the same model tree but integrates a placeholder motion instead of the engine's physics; the
fidelity ``gaps`` state every difference.

The card's entry symbols are Gymnasium task environment classes, not MJCF files; the family-config ``MujocoDriver``
serves the card's models[0] as a raw simulated world, and the task environment's observations, reward and episode
logic are not served (RESULT.json notes).

Every Fact cites a line of the clone at commit 14ea59faad6706b9add5d7f8d386e43239a6360f.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical arm.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

SCENE = "v2/openarm_mujoco_v2/unscrew_scene.xml"
PEDESTAL = "v2/openarm_mujoco_v2/openarm_pedestal.xml"
BIMANUAL = "v2/openarm_mujoco_v2/openarm_v20_bimanual.xml"
#: The card's models[0] relative to this package directory: the read-only clone at the pinned commit.
MODEL_PATH = "../../../../robots/manas-arumalla/openarm-control/" + SCENE


class OpenArmUnscrew(MujocoDriver):
    device_id = "openarm-unscrew"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "OpenArm v2 unscrew scene (MuJoCo)"
    vendor, model = "Manas Reddy Arumalla", "openarm_v20_unscrew MJCF"
    tags = ["mujoco", "openarm", "unscrew", "bottle-opening", "robot-arm", "simulation"]
    facts = [
        Fact("The repository is a control, motion-planning, bimanual-coordination and reinforcement-learning "
             "platform for the Enactic OpenArm v2 (7-DOF x 2 plus grippers) in MuJoCo", source="vendor_doc",
             ref="README.md:11-13"),
        Fact("The package maps the scene name 'unscrew' to v2/openarm_mujoco_v2/unscrew_scene.xml",
             source="upstream_code", ref="openarm_control/config.py:38-71"),
        Fact("The unscrew scene is the MJCF model openarm_v20_unscrew with a 0.002 s integration timestep",
             source="upstream_code", ref=f"{SCENE}:14-18"),
        Fact("The unscrew scene declares openarm_pedestal.xml as an attachable model asset and attaches model "
             "arm_pedestal in its worldbody", source="upstream_code", ref=f"{SCENE}:33-43"),
        Fact("The pedestal model declares openarm_v20_bimanual.xml as an attachable model asset and attaches model "
             "bimanual at a frame 0.698 m above the pedestal origin", source="upstream_code",
             ref=f"{PEDESTAL}:44-54"),
        Fact("The bimanual model is the MJCF model openarm_v20_visual with 16 position actuators, eight per arm "
             "(seven joints and one finger)", source="upstream_code", ref=f"{BIMANUAL}:349-365"),
        Fact("The left arm control ranges are joint1 -3.49066 to 1.39626 rad, joint2 -3.31613 to 0.174533 rad, "
             "joint3 -1.5708 to 1.5708 rad, joint4 0 to 2.44346 rad, joint5 -1.5708 to 1.5708 rad, joint6 "
             "-0.785398 to 0.785398 rad, joint7 -1.5708 to 1.5708 rad and the finger 0 to 0.7854",
             source="upstream_code", ref=f"{BIMANUAL}:350-357"),
        Fact("The right arm control ranges are joint1 -1.39626 to 3.49066 rad, joint2 -0.174533 to 3.31613 rad, "
             "joint3 -1.5708 to 1.5708 rad, joint4 0 to 2.44346 rad, joint5 -1.5708 to 1.5708 rad, joint6 "
             "-0.785398 to 0.785398 rad, joint7 -1.5708 to 1.5708 rad and the finger -0.7854 to 0",
             source="upstream_code", ref=f"{BIMANUAL}:358-365"),
        Fact("The scene adds the cap_lift_drive position actuator on the cap_lift joint with control range 0 to "
             "0.12", source="upstream_code", ref=f"{SCENE}:82"),
        Fact("The cap has a hinge turn joint and a slide lift joint with a 0 to 0.12 range", source="upstream_code",
             ref=f"{SCENE}:60-61"),
        Fact("The ready keyframe states nq = 20 as left arm coordinates 0-8, right arm coordinates 9-17, cap_turn "
             "18 and cap_lift 19", source="upstream_code", ref=f"{SCENE}:85-91"),
        Fact("Each hand's two finger joints are coupled by a joint equality constraint", source="upstream_code",
             ref=f"{BIMANUAL}:345-348"),
        Fact("The arm joint classes motor_DM8009, motor_DM4340, motor_DM4310 and motor_DM3507 default to hinge "
             "joints, and the finger class defaults to a limited hinge joint", source="upstream_code",
             ref=f"{BIMANUAL}:22-40"),
        Fact("The package requires Python 3.10 or newer, pins mujoco==3.8.1 and depends on numpy",
             source="upstream_code", ref="pyproject.toml:10-23"),
        Fact("The unscrew demo loads the scene with mujoco.MjModel.from_xml_path, creates MjData and resets to the "
             "ready keyframe", source="upstream_code", ref="openarm_control/demos/demo_unscrew.py:27-31"),
        Fact("The implementation log describes the single-arm unscrew scene as a clamped bottle whose threaded cap "
             "has a turn hinge, a lift slide and a lift actuator", source="vendor_doc",
             ref="docs/IMPLEMENTATION_LOG.md:1285-1287"),
        Fact("The OpenArm v2 MuJoCo model under v2/openarm_mujoco_v2 (meshes and MJCF) is attributed to Enactic, "
             "Inc. under Apache-2.0", source="vendor_doc", ref="docs/MODELS.md:61-62"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:openarm_v20_unscrew",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so the same ctrl sequence and tick count repeat the trajectory.  The "
                     "package's fake backend is deterministic too, but its placeholder motion is not the engine's "
                     "physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene, follows the "
            "attachable models openarm_pedestal.xml and openarm_v20_bimanual.xml, and takes the 2 ms step, the 20 "
            "qpos coordinates, the 20 dof coordinates and the 17 actuator ctrlranges from that tree, then moves "
            "each actuated joint toward its control target; it computes no inertias, contacts, tendons, finger "
            "equalities or actuator dynamics, so no trajectory here is a MuJoCo result",
            "the stand-in inserts an attached model's actuators at the attach element in document order (the 16 "
            "arm actuators, then the scene's cap_lift actuator); MuJoCo was not installed where the gate runs, so "
            "the engine's ctrl index order was not confirmed against this stand-in",
            "the meshes and textures under v2/openarm_mujoco_v2/assets are not loaded by the stand-in; a real "
            "engine load needs them beside the scene, which the pinned clone provides",
            "the bridge's reset calls mj_resetData and starts from the model defaults (zero qpos in the stand-in), "
            "not from the ready keyframe of unscrew_scene.xml:85-91; a client that wants that pose must send its "
            "qpos and step",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 2 ms step only",
            "no rendering, cameras or sensor publication: the scene's tablecam and frontcam are not exposed as an "
            "observation, only the bridge's time, qpos, qvel and ctrl state is",
            "the upstream task logic on top of the model (UnscrewTask, the demo controller and its rewards) is not "
            "served; this package exposes the raw simulated model",
            "the stand-in snapshot covers time, qpos, qvel and ctrl only; MuJoCo's mjSTATE_INTEGRATION also covers "
            "act, warm-start and mocap fields, which this model does not use",
            "the model is a simulation asset for OpenArm: no physical arm is modelled or controlled and nothing "
            "here was validated against the hardware",
        ],
    }
