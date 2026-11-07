"""Fake ``mujoco`` module of the ACT driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's MJCF file, then
``mj_resetData``/``mj_forward``/``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange`` and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is read from the MJCF file itself, so the derived contract (per-actuator ``ctrl`` limits, the joint
dimensions, the time step) is the card's model and not a number of this file: ``_load`` parses the XML and expands its
``<include>`` elements, and ``MjModel`` takes the actuator control ranges, the joint dimensions and the option time
step from that tree.  The only number this module adds is the MuJoCo library default time step, used when the model
sets none (this model sets none: ``assets/scene.xml:2`` is commented out).

What this is not: MuJoCo.  It does not load the STL meshes, it resolves no contact, equality or tendon constraint,
and its integration is a placeholder first-order motion of each actuated joint toward its control target
(``_STEP_FRACTION``), not MuJoCo's physics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here
talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets none
_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to its control target that one fake step moves a joint
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of a joint type; MuJoCo's own layout.  Missing means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
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
    """The MJCF tree of ``path`` with its includes expanded (paths relative to the file that names them)."""
    tree = ET.parse(str(path)).getroot()
    _expand(tree, Path(path).resolve().parent)
    return tree


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        ranges, limited = [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                if "ctrlrange" in element.attrib:
                    low, high = (float(value) for value in element.attrib["ctrlrange"].split()[:2])
                    ranges.append([low, high])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
        qpos = qvel = 0
        for worldbody in root.findall("worldbody"):
            for joint in worldbody.iter("joint"):
                kind = joint.get("type", "hinge")
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
    """Advance the stand-in one time step: each actuated joint moves toward its control target (placeholder)."""
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
