"""Stand-in ``mujoco`` module for the MuJoCo MPC fingers driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use,
and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  The bridge
calls ``MjModel.from_xml_path`` on the card's MJCF file (``models[0]``, ``mjpc/tasks/fingers/task.xml``), then
``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is read from the MJCF file itself, so the derived contract (six actuator control ranges, the
qpos/qvel dimensions and the time step) is the card's model and not a number of this file: ``_load`` parses the XML
and expands its ``<include>`` elements (``task.xml:2`` includes ``../common.xml``), ``_Defaults`` resolves the MJCF
default classes, and ``MjModel`` takes the actuator control ranges, the joint dimensions and the option time step
from that tree.  The only numbers this file adds are the MuJoCo library default time step, used when a model sets
none (this model sets 0.001 s at ``task.xml:4``), and the placeholder integration constants below.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or actuator constraint,
and its integration is a placeholder first-order motion of each actuated slide joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import types
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.001 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves a slide joint
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


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        free_qpos = []
        qpos = qvel = 0
        for worldbody in root.findall("worldbody"):
            for element in worldbody.iter():
                kind = None
                if element.tag == "freejoint":
                    kind = "free"
                elif element.tag == "joint":
                    kind = defaults.of(element, "joint").get("type", "hinge")
                if kind is None:
                    continue
                name = element.get("name")
                if name:
                    joints[name] = (qpos, qvel)
                if kind == "free":
                    free_qpos.append(qpos)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
        ranges, limited, places = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                if "ctrlrange" in attributes:
                    low, high = (float(value) for value in attributes["ctrlrange"].split()[:2])
                    ranges.append([low, high])
                    limited.append(str(attributes.get("ctrllimited", "true")).lower() == "true")
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                places.append(joints.get(element.get("name")))
        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, len(ranges)
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.actuator_joint = places
        self.free_qpos = free_qpos

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
        self.act = [0.0] * model.na
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = [0.0] * model.na
    data.time = 0.0
    # placeholder: a free joint starts at the identity orientation (w = 1)
    for start in model.free_qpos:
        data.qpos[start + 3] = 1.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities (sensors, contacts) to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated slide joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        error = float(data.ctrl[index]) - float(data.qpos[qpos_index])
        data.qvel[qvel_index] = error * _STEP_FRACTION / dt
        data.qpos[qpos_index] += error * _STEP_FRACTION
    data.time += dt


def fake_mujoco(**_options):
    """The backend factory: an object with the ``mujoco`` module members the bridge uses."""
    return types.SimpleNamespace(
        MjModel=MjModel,
        MjData=MjData,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
    )
