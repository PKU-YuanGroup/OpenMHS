"""Stand-in ``mujoco`` module for the Unitree G1 29-DoF MuJoCo driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge imports the ``mujoco`` module when
the model is first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network,
no pip).  ``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_string`` on the
patched XML the driver builds from the card's model (``robot/g1_29dof/g1_29dof.xml``), then
``mj_resetData``/``mj_forward``/``mj_step`` on the data and reads ``model.opt.timestep``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and ``data.time``/``qpos``/``qvel``/``ctrl``/``act``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``MjModel`` takes the qpos/qvel
dimensions, the joint/qpos addresses, the 29 actuator control ranges and the option time step from that tree.  The
driver's patched XML already drops the contact block, injects the floor plane and writes the upstream SIM_DT
(0.0005 s), so the fake publishes the same dimensions and control ranges the real bridge would derive.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no inertia, contact, friction, tendon, equality or
actuator constraint, and it does not integrate the free base. Its step uses each motor control as an effort with
placeholder unit inverse inertia, not as a position target or as the engine's dynamics; every difference is listed in the driver's
fidelity ``gaps``.  Nothing here talks to a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>
_TIMESTEP_DEFAULT = 0.002
#: placeholder: inverse inertia for the synthetic effort response, not a model-derived joint inertia
_INVERSE_INERTIA = 1.0
#: qpos and qvel contributions of a joint type in MuJoCo's layout; a missing type means "hinge"
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _expand(node, base, depth=0):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included file."""
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


def _load_path(path):
    """The MJCF tree of ``path`` with its includes expanded (paths relative to the file that names them)."""
    model = Path(path).resolve()
    root = ET.parse(str(model)).getroot()
    _expand(root, model.parent)
    return root


def _load_text(xml):
    """The MJCF tree of an XML string with its includes expanded relative to the current directory."""
    root = ET.fromstring(xml)
    _expand(root, Path.cwd())
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and the per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class") or parent
                if name is not None:
                    self._parent[name] = parent
                self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` in a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name in self._attributes and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes[item].get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        qpos = qvel = 0
        joint_place = {}
        for world in root.findall("worldbody"):
            for element in world.iter():
                if element.tag == "freejoint":
                    joint_place[element.get("name") or "freejoint"] = (qpos, qvel, "free")
                    qpos += _QPOS["free"]
                    qvel += _QVEL["free"]
                elif element.tag == "joint":
                    kind = defaults.of(element, "joint").get("type", "hinge")
                    if kind not in _QPOS:
                        raise ValueError(f"unsupported joint type {kind!r}")
                    name = element.get("name")
                    if name:
                        joint_place[name] = (qpos, qvel, kind)
                    qpos += _QPOS[kind]
                    qvel += _QVEL[kind]

        ranges, limited, places = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                control_range = attributes.get("ctrlrange")
                if control_range is not None:
                    low, high = (float(value) for value in control_range.split()[:2])
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                joint = attributes.get("joint")
                places.append(joint_place.get(joint) if joint else None)

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        self.actuator_joint = places
        #: placeholder: the free joint starts at the body's model position and the identity quaternion
        self.qpos0 = [0.0] * qpos
        for body in root.iter("body"):
            if body.find("freejoint") is not None:
                self.qpos0[0:3] = [float(value) for value in (body.get("pos") or "0 0 0").split()[:3]]
                self.qpos0[3] = 1.0
                break

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load_path(path))

    @classmethod
    def from_xml_string(cls, xml):
        return cls(_load_text(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the model defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in derives no forward quantities."""


def mj_step(model, data):
    """Advance the stand-in with effort-driven acceleration and placeholder unit inverse inertia."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_addr, qvel_addr, _kind = place
        if qpos_addr >= len(data.qpos) or qvel_addr >= len(data.qvel) or index >= len(data.ctrl):
            continue
        data.qvel[qvel_addr] += data.ctrl[index] * _INVERSE_INERTIA * dt
        data.qpos[qpos_addr] += data.qvel[qvel_addr] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.__version__ = "fake"
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
