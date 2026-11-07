"""Fake ``mujoco`` module for gh.denisgriaznov/custommujocoenviromentforrl: a pure Python stand-in for the library.

Why a stand-in: the driver is a ``MujocoDriver`` over the card's MJCF model (``assets/ball_balance.xml``), the
bridge imports ``mujoco`` lazily, and MuJoCo is not installed where the acceptance gate runs.  ``backends["fake"]``
names this class; the bridge calls ``MjModel.from_xml_path`` on the model, then ``mj_resetData``/``mj_forward``/
``mj_step`` and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited``, ``data.time``, ``data.qpos``, ``data.qvel`` and ``data.ctrl``.

The model shape comes from the MJCF text itself: the bodies, joints and actuator elements of
``assets/ball_balance.xml`` give the joint dimensions (two hinge joints and one free joint), the actuator count and
the per-actuator control ranges (``ctrlrange="-1 1"`` on both ``general`` actuators, lines 25-27).  The start state is
the model's reference configuration: the free ball starts at its body position (line 18) with an identity quaternion,
and the hinge joints start at zero.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, actuator force or sensor
model, and its integration is a placeholder first-order motion of each actuated hinge plus a placeholder free fall
of the ball.  Every number that is not read from the MJCF is marked ``# placeholder``.  The driver's fidelity
``gaps`` list these omissions.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET

#: The card's model, relative to this package directory (the read-only clone under robots/ at the pinned commit).
MODEL_PATH = "../../../../robots/denisgriaznov/custommujocoenviromentforrl/assets/ball_balance.xml"

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when the model sets no <option timestep>; the model sets none.
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: hinge angle rate per unit of control.
_HINGE_RATE = 0.5
#: placeholder: free-joint fall acceleration.
_GRAVITY = 9.81
#: qpos and qvel widths of a joint type; a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: The control range of an actuator with neither a ctrlrange nor an inherited joint range.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _numbers(text):
    return [float(item) for item in str(text).split()]


def _two_floats(text):
    values = _numbers(text)
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _vec3(text, default):
    if text is None:
        return list(default)
    values = _numbers(text)
    if len(values) != 3:
        raise ValueError(f"expected three numbers, got {text!r}")
    return values


def _vec4(text, default):
    if text is None:
        return list(default)
    values = _numbers(text)
    if len(values) != 4:
        raise ValueError(f"expected four numbers, got {text!r}")
    return values


def _load(path):
    """The MJCF tree of ``path`` (this model has no includes)."""
    return ET.parse(str(path)).getroot()


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: name, type, range and its positions in the data arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high, position=None, quat=None):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high
        self.position = position
        self.quat = quat


def _collect(body, joints, nq, nv):
    """Collect the joints of ``body`` and its child bodies in MuJoCo's qpos/qvel order."""
    position = _vec3(body.get("pos"), (0.0, 0.0, 0.0))
    quat = _vec4(body.get("quat"), (1.0, 0.0, 0.0, 0.0))
    for child in body:
        if child.tag in ("joint", "freejoint"):
            if child.tag == "freejoint":
                kind, low, high = "free", None, None
            else:
                kind = child.get("type", "hinge")
                if child.get("range") is not None:
                    low, high = _two_floats(child.get("range"))
                else:
                    low, high = None, None
            entry = _Joint(child.get("name"), kind, nq, nv, low, high,
                           position if kind == "free" else None,
                           quat if kind == "free" else None)
            joints[entry.name] = entry
            nq += _QPOS.get(kind, 1)
            nv += _QVEL.get(kind, 1)
        elif child.tag == "body":
            nq, nv = _collect(child, joints, nq, nv)
    return nq, nv


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        joints = {}
        nq = nv = 0
        for body in root.findall("worldbody"):
            nq, nv = _collect(body, joints, nq, nv)

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                joint = joints.get(element.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if element.get("ctrlrange") is not None:
                    low, high = _two_floats(element.get("ctrlrange"))
                    is_limited = True
                elif joint is not None and joint.low is not None and joint.high is not None:
                    try:
                        inherit = float(element.get("inheritrange") or 0.0)
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint.low * inherit, joint.high * inherit
                        is_limited = True
                if str(element.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(joint)

        timestep = _DEFAULT_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        qpos0 = [0.0] * nq
        for joint in joints.values():
            if joint.kind == "free":
                qpos0[joint.qpos_adr:joint.qpos_adr + 7] = list(joint.position) + list(joint.quat)
            elif joint.kind == "ball":
                qpos0[joint.qpos_adr:joint.qpos_adr + 4] = [1.0, 0.0, 0.0, 0.0]
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.qpos0 = qpos0
        self._joints = list(joints.values())
        self._actuators = targets

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


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
    """Advance the stand-in one time step: hinge motion toward ctrl and a free-falling ball (placeholder)."""
    dt = float(model.opt.timestep)
    for index, joint in enumerate(model._actuators):
        if joint is None or index >= len(data.ctrl) or joint.kind == "free":
            continue
        value = float(data.ctrl[index])
        rate = _HINGE_RATE * value  # placeholder
        new = float(data.qpos[joint.qpos_adr]) + rate * dt
        if joint.low is not None and new < joint.low:
            new, rate = joint.low, 0.0
        if joint.high is not None and new > joint.high:
            new, rate = joint.high, 0.0
        data.qpos[joint.qpos_adr] = new
        data.qvel[joint.qvel_adr] = rate
    for joint in model._joints:
        if joint.kind != "free":
            continue
        base = joint.qpos_adr
        velocity = joint.qvel_adr
        data.qvel[velocity + 2] -= _GRAVITY * dt  # placeholder
        data.qpos[base] += data.qvel[velocity] * dt
        data.qpos[base + 1] += data.qvel[velocity + 1] * dt
        data.qpos[base + 2] += data.qvel[velocity + 2] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
