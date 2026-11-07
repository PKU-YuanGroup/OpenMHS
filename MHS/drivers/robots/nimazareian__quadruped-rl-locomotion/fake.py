"""Fake ``mujoco`` module for the Unitree Go1 torque scene: a pure Python stand-in for the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the MuJoCo bridge imports ``mujoco``
lazily, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` names :class:`FakeMujoco`; the bridge calls ``MjModel.from_xml_path`` on
``unitree_go1/scene_torque.xml``, then ``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF text itself: ``_expand`` resolves the scene's ``<include>`` elements and
``_Defaults`` follows the ``<default>`` class chain, so the actuator count, the per-actuator ``ctrlrange`` and the
joint dimensions are the model's, not this file's.  For ``go1_torque.xml`` the global default states
``<motor ctrllimited="true" ctrlrange="-1.0 1.0"/>`` (line 7) and every one of the 12 ``<motor>`` elements inherits
it.

What this is not: MuJoCo.  It loads no mesh, texture or sensor, resolves no contact, constraint or gravity, and its
integration is a placeholder torque response (``_TORQUE_GAIN``), not MuJoCo's physics.  The driver's fidelity
``gaps`` list all of that.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

#: The largest double: the bridge reads an absent ctrlrange as unbounded.  # placeholder
_FLOAT_MAX = 1.7976931348623157e308
#: MuJoCo's library default when the model states no <option timestep>; go1_mujoco_env.py:37 states dt(=0.002) for
#: this scene, and go1_torque.xml:4 has an <option> without timestep.
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: arbitrary torque-to-angular-acceleration scale of the stand-in, not a physical parameter
_TORQUE_GAIN = 50.0
#: qpos and qvel contributions of a joint type (MuJoCo's state layout); a missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included ``<mujoco>`` root."""
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
    """The MJCF tree of ``path`` with its includes expanded, each path relative to the file that names it."""
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


def _floats(text, count=2):
    values = [float(item) for item in str(text).split()]
    if len(values) < count:
        raise ValueError(f"expected at least {count} numbers, got {text!r}")
    return values


class _Defaults:
    """The ``<default>`` classes of a model tree: class inheritance and per-tag attribute defaults."""

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
                    self._parent.setdefault(name, parent)
                self._walk(child, name)
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def _chain(self, class_name):
        names, name = [], class_name
        while name is not None and name not in names:
            names.append(name)
            name = self._parent.get(name)
        names.reverse()
        if not names or names[0] is not None:
            names.insert(0, None)
        return names

    def get(self, class_name, tag):
        """The merged defaults of ``tag`` for a class, from the global defaults down to that class."""
        out = {}
        for name in self._chain(class_name):
            out.update(self._attributes.get(name, {}).get(tag, {}))
        return out

    def of(self, element, tag, inherited_class=None):
        """The defaults of ``element``'s effective class for ``tag``, overridden by its own attributes."""
        out = self.get(element.get("class") or inherited_class, tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its name, kind and qpos/qvel positions."""

    def __init__(self, name, kind, qpos_adr, qvel_adr, qpos0):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.qpos0 = qpos0


def _body_pose(body):
    """The initial position and quaternion of a body (MuJoCo's default is the body ``pos``/``quat``)."""
    pos = _floats(body.get("pos", "0 0 0"), 3)[:3]
    quat = _floats(body.get("quat", "1 0 0 0"), 4)[:4]
    return pos + quat


def _walk_body(body, inherited_class):
    """Yield ``(joint element, effective default class, parent body)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass, body
        elif child.tag == "body":
            yield from _walk_body(child, childclass)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        option = root.find("option")
        timestep = float(option.get("timestep")) if option is not None and option.get("timestep") else \
            _DEFAULT_TIMESTEP_S
        self.opt = _Opt(timestep)

        joints = {}
        ordered = []
        dofs = []
        nq = nv = 0
        for worldbody in root.findall("worldbody"):
            for joint, inherited_class, parent in _walk_body(worldbody, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                qpos0 = _body_pose(parent) if kind == "free" else [float(attributes.get("ref", 0.0))]
                entry = _Joint(joint.get("name"), kind, nq, nv, qpos0)
                ordered.append(entry)
                if entry.name is not None:
                    joints[entry.name] = entry
                if kind != "free":
                    dofs.append((entry.qpos_adr, entry.qvel_adr))
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        actuators = []
        for block in root.findall("actuator"):
            for element in block:
                attributes = defaults.of(element, element.tag)
                pair = attributes.get("ctrlrange")
                if pair is not None:
                    low, high = _floats(pair)[:2]
                    limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    limited = False
                if not limited:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                joint_name = element.get("joint")
                actuators.append({"range": [low, high], "limited": limited,
                                  "joint": joints.get(joint_name) if joint_name else None})

        self.nu = len(actuators)
        self.nq = nq
        self.nv = nv
        self.qpos0 = []
        for joint in sorted(ordered, key=lambda item: item.qpos_adr):
            self.qpos0.extend(joint.qpos0)
        self.actuator_ctrlrange = [list(item["range"]) for item in actuators]
        self.actuator_ctrllimited = [1 if item["limited"] else 0 for item in actuators]
        self._dofs = dofs
        self._actuator_dofs = [None if item["joint"] is None else (item["joint"].qpos_adr, item["joint"].qvel_adr)
                               for item in actuators]

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
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint receives a torque (placeholder integration)."""
    dt = float(model.opt.timestep)
    for index, dof in enumerate(model._actuator_dofs):
        if dof is None or index >= len(data.ctrl):
            continue
        _qpos_adr, qvel_adr = dof
        data.qvel[qvel_adr] += float(data.ctrl[index]) * _TORQUE_GAIN * dt
    for qpos_adr, qvel_adr in model._dofs:
        data.qpos[qpos_adr] += data.qvel[qvel_adr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
