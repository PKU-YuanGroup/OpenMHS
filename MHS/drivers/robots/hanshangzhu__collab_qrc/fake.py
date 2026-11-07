"""Package-local stand-in for the ``mujoco`` module used by the collab_qrc driver.

``MujocoDriver.make_bridge`` builds an ``mhs.bridge.mujoco.MujocoBridge`` with
``mujoco=native``.  The bridge calls ``MjModel.from_xml_path`` on the configured
scene, then ``mj_resetData``/``mj_forward``/``mj_step`` and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.na``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and
``data.time``/``qpos``/``qvel``/``ctrl``/``act``.

MuJoCo is not installed here, so this module supplies only those members.  It
parses the same MJCF file and every ``<include>`` for the model shape: joint
dimensions, the default pose (qpos0), actuator names and kinds and the option
timestep.  It is not MuJoCo: it loads no mesh, texture or inertia, resolves no
contact, friction, tendon, equality or actuator force constraint, and its step
is a placeholder joint update.  The fidelity gaps in ``driver.py`` disclose
those differences.  All integration constants are placeholders and test data.

Model review (2026-11-05): the stand-in used to reset every qpos entry to zero,
including the free joint's quaternion, and to treat every control value as a
joint velocity.  MuJoCo's ``mj_resetData`` restores qpos0 (the base body's pos
4.0 0 0.6 with an identity quaternion, the hinges at their ref of 0), the twelve
``<motor>`` actuators are force (torque) actuators and the four ``<velocity>``
actuators apply kv * (ctrl - qvel); the stand-in now follows those semantics
with placeholder constants.
"""

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max

#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}

# placeholder: the stand-in's inertia of every actuated joint (not the model's inertia).
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


class _Defaults:
    """The MJCF default classes: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            name = section.get("class")
            if name is not None:
                self._parent[name] = None
            self._walk(section, name)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name is not None:
                    self._parent[name] = parent
                    self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def of(self, element, tag, inherited_class=None):
        """The attributes of ``element`` for ``tag``: its class chain (or the body's childclass), then its own."""
        chain = []
        name = element.get("class") or inherited_class
        while name is not None and name in self._parent and name not in chain:
            chain.append(name)
            name = self._parent[name]
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        out.update(element.attrib)
        return out


def _walk_joints(body, inherited_class):
    """Yield ``(joint element, effective class, owning body)`` in MuJoCo's depth-first body order."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, childclass, body
    for child in body:
        if child.tag == "body":
            yield from _walk_joints(child, childclass)


def _free_qpos0(body):
    """qpos0 of a free joint: its body's position and orientation (only pos and quat are modelled)."""
    for unsupported in ("euler", "axisangle", "xyaxes", "zaxis"):
        if body.get(unsupported) is not None:
            raise ValueError(f"the stand-in models only pos and quat on a free body, not {unsupported!r}")
    position = _numbers(body.get("pos") or "0 0 0", 3, "free body pos")
    quaternion = _numbers(body.get("quat") or "1 0 0 0", 4, "free body quat")
    return position + quaternion


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = float(timestep)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree."""

    def __init__(self, root):
        defaults = _Defaults(root)

        timestep = None
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        if timestep is None:
            # placeholder: MuJoCo's library default when the model sets no option timestep
            timestep = 0.002
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
        for element, inherited_class, owner in _walk_joints(worldbody, None):
            if element.tag == "freejoint":
                kind = "free"
            else:
                kind = defaults.of(element, "joint", inherited_class).get("type", "hinge")
            if kind not in _QPOS_SIZE:
                raise ValueError(f"the MJCF joint type {kind!r} is not supported by the stand-in")
            name = element.get("name")
            if name:
                joints[name] = (qpos, qvel, kind)
            qpos += _QPOS_SIZE[kind]
            qvel += _QVEL_SIZE[kind]
            if kind == "free":
                qpos0.extend(_free_qpos0(owner))
            elif kind == "ball":
                qpos0.extend([1.0, 0.0, 0.0, 0.0])
            else:
                qpos0.append(float(defaults.of(element, "joint", inherited_class).get("ref", 0.0)))
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.qpos0 = qpos0

        ranges, limited, names, qpos_index, qvel_index, kinds = [], [], [], [], [], []
        actuator = root.find("actuator")
        if actuator is not None:
            for element in actuator:
                if element.tag == "default":
                    continue
                if element.tag not in ("motor", "velocity"):
                    raise ValueError(f"the stand-in models only motor and velocity actuators, not {element.tag!r}")
                attributes = defaults.of(element, element.tag)
                raw = attributes.get("ctrlrange")
                if raw is None:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                else:
                    low, high = (float(value) for value in raw.split()[:2])
                    ranges.append([low, high])
                    limited.append(attributes.get("ctrllimited", "true").lower() == "true")
                joint = attributes.get("joint")
                names.append(attributes.get("name") or joint)
                if element.tag == "motor":
                    # MuJoCo's <motor> is a force actuator: force = gear * ctrl (gear defaults to 1).
                    kinds.append(("motor", float(str(attributes.get("gear", "1")).split()[0])))
                else:
                    # MuJoCo's <velocity> applies force = kv * (ctrl - qvel) (kv defaults to 1).
                    kinds.append(("velocity", float(attributes.get("kv", "1"))))
                if joint in joints:
                    qpos_index.append(joints[joint][0])
                    qvel_index.append(joints[joint][1])
                else:
                    qpos_index.append(None)
                    qvel_index.append(None)
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: the stand-in's own actuator-to-joint map (not a public MuJoCo member)
        self._actuator_names = names
        self._actuator_qpos = qpos_index
        self._actuator_qvel = qvel_index
        self._actuator_kinds = kinds

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
    """Advance the placeholder one step: each actuator's force accelerates its own joint (placeholder).

    A motor's force is gear * ctrl, a velocity actuator's force is kv * (ctrl - qvel); each acts on a
    placeholder unit inertia, and motor-driven joints lose velocity through a placeholder damping.  The free
    base, gravity, contacts, joint limits and every coupling between joints are not integrated.
    """
    dt = float(model.opt.timestep)
    for index, control in enumerate(data.ctrl):
        qpos = model._actuator_qpos[index]
        if qpos is None:
            continue
        qvel = model._actuator_qvel[index]
        kind, gain = model._actuator_kinds[index]
        velocity = float(data.qvel[qvel])
        if kind == "motor":
            acceleration = gain * float(control) / _PLACEHOLDER_INERTIA - _PLACEHOLDER_DAMPING * velocity
        else:
            acceleration = gain * (float(control) - velocity) / _PLACEHOLDER_INERTIA
        data.qvel[qvel] = velocity + acceleration * dt
        data.qpos[qpos] = float(data.qpos[qpos]) + data.qvel[qvel] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object named by ``backends["fake"]``."""

    __version__ = "fake-mujoco-stand-in"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
