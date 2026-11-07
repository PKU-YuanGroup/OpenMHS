"""Fake ``mujoco`` module for the Unitree MuJoCo H2 package: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs.  ``backends["fake"]`` names this class;
the bridge calls ``MjModel.from_xml_path`` on the card's H2 scene, then ``mj_resetData``/``mj_forward``/``mj_step``
on it, and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the scene and expands its ``<include>`` elements,
``_Defaults`` resolves the ``<default>`` class chain, and ``MjModel`` takes the joint count, the actuator count and
the per-actuator control ranges from that tree.  The H2 model (``unitree_robots/h2/h2_mujoco.xml``) states its own
1 ms timestep and a ctrlrange for every one of its 31 motors, so those values are the model's, not this file's.

What this is not: MuJoCo.  It loads no mesh, texture or sensor, resolves no contact, constraint or gravity, and its
integration is a placeholder torque response (``_TORQUE_GAIN``), not MuJoCo's physics.  The driver's fidelity
``gaps`` list all of that.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; the H2 model sets 0.001 s
_LIBRARY_TIMESTEP_S = 0.002
#: placeholder: arbitrary torque-to-angular-acceleration scale of the stand-in, not a physical parameter
_TORQUE_GAIN = 0.05
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control range of a motor with neither a ctrlrange nor an inherited joint range.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


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


def _floats(text, count=2):
    values = [float(item) for item in str(text).split()]
    if len(values) < count:
        raise ValueError(f"expected at least {count} numbers, got {text!r}")
    return values


class _Defaults:
    """The ``<default>`` classes of a model tree: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name is not None:
                    self._parent.setdefault(name, parent)
                self._walk(child, name)
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def _chain(self, class_name):
        names, name = [], class_name
        while name is not None and name not in names:
            names.append(name)
            name = self._parent.get(name)
        names.reverse()
        if not names or names[0] is not None:
            names.insert(0, None)
        return names

    def get(self, class_name, tag):
        """The merged defaults of ``tag`` for a class, following the class chain from the global defaults down."""
        out = {}
        for name in self._chain(class_name):
            out.update(self._attributes.get(name, {}).get(tag, {}))
        return out

    def of(self, element, tag, inherited_class=None):
        """The defaults of ``element``'s effective class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class") or inherited_class, tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its name, type, range and qpos/qvel positions in the data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high, qpos0):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high
        self.qpos0 = qpos0


def _body_pose(body):
    """The initial position and quaternion of a body (MuJoCo's default is the body ``pos``/``quat``)."""
    pos = _floats(body.get("pos", "0 0 0"), 3)[:3]
    quat = _floats(body.get("quat", "1 0 0 0"), 4)[:4]
    return pos + quat


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        nq = nv = 0
        for body in root.findall("worldbody"):
            for joint, inherited_class, parent in _walk_body(body, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                entry = _Joint(joint.get("name"), kind, nq, nv, None, None, None)
                if kind == "free":
                    entry.qpos0 = _body_pose(parent)
                elif "range" in attributes and kind in ("hinge", "slide"):
                    entry.low, entry.high = _floats(attributes["range"])[:2]
                if entry.name is not None:
                    joints[entry.name] = entry
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        ranges, limited, joints_of_actuator = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                joint = joints.get(attributes.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _floats(attributes["ctrlrange"])[:2]
                    is_limited = True
                elif joint is not None and joint.low is not None and joint.high is not None:
                    try:
                        inherit = float(attributes.get("inheritrange", 0.0))
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint.low * inherit, joint.high * inherit
                        is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                joints_of_actuator.append(joint)

        timestep = _LIBRARY_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._joints = joints
        self._actuators = joints_of_actuator
        self.qpos0 = [0.0] * nq
        for entry in joints.values():
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


def _walk_body(body, inherited_class):
    """Yield ``(joint element, effective default class, parent body)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass, body
        elif child.tag == "body":
            yield from _walk_body(child, childclass)


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
