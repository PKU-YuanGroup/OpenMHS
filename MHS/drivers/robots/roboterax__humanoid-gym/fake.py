"""Fake ``mujoco`` module of the humanoid-gym driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
the package must also be checkable where MuJoCo is not installed.  ``backends["fake"]`` is therefore the module object
this file provides: the bridge calls ``MjModel.from_xml_path`` on the card's model
(``resources/robots/XBot/mjcf/XBot-L.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.  The shape (joint types,
joint order, twelve motor actuators, their explicit control ranges and the 0.001 s option step) is parsed from the
MJCF itself, so the derived contract comes from the card's model, not from constants of this file.

The integration is a placeholder: each actuated hinge takes a velocity from a fixed gain times its control value,
and the free base is held where the model puts it.  That is not MuJoCo's physics; the driver's fidelity ``gaps`` say
so.  Nothing here talks to a physical robot.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: velocity per unit of control for one stand-in step (the model's motors apply a torque, not a velocity)
_CONTROL_GAIN = 1e-4
#: qpos and qvel dimensions by MJCF joint type; a missing type means "hinge".
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand_includes(node, base, depth=0):
    """Replace the ``<include file=...>`` children of ``node`` with the included file's children."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 levels deep")
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand_includes(included, target.resolve().parent, depth + 1)
            index = list(node).index(child)
            node.remove(child)
            for offset, item in enumerate(list(included)):
                node.insert(index + offset, item)
        else:
            _expand_includes(child, base, depth)


def _load(path):
    root = ET.parse(str(path)).getroot()
    _expand_includes(root, Path(path).resolve().parent)
    return root


def _numbers(text, count):
    return [float(value) for value in (text or "").split()[:count]]


def _default_motor(root):
    """The direct ``<default><motor>`` attributes this MJCF uses for its actuators (no class hierarchy)."""
    for section in root.findall("default"):
        for motor in section.findall("motor"):
            return motor.attrib
    return {}


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        self.nq, self.nv = 0, 0
        joints = {}
        for body in root.iter("body"):
            for joint in body:
                if joint.tag == "freejoint":
                    kind, name = "free", joint.get("name")
                elif joint.tag == "joint":
                    kind = joint.get("type", "hinge")
                    name = joint.get("name")
                else:
                    continue
                if kind not in _QPOS_DIM:
                    raise ValueError(f"unsupported joint type {kind!r} in the MJCF")
                entry = (kind, self.nq, self.nv, body)
                if name:
                    joints[name] = entry
                else:
                    joints[f"joint_{len(joints)}"] = entry
                self.nq += _QPOS_DIM[kind]
                self.nv += _QVEL_DIM[kind]

        default = _default_motor(root)
        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                raw = element.get("ctrlrange") or default.get("ctrlrange")
                limited = element.get("ctrllimited", default.get("ctrllimited", "false")).lower() in ("true", "1")
                if raw is not None:
                    low, high = _numbers(raw, 2)
                    self.actuator_ctrlrange.append([low, high])
                    self.actuator_ctrllimited.append(limited)
                else:
                    self.actuator_ctrlrange.append([-_FLOAT_MAX, _FLOAT_MAX])
                    self.actuator_ctrllimited.append(False)
                self.actuator_joints.append(joints.get(element.get("joint")))
        self.nu = len(self.actuator_ctrlrange)

        self.qpos0 = [0.0] * self.nq
        for entry in joints.values():
            kind, qpos_offset, _qvel_offset, body = entry
            if kind == "ball":
                self.qpos0[qpos_offset:qpos_offset + 4] = [1.0, 0.0, 0.0, 0.0]
            elif kind == "free":
                position = _numbers(body.get("pos"), 3)
                quaternion = _numbers(body.get("quat"), 4)
                self.qpos0[qpos_offset:qpos_offset + 7] = (position or [0.0, 0.0, 0.0]) + (
                    quaternion or [1.0, 0.0, 0.0, 0.0])

        timestep = 0.002  # placeholder: MuJoCo's default when the MJCF states no option timestep
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand_includes(root, Path.cwd())
        return cls(root)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Restore the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model, data):
    """Advance the stand-in one step: each actuated hinge takes a placeholder velocity from its control value."""
    dt = float(model.opt.timestep)
    for index, entry in enumerate(model.actuator_joints):
        if entry is None:
            continue
        kind, qpos_offset, qvel_offset, _body = entry
        if kind not in ("hinge", "slide"):
            continue
        data.qvel[qvel_offset] = float(data.ctrl[index]) * _CONTROL_GAIN
        data.qpos[qpos_offset] += data.qvel[qvel_offset] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
