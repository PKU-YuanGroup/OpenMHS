"""Fake ``mujoco`` module of the pnd_mujoco driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use,
and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  The fake
entry ``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's
scene (``models[0]``, ``pnd_robots/adam_lite/scene.xml``), then ``mj_resetData``/``mj_forward``/``mj_step``, and
reads ``model.opt.timestep``, ``model.nq``/``nv``/``nu``, ``model.actuator_ctrlrange`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself, not from constants of this file: ``_load`` expands the
``<include>`` elements (the scene includes ``adam_lite.xml``), ``_Defaults`` resolves the MJCF default classes, and
``MjModel`` takes the joint dimensions, the actuator count and every control range from that tree.  The scene states
its 0.001 s step (``scene.xml:18``), so the derived timestep is 1.0 ms as well.  The only numbers added here are the
placeholder integration constants below, marked ``# placeholder``.

What this is not: MuJoCo.  It loads no mesh and no texture, resolves no contact, equality, tendon or muscle model,
applies no gravity, and its integration is a placeholder first-order motion of each actuated hinge at a velocity
proportional to its control command.  The driver's fidelity ``gaps`` say so.  Nothing here talks to a device.
"""

import math
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: the qpos/qvel width of each MJCF joint type in MuJoCo's own layout
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: placeholder: joint speed (rad/s) one full-scale actuator command asks the stand-in for
_PLACEHOLDER_SPEED = 0.5


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
                name = child.get("class") or parent
                if name is not None:
                    self._parent[name] = parent
                self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes[item].get(tag, {}))
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


def _floats(text):
    return [float(value) for value in str(text).split()]


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        defaults = _Defaults(root)
        ranges, limited, joints, starts = [], [], [], {}
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default" or element.tag not in (
                        "motor", "position", "velocity", "general", "intvelocity", "damper", "cylinder", "muscle",
                        "adhesion"):
                    continue
                attributes = defaults.of(element, element.tag)
                joints.append(attributes.get("joint"))
                if "ctrlrange" in attributes:
                    low, high = _floats(attributes["ctrlrange"])[:2]
                    ranges.append([low, high])
                    limited.append(str(attributes.get("ctrllimited", "true")).lower() in ("true", "1"))
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
        qpos = qvel = 0
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                attributes = defaults.of(joint, "joint")
                kind = attributes.get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"the stand-in does not know the MJCF joint type {kind!r}")
                name = attributes.get("name")
                if name is not None:
                    starts[name] = (qpos, qvel, kind)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
        timestep = None
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        # placeholder: the library default of a model that states no <option timestep>
        self.opt = _Opt(0.002 if timestep is None else timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._actuator_joint = joints
        self._joint_starts = starts

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


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one step: each actuated hinge moves at a speed set by its command (placeholder)."""
    dt = float(model.opt.timestep)
    for index in range(model.nu):
        name = model._actuator_joint[index] if index < len(model._actuator_joint) else None
        start = model._joint_starts.get(name) if name is not None else None
        if start is None or start[2] not in ("hinge", "slide"):
            continue
        qpos_adr, qvel_adr, _kind = start
        low, high = model.actuator_ctrlrange[index]
        span = max(abs(low), abs(high))
        if not math.isfinite(span) or span <= 0:
            span = 1.0
        data.qvel[qvel_adr] = float(data.ctrl[index]) / span * _PLACEHOLDER_SPEED
        data.qpos[qpos_adr] += data.qvel[qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
