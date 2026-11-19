"""OpenMHS driver for gh.jeongeun980906/lerobot-mujoco-tutorial: the OMY robot MJCF.

A ``MujocoDriver`` is configuration only: ``model_path`` names the card's first model
(``asset/robotis_omy/scene.xml``) and the bridge derives the contract from the model it loads.  The served scene
includes the OMY six-joint arm and its four-finger gripper; its ten ``<position>`` actuators give
``cap.world.step.v1`` an ``action.ctrl`` vector of ten numbers, each bounded per actuator by the model's effective
``actuator_ctrlrange`` (the six arm actuators inherit ``-6.28319 6.28319`` from default class ``Y``, the four gripper
actuators declare ``0 1.1``, ``0 1``, ``0 1.1`` and ``0 1``).  ``cap.world.reset.v1`` restores the model defaults
with ``mj_resetData`` + ``mj_forward``.

The card's entry symbols ``mujoco_env.y_env:SimpleEnv`` and ``mujoco_env.y_env2:SimpleEnv2`` are the repository's
concrete MuJoCo environment wrappers; they construct ``MuJoCoParserClass`` on an MJCF file and expose a seven-element
joint-action step.  This package serves the primary environment-step interface through the MJCF model itself, as the
card's ``helper`` and candidate ``cap.world.*`` classes specify, rather than through the wrapper (which also opens a
GLFW viewer).  The wrapper's camera helpers are not carried by the MuJoCo bridge and are not covered (facts.md).

The device is simulated (R0): the model is a simulation asset, there is no hardware backend and no
operator-required bound.  MuJoCo is not installed and cannot be installed where the acceptance gate runs (no network,
no pip), so ``backends["fake"]`` is this package's stand-in ``mujoco`` module (fake.py).  It reads the same model for
the ten hinge joints, the ten position actuators, their effective control ranges and the option timestep, but its
integration is a placeholder motion, not MuJoCo's physics; the F0 fidelity contract in ``fidelity_by_backend`` lists
every difference.  A backend name that ``backends`` does not list (``sim``) loads the real ``mujoco`` module and the
same file; that path was not run here.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package,
never imported and never modified).  Every Fact cites a line or line range of the clone at commit
931f26f267386a83669bc8b937404824dfa21021.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and no MuJoCo, hardware or simulator run is claimed.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], relative to the package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "asset/robotis_omy/scene.xml"
MODEL_PATH = "../../../../robots/jeongeun980906/lerobot-mujoco-tutorial/" + MODEL
README = "README.md"
SCENE = "asset/robotis_omy/scene.xml"
OMY = "asset/robotis_omy/omy.xml"
EXAMPLE_SCENE = "asset/example_scene_y.xml"
Y_ENV = "mujoco_env/y_env.py"
Y_ENV2 = "mujoco_env/y_env2.py"


class LerobotOmyScene(MujocoDriver):
    device_id = "lerobot-omy-scene"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "LeRobot MuJoCo tutorial OMY robot scene"
    vendor, model = "jeongeun980906", "open_manipulator_y"
    tags = ["lerobot", "mujoco", "mjcf", "omy", "open-manipulator", "simulation", "tabletop"]
    facts = [
        Fact("The README title is 'LeRobot Tutorial with MuJoCo' and it describes minimal examples for collecting "
             "demonstration data and training vision-language-action models on custom datasets.",
             source="vendor_doc", ref=f"{README}:1-2"),
        Fact("The README tells the user to install the requirements with mujoco version 3.1.6.",
             source="vendor_doc", ref=f"{README}:22-26"),
        Fact("The README tells the user to unzip asset/objaverse/plate_11.zip before use.",
             source="vendor_doc", ref=f"{README}:28-32"),
        Fact("The served scene is the MJCF model 'open_manipulator_y scene' and it includes omy.xml.",
             source="upstream_code", ref=f"{SCENE}:1-2"),
        Fact("The robot model compiles angles in radians with autolimits enabled and sets the implicitfast "
             "integrator.", source="upstream_code", ref=f"{OMY}:2-4"),
        Fact("Default class Y declares joint range -6.28319 to 6.28319, armature 0.1 and damping 100.0.",
             source="upstream_code", ref=f"{OMY}:8-10"),
        Fact("Default class Y's position actuator has kp 5000, forcerange -2000 to 2000 and ctrlrange -6.28319 to "
             "6.28319.", source="upstream_code", ref=f"{OMY}:10"),
        Fact("The arm is a six-joint chain joint1 through joint6, all of default class Y.",
             source="upstream_code", ref=f"{OMY}:38-58"),
        Fact("The gripper has four joints: rh_r1 and rh_l1 have range 0 to 1.1 and rh_r2 and rh_l2 have range 0 to "
             "1, all of default class gripper.", source="upstream_code", ref=f"{OMY}:74-88"),
        Fact("Default class gripper's position actuator has kp 1000 and forcerange -100 to 100 but no ctrlrange.",
             source="upstream_code", ref=f"{OMY}:12-14"),
        Fact("The model has ten position actuators: six arm actuators of class Y (actuator_joint1 through "
             "actuator_joint6) and four gripper actuators that declare ctrlrange 0 to 1.1, 0 to 1, 0 to 1.1 and 0 "
             "to 1.", source="upstream_code", ref=f"{OMY}:106-117"),
        Fact("The robot model declares a camera named egocentric.",
             source="upstream_code", ref=f"{OMY}:67"),
        Fact("The served scene's worldbody contains a floor plane and a directional light.",
             source="upstream_code", ref=f"{SCENE}:19-21"),
        Fact("The card's entry symbol SimpleEnv is a concrete class in mujoco_env/y_env.py that constructs "
             "MuJoCoParserClass from the xml_path argument.", source="upstream_code", ref=f"{Y_ENV}:13-27"),
        Fact("SimpleEnv.step for joint_angle takes action[:-1] as the six joint targets, repeats action[-1] four "
             "times for the gripper command and scales elements 1 and 3 by 0.8.",
             source="upstream_code", ref=f"{Y_ENV}:98-137"),
        Fact("SimpleEnv.step stores self.q and returns the selected state; SimpleEnv.step_env separately calls "
             "self.env.step(self.q).", source="upstream_code", ref=f"{Y_ENV}:139-151"),
        Fact("SimpleEnv.get_joint_state returns the six joint angles plus a binary gripper state.",
             source="upstream_code", ref=f"{Y_ENV}:192-202"),
        Fact("SimpleEnv.grab_image reads the agentview, egocentric and sideview camera frames.",
             source="upstream_code", ref=f"{Y_ENV}:153-168"),
        Fact("The card's second entry symbol SimpleEnv2 is a concrete class in mujoco_env/y_env2.py.",
             source="upstream_code", ref=f"{Y_ENV2}:13"),
        Fact("SimpleEnv2.set_instruction chooses the red mug body_obj_mug_5 or the blue mug body_obj_mug_6 from the "
             "instruction.", source="upstream_code", ref=f"{Y_ENV2}:110-129"),
        Fact("The tutorial's example scene includes the tabletop, mug_5 and plate_11 object models in addition to "
             "the OMY robot model.", source="upstream_code", ref=f"{EXAMPLE_SCENE}:23-34"),
    ]
    safe_state = ("the bridge-owned simulation stops advancing: no step or world reset is accepted after an "
                  "e-stop until mhs.safety.reset clears the latch, while the integration state and stored ctrl "
                  "stay readable; releasing the latch does not integrate or clear ctrl, and a new explicit "
                  "step without an action reuses the stored position targets")
    #: The fidelity contract of the real MuJoCo engine path, which was not run here.  The model states no <option
    #: timestep>, so the engine path would use MuJoCo's library default, which is outside the clone; the fake's F0
    #: contract says so and the F1 path is not claimed as validated.
    fidelity = {
        "engine": "mujoco:open_manipulator_y scene",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "none",
            "seed_control": "none",
            "notes": "The bridge reports determinism none: cap.world.reset.v1 restores the model defaults with "
                     "mj_resetData and takes no seed, and a native checkpoint does not establish hidden-state or "
                     "contact completeness.",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": True,
        "gaps": [
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine and the scene was never compiled",
            "the MJCF declares no <option timestep>, so the engine would run at MuJoCo's library default (0.002 s, "
            "outside the clone); 2.0 ms is not a line of the clone",
            "the bridge exposes qpos, qvel, ctrl and time, not the camera frames of SimpleEnv.grab_image; the "
            "served scene has only the egocentric camera, while agentview and sideview come from the tabletop "
            "object model that the example scene includes",
            "the package serves the card's models[0], asset/robotis_omy/scene.xml, only; the example scenes and the "
            "second language-conditioned model are not served",
            "SimpleEnv.step stages self.q and returns state, while step_env separately integrates "
            "(mujoco_env/y_env.py:139-151); the bridge instead writes ten controls and integrates in one call, "
            "and the served robot-and-floor scene has no tabletop task objects",
            "no physical OMY arm is modelled or driven; this simulated package has no hardware backend and nothing "
            "was validated against hardware",
            "the software e-stop pauses bridge stepping and retains data.ctrl; mhs.safety.reset only releases "
            "the latch, and an explicit step with no action integrates the stored position targets",
        ],
    }
    #: The fake backend is the package's stand-in mujoco module, not MuJoCo: F0, no physics.
    fidelity_by_backend = {
        "fake": {
            "engine": "analytic:stand-in mujoco module (no MuJoCo engine)",
            "fidelity_level": "F0",
            "determinism": {
                "kind": "none",
                "seed_control": "none",
                "notes": "The stand-in moves each position-actuated joint by a fixed placeholder fraction toward "
                         "its control value from the model-default reset state; it has no seed input and its "
                         "motion is not MuJoCo's physics.",
            },
            "gaps": [
                "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the pinned MJCF and "
                "its include for the ten hinge joints, the ten position actuators and their effective ctrlranges, "
                "but integrates a placeholder first-order motion of each actuated joint toward its control value; "
                "trajectories, contacts, actuator dynamics and the model's inertials are not MuJoCo's",
                "the model's ten <position> actuators are position servos with kp and forcerange; the fake's "
                "first-order step is not a position servo and ignores kp, forcerange, damping, inertia and the "
                "joint ranges",
                "the MJCF declares no <option timestep>, so the fake uses MuJoCo's library default 0.002 s as a "
                "placeholder; the reported 2.0 ms comes from the fake, not from a line of the clone",
                "the fake has no mj_getState/mj_setState/mj_stateSize, so the bridge uses its basic checkpoint "
                "profile: time, qpos, qvel and ctrl are restored, not MuJoCo's full integration state",
                "no mesh, texture, collision, contact or camera is loaded or resolved by the stand-in; the bridge "
                "exposes qpos, qvel, ctrl and time, not the SimpleEnv.grab_image frames",
                "MuJoCo itself was not importable where the gate ran, so the stand-in was not compared with the "
                "real engine, and the example scenes were not loaded",
                "the package serves the card's models[0], asset/robotis_omy/scene.xml, only, and no physical OMY "
                "arm is modelled or driven",
                "the robot-and-floor scene omits the tabletop task objects, and bridge stepping combines a "
                "ten-control write with integration; SimpleEnv.step only stages targets and step_env integrates "
                "separately (mujoco_env/y_env.py:139-151)",
                "the e-stop retains ctrl and the position targets; releasing the latch changes no integration "
                "state, and an explicit step with no action reuses the stored targets",
            ],
        },
    }
