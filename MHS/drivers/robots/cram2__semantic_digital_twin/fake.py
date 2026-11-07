"""Fake backend of the Semantic Digital Twin driver: a stand-in ``mujoco`` module for the panda MJCF scene.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine (nothing is installed for the gate), and a
``MujocoDriver`` is configuration only.  ``backends["fake"]`` therefore names the factory below, whose result has the
small part of the ``mujoco`` API the bridge calls: ``MjModel.from_xml_path`` / ``from_xml_string``, ``MjData``,
``mj_resetData``, ``mj_forward``, ``mj_step``, and the integration-state snapshot functions.

The model shape is read from the pinned clone's MJCF text, never invented: ``_load`` parses
``resources/mjcf/mjx_single_cube_no_mesh.xml``, ``_Defaults`` resolves the MJCF ``panda`` and ``finger`` default
classes, and ``MjModel`` takes the 0.005 s integration step, the coordinate counts (seven arm hinges, two finger
slides and the box's free joint) and each of the eight actuator ``ctrlrange`` values from that tree.  A position
actuator is the MJCF shortcut of a general actuator, so when a position element states no control range the general
default of its class is used; that is how actuator7 gets the panda default -2.8973 to 2.8973.

What this is not: MuJoCo.  It computes no inertias, contacts, equality constraint or actuator dynamics; one placeholder
step moves each actuated joint a fraction of the way to its control target.  The driver's fidelity ``gaps`` state every
difference.  Nothing here talks to a device or to the real engine.
"""

from __future__ import annotations

import types
import xml.etree.ElementTree as ElementTree
from pathlib import Path

#: Sentinel for an actuator with no resolvable ctrlrange; it is not a model bound.
_FLOAT_MAX = 1.7976931348623157e308

#: MuJoCo's library default when an MJCF sets no <option timestep>.  The served model sets 0.005 s
#: (resources/mjcf/mjx_single_cube_no_mesh.xml:118), so this value is not used here.
_FALLBACK_TIMESTEP = 0.002  # placeholder

#: Fraction of the distance to its control target that one fake step moves a joint.
_STEP_FRACTION = 0.02  # placeholder

#: qpos and dof contributions of the MJCF joint types; a joint with no ``type`` is a hinge.
_JOINT_SIZES = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}


def _expand(node: ElementTree.Element, base: Path, depth: int = 0) -> None:
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = ElementTree.parse(str(target)).getroot()
            _expand(included, target.resolve().parent, depth + 1)
            children.extend(list(included) if included.tag == "mujoco" else [included])
        else:
            _expand(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path: str | Path) -> ElementTree.Element:
    """The MJCF tree of ``path`` with its includes expanded relative to the file that names them."""
    root = ElementTree.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and the attributes of each element tag."""

    def __init__(self, root: ElementTree.Element):
        self._tables: dict[str, dict[str, dict[str, str]]] = {"main": {}}
        for section in root.findall("default"):
            table = self._tables["main"]
            for item in section:
                if item.tag != "default":
                    table.setdefault(item.tag, {}).update(item.attrib)
        for section in root.findall("default"):
            for child in section:
                if child.tag == "default":
                    self._collect(child, "main")

    def _collect(self, node: ElementTree.Element, parent: str) -> None:
        name = node.get("class") or parent
        table = {tag: dict(attrs) for tag, attrs in self._tables.get(parent, {}).items()}
        for item in node:
            if item.tag != "default":
                table.setdefault(item.tag, {}).update(item.attrib)
        self._tables[name] = table
        for child in node:
            if child.tag == "default":
                self._collect(child, name)

    def of(self, element: ElementTree.Element) -> dict[str, str]:
        """The class defaults of the element's tag, overridden by the element's own attributes."""
        table = self._tables.get(element.get("class") or "main", {})
        attributes = dict(table.get(element.tag, {}))
        attributes.update(element.attrib)
        return attributes

    def general_ctrlrange(self, element: ElementTree.Element) -> str | None:
        """The ``<general>`` control range of the element's class, if the class states one."""
        table = self._tables.get(element.get("class") or "main", {})
        return (table.get("general") or {}).get("ctrlrange")


def _timestep(root: ElementTree.Element) -> float:
    for option in root.findall("option"):
        text = option.get("timestep")
        if text:
            return float(text)
    return _FALLBACK_TIMESTEP


def _joint_table(root: ElementTree.Element, defaults: _Defaults) -> tuple[dict[str, tuple[int, int]], int, int]:
    """``{joint name: (qpos address, dof address)}`` and the coordinate counts of the model."""
    table: dict[str, tuple[int, int]] = {}
    qpos = dof = 0
    for world in root.findall("worldbody"):
        for element in world.iter():
            if element.tag == "freejoint":
                qpos_size, dof_size = _JOINT_SIZES["free"]
            elif element.tag == "joint":
                kind = defaults.of(element).get("type", "hinge")
                qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
            else:
                continue
            name = element.get("name")
            if name:
                table[name] = (qpos, dof)
            qpos += qpos_size
            dof += dof_size
    return table, qpos, dof


