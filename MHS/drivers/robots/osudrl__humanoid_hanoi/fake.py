"""Fake ``mujoco`` module of the humanoid_hanoi driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's first model
(``sim/digit_sim/digit-v3-box-tower-of-hanoi.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl``
arrays.

The model shape is read from the MJCF file itself, so the derived contract (per-actuator ``ctrl`` limits, the joint
dimensions, the time step) is the card's model and not a number of this file: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the actuator control
ranges, the joint dimensions and the option time step from that tree.  The only numbers this module adds are the
MuJoCo library default time step, used when the model sets none (this model sets ``timestep='0.0005'`` at line 3), and
the placeholder step fraction below.

What this is not: MuJoCo.  It does not load meshes or textures, it resolves no contact, equality or tendon constraint,
and its integration is a placeholder first-order motion of each actuated joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets one
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves an actuated joint
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of a joint type; MuJoCo's own layout.  Missing means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
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
    """The MJCF tree of ``path`` with its includes expanded (paths relative to the file that names them)."""
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


class _Defaults:
    """The MJCF ``<default>`` classes of a model tree: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class")
                if name is None:
                    self._walk(child, parent)
                else:
                    self._parent[name] = parent
                    self._walk(child, name)
            else:
                self._attributes.setdefault(parent or "", {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        chain, name = [], class_name or ""
        while name not in chain:
            chain.append(name)
            if not name:
                break
            name = self._parent.get(name) or ""
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its type, its qpos/qvel addresses and its reset value."""

    def __init__(self, name, kind, qpos, qvel, default):
        self.name = name
        self.kind = kind
        self.qpos = qpos
        self.qvel = qvel
        self.default = default


class _Actuator:
    """One actuator of the model: its control range and the joint coordinate it drives."""

    def __init__(self, name, joint, low, high, limited, qpos, qvel):
        self.name = name
        self.joint = joint
        self.low = low
        self.high = high
        self.limited = limited
        self.qpos = qpos
        self.qvel = qvel


def _joint_default(kind, attributes):
    if kind == "free":
        return [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    if kind == "ball":
        return [1.0, 0.0, 0.0, 0.0]
    return [float(attributes.get("ref", 0.0))]


def _joints(root, defaults):
    """The joints of the model in document order, with their qpos/qvel addresses."""
    joints = []
    qpos = qvel = 0

    def walk(body):
        nonlocal qpos, qvel
        for child in list(body):
            if child.tag not in ("joint", "freejoint"):
                continue
            attributes = defaults.of(child, "joint")
            kind = "free" if child.tag == "freejoint" else attributes.get("type", "hinge")
            if kind not in _QPOS:
                kind = "hinge"
            default = _joint_default(kind, attributes)
            joints.append(_Joint(attributes.get("name"), kind, qpos, qvel, default))
            qpos += _QPOS[kind]
            qvel += _QVEL[kind]
        for child in list(body):
            if child.tag == "body":
                walk(child)

    for body in root.findall("worldbody"):
        walk(body)
    return joints, qpos, qvel


def _actuators(root, defaults, joints):
    """The actuator elements in document order, with ctrlrange and the addressed joint."""
    by_name = {joint.name: joint for joint in joints if joint.name}
    actuators = []
    for section in root.findall("actuator"):
        for element in section:
            if element.tag == "default":
                continue
            attributes = defaults.of(element, element.tag)
            joint = by_name.get(attributes.get("joint"))
            if "ctrlrange" in attributes:
                low, high = (float(value) for value in attributes["ctrlrange"].split()[:2])
                limited = str(attributes.get("ctrllimited", "true")).lower() != "false"
            else:
                low, high = -_FLOAT_MAX, _FLOAT_MAX
                limited = False
            actuators.append(_Actuator(attributes.get("name"), attributes.get("joint"), low, high, limited,
                                       joint.qpos if joint else None, joint.qvel if joint else None))
    return actuators


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        self._joints, self.nq, self.nv = _joints(root, defaults)
        self._actuators = _actuators(root, defaults, self._joints)
        self.na = 0
        self.nu = len(self._actuators)
        self.actuator_ctrlrange = [[item.low, item.high] for item in self._actuators]
        self.actuator_ctrllimited = [item.limited for item in self._actuators]
        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)

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
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0
        mj_resetData(model, self)


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    for joint in model._joints:
        data.qpos[joint.qpos:joint.qpos + len(joint.default)] = joint.default
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, actuator in enumerate(model._actuators):
        if actuator.qpos is None:
            continue
        velocity = (float(data.ctrl[index]) - data.qpos[actuator.qpos]) * _STEP_FRACTION / dt
        data.qvel[actuator.qvel] = velocity
        data.qpos[actuator.qpos] += velocity * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
