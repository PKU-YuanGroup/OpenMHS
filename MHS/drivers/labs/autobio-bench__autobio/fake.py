"""Stand-in ``mujoco`` module for the AutoBio DexHand021 package: a pure Python fake of the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
therefore names this class object; the bridge calls ``MjModel.from_xml_path`` on the card's model
(``autobio/model/hand/dexhand021_right.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the file and expands any ``<include>`` elements,
and ``_Model`` takes the joint dimensions, the actuator count, the explicit per-actuator ``ctrlrange`` values and the
option timestep from that tree.  The model sets its own 0.01 s step (model:5), so no library default is used for it.

What this is not: MuJoCo.  It loads no STL mesh or texture, resolves no contact, equality, tendon or actuator
constraint, and its integration is a placeholder first-order motion of each directly actuated joint toward its
control target.  The five tendon actuators move no joint in the stand-in.  All of that is listed in the driver's
fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.01 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves a position-actuated joint
_STEP_FRACTION = 0.05
#: placeholder: velocity (rad/s) the stand-in assigns per unit of a non-position control value
_CTRL_TO_VELOCITY = 0.05
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


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _walk_joints(body):
    """Yield the joint elements below a body in document order (including a freejoint)."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child
        elif child.tag in ("body", "frame"):
            yield from _walk_joints(child)


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
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
                # placeholder: the stand-in starts every joint at zero and ignores any MJCF keyframe or qpos0
                qpos0.extend([0.0] * _QPOS[kind])
                qvel0.extend([0.0] * _QVEL[kind])
                count += 1

        ranges, limited, targets, kinds = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                control_range = element.get("ctrlrange")
                if control_range is not None:
                    low, high = _two_floats(control_range)
                    is_limited = str(element.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(joint_place.get(element.get("joint")))
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
    """Advance the stand-in one step: a placeholder motion of each directly actuated joint."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model._targets):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_index, qvel_index = place
        target = float(data.ctrl[index])
        current = float(data.qpos[qpos_index])
        if model._kinds[index] == "position":
            data.qpos[qpos_index] = current + (target - current) * _STEP_FRACTION
            data.qvel[qvel_index] = (data.qpos[qpos_index] - current) / dt
        elif model._kinds[index] == "velocity":
            data.qvel[qvel_index] = target
            data.qpos[qpos_index] = current + target * dt
        else:
            data.qvel[qvel_index] = target * _CTRL_TO_VELOCITY
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
