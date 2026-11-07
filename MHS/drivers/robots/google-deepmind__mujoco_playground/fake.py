"""Stand-in ``mujoco`` module for the acrobot MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge loads ``mujoco`` when the model is
first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's MJCF
file, then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and ``data.time``/``qpos``/``qvel``/``ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``_Model`` takes the actuator control
ranges, the joint dimensions and the option time step from that tree.  The card's model is
``mujoco_playground/_src/dm_control_suite/xmls/acrobot.xml``: it sets the step to 0.01 s (line 18), declares two hinge
joints (lines 29 and 33) and one ``<motor>`` actuator with ``ctrlrange="-1 1"`` (line 41).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, constraint or tendon, applies no gear
ratio or actuator dynamics, and its integration is a placeholder motion of the actuated joint proportional to its
control value.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308  # placeholder: the largest finite float, used as an unbounded ctrl range
_TIMESTEP_DEFAULT = 0.002  # placeholder: a MuJoCo library default; the card's model states 0.01 s at line 18
_VELOCITY_PER_CTRL = 0.01  # placeholder: fake joint velocity per unit of control, not a physical coefficient
_FREE_QPOS_QUATERNION_W = 1.0  # placeholder: identity orientation of a free joint in the stand-in's default state
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}  # placeholder: MuJoCo's joint layout
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}  # placeholder: MuJoCo's joint layout


def _expand(node, base):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included file."""
    index = 0
    while index < len(node):
        child = node[index]
        if child.tag == "include":
            target = (base / str(child.get("file"))).resolve()
            included = ET.parse(str(target)).getroot()
            _expand(included, target.parent)
            node.remove(child)
            for offset, item in enumerate(list(included)):
                node.insert(index + offset, item)
            index += len(included)
        else:
            _expand(child, base)
            index += 1


def _load(path):
    """The MJCF tree of ``path`` with includes expanded (paths relative to the file that names them)."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: global attributes, class inheritance and per-tag defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        self._global = {}
        for section in root.findall("default"):
            self._walk(section, self._global, None)

    def _walk(self, section, target, parent):
        name = section.get("class")
        if name is not None:
            self._parent[name] = parent
        for child in section:
            if child.tag == "default":
                nested = child.get("class")
                node = self._attributes.setdefault(nested, {}) if nested is not None else target
                self._walk(child, node, name)
            else:
                target.setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The defaults of ``tag`` in ``class_name``, from the global section down the class chain."""
        out = dict(self._global.get(tag, {}))
        if class_name:
            chain, name, seen = [], class_name, set()
            while name is not None and name not in seen:
                seen.add(name)
                chain.append(name)
                name = self._parent.get(name)
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


class _Model:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        places = {}
        qpos = qvel = count = 0
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                kind = defaults.of(joint, "joint").get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = joint.get("name")
                if name:
                    places[name] = (qpos, qvel)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
                count += 1

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                ctrlrange = attributes.get("ctrlrange")
                is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                if ctrlrange is not None and is_limited:
                    low, high = (float(value) for value in ctrlrange.split()[:2])
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                targets.append(places.get(attributes.get("joint")))

        timestep = _TIMESTEP_DEFAULT
        for option in root.iter("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.njnt = count
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: The integration target of each actuator: its joint's qpos/qvel slot (a placeholder mapping)
        self.actuator_joint = targets

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
            self.qpos[3] = _FREE_QPOS_QUATERNION_W


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0
    # placeholder: a free joint starts at the identity orientation
    if model.nq >= 7:
        data.qpos[3] = _FREE_QPOS_QUATERNION_W


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one time step (placeholder dynamics, not MuJoCo's equations of motion)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        data.qvel[qvel_index] = data.ctrl[index] * _VELOCITY_PER_CTRL
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = _Model
        self.MjData = _Data
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
