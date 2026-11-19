"""Pure Python stand-in for the ``mujoco`` module used by the fake backend.

The driver is a configuration-only ``MujocoDriver``.  Its bridge imports ``mujoco`` lazily; MuJoCo is not installed
where the acceptance gate runs, and package code never imports the clone.  ``backends["fake"]`` therefore names this
module object; the bridge calls ``MjModel.from_xml_path`` on the pinned MJCF
(``trajopt/envs/assets/sawyer.xml``), then ``mj_resetData``/``mj_forward``/``mj_step``, and reads
``model.opt.timestep``, ``model.nq``/``nv``/``na``/``nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and ``data.time``/``qpos``/``qvel``/``ctrl``/``act``.

The model shape comes from the MJCF text: this parser reads the ``<option>``, the default ``<joint>`` class, the
nested hinge joints with their ranges and the seven ``<motor>`` actuators with ctrlrange, ctrllimited and gear.
The control ranges are taken from the file, never invented.

What this is not: MuJoCo.  The integration is a placeholder torque integrator, not MuJoCo's Euler step: it uses the
model's gear, joint damping and armature, a placeholder unit inertia, and no composite rigid-body inertia, contact,
friction, equality, tendon, sensor or actuator force limit.  The driver's fidelity ``gaps`` list every difference.
Nothing here talks to a device.
"""

import math
import sys
import xml.etree.ElementTree as ET

_FLOAT_MAX = sys.float_info.max
# placeholder: the stand-in's inertia of every actuated joint.  The MJCF sets inertiafromgeom="true"
# (sawyer.xml:2) and states geom shapes, but this parser does not compute the composite rigid-body inertia.
_PLACEHOLDER_INERTIA = 1.0
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_DIMS = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}


def _pair(text):
    """Two finite floats from one MJCF attribute."""
    values = [float(item) for item in str(text).split()]
    if len(values) != 2 or not all(math.isfinite(value) for value in values):
        raise ValueError(f"expected two finite numbers, got {text!r}")
    return values[0], values[1]


def _truth(text, default):
    """A MuJoCo boolean attribute (``true``/``false``/``1``/``0``)."""
    if text is None:
        return default
    lowered = str(text).strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    raise ValueError(f"expected a boolean attribute, got {text!r}")


def _walk_joints(body):
    """Yield every joint element below ``body``; the pinned MJCF nests them inside <body> elements."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child
        elif child.tag == "body":
            yield from _walk_joints(child)


def _default_joint_attributes(root):
    """The attributes of the unnamed default ``<joint>`` class (sawyer.xml:4-7)."""
    attributes = {}
    for section in root.findall("default"):
        if section.get("class") is not None:
            continue
        for child in section:
            if child.tag == "joint":
                attributes.update(child.attrib)
    return attributes


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint: its qpos/qvel addresses, its range, and the damping/armature used by the stand-in."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, low, high, limited, ref, damping, armature):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high
        self.limited = limited
        self.ref = ref
        self.damping = damping
        self.armature = armature


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the pinned MJCF tree."""

    def __init__(self, root):
        defaults = _default_joint_attributes(root)
        joints = {}
        qpos0 = []
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for element in _walk_joints(worldbody):
                kind = "free" if element.tag == "freejoint" else element.get("type", "hinge")
                if kind not in _DIMS:
                    raise ValueError(f"unsupported joint type {kind!r} in the stand-in")
                merged = dict(defaults)
                merged.update(element.attrib)
                if kind not in ("hinge", "slide"):
                    raise ValueError(f"the stand-in supports hinge and slide joints only, not {kind!r}")
                low = high = None
                limited = _truth(merged.get("limited"), False)
                if merged.get("range") is not None:
                    low, high = _pair(merged["range"])
                    if limited and low > high:
                        raise ValueError(f"joint {element.get('name')!r} has a reversed range")
                ref = float(merged.get("ref", 0.0))  # placeholder: MuJoCo's joint ref default; the model states none
                if not math.isfinite(ref):
                    raise ValueError(f"joint {element.get('name')!r} has a non-finite ref")
                # placeholder: zero damping/armature when the model states none; this model states both (sawyer.xml:5).
                joint = _Joint(element.get("name"), kind, nq, nv, low, high, limited, ref,
                               float(merged.get("damping", 0.0)), float(merged.get("armature", 0.0)))
                if joint.name in joints:
                    raise ValueError(f"duplicate joint name {joint.name!r} in the stand-in")
                joints[joint.name] = joint
                qpos0.append(ref)
                nq += _DIMS[kind][0]
                nv += _DIMS[kind][1]

        ranges, limited, actuators = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag != "motor":
                    raise ValueError(f"the stand-in supports motor actuators only, not {element.tag!r}")
                joint = joints.get(element.get("joint"))
                if joint is None:
                    raise ValueError(f"actuator names unknown joint {element.get('joint')!r}")
                ctrlrange = element.get("ctrlrange")
                ctrllimited = _truth(element.get("ctrllimited"), ctrlrange is not None)
                if ctrllimited and ctrlrange is None:
                    raise ValueError(f"actuator {element.get('joint')!r} is limited but states no ctrlrange")
                if ctrlrange is not None:
                    low, high = _pair(ctrlrange)
                    if low > high:
                        raise ValueError(f"actuator {element.get('joint')!r} has a reversed ctrlrange")
                else:
                    # The bridge marks an actuator without ctrllimited as operator_required; this sentinel is not a bound.
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                # placeholder: MuJoCo's neutral gear when the model states none; every motor here states gear.
                gear = float(element.get("gear", 1.0))
                if not math.isfinite(gear):
                    raise ValueError(f"actuator {element.get('joint')!r} has a non-finite gear")
                ranges.append([low, high])
                limited.append(ctrllimited)
                actuators.append((joint, gear))

        timestep = None
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        if timestep is None or not math.isfinite(timestep) or timestep <= 0:
            raise ValueError("the pinned model must state a positive <option timestep>")
        self.name = root.get("model")
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._joints = joints
        self._actuators = actuators
        self._qpos0 = qpos0

    @classmethod
    def from_xml_path(cls, path):
        return cls(ET.parse(str(path)).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model._qpos0)
        self.qvel = [0.0] * model.nv
        self.qacc = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset).

    The stand-in uses the joint ``ref`` of the model (all zero in the pinned MJCF), as ``mj_resetData`` restores
    ``qpos0``.
    """
    data.qpos[:] = list(model._qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.qacc[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the bridge reads no derived quantity from the stand-in."""


def mj_step(model, data):
    """Advance the stand-in one placeholder torque step (see the module docstring)."""
    dt = float(model.opt.timestep)
    for index, (joint, gear) in enumerate(model._actuators):
        value = float(data.ctrl[index])
        low, high = model.actuator_ctrlrange[index]
        if model.actuator_ctrllimited[index]:
            value = min(max(value, low), high)
        velocity = float(data.qvel[joint.qvel_adr])
        acceleration = (gear * value - joint.damping * velocity) / (joint.armature + _PLACEHOLDER_INERTIA)
        velocity += acceleration * dt
        position = float(data.qpos[joint.qpos_adr]) + velocity * dt
        if joint.limited and joint.low is not None:
            if position < joint.low:
                position, velocity = joint.low, 0.0
            elif position > joint.high:
                position, velocity = joint.high, 0.0
        data.qacc[joint.qvel_adr] = acceleration
        data.qvel[joint.qvel_adr] = velocity
        data.qpos[joint.qpos_adr] = position
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
