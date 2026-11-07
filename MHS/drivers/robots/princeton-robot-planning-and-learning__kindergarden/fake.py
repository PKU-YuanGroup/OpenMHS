"""Fake ``mujoco`` module for the kindergarden RBY1A package: the MuJoCo API the bridge calls, over a placeholder.

The MuJoCo bridge imports ``mujoco`` lazily and takes the module from ``backends["fake"]``; here that is the callable
:func:`fake_mujoco`, which returns a small stand-in module.  The stand-in parses the pinned MJCF file with the standard
library: the model name, the option time step, the number and type of joints, and every actuator's control range from
the MJCF default classes.  Those are the model's numbers, so the derived contract (the per-actuator ``ctrl`` limits
and the lengths of ``qpos``, ``qvel`` and ``ctrl``) is the model's, not this file's.

What this is not: MuJoCo.  It loads no mesh, resolves no contact or equality constraint and integrates a placeholder
first-order motion of each actuated coordinate (``_STEP_FRACTION``), so trajectories are not the model's and are not
valid simulation results.  The engine and the model file are not installed or imported by the gate.  Nothing here
talks to a device.

The only numbers this module invents are the library default time step used when the model states none and the
placeholder integration constant; both are marked ``# placeholder`` and both are named in the driver's fidelity gaps.
"""

import types
import xml.etree.ElementTree as ET

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model states no <option timestep>; rby1a_model_v1.2.xml states none
_TIMESTEP_S = 0.002
#: placeholder: fraction of the control target one fake step moves an actuated coordinate toward
_STEP_FRACTION = 0.01
#: MuJoCo's mjtState.mjSTATE_INTEGRATION is a bit mask; the fake needs one constant for the integration state
MJSTATE_INTEGRATION = 1
#: qpos and qvel contributions of a joint type; MuJoCo's own layout.  Missing means "hinge".
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}
_ROOT_DEFAULT = ""


class _Opt:
    """The members of ``MjModel.opt`` the bridge reads."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Defaults:
    """The MJCF ``<default>`` classes of a model tree: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, _ROOT_DEFAULT)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                self._parent[name] = parent
                self._walk(child, name)
            else:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` for a default class, following the class chain from the root down."""
        chain, name = [], class_name if class_name is not None else _ROOT_DEFAULT
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


class MjModel:
    """The ``mujoco.MjModel`` members the bridge and this stand-in read, derived from the MJCF tree."""

    def __init__(self, *, name, timestep, njnt, nq, nv, ctrlrange, ctrllimited):
        self.name = name
        self.opt = _Opt(timestep)
        self.njnt = njnt
        self.nq = nq
        self.nv = nv
        self.nu = len(ctrlrange)
        self.actuator_ctrlrange = [list(pair) for pair in ctrlrange]
        self.actuator_ctrllimited = list(ctrllimited)

    @classmethod
    def from_xml_string(cls, xml):
        return cls(**_parse_root(ET.fromstring(xml)))

    @classmethod
    def from_xml_path(cls, path):
        with open(path, "r", encoding="utf-8") as handle:
            return cls(**_parse_root(ET.fromstring(handle.read())))


class MjData:
    """The integration state of one model instance (the members the bridge reads and writes)."""

    def __init__(self, model):
        self.model = model
        self.time = 0.0
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []


def _parse_root(root):
    """The model shape this stand-in derives from one MJCF tree (the file is read, never imported)."""

    option = root.find("option")
    timestep = option.get("timestep") if option is not None else None
    if timestep is None:
        timestep = _TIMESTEP_S  # placeholder: the library default, because the model states none

    worldbody = root.find("worldbody")
    njnt = nq = nv = 0
    if worldbody is not None:
        for joint in worldbody.iter("joint"):
            kind = joint.get("type", "hinge")
            njnt += 1
            nq += _QPOS.get(kind, 1)
            nv += _QVEL.get(kind, 1)
        for _free in worldbody.iter("freejoint"):
            njnt += 1
            nq += _QPOS["free"]
            nv += _QVEL["free"]

    defaults = _Defaults(root)
    ctrlrange, ctrllimited = [], []
    actuator = root.find("actuator")
    if actuator is not None:
        for element in actuator:
            if element.tag == "default":
                continue
            attributes = defaults.of(element, element.tag)
            pair = attributes.get("ctrlrange")
            if pair is None:
                ctrlrange.append((-_FLOAT_MAX, _FLOAT_MAX))
                ctrllimited.append(False)
                continue
            low, high = (float(value) for value in pair.split()[:2])
            ctrlrange.append((low, high))
            # MuJoCo's ctrllimited default is "auto": true when a ctrlrange is present and not "false".
            ctrllimited.append(str(attributes.get("ctrllimited", "true")).lower() != "false")

    return {"name": root.get("model") or "model", "timestep": float(timestep), "njnt": njnt, "nq": nq, "nv": nv,
            "ctrlrange": ctrlrange, "ctrllimited": ctrllimited}


def mj_resetData(model, data):
    """Set the data to the model defaults: zero time and zero state (the model has no keyframe)."""
    data.time = 0.0
    data.qpos = [0.0] * model.nq
    data.qvel = [0.0] * model.nv
    data.ctrl = [0.0] * model.nu
    data.act = []


def mj_forward(model, data):
    """No-op: the stand-in has no kinematics, dynamics or constraints to evaluate."""


def mj_step(model, data):
    """One placeholder integration step: ctrl moves qvel, qvel moves qpos, and time advances by the model step."""
    dt = float(model.opt.timestep)
    if model.nv:
        for index in range(model.nu):
            data.qvel[index % model.nv] += float(data.ctrl[index]) * _STEP_FRACTION
    for index in range(min(model.nq, model.nv)):
        data.qpos[index] += float(data.qvel[index]) * dt
    data.time += dt


def mj_stateSize(model, spec=0):
    """Size of the integration state: time, qpos, qvel and ctrl."""
    return 1 + model.nq + model.nv + model.nu


def mj_getState(model, data, state, spec=0):
    """Write the integration state into ``state`` (a numpy array or a list of floats)."""
    values = [float(data.time)] + [float(value) for value in data.qpos] \
        + [float(value) for value in data.qvel] + [float(value) for value in data.ctrl]
    for index, value in enumerate(values):
        state[index] = value


def mj_setState(model, data, state, spec=0):
    """Read the integration state back from ``state``."""
    values = [float(value) for value in state]
    data.time = values[0]
    data.qpos = values[1:1 + model.nq]
    data.qvel = values[1 + model.nq:1 + model.nq + model.nv]
    data.ctrl = values[1 + model.nq + model.nv:1 + model.nq + model.nv + model.nu]


def fake_mujoco(**_options):
    """The stand-in module: a fresh object with the MuJoCo members the bridge calls."""
    return types.SimpleNamespace(
        MjModel=MjModel,
        MjData=MjData,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
        mj_stateSize=mj_stateSize,
        mj_getState=mj_getState,
        mj_setState=mj_setState,
        mjtState=types.SimpleNamespace(mjSTATE_INTEGRATION=MJSTATE_INTEGRATION),
    )
