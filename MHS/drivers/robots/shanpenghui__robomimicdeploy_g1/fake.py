"""Fake ``mujoco`` module for the G1 MuJoCo package: a pure Python stand-in for the library.

The package is a ``MujocoDriver`` and the driver's contract is derived from the model it loads, so the gate needs a
``mujoco`` module even though MuJoCo is neither installed nor installable where the gate runs.  ``backends["fake"]``
names this class; the bridge calls ``MjModel.from_xml_path`` on the card's scene, then
``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses ``g1_description/scene.xml`` and expands its
``<include>`` of ``g1_29dof_rev_1_0.xml``; ``MjModel`` takes the joint count, the floating-base start pose, the
actuator count and the 0.002 s timestep from that tree.  The G1 model states no ``ctrlrange`` on its motors, so this
stand-in reports every actuator as unlimited, as MuJoCo does (the driver's own step limits come from the upstream
``tau_limit`` configuration, not from this file).

What this is not: MuJoCo.  It resolves no mesh, texture, sensor, contact, constraint or inertia, and its integration is
a placeholder torque response (``_TORQUE_GAIN``), not MuJoCo's physics.  The driver's fidelity ``gaps`` list all of
that.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; the G1 model sets 0.002 s
_LIBRARY_TIMESTEP_S = 0.002
#: placeholder: arbitrary torque-to-velocity scale of the stand-in, not a physical parameter
_TORQUE_GAIN = 0.05
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included ``<mujoco>`` root."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded, each path relative to the file that names it."""
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


def _floats(text, count):
    values = [float(item) for item in str(text).split()]
    if len(values) < count:
        raise ValueError(f"expected at least {count} numbers, got {text!r}")
    return values[:count]


def _body_pose(body):
    """The initial position and quaternion of a body (MuJoCo's default is the body ``pos``/``quat``)."""
    return _floats(body.get("pos", "0 0 0"), 3) + _floats(body.get("quat", "1 0 0 0"), 4)


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its name, type and qpos/qvel positions in the data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, qpos0):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.qpos0 = qpos0


def _walk_joints(body):
    """Yield ``(joint element, parent body)`` for every joint below ``body`` in document order."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, body
        elif child.tag == "body":
            yield from _walk_joints(child)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the model."""

    def __init__(self, root):
        joints = []
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for joint, parent in _walk_joints(worldbody):
                kind = "free" if joint.tag == "freejoint" else joint.get("type", "hinge")
                qpos0 = _body_pose(parent) if kind == "free" else None
                entry = _Joint(joint.get("name"), kind, nq, nv, qpos0)
                joints.append(entry)
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        by_name = {entry.name: entry for entry in joints if entry.name is not None}
        actuators = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                actuators.append(by_name.get(element.get("joint")))

        timestep = _LIBRARY_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(actuators)
        self.actuator_ctrlrange = [[0.0, 0.0] for _ in actuators]
        self.actuator_ctrllimited = [False for _ in actuators]
        self._joints = joints
        self._actuators = actuators
        self.qpos0 = [0.0] * nq
        for entry in joints:
            if entry.qpos0 is not None:
                self.qpos0[entry.qpos_adr:entry.qpos_adr + 7] = entry.qpos0

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
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
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint receives a torque (placeholder integration)."""
    dt = float(model.opt.timestep)
    for index, joint in enumerate(model._actuators):
        if joint is None or index >= len(data.ctrl):
            continue
        data.qvel[joint.qvel_adr] += float(data.ctrl[index]) * _TORQUE_GAIN * dt
        data.qpos[joint.qpos_adr] += data.qvel[joint.qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
