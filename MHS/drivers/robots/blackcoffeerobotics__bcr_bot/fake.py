"""Package-local stand-in for the ``mujoco`` module used by the bcr_bot driver.

``MujocoDriver.make_bridge`` builds an ``mhs.bridge.mujoco.MujocoBridge`` with
``mujoco=native``.  The bridge calls ``MjModel.from_xml_path`` on the configured
scene, then ``mj_resetData``/``mj_forward``/``mj_step`` and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``,
``model.actuator_ctrllimited`` and ``data.time``/``qpos``/``qvel``/``ctrl``/
``act``.

MuJoCo is not installed here, so this module supplies only those members.  It
parses the same MJCF file and every ``<include>`` for the model shape: joint
dimensions, actuator names, default classes and the option timestep.  It is not
MuJoCo: it loads no mesh, texture or inertia, resolves no contact, friction,
tendon, equality or actuator force constraint, and its step is a placeholder
joint-velocity integration.  The fidelity gaps in ``driver.py`` disclose those
differences.  All state values start as placeholders and are test data.
"""

import math
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = sys.float_info.max

#: placeholder: the stand-in exposes only the bridge's basic snapshot profile
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


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
            self._walk(section, None)

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
            # placeholder: MuJoCo's library default when the model sets no option timestep
            timestep = 0.002
        if not math.isfinite(timestep) or timestep <= 0:
            raise ValueError("the MJCF option timestep must be positive and finite")
        self.opt = _Opt(timestep)

        joints = {}
        qpos = qvel = 0
        for element in root.iter():
            if element.tag not in ("joint", "freejoint"):
                continue
            if element.tag == "freejoint":
                kind = "free"
            else:
                kind = defaults.of(element, "joint").get("type", "hinge")
            if kind not in _QPOS_SIZE:
                raise ValueError(f"the MJCF joint type {kind!r} is not supported by the stand-in")
            name = element.get("name")
            if name:
                joints[name] = (qpos, qvel, kind)
            qpos += _QPOS_SIZE[kind]
            qvel += _QVEL_SIZE[kind]
        self.nq, self.nv, self.na = qpos, qvel, 0

        ranges, limited, names, qpos_index, qvel_index = [], [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
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
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Restore the stand-in's arrays to their zero defaults."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward or contact quantities."""


def mj_step(model, data):
    """Advance the placeholder one step: velocity actuators turn their joints."""
    dt = float(model.opt.timestep)
    for index, target in enumerate(data.ctrl):
        qpos = model._actuator_qpos[index]
        if qpos is None:
            continue
        velocity = float(target)
        data.qvel[model._actuator_qvel[index]] = velocity
        data.qpos[qpos] += velocity * dt
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
