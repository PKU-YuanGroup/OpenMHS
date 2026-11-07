"""Fake backend of the go_bdx scene package: a pure Python stand-in for the ``mujoco`` library.

The driver is configuration only (a ``MujocoDriver``).  Its bridge imports ``mujoco`` lazily, and MuJoCo is neither
installed nor installable where the acceptance gate runs.  ``backends["fake"]`` therefore names this module object;
the bridge calls ``MjModel.from_xml_path`` on the card's first model (``go_bdx/scene.xml``), then
``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``,
``model.nu``, ``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl``/``act`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the scene and expands its ``<include>``
element, and ``MjModel`` takes the joint dimensions, the actuator list and the per-actuator control ranges from
that tree.  The scene includes ``go_bdx.xml``, which declares one freejoint and 16 hinge joints; every actuator
element is a ``<position>`` with an explicit ``ctrlrange`` (``go_bdx.xml:163-179``), so the stand-in reports one
bounded control interval per actuator.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor, and its
integration is a placeholder first-order motion of each actuated hinge toward its control value, not MuJoCo's
physics.  The freejoint is not integrated, so the floating base never moves.  All of that is listed in the
driver's fidelity ``gaps``.  All numbers below are placeholders or test data, not device facts.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets none.
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint.
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control interval of an actuator with no ctrlrange.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


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
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


def _pair(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint and its qpos/qvel addresses in the flat data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr


def _walk_joints(body, inherited_type=None):
    """Yield ``(joint element, kind)`` for every joint below ``body`` in document order."""
    for child in body:
        if child.tag == "freejoint":
            yield child, "free"
        elif child.tag == "joint":
            yield child, child.get("type") or inherited_type or "hinge"
        elif child.tag == "body":
            yield from _walk_joints(child, inherited_type)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        joints = {}
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for joint, kind in _walk_joints(worldbody):
                entry = _Joint(joint.get("name"), kind, nq, nv)
                if entry.name is not None:
                    joints[entry.name] = entry
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                joint = joints.get(element.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if element.get("ctrlrange") is not None:
                    low, high = _pair(element.get("ctrlrange"))
                    is_limited = True
                if str(element.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                #: A position actuator moves its joint's qpos/qvel entries; the free joint makes them diverge.
                targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._joints = joints

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


def mj_resetData(model, data):
    """Reset the data arrays; the zero qpos is a placeholder, not MuJoCo's model qpos0."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated hinge moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, addresses in enumerate(model._targets):
        if addresses is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = addresses
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
