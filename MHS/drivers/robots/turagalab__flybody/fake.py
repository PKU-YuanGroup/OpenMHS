"""Fake backend of the FlyBody driver: a stand-in ``mujoco`` module for the package's MuJoCo family driver.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine (it is not installed, and nothing is
installed for the gate), and a MuJoCo family driver's fake backend is the module the bridge is given instead of the
real ``mujoco`` (``mhs.bridge.mujoco.MujocoBridge`` imports it lazily and accepts one).  This module reads the
dimensions of the model file the package carries (``model.xml``, a copy of flybody/fruitfly/assets/fruitfly.xml):
the integration step of the ``<option>`` element, the number of joints (one qpos and one dof per hinge, four and three
per ball joint, seven and six for the free joint) and the number of actuators.  It then advances a minimal stand-in
state: time grows by the model's timestep, qpos follows qvel, qvel is kept and ctrl is stored.  It does not compute
equations of motion, contacts, adhesion or actuator dynamics; the driver's fidelity ``gaps`` say so.

What it provides (the part of the ``mujoco`` interface ``mhs/bridge/mujoco.py`` uses):

* ``MjModel.from_xml_path(path)`` / ``from_xml_string(text)`` -> a model with ``opt.timestep``, ``nu``, ``nq`` and
  ``nv``, and ``actuator_ctrlrange`` / ``actuator_ctrllimited`` read from each actuator element and its default
  classes (model review 2026-11-05: the author's stand-in gave ``None``, so the reference bounded nothing although
  the model's main default makes every actuator ctrl-limited, fruitfly.xml:11);
* ``MjData(model)`` -> ``time``, ``qpos``, ``qvel``, ``ctrl``;
* ``mj_resetData``, ``mj_forward``, ``mj_step``.

No ``mj_getState`` / ``mj_setState``: the bridge then snapshots by copying time, qpos, qvel and ctrl.

Nothing here talks to a device or to the MuJoCo engine.  The only numbers are the model file's own (parsed, never
invented) and the fallback timestep marked below.  The class resolution follows the MJCF rules this model uses (a
class's actuator defaults over those of the classes it nests in, the element's own attributes last, ``ctrllimited``
"auto" meaning "limited when a ctrlrange is given" under ``autolimits``); it is not MuJoCo's compiler.
"""

import types
import xml.etree.ElementTree as ElementTree

#: Fallback integration step, in seconds, when the model file has no <option timestep="...">.  Placeholder: the
#: package's model.xml states 0.0001 s (flybody/fruitfly/assets/fruitfly.xml:4), so this value is never used here.
FALLBACK_TIMESTEP = 0.0001

#: qpos and dof counts of a free joint.
_FREE_QPOS, _FREE_DOF = 7, 6
#: qpos and dof counts of a ball joint.
_BALL_QPOS, _BALL_DOF = 4, 3


def _walk(element):
    """The elements below ``element``, skipping subtrees that name no body or joint of their own.

    ``<default>`` holds class templates and ``<tendon>`` holds references to joints that already exist elsewhere; the
    other sections (assets, actuators, sensors) carry no joint definitions.
    """
    for child in element:
        if child.tag in ("default", "tendon"):
            continue
        yield child
        yield from _walk(child)


#: The actuator elements; inside a ``<default>`` class each of them sets the one actuator default of that class.
_ACTUATOR_TAGS = ("general", "motor", "position", "velocity", "intvelocity", "damper", "cylinder", "muscle", "adhesion")


def _actuator_defaults(root: ElementTree.Element) -> tuple[dict, dict]:
    """``(attributes, parent)``: the actuator attributes each default class sets, and the class it is nested in."""
    attributes: dict = {}
    parent: dict = {}

    def walk(node, name, up):
        parent.setdefault(name, up)
        own = attributes.setdefault(name, {})
        for child in node:
            if child.tag == "default":
                walk(child, child.get("class") or name, name)
            elif child.tag in _ACTUATOR_TAGS:
                own.update(child.attrib)

    for section in root.findall("default"):
        walk(section, section.get("class") or "main", None)
    return attributes, parent


def _ctrl_ranges(root: ElementTree.Element, elements: list) -> tuple[list, list]:
    """``(actuator_ctrlrange, actuator_ctrllimited)`` of ``elements``, from each element and its default classes."""
    attributes, parent = _actuator_defaults(root)
    autolimits = all((item.get("autolimits") or "true").lower() == "true" for item in root.findall("compiler"))
    ranges: list = []
    limited: list = []
    for element in elements:
        chain, name = [], element.get("class") or "main"
        while name is not None and name not in chain:
            chain.append(name)
            name = parent.get(name)
        if "main" not in chain:
            chain.append("main")
        values: dict = {}
        for item in reversed(chain):
            values.update(attributes.get(item, {}))
        values.update(element.attrib)
        text = values.get("ctrlrange")
        flag = (values.get("ctrllimited") or "auto").lower()
        ranges.append([float(part) for part in text.split()[:2]] if text else [0.0, 0.0])
        limited.append(flag == "true" or (flag == "auto" and autolimits and text is not None))
    return ranges, limited


def _joint_counts(root: ElementTree.Element) -> tuple[int, int]:
    """``(nq, nv)`` from the joint elements of the model (hinge and slide 1, ball 4/3, free 7/6)."""
    nq = nv = 0
    for element in _walk(root):
        if element.tag == "freejoint":
            nq, nv = nq + _FREE_QPOS, nv + _FREE_DOF
        elif element.tag == "joint":
            kind = element.get("type", "hinge")
            if kind == "free":
                nq, nv = nq + _FREE_QPOS, nv + _FREE_DOF
            elif kind == "ball":
                nq, nv = nq + _BALL_QPOS, nv + _BALL_DOF
            else:
                nq, nv = nq + 1, nv + 1
    return nq, nv


class _Model:
    """The stand-in model: the integration step, the dimension counts and the actuator control ranges."""

    def __init__(self, root: ElementTree.Element):
        option = root.find("option")
        timestep = option.get("timestep") if option is not None else None
        self.opt = types.SimpleNamespace(timestep=float(timestep) if timestep is not None else FALLBACK_TIMESTEP)
        self.nq, self.nv = _joint_counts(root)
        actuators = root.find("actuator")
        elements = list(actuators) if actuators is not None else []
        self.nu = len(elements)
        self.actuator_ctrlrange, self.actuator_ctrllimited = _ctrl_ranges(root, elements)

    @classmethod
    def from_xml_path(cls, path):
        return cls(ElementTree.parse(path).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ElementTree.fromstring(xml))


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
    """The stand-in has nothing to forward: kinematics are not computed."""


def _step(model, data):
    """One stand-in step: time grows by the model's timestep and qpos follows qvel (which stays as it is)."""
    data.time += data._timestep
    for index, velocity in enumerate(data.qvel):
        data.qpos[index] += velocity * data._timestep


def fake_mujoco(**_options):
    """The stand-in ``mujoco`` module (the driver's fake backend factory)."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=_reset,
        mj_forward=_forward,
        mj_step=_step,
    )
