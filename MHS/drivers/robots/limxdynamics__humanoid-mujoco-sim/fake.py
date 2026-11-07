"""Stand-in ``mujoco`` module for the LimX HU_D03 MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` when the model
is first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's MJCF
file (``models[0]``), then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange`` and ``data.time``/``qpos``/``qvel``/``ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``_Model`` takes the actuator control
ranges, the joint dimensions and the option time step from that tree.  The card's model
(``humanoid-description/HU_D03_description/xml/HU_D03_03.xml``) sets the step to 0.001 s (line 16), declares 31
``<motor>`` actuators (lines 406-443) and one free joint (line 92).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality or tendon constraint, and its
integration is a placeholder motion of each actuated joint driven by its control value, not the engine's dynamics.
All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import types
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.001 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: velocity (rad/s) the stand-in assigns to a joint per unit of its control value
_CTRL_TO_VELOCITY = 0.01
#: qpos and qvel contributions of a joint type; a missing type means a hinge
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included file."""
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
    """The MJCF tree of ``path`` with includes expanded (paths relative to the file that names them)."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and per-tag attribute defaults."""

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
        """The attributes of ``tag`` in a default class, following the class chain from the root down."""
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
        joint_place = {}
        qpos = qvel = count = 0
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                kind = defaults.of(joint, "joint").get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = joint.get("name")
                if name:
                    joint_place[name] = (qpos, qvel)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
                count += 1

        ranges, limited, places = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                control_range = attributes.get("ctrlrange")
                if control_range is not None:
                    low, high = (float(value) for value in control_range.split()[:2])
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                places.append(joint_place.get(attributes.get("joint")))

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.njnt = count
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: placeholder: the integration target of each actuator is its joint's qpos slot; no MuJoCo mapping
        self.actuator_joint = places

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


class _Data:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0
        # placeholder: a free joint starts at the identity orientation
        if model.nq >= 7:
            self.qpos[3] = 1.0


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0
    # placeholder: a free joint starts at the identity orientation
    if model.nq >= 7:
        data.qpos[3] = 1.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint moves by ``ctrl * _CTRL_TO_VELOCITY`` (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        data.qvel[qvel_index] = data.ctrl[index] * _CTRL_TO_VELOCITY
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


def fake_mujoco(**_options):
    """The backend factory: an object with the ``mujoco`` module members the bridge uses."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
    )
