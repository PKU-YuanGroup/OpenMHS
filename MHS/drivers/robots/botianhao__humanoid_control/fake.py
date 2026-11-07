"""Fake ``mujoco`` module of the botianhao humanoid driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore the module object this file provides: the bridge calls ``MjModel.from_xml_path`` on the card's model
(``humanoid_legged_description/mjcf/humanoid_legged_control_.xml``), then ``mj_resetData``/``mj_forward``/``mj_step``
on it, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The shape (joint types, joint order, twelve motor actuators, their explicit control ranges, the free base pose and the
1 ms option step) is parsed from the MJCF file itself, so the derived contract comes from the card's model, not from
constants of this file.  The integration is a placeholder: each actuated hinge takes a velocity from a fixed gain
times the control value, and the free base is held where the model puts it.  That is not MuJoCo's physics; the
driver's fidelity ``gaps`` say so.  Nothing here talks to a physical robot.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: velocity per unit of control for one fake step (the model's motors take a torque, not a velocity)
_CONTROL_GAIN = 1e-4
#: qpos and qvel dimensions by MJCF joint type; a missing type means "hinge".
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _load(path):
    return ET.parse(str(path)).getroot()


def _floats(raw, default):
    return [float(value) for value in (raw if raw is not None else default).split()]


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        self.qpos0 = []
        self.nv = 0
        joints = {}
        for body in root.iter("body"):
            for child in body:
                if child.tag == "freejoint":
                    offset = len(self.qpos0)
                    position = _floats(body.get("pos"), "0 0 0")[:3]
                    quaternion = _floats(body.get("quat"), "1 0 0 0")[:4]
                    self.qpos0.extend(position + quaternion)
                    self.nv += _QVEL_DIM["free"]
                    joints[None] = ("free", offset, self.nv - _QVEL_DIM["free"])
                elif child.tag == "joint":
                    kind = child.get("type", "hinge")
                    if kind not in _QPOS_DIM:
                        raise ValueError(f"unsupported MJCF joint type {kind!r}")
                    name = child.get("name") or f"joint_{len(joints)}"
                    offset = len(self.qpos0)
                    if kind == "free":
                        position = _floats(child.get("pos"), "0 0 0")[:3]
                        quaternion = _floats(child.get("quat"), "1 0 0 0")[:4]
                        self.qpos0.extend(position + quaternion)
                    elif kind == "ball":
                        self.qpos0.extend(_floats(child.get("ref"), "1 0 0 0")[:4])
                    else:
                        self.qpos0.extend(_floats(child.get("ref"), "0")[:1])
                    self.nv += _QVEL_DIM[kind]
                    joints[name] = (kind, offset, self.nv - _QVEL_DIM[kind])
        self.nq = len(self.qpos0)

        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        for section in root.findall("actuator"):
            for element in section:
                if element.get("joint") is None:
                    continue
                self.actuator_joints.append(joints.get(element.get("joint")))
                raw = element.get("ctrlrange")
                limited = element.get("ctrllimited", "false").lower() in ("true", "1")
                if raw is not None:
                    low, high = (float(value) for value in raw.split()[:2])
                    self.actuator_ctrlrange.append([low, high])
                    self.actuator_ctrllimited.append(limited)
                else:
                    self.actuator_ctrlrange.append([-_FLOAT_MAX, _FLOAT_MAX])
                    self.actuator_ctrllimited.append(False)
        self.nu = len(self.actuator_ctrlrange)

        timestep = 0.002  # placeholder: MuJoCo's library default when the model states none
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(Path(path)))

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
    data.qvel[:] = [0.0] * len(data.qvel)
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

    #: placeholder: identifies the stand-in, not a MuJoCo release
    __version__ = "stand-in"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
