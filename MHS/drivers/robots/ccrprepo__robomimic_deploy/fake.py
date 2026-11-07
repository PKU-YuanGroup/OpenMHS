"""Stand-in ``mujoco`` module for the RoboMimic Deploy G1 MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` when the model
is first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore this module's ``fake_mujoco`` factory: the bridge calls ``MjModel.from_xml_path``
on the card's scene, then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and ``data.time``/``qpos``/``qvel``/
``ctrl``.  These are the members the upstream loop uses too: it builds ``MjModel.from_xml_path`` and ``MjData``,
reads ``m.nu`` and ``m.opt.timestep``, writes ``d.ctrl`` and calls ``mujoco.mj_step(m, d)``
(deploy_mujoco/deploy_mujoco.py:33-37, :80-82).

The model shape is read from the MJCF text, not hard-coded here: ``_load`` parses the scene and expands its
``<include>`` element, and ``_Model`` takes the joint dimensions, the actuator list, any actuator ``ctrlrange`` and
the option time step from that tree.  The scene includes ``g1_29dof_rev_1_0.xml`` (g1_description/scene.xml:2); the
robot file sets the step to 0.002 s (g1_description/g1_29dof_rev_1_0.xml:8), declares one free joint (:52) and 29
``<motor>`` actuators (:246-274), none with a ``ctrlrange``.

What this is not: MuJoCo.  It loads no STL mesh or texture, resolves no contact, equality, tendon or actuator
constraint, applies none of the joint damping, armature or frictionloss defaults, leaves the free base fixed, and
its integration is a placeholder motion of each actuated joint driven by its control value, not the engine's
dynamics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import types
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.002 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: velocity (rad/s) the stand-in assigns to a joint per unit of its control value
_CTRL_TO_VELOCITY = 0.05
#: qpos and qvel contributions of a joint type
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


def _numbers(text, count):
    values = [float(value) for value in str(text).split()]
    if len(values) < count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return values[:count]


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Model:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        qpos0 = []
        qvel0 = []
        joint_place = {}
        count = 0
        for section in root.findall("worldbody"):
            for body in section.iter("body"):
                for joint in body.findall("joint"):
                    kind = joint.get("type", "hinge")
                    if kind not in _QPOS:
                        raise ValueError(f"unsupported joint type {kind!r}")
                    name = joint.get("name")
                    if name:
                        joint_place[name] = (len(qpos0), len(qvel0))
                    if kind == "free":
                        # placeholder: the stand-in takes the body's initial pose as the free joint's qpos0
                        position = _numbers(body.get("pos", "0 0 0"), 3)
                        orientation = _numbers(body.get("quat", "1 0 0 0"), 4)
                        qpos0.extend(position)
                        qpos0.extend(orientation)
                        qvel0.extend([0.0] * 6)
                    else:
                        qpos0.extend([0.0] * _QPOS[kind])
                        qvel0.extend([0.0] * _QVEL[kind])
                    count += 1

        ranges, limited, places = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                control_range = element.get("ctrlrange")
                if control_range is not None:
                    low, high = _numbers(control_range, 2)
                    is_limited = str(element.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                places.append(joint_place.get(element.get("joint")))

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
        #: the qpos/qvel slot of each actuator's joint; no MuJoCo transmission is modelled
        self.actuator_joint = places

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


class _Data:
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
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint moves by ``ctrl * _CTRL_TO_VELOCITY`` (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        data.qvel[qvel_index] = data.ctrl[index] * _CTRL_TO_VELOCITY
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


def fake_mujoco(**_options):
    """The backend factory: an object with the ``mujoco`` module members the bridge and the upstream loop use."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
    )
