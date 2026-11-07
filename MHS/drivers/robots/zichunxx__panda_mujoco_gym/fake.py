"""Fake backend of the Franka Panda driver: a stand-in ``mujoco`` module for the package's MuJoCo family driver.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine (it is not installed and nothing is installed
for the gate), and a MuJoCo family driver's fake backend is the module the bridge is given instead of the real
``mujoco`` (``mhs.bridge.mujoco.MujocoBridge`` imports it lazily and accepts an injected one).  This module reads the
model the package carries -- ``model.xml`` (a copy of ``pick_and_place.xml``) together with the robot file it includes,
``panda_mocap.xml`` -- and derives the part of the model the bridge publishes: the integration step of the
``<option>`` element, the numbers of coordinates and degrees of freedom (one qpos and one dof per hinge and slide
joint, four and three per ball joint, seven and six per free joint), the number of actuators, and the actuator
``ctrlrange`` of each actuator, resolved through the default classes the model states.

It then advances a minimal stand-in state: time grows by the model's timestep and every qpos value follows its velocity.
It computes no equations of motion, contacts or actuator dynamics, so a control vector changes nothing except
``data.ctrl``; the driver's fidelity ``gaps`` say so.

What it provides (the part of the ``mujoco`` interface ``mhs/bridge/mujoco.py`` uses):

* ``MjModel.from_xml_path(path)`` / ``from_xml_string(text)`` -> a model with ``opt.timestep``, ``nu``, ``nq``,
  ``nv`` and ``actuator_ctrlrange``/``actuator_ctrllimited``;
* ``MjData(model)`` -> ``time``, ``qpos``, ``qvel``, ``ctrl`` and ``act``;
* ``mj_resetData``, ``mj_forward`` and ``mj_step``.

There is no ``mj_getState``/``mj_setState``/``mj_stateSize``, so the bridge snapshots by copying time, qpos, qvel and
ctrl.  Nothing here talks to a device or to the MuJoCo engine; the numbers are the model file's own, never invented.
"""

import types
import xml.etree.ElementTree as ElementTree
from pathlib import Path

#: MuJoCo's default integration step when a model states none.  Placeholder: the carried model states 0.002 s
#: (model.xml:4), so this value is never used here.
FALLBACK_TIMESTEP = 0.002

#: qpos and dof counts of the joint types (MuJoCo model file format).
_JOINT_SIZES = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}

_JOINT_SKIP = ("default", "tendon")


def _class_defaults(root):
    """The default classes of the model: ``{class name: {element tag: {attribute: value}}}``, inheriting downwards."""
    table = {}

    def walk(element, inherited, prefix):
        for child in list(element):
            if child.tag != "default":
                continue
            name = child.get("class") or "main"
            qualified = name if prefix in (None, "main") else f"{prefix}/{name}"
            attrs = {tag: dict(values) for tag, values in inherited.items()}
            for item in list(child):
                if item.tag == "default":
                    continue
                attrs.setdefault(item.tag, {}).update(item.attrib)
            for key in (name, qualified):
                table.setdefault(key, attrs)
            walk(child, attrs, name)

    for top in root.findall("default"):
        attrs = {}
        for item in list(top):
            if item.tag == "default":
                continue
            attrs.setdefault(item.tag, {}).update(item.attrib)
        table.setdefault("main", attrs)
        walk(top, attrs, None)
    return table


def _expand_includes(element, base):
    """Resolve ``<include file=...>`` the way MuJoCo does: the children of the included root are inserted in place."""
    children = []
    for child in list(element):
        if child.tag == "include":
            path = base / str(child.get("file"))
            included = ElementTree.parse(path).getroot()
            _expand_includes(included, path.parent)
            children.extend(list(included) if included.tag == "mujoco" else [included])
        else:
            _expand_includes(child, base)
            children.append(child)
    for child in list(element):
        element.remove(child)
    for child in children:
        element.append(child)
    return element


def _model_root(path):
    root = ElementTree.parse(path).getroot()
    return _expand_includes(root, Path(path).parent)


def _walk_model(element):
    """The elements below the model root, skipping the default classes (templates) and the tendons (references)."""
    for child in element:
        if child.tag in _JOINT_SKIP:
            continue
        yield child
        yield from _walk_model(child)


def _joint_sizes(root):
    """``(nq, nv)`` of the model: the coordinate count of every joint it declares."""
    nq = nv = 0
    for element in _walk_model(root):
        if element.tag == "freejoint":
            qpos, dof = _JOINT_SIZES["free"]
        elif element.tag == "joint":
            qpos, dof = _JOINT_SIZES.get(str(element.get("type") or "hinge"), (1, 1))
        else:
            continue
        nq, nv = nq + qpos, nv + dof
    return nq, nv


def _ctrl_range(element, defaults):
    """``(low, high)`` of one actuator: its own ctrlrange, else the one of its default class, else None."""
    text = element.get("ctrlrange")
    if text is None:
        class_name = element.get("class") or "main"
        class_defaults = defaults.get(class_name) or defaults.get(class_name.split("/")[-1]) or {}
        text = (class_defaults.get(element.tag) or {}).get("ctrlrange")
    if text is None:
        return None
    low, high = (float(item) for item in text.split())
    return low, high


class _Model:
    """The stand-in model: the integration step and the dimension counts of the carried model file."""

    def __init__(self, root):
        option = root.find("option")
        timestep = option.get("timestep") if option is not None else None
        self.opt = types.SimpleNamespace(timestep=float(timestep) if timestep is not None else FALLBACK_TIMESTEP)
        self.nq, self.nv = _joint_sizes(root)
        defaults = _class_defaults(root)
        ranges = []
        for actuators in root.findall("actuator"):
            for element in list(actuators):
                ranges.append(_ctrl_range(element, defaults))
        self.nu = len(ranges)
        self.actuator_ctrlrange = [list(pair) for pair in ranges if pair is not None] or None
        ctrlrange_given = all(pair is not None for pair in ranges) and bool(ranges)
        self.actuator_ctrllimited = [True] * self.nu if ctrlrange_given else None

    @classmethod
    def from_xml_path(cls, path):
        return cls(_model_root(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ElementTree.fromstring(xml)
        _expand_includes(root, Path.cwd())
        return cls(root)


class _Data:
    """The stand-in data: time, the position and velocity vectors and the control vector of one model."""

    def __init__(self, model):
        self.time = 0.0
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self._timestep = float(model.opt.timestep)


def _reset(model, data):
    data.time = 0.0
    data.qpos = [0.0] * model.nq
    data.qvel = [0.0] * model.nv
    data.ctrl = [0.0] * model.nu
    data.act = []


def _forward(model, data):
    """The stand-in computes no kinematics: there is nothing to forward."""


def _step(model, data):
    """One stand-in step: time grows by the model's timestep and every qpos value follows its velocity."""
    data.time += data._timestep
    for index, velocity in enumerate(data.qvel):
        data.qpos[index] += velocity * data._timestep


def fake_mujoco(**_options):
    """The stand-in ``mujoco`` module the driver names as its fake backend."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=_reset,
        mj_forward=_forward,
        mj_step=_step,
    )
