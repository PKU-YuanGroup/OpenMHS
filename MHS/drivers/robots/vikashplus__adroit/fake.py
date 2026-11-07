"""Stand-in ``mujoco`` module for the Adroit MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` when the
model is first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no
network, no pip).  ``backends["fake"]`` is therefore this module object: the bridge calls
``MjModel.from_xml_path`` on the card's ``models[0]`` (``Adroit_hand.xml``), then
``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``, ``model.nq``,
``model.nv``, ``model.nu``, ``model.actuator_ctrlrange`` and ``data.time``/``qpos``/``qvel``/``ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands
its ``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the joint
dimensions, the actuator control ranges and the option time step from that tree.  The scene includes
``resources/assets.xml`` (compiler, option, defaults, tendons, sensors) and
``resources/joint_position_actuation.xml`` (the position actuators).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality or tendon constraint, and
its integration is a placeholder motion of each actuated hinge toward its control value, not the engine's
dynamics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.002 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated hinge
_STEP_FRACTION = 0.25
#: placeholder: qpos and qvel contributions of a joint type; a missing type means a hinge
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: placeholder: identity quaternion component of a free joint in the stand-in's reset state
_FREE_QUAT_W = 1.0


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


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


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
                    self._parent.setdefault(name, parent)
                self._walk(child, name)
            elif parent is not None:
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

    def get(self, class_name, tag):
        """The merged defaults of ``tag`` for a class, following the class chain from the global defaults down."""
        out = {}
        for name in self._chain(class_name):
            out.update(self._attributes.get(name, {}).get(tag, {}))
        return out

    def of(self, element, tag, inherited_class=None):
        """The defaults of ``element``'s effective class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class") or inherited_class, tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its kind, its qpos/qvel addresses and its range when it has one."""

    def __init__(self, kind, qpos_adr, qvel_adr, low=None, high=None):
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


def _walk_body(body, inherited_class):
    """Yield ``(joint element, effective default class)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass
        elif child.tag == "body":
            yield from _walk_body(child, childclass)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        free_qpos = []
        qpos = qvel = 0
        for body in root.findall("worldbody"):
            for joint, inherited_class in _walk_body(body, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                low = high = None
                if "range" in attributes and kind in ("hinge", "slide"):
                    low, high = _two_floats(attributes["range"])
                entry = _Joint(kind, qpos, qvel, low, high)
                joints[joint.get("name")] = entry
                if kind == "free":
                    free_qpos.append(entry.qpos_adr)
                qpos += _QPOS.get(kind, 1)
                qvel += _QVEL.get(kind, 1)

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                joint = joints.get(attributes.get("joint"))
                low, high = -_FLOAT_MAX, _FLOAT_MAX
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _two_floats(attributes["ctrlrange"])
                    is_limited = True
                elif joint is not None and joint.low is not None and joint.high is not None:
                    try:
                        inherit = float(attributes.get("inheritrange", 0.0))
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint.low * inherit, joint.high * inherit
                        is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._free_qpos = free_qpos

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
        _initial_state(model, self)


def _initial_state(model, data):
    """Set the stand-in's reset state; a free joint gets the identity orientation (placeholder)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0
    for adr in model._free_qpos:
        if adr + 3 < len(data.qpos):
            data.qpos[adr + 3] = _FREE_QUAT_W


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    _initial_state(model, data)


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated hinge moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, target in enumerate(model._targets):
        if target is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = target
        current = float(data.qpos[qpos_adr])
        ctrl = float(data.ctrl[index])
        new = current + (ctrl - current) * _STEP_FRACTION
        data.qpos[qpos_adr] = new
        data.qvel[qvel_adr] = (new - current) / dt if dt > 0 else 0.0
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
