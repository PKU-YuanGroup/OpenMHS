"""Stand-in ``mujoco`` module for the fake backend of the humanoid model driver.

The package is a ``MujocoDriver`` and configuration only.  ``MujocoDriver``
builds an ``mhs.bridge.mujoco.MujocoBridge`` with ``mujoco=native``; the bridge
calls ``MjModel.from_xml_path`` on the card's MJCF, then
``mj_resetData``/``mj_forward``/``mj_step`` and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and
the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

MuJoCo is not installed where this repository's gate runs and cannot be
installed (no network, no pip), so this module supplies exactly those members.
The model shape is read from the MJCF file itself: the actuator control ranges,
the joint dimensions and the option timestep are the model's values, not
constants of this file.  What this is not: MuJoCo.  It loads no mesh or
texture, resolves no contact, friction, inertia, tendon, equality or actuator
constraint, and its step is a placeholder first-order motion of each actuated
joint, not the model's torque dynamics.  Those differences are listed in the
driver's fidelity ``gaps``.  Every numeric constant below is placeholder test
data, not a Fact, Limit or device bound.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's qpos qvel layout contribution per joint type
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: placeholder: fraction of the control value added to the joint velocity per second
_TORQUE_GAIN = 0.001
#: placeholder: velocity damping per simulated second in the stand-in integration
_DAMPING = 1.0


def _load(path):
    """The MJCF tree of ``path``; the pinned model has no ``<include>`` elements."""
    model = Path(path).resolve()
    tree = ET.parse(str(model)).getroot()
    if tree.find(".//include") is not None:
        raise ValueError("the stand-in does not expand MJCF <include> files")
    return tree


def _joint_kind(element, root):
    """The effective joint type, taking a simple same-tag default class into account."""
    kind = element.get("type")
    if kind is not None:
        return kind
    class_name = element.get("class")
    if class_name:
        for default in root.findall("default"):
            for child in default.iter("default"):
                if child.get("class") == class_name:
                    joint = child.find("joint")
                    if joint is not None and joint.get("type") is not None:
                        return joint.get("type")
            joint = default.find("joint")
            if joint is not None and joint.get("type") is not None:
                return joint.get("type")
    return "hinge"


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree."""

    def __init__(self, root):
        ranges, limited = [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                if "ctrlrange" in element.attrib:
                    low, high = (float(value) for value in element.get("ctrlrange").split()[:2])
                    ranges.append([low, high])
                    limited.append(str(element.get("ctrllimited", "true")).lower() == "true")
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)

        qpos = qvel = 0
        names = {}
        for body in root.findall("worldbody"):
            for free in body.iter("freejoint"):
                qpos += _QPOS["free"]
                qvel += _QVEL["free"]
            for joint in body.iter("joint"):
                kind = _joint_kind(joint, root)
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r} in the stand-in")
                name = joint.get("name")
                if name is not None:
                    names[name] = (qpos, qvel)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]

        timestep = 0.001  # placeholder: MuJoCo's library default when a model sets none
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: actuator index -> (qpos offset, qvel offset) for a joint actuator
        self.actuator_joint = {}
        index = 0
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                joint = element.get("joint")
                if joint in names:
                    self.actuator_joint[index] = names[joint]
                index += 1

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0
        if model.nq >= 7:
            self.qpos[3] = 1.0  # placeholder: free-joint quaternion w=1, MuJoCo's qpos0 convention


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0
    if model.nq >= 7:
        data.qpos[3] = 1.0  # placeholder: free-joint quaternion w=1


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward quantities."""


def mj_step(model, data):
    """Advance the stand-in one time step with a placeholder first-order motion."""
    dt = float(model.opt.timestep)
    for index, (qpos_offset, qvel_offset) in model.actuator_joint.items():
        if index >= len(data.ctrl):
            continue
        qpos_index = qpos_offset
        qvel_index = qvel_offset
        if not 0 <= qpos_index < len(data.qpos) or not 0 <= qvel_index < len(data.qvel):
            continue
        data.qvel[qvel_index] += (data.ctrl[index] * _TORQUE_GAIN - data.qvel[qvel_index] * _DAMPING) * dt
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
