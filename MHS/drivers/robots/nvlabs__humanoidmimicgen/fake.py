"""Fake ``mujoco`` module of the HumanoidMimicGen driver: a pure Python stand-in for the MuJoCo library.

Why a stand-in: the driver is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` lazily, and
MuJoCo is not installed where the acceptance gate runs (the upstream pins ``mujoco==3.2.6``, pyproject.toml:22, and
the gate installs nothing).  ``backends["fake"]`` is therefore the class object below: the bridge calls
``MjModel.from_xml_path`` on the card's model (``models[0]``), then ``MjData``, ``mj_resetData``, ``mj_forward`` and
``mj_step``, and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited``
and the ``data.time``/``qpos``/``qvel``/``ctrl`` arrays.

The model shape is read from the MJCF file itself, never invented: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the joint dimensions
(one free joint and 29 hinge joints), the 29 motor actuators and their control ranges from that tree.  The only
number this module adds is the fallback step when the model sets no ``<option timestep>``; it is marked placeholder.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no inertia, contact, actuator or sensor dynamics,
and its integration is a placeholder first-order motion of each actuated hinge toward its control value.  The
driver's fidelity ``gaps`` list every difference.  Nothing here talks to a device or to the real engine.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no ctrlrange; not a model bound.
_FLOAT_MAX = 1.7976931348623157e308

#: Placeholder: MuJoCo's library default when a model sets no ``<option timestep>``.  The served model sets none,
#: so this is the fallback the stand-in reads; it is not a number stated by the model file.
_TIMESTEP_S = 0.002

#: Placeholder: fraction of the distance to its control value that one fake step moves an actuated hinge.
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
    return _TIMESTEP_S


def _joint_table(root: ET.Element, defaults: _Defaults) -> tuple[dict[str, tuple[int, int]], int, int, list[float]]:
    """``{joint name: (qpos address, dof address)}``, the coordinate counts and the model default qpos."""
    table: dict[str, tuple[int, int]] = {}
    qpos = dof = 0
    qpos0: list[float] = []
    for body in root.findall("worldbody"):
        for element in body.iter():
            if element.tag == "freejoint":
                kind = "free"
            elif element.tag == "joint":
                kind = defaults.of(element, "joint").get("type", "hinge")
            else:
                continue
            qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
            name = element.get("name")
            if name:
                table[name] = (qpos, dof)
            qpos0.extend([0.0] * qpos_size)
            if kind == "free":
                qpos0[qpos + 3] = 1.0            # identity quaternion: MuJoCo stores [x, y, z, qw, qx, qy, qz]
            elif kind == "ball":
                qpos0[qpos] = 1.0                # identity quaternion: MuJoCo stores [qw, qx, qy, qz]
            qpos += qpos_size
            dof += dof_size
    return table, qpos, dof, qpos0


class _Model:
    """The stand-in ``mujoco.MjModel``: dimensions, time step and actuator control ranges of the MJCF tree."""

    def __init__(self, root: ET.Element):
        defaults = _Defaults(root)
        self._joints, self.nq, self.nv, self.qpos0 = _joint_table(root, defaults)
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
        self.opt = _Opt(_timestep(root))

    @classmethod
    def from_xml_path(cls, path: str | Path) -> "_Model":
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml: str) -> "_Model":
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)

    def target(self, index: int) -> tuple[int, int] | None:
        """The ``(qpos address, dof address)`` the actuator drives, if the model names a joint."""
        return self._targets[index]


class _Data:
    """The stand-in ``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model: _Model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act: list[float] = []
        self.time = 0.0


def mj_resetData(model: _Model, data: _Data) -> None:
    """Reset the data to the model defaults: qpos0, zero qvel and ctrl, and time zero."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act = []
    data.time = 0.0


def mj_forward(model: _Model, data: _Data) -> None:
    """Placeholder: the stand-in computes no derived quantities (no forward kinematics or sensor values)."""
    del model, data


def mj_step(model: _Model, data: _Data) -> None:
    """Advance one placeholder step: each actuated hinge moves toward its control value."""
    dt = float(model.opt.timestep)
    for index in range(min(model.nu, len(data.ctrl))):
        target = model.target(index)
        if target is None:
            continue
        qpos_index, dof_index = target
        error = float(data.ctrl[index]) - float(data.qpos[qpos_index])
        data.qvel[dof_index] = error * _STEP_FRACTION / dt
        data.qpos[qpos_index] = float(data.qpos[qpos_index]) + data.qvel[dof_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options: object):
        self.MjModel = _Model
        self.MjData = _Data
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
