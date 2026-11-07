"""Fake backend of the vikashplus/franka_sim driver: a pure Python stand-in for the ``mujoco`` library.

Why a stand-in: a ``MujocoDriver`` is configuration only, the bridge imports ``mujoco`` lazily, and MuJoCo is neither
installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]`` therefore names
the factory below; its result carries the part of the ``mujoco`` API the bridge calls: ``MjModel.from_xml_path`` /
``from_xml_string``, ``MjData``, ``mj_resetData``, ``mj_forward``, ``mj_step``, the integration-state snapshot
functions, and ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange`` and the data arrays.

The model shape is read from the pinned clone's MJCF text, never invented: ``_load`` parses the served scene
``bi-franka_panda.xml`` and expands its ``<include>`` elements, ``_Defaults`` resolves the MJCF default classes
(``panda``, ``panda_arm``, ``panda_forearm`` and ``panda_finger`` of assets/assets.xml:41-68), and ``MjModel`` takes
the joint dimensions, the integration step and each actuator's control range from that tree.  The served scene is the
card's first model: a torso with a left arm from assets/chain0.xml and a right arm from assets/chain1.xml
(bi-franka_panda.xml:23-35), 18 one-DOF joints in all and 16 position actuators, 9 on the right arm and 7 on the left
(the two right finger actuators at assets/actuator1.xml:17-18; the two left finger joints have no actuator).

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality or tendon constraint, and its
integration is a placeholder first-order motion of each actuated joint toward its control value, not MuJoCo's
physics.  The driver's fidelity ``gaps`` state every difference.  Nothing here talks to a device.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no finite ctrlrange; it is not a model bound.
_FLOAT_MAX = sys.float_info.max

#: placeholder: MuJoCo's library default step when a model sets no <option timestep>.  The served scene sets
#: 0.002 s explicitly (assets/assets.xml:12), so this value is only the fallback.
_FALLBACK_TIMESTEP = 0.002

#: placeholder: fraction of the distance to its control value that one fake step moves a joint.
_STEP_FRACTION = 0.05

#: qpos and dof contributions of the MJCF joint types; a joint with no ``type`` is a hinge.
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


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


def _two_floats(text: str) -> tuple[float, float]:
    values = [float(item) for item in str(text).split()]
    if len(values) < 2:
        raise ValueError(f"expected two numbers, got {text!r}")
    return values[0], values[1]


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and the attributes of each element tag."""

    def __init__(self, root: ET.Element):
        self._parents: dict[str | None, str | None] = {}
        self._tables: dict[str | None, dict[str, dict[str, str]]] = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node: ET.Element, parent: str | None) -> None:
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                self._parents.setdefault(name, parent)
                self._walk(child, name)
            else:
                self._tables.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def _chain(self, class_name: str | None) -> list[str | None]:
        names: list[str | None] = []
        name = class_name
        while name is not None and name not in names:
            names.append(name)
            name = self._parents.get(name)
        names.reverse()
        if not names or names[0] is not None:
            names.insert(0, None)
        return names

    def get(self, class_name: str | None, tag: str) -> dict[str, str]:
        """The merged defaults of ``tag`` for a class, following the class chain from the root down."""
        out: dict[str, str] = {}
        for name in self._chain(class_name):
            out.update(self._tables.get(name, {}).get(tag, {}))
        return out

    def of(self, element: ET.Element, tag: str, inherited_class: str | None = None) -> dict[str, str]:
        """The defaults of ``element``'s effective class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class") or inherited_class, tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads only ``timestep``."""

    def __init__(self, timestep: float):
        self.timestep = timestep


class _Joint:
    """One joint of the model: its name, type, range, and qpos/qvel positions in the data arrays."""

    def __init__(self, name: str | None, kind: str, qpos_adr: int, qvel_adr: int,
                 low: float | None, high: float | None):
        self.name = name
        self.kind = kind
        self.qpos_adr = qpos_adr
        self.qvel_adr = qvel_adr
        self.low = low
        self.high = high


def _walk_body(body: ET.Element, inherited_class: str | None):
    """Yield ``(joint element, effective default class)`` for every joint below ``body``."""
    childclass = body.get("childclass") or inherited_class
    for child in body:
        if child.tag in ("joint", "freejoint"):
            yield child, child.get("class") or childclass
        elif child.tag == "body":
            yield from _walk_body(child, childclass)


