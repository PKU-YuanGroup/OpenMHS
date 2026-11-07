"""Fake ``mujoco`` module for the EBiM Benchmark Task 1 package: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs.  ``backends["fake"]`` therefore names this
module object; the bridge calls ``MjModel.from_xml_path`` on the card's first model
(``task1_mujoco/robotiq_duo_full_scene_minimal_core/duo_full_scene_grasp.xml``), then ``mj_resetData``/``mj_forward``/
``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``,
``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the scene and expands its ``<include>`` elements,
and ``MjModel`` counts the explicitly declared joints and actuators and takes each actuator's control range from its
own ``ctrlrange`` attribute.  The time step is the scene's ``<option timestep>``.  The scene's ``<composite
type="cable">`` is counted but not expanded: MuJoCo generates its bodies and joints at compile time, while this
stand-in has no compiler, so the fake's qpos/qvel cover only the explicitly declared joints and are smaller than the
real model's.  That difference is listed in the driver's fidelity ``gaps``.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or actuator gain, and it
does not run the ``mujoco.elasticity.cable`` plugin.  Its integration is a placeholder motion: a velocity actuator
sets its joint velocity to the control value, and a position actuator moves its joint a fixed fraction of the way
toward the control value per step.  Every constant below that is not read from the model is marked ``# placeholder``.
Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this scene sets one, so it is unused.
_TIMESTEP_DEFAULT_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves a position actuator's joint.
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of each joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control range of an actuator with no ctrlrange.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included ``<mujoco>`` root."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    index = 0
    while index < len(node):
        child = node[index]
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, depth + 1)
            node.remove(child)
            for offset, item in enumerate(list(included)):
                node.insert(index + offset, item)
            index += len(included)
        else:
            _expand(child, base, depth)
            index += 1


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded, each path relative to the file that names it."""
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One explicit joint of the scene: its type and its ``qpos`` address (all joints here have one dof)."""

    def __init__(self, name, kind, qpos_adr):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr


def _walk_body(body):
    """Yield every explicit joint element below ``body`` (the composite template is not a declared joint)."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child
        elif child.tag == "body":
            yield from _walk_body(child)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        joints = {}
        nq = nv = 0
        for body in root.findall("worldbody"):
            for element in _walk_body(body):
                if element.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = element.attrib
                    kind = attributes.get("type", "hinge")
                name = element.get("name")
                entry = _Joint(name, kind, nq)
                if name is not None:
                    joints[name] = entry
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        ranges, limited, targets, kinds = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                kind = element.tag
                low, high = _UNBOUNDED
                is_limited = False
                if element.get("ctrlrange") is not None:
                    low, high = _two_floats(element.get("ctrlrange"))
                    is_limited = True
                if str(element.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                joint = joints.get(element.get("joint"))
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else joint.qpos_adr)
                kinds.append(kind)

        timestep = _TIMESTEP_DEFAULT_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        segments = 0
        for body in root.findall("worldbody"):
            for composite in body.iter("composite"):
                if composite.get("count"):
                    counts = [int(item) for item in composite.get("count").split()]
                    if counts and counts[0] > 0:
                        segments += counts[0]
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.composite_segments = segments
        self._targets = targets
        self._kinds = kinds
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
    """Reset the data arrays to zero.

    placeholder: MuJoCo resets to the model's ``qpos0`` defaults; this stand-in does not resolve them and zeroes
    every array.
    """
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step (placeholder motion, not MuJoCo's physics)."""
    dt = float(model.opt.timestep)
    for index, adr in enumerate(model._targets):
        if adr is None or index >= len(data.ctrl) or adr >= len(data.qpos):
            continue
        target = float(data.ctrl[index])
        if model._kinds[index] == "velocity":
            data.qvel[adr] = target
            data.qpos[adr] = float(data.qpos[adr]) + target * dt
        else:
            delta = target - float(data.qpos[adr])
            data.qvel[adr] = delta * _STEP_FRACTION / dt
            data.qpos[adr] = float(data.qpos[adr]) + delta * _STEP_FRACTION
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
