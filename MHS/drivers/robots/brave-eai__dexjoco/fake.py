"""Stand-in ``mujoco`` module for the DexJoCo bimanual-assembly MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` on first use,
and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  The bridge
calls ``MjModel.from_xml_path`` on the card's scene, ``MjData(model)``, ``mj_resetData``/``mj_forward``/``mj_step``,
and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and ``data.time``/``qpos``/``qvel``/
``ctrl``; this module supplies exactly those members.

The model shape is read from the MJCF file, not hard-coded: ``_expand`` follows the ``<include>`` graph of the scene
(``arena_arm_hand_bimanual_assembly.xml`` includes ``panda_allegro_bimanual.xml``, which includes the right and left
arm/hand models, plus the peg and tray), ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the
per-actuator control ranges, the ``qpos``/``qvel`` dimensions and the option time step from that tree.  The three
``# placeholder`` numbers below are the only numbers this module adds: library defaults and a fake integration
fraction, never a device limit or a fact.

What this is not: MuJoCo.  It loads no mesh, texture, camera or sensor, resolves no contact, equality, tendon or
actuator constraint, and its integration is a placeholder first-order motion of each actuated joint toward its
control target, not the engine's dynamics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this scene sets 0.002 s itself
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the distance to its control target that one fake step closes
_STEP_FRACTION = 0.02
#: qpos and qvel contributions of a joint type; a missing type means a hinge
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
    if depth > 16:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 16 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = (base / str(child.get("file"))).resolve()
            included = ET.parse(str(target)).getroot()
            _expand(included, target.parent, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path):
    """The MJCF tree of ``path`` with its includes expanded (paths relative to the file that names them)."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        self._walk(root, None)

    def _walk(self, node, current):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or current
                if name is not None:
                    self._parent.setdefault(name, current)
                self._walk(child, name)
            elif current is not None:
                self._attributes.setdefault(current, {}).setdefault(child.tag, {}).update(child.attrib)

    def chain(self, class_name):
        """The class chain from the root class down to ``class_name`` (a cycle stops the walk)."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        return list(reversed(chain))

    def of(self, element, tag):
        """The attributes of ``tag`` for ``element``'s class, overridden by the element's own attributes."""
        out = {}
        for name in self.chain(element.get("class")):
            out.update(self._attributes.get(name, {}).get(tag, {}))
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's scene."""

    def __init__(self, root):
        defaults = _Defaults(root)
        ranges, limited = [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                ctrlrange = attributes.get("ctrlrange")
                ctrllimited = str(attributes.get("ctrllimited", "auto")).lower()
                if ctrlrange is not None and ctrllimited not in ("false", "0"):
                    low, high = (float(value) for value in str(ctrlrange).split()[:2])
                    ranges.append([low, high])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)

        nq = nv = 0
        free_qpos = []
        for section in root.findall("worldbody"):
            for element in section.iter():
                if element.tag == "freejoint":
                    free_qpos.append(nq)
                    nq += _QPOS["free"]
                    nv += _QVEL["free"]
                elif element.tag == "joint":
                    kind = defaults.of(element, "joint").get("type", "hinge")
                    nq += _QPOS.get(kind, _QPOS["hinge"])
                    nv += _QVEL.get(kind, _QVEL["hinge"])

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.free_qpos = free_qpos

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
    for start in getattr(model, "free_qpos", ()):
        data.qpos[start + 3] = 1.0  # the w component of a free joint's unit quaternion
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities (sensors, contacts) to compute."""


def mj_step(model, data):
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
    dt = float(model.opt.timestep)
    for index in range(min(model.nu, model.nq)):
        error = float(data.ctrl[index]) - float(data.qpos[index])
        data.qvel[index] = error * _STEP_FRACTION / dt
        data.qpos[index] += error * _STEP_FRACTION
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