def _timestep(root: ET.Element) -> float:
    for option in root.findall("option"):
        text = option.get("timestep")
        if text:
            return float(text)
    return _FALLBACK_TIMESTEP


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the served scene."""

    def __init__(self, root: ET.Element):
        defaults = _Defaults(root)
        joints: dict[str | None, _Joint] = {}
        nq = nv = 0
        for body in root.findall("worldbody"):
            for joint, inherited_class in _walk_body(body, None):
                if joint.tag == "freejoint":
                    attributes, kind = {}, "free"
                else:
                    attributes = defaults.of(joint, "joint", inherited_class)
                    kind = attributes.get("type", "hinge")
                entry = _Joint(joint.get("name"), kind, nq, nv, None, None)
                if "range" in attributes and kind in ("hinge", "slide"):
                    entry.low, entry.high = _two_floats(attributes["range"])
                joints[entry.name] = entry
                nq += _QPOS.get(kind, 1)
                nv += _QVEL.get(kind, 1)

        ranges: list[list[float]] = []
        limited: list[bool] = []
        targets: list[int | None] = []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                joint = joints.get(attributes.get("joint"))
                low, high = -_FLOAT_MAX, _FLOAT_MAX
                is_limited = False
                if "ctrlrange" in attributes:
                    low, high = _two_floats(attributes["ctrlrange"])
                    is_limited = True
                elif joint is not None and joint.low is not None and joint.high is not None:
                    try:
                        inherit = float(attributes.get("inheritrange", 0.0))
                    except (TypeError, ValueError):
                        inherit = 0.0
                    if inherit > 0:
                        low, high = joint.low * inherit, joint.high * inherit
                        is_limited = True
                if str(attributes.get("ctrllimited", "")).lower() in ("false", "0"):
                    is_limited = False
                ranges.append([float(low), float(high)])
                limited.append(is_limited)
                targets.append(None if joint is None else joint.qpos_adr)

        self.opt = _Opt(_timestep(root))
        self.nq, self.nv, self.na = nq, nv, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self._targets = targets
        self._joints = joints

    @classmethod
    def from_xml_path(cls, path: str | Path) -> "MjModel":
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml: str) -> "MjModel":
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)

    def target(self, index: int) -> int | None:
        """The qpos address the actuator drives, when the model names a joint."""
        return self._targets[index]


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model: MjModel):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act: list[float] = []
        self.time = 0.0


def mj_resetData(model: MjModel, data: MjData) -> None:
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model: MjModel, data: MjData) -> None:
    """Placeholder: the stand-in has no derived quantities to compute."""


def mj_step(model: MjModel, data: MjData) -> None:
    """Advance the stand-in one time step: each actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index, address in enumerate(model._targets):
        if address is None or index >= len(data.ctrl):
            continue
        target = float(data.ctrl[index])
        current = float(data.qpos[address])
        data.qvel[address] = (target - current) * _STEP_FRACTION / dt
        data.qpos[address] = current + data.qvel[address] * dt
    data.time += dt


class _MjtState:
    """The ``mujoco.mjtState`` flags the bridge reads: one integration-state flag is enough."""

    mjSTATE_INTEGRATION = 1


def mj_stateSize(model: MjModel, spec: int) -> int:
    """The length of the stand-in integration state: time, qpos, qvel and ctrl."""
    del spec
    return 1 + model.nq + model.nv + model.nu


def mj_getState(model: MjModel, data: MjData, state: object, spec: int) -> None:
    """Copy the stand-in integration state into ``state`` (a list or a numpy array)."""
    del spec
    values = [float(data.time)] + [float(item) for item in data.qpos] + \
             [float(item) for item in data.qvel] + [float(item) for item in data.ctrl]
    state[:] = values  # type: ignore[index]


def mj_setState(model: MjModel, data: MjData, state: object, spec: int) -> None:
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


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class."""

    def __init__(self, **_options: object):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mjtState = _MjtState
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
        self.mj_stateSize = mj_stateSize
        self.mj_getState = mj_getState
        self.mj_setState = mj_setState
