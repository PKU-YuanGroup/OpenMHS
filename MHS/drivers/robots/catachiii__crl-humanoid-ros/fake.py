"""Stand-in ``mujoco`` module for the CRL Humanoid G1 package.

The driver is a ``MujocoDriver`` and configuration only.  Its bridge imports ``mujoco`` lazily and calls
``MjModel.from_xml_path`` on the card's G1 scene, then ``mj_resetData`` / ``mj_forward`` / ``mj_step`` and
reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time`` / ``qpos`` / ``qvel`` / ``ctrl`` arrays.  MuJoCo is
not installed and cannot be installed where the acceptance gate runs (no network, no pip), so this module
supplies exactly those members.

The model shape is read from the MJCF text itself: every ``<include>`` is expanded, the MJCF ``<default>``
classes are resolved, and the free base, the hinge joints, the actuators and the option timestep come from
the card's scene rather than from constants in this file.  The G1 model declares 29 motor actuators but no
``ctrlrange``, so the derived control envelope is intentionally absent.

What this is not: MuJoCo.  It loads no STL mesh or texture, resolves no inertia, gravity, contact, friction,
equality or tendon constraint, and its step is a placeholder torque response of each actuated hinge, not
MuJoCo's physics.  Those differences are listed in the driver's fidelity ``gaps``.  Nothing here talks to a
device.  All numbers used for the placeholder motion are test data and are marked ``# placeholder``.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; the G1 scene sets none
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves a position actuator
_STEP_FRACTION = 0.05
#: placeholder: scale from a fake motor control value to joint acceleration
_TORQUE_SCALE = 10.0
#: qpos and qvel contributions of a joint type; a missing type means "hinge"
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, model_dir, depth=0):
    """Replace every ``<include file=...>`` below ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            name = str(child.get("file"))
            target = base / name
            if not target.is_file():
                target = model_dir / name
            if not target.is_file():
                raise FileNotFoundError(f"the MJCF include {name!r} is not below {base} or {model_dir}")
            included = ET.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, model_dir, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, model_dir, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded (both MJCF include path conventions are tried)."""
    model = Path(path).resolve()
    tree = ET.parse(str(model)).getroot()
    _expand(tree, model.parent, model.parent)
    return tree


class _Defaults:
    """The MJCF ``<default>`` classes of a model: class inheritance and the per-tag attribute defaults."""

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


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _floats(text, count):
    values = [float(item) for item in str(text).split()]
    if len(values) < count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return values[:count]


def _walk_joints(body):
    """Yield ``(joint_element, owning_body)`` below a body in document order (including a freejoint)."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, body
        elif child.tag in ("body", "frame", "replicate"):
            yield from _walk_joints(child)


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        qpos0 = []
        qvel0 = []
        joint_place = {}
        joint_limits = {}
        count = 0
        for body in root.findall("worldbody"):
            for joint, owner in _walk_joints(body):
                kind = "free" if joint.tag == "freejoint" else defaults.of(joint, "joint").get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = joint.get("name")
                if name:
                    joint_place[name] = (len(qpos0), len(qvel0))
                if kind == "free":
                    # MuJoCo's free-joint qpos0 is the owning body's initial position and quaternion.
                    qpos0.extend(_floats(owner.get("pos", "0 0 0"), 3))
                    qpos0.extend(_floats(owner.get("quat", "1 0 0 0"), 4))
                else:
                    qpos0.extend([0.0] * _QPOS[kind])
                    attributes = defaults.of(joint, "joint")
                    if "range" in attributes and str(attributes.get("limited", "true")).lower() not in ("false", "0"):
                        joint_limits[len(qpos0) - 1] = _two_floats(attributes["range"])
                qvel0.extend([0.0] * _QVEL[kind])
                count += 1

        ranges, limited, targets, kinds = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                if "ctrlrange" in attributes:
                    low, high = _two_floats(attributes["ctrlrange"])
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(joint_place.get(attributes.get("joint")))
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
        self._kinds = kinds
        self._joint_limits = joint_limits

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd(), Path.cwd())
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
    """Placeholder: the stand-in derives no forward kinematics or dynamics quantities."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: a placeholder response of each actuated joint."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model._targets):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_index, qvel_index = place
        control = float(data.ctrl[index])
        current = float(data.qpos[qpos_index])
        if model._kinds[index] == "position":
            data.qpos[qpos_index] = current + (control - current) * _STEP_FRACTION
            data.qvel[qvel_index] = (data.qpos[qpos_index] - current) / dt
        elif model._kinds[index] == "velocity":
            data.qvel[qvel_index] = control
            data.qpos[qpos_index] = current + control * dt
        else:
            data.qvel[qvel_index] = float(data.qvel[qvel_index]) + control * dt * _TORQUE_SCALE
            data.qpos[qpos_index] = current + float(data.qvel[qvel_index]) * dt
        limit = model._joint_limits.get(qpos_index)
        if limit is not None:
            low, high = limit
            if data.qpos[qpos_index] < low:
                data.qpos[qpos_index] = low
                data.qvel[qvel_index] = 0.0
            elif data.qpos[qpos_index] > high:
                data.qpos[qpos_index] = high
                data.qvel[qvel_index] = 0.0
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
