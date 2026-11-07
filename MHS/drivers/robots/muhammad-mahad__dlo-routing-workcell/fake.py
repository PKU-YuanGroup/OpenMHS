"""Fake ``mujoco`` module for the DLO routing workcell driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is not installable where the acceptance gate runs (no network, no pip) and this scene needs a patched MuJoCo
3.3.2 build with the Chen ``wire`` plugin (README.md:93).  ``backends["fake"]`` is therefore this module object: the
bridge calls ``MjModel.from_xml_path`` on the card's MJCF file (``models[0]``, scene.xml), then
``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange``/``actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape comes from the MJCF file itself, so the derived contract (one ``ctrl`` interval per actuator, the
number of qpos and qvel entries) is the card's model, not a number of this file.  The generated scene.xml is not
UTF-8: its header comment carries byte 0x97 (a CP1252 dash), so ``_read`` falls back to CP1252 after a strict UTF-8
decode.  ``_Defaults`` resolves the MJCF default classes, as the model does when it binds ``class="paL_panda"`` and
friends.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or plugin constraint,
and its integration is a placeholder first-order motion of each actuated scalar joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  The wire cable's ball joints never move.  All of that is listed in the
driver's fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; scene.xml sets none (scene.xml:19)
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves an actuated joint
_STEP_FRACTION = 0.02
#: qpos and qvel contributions per joint type; MuJoCo's own layout.  Missing type means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _read(path):
    """The XML root of ``path``: strict UTF-8, then CP1252 (the generated scene.xml is CP1252)."""
    data = Path(path).read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("cp1252")
    return ET.fromstring(text)


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = _read(target)
            _expand(included, target.resolve().parent, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF root of ``path`` with its includes expanded (paths relative to the file that names them)."""
    root = _read(path)
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes of a model: class inheritance and per-tag attribute defaults."""

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
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members this bridge reads, derived from the MJCF model of the card."""

    def __init__(self, root):
        defaults = _Defaults(root)
        ranges, limited, joints = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                if "ctrlrange" in attributes:
                    pair = attributes["ctrlrange"].split()
                    ranges.append([float(pair[0]), float(pair[1])])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                joints.append(attributes.get("joint"))
        qpos = qvel = 0
        qpos_index, qvel_index = {}, {}
        for body in root.findall("worldbody"):
            for joint in body.iter("joint"):
                attributes = defaults.of(joint, "joint")
                kind = attributes.get("type", "hinge")
                name = attributes.get("name")
                if name:
                    qpos_index[name] = qpos
                    qvel_index[name] = qvel
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
        #: qpos/qvel offsets of each actuated joint; None for an actuator that drives a tendon.
        self._actuator_qpos = [qpos_index.get(name) for name in joints]
        self._actuator_qvel = [qvel_index.get(name) for name in joints]

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
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated scalar joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index, target in enumerate(data.ctrl):
        qpos_index = model._actuator_qpos[index]
        qvel_index = model._actuator_qvel[index]
        if qpos_index is None or qvel_index is None:
            continue
        velocity = (float(target) - float(data.qpos[qpos_index])) * _STEP_FRACTION / dt
        data.qvel[qvel_index] = velocity
        data.qpos[qpos_index] += velocity * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do too)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
