"""Fake ``mujoco`` module for the DianaMed package: the MuJoCo API the bridge calls, over a placeholder model.

The MuJoCo bridge imports ``mujoco`` lazily and takes the module from ``backends["fake"]``; here that is the callable
:func:`fake_mujoco`, which returns a small stand-in module.  The stand-in parses the pinned model file with the
standard library (timestep, the seven joints, the seven actuator ctrlranges) so the derived contract is the model's,
and then integrates a placeholder model: ctrl drives qvel and qvel drives qpos.  It is not MuJoCo: no inertias,
contacts, constraints, sensors or rendering, so its trajectories are not valid simulation results.  The state it
keeps is placeholder test data.

Exact snapshots are offered the way MuJoCo offers them (mj_stateSize/mj_getState/mj_setState with
mjSTATE_INTEGRATION), so the bridge can snapshot and restore the fake's integration state.
"""

import types
from xml.etree import ElementTree

#: placeholder: the fake gives every joint this inertia, so a ctrl torque T accelerates it by T / INERTIA
INERTIA = 1.0
#: mjtState.mjSTATE_INTEGRATION of MuJoCo is a bit mask; the fake only needs one constant for the integration state
MJSTATE_INTEGRATION = 1


class _Opt:
    """The members of ``MjModel.opt`` the bridge reads."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The members of a MuJoCo model the bridge and the fake use, read from the model file."""

    def __init__(self, *, name, timestep, joints, ctrlrange, ctrllimited):
        self.name = name
        self.opt = _Opt(timestep)
        self.njnt = len(joints)
        self.nq = len(joints)          # every joint of the template is a hinge (one position coordinate)
        self.nv = len(joints)
        self.nu = len(ctrlrange)
        self.actuator_ctrlrange = [list(pair) for pair in ctrlrange]
        self.actuator_ctrllimited = list(ctrllimited)

    @classmethod
    def from_xml_string(cls, xml):
        return cls(**_parse(xml))

    @classmethod
    def from_xml_path(cls, path):
        with open(path, "r", encoding="utf-8") as handle:
            return cls(**_parse(handle.read()))


class MjData:
    """The integration state of one model instance (the members the bridge reads and writes)."""

    def __init__(self, model):
        self.model = model
        self.time = 0.0
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []


def _parse(xml):
    """``(name, timestep, joints, ctrlrange, ctrllimited)`` of a MJCF model file (the subset this package uses)."""
    root = ElementTree.fromstring(xml)
    option = root.find("option")
    timestep = option.get("timestep") if option is not None else None
    if timestep is None:
        raise ValueError("the model file states no <option timestep=...>: the fake refuses to invent one")
    joints = [joint.get("name") for joint in root.iter("joint")]
    ctrlrange = []
    ctrllimited = []
    for motor in root.iter("motor"):
        pair = motor.get("ctrlrange")
        if pair is None:
            raise ValueError("the model file has a motor without ctrlrange: the fake refuses to invent a bound")
        low, high = (float(value) for value in pair.split())
        ctrlrange.append((low, high))
        ctrllimited.append(motor.get("ctrllimited", "true") == "true")
    return {"name": root.get("model") or "model", "timestep": float(timestep), "joints": joints,
            "ctrlrange": ctrlrange, "ctrllimited": ctrllimited}


def mj_resetData(model, data):
    """Set the data to the model defaults: zero time and zero state (no keyframe in the template)."""
    data.time = 0.0
    data.qpos = [0.0] * model.nq
    data.qvel = [0.0] * model.nv
    data.ctrl = [0.0] * model.nu


def mj_forward(model, data):
    """No-op: the fake has no kinematics or dynamics to evaluate."""


def mj_step(model, data):
    """One placeholder integration step: ctrl acts through INERTIA, qpos advances by qvel * timestep."""
    dt = float(model.opt.timestep)
    for index in range(model.nu):
        data.qvel[index] += float(data.ctrl[index]) / INERTIA * dt
    for index in range(model.nq):
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
