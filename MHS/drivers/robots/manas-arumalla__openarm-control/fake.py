"""Fake backend of the OpenArm unscrew driver: a stand-in ``mujoco`` module for the scene.

Why a stand-in module: the acceptance gate runs without the MuJoCo engine, and a ``MujocoDriver`` is configuration
only.  ``backends["fake"]`` therefore names the factory below, whose result has the small part of the ``mujoco`` API
the bridge calls: ``MjModel.from_xml_path`` / ``from_xml_string``, ``MjData``, ``mj_resetData``, ``mj_forward``,
``mj_step`` and the integration-state snapshot functions.

The model shape is read from the pinned clone's MJCF text, never invented: ``_load`` parses a scene, expands its
``<include>`` elements, follows ``<asset><model>`` and ``<attach>`` references, resolves the inherited ``<default>``
classes and takes the integration step, the coordinate counts and each actuator's ``ctrlrange`` from that tree.  The
served scene is ``v2/openarm_mujoco_v2/unscrew_scene.xml``: it attaches ``openarm_pedestal.xml``, which attaches
``openarm_v20_bimanual.xml``, and adds the cap turn and lift joints plus the cap lift actuator.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, tendon or equality constraint, and its
integration is a placeholder first-order motion of each actuated joint toward its control target.  The driver's
fidelity ``gaps`` state every difference.  Nothing here talks to a device or to the real engine.
"""

from __future__ import annotations

import copy
import re
import types
import xml.etree.ElementTree as ET
from pathlib import Path

#: Sentinel for an actuator with no ctrlrange; not a model bound.
_FLOAT_MAX = 1.7976931348623157e308

#: Placeholder: MuJoCo's library default when an MJCF sets no <option timestep>.  The served scene declares
#: 0.002 s (v2/openarm_mujoco_v2/unscrew_scene.xml:18), so this value is not used for it.
_FALLBACK_TIMESTEP = 0.002

#: Placeholder: fraction of the distance to its control target that one fake step moves a joint.
_STEP_FRACTION = 0.02

#: qpos and dof contributions of the MJCF joint types; a joint with no ``type`` is a hinge.
_JOINT_SIZES = {"free": (7, 6), "ball": (4, 3), "hinge": (1, 1), "slide": (1, 1)}

#: Python's ElementTree rejects a double hyphen inside a comment; the served scene has one in its first comment
#: (unscrew_scene.xml:7), so the stand-in normalizes comment bodies before parsing.  It changes no element or value.
_COMMENT = re.compile(r"<!--(.*?)-->", re.DOTALL)


def _parse_file(path: str | Path) -> ET.Element:
    """Parse an MJCF file after normalizing the comment bodies Python's XML parser rejects."""
    text = Path(path).read_text(encoding="utf-8")
    text = _COMMENT.sub(lambda match: "<!--" + match.group(1).replace("--", "- -") + "-->", text)
    return ET.fromstring(text)


