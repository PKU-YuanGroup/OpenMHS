"""OpenMHS driver for gh.kscalelabs/mujoco_playground: the K-Bot feet-only flat terrain scene as a simulated world.

A ``MujocoDriver`` is configuration only.  ``model_path`` names the card's primary scene, ``models[0]``
``playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml``, which includes the robot model
``playground/kbot/xmls/kbot.xml``.  The bridge loads the scene with the MuJoCo engine, derives
``cap.world.step.v1``'s ``action.ctrl`` from the model's ``actuator_ctrlrange`` (20 position actuators whose
``inheritrange`` of 1 makes each control range the matching joint range), writes ``data.ctrl``, runs ``mj_step``
for ``ticks``, and serves ``cap.world.reset.v1`` with ``mj_resetData`` + ``mj_forward``.  The world state is the
bridge's integration state (``time_ms``, ``qpos``, ``qvel``, ``ctrl``, ``tick``, ``timestep_ms``, ``seed``).

The device is simulated (R0): there is no hardware backend and no physical K-Bot is driven.  The scene and its
include are read from the read-only clone at the pinned commit and are not copied into this package.  MuJoCo is not
installed where the acceptance gate runs, so ``backends["fake"]`` is this package's stand-in ``mujoco`` module
(fake.py), which reads the model shape from the same scene but integrates a placeholder motion instead of the
engine's physics; the fidelity ``gaps`` below state every difference.  ``kbot.xml`` declares no ``<option
timestep>``, so the engine's default 0.002 s applies and the bridge reads it from the loaded model.

Every Fact cites a line of the clone at commit 9762ac537cf8d03197ce8bfeaf116f56687f3c19.  This package is
model-authored and unreviewed: it is checked on the fake backend only, and nothing here ran the MuJoCo engine or a
physical robot.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import fake_mujoco

SCENE = "playground/kbot/xmls/scene_mjx_feetonly_flat_terrain.xml"
ROBOT = "playground/kbot/xmls/kbot.xml"
#: The card's models[0] relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL_PATH = "../../../../robots/kscalelabs/mujoco_playground/" + SCENE


class KbotFlat(MujocoDriver):
    device_id = "kbot-flat"
    model_path = MODEL_PATH
    backends = {"fake": fake_mujoco}
    display_name = "K-Bot feet-only flat terrain scene (MuJoCo)"
    vendor, model = "K-Scale Labs", "kbot feetonly flat terrain scene"
    tags = ["mujoco", "kbot", "humanoid", "feet-only", "flat-terrain", "simulation"]
    facts = [
        Fact("The README names the project the K-Scale Mujoco Playground Library", source="vendor_doc",
             ref="README.md:14"),
        Fact("The setup script names the distribution kscale-mujoco-playground and requires Python 3.12 or newer",
             source="upstream_code", ref="setup.py:27-36"),
        Fact("The K-Bot flat terrain scene is the MJCF model 'kbot feetonly flat terrain scene' and includes "
             "kbot.xml from the same directory", source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The included robot model is named k-bot_sim", source="upstream_code", ref=f"{ROBOT}:1"),
        Fact("The model compiles joint and actuator angles in radians", source="upstream_code", ref=f"{ROBOT}:30"),
        Fact("The robot default class gives every position actuator inheritrange 1, so its control range is the "
             "matching joint range", source="upstream_code", ref=f"{ROBOT}:3-4"),
        Fact("The motor_00, motor_02, motor_03 and motor_04 default classes set joint armatures of 0.0005, 0.002, "
             "0.005 and 0.007, friction losses of 0.1, 0.1, 0.3 and 0.1, actuator force ranges of -14 to 14, -17 "
             "to 17, -60 to 60 and -120 to 120, and position gains of 20, 20, 50 and 100", source="upstream_code",
             ref=f"{ROBOT}:5-20"),
        Fact("The floating base body is placed at z 1.08006263 and carries the free joint named floating_base",
             source="upstream_code", ref=f"{ROBOT}:64-65"),
        Fact("The left arm hinge ranges are: shoulder pitch 0 to 3.141593 rad, shoulder roll -3.630285 to "
             "0.479966 rad, shoulder yaw -1.570796 to 1.570796 rad, elbow -2.530727 to 0 rad and wrist -3.141593 "
             "to 3.141593 rad", source="upstream_code", ref=f"{ROBOT}:68-84"),
        Fact("The right arm hinge ranges are: shoulder pitch -3.141593 to 0 rad, shoulder roll -0.479966 to "
             "3.630285 rad, shoulder yaw -1.570796 to 1.570796 rad, elbow 0 to 2.530727 rad and wrist -3.141593 "
             "to 3.141593 rad", source="upstream_code", ref=f"{ROBOT}:93-109"),
        Fact("The left leg hinge ranges are: hip pitch -1.570796 to 1.570796 rad, hip roll -3.185226 to 0.349066 "
             "rad, hip yaw -1.570796 to 1.570796 rad, knee 0 to 2.094395 rad and ankle -0.698132 to 0.698132 rad",
             source="upstream_code", ref=f"{ROBOT}:118-134"),
        Fact("The right leg hinge ranges are: hip pitch -1.570796 to 1.570796 rad, hip roll -0.349066 to 3.185226 "
             "rad, hip yaw -1.570796 to 1.570796 rad, knee -2.094395 to 0 rad and ankle -0.698132 to 0.698132 rad",
             source="upstream_code", ref=f"{ROBOT}:144-160"),
        Fact("The actuator section declares 20 position actuators, one for each hinge joint, in the motor_02, "
             "motor_03 and motor_04 default classes", source="upstream_code", ref=f"{ROBOT}:175-196"),
        Fact("The scene's floor is a plane with friction 0.6 and condim 3", source="upstream_code",
             ref=f"{SCENE}:22-25"),
        Fact("The scene's keyframe block is commented out, so the model has no home or standing keyframe",
             source="upstream_code", ref=f"{SCENE}:27-30"),
        Fact("The model declares an accelerometer, a gyro, a magnetometer and frame sensors at the imu site",
             source="upstream_code", ref=f"{ROBOT}:198-206"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, and the world state stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity FID-002).  The bridge derives the engine,
    #: the determinism kind, the timestep and the lockstep clock from the loaded model; they are written out so the
    #: whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:kbot_feetonly_flat_terrain",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "exact",
            "seed_control": "none",
            "notes": "MuJoCo integrates the MJCF deterministically from the reset state and the model has no "
                     "random element, so the same ctrl sequence and tick count repeat the trajectory; the "
                     "bridge's integration-state snapshot restores it exactly.  The package's fake backend is "
                     "deterministic too, but its placeholder motion is not the engine's physics.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the scene and its "
            "included kbot.xml for the 2 ms engine default step, the 27 qpos and 26 dof coordinates and the 20 "
            "actuator ctrlranges, then moves each actuated joint toward its control target; it computes no "
            "inertias, contacts, friction, meshes or actuator dynamics, so no trajectory here is a MuJoCo result",
            "kbot.xml declares no <option timestep>, so the MuJoCo engine default 0.002 s applies; the bridge "
            "reads the step from the loaded model and the stand-in uses the same default",
            "the bridge's reset calls mj_resetData and starts from the model defaults (the free body at its XML "
            "pose, z 1.08006263, with an identity quaternion and zero hinge angles), not from a keyframe; the "
            f"scene's keyframe block is commented out ({SCENE}:27-30)",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the model's 2 ms step only",
            "no rendering, cameras or sensor publication: the model's imu and frame sensors are not exposed as an "
            "observation, only the bridge's time, qpos, qvel and ctrl state is",
            "the meshes and textures under playground/kbot/xmls/meshes are not loaded by the stand-in; a real "
            "engine load needs them beside the scene, which the pinned clone provides",
            "the model is a simulation asset for the K-Bot: no physical robot is modelled or controlled and "
            "nothing here was validated against hardware",
        ],
    }
