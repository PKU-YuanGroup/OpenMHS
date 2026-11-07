"""Fake backend of the mujoco_panda driver: a stand-in for the ``mujoco`` module the bridge imports.

The package is a ``MujocoDriver`` and configuration only.  ``MujocoDriver.make_bridge`` builds an
``mhs.bridge.mujoco.MujocoBridge`` with ``mujoco=native``; the bridge calls ``MjModel.from_xml_path`` on the
card's scene (``mujoco_panda/models/franka_panda.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` and
reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.  MuJoCo (and the deprecated mujoco_py the clone targets) is not
installed and cannot be installed where the gate runs, so this module supplies exactly those members.

The model shape is read from the MJCF file itself: the XML is parsed, every ``<include>`` is expanded, and the
``<default>`` classes are resolved, so the actuator control ranges, the joint dimensions and the option timestep
are the card model's values and not constants of this file.  Two resolutions of an include path are tried, the
directory of the file that carries the include and the directory of the top-level model: ``arm_with_gripper.xml``
includes ``panda/gripper.xml`` although it lives in ``panda/``, which only resolves below the model directory.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, tendon, equality or
actuator constraint, and its step is a placeholder first-order motion of each actuated joint toward its control
value, not the model's torque dynamics.  Those differences are listed in the driver's fidelity ``gaps``.  Nothing
here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; franka_panda.xml:8-10 sets none
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to the control value that one fake step closes
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of a joint type in MuJoCo's layout; a missing type means "hinge"
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, model_dir, depth=0):
    """Replace every ``<include file=...>`` below ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            name = str(child.get("file"))
            target = base / name
            if not target.is_file():
                target = model_dir / name
            if not target.is_file():
                raise FileNotFoundError(f"the MJCF include {name!r} is not below {base} or {model_dir}")
            included = ET.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, model_dir, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, model_dir, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded (both MJCF include path conventions are tried)."""
    model = Path(path).resolve()
    tree = ET.parse(str(model)).getroot()
    _expand(tree, model.parent, model.parent)
    return tree


class _Defaults:
    """The MJCF ``<default>`` classes of a model: class inheritance and the per-tag attribute defaults."""

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

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes[item].get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        ranges, limited = [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                if "ctrlrange" in attributes:
                    low, high = (float(value) for value in attributes["ctrlrange"].split()[:2])
                    ranges.append([low, high])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
        qpos = qvel = 0
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                kind = defaults.of(joint, "joint").get("type", "hinge")
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
        timestep = _TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd(), Path.cwd())
        return cls(root)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward quantities."""


def mj_step(model, data):
    """Advance the stand-in one time step: every actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index in range(min(model.nu, model.nq)):
        data.qvel[index] = (data.ctrl[index] - data.qpos[index]) * _STEP_FRACTION / dt
        data.qpos[index] += data.qvel[index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
