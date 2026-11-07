"""Fake ``mujoco`` module of the robot-unitree-g1 driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore the module object this file provides: the bridge calls ``MjModel.from_xml_path`` on the card's scene
(``resources/g1/scene53.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The shape (joint types and order, the free base, the scene's free bodies and drawer slides, the 53 motor actuators and
the option step) is parsed from the MJCF file itself, so the derived contract comes from the card's models rather than
from constants of this file.  The integration is a placeholder: each actuated hinge or slide takes a velocity from a
fixed gain times its control value, and every other joint is held where the model puts it.  That is not MuJoCo's
physics; the driver's fidelity ``gaps`` say so.  Nothing here talks to a physical robot.

The scene declares no ``ctrlrange`` on any motor, so the bridge derives no per-actuator control bound from this model.
The placeholder default step is 0.002 s because the deployment configuration sets ``simulation_dt: 0.002``
(``deploy/config/g1_53.yaml:8``) and the deployment script assigns it to ``model.opt.timestep``
(``deploy/deploy_mujoco53.py:1939``); the MJCF itself has no ``<option>`` element, so this number is test data of the
stand-in, not a fact about the engine.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: velocity per unit of control for one fake step (the G1 motors take a torque, not a velocity)
_CONTROL_GAIN = 1e-4
#: placeholder: step of the stand-in when the MJCF has no <option timestep>; the deployment config uses 0.002 s
_DEFAULT_TIMESTEP = 0.002
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


def _joint_entry(body, child):
    """The ``(kind, name, qpos offset, qvel offset, range)`` of a joint element, or ``None`` for another tag."""
    if child.tag == "freejoint":
        return "free", f"freejoint@{body.get('name')}", child.get("range")
    if child.tag != "joint":
        return None
    kind = child.get("type", "hinge")
    return kind, child.get("name") or f"joint_{body.get('name')}", child.get("range")


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        self.nq, self.nv = 0, 0
        joints = {}
        self.qpos0 = []
        for body in root.iter("body"):
            for child in body:
                entry = _joint_entry(body, child)
                if entry is None:
                    continue
                kind, name, _range = entry
                joints[name] = (kind, self.nq, self.nv)
                self.nq += _QPOS_DIM[kind]
                self.nv += _QVEL_DIM[kind]

        self.qpos0 = [0.0] * self.nq
        for body in root.iter("body"):
            for child in body:
                entry = _joint_entry(body, child)
                if entry is None or entry[0] != "free":
                    continue
                kind, name, _range = entry
                offset = joints[name][1]
                position = [float(value) for value in (body.get("pos") or "0 0 0").split()[:3]]
                quaternion = [float(value) for value in (body.get("quat") or "1 0 0 0").split()[:4]]
                self.qpos0[offset:offset + 7] = position + quaternion

        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
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
    """Advance the stand-in one step: each actuated hinge or slide takes a placeholder velocity from its control."""
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
