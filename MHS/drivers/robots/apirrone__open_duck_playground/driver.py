"""OpenMHS driver for gh.apirrone/open_duck_playground: the Open Duck Mini V2 MuJoCo model.

A ``MujocoDriver`` is configuration only: ``model_path`` or ``model_xml`` names an MJCF scene of the read-only
clone and the MuJoCo bridge derives the contract from the loaded model.  ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action.ctrl`` bounded per actuator by the model's ``actuator_ctrlrange``;
``cap.world.reset.v1`` restores the model defaults.  The device is simulated (R0): there is no hardware backend and no operator-required limit.

The card's first model is ``playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml``, a scene that
includes the backlash variant of the Open Duck Mini V2 robot (14 position actuators).  MuJoCo is not installed
where the fake acceptance gate runs and package code never imports the clone, so the ``fake`` backend is this
package's own stand-in ``mujoco`` module (fake.py).  It reads the model file for the joint and actuator layout and
the inherited control ranges, but its integration is a placeholder and not MuJoCo's physics; the fidelity ``gaps``
say so.  A backend name that ``backends`` does not name (``sim``) is served by the real ``mujoco`` module through
``MujocoDriver.open_native``.

The upstream never loads this scene by path: it passes the scene text to ``MjModel.from_xml_string`` with an asset
map (``mujoco_infer_base.py:10-11``, ``base.py:31-38``).  A path load prefixes the included robot's
``meshdir="assets"`` to the scene's ``assets/hfield.png`` and looks for ``assets/assets/hfield.png``.  The sim path
therefore hands the same scene to the bridge as ``model_xml``, with the include, mesh directory and height field
made absolute; the physics, observations and rewards are the upstream scene's, only the file lookups differ.

Every Fact cites a line of the clone at commit b9be205ac64488c23504ca42e5ec790337adeec3.  This package is
model-authored and unreviewed.
"""

from pathlib import Path

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[0] and its included robot, as the clone names them.
MODEL = "playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml"
SCENE = "playground/open_duck_mini_v2/xmls/scene_rough_terrain_backlash.xml"
ROBOT = "playground/open_duck_mini_v2/xmls/open_duck_mini_v2_backlash.xml"
README = "README.md"
INFER = "playground/open_duck_mini_v2/mujoco_infer.py"

#: The read-only clone's scene, robot and asset directory, resolved as the other MuJoCo drivers resolve their models.
CLONE = (Path(__file__).resolve().parent / "../../../../robots/apirrone/open_duck_playground").resolve()
SCENE_PATH = CLONE / MODEL
ROBOT_PATH = CLONE / ROBOT
ASSET_DIR = SCENE_PATH.parent / "assets"
HFIELD_PATH = ASSET_DIR / "hfield.png"


def _model_xml() -> str:
    """The upstream scene with its include, mesh directory and height field made absolute.

    MuJoCo applies the included robot's ``meshdir="assets"`` to the scene's ``assets/hfield.png`` when the scene is
    loaded by path, so it looks for ``assets/assets/hfield.png``.  The upstream loads the scene text with an asset
    map instead (``mujoco_infer_base.py:10-11``); the bridge's ``from_xml_string`` has no asset map, so this keeps
    the same scene text and only makes the files it names absolute.  The physics and all values are unchanged.
    """

    text = SCENE_PATH.read_text()
    include = f'<include file="{Path(ROBOT).name}"/>'
    if include not in text:
        raise ValueError(f"{MODEL} no longer includes {Path(ROBOT).name}")
    text = text.replace(include, f'<include file="{ROBOT_PATH}"/>\n'
                                 f'  <compiler angle="radian" meshdir="{ASSET_DIR}"/>')
    hfield = 'file="assets/hfield.png"'
    if hfield not in text:
        raise ValueError(f"{MODEL} no longer names assets/hfield.png")
    return text.replace(hfield, f'file="{HFIELD_PATH}"')


MODEL_XML = _model_xml()


class OpenDuckMiniV2(MujocoDriver):
    device_id = "open-duck-mini-v2"
    #: The upstream scene text with absolute asset paths; the included ``meshdir="assets"`` is why the sim path does
    #: not use ``model_path`` (a path load would look for ``assets/assets/hfield.png``).
    model_xml = MODEL_XML
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
        Fact("The upstream loads the scene from its text with mujoco.MjModel.from_xml_string and an asset map, not "
             "from a filesystem path", source="upstream_code",
             ref="playground/open_duck_mini_v2/mujoco_infer_base.py:10-11"),
        Fact("base.get_assets collects the xmls directory and its assets subdirectory into that asset map",
             source="upstream_code", ref="playground/open_duck_mini_v2/base.py:31-38"),
    ]

    def _model_name(self) -> str | None:
        """The served scene as the clone names it, for the derived actuator_ctrlrange citation."""
        return MODEL

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
