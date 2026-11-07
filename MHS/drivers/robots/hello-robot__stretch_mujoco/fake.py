"""Stand-in ``mujoco`` module for the Hello Robot Stretch MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` when the model
is first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's model
(``models[0]``, ``stretch_mujoco/models/scene.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and
reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and ``data.time``/``qpos``/``qvel``/``ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands its
``<include>`` elements (the scene includes ``stretch.xml`` and ``docking_station.xml``, scene.xml:2-3), ``_Defaults``
resolves the MJCF default classes, and ``_Model`` takes the actuator control ranges, the joint dimensions and the
option time step from that tree.  The robot model's actuator block is ``stretch.xml:524-535`` (two velocity and eight
position actuators); the control ranges are the defaults at ``stretch.xml:16-62``; the fixed tendon ``extend`` joins
the four arm slides (``stretch.xml:507-514``) and is the target of the ``arm`` actuator.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality or tendon constraint, and its
integration is a placeholder motion of each actuated joint toward its control value, not the engine's dynamics.  All
of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model states no <option timestep>; stretch.xml:7-9 states none
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of a position error per second that the stand-in turns into joint velocity
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

    def chain(self, class_name):
        """The default classes from the root down to ``class_name``."""
        chain, name = [], class_name
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        return list(reversed(chain))

    def get(self, class_name, tag):
        """The attributes of ``tag`` in a default class, following the class chain."""
        out = {}
        for name in self.chain(class_name):
            out.update(self._attributes[name].get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out

    def actuator(self, element):
        """The attributes of an actuator element.

        MuJoCo expands the actuator shortcuts (``motor``, ``position``, ``velocity`` ...) to general actuators, so
        the ``<general>`` defaults of the class also reach a ``<position>`` or ``<velocity>`` element.  The robot
        model relies on that: the ``lift`` class states its ctrlrange on ``<general>`` (stretch.xml:20-23) while the
        actuator element is ``<position ... class="lift"/>`` (stretch.xml:527).
        """
        out = self.get(element.get("class"), "general")
        out.update(self.get(element.get("class"), element.tag))
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
        free_slots = []
        qpos = qvel = count = 0
        for worldbody in root.findall("worldbody"):
            for element in worldbody.iter():
                if element.tag == "freejoint":
                    free_slots.append(qpos)
                    qpos += _QPOS["free"]
                    qvel += _QVEL["free"]
                    count += 1
                elif element.tag == "joint":
                    kind = defaults.of(element, "joint").get("type", "hinge")
                    if kind not in _QPOS:
                        raise ValueError(f"unsupported joint type {kind!r}")
                    name = element.get("name")
                    if name:
                        joint_place[name] = (qpos, qvel)
                    qpos += _QPOS[kind]
                    qvel += _QVEL[kind]
                    count += 1

        tendons = {}
        for section in root.findall("tendon"):
            for fixed in section.iter("fixed"):
                name = fixed.get("name")
                if name:
                    tendons[name] = [joint.get("joint") for joint in fixed.findall("joint")]

        ranges, limited, places, kinds = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.actuator(element)
                control_range = attributes.get("ctrlrange")
                if control_range is not None:
                    low, high = (float(value) for value in control_range.split()[:2])
                    is_limited = str(attributes.get("ctrllimited", "auto")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                targets = []
                if attributes.get("joint") is not None:
                    target = joint_place.get(attributes["joint"])
                    if target is not None:
                        targets.append(target)
                elif attributes.get("tendon") is not None:
                    for name in tendons.get(attributes["tendon"], []):
                        target = joint_place.get(name)
                        if target is not None:
                            targets.append(target)
                ranges.append([low, high])
                limited.append(is_limited)
                places.append(targets)
                kinds.append(element.tag)

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
        #: the (qpos, qvel) slots each actuator drives; several for a tendon actuator
        self.actuator_joints = places
        self.actuator_kind = kinds
        #: the qpos offset of every free joint, whose quaternion starts at the identity
        self.free_qpos = free_slots

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


def _identity_qpos(model):
    """A zero qpos with the identity quaternion at every free joint."""
    values = [0.0] * model.nq
    for offset in model.free_qpos:
        values[offset + 3] = 1.0
    return values


class _Data:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = _identity_qpos(model)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = _identity_qpos(model)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step with a placeholder motion (not MuJoCo's integration)."""
    dt = float(model.opt.timestep)
    for index, targets in enumerate(model.actuator_joints):
        if not targets:
            continue
        target = float(data.ctrl[index])
        if model.actuator_kind[index] == "velocity":
            for qpos_index, qvel_index in targets:
                data.qvel[qvel_index] = target
                data.qpos[qpos_index] += target * dt
        else:
            # a fixed tendon couples its joints: split the control target over them, then relax toward it
            share = target / len(targets)
            for qpos_index, qvel_index in targets:
                data.qvel[qvel_index] = (share - data.qpos[qpos_index]) * _CTRL_TO_VELOCITY
                data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The fake backend: the ``mujoco`` module members the bridge calls, derived from the served MJCF."""

    MjModel = _Model
    MjData = _Data
    mj_resetData = staticmethod(mj_resetData)
    mj_forward = staticmethod(mj_forward)
    mj_step = staticmethod(mj_step)
