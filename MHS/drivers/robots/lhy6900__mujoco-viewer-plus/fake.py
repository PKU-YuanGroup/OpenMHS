"""Stand-in ``mujoco`` module for gh.lhy6900/mujoco-viewer-plus.

Why a stand-in: the driver is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  Package code also
never imports the clone.  ``backends["fake"]`` therefore names this class.  The bridge calls
``MjModel.from_xml_path`` on the card's model (``deploy_robot/assets/mjcf/g1.xml``), then ``mj_resetData``,
``mj_forward`` and ``mj_step``, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.na``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time`` / ``data.qpos`` /
``data.qvel`` / ``data.ctrl`` / ``data.act`` arrays.

The shape comes from the MJCF text of the clone: the body tree below every ``<worldbody>`` gives the qpos and qvel
dimensions and each joint's address, and the active ``<actuator>`` elements give the control count and each
actuator's joint target.  The model declares 29 ``<motor>`` actuators and no ``ctrlrange`` on any of them
(``g1.xml:386-416``), so the stand-in reports the library default ``[0, 0]`` with ``ctrllimited`` false for every
motor, which the bridge reads as "no bound".

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon, sensor or actuator
constraint, does not integrate the free base, and its integration is a placeholder velocity proportional to each
control value, not the engine's dynamics.  These differences are listed in the fidelity ``gaps`` of driver.py.
Nothing here talks to a device.
"""

import types
import xml.etree.ElementTree as ET
from pathlib import Path

#: placeholder: MuJoCo's library default when a model sets no ``<option timestep>``; this model sets none
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: velocity (of the actuator's joint) per unit of the control value in one fake step
_CTRL_TO_VELOCITY = 0.01
#: qpos and qvel widths per joint type: the library's structural contract, not a number of this device
_QPOS_WIDTH = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_WIDTH = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


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


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class")
                if name:
                    self._parent[name] = parent
                    self._walk(child, name)
                else:
                    self._walk(child, parent)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` in a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag, inherited_class=None):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class") or inherited_class, tag)
        out.update(element.attrib)
        return out


class _Joint:
    """One joint of the model: its name, type and position in the qpos and qvel arrays."""

    def __init__(self, name, kind, qpos_default):
        self.name = name
        self.kind = kind
        self.qpos_default = qpos_default
        self.qpos_adr = 0
        self.qvel_adr = 0


def _walk_bodies(body, inherited_class, defaults, joints):
    """Append every joint below ``body`` in the order MuJoCo lays qpos and qvel out."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("freejoint", "joint"):
            attributes = defaults.of(child, "joint", childclass)
            kind = attributes.get("type", "free" if child.tag == "freejoint" else "hinge")
            if kind not in _QPOS_WIDTH:
                raise ValueError(f"the fake cannot model joint {child.get('name')!r} of type {kind!r}")
            if kind == "free":
                # The selected model's free joint is on the root pelvis (g1.xml:134-136).
                position = [float(value) for value in body.get("pos", "0 0 0").split()]
                orientation = [float(value) for value in body.get("quat", "1 0 0 0").split()]
                qpos_default = position + orientation
            elif kind == "ball":
                qpos_default = [1.0, 0.0, 0.0, 0.0]
            else:
                qpos_default = [float(attributes.get("ref", "0"))]
            joints.append(_Joint(child.get("name"), kind, qpos_default))
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
        defaults = _Defaults(root)
        joints, nq, nv = _collect_joints(root, defaults)
        actuators = _collect_actuators(root, defaults, joints)

        timestep = _DEFAULT_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Options(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.njnt = len(joints)
        self.nu = len(actuators)
        self.actuator_ctrlrange = [[low, high] for _joint, low, high, _limited in actuators]
        self.actuator_ctrllimited = [limited for _joint, _low, _high, limited in actuators]
        #: placeholder: the integration target of each actuator is its joint's qpos/qvel slot
        self.actuator_joint = [None if joint is None else (joint.qpos_adr, joint.qvel_adr)
                               for joint, _low, _high, _limited in actuators]
        #: Structural reset pose of the selected MJCF, including the pelvis height and valid quaternions.
        self.qpos0 = [value for joint in joints for value in joint.qpos_default]

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
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint moves by ``ctrl * _CTRL_TO_VELOCITY`` (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_adr, qvel_adr = place
        data.qvel[qvel_adr] = float(data.ctrl[index]) * _CTRL_TO_VELOCITY
        data.qpos[qpos_adr] += data.qvel[qvel_adr] * dt
    data.time = float(data.time) + dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    #: a string identity for the bridge's checkpoint metadata
    __version__ = "0.0-fake"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
        self.types = types.SimpleNamespace()
