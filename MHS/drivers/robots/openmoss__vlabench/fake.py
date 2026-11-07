"""Fake ``mujoco`` module of the vlabench driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: a ``MujocoDriver`` is configuration only.  The bridge imports ``mujoco`` on first use, and MuJoCo is
neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]`` is
therefore this class object, the stand-in module object the SDK's own MuJoCo family tests use.  The bridge calls
``MjModel.from_xml_path`` on the card's xarm7 scene, then ``mj_resetData``, ``mj_forward`` and ``mj_step``, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is read from the MJCF file itself, so the derived contract (the per-actuator ``ctrl`` limits, the joint
count, the time step) is the card's model and not a number of this file: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the actuator control
ranges, the joint dimensions and the option time step from that tree.  The only number this module adds is the MuJoCo
library default time step, used when the model sets none (this model sets none: ``xarm7.xml:4``).

What this is not: MuJoCo.  It loads no meshes and textures, resolves no contact, equality or tendon constraint, and its
integration is a placeholder first-order motion of each actuated joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets none
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves a joint
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of a joint type (MuJoCo's own layout).  Missing means "hinge".
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


def _tendon_joint(root, name):
    """The name of the first joint a fixed tendon couples (the gripper actuator of this model)."""
    for tendon in root.iter("tendon"):
        for fixed in tendon.findall("fixed"):
            if fixed.get("name") != name:
                continue
            joint = fixed.find("joint")
            if joint is not None:
                return joint.get("joint")
    return None


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        # The worldbody joints in document order, with the qpos offset MJCF gives each of them.
        joints = {}
        qpos = qvel = 0
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                attributes = defaults.of(joint, "joint")
                kind = attributes.get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r} in the card model")
                if joint.get("name"):
                    joints[joint.get("name")] = (qpos, kind)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                if "ctrlrange" in attributes:
                    low, high = (float(value) for value in attributes["ctrlrange"].split()[:2])
                    ranges.append([low, high])
                    limited.append(True)  # <compiler autolimits="true"/> infers ctrllimited from ctrlrange
                else:
                    ranges.append([0.0, 0.0])
                    limited.append(False)
                joint_name = element.get("joint")
                if joint_name is None and element.get("tendon") is not None:
                    joint_name = _tendon_joint(root, element.get("tendon"))
                target = joints.get(joint_name)
                targets.append(target[0] if target is not None else None)
        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: qpos index each actuator pushes, for the stand-in integration only.
        self.actuator_joint = targets

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
    if dt <= 0:
        return
    for index, target in enumerate(model.actuator_joint):
        if target is None or target >= model.nq:
            continue
        data.qvel[target] = (data.ctrl[index] - data.qpos[target]) * _STEP_FRACTION / dt
        data.qpos[target] += data.qvel[target] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
