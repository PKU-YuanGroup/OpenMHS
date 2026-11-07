"""Stand-in ``mujoco`` module for the MuJoCo Worldgen particle driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco``
when the model is first opened, and MuJoCo is neither installed nor installable where the acceptance
gate runs (no network, no pip).  ``backends["fake"]`` is therefore this module factory: the bridge
calls ``MjModel.from_xml_path`` on the card's MJCF file (``assets/xmls/particle/main.xml``), then
``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``,
``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited``, ``data.time``,
``data.qpos``, ``data.qvel`` and ``data.ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and
expands its ``<include>`` elements, and ``_Model`` takes the actuator control ranges, the actuator
count, the joint dimensions and the option time step from that tree.  The card's model sets the step
to 0.005 s (``main.xml:3``), declares three slide joints (``main.xml:6-8``) and two motors with gear
100 and no ``ctrlrange`` (``main.xml:16-19``).

What this is not: MuJoCo.  It resolves no contact, constraint, friction or actuator force model and
its integration is a placeholder motion of each actuated joint driven by its control value, not the
engine's dynamics.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a
device.
"""

import types
import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; this model sets 0.005 s
_TIMESTEP_DEFAULT = 0.002
#: placeholder: velocity (model units per second) the stand-in assigns per unit of gear-scaled control
_VELOCITY_PER_CTRL = 0.01
#: qpos and qvel contributions of a joint type; a missing type means a hinge
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included file."""
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
    """The MJCF tree of ``path`` with includes expanded (paths relative to the file that names them)."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Model:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        qpos = qvel = count = 0
        joint_place = {}
        for worldbody in root.findall("worldbody"):
            for joint in worldbody.iter("joint"):
                kind = joint.get("type", "hinge")
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = joint.get("name")
                if name:
                    joint_place[name] = (qpos, qvel)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
                count += 1

        ranges, limited, places, gears = [], [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                control_range = element.get("ctrlrange")
                if control_range is not None:
                    low, high = (float(value) for value in control_range.split()[:2])
                    is_limited = str(element.get("ctrllimited", "false")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                places.append(joint_place.get(element.get("joint")))
                gears.append(float(element.get("gear", "1")))

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.njnt = count
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.actuator_gear = gears
        #: the qpos/qvel slot each actuator drives; a motor with no joint (a tendon or site actuator) maps to None
        self.actuator_joint = places

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


class _Data:
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
    """Placeholder: the stand-in keeps no derived quantity that a forward pass would compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint takes a placeholder velocity from its control."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        data.qvel[qvel_index] = data.ctrl[index] * model.actuator_gear[index] * _VELOCITY_PER_CTRL
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


def fake_mujoco(**_options):
    """The backend factory: an object with the ``mujoco`` module members the bridge uses."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
    )
