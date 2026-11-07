"""Fake ``mujoco`` module for the Safety Gym package: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs.  ``backends["fake"]`` therefore names this
module object; the bridge calls ``MjModel.from_xml_path`` on the card's models[0] (``safety_gym/xmls/car.xml``), then
``mj_resetData`` / ``mj_forward`` / ``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange`` and the ``data.time`` / ``qpos`` / ``qvel`` / ``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the file and expands its ``<include>`` elements,
``_Defaults`` resolves the ``<default>`` class chain, and ``MjModel`` derives the joint layout (a free joint 7 qpos and
6 qvel, a ball 4 and 3, a hinge or slide 1 and 1) and the per-actuator control ranges from the actuator's
``ctrlrange`` and ``ctrllimited`` (the global default of car.xml:7 gives the two motors ``ctrlrange="-1 1"`` with
``ctrllimited true``).  The initial free-joint position is the body position of the model (car.xml:12); the identity
quaternion and the step fraction are placeholders of this stand-in.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, constraint or sensor, and its
integration is a placeholder first-order motion of each actuated hinge or slide joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a MuJoCo joint type (the format's dimensions, not a model fact)
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control range of an actuator with no ctrlrange (the bridge treats it as unbounded).
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
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


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
    """One joint of the model: its name, type, positions in qpos/qvel, and its initial qpos."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, default):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.default = default


def _initial_qpos(kind, body):
    """The initial qpos of one joint: the body position for a free joint, a placeholder identity quaternion otherwise."""
    if kind == "free":
        values = [float(item) for item in str(body.get("pos", "0 0 0")).split()]
        values = (values + [0.0, 0.0, 0.0])[:3]
        return values + [1.0, 0.0, 0.0, 0.0]  # placeholder: the identity quaternion
    if kind == "ball":
        return [1.0, 0.0, 0.0, 0.0]  # placeholder: the identity quaternion
    return [0.0]


def _walk_body(body, inherited_class):
    """Yield ``(joint element, effective default class, body element)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass, body
        elif child.tag == "body":
            yield from _walk_body(child, childclass)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        qpos0 = []
        nq = nv = 0
        for body in root.findall("worldbody"):
            for joint, inherited_class, parent_body in _walk_body(body, None):
                if joint.tag == "freejoint":
                    kind = "free"
                else:
                    kind = defaults.of(joint, "joint", inherited_class).get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"joint type {kind!r} is not a MuJoCo joint type")
                default = _initial_qpos(kind, parent_body)
                entry = _Joint(joint.get("name"), kind, nq, nv, default)
                joints[entry.name] = entry
                qpos0.extend(default)
                nq += _QPOS[kind]
                nv += _QVEL[kind]

        ranges, limited, actuated = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                joint = joints.get(attributes.get("joint") or attributes.get("jointinparent"))
                low, high = _UNBOUNDED
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _two_floats(attributes["ctrlrange"])
                    is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                actuated.append(joint)

        timestep = 0.002  # placeholder: MuJoCo's library default when a model sets no <option timestep>
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.qpos0 = qpos0
        self._actuated = actuated

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
    """Advance the stand-in one time step: each actuated hinge or slide joint moves toward its control target."""
    dt = float(model.opt.timestep)
    for index, joint in enumerate(model._actuated):
        if joint is None or index >= len(data.ctrl) or joint.kind not in ("hinge", "slide"):
            continue
        target = float(data.ctrl[index])
        current = float(data.qpos[joint.qpos_adr])
        data.qvel[joint.qvel_adr] = (target - current) * _STEP_FRACTION / dt
        data.qpos[joint.qpos_adr] = current + data.qvel[joint.qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
