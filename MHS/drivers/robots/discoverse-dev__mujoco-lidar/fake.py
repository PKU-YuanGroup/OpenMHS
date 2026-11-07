"""Fake ``mujoco`` module of the MuJoCo-LiDAR scene driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use,
and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  The ``fake``
backend is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's scene
(``models/scene_g1.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/
``ctrl`` arrays.

The model shape is read from the MJCF text itself, so the derived contract (per-actuator ``ctrl`` limits, the qpos
and qvel dimensions, the time step) is the card's model and not a number of this file.  ``_load`` parses the XML and
expands its ``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, ``_joints`` walks the body tree
in document order (the MuJoCo qpos/qvel layout) and ``_actuators`` takes the control ranges from the actuator
elements plus their default classes (including ``inheritrange``).

What this is not: MuJoCo.  It does not load meshes and textures, it resolves no contact, equality, tendon or sensor
constraint, and its integration is a placeholder first-order motion of each actuated joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  It never imports ``mujoco_lidar`` and it traces no LiDAR ray: the scan
array of the upstream ``MjLidarWrapper`` is not part of ``cap.world.step.v1``/``cap.world.reset.v1`` (see the
``gaps`` of driver.py and RESULT.json).  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: sentinel for an actuator whose model states no finite ctrlrange
_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; scene_g1 sets 0.002
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves a joint
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
                name = child.get("class") or parent
                if name is not None:
                    self._parent[name] = parent
                self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
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


def _joints(root, defaults):
    """The qpos/qvel address and the range of every named joint, in document order (MuJoCo's layout)."""
    joints = {}
    qpos = qvel = 0
    for body in root.findall("worldbody"):
        for element in body.iter():
            if element.tag == "freejoint":
                qpos += _QPOS["free"]
                qvel += _QVEL["free"]
            elif element.tag == "joint":
                attributes = defaults.of(element, "joint")
                kind = attributes.get("type", "hinge")
                name = attributes.get("name")
                span = attributes.get("range")
                limits = None
                if span is not None:
                    low, high = (float(value) for value in span.split()[:2])
                    limits = (low, high)
                if name:
                    joints[name] = (qpos, qvel, limits)
                qpos += _QPOS.get(kind, 1)
                qvel += _QVEL.get(kind, 1)
    return joints, qpos, qvel


def _actuators(root, defaults, joints):
    """The ctrlrange, ctrllimited flag and joint name of every actuator, in document order."""
    ranges, limited, names = [], [], []
    for section in root.findall("actuator"):
        for element in section:
            if element.tag == "default":
                continue
            attributes = defaults.of(element, element.tag)
            name = attributes.get("joint")
            names.append(name)
            span = attributes.get("ctrlrange")
            if span is not None:
                low, high = (float(value) for value in span.split()[:2])
                ranges.append([low, high])
                limited.append(True)
                continue
            inherited = attributes.get("inheritrange")
            joint = joints.get(name) if name else None
            if inherited is not None and float(inherited) != 0.0 and joint is not None and joint[2] is not None:
                low, high = joint[2]
                scale = float(inherited)
                ranges.append([low * scale, high * scale])
                limited.append(True)
                continue
            ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
            limited.append(False)
    return ranges, limited, names


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints, qpos, qvel = _joints(root, defaults)
        ranges, limited, names = _actuators(root, defaults, joints)
        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._joints = joints
        self._actuator_joints = names

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
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, name in enumerate(model._actuator_joints):
        joint = model._joints.get(name) if name else None
        if joint is None:
            continue
        qpos_address, qvel_address, _limits = joint
        data.qvel[qvel_address] = (data.ctrl[index] - data.qpos[qpos_address]) * _STEP_FRACTION / dt
        data.qpos[qpos_address] += data.qvel[qvel_address] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
