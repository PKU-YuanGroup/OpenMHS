"""Fake ``mujoco`` module for gh.cxy1997/robotiq-ur5: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` lazily, and
MuJoCo and mujoco-py are neither installed nor installable where the acceptance gate runs.  Package code also never
imports the clone.  ``backends["fake"]`` therefore names this module object.  The bridge calls ``MjModel.from_xml_path``
on the card's model (``xmls/lab_env.xml``), then ``mj_resetData``, ``mj_forward`` and ``mj_step``, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time`` / ``data.qpos`` / ``data.qvel`` / ``data.ctrl`` arrays.

The shape comes from the MJCF text of the clone: the joint tree below ``<worldbody>`` gives the qpos and qvel
dimensions and each joint's address, and the active ``<actuator>`` elements give the control count and each
actuator's joint target.  The model declares no ``ctrlrange`` on its motors (``xmls/lab_env.xml:232-243``), so the
stand-in reports the library default ``[0, 0]`` with ``ctrllimited`` false for every motor, which the bridge reads as
"no bound".  XML comments are not elements, so the commented-out velocity and position actuators of
``xmls/lab_env.xml:217-230`` are not counted.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor constraint, and
its integration is a placeholder first-order motion of each actuated joint toward its control value.  These
differences are listed in the fidelity ``gaps`` of driver.py.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET

#: placeholder: MuJoCo's library default when a model sets no ``<option timestep>``
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: fraction of the remaining distance that one fake step moves an actuated joint
_STEP_FRACTION = 0.05
#: qpos and qvel widths per joint type: the library's structural contract, not a number of this device
_QPOS_WIDTH = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_WIDTH = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


class _DefaultClasses:
    """The ``<default>`` class tree: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parents = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._read(section, None)

    def _read(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class")
                if name:
                    self._parents[name] = parent
                    self._read(child, name)
                else:
                    self._read(child, parent)
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The merged defaults of ``tag`` for a class, from the global class down the class chain."""
        chain = []
        name = class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parents.get(name)
        chain.reverse()
        merged = {}
        for item in [None] + chain:
            merged.update(self._attributes.get(item, {}).get(tag, {}))
        return merged

    def of(self, element, tag, inherited_class=None):
        """The defaults of ``element``'s effective class for ``tag``, overridden by the element's own attributes."""
        merged = self.get(element.get("class") or inherited_class, tag)
        merged.update(element.attrib)
        return merged


class _Joint:
    """One joint of the model: its name, type and position in the qpos and qvel arrays."""

    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.qpos_adr = 0
        self.qvel_adr = 0


def _walk_bodies(body, inherited_class, defaults, joints):
    """Append every joint below ``body`` in the order MuJoCo lays qpos and qvel out."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag == "freejoint":
            joints.append(_Joint(child.get("name"), "free"))
        elif child.tag == "joint":
            attributes = defaults.of(child, "joint", childclass)
            kind = attributes.get("type", "hinge")
            if kind not in _QPOS_WIDTH:
                raise ValueError(f"the fake cannot model joint {child.get('name')!r} of type {kind!r}")
            joints.append(_Joint(child.get("name"), kind))
        elif child.tag == "body":
            _walk_bodies(child, childclass, defaults, joints)


def _collect_joints(root, defaults):
    """The joints of the model and its qpos and qvel dimensions."""
    joints = []
    for body in root.findall("worldbody"):
        _walk_bodies(body, None, defaults, joints)
    nq = nv = 0
    for joint in joints:
        joint.qpos_adr = nq
        joint.qvel_adr = nv
        nq += _QPOS_WIDTH[joint.kind]
        nv += _QVEL_WIDTH[joint.kind]
    return joints, nq, nv


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


def _collect_actuators(root, defaults, joints):
    """The active actuator elements: their joint target, ctrlrange and ctrllimited flag."""
    by_name = {joint.name: joint for joint in joints if joint.name}
    actuators = []
    for section in root.findall("actuator"):
        for element in section:
            if element.tag == "default":
                continue
            attributes = defaults.of(element, element.tag)
            joint = by_name.get(attributes.get("joint"))
            low, high = 0.0, 0.0  # placeholder: MuJoCo's default ctrlrange when a model states none
            if "ctrlrange" in attributes:
                low, high = _two_floats(attributes["ctrlrange"])
            limited = str(attributes.get("ctrllimited", "false")).lower() in ("true", "1")
            actuators.append((joint, low, high, limited))
    return actuators


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        if root.tag != "mujoco":
            raise ValueError(f"the model root is <{root.tag}>, not <mujoco>")
        if root.find(".//include") is not None:
            raise ValueError("the fake does not expand <include> elements; this model has none")
        defaults = _DefaultClasses(root)
        joints, nq, nv = _collect_joints(root, defaults)
        actuators = _collect_actuators(root, defaults, joints)

        timestep = _DEFAULT_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Options(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(actuators)
        self.actuator_ctrlrange = [[low, high] for _joint, low, high, _limited in actuators]
        self.actuator_ctrllimited = [limited for _joint, _low, _high, limited in actuators]
        self._qpos_targets = [None if joint is None else joint.qpos_adr
                              for joint, _low, _high, _limited in actuators]
        self._qvel_targets = [None if joint is None else joint.qvel_adr
                              for joint, _low, _high, _limited in actuators]
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
        # placeholder: the fake reset state is the all-zero model state
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the fake's zero state (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, qpos_adr in enumerate(model._qpos_targets):
        qvel_adr = model._qvel_targets[index]
        if qpos_adr is None or qvel_adr is None or index >= len(data.ctrl):
            continue
        target = float(data.ctrl[index])
        current = float(data.qpos[qpos_adr])
        velocity = (target - current) * _STEP_FRACTION / dt if dt > 0 else 0.0
        data.qvel[qvel_adr] = velocity
        data.qpos[qpos_adr] = current + velocity * dt
    data.time = float(data.time) + dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
