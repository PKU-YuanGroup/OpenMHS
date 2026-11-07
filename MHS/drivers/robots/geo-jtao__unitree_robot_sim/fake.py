"""Package-local stand-in for the ``mujoco`` module used by the unitree B2 driver.

``MujocoDriver.make_bridge`` builds an ``mhs.bridge.mujoco.MujocoBridge`` with
``mujoco=native``.  The bridge calls ``MjModel.from_xml_path`` on the configured
scene, then ``mj_resetData``/``mj_forward``/``mj_step`` and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.na``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and
``data.time``/``qpos``/``qvel``/``ctrl``/``act``.

MuJoCo is not installed where the acceptance gate runs, so this module supplies
only those members.  It parses the same MJCF scene and every ``<include>`` for
the model shape, the actuator names and ctrlranges, and the option timestep.
It is not MuJoCo: it loads no mesh, texture or inertia, resolves no contact,
friction, tendon, equality or actuator-force constraint, and its step is a
placeholder joint update: the model's ``<motor>`` entries are torque actuators,
so each control value accelerates its joint through a placeholder gain against
a placeholder damping (model review r20, 2026-11-05: the stand-in used to copy
the control value into the joint velocity).  Reset restores qpos0 as MuJoCo
defines it (the free base at its body's pos and quat), not zeros.  The fidelity
gaps in ``driver.py`` disclose those differences.  Every state value is test
data, not a fact about the B2 robot or a MuJoCo trajectory.
"""

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max

#: MJCF joint-type widths in MuJoCo's qpos/qvel vectors (API structure, not data).
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
# placeholder: joint acceleration per unit of motor control (a torque stand-in, not the model's inertia).
_TORQUE_GAIN = 0.5
# placeholder: velocity damping of the stand-in per second.
_DAMPING = 2.0
#: Body orientation attributes other than quat; the stand-in does not convert them.
_OTHER_ORIENTATIONS = ("euler", "axisangle", "xyaxes", "zaxis")


def _joints_in_tree_order(body):
    """Yield (joint element, owner body) as MuJoCo orders them: a body's joints, then its child bodies."""
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, body
    for child in body:
        if child.tag == "body":
            yield from _joints_in_tree_order(child)


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

    def of(self, element, tag):
        chain = []
        name = element.get("class")
        while name is not None and name in self._parent and name not in chain:
            chain.append(name)
            name = self._parent[name]
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        out.update(element.attrib)
        return out


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
            # placeholder: the stand-in's step when the MJCF declares no <option> timestep
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
        #: identity quaternion, a hinge or slide at its ref (0 when the MJCF states none).
        qpos0 = []
        for element, owner in _joints_in_tree_order(worldbody):
            if element.tag == "freejoint":
                kind = "free"
                attributes = dict(element.attrib)
            else:
                attributes = defaults.of(element, "joint")
                kind = attributes.get("type", "hinge")
            if kind not in _QPOS_SIZE:
                raise ValueError(f"the MJCF joint type {kind!r} is not supported by the stand-in")
            name = element.get("name")
            if name:
                joints[name] = (qpos, qvel, kind)
            if kind == "free":
                if any(owner.get(key) is not None for key in _OTHER_ORIENTATIONS):
                    raise ValueError("the stand-in reads a free body's orientation from quat only")
                position = [float(item) for item in str(owner.get("pos") or "0 0 0").split()][:3]
                quaternion = [float(item) for item in str(owner.get("quat") or "1 0 0 0").split()][:4]
                qpos0.extend(position + quaternion)
            elif kind == "ball":
                qpos0.extend([1.0, 0.0, 0.0, 0.0])
            else:
                qpos0.append(float(attributes.get("ref", 0.0)))
            qpos += _QPOS_SIZE[kind]
            qvel += _QVEL_SIZE[kind]
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.qpos0 = qpos0

        ranges, limited, names, qpos_index, qvel_index = [], [], [], [], []
        actuator = root.find("actuator")
        if actuator is not None:
            for element in actuator:
                if element.tag == "default":
                    continue
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
        # qpos starts at the model's qpos0; velocities and controls start at zero
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset to the model defaults: qpos0 (see ``MjModel``), zero velocity, control and time."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward or contact quantities."""


def mj_step(model, data):
    """Advance the stand-in one step: each motor's torque-like control accelerates its joint (placeholder)."""
    dt = float(model.opt.timestep)
    for index, control in enumerate(data.ctrl):
        qpos = model._actuator_qpos[index]
        if qpos is None:
            continue
        qvel = model._actuator_qvel[index]
        velocity = float(data.qvel[qvel])
        data.qvel[qvel] = velocity + (float(control) * _TORQUE_GAIN - velocity * _DAMPING) * dt
        data.qpos[qpos] += data.qvel[qvel] * dt
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
