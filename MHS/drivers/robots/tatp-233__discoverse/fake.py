"""Fake backend of the DISCOVERSE MMK2 driver: a pure Python stand-in for the ``mujoco`` module.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine (the upstream core dependency is
``mujoco>=3.2.0``, pyproject.toml:40), and package code never imports the clone.  ``backends["fake"]`` therefore
names the class below.  The ``MujocoBridge`` calls ``MjModel.from_xml_path`` and ``MjData`` on it, then
``mj_resetData``, ``mj_forward`` and ``mj_step``, and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange`` and ``model.actuator_ctrllimited``.

The model shape is read from the MJCF text, never invented: ``_load`` parses the scene and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``_Model`` takes the joint
dimensions, the integration step and each actuator's control range from that tree.  The served scene is
``models/mjcf/mmk2_floor.xml``; it includes ``mobile_chassis/mmk2/mmk2.xml`` (the mobile base, lift, head and two
arms) and ``mobile_chassis/mmk2/mmk2_control.xml`` (19 actuators).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no inertia, contact, tendon, equality, actuator or
sensor dynamics, and its integration is a placeholder first-order motion of each actuated joint toward its control
value.  The driver's fidelity ``gaps`` list every difference.  Nothing here talks to a device or to the real engine.
"""

from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no control range; not a model bound.
_FLOAT_MAX = 1.7976931348623157e308

#: Placeholder: MuJoCo's library default when a model sets no ``<option timestep>``.  The served model states none
#: (models/mjcf/mobile_chassis/mmk2/mmk2_options.xml:2 sets only the integrator and solver); the upstream MMK2Cfg
#: supplies 0.0025 s (discoverse/robots_env/mmk2_base.py:9) and SimulatorBase copies it onto the model
#: (discoverse/envs/simulator.py:220), but this package loads the model file directly and does not apply that
#: configuration, so the stand-in falls back to the library default as test data.
_FALLBACK_TIMESTEP = 0.002

#: Placeholder: fraction of the distance to its control value that one fake step moves an actuated joint.
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
        self._tables: dict[str, dict[str, dict[str, str]]] = {"main": {}}
        for section in root.findall("default"):
            for item in section:
                if item.tag == "default":
                    self._walk(item, "main")
                else:
                    self._tables["main"].setdefault(item.tag, {}).update(item.attrib)

    def _walk(self, node: ET.Element, parent: str) -> None:
        name = node.get("class") or parent
        table = copy.deepcopy(self._tables.get(parent, {}))
        for item in node:
            if item.tag == "default":
                continue
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


def _limits(text: str | None) -> tuple[float, float] | None:
    if not text:
        return None
    low, high = (float(item) for item in text.split()[:2])
    return low, high


def _joint_table(root: ET.Element, defaults: _Defaults) -> tuple[dict[str, tuple[int, int, tuple[float, float] | None]],
                                                                 int, int, list[float]]:
    """``{joint name: (qpos address, dof address, range)}`` and the qpos/dof counts and zero state."""
    table: dict[str, tuple[int, int, tuple[float, float] | None]] = {}
    qpos0: list[float] = []
    qpos = dof = 0
    for body in root.findall("worldbody"):
        for element in body.iter():
            if element.tag == "freejoint":
                kind = "free"
            elif element.tag == "joint":
                kind = defaults.of(element, "joint").get("type", "hinge")
            else:
                continue
            qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
            attributes = defaults.of(element, "joint")
            name = element.get("name")
            if name:
                table[name] = (qpos, dof, _limits(attributes.get("range")))
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
                joint = self._joints.get(str(element.get("joint")))
                bounds = _limits(attributes.get("ctrlrange"))
                if bounds is None:
                    # ``inheritrange``: a positive fraction of the joint range, centered on the joint range.
                    # No actuator of the served MMK2 scene sets it; the branch keeps the stand-in usable for a
                    # model that does.
                    inherit = attributes.get("inheritrange")
                    if inherit and joint is not None and joint[2] is not None:
                        fraction = float(inherit)
                        if fraction > 0:
                            low, high = joint[2]
                            middle, half = (low + high) / 2.0, (high - low) * fraction / 2.0
                            bounds = (middle - half, middle + half)
                if bounds is None:
                    ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                    limited.append(False)
                else:
                    ranges.append([bounds[0], bounds[1]])
                    limited.append(True)
                targets.append(None if joint is None else (joint[0], joint[1]))
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
    """Advance one placeholder step: each actuated joint moves toward its control value."""
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
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's tests do the same)."""

    def __init__(self, **_options: object):
        self.MjModel = _Model
        self.MjData = _Data
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
