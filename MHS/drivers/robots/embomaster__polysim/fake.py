"""Fake ``mujoco`` module of the polysim driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's model
(``humanoidverse/data/robots/g1/scene_29dof.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The shape (joint types, joint order, 29 motor actuators, their control ranges, the free base pose and the option step)
is parsed from the MJCF itself, so the derived contract comes from the card's model, not from constants of this file.
The scene includes ``g1_29dof_old.xml``; the include is expanded in memory and the clone is never written.  The
integration is a placeholder: each actuated hinge takes a velocity from a fixed gain times the control value, and the
free base is held where the model puts it.  That is not MuJoCo's physics; the driver's fidelity ``gaps`` say so.
Nothing here talks to a physical robot.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: velocity per unit of control for one fake step (the model's motors take a torque, not a velocity)
_CONTROL_GAIN = 1e-4
#: placeholder: MuJoCo's built-in default when the MJCF has no <option timestep=...>; the served scene states none
_DEFAULT_TIMESTEP = 0.002
#: qpos and qvel dimensions by MJCF joint type; a missing type means "hinge".
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: Actuator elements that drive a joint through ``data.ctrl``.
_JOINT_ACTUATORS = ("motor", "general", "position", "velocity", "intvelocity", "damper", "cylinder", "muscle")


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


def _as_bool(raw):
    """MJCF boolean: ``true``/``false``, or ``auto`` when the value depends on a companion attribute."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in ("true", "1"):
        return True
    if text in ("false", "0"):
        return False
    if text == "auto":
        return None
    raise ValueError(f"the MJCF boolean {raw!r} is not true, false or auto")


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
                if joint.tag not in ("joint", "freejoint"):
                    continue
                kind = "free" if joint.tag == "freejoint" else joint.get("type", "hinge")
                if kind not in _QPOS_DIM:
                    raise ValueError(f"this stand-in does not know the MJCF joint type {kind!r}")
                name = joint.get("name") or f"joint_{len(joints)}"
                joints[name] = (kind, self.nq, self.nv)
                self.nq += _QPOS_DIM[kind]
                self.nv += _QVEL_DIM[kind]

        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag not in _JOINT_ACTUATORS:
                    continue
                joint_name = element.get("joint")
                if joint_name not in joints:
                    raise ValueError(f"actuator {element.get('name')!r} drives unknown joint {joint_name!r}")
                self.actuator_joints.append(joints[joint_name])
                raw = element.get("ctrlrange")
                limited = _as_bool(element.get("ctrllimited"))
                if raw is not None:
                    low, high = (float(value) for value in raw.split()[:2])
                    # MJCF "auto" (the default): a declared ctrlrange is enforced unless stated otherwise.
                    self.actuator_ctrlrange.append([low, high])
                    self.actuator_ctrllimited.append(True if limited is None else limited)
                else:
                    self.actuator_ctrlrange.append([-_FLOAT_MAX, _FLOAT_MAX])
                    self.actuator_ctrllimited.append(False if limited is None else limited)
        self.nu = len(self.actuator_ctrlrange)

        self.qpos0 = [0.0] * self.nq
        for body in root.iter("body"):
            for joint in body:
                if joint.tag != "joint" and joint.tag != "freejoint":
                    continue
                entry = joints.get(joint.get("name") or "")
                if entry is None:
                    continue
                kind, offset, _qvel_offset = entry
                if kind == "free":
                    position = [float(value) for value in (body.get("pos") or "0 0 0").split()[:3]]
                    quaternion = [float(value) for value in (body.get("quat") or "1 0 0 0").split()[:4]]
                    self.qpos0[offset:offset + 7] = position + quaternion
                elif kind in ("hinge", "slide"):
                    self.qpos0[offset] = float(joint.get("ref") or 0.0)

        timestep = _DEFAULT_TIMESTEP
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


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
        kind, qpos_offset, qvel_offset = entry
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
