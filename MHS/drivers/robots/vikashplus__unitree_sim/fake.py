"""Fake backend of the unitree_sim driver: a pure Python stand-in for the MuJoCo library.

The driver is configuration only (a ``MujocoDriver``).  The bridge imports ``mujoco`` on first use, and MuJoCo is
neither installed nor installable where the acceptance gate runs (no network, no pip), so the ``fake`` backend is this
module object: the bridge calls ``MjModel.from_xml_path`` on the card's model (``a1.xml``), then
``mj_resetData``/``mj_forward``/``mj_step``, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``,
``model.nu``, ``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is read from the MJCF text itself, so the derived contract (the twelve per-actuator ``ctrl`` intervals,
the joint dimensions and the time step) is the card's model and not a number of this file.  ``_load`` parses the XML
and expands its ``<include>`` elements (``a1.xml:33`` names ``basic_scene.xml``), ``_Defaults`` resolves the MJCF
default classes, and ``MjModel`` takes the actuator control ranges, the joint dimensions and the free-joint start pose
from that tree.  Only two numbers are added, both placeholders and both listed in the driver's fidelity ``gaps``: the
MuJoCo library default step used when a model sets no ``<option timestep>``, and the fraction of the distance to its
control target that one fake step moves a joint.

What this is not: MuJoCo.  It does not load meshes or textures, it resolves no contact, equality or tendon
constraint, it does not integrate the free base, and its joint motion is a placeholder first-order approach, not
MuJoCo's physics.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default timestep when a model sets no <option timestep>; a1.xml sets none
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves a joint
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of an MJCF joint type, MuJoCo's own layout.  Missing means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = (base / str(child.get("file"))).resolve()
            included = ET.parse(str(target)).getroot()
            _expand(included, target.parent, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded relative to the file that names them."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes of a model: class inheritance and the attributes of each element tag."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class")
                if name is not None:
                    self._parent[name] = parent
                self._walk(child, name if name is not None else parent)
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = dict(self._attributes.get(None, {}).get(tag, {}))
        chain, name = [], element.get("class")
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        for item in reversed(chain):
            out.update(self._attributes[item].get(tag, {}))
        out.update(element.attrib)
        return out


def _joints(root):
    """The joints of the model in MuJoCo's qpos order: ``(type, name, parent body)`` per free joint and joint."""
    out = []

    def walk(node):
        for child in node:
            if child.tag == "freejoint":
                out.append(("free", None, node))
            elif child.tag == "joint":
                out.append((child.get("type", "hinge"), child.get("name"), node))
            walk(child)

    for body in root.findall("worldbody"):
        walk(body)
    return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        self.nq = 0
        self.nv = 0
        self.qpos0 = []
        self._joint_offsets = {}
        for kind, name, body in _joints(root):
            if kind not in _QPOS:
                raise ValueError(f"the stand-in does not know the MJCF joint type {kind!r}")
            if kind == "free":
                position = [float(value) for value in (body.get("pos") or "0 0 0").split()[:3]]
                quaternion = [float(value) for value in (body.get("quat") or "1 0 0 0").split()[:4]]
                self.qpos0.extend(position + quaternion)
            elif kind == "ball":
                self.qpos0.extend([1.0, 0.0, 0.0, 0.0])
            else:
                self.qpos0.extend([0.0] * _QPOS[kind])
            if name is not None and kind in ("hinge", "slide"):
                self._joint_offsets[name] = (self.nq, self.nv)
            self.nq += _QPOS[kind]
            self.nv += _QVEL[kind]
        ranges, limited, actuator_joint = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                ctrlrange = attributes.get("ctrlrange")
                if ctrlrange is None:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                else:
                    low, high = (float(value) for value in ctrlrange.split()[:2])
                    ranges.append([low, high])
                    limited.append(str(attributes.get("ctrllimited", "false")).lower() in ("true", "1"))
                actuator_joint.append(self._joint_offsets.get(element.get("joint")))
        self.nu = len(ranges)
        self.na = 0
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._actuator_joint = actuator_joint
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
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (qpos0, zero velocity and control, time zero)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, offset in enumerate(model._actuator_joint):
        if offset is None:
            continue
        qpos_index, qvel_index = offset
        data.qvel[qvel_index] = (data.ctrl[index] - data.qpos[qpos_index]) * _STEP_FRACTION / dt
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
