"""Stand-in ``mujoco`` module for the OMY tabletop package: a pure Python fake of the library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
names this class object; the bridge calls ``MjModel.from_xml_path`` on the card's scene
(``asset/robotis_omy/scene.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads
``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.na``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl``/``act`` arrays.

The model shape comes from the MJCF text itself: ``_load`` parses the file and expands every ``<include>`` (the scene
includes ``omy.xml``), and ``MjModel`` takes the hinge dimensions, the ten position actuators, the effective
per-actuator ``ctrlrange`` of each default class and the option timestep from that tree.  The model states no
``<option timestep>``, so ``_TIMESTEP_DEFAULT`` is a placeholder for MuJoCo's library default.

What this is not: MuJoCo.  It loads no STL mesh or texture, resolves no contact, equality, tendon or actuator force
constraint, and its integration is a placeholder first-order motion of each position-actuated joint toward its
control value.  All of that is listed in the driver's F0 fidelity gaps.  Nothing here talks to a device.
"""

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max
#: qpos and qvel contributions of a joint type; a missing type means "hinge".
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
# placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets none.
_TIMESTEP_DEFAULT = 0.002
# placeholder: fraction of the remaining distance that one fake step moves a position-actuated joint.
_STEP_FRACTION = 0.05
# placeholder: velocity (rad/s) the stand-in assigns per unit of a non-position control value.
_CTRL_TO_VELOCITY = 0.05


def _expand_includes(node, base, depth=0):
    """Replace every ``<include file=...>`` below ``node`` with the included root's children."""
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
    """The MJCF tree of ``path`` with every include expanded relative to the file that names it."""
    root = ET.parse(str(path)).getroot()
    _expand_includes(root, Path(path).resolve().parent)
    return root


def _two_floats(text):
    values = [float(item) for item in str(text).split()]
    if len(values) < 2 or not all(math.isfinite(value) for value in values[:2]):
        raise ValueError(f"expected two finite numbers, got {text!r}")
    return values[0], values[1]


class _Defaults:
    """The MJCF default classes: class inheritance and per-tag attribute defaults.

    The unnamed top-level ``<default>`` is MuJoCo's ``main`` class; a named class inherits from the class that
    encloses it (or ``main``), and an element's own attributes override every inherited one.
    """

    def __init__(self, root):
        self._parent = {"main": None}
        self._attributes = {}
        for section in root.findall("default"):
            name = section.get("class")
            if name is None:
                self._walk(section, "main")
            else:
                self._parent.setdefault(name, "main")
                self._walk(section, name)

    def _walk(self, node, name):
        for child in node:
            if child.tag == "default":
                child_name = child.get("class") or name
                self._parent[child_name] = name
                self._walk(child, child_name)
            else:
                self._attributes.setdefault(name, {}).setdefault(child.tag, {}).update(child.attrib)

    def of(self, element, tag, inherited_class=None):
        """The effective attributes of ``element`` for ``tag``: its class chain then its own attributes."""
        chain = []
        seen = set()
        name = element.get("class") or inherited_class or "main"
        while name is not None and name not in seen:
            seen.add(name)
            chain.append(name)
            name = self._parent.get(name)
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
        if child.tag in ("body", "frame"):
            yield from _walk_joints(child, childclass)


def _free_qpos0(body):
    """qpos0 of a free joint: its body's position and orientation (only pos and quat are modelled)."""
    for unsupported in ("euler", "axisangle", "xyaxes", "zaxis"):
        if body.get(unsupported) is not None:
            raise ValueError(f"the stand-in models only pos and quat on a free body, not {unsupported!r}")
    position = [float(item) for item in str(body.get("pos") or "0 0 0").split()]
    quaternion = [float(item) for item in str(body.get("quat") or "1 0 0 0").split()]
    if len(position) != 3 or len(quaternion) != 4:
        raise ValueError("the MJCF free body pos must hold 3 numbers and quat 4")
    return position + quaternion


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = float(timestep)


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        defaults = _Defaults(root)

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        if not math.isfinite(timestep) or timestep <= 0:
            raise ValueError("the MJCF option timestep must be positive and finite")
        self.opt = _Opt(timestep)

        body = root.find("worldbody")
        if body is None:
            raise ValueError("the MJCF scene has no worldbody")
        joints = {}
        qpos = qvel = 0
        qpos0 = []
        qvel0 = []
        count = 0
        for element, inherited_class, owner in _walk_joints(body, None):
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
            qvel0.extend([0.0] * _QVEL_SIZE[kind])
            count += 1
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.njnt = count
        self.qpos0 = qpos0
        self.qvel0 = qvel0

        compiler = root.find("compiler")
        autolimits = compiler is None or str(compiler.get("autolimits", "true")).lower() in ("true", "1")
        ranges, limited, targets, kinds = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                if element.tag not in ("position", "motor", "velocity"):
                    raise ValueError(f"the stand-in models only position, motor and velocity actuators, not "
                                     f"{element.tag!r}")
                attributes = defaults.of(element, element.tag)
                raw = attributes.get("ctrlrange")
                if raw is None:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                else:
                    low, high = _two_floats(raw)
                    token = str(attributes.get("ctrllimited", "true" if autolimits else "false")).lower()
                    ranges.append([low, high])
                    limited.append(token in ("true", "1"))
                joint = attributes.get("joint")
                targets.append(joints.get(joint, (None, None))[:2] if joint else None)
                kinds.append(element.tag)
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: the stand-in's own actuator-to-joint map (not a public MuJoCo member)
        self._targets = targets
        self._kinds = kinds

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand_includes(root, Path.cwd())
        return cls(root)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = list(model.qvel0)
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = list(model.qvel0)
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no forward or derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: a placeholder motion of each directly actuated joint."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model._targets):
        if place is None or index >= len(data.ctrl):
            continue
        qpos_index, qvel_index = place
        target = float(data.ctrl[index])
        current = float(data.qpos[qpos_index])
        if model._kinds[index] == "position":
            data.qpos[qpos_index] = current + (target - current) * _STEP_FRACTION
            data.qvel[qvel_index] = (data.qpos[qpos_index] - current) / dt
        elif model._kinds[index] == "velocity":
            data.qvel[qvel_index] = target
            data.qpos[qpos_index] = current + target * dt
        else:
            data.qvel[qvel_index] = target * _CTRL_TO_VELOCITY
            data.qpos[qpos_index] = current + data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    __version__ = "fake-mujoco-stand-in"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
