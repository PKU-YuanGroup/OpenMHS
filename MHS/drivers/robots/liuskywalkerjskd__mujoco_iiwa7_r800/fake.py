"""Fake ``mujoco`` module for the iiwa7 package: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
therefore names this class; the bridge calls ``MjModel.from_xml_path`` on the card's first model
(``iiwa7_mjcf/iiwa7_tuned.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl``
arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the file and expands any ``<include>`` elements,
``_Defaults`` resolves the ``<default>`` class chain, and ``MjModel`` takes the joint dimensions, the actuator count
and the per-actuator control ranges (an explicit ``ctrlrange``, or a joint range scaled by ``inheritrange``) from the
tree.  The only numbers added here are the library default time step used when a model sets none and the fraction a
fake step moves toward a control target; both are marked ``placeholder``.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality or tendon constraint, and its
integration is a placeholder first-order motion of each actuated joint toward its control target, not MuJoCo's
physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control range of an actuator with neither a ctrlrange nor an inherited joint range.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _expand_includes(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included ``<mujoco>`` root."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand_includes(included, target.resolve().parent, depth + 1)
            children.extend(list(included))
        else:
            _expand_includes(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded, each path relative to the file that names it."""
    root = ET.parse(str(path)).getroot()
    _expand_includes(root, Path(path).resolve().parent)
    return root


def _two_floats(text):
    """The two numbers of an MJCF range such as ``"-2.96706 2.96706"``."""
    values = [float(item) for item in str(text).split()]
    if len(values) != 2:
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
    """One joint of the model: its name, type, range and qpos/qvel positions in the data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


def _walk_bodies(body, inherited_class):
    """Yield ``(joint element, effective default class)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass
        elif child.tag == "body":
            yield from _walk_bodies(child, childclass)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for joint, inherited_class in _walk_bodies(worldbody, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                entry = _Joint(joint.get("name"), kind, nq, nv, None, None)
                if "range" in attributes and kind in ("hinge", "slide"):
                    entry.low, entry.high = _two_floats(attributes["range"])
                joints[entry.name] = entry
                nq += _QPOS_DIM.get(kind, 1)
                nv += _QVEL_DIM.get(kind, 1)

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
                    low, high = _two_floats(attributes["ctrlrange"])
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
                targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._joints = joints

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, target in enumerate(model._targets):
        if target is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = target
        target_value = float(data.ctrl[index])
        current = float(data.qpos[qpos_adr])
        delta = (target_value - current) * _STEP_FRACTION
        data.qvel[qvel_adr] = delta / dt
        data.qpos[qpos_adr] = current + delta
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
