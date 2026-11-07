"""Package-local stand-in for the ``mujoco`` module of the multipanda dual scene.

``MujocoDriver.make_bridge`` builds ``mhs.bridge.mujoco.MujocoBridge`` with this
object as its ``mujoco=`` module.  The bridge calls ``MjModel.from_xml_path`` on
the card's first model (``franka_description/mujoco/franka/dual_scene.xml``),
then ``mj_resetData`` / ``mj_forward`` / ``mj_step`` and reads ``opt.timestep``,
``nu``, ``actuator_ctrlrange`` and ``actuator_ctrllimited``, plus ``data.time``,
``data.qpos``, ``data.qvel``, ``data.ctrl`` and ``data.act``.

Model review (2026-11-05): the stand-in used to leave the 28 position and
velocity servo channels, which declare no ctrlrange, out of its control vector
(16 channels in place of the model's 44, in a different order).  It now reports
every actuator of the model in document order, the servos as not ctrl-limited
(``ctrlrange`` 0 0, ``ctrllimited`` false, as MuJoCo compiles an actuator
without a ctrlrange), and restores the model's qpos0 on reset.

MuJoCo is not installed where the gate runs, so this module supplies exactly
those members.  The model shape is read from the MJCF and its ``<include>``
files, with the ``<default>`` class chain resolved, so the actuator control
ranges and the joint dimensions are the model's values rather than constants of
this file.  The integrator is a placeholder: it moves each actuated joint toward
its command, but it is not MuJoCo physics (no mesh, inertia, contact, friction,
tendon, equality or gravity compensation).  The driver's fidelity ``gaps`` list
those differences.  Nothing here talks to a device.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

# placeholder: MuJoCo's library default timestep, used only when the model does
# not declare <option timestep=...>.  The served dual scene declares 0.002 in
# mj_dual.xml, so this value is not used for that model.
_DEFAULT_TIMESTEP_S = 0.002
# placeholder: fraction of a position error closed by one fake step
_POSITION_FRACTION = 0.02
# placeholder: fraction of a velocity error closed by one fake step
_VELOCITY_FRACTION = 0.02
# placeholder: velocity gain of a torque command per second of fake time
_TORQUE_GAIN = 0.5

# MuJoCo joint-type widths in qpos and qvel.
_QPOS_SIZE = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_SIZE = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node: ET.Element, base: Path, model_dir: Path, depth: int = 0) -> None:
    """Replace every ``<include file=...>`` below ``node`` with the included children."""
    if depth > 8:
        raise ValueError("the MJCF include tree is deeper than 8")
    children: list[ET.Element] = []
    for child in list(node):
        if child.tag == "include":
            name = child.get("file")
            target = (base / str(name)).resolve()
            if not target.is_file():
                target = (model_dir / str(name)).resolve()
            if not target.is_file():
                raise FileNotFoundError(f"the MJCF include {name!r} is not below {base} or {model_dir}")
            included = ET.parse(str(target)).getroot()
            _expand(included, target.parent, model_dir, depth + 1)
            children.extend(list(included))
        else:
            _expand(child, base, model_dir, depth)
            children.append(child)
    for child in list(node):
        node.remove(child)
    node.extend(children)


def _load(path: str | Path) -> ET.Element:
    """The MJCF tree of ``path`` with its includes expanded."""
    model = Path(path).resolve()
    tree = ET.parse(str(model)).getroot()
    _expand(tree, model.parent, model.parent)
    return tree


def _range(text: str | None) -> list[float] | None:
    if text is None:
        return None
    parts = str(text).split()
    if len(parts) < 2:
        return None
    return [float(parts[0]), float(parts[1])]


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and per-tag attributes."""

    def __init__(self, root: ET.Element):
        self._parent: dict[str, str | None] = {}
        self._attributes: dict[str, dict[str, dict[str, str]]] = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node: ET.Element, parent: str | None) -> None:
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name is not None:
                    self._parent[name] = parent
                self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def of(self, element: ET.Element, tag: str) -> dict[str, str]:
        """The defaults of ``element``'s class for ``tag``, overridden by its own attributes."""
        chain: list[str] = []
        name = element.get("class")
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out: dict[str, str] = {}
        for item in reversed(chain):
            out.update(self._attributes[item].get(tag, {}))
        out.update(element.attrib)
        return out


