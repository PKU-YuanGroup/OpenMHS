"""Pure Python stand-in for the ``mujoco`` library used by the fake backend.

The driver is a configuration-only ``MujocoDriver``.  Its bridge imports ``mujoco`` lazily, and MuJoCo is neither
installed nor installable where the acceptance gate runs.  ``backends["fake"]`` therefore names this module object;
the bridge calls ``MjModel.from_xml_path`` on the pinned MJCF
(``piper_description/mujoco_model/piper_description.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on it,
and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the XML, ``MjModel`` walks the nested bodies for
the joint dimensions and the actuator list, and takes the per-actuator control interval from an explicit
``ctrlrange`` (this model sets one on every actuator).  The XML has no ``<default>`` classes, ``<include>`` files or
``<option timestep>``, so the parser stays on that subset and reports the library-default timestep.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor, and its
integration is a placeholder first-order motion of each actuated joint toward its control value, not MuJoCo's
physics or the model's position servo.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks
to a device.
"""

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max
# placeholder: MuJoCo's library default when a model sets no <option timestep>; the pinned model sets none.
_TIMESTEP_S = 0.002
# placeholder: fraction of the remaining distance that one fake step moves an actuated joint.
_STEP_FRACTION = 0.05
#: qpos and qvel contributions of a joint type.
_DIMS = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}
#: The control interval of an actuator with no explicit ctrlrange.
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _pair(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _walk_joints(body):
    """Yield every joint element below ``body``; the pinned MJCF nests them inside <body>."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child
        elif child.tag == "body":
            yield from _walk_joints(child)


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint: its qpos/qvel addresses and its range, if the MJCF states one."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the pinned MJCF tree."""

    def __init__(self, root):
        joints = {}
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for element in _walk_joints(worldbody):
                if element.tag == "freejoint":
                    kind = "free"
                else:
                    kind = element.get("type", "hinge")
                if kind not in _DIMS:
                    raise ValueError(f"unsupported joint type {kind!r} in the stand-in")
                low = high = None
                if kind in ("hinge", "slide") and element.get("range"):
                    low, high = _pair(element.get("range"))
                joint = _Joint(element.get("name"), kind, nq, nv, low, high)
                joints[joint.name] = joint
                nq += _DIMS[kind][0]
                nv += _DIMS[kind][1]

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                joint = joints.get(element.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if element.get("ctrlrange"):
                    low, high = _pair(element.get("ctrlrange"))
                    is_limited = True
                if str(element.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else (joint.qpos_adr, joint.qvel_adr))

        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.name = root.get("model")
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._joints = joints

    @classmethod
    def from_xml_path(cls, path):
        return cls(ET.parse(str(path)).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset).

    placeholder: MuJoCo derives qpos0 from the model; this stand-in uses zeros for every joint.
    """
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, addresses in enumerate(model._targets):
        if addresses is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = addresses
        target = float(data.ctrl[index])
        current = float(data.qpos[qpos_adr])
        velocity = (target - current) * _STEP_FRACTION / dt
        data.qvel[qvel_adr] = velocity
        data.qpos[qpos_adr] = current + velocity * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    __version__ = "fake-mujoco-standin"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
