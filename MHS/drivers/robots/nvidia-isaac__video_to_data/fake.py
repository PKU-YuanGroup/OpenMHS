"""Package-local stand-in for the ``mujoco`` module used by the pinned G1 scene driver.

``MujocoDriver.make_bridge`` builds an ``mhs.bridge.mujoco.MujocoBridge`` with
``mujoco=native``.  The bridge calls ``MjModel.from_xml_path`` on the configured
scene, then ``mj_resetData``/``mj_forward``/``mj_step`` and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.na``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited``, and
``data.time``/``qpos``/``qvel``/``ctrl``/``act``.

MuJoCo is not installed in the gate environment, so this module supplies only
those members.  It parses the same scene and its ``<include>`` for the model
shape: joint dimensions, the default pose ``qpos0``, the option timestep and
the actuator names, kinds and ctrlranges.  It is not MuJoCo: it loads no mesh,
texture or inertia, resolves no contact, friction, tendon, equality or actuator
force constraint, and its step is a placeholder joint update.  The fidelity
gaps in ``driver.py`` disclose those differences.

The served scene is ``planner/assets/mujoco/scene_29dof.xml``: one G1 29dof
robot model plus a floor and a light.  The model states no ``<option>``
timestep, so the stand-in uses MuJoCo's library default (0.002 s) as a
placeholder and ``driver.py`` says so in the fake fidelity gaps.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from pathlib import Path

#: qpos and qvel contributions of one joint type; a missing type means "hinge".
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}

# placeholder: MuJoCo's library default timestep when the model states no <option timestep>; the served scene
# states none, so this is test data, not a model value.
_PLACEHOLDER_TIMESTEP = 0.002
# placeholder: unit inertia of an actuated joint in the stand-in (not the model's inertia).
_PLACEHOLDER_INERTIA = 1.0
# placeholder: velocity damping of a motor-driven joint in the stand-in, per second.
_PLACEHOLDER_DAMPING = 2.0


def _expand_includes(node, base, depth=0):
    """Replace every ``<include file=...>`` below ``node`` with the included children."""
    if depth > 8:
        raise ValueError("the MJCF include nesting exceeds 8 levels")
    children = []
    for child in list(node):
        if child.tag == "include":
            name = str(child.get("file"))
            target = (base / name).resolve()
            if not target.is_file():
                raise FileNotFoundError(f"the MJCF include {name!r} is not below {base}")
            included = ET.parse(str(target)).getroot()
            _expand_includes(included, target.parent, depth + 1)
            children.extend(list(included))
        else:
            _expand_includes(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    model = Path(path).resolve()
    tree = ET.parse(str(model)).getroot()
    _expand_includes(tree, model.parent)
    return tree


def _numbers(text, count, label):
    values = [float(item) for item in str(text).split()]
    if len(values) != count or not all(math.isfinite(value) for value in values):
        raise ValueError(f"the MJCF {label} must hold {count} finite numbers")
    return values


def _body_pose(body):
    """The body's ``pos`` and ``quat`` (wxyz), which MuJoCo's free-joint ``qpos0`` uses."""
    pos = _numbers(body.get("pos", "0 0 0"), 3, "body pos")
    quat = _numbers(body.get("quat", "1 0 0 0"), 4, "body quat")
    return pos, quat


def _walk_joints(body):
    """Yield ``(joint element, owning body)`` depth-first, a body's joints before its child bodies.

    MuJoCo orders ``qpos`` by the body tree: a body's own joints come before the
    joints of its children.  A bare ``<freejoint>`` element is the free joint of
    the body that holds it.
    """
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, body
    for child in body:
        if child.tag == "body":
            yield from _walk_joints(child)


class _Opt:
    """``mujoco.MjOption``: the one member the bridge reads."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree."""

    def __init__(self, root):
        timestep = None
        for option in root.iter("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
                break
        if timestep is None:
            timestep = _PLACEHOLDER_TIMESTEP
        if not math.isfinite(timestep) or timestep <= 0:
            raise ValueError("the MJCF option timestep must be positive and finite")
        self.opt = _Opt(timestep)

        worldbody = root.find("worldbody")
        if worldbody is None:
            raise ValueError("the MJCF scene has no worldbody")
        joints = {}
        qpos = qvel = 0
        #: qpos0 as MuJoCo defines it: a free joint starts at its body's pos and quat, a ball joint at the
        #: identity quaternion, a hinge or slide joint at its ref (0 when the MJCF states none).
        qpos0 = []
        for element, owner in _walk_joints(worldbody):
            kind = "free" if element.tag == "freejoint" else element.get("type", "hinge")
            if kind not in _QPOS_SIZE:
                raise ValueError(f"the MJCF joint type {kind!r} is not supported by the stand-in")
            name = element.get("name")
            if name:
                joints[name] = (qpos, qvel)
            qpos += _QPOS_SIZE[kind]
            qvel += _QVEL_SIZE[kind]
            if kind == "free":
                pos, quat = _body_pose(owner)
                qpos0.extend(pos + quat)
            elif kind == "ball":
                qpos0.extend([1.0, 0.0, 0.0, 0.0])
            else:
                qpos0.append(float(element.get("ref", "0")))
        if len(qpos0) != qpos:
            raise ValueError("the stand-in did not derive one qpos0 entry per joint coordinate")
        self.qpos0 = qpos0

        names, ranges, limited = [], [], []
        qpos_index, qvel_index, gains = [], [], []
        actuator = root.find("actuator")
        for element in list(actuator) if actuator is not None else []:
            if element.tag != "motor":
                # The pinned scene uses force motors only.  Rather than silently misread a different actuator,
                # the stand-in refuses one it does not model.
                raise ValueError(f"the MJCF actuator {element.tag!r} is not a motor; the stand-in models motors")
            name = element.get("name")
            joint = element.get("joint")
            if not joint or joint not in joints:
                raise ValueError(f"the MJCF motor {name!r} names no joint of the model")
            raw = element.get("ctrlrange")
            span = _numbers(raw, 2, f"ctrlrange of motor {name!r}") if raw is not None else None
            is_limited = span is not None and element.get("ctrllimited", "true").lower() not in ("false", "0")
            if span is not None and span[0] > span[1]:
                raise ValueError(f"the MJCF ctrlrange of motor {name!r} is inverted")
            names.append(name)
            ranges.append(span if span is not None else [0.0, 0.0])
            limited.append(bool(is_limited))
            qpos_at, qvel_at = joints[joint]
            qpos_index.append(qpos_at)
            qvel_index.append(qvel_at)
            gains.append(float(element.get("gear", "1")))
        self.nq, self.nv = qpos, qvel
        self.na = 0
        self.nu = len(names)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: the stand-in's own actuator-to-joint map (not a public MuJoCo member)
        self._actuator_names = names
        self._actuator_qpos = qpos_index
        self._actuator_qvel = qvel_index
        self._actuator_gear = gains

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand_includes(root, Path.cwd())
        return cls(root)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Restore the model defaults: qpos0, zero velocities and controls, time zero."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward or contact quantities."""


def mj_step(model, data):
    """Advance the placeholder one step: each motor's force accelerates its own joint (placeholder).

    A motor's force is gear * ctrl; it acts on a placeholder unit inertia and
    the driven joint loses velocity through a placeholder damping.  The free
    base, gravity, contacts, joint limits and every coupling between joints are
    not integrated.
    """
    dt = float(model.opt.timestep)
    for index, control in enumerate(data.ctrl):
        qpos = model._actuator_qpos[index]
        qvel = model._actuator_qvel[index]
        gear = model._actuator_gear[index]
        velocity = float(data.qvel[qvel])
        acceleration = gear * float(control) / _PLACEHOLDER_INERTIA - _PLACEHOLDER_DAMPING * velocity
        data.qvel[qvel] = velocity + acceleration * dt
        data.qpos[qpos] = float(data.qpos[qpos]) + data.qvel[qvel] * dt
    data.time = float(data.time) + dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object named by ``backends["fake"]``."""

    __version__ = "video_to_data-fake-mujoco-stand-in"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
