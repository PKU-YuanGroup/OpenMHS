"""Fake backend of the LimX HU_D03 description package: a pure Python stand-in for the ``mujoco`` library.

The driver is configuration only (a ``MujocoDriver``).  Its bridge imports ``mujoco`` lazily, and MuJoCo is neither
installed nor installable where the acceptance gate runs.  ``backends["fake"]`` therefore names this module object;
the bridge calls ``MjModel.from_xml_path`` on the card's first model
(``HU_D03_description/xml/HU_D03_03.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl``
arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the XML, ``_Defaults`` resolves the ``<default>``
class chain, and ``MjModel`` takes the joint dimensions, the actuator list, the per-actuator control ranges (an
explicit ``ctrlrange``, or a joint range scaled by ``inheritrange``) and the time step from that tree.  Every motor
in this model states ``ctrllimited="true"`` and an explicit ``ctrlrange``
(``HU_D03_description/xml/HU_D03_03.xml:406-443``), so the stand-in reports one bounded control interval per motor.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor, and its
integration is a placeholder: the model's ``<motor>`` entries are torque actuators, so each control value
accelerates its joint through a placeholder gain against a placeholder damping (model review, 2026-11-05: the
stand-in used to treat the control value as a position target).  There is no inertia, gravity, contact or joint
limit.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.  The numbers used
for integration are placeholders, not device facts.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max
# placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.001 s.
_TIMESTEP_S = 0.002
# placeholder: joint acceleration per unit of motor control (a torque stand-in, not the model's inertia).
_TORQUE_GAIN = 0.5
# placeholder: velocity damping of the stand-in per second.
_DAMPING = 2.0
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control interval of an actuator with neither a ctrlrange nor an inherited joint range.
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


def _pair(text):
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
    """One joint: its name, type, range, and its qpos/qvel positions in the data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        nq = nv = 0
        #: qpos0 as MuJoCo defines it: a free joint starts at its body's pos and quat, a ball joint at the identity
        #: quaternion, a hinge or slide at its ref (0 when the MJCF states none).
        qpos0 = []
        for worldbody in root.findall("worldbody"):
            for joint, inherited_class, owner in _walk_joints(worldbody, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                entry = _Joint(joint.get("name"), kind, nq, nv, None, None)
                if "range" in attributes and kind in ("hinge", "slide"):
                    entry.low, entry.high = _pair(attributes["range"])
                joints[entry.name] = entry
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)
                if kind == "free":
                    position = [float(item) for item in str(owner.get("pos") or "0 0 0").split()][:3]
                    quaternion = [float(item) for item in str(owner.get("quat") or "1 0 0 0").split()][:4]
                    qpos0.extend(position + quaternion)
                elif kind == "ball":
                    qpos0.extend([1.0, 0.0, 0.0, 0.0])
                else:
                    qpos0.append(float(attributes.get("ref", 0.0)))

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                joint = joints.get(attributes.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _pair(attributes["ctrlrange"])
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
                #: A motor acts on its joint's qpos and qvel entries; the free joint makes the two arrays diverge.
                targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.qpos0 = qpos0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._joints = joints

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


def _walk_joints(body, inherited_class):
    """Yield ``(joint element, effective default class, owning body)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass, body
        elif child.tag == "body":
            yield from _walk_joints(child, childclass)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset).

    qpos returns to the model's qpos0 (see ``MjModel``); the stand-in settles nothing by physics.
    """

    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each motor's torque-like control accelerates its joint (placeholder)."""
    dt = float(model.opt.timestep)
    for index, addresses in enumerate(model._targets):
        if addresses is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = addresses
        control = float(data.ctrl[index])
        velocity = float(data.qvel[qvel_adr])
        data.qvel[qvel_adr] = velocity + (control * _TORQUE_GAIN - velocity * _DAMPING) * dt
        data.qpos[qpos_adr] = float(data.qpos[qpos_adr]) + data.qvel[qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
