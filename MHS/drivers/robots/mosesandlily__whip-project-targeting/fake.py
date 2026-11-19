"""Fake ``mujoco`` module for gh.mosesandlily/whip-project-targeting: a pure Python stand-in for MuJoCo.

Why a stand-in: the driver is a configuration-only ``MujocoDriver``, the bridge imports ``mujoco`` lazily, and
MuJoCo and mujoco-py are neither installed nor installable where the acceptance gate runs.  Package code never
imports the clone.  ``backends["fake"]`` therefore names this module object.  The bridge calls
``MjModel.from_xml_path`` on the card's model (``models/3D_model_w_whip_T1.xml``), then ``mj_resetData``,
``mj_forward`` and ``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time`` / ``data.qpos`` / ``data.qvel`` /
``data.ctrl`` arrays.

The shape comes from the MJCF text of the clone: the joint tree below ``<worldbody>`` gives the qpos and qvel
dimensions and each joint's address, and the active ``<actuator>`` elements give the control count and each
actuator's joint target.  The model's four motors declare no ``ctrlrange`` (``models/3D_model_w_whip_T1.xml:220-225``),
so the stand-in reports the library default ``[0, 0]`` with ``ctrllimited`` false for each of them, which the bridge
reads as "no bound" (a placeholder, not a device limit).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor constraint,
and its integration is a placeholder motion, not the engine's physics.  These differences are listed in the fidelity
``gaps`` of driver.py.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: MuJoCo's library default when a model sets no ``<option timestep>``; this model states 0.0001 s
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: a torque control moves an actuated joint at this rate; the stand-in has no inertia, gear or actuator
#: model, so this is test data, not a value of the model
_TORQUE_GAIN = 100.0
#: qpos and qvel widths per joint type: MuJoCo's structural contract, not a number of this device
_QPOS_WIDTH = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_WIDTH = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


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


class _Joint:
    """One joint of the model: its name, type and position in the qpos and qvel arrays."""

    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.qpos_adr = 0
        self.qvel_adr = 0


def _walk_bodies(body, joints):
    """Append every joint below ``body`` in the order MuJoCo lays qpos and qvel out."""
    for child in body:
        if child.tag == "freejoint":
            joints.append(_Joint(child.get("name"), "free"))
        elif child.tag == "joint":
            kind = child.get("type", "hinge")
            if kind not in _QPOS_WIDTH:
                raise ValueError(f"the fake cannot model joint {child.get('name')!r} of type {kind!r}")
            joints.append(_Joint(child.get("name"), kind))
        elif child.tag == "body":
            _walk_bodies(child, joints)


def _collect_joints(root):
    """The joints of the model, their qpos/qvel addresses and the model's default qpos."""
    joints = []
    for body in root.findall("worldbody"):
        _walk_bodies(body, joints)
    nq = nv = 0
    for joint in joints:
        joint.qpos_adr = nq
        joint.qvel_adr = nv
        nq += _QPOS_WIDTH[joint.kind]
        nv += _QVEL_WIDTH[joint.kind]
    # placeholder: this model has no free joint or nonzero qpos0, so its defaults are all zeros
    return joints, nq, nv, [0.0] * nq


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _collect_actuators(root, joints):
    """The active actuator elements: their joint target, ctrlrange and ctrllimited flag."""
    by_name = {joint.name: joint for joint in joints if joint.name}
    actuators = []
    for section in root.findall("actuator"):
        for element in section:
            if element.tag == "default":
                continue
            joint = by_name.get(element.get("joint"))
            raw = element.get("ctrlrange")
            if raw is None:
                # placeholder: MuJoCo's default ctrlrange [0, 0] when an element states none; ctrllimited stays false
                low, high, limited = 0.0, 0.0, False
            else:
                low, high = _two_floats(raw)
                # MuJoCo's autolimits makes a stated ctrlrange limited unless the element opts out.
                limited = str(element.get("ctrllimited", "true")).lower() in ("true", "1")
            actuators.append((joint, low, high, limited))
    return actuators


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        if root.tag != "mujoco":
            raise ValueError(f"the model root is <{root.tag}>, not <mujoco>")
        joints, nq, nv, qpos0 = _collect_joints(root)
        actuators = _collect_actuators(root, joints)
        timestep = _DEFAULT_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(actuators)
        self.qpos0 = qpos0
        self.actuator_ctrlrange = [[low, high] for _joint, low, high, _limited in actuators]
        self.actuator_ctrllimited = [limited for _joint, _low, _high, limited in actuators]
        self._qpos_targets = [None if joint is None else joint.qpos_adr
                              for joint, _low, _high, _limited in actuators]
        self._qvel_targets = [None if joint is None else joint.qvel_adr
                              for joint, _low, _high, _limited in actuators]
        self._joints = joints

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
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
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint takes a placeholder velocity from its control."""
    dt = float(model.opt.timestep)
    for index, qpos_adr in enumerate(model._qpos_targets):
        qvel_adr = model._qvel_targets[index]
        if qpos_adr is None or qvel_adr is None or index >= len(data.ctrl):
            continue
        velocity = float(data.ctrl[index]) * _TORQUE_GAIN
        data.qvel[qvel_adr] = velocity
        data.qpos[qpos_adr] = float(data.qpos[qpos_adr]) + velocity * dt
    data.time = float(data.time) + dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
