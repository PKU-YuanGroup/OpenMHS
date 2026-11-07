"""Fake ``mujoco`` module for the muble gripper package: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``) and the bridge imports ``mujoco`` lazily;
MuJoCo is neither installed nor installable where the acceptance gate runs, so ``backends["fake"]`` names this module
object.  The bridge then calls ``MjModel.from_xml_path`` on the card's first model
(``conda/robotiq_gripper_85.xml``), ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``,
``model.actuator_ctrlrange``/``actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``MjModel`` walks the ``<worldbody>`` bodies for their joints and
reads the ``<actuator>`` elements for the actuator count and the control ranges (an explicit ``ctrlrange``, or a joint
range scaled by ``inheritrange``).  No number of the served model is copied into this file.  The numbers that are here
are placeholders: the library default time step used when the model sets no ``<option timestep>``, the fraction of the
remaining distance a placeholder step moves a joint, and the joint dimensions of MuJoCo's joint types.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, tendon or equality constraint (the served
model's two fixed tendons are ignored), and its integration is a placeholder first-order motion of each actuated joint
toward its control target.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET

#: placeholder: the sentinel of a range the model does not limit (MuJoCo's mjMAXVAL is not read from the model)
_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default time step, used only when the model sets no <option timestep>
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: placeholder: qpos and qvel entries per MuJoCo joint type; a missing type means "hinge"
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
#: placeholder: the control range of an actuator with neither a ctrlrange nor an inherited joint range
_UNBOUNDED = (-_FLOAT_MAX, _FLOAT_MAX)


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _iter_joints(body):
    """Yield every joint element below a ``<body>``, in document order (the bodies of the model nest)."""
    for child in body:
        if child.tag == "body":
            yield from _iter_joints(child)
        elif child.tag in ("joint", "freejoint"):
            yield child


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its name, type, range and its positions in the qpos/qvel arrays."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low=None, high=None):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the served model."""

    def __init__(self, root):
        joints = {}
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for joint in _iter_joints(worldbody):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = dict(joint.attrib)
                    kind = attributes.get("type", "hinge")
                entry = _Joint(joint.get("name"), kind, nq, nv)
                if "range" in attributes and kind in ("hinge", "slide"):
                    entry.low, entry.high = _two_floats(attributes["range"])
                joints[entry.name] = entry
                nq += _QPOS.get(kind, 1)                                  # placeholder size of the type
                nv += _QVEL.get(kind, 1)                                  # placeholder size of the type

        ranges, limited, targets = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = dict(element.attrib)
                joint = joints.get(attributes.get("joint"))
                low, high = _UNBOUNDED
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _two_floats(attributes["ctrlrange"])
                    is_limited = True
                elif joint is not None and joint.low is not None and joint.high is not None:
                    try:
                        inherit = float(attributes.get("inheritrange", 0.0) or 0.0)
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint.low * inherit, joint.high * inherit
                        is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else joint.qpos_adr)

        timestep = _TIMESTEP_S                                          # placeholder default of the library
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
        return cls(_load_text(xml))


def _load(path):
    """The MJCF tree of ``path``; the served model has no ``<include>``, and the stand-in does not expand one."""
    root = ET.parse(str(path)).getroot()
    if next(root.iter("include"), None) is not None:
        raise ValueError("the fake mujoco module does not expand <include> elements")
    return root


def _load_text(xml):
    root = ET.fromstring(xml)
    if next(root.iter("include"), None) is not None:
        raise ValueError("the fake mujoco module does not expand <include> elements")
    return root


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to zero (the bridge calls this on load and on every reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, adr in enumerate(model._targets):
        if adr is None or index >= len(data.ctrl):
            continue
        target = float(data.ctrl[index])
        current = float(data.qpos[adr])
        data.qvel[adr] = (target - current) * _STEP_FRACTION / dt
        data.qpos[adr] = current + data.qvel[adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
