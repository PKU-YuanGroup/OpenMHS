"""Stand-in ``mujoco`` module for gh.simple-robotics/simple: a pure Python fake of the library.

Why a stand-in: the package is a configuration-only ``MujocoDriver``; the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  The upstream
``sandbox/humanoid_mj.py:115-116`` runs the card's model through ``runMujocoXML`` when ``--mujoco`` is given, and
``sandbox/sim_utils.py:253-279`` loads the same XML with ``mujoco.MjModel.from_xml_path`` and steps it with
``mujoco.mj_step``.  ``backends["fake"]`` therefore names this class object, whose attributes mimic that module:
``MjModel.from_xml_path``, ``MjData``, ``mj_resetData``, ``mj_forward`` and ``mj_step``.

The model shape comes from the MJCF text itself: ``_load`` parses the file and expands ``<include>`` elements, and
``MjModel`` resolves the top-level ``<default>`` class chain for the actuators, so the inherited
``<motor ctrlrange="-1 1" ctrllimited="true"/>`` (``sandbox/robots/humanoid.xml:36``) becomes the control envelope.
It reads the joint dimensions, the actuator count and the ``<option timestep>`` from the same tree; no library
default is used for a value the model states.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, tendon, joint-limit or actuator-force
constraint, and its integration is a placeholder first-order motion of each directly actuated joint.  The free base
is not integrated, so the stand-in does not fall or balance.  All of that is listed in the driver's fidelity
``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: the bridge's sentinel for an actuator without a usable ctrlrange
_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model states no <option timestep>; this model states 0.005 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the remaining distance one fake position-servo step moves
_STEP_FRACTION = 0.05
#: placeholder: velocity (rad/s) the stand-in assigns per unit of a non-position control value
_CTRL_TO_VELOCITY = 0.05
#: placeholder: velocity gain (rad/s per unit control and unit gear) of the stand-in's motor model
_TORQUE_GAIN = 0.05

#: qpos and qvel contributions of a joint type; a missing type means "hinge" (MuJoCo joint dimensions).
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


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _first_float(text):
    values = [float(item) for item in str(text).split()]
    if not values:
        raise ValueError(f"expected a number, got {text!r}")
    return values[0]


def _walk_joints(body):
    """Yield the joint elements below a body in document order (including a freejoint)."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child
        elif child.tag in ("body", "frame"):
            yield from _walk_joints(child)


def _default_classes(root):
    """Map a default class name (``None`` is the top-level default) to its parent and element attributes."""
    top = next((child for child in root if child.tag == "default"), None)
    if top is None:
        return {None: (None, {})}
    classes = {None: (None, {child.tag: dict(child.attrib) for child in top if child.tag != "default"})}

    def walk(node, parent):
        for child in node:
            if child.tag != "default":
                continue
            name = child.get("class")
            if not name:
                continue
            classes[name] = (parent, {item.tag: dict(item.attrib) for item in child if item.tag != "default"})
            walk(child, name)

    walk(top, None)
    return classes


def _resolve_default(classes, class_name, tag):
    """Merge the top-level default and a class chain for one element kind (MuJoCo default inheritance)."""
    chain = []
    name = class_name
    while name is not None:
        chain.append(name)
        name = classes.get(name, (None, {}))[0]
    attributes = dict(classes.get(None, (None, {}))[1].get(tag, {}))
    for name in reversed(chain):
        attributes.update(classes.get(name, (None, {}))[1].get(tag, {}))
    return attributes


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        classes = _default_classes(root)
        qpos0 = []
        qvel0 = []
        joint_place = {}
        count = 0
        body = root.find("worldbody")
        if body is not None:
            for joint in _walk_joints(body):
                kind = "free" if joint.tag == "freejoint" else joint.get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = joint.get("name")
                if name:
                    joint_place[name] = (len(qpos0), len(qvel0))
                if kind == "free":
                    # placeholder: the stand-in's free-joint start pose; the model file states no qpos0
                    qpos0.extend([0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
                else:
                    qpos0.extend([0.0] * _QPOS[kind])
                qvel0.extend([0.0] * _QVEL[kind])
                count += 1

        ranges, limited, targets, gears, kinds = [], [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = _resolve_default(classes, element.get("class"), element.tag)
                attributes.update(element.attrib)
                control_range = attributes.get("ctrlrange")
                if control_range is not None:
                    low, high = _two_floats(control_range)
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(joint_place.get(attributes.get("joint")))
                gears.append(_first_float(attributes.get("gear", "1")))
                kinds.append(element.tag)

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = len(qpos0), len(qvel0), 0
        self.njnt = count
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.qpos0 = qpos0
        self.qvel0 = qvel0
        self._targets = targets
        self._gears = gears
        self._kinds = kinds

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
        self.qvel = list(model.qvel0)
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = list(model.qvel0)
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step with a placeholder motion of each directly actuated joint."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model._targets):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_index, qvel_index = place
        control = float(data.ctrl[index])
        kind = model._kinds[index]
        current = float(data.qpos[qpos_index])
        if kind == "position":
            data.qpos[qpos_index] = current + (control - current) * _STEP_FRACTION
            data.qvel[qvel_index] = (data.qpos[qpos_index] - current) / dt
        elif kind == "velocity":
            data.qvel[qvel_index] = control
            data.qpos[qpos_index] = current + control * dt
        elif kind == "motor":
            data.qvel[qvel_index] += model._gears[index] * control * _TORQUE_GAIN * dt
            data.qpos[qpos_index] = current + data.qvel[qvel_index] * dt
        else:
            data.qvel[qvel_index] = control * _CTRL_TO_VELOCITY
            data.qpos[qpos_index] = current + data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