def _ctrl_range(element: ElementTree.Element, defaults: _Defaults) -> tuple[float, float] | None:
    """``(low, high)`` of one actuator, or None when the model states no control range."""
    text = defaults.of(element).get("ctrlrange")
    if text is None and element.tag == "position":
        text = defaults.general_ctrlrange(element)
    if text is None:
        return None
    low, high = (float(item) for item in text.split()[:2])
    return low, high


class _Model:
    """The stand-in ``mujoco.MjModel``: dimensions, time step and actuator control ranges of the MJCF tree."""

    def __init__(self, root: ElementTree.Element):
        defaults = _Defaults(root)
        self.opt = types.SimpleNamespace(timestep=_timestep(root))
        self._joints, self.nq, self.nv = _joint_table(root, defaults)
        ranges: list[list[float]] = []
        limited: list[bool] = []
        targets: list[tuple[int, int] | None] = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                pair = _ctrl_range(element, defaults)
                if pair is None:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                else:
                    ranges.append([pair[0], pair[1]])
                    limited.append(True)
                targets.append(self._joints.get(str(element.get("joint"))))
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets

    @classmethod
    def from_xml_path(cls, path: str | Path) -> "_Model":
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml: str) -> "_Model":
        root = ElementTree.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)

    def target(self, index: int) -> tuple[int, int] | None:
        """The ``(qpos address, dof address)`` the actuator drives, if the model names one."""
        return self._targets[index]


class _Data:
    """The stand-in ``mujoco.MjData``: the arrays the bridge reads and writes."""

    def __init__(self, model: _Model):
        self.qpos = [0.0] * model.nq  # placeholder: start positions
        self.qvel = [0.0] * model.nv  # placeholder: start velocities
        self.ctrl = [0.0] * model.nu  # placeholder: start controls
        self.act: list[float] = []  # placeholder: empty activation state
        self.time = 0.0  # placeholder: start time


def mj_resetData(model: _Model, data: _Data) -> None:
    """Reset the data arrays to zero (the stand-in's model-default pose)."""
    data.qpos[:] = [0.0] * model.nq  # placeholder: reset positions
    data.qvel[:] = [0.0] * model.nv  # placeholder: reset velocities
    data.ctrl[:] = [0.0] * model.nu  # placeholder: reset controls
    data.act = []  # placeholder: empty activation state
    data.time = 0.0  # placeholder: reset time


def mj_forward(model: _Model, data: _Data) -> None:
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model: _Model, data: _Data) -> None:
    """Advance one placeholder step: each actuated joint moves toward its control target."""
    dt = float(model.opt.timestep)
    for index in range(model.nu):
        target = model.target(index)
        if target is None:
            continue
        qpos_index, dof_index = target
        error = data.ctrl[index] - data.qpos[qpos_index]
        data.qvel[dof_index] = error * _STEP_FRACTION / dt
        data.qpos[qpos_index] += data.qvel[dof_index] * dt
    data.time += dt


class _MjtState:
    """The ``mujoco.mjtState`` member the bridge checks for exact snapshots."""

    mjSTATE_INTEGRATION = 1


def mj_stateSize(model: _Model, spec: int) -> int:
    """The length of the stand-in integration state: time, qpos, qvel and ctrl."""
    del spec
    return 1 + model.nq + model.nv + model.nu


def mj_getState(model: _Model, data: _Data, state: object, spec: int) -> None:
    """Copy the stand-in integration state into ``state`` (a list or a numpy array)."""
    del spec
    values = [float(data.time)] + [float(item) for item in data.qpos] + \
             [float(item) for item in data.qvel] + [float(item) for item in data.ctrl]
    state[:] = values  # type: ignore[index]


def mj_setState(model: _Model, data: _Data, state: object, spec: int) -> None:
    """Restore the stand-in integration state written by :func:`mj_getState`."""
    del spec
    offset = 0
    data.time = float(state[offset])  # type: ignore[index]
    offset += 1
    data.qpos[:] = [float(item) for item in state[offset:offset + model.nq]]  # type: ignore[index]
    offset += model.nq
    data.qvel[:] = [float(item) for item in state[offset:offset + model.nv]]  # type: ignore[index]
    offset += model.nv
    data.ctrl[:] = [float(item) for item in state[offset:offset + model.nu]]  # type: ignore[index]


def fake_mujoco(**_options: object) -> types.SimpleNamespace:
    """The stand-in ``mujoco`` module the driver names as its fake backend."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mjtState=_MjtState,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
        mj_stateSize=mj_stateSize,
        mj_getState=mj_getState,
        mj_setState=mj_setState,
    )