class _Option:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep: float):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree."""

    def __init__(self, root: ET.Element):
        defaults = _Defaults(root)

        timestep = _DEFAULT_TIMESTEP_S
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Option(timestep)

        # Tendons are named fixed combinations of joints; the gripper channels
        # drive a tendon rather than one joint.
        self.tendons: dict[str, list[tuple[str, float]]] = {}
        for section in root.findall("tendon"):
            for element in section:
                if element.tag != "fixed":
                    continue
                name = element.get("name")
                if name is None:
                    continue
                self.tendons[name] = [
                    (joint.get("joint"), float(joint.get("coef", "1")))
                    for joint in element.findall("joint") if joint.get("joint") is not None
                ]

        # Joint order follows the document order of the world bodies, which is
        # the order MuJoCo uses for qpos/qvel.
        self.joint_qpos: dict[str, int] = {}
        self.joint_qvel: dict[str, int] = {}
        self.joint_range: dict[str, list[float]] = {}
        # qpos0 as MuJoCo defines it: a free joint starts at its body's pos and
        # quat, a ball joint at the identity quaternion, a hinge or slide at its
        # ref (0 when the MJCF states none).
        owner: dict[ET.Element, ET.Element] = {}
        for body in root.iter("body"):
            for joint in body.findall("joint"):
                owner[joint] = body
        qpos0: list[float] = []
        qpos, qvel = 0, 0
        for worldbody in root.findall("worldbody"):
            for joint in worldbody.iter("joint"):
                attributes = defaults.of(joint, "joint")
                kind = attributes.get("type", "hinge")
                name = joint.get("name")
                if name is not None:
                    self.joint_qpos[name] = qpos
                    self.joint_qvel[name] = qvel
                    joint_range = _range(attributes.get("range"))
                    if joint_range is not None:
                        self.joint_range[name] = joint_range
                qpos += _QPOS_SIZE[kind]
                qvel += _QVEL_SIZE[kind]
                if kind == "free":
                    body = owner.get(joint)
                    position_text = (body.get("pos") if body is not None else None) or "0 0 0"
                    quaternion_text = (body.get("quat") if body is not None else None) or "1 0 0 0"
                    position = [float(item) for item in position_text.split()][:3]
                    quaternion = [float(item) for item in quaternion_text.split()][:4]
                    qpos0.extend(position + quaternion)
                elif kind == "ball":
                    qpos0.extend([1.0, 0.0, 0.0, 0.0])
                else:
                    qpos0.append(float(attributes.get("ref", "0")))
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.qpos0 = qpos0

        # Actuator order is the document order of the <actuator> sections, as in
        # MuJoCo.  The dual scene has 44 channels: per arm seven torque motors,
        # seven position servos, seven velocity servos and one gripper.  Only the
        # torque and gripper channels declare a ctrlrange; MuJoCo compiles the
        # servos as not ctrl-limited (ctrlrange 0 0), and so does this stand-in.
        self.actuators: list[dict[str, object]] = []
        ranges: list[list[float]] = []
        limited: list[bool] = []
        for section in root.findall("actuator"):
            for element in section:
                attributes = defaults.of(element, element.tag)
                ctrlrange = _range(attributes.get("ctrlrange"))
                ctrllimited = attributes.get("ctrllimited")
                is_limited = (ctrlrange is not None
                              and (ctrllimited is None or ctrllimited.lower() != "false"))
                targets: list[tuple[str, float]] = []
                if attributes.get("joint") is not None:
                    targets.append((str(attributes["joint"]), 1.0))
                elif attributes.get("tendon") is not None:
                    targets.extend(self.tendons.get(str(attributes["tendon"]), []))
                actuator = {
                    "name": element.get("name"),
                    "tag": element.tag,
                    "targets": targets,
                }
                self.actuators.append(actuator)
                if is_limited:
                    ranges.append([ctrlrange[0], ctrlrange[1]])
                    limited.append(True)
                else:
                    ranges.append([0.0, 0.0])
                    limited.append(False)
        self.nu = len(self.actuators)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited

    @classmethod
    def from_xml_path(cls, path: str | Path) -> "MjModel":
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml: str) -> "MjModel":
        root = ET.fromstring(xml)
        _expand(root, Path.cwd(), Path.cwd())
        return cls(root)


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes."""

    def __init__(self, model: MjModel):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act: list[float] = []
        self.time = 0.0


def mj_resetData(model: MjModel, data: MjData) -> None:
    """Reset the data arrays to the model defaults (qpos0); the bridge calls this before the first step and on reset."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model: MjModel, data: MjData) -> None:
    """Placeholder: the stand-in derives no forward quantities."""


def mj_step(model: MjModel, data: MjData) -> None:
    """Advance the stand-in one time step toward the commanded actuator values.

    This is a placeholder first-order motion, not MuJoCo's dynamics.  Position
    and general actuators move their joint toward the command, velocity
    actuators move qvel toward it, and motor actuators add a small qvel
    increment.  All model channels are applied independently.
    """
    dt = float(model.opt.timestep)
    positions: dict[int, float] = {}
    velocities: dict[int, float] = {}
    torques: dict[int, float] = {}
    for index, actuator in enumerate(model.actuators):
        value = float(data.ctrl[index])
        low, high = model.actuator_ctrlrange[index]
        is_limited = bool(model.actuator_ctrllimited[index]) and high > low
        normalized = (value - low) / (high - low) if is_limited else value
        tag = str(actuator["tag"])
        for joint, coefficient in actuator["targets"]:  # type: ignore[union-attr]
            address = model.joint_qpos.get(joint)
            if address is None:
                continue
            if tag == "position":
                positions[address] = coefficient * value
            elif tag == "velocity":
                velocities[address] = coefficient * value
            elif tag in ("general", "intvelocity", "damper"):
                joint_range = model.joint_range.get(joint)
                if joint_range is not None:
                    positions[address] = joint_range[0] + normalized * (joint_range[1] - joint_range[0])
                else:
                    positions[address] = coefficient * value
            else:
                torques[address] = torques.get(address, 0.0) + coefficient * value
    for address, target in positions.items():
        data.qpos[address] += (target - data.qpos[address]) * _POSITION_FRACTION
    for address, target in velocities.items():
        data.qvel[address] += (target - data.qvel[address]) * _VELOCITY_FRACTION
    for address, force in torques.items():
        data.qvel[address] += force * _TORQUE_GAIN * dt
    for address in range(min(model.nq, model.nv)):
        data.qpos[address] += data.qvel[address] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object named by ``backends["fake"]``."""

    __version__ = "fake-mjcf-parser"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
