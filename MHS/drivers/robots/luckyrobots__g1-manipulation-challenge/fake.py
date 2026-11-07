"""Stand-in ``mujoco`` module for the Lucky Robots G1 pick-and-place package.

Why a stand-in: the driver is a configuration-only ``MujocoDriver`` and its bridge imports ``mujoco`` lazily.
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip), so
``backends["fake"]`` names this class object.  The bridge calls ``MjModel.from_xml_path`` on the card's first model
(``scene.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/
``ctrl`` arrays.

The model shape comes from the MJCF text itself.  ``_load`` parses the scene and expands its ``<include>`` element,
``_Defaults`` resolves the ``<default>`` class chain, ``_layout`` walks the body tree in document order (MuJoCo's
qpos/qvel layout, including the two free joints) and ``_actuators`` takes the control ranges from the actuator
elements plus their default classes.  The robot position actuators are in default class ``g1``, which sets
``inheritrange`` 1 (``g1.xml:9-10``), so their control range is the matching joint range.  The 14 finger actuators
carry no class, no ``ctrlrange`` and no ``inheritrange`` (``g1.xml:435-449``), so MuJoCo compiles them as not
ctrl-limited (``ctrlrange`` 0 0), and so does this stand-in (model review 2026-11-05: the author's stand-in gave
them the matching joint range as an envelope the MJCF does not state).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon, sensor or actuator
constraint, and its integration is a placeholder first-order motion of each actuated joint toward its control target.
It applies no joint limit, no armature or damping, no gravity and no collision; the red cylinder's free joint is
carried in qpos/qvel but never falls or rolls.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.005 s
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included ``<mujoco>`` root."""
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
    """The MJCF tree of ``path`` with its includes expanded, each path relative to the file that names it."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


def _pair(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


class _Defaults:
    """The ``<default>`` classes of a model tree: class inheritance and per-tag attribute defaults."""

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
    """One joint: its name, type, qpos/qvel addresses, range and model default position."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high, qpos0):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high
        self.qpos0 = qpos0


def _body_pose(body):
    """The initial free-joint pose of ``body``: position then quaternion (MJCF quat is w x y z)."""
    position = [float(item) for item in (body.get("pos") or "0 0 0").split()[:3]]
    while len(position) < 3:
        position.append(0.0)
    quat = [float(item) for item in (body.get("quat") or "1 0 0 0").split()[:4]]
    while len(quat) < 4:
        quat.append(0.0)
    return position + quat


def _layout(root, defaults):
    """The joints of the expanded model in document order, with qpos/qvel addresses and model defaults."""
    joints = {}
    qpos = [0]
    qvel = [0]
    qpos0 = []

    def walk(body, inherited_class):
        inherited_class = body.get("childclass") or inherited_class
        for child in body:
            if child.tag == "freejoint":
                name = child.get("name")
                entry = _Joint(name, "free", qpos[0], qvel[0], None, None, _body_pose(body))
                if name:
                    joints[name] = entry
                qpos0.extend(entry.qpos0)
                qpos[0] += _QPOS["free"]
                qvel[0] += _QVEL["free"]
            elif child.tag == "joint":
                attributes = defaults.of(child, "joint", inherited_class)
                kind = attributes.get("type", "hinge")
                name = attributes.get("name")
                low = high = None
                if "range" in attributes and kind in ("hinge", "slide"):
                    low, high = _pair(attributes["range"])
                start = float(attributes.get("ref", 0.0)) if kind in ("hinge", "slide") else \
                    (1.0 if kind == "ball" else 0.0)
                entry = _Joint(name, kind, qpos[0], qvel[0], low, high, start)
                if name:
                    joints[name] = entry
                if kind == "free":
                    qpos0.extend([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
                elif kind == "ball":
                    qpos0.extend([1.0, 0.0, 0.0, 0.0])
                else:
                    qpos0.append(start)
                qpos[0] += _QPOS.get(kind, 1)
                qvel[0] += _QVEL.get(kind, 1)
            elif child.tag in ("body", "frame"):
                walk(child, inherited_class)

    for worldbody in root.findall("worldbody"):
        walk(worldbody, None)
    return joints, qpos[0], qvel[0], qpos0


def _actuators(root, defaults, joints):
    """The ctrlrange, ctrllimited flag and joint of every actuator, in document order."""
    ranges, limited, targets = [], [], []
    for section in root.findall("actuator"):
        for element in section:
            if element.tag == "default":
                continue
            attributes = defaults.of(element, element.tag)
            joint = joints.get(attributes.get("joint"))
            # no control range: MuJoCo compiles ctrlrange 0 0 with ctrllimited false
            low, high = 0.0, 0.0
            is_limited = False
            if "ctrlrange" in attributes:
                low, high = _pair(attributes["ctrlrange"])
                is_limited = True
            elif joint is not None and joint.low is not None and joint.high is not None:
                try:
                    inherit = float(attributes.get("inheritrange", 0.0))
                except (TypeError, ValueError):
                    inherit = 0.0
                if inherit > 0:
                    # a positive fraction of the joint range, centred on that range (inheritrange 1 is
                    # exactly the joint range; use the XML numbers unchanged to avoid float noise)
                    if inherit == 1.0:
                        low, high = joint.low, joint.high
                    else:
                        middle, half = (joint.low + joint.high) / 2.0, (joint.high - joint.low) * inherit / 2.0
                        low, high = middle - half, middle + half
                    is_limited = True
            if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                is_limited = False
            ranges.append([float(low), float(high)])
            limited.append(is_limited)
            targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))
    return ranges, limited, targets


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        defaults = _Defaults(root)
        self._joints, self.nq, self.nv, self.qpos0 = _layout(root, defaults)
        ranges, limited, targets = _actuators(root, defaults, self._joints)
        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.na = 0
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


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
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
    for index, place in enumerate(model._targets):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = place
        target = float(data.ctrl[index])
        current = float(data.qpos[qpos_adr])
        data.qvel[qvel_adr] = (target - current) * _STEP_FRACTION / dt
        data.qpos[qpos_adr] = current + data.qvel[qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
