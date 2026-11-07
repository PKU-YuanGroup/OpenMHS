"""Fake backend of the robogym ShadowHand driver: a pure Python stand-in for the ``mujoco`` library.

The driver is a configuration-only ``MujocoDriver``: the bridge imports ``mujoco`` on first use, and the MuJoCo
engine is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
therefore names :class:`FakeMujoco`, whose instance carries the part of the ``mujoco`` API the bridge calls:
``MjModel.from_xml_path`` / ``from_xml_string``, ``MjData``, ``mj_resetData``, ``mj_forward``, ``mj_step``, the
integration-state snapshot functions and the model/data arrays.

The model shape is read from the pinned clone's MJCF text, never invented: ``_load`` parses the card's model and
expands its ``<include>`` elements (the scene includes ``assets.xml``, ``joint_position_actuation.xml`` and
``chain.xml``), ``_Defaults`` resolves the MJCF default classes, and ``_Model`` takes the integer dimensions, the
integration step and each actuator's control range from that tree.  The served model is
``robogym/assets/xmls/robot/shadowhand/main.xml``: one free joint (the hand base), 24 hinge joints and 20 ``general``
actuators whose ``ctrlrange`` is written on the actuator lines.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or actuator dynamics,
and its integration is a placeholder first-order motion of each actuated hinge toward its control target.  The
tendon-driven actuators (FFJ1, MFJ1, RFJ1, LFJ1) name a tendon, not a joint, so the stand-in moves no joint for
them.  The driver's fidelity ``gaps`` state every difference.  Nothing here talks to a device.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no finite ctrlrange; it is not a model bound.
_FLOAT_MAX = sys.float_info.max

#: placeholder: library default step when a model sets no <option timestep>; the served model states 0.008 s
#: (assets.xml:14), so this fallback is not used for the card's model.
_FALLBACK_TIMESTEP = 0.002

#: placeholder: fraction of the distance to its control target that one fake step moves a hinge.
_STEP_FRACTION = 0.05

#: qpos and dof contributions of the MJCF joint types; a joint with no ``type`` is a hinge.
_JOINT_SIZES = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file, in order."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, depth + 1)
            replacement = list(included)
            for item in replacement:
                included.remove(item)
            position = list(node).index(child)
            node.remove(child)
            for offset, item in enumerate(replacement):
                node.insert(position + offset, item)
        else:
            _expand(child, base, depth)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded relative to the file that names them."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and the attributes of each element tag."""

    def __init__(self, root):
        self._parents = {}
        self._tables = {}
        for section in root.findall("default"):
            self._walk(section, "main")

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name != parent:
                    self._parents[name] = parent
                self._walk(child, name)
            else:
                self._tables.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        name = class_name if class_name is not None else "main"
        chain = []
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parents.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._tables.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads only ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


def _timestep(root):
    for option in root.findall("option"):
        text = option.get("timestep")
        if text:
            return float(text)
    return _FALLBACK_TIMESTEP


def _joint_table(root, defaults):
    """``{joint name: (qpos address, dof address)}`` and the coordinate counts of the model."""
    table = {}
    qpos = dof = 0
    for world in root.findall("worldbody"):
        for element in world.iter():
            if element.tag == "freejoint":
                qpos_size, dof_size = _JOINT_SIZES["free"]
            elif element.tag == "joint":
                kind = defaults.of(element, "joint").get("type", "hinge")
                qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
            else:
                continue
            name = element.get("name")
            if name:
                table[name] = (qpos, dof)
            qpos += qpos_size
            dof += dof_size
    return table, qpos, dof


class _Model:
    """The stand-in ``mujoco.MjModel``: dimensions, time step and actuator control ranges of the MJCF tree."""

    def __init__(self, root):
        defaults = _Defaults(root)
        self.opt = _Opt(_timestep(root))
        self._joints, self.nq, self.nv = _joint_table(root, defaults)
        self.na = 0
        ranges = []
        limited = []
        targets = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                text = attributes.get("ctrlrange")
                is_limited = attributes.get("ctrllimited", "true").lower() not in ("false", "0")
                if text and is_limited:
                    low, high = (float(item) for item in text.split()[:2])
                    ranges.append([low, high])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                targets.append(self._joints.get(str(attributes.get("joint"))))
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)

    def target(self, index):
        """The ``(qpos address, dof address)`` the actuator drives, when the model names a joint."""
        return self._targets[index]


class _Data:
    """The stand-in ``mujoco.MjData``: the arrays the bridge reads and writes."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data arrays to zero (the stand-in has no keyframe pose or qpos0 table)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated hinge moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index in range(model.nu):
        target = model.target(index)
        if target is None:
            continue  # a tendon-driven actuator names no joint; the stand-in does not resolve tendons
        address, dof = target
        data.qvel[dof] = (float(data.ctrl[index]) - data.qpos[address]) * _STEP_FRACTION / dt
        data.qpos[address] += data.qvel[dof] * dt
    data.time += dt


class _MjtState:
    """The ``mujoco.mjtState`` flag the bridge reads."""

    mjSTATE_INTEGRATION = 1


def mj_stateSize(model, spec):
    """The length of the stand-in integration state: time, qpos, qvel and ctrl."""
    del spec
    return 1 + model.nq + model.nv + model.nu


def mj_getState(model, data, state, spec):
    """Copy the stand-in integration state into ``state`` (a list or a numpy array)."""
    del spec
    values = [float(data.time)] + [float(item) for item in data.qpos] + \
             [float(item) for item in data.qvel] + [float(item) for item in data.ctrl]
    state[:] = values


def mj_setState(model, data, state, spec):
    """Restore the stand-in integration state written by :func:`mj_getState`."""
    del spec
    offset = 0
    data.time = float(state[offset])
    offset += 1
    data.qpos[:] = [float(item) for item in state[offset:offset + model.nq]]
    offset += model.nq
    data.qvel[:] = [float(item) for item in state[offset:offset + model.nv]]
    offset += model.nv
    data.ctrl[:] = [float(item) for item in state[offset:offset + model.nu]]


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = _Model
        self.MjData = _Data
        self.mjtState = _MjtState
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
        self.mj_stateSize = mj_stateSize
        self.mj_getState = mj_getState
        self.mj_setState = mj_setState
