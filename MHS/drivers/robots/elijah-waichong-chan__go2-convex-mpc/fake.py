"""Fake backend of the Go2 MuJoCo driver: a stand-in ``mujoco`` module for the scene ``models/MJCF/go2/scene.xml``.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine and a ``MujocoDriver`` is configuration
only.  ``backends["fake"]`` therefore names the factory below, whose result has the small part of the ``mujoco`` API
the bridge calls: ``MjModel.from_xml_path`` / ``from_xml_string``, ``MjData``, ``mj_resetData``, ``mj_forward``,
``mj_step``, and the integration-state snapshot functions.

The model shape is read from the pinned clone's MJCF text, never invented: ``_load`` parses the scene and expands its
``<include>`` element, ``_Defaults`` resolves the MJCF default classes (the ``go2`` class with its ``abduction``,
``hip``, ``front_hip``, ``back_hip`` and ``knee`` subclasses), and ``MjModel`` takes the model dimensions and each
actuator's ``ctrlrange`` from that tree.  The scene is ``models/MJCF/go2/scene.xml``; it includes
``models/MJCF/go2/go2.xml``, which carries the 12 motor actuators and the model's home keyframe.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, sensor or actuator dynamics,
and its integration is a placeholder first-order motion of each actuated hinge toward its control value.  The
driver's fidelity ``gaps`` state every difference.  Nothing here talks to a device or to the real engine.
"""

from __future__ import annotations

import copy
import types
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no ctrlrange; not a model bound.
_FLOAT_MAX = 1.7976931348623157e308

#: Placeholder: MuJoCo's library default when an MJCF states no <option timestep="...">.  The served scene states
#: none; the upstream demos set model.opt.timestep to 0.001 s (examples/ex00_demo.py:83-85,185-186).
_FALLBACK_TIMESTEP = 0.002

#: Placeholder: fraction of the distance to its control target that one fake step moves a joint.
_STEP_FRACTION = 0.02

#: qpos and dof contributions of the MJCF joint types; a joint with no ``type`` is a hinge.
_JOINT_SIZES = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}


def _expand(node: ET.Element, base: Path, depth: int = 0) -> None:
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


def _load(path: str | Path) -> ET.Element:
    """The MJCF tree of ``path`` with its includes expanded relative to the file that names them."""
    root = ET.parse(str(path)).getroot()
    _expand(root, Path(path).resolve().parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and the attributes of each element tag."""

    def __init__(self, root: ET.Element):
        self._tables: dict[str, dict[str, dict[str, str]]] = {}
        for section in root.findall("default"):
            table = self._tables.setdefault("main", {})
            for item in section:
                if item.tag != "default":
                    table.setdefault(item.tag, {}).update(item.attrib)
        for section in root.findall("default"):
            for child in section:
                if child.tag == "default":
                    self._walk(child, "main")

    def _walk(self, node: ET.Element, parent: str) -> None:
        name = node.get("class") or parent
        table = copy.deepcopy(self._tables.get(parent, {}))
        for item in node:
            if item.tag != "default":
                table.setdefault(item.tag, {}).update(item.attrib)
        self._tables[name] = table
        for child in node:
            if child.tag == "default":
                self._walk(child, name)

    def of(self, element: ET.Element, tag: str) -> dict[str, str]:
        """The class defaults of ``tag``, overridden by the element's own attributes."""
        table = self._tables.get(element.get("class") or "main", {})
        attributes = dict(table.get(tag, {}))
        attributes.update(element.attrib)
        return attributes


class _Opt:
    """``model.opt``: the bridge reads only ``timestep``."""

    def __init__(self, timestep: float):
        self.timestep = timestep


def _timestep(root: ET.Element) -> float:
    for option in root.findall("option"):
        text = option.get("timestep")
        if text:
            return float(text)
    return _FALLBACK_TIMESTEP


def _joint_table(root: ET.Element, defaults: _Defaults) -> tuple[dict[str, tuple[int, int]], int, int]:
    """``{joint name: (qpos address, dof address)}`` and the coordinate counts of the model."""
    table: dict[str, tuple[int, int]] = {}
    qpos = dof = 0
    for body in root.findall("worldbody"):
        for element in body.iter():
            if element.tag == "freejoint":
                qpos_size, dof_size = _JOINT_SIZES["free"]
            elif element.tag == "joint":
                kind = defaults.of(element, "joint").get("type", "hinge")
                qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
            else:
                continue
            name = element.get("name")
            if name:
                table[name] = (qpos, dof)
            qpos += qpos_size
            dof += dof_size
    return table, qpos, dof


class _Model:
    """The stand-in ``mujoco.MjModel``: dimensions, time step and actuator control ranges of the MJCF tree."""

    def __init__(self, root: ET.Element):
        defaults = _Defaults(root)
        self.opt = _Opt(_timestep(root))
        self._joints, self.nq, self.nv = _joint_table(root, defaults)
        self.na = 0
        ranges: list[list[float]] = []
        limited: list[bool] = []
        targets: list[tuple[int, int] | None] = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                text = attributes.get("ctrlrange")
                if text:
                    low, high = (float(item) for item in text.split()[:2])
                    ranges.append([low, high])
                    limited.append(True)
                else:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
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
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)

    def target(self, index: int) -> tuple[int, int] | None:
        """The ``(qpos address, dof address)`` the actuator drives, if the model names one."""
        return self._targets[index]


class _Data:
    """The stand-in ``mujoco.MjData``: the arrays the bridge reads and writes."""

    def __init__(self, model: _Model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act: list[float] = []
        self.time = 0.0


def mj_resetData(model: _Model, data: _Data) -> None:
    """Reset the data arrays to the stand-in's defaults (zero; the model's base height and home key are not applied)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act = []
    data.time = 0.0


def mj_forward(model: _Model, data: _Data) -> None:
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model: _Model, data: _Data) -> None:
    """Advance the stand-in one time step: each actuated hinge moves toward its control target (placeholder)."""
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
