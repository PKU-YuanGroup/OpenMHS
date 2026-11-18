"""OpenMHS driver for gh.sanan222/lecasa: the SO101 arm MJCF model (a MuJoCo family driver).

A MujocoDriver is configuration only: ``model_xml`` is the card's robot MJCF and the bridge derives the whole contract
from the model it loads.  ``cap.world.step.v1`` takes ``{ticks, action: {ctrl: [...]}}``; ``ctrl`` is bounded per
actuator by the model's ``actuator_ctrlrange`` (six position actuators), and the world state is the integration state
of the model (``time``, ``qpos``, ``qvel``, ``ctrl``) plus the tick count.  ``cap.world.reset.v1`` restores the model
defaults with ``mj_resetData``/``mj_forward``.  The device is simulated (R0): there is no hardware backend, no e-stop
path to a machine and no operator-required limit.

This package serves the card's robot model, ``src/robot/so101_simplified.xml`` (card ``models[1]``), the model that
``src/main.py`` passes to the task controller as ``robot_xml_path``.  The card's scene model
(``configs/kitchen_configs/kitchen_robot_scene.xml``, ``models[0]``) is a RoboCasa kitchen export whose mesh and
texture files are absolute Windows paths outside the clone, so it is not self-contained; the robot model is (its
meshes are under ``src/robot/assets``).

The compiler sets ``meshdir="assets"`` (``so101_simplified.xml:3``) and each mesh ``file`` is already
``assets/<name>.stl`` (``:127``), so a path load looks for ``assets/assets/<name>.stl``, which the clone does not have.
That is the ``ValueError`` the sim gate reported while loading this file.

The teleoperator does not load the file that way: it builds ``MujocoXML(robot_xml_path)``
(``teleoperator.py:111``), and that constructor's ``resolve_asset_dependency`` joins each relative mesh file with
the XML file's directory and stores the absolute path (``mujoco_xml.py:90``, ``:116-120``).  An absolute mesh file
is not prefixed by ``meshdir``.  ``model_xml`` is the clone file with that same join.  Joints, actuators and every
other attribute stay as the file writes them.  ``_model_name`` still returns ``src/robot/so101_simplified.xml``, so
the derived ctrl limit stays ``src/robot/so101_simplified.xml:actuator_ctrlrange``.

The gate cannot install MuJoCo where it runs, so the ``fake`` backend is this package's stand-in ``mujoco`` module
(fake.py).  It parses the same model text for the joint count, the actuator count and the per-actuator control ranges,
but its integration is a placeholder, not MuJoCo's physics; the fidelity ``gaps`` say so.  A backend name that
``backends`` does not list (``sim``) imports the real ``mujoco`` module and loads ``model_xml`` with
``MjModel.from_xml_string``.

The model file is read from the read-only upstream clone at the pinned commit (it is never copied into this package
and never imported).  Every Fact cites a line of the clone at commit 7dc0f63c0fc1519226262f0cc8cf48c6343043c0.  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

import os
import re
from pathlib import Path

from mhs.driver import Fact, MujocoDriver

from .fake import FakeMujoco

#: The card's models[1], relative to this package directory: the read-only clone under robots/ at the pinned commit.
MODEL = "src/robot/so101_simplified.xml"
_CLONE = Path(__file__).resolve().parent / "../../../../robots/sanan222/lecasa"
MODEL_FILE = (_CLONE / MODEL).resolve()
ROBOT_XML = MODEL
MAIN = "src/main.py"
README = "README.md"
XML_PY = "src/mujoco_utils/mujoco_xml.py"
TELEOP = "src/tasks/teleoperator.py"
#: so101_simplified.xml:127-139 names one STL per mesh element.
_MESH_COUNT = 13


def _model_xml() -> str:
    """The robot MJCF with mesh files absolute, the join ``resolve_asset_dependency`` writes.

    ``so101_simplified.xml:3`` sets ``meshdir="assets"`` and ``:127`` names each mesh ``assets/<name>.stl``.
    A path load prefixes ``meshdir`` and looks for ``assets/assets/<name>.stl``, which the clone does not have.
    ``MujocoXML.resolve_asset_dependency`` joins a relative mesh file with the XML file's directory
    (``mujoco_xml.py:116-120``) before the model is built.  That directory join is ``src/robot/<file>``, the STL
    under ``src/robot/assets``.  Only the ``file`` attribute of each ``<mesh>`` changes.
    """

    text = MODEL_FILE.read_text()
    folder = str(MODEL_FILE.parent)
    found = 0

    def absolute(match: re.Match) -> str:
        nonlocal found
        relative = match.group(1)
        if os.path.isabs(relative):
            raise ValueError(f"{MODEL} mesh file {relative} is already absolute")
        target = os.path.abspath(os.path.join(folder, relative))
        if not os.path.isfile(target):
            raise ValueError(f"{MODEL} mesh file {relative} is not a file under {folder}")
        found += 1
        return match.group(0).replace(f'file="{relative}"', f'file="{target}"', 1)

    rewritten = re.sub(r'<mesh\b[^>]*\bfile="([^"]+)"', absolute, text)
    if found != _MESH_COUNT:
        raise ValueError(f"{MODEL} should name {_MESH_COUNT} mesh files, found {found}")
    return rewritten


MODEL_XML = _model_xml()


class LecasaSo101(MujocoDriver):
    device_id = "lecasa-so101"
    #: from_xml_path prefixes meshdir="assets" onto file="assets/<name>.stl" (so101_simplified.xml:3 and :127).
    #: The bridge uses model_xml when model_path is unset.  The string is the clone file with those mesh paths
    #: made absolute, the join MujocoXML.resolve_asset_dependency does (mujoco_xml.py:116-120).
    model_xml = MODEL_XML
    backends = {"fake": FakeMujoco}
    display_name = "LeCasa SO101 arm (MuJoCo)"
    vendor, model = "sanan222 (LeCasa)", "SO101 simplified"
    tags = ["arm", "lecasa", "manipulator", "mujoco", "robot", "robocasa", "simulation", "so101"]
    facts = [
        Fact("The LeCasa README describes the project as a Real2Sim2Real platform for joint-level teleoperation, "
             "dataset collection, Vision-Language-Action policy training and evaluation in both simulation and real "
             "robots", source="vendor_doc", ref=f"{README}:3"),
        Fact("The README says the work focuses on single- and multi-stage tasks in RoboCasa kitchen environments "
             "using the SO101 arm, with policies trained through the LeRobot framework", source="vendor_doc",
             ref=f"{README}:4"),
        Fact("main.py resolves the robot model from src/robot/so101_simplified.xml and passes it to the task "
             "controller as robot_xml_path", source="upstream_code", ref=f"{MAIN}:231-247"),
        Fact("The model file declares '<mujoco model=\"so101_simplified\">'", source="upstream_code",
             ref=f"{ROBOT_XML}:2"),
        Fact("The model compiler declares angle='radian', meshdir='assets' and autolimits='true', so its joint "
             "ranges are radians and a range implies the limit", source="upstream_code", ref=f"{ROBOT_XML}:3"),
        Fact("Each mesh asset names its file as assets/<name>.stl, from assets/waveshare_mounting_plate_so101_v2.stl "
             "through assets/base_so101_v2.stl", source="upstream_code", ref=f"{ROBOT_XML}:127-139"),
        Fact("MujocoXML.__init__ calls resolve_asset_dependency after parsing the MJCF file",
             source="upstream_code", ref=f"{XML_PY}:90"),
        Fact("MujocoXML.resolve_asset_dependency joins a relative mesh file with the directory of the XML file and "
             "stores that absolute path", source="upstream_code", ref=f"{XML_PY}:116-120"),
        Fact("The teleoperator loads the robot MJCF with MujocoXML(self.robot_xml_path)",
             source="upstream_code", ref=f"{TELEOP}:111"),
        Fact("The default joint class sets damping 0.60, frictionloss 0.052 and armature 0.028",
             source="upstream_code", ref=f"{ROBOT_XML}:6"),
        Fact("The default geom class sets contype 0, conaffinity 0 and friction '2.0 0.8 0.3'",
             source="upstream_code", ref=f"{ROBOT_XML}:7"),
        Fact("The base body is at the origin with quat '1 0 0 0'", source="upstream_code", ref=f"{ROBOT_XML}:13"),
        Fact("shoulder_pan is a hinge joint with range -1.9198621771937616 to 1.9198621771937634 rad and damping "
             "0.60", source="upstream_code", ref=f"{ROBOT_XML}:29"),
        Fact("shoulder_lift is a hinge joint with range -1.7453292519943224 to 1.7453292519943366 rad and damping "
             "0.60", source="upstream_code", ref=f"{ROBOT_XML}:47"),
        Fact("elbow_flex is a hinge joint with range -1.69 to 1.69 rad and damping 0.60", source="upstream_code",
             ref=f"{ROBOT_XML}:59"),
        Fact("wrist_flex is a hinge joint with range -1.6580628494556928 to 1.6580627293335335 rad and damping "
             "0.60", source="upstream_code", ref=f"{ROBOT_XML}:77"),
        Fact("wrist_roll is a hinge joint with range -2.7438472969992493 to 2.841206309382605 rad and damping "
             "0.60", source="upstream_code", ref=f"{ROBOT_XML}:93"),
        Fact("gripper is a hinge joint with range -0.17453297762778586 to 1.7453291995659765 rad and damping 0.60",
             source="upstream_code", ref=f"{ROBOT_XML}:111"),
        Fact("The model has six position actuators named shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, "
             "wrist_roll and gripper; each sets kp 17.8, forcerange -3.35 to 3.35 and a ctrlrange that rounds its "
             "joint range to five decimals", source="upstream_code", ref=f"{ROBOT_XML}:157-162"),
        Fact("The model's equality section is empty", source="upstream_code", ref=f"{ROBOT_XML}:165"),
    ]
    def _model_name(self) -> str:
        """The clone names the model ``src/robot/so101_simplified.xml``.  The base reads ``model_path``, which is unset."""

        return MODEL

    safe_state = ("an e-stop latches the runtime and no further step or reset reaches the model until "
                  "mhs.safety.reset clears the latch; time, qpos, qvel and ctrl remain readable and unchanged")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the time step and the lockstep clock; the values below are this package's.
    fidelity = {
        "engine": "mujoco:so101_simplified",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "none",
            "notes": "MuJoCo integrates one model deterministically from one initial state; the bridge takes no "
                     "seed that selects a state (the reset input seed is accepted for the class contract, but the "
                     "reset restores the model defaults), so a run repeats on the same engine and no seed selects "
                     "a different state.  The fake stand-in is not MuJoCo and is not claimed to reproduce a MuJoCo "
                     "trajectory.",
        },
        "gaps": [
            "the fake backend is a stand-in for the mujoco library, not MuJoCo: it reads the model file for the "
            "joint count, the actuator count and the control ranges but integrates a placeholder first-order motion "
            "of each actuated joint toward its control target, so trajectories, contacts, actuator dynamics and "
            "the model's damping, frictionloss and armature are not MuJoCo's",
            "no mesh or texture of src/robot/assets is loaded and no contact, equality or tendon constraint is "
            "resolved by the stand-in; the model's equality section is empty, and the stand-in does not use the "
            "collision geoms (contype/conaffinity 1) either",
            "MuJoCo itself was not importable where the gate ran, so no trajectory of this package was compared "
            "with the real engine",
            "the card's scene model configs/kitchen_configs/kitchen_robot_scene.xml is not served: its mesh and "
            "texture files are absolute Windows paths outside the clone, so the self-contained robot model is "
            "served; the kitchen objects and fixtures of that scene are not modelled",
            "no rendering is offered and no physical SO101 robot is modelled; nothing was validated against the "
            "LeRobot or hardware stack",
        ],
    }
