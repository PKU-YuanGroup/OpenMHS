"""Stand-in ``mujoco`` module for the LeCasa package: the model shape of the SO101 MJCF, in pure Python.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the ``mujoco`` bridge imports the library
lazily, and MuJoCo is neither installed nor installable where the acceptance gate runs.  ``backends["fake"]``
therefore names this module object; the bridge calls ``MjModel.from_xml_path`` on the card's robot model
(``src/robot/so101_simplified.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange`` and
``model.actuator_ctrllimited`` plus the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_parse`` reads the ``<default>`` classes, walks the nested
``<worldbody>`` bodies for their joints, and takes the actuator count, the per-actuator control ranges (an explicit
``ctrlrange`` or a joint range scaled by ``inheritrange``) and the joint dimensions from that tree.  The one number
added here is MuJoCo's own library default time step, used when the model sets no ``<option timestep>``
(``src/robot/so101_simplified.xml`` sets none); it is marked ``placeholder``.

What this is not: MuJoCo.  It loads no mesh, resolves no contact, equality or tendon constraint, and its integration
is a placeholder first-order motion of each actuated joint toward its control target, not MuJoCo's physics.  Those
limits are listed in the fidelity ``gaps`` of ``driver.py``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep> (this model sets none)
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint
_SETTLE_FRACTION = 0.1
#: qpos and qvel widths of a joint type; a joint without a type is a hinge.
_QPOS_WIDTH = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_WIDTH = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control interval of an actuator with neither a ctrlrange nor an inherited joint range.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


class _Defaults:
    """The ``<default>`` classes of a model: class inheritance and the per-tag attributes of each class."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._visit(section, None)

    def _visit(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name is not None:
                    self._parent.setdefault(name, parent)
                self._visit(child, name)
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

    def of(self, element, tag, inherited_class=None):
        """The merged defaults of ``element``'s effective class for ``tag``, overridden by its own attributes."""
        out = {}
        for name in self._chain(element.get("class") or inherited_class):
            out.update(self._attributes.get(name, {}).get(tag, {}))
        out.update(element.attrib)
        return out


def _walk_joints(container, inherited_class):
    """Yield ``(joint element, effective default class)`` for every joint below a body."""
    childclass = container.get("childclass") or inherited_class
    for child in container:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass
        elif child.tag in ("body", "frame"):
            yield from _walk_joints(child, childclass)


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        nq = nv = 0
        for world in root.findall("worldbody"):
            for joint, inherited_class in _walk_joints(world, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                entry = {"kind": kind, "qpos": nq, "qvel": nv, "low": None, "high": None}
                if "range" in attributes and kind in ("hinge", "slide"):
                    entry["low"], entry["high"] = _two_floats(attributes["range"])
                if joint.get("name"):
                    joints[joint.get("name")] = entry
                nq += _QPOS_WIDTH.get(kind, 1)
                nv += _QVEL_WIDTH.get(kind, 1)

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
                elif joint is not None and joint["low"] is not None and joint["high"] is not None:
                    try:
                        inherit = float(attributes.get("inheritrange", 0.0))
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint["low"] * inherit, joint["high"] * inherit
                        is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else joint["qpos"])

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets

    @classmethod
    def from_xml_path(cls, path):
        return cls(ET.parse(str(path)).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (called before the first step and on every reset)."""
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
    for index, address in enumerate(model._targets):
        if address is None or index >= len(data.ctrl):
            continue
        error = float(data.ctrl[index]) - float(data.qpos[address])
        velocity = error * _SETTLE_FRACTION / dt
        data.qvel[address] = velocity
        data.qpos[address] = float(data.qpos[address]) + velocity * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
