"""Stand-in ``mujoco`` module for the ROBOTIS FFW-BG2 MuJoCo driver.

The driver is a :class:`mhs.driver.MujocoDriver`, and the bridge imports the real ``mujoco`` library lazily.
MuJoCo is not installed where the acceptance gate runs, so ``backends["fake"]`` is the module object this file
builds: the bridge calls ``MjModel.from_xml_path`` on the card's scene, then ``MjData``, ``mj_resetData``,
``mj_forward`` and ``mj_step``, and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is not written in this file.  ``_load`` parses the scene and expands its ``<include>`` elements;
``_Defaults`` resolves the MJCF default classes; ``_Model`` derives the joint dimensions and the actuator control
ranges from the model tree.  For this repository every actuator is a ``<position>`` element with
``inheritrange="1"`` (``robotis_ffw/ffw_bg2.xml:325-348``), so its control range is the range of the joint it
drives (for example ``lift_joint``: ``robotis_ffw/ffw_bg2.xml:41``).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or actuator
constraint, and its integration is a placeholder first-order motion of each actuated joint toward its control
target (``_STEP_FRACTION``).  The driver's fidelity ``gaps`` say so.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: MuJoCo's library default step when the model sets no <option timestep>; this model sets none
#: (robotis_ffw/ffw_bg2.xml:4).  The real engine's value was not read here.
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a joint type (MuJoCo's own layout); a missing type means a hinge.
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
_UNLIMITED = float("inf")


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
    """The MJCF ``<default>`` classes of a model tree: class inheritance and per-tag attributes."""

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


class _Model:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joint_attributes = {}
        qpos_index, qvel_index = {}, {}
        qpos = qvel = 0
        for worldbody in root.findall("worldbody"):
            for joint in worldbody.iter("joint"):
                attributes = defaults.of(joint, "joint")
                name = joint.get("name")
                if name:
                    joint_attributes[name] = attributes
                    qpos_index[name] = qpos
                    qvel_index[name] = qvel
                kind = attributes.get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"the fake does not understand joint type {kind!r}")
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]

        ranges, limited, actuator_joint = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                low, high = -_UNLIMITED, _UNLIMITED
                is_limited = False
                if attributes.get("ctrlrange") is not None:
                    low, high = (float(value) for value in str(attributes["ctrlrange"]).split()[:2])
                    is_limited = True
                elif str(attributes.get("inheritrange")) == "1":
                    joint_name = attributes.get("joint")
                    joint_range = (joint_attributes.get(joint_name) or {}).get("range")
                    if joint_range is not None:
                        low, high = (float(value) for value in str(joint_range).split()[:2])
                        is_limited = True
                ranges.append([low, high])
                limited.append(is_limited)
                joint_name = attributes.get("joint")
                actuator_joint.append((qpos_index.get(joint_name), qvel_index.get(joint_name)))

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.actuator_joint = actuator_joint

    @classmethod
    def from_xml_path(cls, path):
        """The model the bridge loads: the scene with its includes expanded, parsed for its shape only."""
        return cls(_load(path))


class _Data:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        # placeholder: the model defines no keyframe, so resetData starts every joint at zero
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = [0.0] * model.na
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq  # placeholder: no keyframe in the model, so qpos starts at zero
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = [0.0] * model.na
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        qpos_index, qvel_index = place
        if qpos_index is None or qvel_index is None:
            continue
        data.qvel[qvel_index] = (float(data.ctrl[index]) - float(data.qpos[qpos_index])) * _STEP_FRACTION / dt
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object named by ``backends["fake"]``."""

    def __init__(self, **_options):
        self.MjModel = _Model
        self.MjData = _Data
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
