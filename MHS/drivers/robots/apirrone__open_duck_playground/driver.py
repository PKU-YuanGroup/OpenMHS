"""OpenMHS driver for gh.apirrone/open_duck_playground: the Open Duck Mini V2 MuJoCo model.

A ``MujocoDriver`` is configuration only: ``model_path`` names an MJCF scene of the read-only clone and the
MuJoCo bridge derives the contract from the loaded model.  ``cap.world.step.v1`` takes ``{ticks, action}`` with
``action.ctrl`` bounded per actuator by the model's ``actuator_ctrlrange``; ``cap.world.reset.v1`` restores the
model defaults.  The device is simulated (R0): there is no hardware backend and no operator-required limit.

The card's first model is ``playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml``, a scene that
includes the backlash variant of the Open Duck Mini V2 robot (14 position actuators).  MuJoCo is not installed
where the acceptance gate runs and package code never imports the clone, so the ``fake`` backend is this package's
own stand-in ``mujoco`` module (fake.py).  It reads the model file for the joint and actuator layout and the
inherited control ranges, but its integration is a placeholder and not MuJoCo's physics; the fidelity ``gaps``
say so.  A backend name that ``backends`` does not name (``sim``) is served by the real ``mujoco`` module through
``MujocoDriver.open_native``; that path was not run here.

Every Fact cites a line of the clone at commit b9be205ac64488c23504ca42e5ec790337adeec3.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0], as the clone names it (the model path below is relative to this package directory).
MODEL = "playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml"
MODEL_PATH = "../../../../robots/apirrone/open_duck_playground/" + MODEL
SCENE = "playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml"
ROBOT = "playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml"
README = "README.md"
INFER = "playground/open_duck_mini_v2/mujoco_infer.py"


class OpenDuckMiniV2(MujocoDriver):
    device_id = "open-duck-mini-v2"
    model_path = MODEL_PATH
    backends = {"fake": FakeMujoco}
    display_name = "Open Duck Mini V2 (MuJoCo rough terrain, backlash)"
    vendor, model = "apirrone (Open Duck Playground)", "Open Duck Mini V2"
    tags = ["biped", "humanoid", "locomotion", "mujoco", "open-duck-mini", "robot", "simulation"]
    facts = [
        Fact("The package serves the card's first model, the MJCF scene "
             "playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml, whose root element is "
             "'<mujoco model=\"Open Duck Mini V2 rough terrain scene\">' and which includes "
             "open_duck_mini_v2_backlash.xml", source="upstream_code", ref=f"{SCENE}:1-3"),
        Fact("The rough scene's floor is a geom of type hfield that uses the hfield asset assets/hfield.png with "
             "size '10 10 .01 0.1', and the floor geom's friction is 1.0", source="upstream_code",
             ref=f"{SCENE}:22-28"),
        Fact("The robot model's root element is '<mujoco model=\"open_duck_mini_v2\">'", source="upstream_code",
             ref=f"{ROBOT}:4"),
        Fact("The robot's compiler element declares angle 'radian' and meshdir 'assets'", source="upstream_code",
             ref=f"{ROBOT}:9"),
        Fact("The robot option sets iterations 1, ls_iterations 5 and eulerdamp disable, and it sets no timestep",
             source="upstream_code", ref=f"{ROBOT}:6-8"),
        Fact("The sts3215 default class sets joint damping 0.56, frictionloss 0.068 and armature 0.027",
             source="upstream_code", ref=f"{ROBOT}:49"),
        Fact("The sts3215 default class sets the position actuator kp 17.11, kv 0.0 and forcerange -3.23 3.23",
             source="upstream_code", ref=f"{ROBOT}:50"),
        Fact("The backlash default class limits its hinge range to -0.008726646259971648 to "
             "0.008726646259971648 rad, commented as plus or minus 0.5 degrees", source="upstream_code",
             ref=f"{ROBOT}:52-55"),
        Fact("The robot base body has the free joint floating_base", source="upstream_code", ref=f"{ROBOT}:59-61"),
        Fact("The model has 14 position actuators, one for each actuated hinge joint, and every one sets "
             "inheritrange 1 and class sts3215", source="upstream_code", ref=f"{ROBOT}:497-512"),
        Fact("The left_hip_yaw hinge joint has range -0.5235987755982979 to 0.5235987755982997 rad",
             source="upstream_code", ref=f"{ROBOT}:118"),
        Fact("The left_hip_roll hinge joint has range -0.4363323129985815 to 0.43633231299858327 rad",
             source="upstream_code", ref=f"{ROBOT}:137"),
        Fact("The left_hip_pitch hinge joint has range -1.2217304763960306 to 0.5235987755982988 rad",
             source="upstream_code", ref=f"{ROBOT}:153"),
        Fact("The left_knee hinge joint has range -1.5707963267948966 to 1.5707963267948966 rad",
             source="upstream_code", ref=f"{ROBOT}:178"),
        Fact("The left_ankle hinge joint has range -1.5707963267948957 to 1.5707963267948974 rad",
             source="upstream_code", ref=f"{ROBOT}:199"),
        Fact("The neck_pitch hinge joint has range -0.3490658503988437 to 1.1344640137963364 rad",
             source="upstream_code", ref=f"{ROBOT}:229"),
        Fact("The head_pitch hinge joint has range -0.7853981633974483 to 0.7853981633974483 rad",
             source="upstream_code", ref=f"{ROBOT}:246"),
        Fact("The head_yaw hinge joint has range -2.792526803190927 to 2.792526803190927 rad",
             source="upstream_code", ref=f"{ROBOT}:256"),
        Fact("The head_roll hinge joint has range -0.523598775598218 to 0.5235987755983796 rad",
             source="upstream_code", ref=f"{ROBOT}:272"),
        Fact("The right_hip_yaw hinge joint has range -0.523598775598297 to 0.5235987755983006 rad",
             source="upstream_code", ref=f"{ROBOT}:328"),
        Fact("The right_hip_roll hinge joint has range -0.4363323129985797 to 0.43633231299858505 rad",
             source="upstream_code", ref=f"{ROBOT}:346"),
        Fact("The right_hip_pitch hinge joint has range -0.5235987755982988 to 1.2217304763960306 rad",
             source="upstream_code", ref=f"{ROBOT}:362"),
        Fact("The right_knee hinge joint has range -1.5707963267948966 to 1.5707963267948966 rad",
             source="upstream_code", ref=f"{ROBOT}:387"),
        Fact("The right_ankle hinge joint has range -1.5707963267948957 to 1.5707963267948974 rad",
             source="upstream_code", ref=f"{ROBOT}:409"),
        Fact("The sensor block names gyro, local_linvel, accelerometer, upvector, forwardvector, global_linvel, "
             "global_angvel, position, orientation, the left and right foot velocities and positions, and the "
             "left and right foot upvectors", source="upstream_code", ref=f"{ROBOT}:26-42"),
        Fact("The rough scene defines a home keyframe with a qpos list and a ctrl list; the ctrl list has the 14 "
             "actuator targets", source="upstream_code", ref=f"{SCENE}:32-74"),
        Fact("The README documents MuJoCo inference for open_duck_mini_v2 with mujoco_infer.py", source="vendor_doc",
             ref=f"{README}:31-38"),
        Fact("The inference script's default model path is playground/open_duck_mini_v2/xmls/scene_flat_terrain.xml",
             source="upstream_code", ref=f"{INFER}:254-257"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the integration state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, the determinism kind and
    #: the lockstep clock; the members below override them and state what the stand-in does not model.
    fidelity = {
        "engine": "mujoco:open_duck_mini_v2_rough_terrain_backlash",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge exposes no "
                     "seed input and cap.world.reset.v1 restores the model defaults, so the same engine and the "
                     "same control sequence repeat a trajectory, but no seed selects a different state",
        },
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it parses the MJCF for the joint "
            "and actuator layout and the inherited control ranges, but integrates a placeholder first-order motion "
            "of each actuated joint toward its control target, so trajectories, contacts, friction, actuator "
            "dynamics and sensors are not MuJoCo's",
            "the stand-in loads no mesh, texture or hfield asset, so the rough terrain height field and all "
            "collision geometry are absent and no contact is resolved",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "no rendering is offered and no physical Open Duck Mini V2 robot is modelled; nothing was validated "
            "against hardware",
            "the stand-in uses MuJoCo's library default time step because the model's option element sets no "
            "timestep; the real engine uses the same default, but the value is not stated by the model text",
        ],
    }
