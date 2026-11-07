"""Fake backend of the multiagent_mujoco driver: a stand-in for the ``mujoco`` module the bridge imports.

The package is a ``MujocoDriver`` and configuration only.  ``MujocoDriver.make_bridge`` builds an
``mhs.bridge.mujoco.MujocoBridge`` with ``mujoco=native``; the bridge calls ``MjModel.from_xml_path`` on the card's
first model (``multiagent_mujoco/assets/coupled_half_cheetah.xml``), then ``mj_resetData``/``mj_forward``/``mj_step``
and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.  MuJoCo (and the mujoco-py 2.1 the clone targets) is not installed
and cannot be installed where the gate runs, so this module supplies exactly those members.

The model shape is read from the MJCF text itself: the XML is parsed and the unnamed top-level ``<default>`` class
is resolved, so the joint dimensions and the actuator control ranges are the card model's values and not constants
of this file.  The numbers below are placeholders: the library default time step used only when a model sets no
``<option timestep>``, the fraction of the remaining distance one fake step moves a joint, the sentinel of an
unlimited control range, and the MuJoCo joint-type dimensions.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, damping, gear, tendon,
equality or actuator constraint, and its step is a placeholder first-order motion of each actuated joint toward its
control value, not the model's torque dynamics (the twelve motors of the served model are torque channels).  Those
differences are listed in the driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET

#: placeholder: sentinel for a control range the model does not limit
_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default time step, used only when the model sets no <option timestep>
_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: placeholder: qpos and qvel entries per MuJoCo joint type
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _bool(text):
    """A MuJoCo ``true``/``false`` attribute; anything that is not true reads as false."""
    return str(text).strip().lower() in ("true", "1")


def _pair(text):
    """Two whitespace-separated numbers of an MJCF range attribute."""
    values = [float(item) for item in str(text).split()]
    if len(values) != 2:
        raise ValueError(f"expected two numbers in the MJCF range {text!r}")
    return values[0], values[1]


class _Defaults:
    """The ``<default>`` classes of an MJCF model: class inheritance and the per-tag attribute defaults."""

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
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, global defaults first and the named class last."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        if None not in chain:
            chain.append(None)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


def _iter_joints(body):
    """Yield ``(element, tag)`` for every joint below a ``<body>``, in document order (the bodies nest)."""
    for child in body:
        if child.tag == "body":
            yield from _iter_joints(child)
        elif child.tag == "joint":
            yield child, "joint"
        elif child.tag == "freejoint":
            yield child, "freejoint"


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        world = root.find("worldbody")
        if world is None:
            raise ValueError("the MJCF has no <worldbody>")
        self.joints = []
        self.nq = self.nv = 0
        for element, tag in _iter_joints(world):
            attrs = defaults.of(element, tag)
            kind = "free" if tag == "freejoint" else str(attrs.get("type", "hinge"))
            if kind not in _QPOS:
                raise ValueError(f"the fake does not know the MJCF joint type {kind!r}")
            self.joints.append({"name": attrs.get("name"), "type": kind, "qpos": self.nq, "qvel": self.nv})
            self.nq += _QPOS[kind]
            self.nv += _QVEL[kind]
        self.joint_by_name = {joint["name"]: joint for joint in self.joints if joint["name"]}
        self.actuators, self.actuator_ctrlrange, self.actuator_ctrllimited = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attrs = defaults.of(element, element.tag)
                if "ctrlrange" in attrs:
                    low, high = _pair(attrs["ctrlrange"])
                    limited = _bool(attrs.get("ctrllimited", "false"))
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    limited = False
                self.actuators.append({"name": attrs.get("name"), "joint": attrs.get("joint")})
                self.actuator_ctrlrange.append([low, high])
                self.actuator_ctrllimited.append(1 if limited else 0)
        self.nu = len(self.actuators)
        option = root.find("option")
        timestep = option.get("timestep") if option is not None else None
        self.opt = _Opt(float(timestep) if timestep else _TIMESTEP_S)

    @classmethod
    def from_xml_path(cls, path):
        """Load the model shape from the MJCF file at ``path`` (read-only; the clone is never modified)."""
        return cls(ET.parse(str(path)).getroot())


class MjData:
    """The ``mujoco.MjData`` arrays the bridge reads and writes."""

    def __init__(self, model):
        self.time = 0.0
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.time = 0.0
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward quantities (no contacts, forces or sensors)."""


def mj_step(model, data):
    """Advance the stand-in one time step: every actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, actuator in enumerate(model.actuators):
        joint = model.joint_by_name.get(actuator["joint"])
        if joint is None or joint["type"] not in ("hinge", "slide"):
            continue
        position, velocity = joint["qpos"], joint["qvel"]
        data.qvel[velocity] = (float(data.ctrl[index]) - data.qpos[position]) * _STEP_FRACTION / dt
        data.qpos[position] += data.qvel[velocity] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
