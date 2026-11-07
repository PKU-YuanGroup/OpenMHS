"""OpenMHS driver for gh.luckyrobots/g1-manipulation-challenge: the G1 pick-and-place MuJoCo scene.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's first model (``scene.xml``) and the
MuJoCo bridge derives the contract from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl}}``
with one control value per actuator; the 29 body position actuators are in default class ``g1``, whose
``<position inheritrange="1"/>`` (``g1.xml:9-10``) makes each control range the matching joint range.  The 14 finger
position actuators carry no class, no ``ctrlrange`` and no ``inheritrange`` (``g1.xml:435-449``), so MuJoCo leaves
their control unclamped and the bridge publishes ``action.ctrl[29]`` to ``action.ctrl[42]`` as ``operator_required``
(see the paragraph below).
``cap.world.reset.v1`` runs
``mj_resetData``/``mj_forward`` and returns the model defaults; the world state is
``{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}``.

The card's models are ``scene.xml`` (the scene, ``models[0]``) and ``g1.xml`` (the robot it includes); the package
serves the scene, which adds the brown source table, the target table, the red cylinder with its free joint and the
fixed cameras (``scene.xml:1-8,49-96``).  The model is read from the read-only clone in place; the package copies
neither the model nor its mesh assets and never imports or runs upstream code.  The 5 ms step is the MJCF's own
option (``g1.xml:4``) and is also set explicitly by the upstream runner (``run.py:527``).

MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py); it parses the same MJCF for the joint
layout, the actuator list and their control ranges, but its integration is a placeholder first-order motion, not
MuJoCo's physics, and the fidelity ``gaps`` say so.  A backend name that ``backends`` does not list (``sim``) imports
the real ``mujoco`` module and loads the same file; that path was not run here.

The bridge publishes one limit per control channel: the inherited joint range for each of the 29 body actuators
(``upstream_code``) and ``operator_required`` for the 14 finger actuators, so the endpoint refuses a step that sets a
finger control (``MHS.SAFETY.LIMITS_UNSET``, before any native call) until the site's ``site-limits.json`` bounds it.
``site-limits.example.json`` is the operator example the gate serves: the finger joint ranges
(``g1.xml:254-289,347-382``), operator data, not bounds the model states.  (Model review 2026-11-05: the author's
stand-in gave the finger actuators those joint ranges as an envelope published as the model's ctrlrange, and a bridge
subclass left them unbounded on a real model; both are gone with the SDK's treatment of actuators without a control
range.)  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

SCENE = "scene.xml"
ROBOT = "g1.xml"
README = "README.md"
RUN = "run.py"
#: The card's models[0], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/luckyrobots/g1-manipulation-challenge/" + SCENE


class LuckyRobotsG1(MujocoDriver):
    device_id = "luckyrobots-g1"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Lucky Robots G1 pick-and-place scene (MuJoCo model)"
    vendor, model = "Lucky Robots", "G1 pick-and-place (g1_table_red_block)"
    tags = ["g1", "humanoid", "luckyrobots", "manipulation", "mujoco", "pick-and-place", "simulation", "world"]
    facts = [
        Fact("The scene is a MuJoCo scene named g1_table_red_block with the G1 robot, a ground plane, a brown "
             "table, a target table, a red cylindrical block on a free joint, and head, wrist and fixed cameras",
             source="upstream_code", ref=f"{SCENE}:1-5"),
        Fact("The scene includes g1.xml", source="upstream_code", ref=f"{SCENE}:8"),
        Fact("The robot model is g1_29dof_rev_1_0, which compiles angles in radians, resolves meshes from assets "
             "and uses autolimits", source="upstream_code", ref=f"{ROBOT}:1-2"),
        Fact("The model integrates with the implicitfast scheme at a 0.005 s timestep, with a pyramidal cone and "
             "gravity 0 0 -9.81", source="upstream_code", ref=f"{ROBOT}:4-6"),
        Fact("The upstream runner also sets model.opt.timestep to 0.005, which it says must match training",
             source="upstream_code", ref=f"{RUN}:527"),
        Fact("The robot base body pelvis is at -0.6 0 0.79 and carries the freejoint floating_base_joint",
             source="upstream_code", ref=f"{ROBOT}:81-85"),
        Fact("The G1 has 29 actuated body degrees of freedom: 12 leg, 3 waist and 14 arm joints",
             source="vendor_doc", ref=f"{README}:66-69"),
        Fact("The position actuator default class g1 sets inheritrange 1, so an actuator of that class takes its "
             "control range from the matching joint range", source="upstream_code", ref=f"{ROBOT}:9-10"),
        Fact("The joint ranges are explicit, for example the left hip pitch joint is -2.5307 to 2.8798 rad",
             source="upstream_code", ref=f"{ROBOT}:93"),
        Fact("The actuator section has 29 position actuators of class g1 for the body joints and then 14 position "
             "actuators for the finger joints", source="upstream_code", ref=f"{ROBOT}:400-449"),
        Fact("The 14 finger actuators have a joint but no class, ctrlrange or inheritrange", source="upstream_code",
             ref=f"{ROBOT}:435-449"),
        Fact("The right finger joints have explicit ranges: thumb 0 is -1.0472 to 1.0472, thumb 1 -1.0472 to "
             "0.724312, index 0 0 to 1.5708 and index 1 0 to 1.74533", source="upstream_code",
             ref=f"{ROBOT}:347-382"),
        Fact("The red block is a free body at 0.0 0.026 0.85 with the freejoint red_block_joint and a cylinder of "
             "radius 0.02 and half-height 0.035", source="upstream_code", ref=f"{SCENE}:80-84"),
        Fact("The source table top is a 0.8 by 0.5 m box at z 0.713 and the target table top is a 0.7 by 0.5 m "
             "box at z 0.613", source="upstream_code", ref=f"{SCENE}:49-65"),
        Fact("The head camera head_cam is on the torso", source="upstream_code", ref=f"{ROBOT}:207"),
        Fact("The wrist camera wrist_cam is on the right palm", source="upstream_code", ref=f"{ROBOT}:344"),
        Fact("The upstream runner loads scene.xml, sets the 0.005 s timestep and initializes qpos x -0.6, z 0.76 "
             "and the default joint positions before stepping with mj_step", source="upstream_code",
             ref=f"{RUN}:524-538"),
        Fact("The upstream runner writes the 29 body actuator targets and the right finger targets into data.ctrl, "
             "closing the grip to 0.8, -0.9, -1.5, 1.4, 1.5, 1.4 and 1.5 and opening it to 0.0",
             source="upstream_code", ref=f"{RUN}:442-462"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step, the determinism kind and the lockstep clock; the gaps below are this package's.
    fidelity = {
        "engine": "mujoco:g1_table_red_block",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates the fixed model deterministically from the model defaults; the bridge "
                     "accepts a seed in cap.world.reset.v1 but does not use it and a reset restores the model "
                     "defaults, so one ctrl sequence repeats a trajectory on the same engine.  This package's fake "
                     "is deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 5.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its "
            "g1.xml include for the two free joints, the 43 hinge joints, the 43 position actuators, the 29 "
            "inherited control ranges (the 14 finger actuators have none) and the 0.005 s option step, then moves "
            "each actuated joint a placeholder "
            "fraction of the remaining distance to its control target; it computes no inertia, torque, contact, "
            "friction, gravity, equality, damping, armature or actuator-force dynamics and produces no MuJoCo "
            "trajectory",
            "the 14 finger actuators have no ctrlrange in the MJCF (g1.xml:435-449), so the bridge publishes "
            "action.ctrl[29] to [42] operator_required: a step that sets them is refused until the site's "
            "site-limits.json bounds them; the example overlay's finger joint ranges (g1.xml:254-289,347-382) are "
            "operator data, not bounds the model states",
            "the stand-in loads no mesh or texture and resolves no collision or contact, so the red cylinder's "
            "free joint is carried in qpos/qvel but the cylinder never falls, rolls or is grasped; the two "
            "tables, the ground and the robot links do not collide",
            "the stand-in applies no joint limit, no actuator force range, no sensor or camera model and no "
            "implicitfast integration; it carries 57 qpos and 55 qvel values (two free joints and 43 hinge "
            "joints) and 43 control values",
            "the bridge reset restores the MJCF model defaults (pelvis at -0.6 0 0.79 with zero joint angles), "
            "while run.py resets to a custom pose (x -0.6, z 0.76 and the default joint positions from "
            "model_config.json, run.py:637-645); the driver uses mj_resetData, not the runner's pose",
            "NOT COVERED: the RGB camera images of head_cam, wrist_cam, overhead, side_view and tracking, and "
            "the ONNX walker, croucher, rotator and right-reacher policies, the keyboard controller, the grip "
            "toggle and the model_config.json action scales; cap.world.step.v1 and cap.world.reset.v1 carry the "
            "world state and the actuator targets only",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine and the sim backend (real mujoco) was not run",
            "no physical G1 is modelled and nothing was validated against hardware",
        ],
    }