def _expand_includes(node: ET.Element, base: Path, depth: int = 0) -> None:
    """Replace every ``<include file=...>`` of ``node`` with the children of the included file."""
    if depth > 8:
        raise ValueError(f"the MJCF at <{node.tag}> nests includes more than 8 deep")
    children = []
    for child in list(node):
        if child.tag == "include":
            target = base / str(child.get("file"))
            included = _parse_file(target)
            _expand_includes(included, target.resolve().parent, depth + 1)
            children.extend(list(included))
        else:
            _expand_includes(child, base, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


class _Defaults:
    """The MJCF ``<default>`` classes of one model file: class inheritance and per-tag attributes."""

    def __init__(self, root: ET.Element):
        self._tables: dict[str, dict[str, dict[str, str]]] = {}
        for section in root.findall("default"):
            self._walk(section, "main")

    def _walk(self, node: ET.Element, parent: str) -> None:
        name = node.get("class") or parent
        table = copy.deepcopy(self._tables.get(parent, {}))
        for item in node:
            if item.tag != "default":
                table.setdefault(item.tag, {}).update(item.attrib)
        self._tables[name] = table
        for item in node:
            if item.tag == "default":
                self._walk(item, name)

    def of(self, element: ET.Element, tag: str) -> dict[str, str]:
        """The class defaults of ``tag``, overridden by the element's own attributes."""
        table = self._tables.get(element.get("class") or "main", {})
        attributes = dict(table.get(tag, {}))
        attributes.update(element.attrib)
        return attributes


class _Doc:
    """One parsed MJCF file and the sibling files its ``<asset><model>`` elements name."""

    def __init__(self, path: Path, cache: dict[Path, "_Doc"]):
        self.path = path.resolve()
        root = _parse_file(self.path)
        _expand_includes(root, self.path.parent)
        self.root = root
        self.defaults = _Defaults(root)
        self._cache = cache
        self.models: dict[str, Path] = {}
        for section in root.findall("asset"):
            for element in section:
                if element.tag == "model":
                    name, file = element.get("name"), element.get("file")
                    if name and file:
                        self.models[name] = (self.path.parent / file).resolve()

    def child(self, name: str | None) -> "_Doc":
        path = self.models.get(str(name))
        if path is None:
            raise ValueError(f"the MJCF {self.path.name} has no model asset named {name!r}")
        if path not in self._cache:
            self._cache[path] = _Doc(path, self._cache)
        return self._cache[path]


class _Collector:
    """The flattened coordinate table and actuator list of a scene and its attached models."""

    def __init__(self):
        self.nq = 0
        self.nv = 0
        self.joints: dict[str, tuple[int, int]] = {}
        self.actuators: list[dict[str, object]] = []

    def add_joint(self, doc: _Doc, element: ET.Element) -> None:
        if element.tag == "freejoint":
            kind = "free"
        else:
            kind = doc.defaults.of(element, "joint").get("type", "hinge")
        qpos_size, dof_size = _JOINT_SIZES.get(kind, (1, 1))
        name = element.get("name")
        if name:
            self.joints[name] = (self.nq, self.nv)
        self.nq += qpos_size
        self.nv += dof_size

    def add_actuator(self, doc: _Doc, element: ET.Element) -> None:
        attributes = doc.defaults.of(element, element.tag)
        text = attributes.get("ctrlrange")
        if text:
            low, high = (float(item) for item in text.split()[:2])
            limited = attributes.get("ctrllimited", "true").lower() not in ("false", "0")
        else:
            low, high, limited = -_FLOAT_MAX, _FLOAT_MAX, False
        self.actuators.append({"range": [low, high], "limited": limited,
                               "joint": attributes.get("joint")})


def _walk_joints(doc: _Doc, node: ET.Element, collector: _Collector, ancestors: tuple[Path, ...]) -> None:
    for child in node:
        if child.tag == "attach":
            attached = doc.child(child.get("model"))
            if attached.path in ancestors:
                raise ValueError(f"the MJCF attach graph loops through {attached.path}")
            _walk_doc(attached, collector, "joints", ancestors + (attached.path,))
        elif child.tag in ("joint", "freejoint"):
            collector.add_joint(doc, child)
        else:
            _walk_joints(doc, child, collector, ancestors)


def _walk_actuators(doc: _Doc, node: ET.Element, collector: _Collector, ancestors: tuple[Path, ...]) -> None:
    for child in node:
        if child.tag == "attach":
            attached = doc.child(child.get("model"))
            if attached.path in ancestors:
                raise ValueError(f"the MJCF attach graph loops through {attached.path}")
            _walk_doc(attached, collector, "actuators", ancestors + (attached.path,))
        else:
            _walk_actuators(doc, child, collector, ancestors)


def _walk_doc(doc: _Doc, collector: _Collector, mode: str, ancestors: tuple[Path, ...]) -> None:
    """Walk a model in document order: an ``<attach>`` inserts the attached model at its element."""
    for section in doc.root:
        if section.tag == "worldbody":
            if mode == "joints":
                _walk_joints(doc, section, collector, ancestors)
            else:
                _walk_actuators(doc, section, collector, ancestors)
        elif mode == "actuators" and section.tag == "actuator":
            for element in section:
                if element.tag != "default":
                    collector.add_actuator(doc, element)


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


class _Model:
    """The stand-in ``mujoco.MjModel``: dimensions, time step and actuator control ranges of the MJCF tree."""

    def __init__(self, doc: _Doc):
        collector = _Collector()
        _walk_doc(doc, collector, "joints", (doc.path,))
        _walk_doc(doc, collector, "actuators", (doc.path,))
        self.opt = _Opt(_timestep(doc.root))
        self.nq, self.nv, self.nu = collector.nq, collector.nv, len(collector.actuators)
        self.actuator_ctrlrange = [list(item["range"]) for item in collector.actuators]
        self.actuator_ctrllimited = [bool(item["limited"]) for item in collector.actuators]
        self._targets = [collector.joints.get(str(item["joint"])) for item in collector.actuators]

    @classmethod
    def from_xml_path(cls, path: str | Path) -> "_Model":
        cache: dict[Path, _Doc] = {}
        resolved = Path(path).resolve()
        cache[resolved] = _Doc(resolved, cache)
        return cls(cache[resolved])

    @classmethod
    def from_xml_string(cls, xml: str) -> "_Model":
        text = _COMMENT.sub(lambda match: "<!--" + match.group(1).replace("--", "- -") + "-->", xml)
        root = ET.fromstring(text)
        _expand_includes(root, Path.cwd())
        cache: dict[Path, _Doc] = {}
        doc = _Doc.__new__(_Doc)
        doc.path = Path.cwd() / "model.xml"
        doc.root = root
        doc.defaults = _Defaults(root)
        doc._cache = cache
        doc.models = {}
        return cls(doc)

    def target(self, index: int) -> tuple[int, int] | None:
        """The ``(qpos address, dof address)`` the actuator drives, if the model names a joint."""
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
    """Reset the data arrays to the stand-in model defaults (zero pose, velocity and control)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act = []
    data.time = 0.0


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
