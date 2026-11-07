"""Stand-in ``mujoco`` module for the Noetix N2 driver: a pure Python fake of the MuJoCo library surface.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` when the model is
first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore the ``FakeMujoco`` object below: the bridge calls ``MjModel.from_xml_path`` on the
card's model, then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``,
``model.nq``, ``model.nv``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The shape (the free joint, the eighteen hinge joints, the eighteen motor actuators and the option time step) is
parsed from the MJCF file itself, so the derived contract comes from the card's model, not from constants of this
file.  The model declares no ``ctrlrange``, so the stand-in reports an unlimited control range and the bridge
publishes no control envelope.  The integration is a placeholder: each actuated hinge takes a velocity from a fixed
gain times the control value, and the free base is held where the model puts it.  That is not MuJoCo's physics; the
driver's fidelity ``gaps`` say so.  Nothing here talks to a physical robot.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets none
_TIMESTEP_DEFAULT = 0.002
#: placeholder: velocity per unit of control for one fake step (the model's motors take a torque, not a velocity)
_CONTROL_GAIN = 0.01
#: qpos and qvel contributions of a joint type; a missing type means "hinge"
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand_includes(node, base, depth=0):
    """Replace every ``<include file=...>`` child of ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ET.parse(str(target)).getroot()
            _expand_includes(included, target.resolve().parent, depth + 1)
            index = list(node).index(child)
            node.remove(child)
            for offset, item in enumerate(list(included)):
                node.insert(index + offset, item)
        else:
            _expand_includes(child, base, depth)


def _load(path):
    """The MJCF tree of ``path`` with includes expanded (paths relative to the file that names them)."""
    root = ET.parse(str(path)).getroot()
    _expand_includes(root, Path(path).resolve().parent)
    return root


def _numbers(text, count, default):
    """``count`` floats of an MJCF attribute, or ``default`` when the attribute is absent."""
    if text is None:
        return list(default)
    values = [float(value) for value in text.split()]
    if len(values) != count:
        raise ValueError(f"expected {count} numbers, got {text!r}")
    return values


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        self.qpos0 = []
        self.nv = 0
        joints = {}
        for body in root.iter("body"):
            for child in body:
                if child.tag == "freejoint":
                    kind = "free"
                elif child.tag == "joint":
                    kind = child.get("type", "hinge")
                else:
                    continue
                if kind not in _QPOS_DIM:
                    raise ValueError(f"unsupported joint type {kind!r}")
                start = len(self.qpos0)
                name = child.get("name")
                if name:
                    joints[name] = (kind, start, self.nv)
                if kind == "free":
                    position = _numbers(body.get("pos"), 3, [0.0, 0.0, 0.0])
                    quaternion = _numbers(body.get("quat"), 4, [1.0, 0.0, 0.0, 0.0])
                    self.qpos0.extend(position + quaternion)
                elif kind == "ball":
                    self.qpos0.extend([1.0, 0.0, 0.0, 0.0])
                else:
                    self.qpos0.append(0.0)
                if len(self.qpos0) - start != _QPOS_DIM[kind]:
                    raise ValueError(f"joint {name!r}: wrong qpos size")
                self.nv += _QVEL_DIM[kind]
        self.nq = len(self.qpos0)

        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                self.actuator_joints.append(joints.get(element.get("joint")))
                raw = element.get("ctrlrange")
                if raw is not None:
                    low, high = _numbers(raw, 2, [0.0, 0.0])
                    limited = str(element.get("ctrllimited", "false")).lower() in ("true", "1")
                    self.actuator_ctrlrange.append([low, high])
                    self.actuator_ctrllimited.append(limited)
                else:
                    self.actuator_ctrlrange.append([-_FLOAT_MAX, _FLOAT_MAX])
                    self.actuator_ctrllimited.append(False)
        self.nu = len(self.actuator_ctrlrange)

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)

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
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Restore the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated hinge takes a placeholder velocity from its control value."""
    dt = float(model.opt.timestep)
    for index, entry in enumerate(model.actuator_joints):
        if entry is None:
            continue
        kind, qpos_index, qvel_index = entry
        if kind not in ("hinge", "slide"):
            continue
        data.qvel[qvel_index] = float(data.ctrl[index]) * _CONTROL_GAIN
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
