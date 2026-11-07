"""Fake backend of the robo-lab driver: a stand-in for the ``mujoco`` module the bridge imports.

The package is a ``MujocoDriver`` and configuration only.  ``MujocoDriver.make_bridge`` builds an
``mhs.bridge.mujoco.MujocoBridge`` with ``mujoco=native``; the bridge calls ``MjModel.from_xml_path`` on the
card's scene (``assets/trlc_dk1/scene_blocks.xml``), then ``mj_resetData``/``mj_forward``/``mj_step`` and reads
``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the
``data.time``/``qpos``/``qvel``/``ctrl`` arrays.  MuJoCo is not installed and cannot be installed where the gate
runs, so this module supplies exactly those members.

The model shape is read from the MJCF file itself: the XML is parsed in place from the read-only clone and the
``<default>`` classes are resolved, so the actuator control ranges, the joint types and the option timestep are
the card model's values and not constants of this file.  The scene has no ``<include>``; an include would be
reported as an error rather than silently skipped.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, friction, tendon, equality or
actuator constraint, and its step is a placeholder first-order motion of each actuated joint toward its control
value, not the model's implicitfast dynamics.  Those differences are listed in the driver's fidelity ``gaps``.
Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: the library default used when a model sets no <option timestep>; scene_blocks.xml:4 sets none
_DEFAULT_TIMESTEP_S = 0.002
#: placeholder: fraction of the distance to the control value that one fake step closes
_STEP_FRACTION = 0.01
#: qpos and qvel contributions of a MuJoCo joint type; a missing type means "hinge"
_QPOS_WIDTH = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_WIDTH = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _is_true(value):
    """The MJCF boolean spelling MuJoCo accepts for an attribute such as ``ctrllimited``."""
    return str(value).strip().lower() in ("true", "1")


class _Defaults:
    """The MJCF ``<default>`` classes of a model: class inheritance and the per-tag attributes.

    The root ``<default>`` section is the empty-string class, so attributes written directly below it apply to
    every element whose own ``class`` chain reaches it.
    """

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, "")

    def _walk(self, node, inherited):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or inherited
                self._parent.setdefault(name, inherited)
                self._walk(child, name)
            else:
                self._attributes.setdefault(inherited, {}).setdefault(child.tag, {}).update(child.attrib)

    def attributes(self, class_name, tag):
        """The attributes of ``tag`` in a default class, merged from the root class down to ``class_name``."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        merged = {}
        for item in reversed(chain):
            merged.update(self._attributes.get(item, {}).get(tag, {}))
        return merged

    def resolve(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.attributes(element.get("class") or "", tag)
        out.update(element.attrib)
        return out


def _joint_table(worldbody, defaults):
    """``(qpos width, qvel width, {joint name: (qpos index, qvel index)})`` in the model's joint order."""
    qpos = qvel = 0
    by_name = {}
    for element in worldbody.iter():
        if element.tag not in ("joint", "freejoint"):
            continue
        attributes = defaults.resolve(element, "freejoint" if element.tag == "freejoint" else "joint")
        kind = "free" if element.tag == "freejoint" else attributes.get("type", "hinge")
        if kind not in _QPOS_WIDTH:
            raise ValueError(f"unsupported joint type {kind!r} in the MJCF")
        name = attributes.get("name")
        if name is not None:
            by_name[name] = (qpos, qvel)
        qpos += _QPOS_WIDTH[kind]
        qvel += _QVEL_WIDTH[kind]
    return qpos, qvel, by_name


class _Options:
    """``model.opt``: the bridge reads ``timestep`` only."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        if root.findall("include"):
            raise ValueError("the fake does not expand MJCF <include> elements; the served scene is self-contained")
        defaults = _Defaults(root)
        worldbody = root.find("worldbody")
        self.nq, self.nv, joints = _joint_table(worldbody if worldbody is not None else ET.Element("worldbody"),
                                                defaults)
        ranges, limited, qpos_index, qvel_index = [], [], [], []
        actuators = root.find("actuator")
        for element in list(actuators) if actuators is not None else []:
            if element.tag == "default":
                continue
            attributes = defaults.resolve(element, element.tag)
            if "ctrlrange" in attributes:
                low, high = (float(value) for value in attributes["ctrlrange"].split()[:2])
                ranges.append([low, high])
                limited.append(_is_true(attributes["ctrllimited"]) if "ctrllimited" in attributes
                               else low <= high)
            else:
                ranges.append([-_FLOAT_MAX, _FLOAT_MAX])
                limited.append(False)
            target = joints.get(attributes.get("joint"))
            qpos_index.append(target[0] if target is not None else None)
            qvel_index.append(target[1] if target is not None else None)
        timestep = _DEFAULT_TIMESTEP_S
        option = root.find("option")
        if option is not None:
            attributes = defaults.resolve(option, "option")
            if attributes.get("timestep") is not None:
                timestep = float(attributes["timestep"])
        self.opt = _Options(timestep)
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.qpos_index = qpos_index
        self.qvel_index = qvel_index

    @classmethod
    def from_xml_path(cls, path):
        """Load the model from a file of the read-only clone (the bridge passes the card's model path)."""
        return cls(ET.parse(str(Path(path))).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        """Load the model from an XML string; no include is resolved (the served scene has none)."""
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data (the bridge calls this before the first step and on every reset).

    Placeholder: real ``mj_resetData`` copies ``model.qpos0``, which places the scene's free-jointed objects at
    their body positions; this stand-in has no qpos0 and resets every value to zero (a fidelity gap).
    """
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward kinematics, contacts or sensor values."""


def mj_step(model, data):
    """Advance the stand-in one time step: every actuated joint moves toward its control value (placeholder)."""
    dt = float(model.opt.timestep)
    for index in range(model.nu):
        qpos = model.qpos_index[index]
        qvel = model.qvel_index[index]
        if qpos is None or qvel is None:
            continue
        data.qvel[qvel] = (data.ctrl[index] - data.qpos[qpos]) * _STEP_FRACTION / dt
        data.qpos[qpos] += data.qvel[qvel] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends['fake']`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
