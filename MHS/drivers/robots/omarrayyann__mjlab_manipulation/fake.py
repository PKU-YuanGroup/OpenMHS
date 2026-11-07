"""Stand-in ``mujoco`` module for gh.omarrayyann/mjlab_manipulation: the Droid MJCF model.

Why a stand-in: this package is a ``MujocoDriver`` (configuration only), the bridge imports ``mujoco`` lazily, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
therefore names this module object.  The bridge calls ``MjModel.from_xml_path`` on the card's model
(``src/mjlab_manipulation/robots/droid/xmls/droid.xml``), then ``mj_resetData``, ``mj_forward`` and ``mj_step`` on
the data, and reads ``model.opt.timestep``, ``model.nu``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited``
and the ``data.time`` / ``data.qpos`` / ``data.qvel`` / ``data.ctrl`` arrays.

The model shape comes from the MJCF text, not from hard-coded numbers: ``_load`` parses the XML, ``_Defaults``
resolves the default classes (the ``arm`` class gives its position actuators ``inheritrange``, so their control range
follows the target joint range), and ``_Model`` builds the joint dimensions, the actuator targets and control ranges
and the option time step.  The Droid model declares seven hinge joints (``joint_1``..``joint_7``, droid.xml:96-143)
and seven position actuators (droid.xml:160-167); each joint carries a finite range and the ``arm`` default class
gives every position actuator ``inheritrange="1"`` (droid.xml:13-15), so the bridge derives a finite control range for
every ``action.ctrl`` element.

What this is not: MuJoCo.  It loads no mesh or texture, resolves no contact, equality, tendon or sensor constraint, and
its integration is a placeholder motion of each actuated joint, not the engine's dynamics.  The differences are listed
in the fidelity ``gaps`` of driver.py.  Nothing here talks to a device.
"""

import types
import xml.etree.ElementTree as ET

_FLOAT_MAX = 1.7976931348623157e308
#: placeholder: MuJoCo's library default when a model sets no <option timestep>; Droid sets only the integrator
_TIMESTEP_DEFAULT = 0.002
#: placeholder: fraction of the control target that one fake step applies to an actuated joint
_CTRL_TO_VELOCITY = 0.05
#: qpos and qvel widths per joint type; a missing type means a hinge
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _load(path):
    """The MJCF tree of ``path``."""
    return ET.parse(str(path)).getroot()


class _Defaults:
    """The MJCF ``<default>`` classes: class inheritance and per-tag attribute defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        for section in root.findall("default"):
            self._walk(section, None)

    def _walk(self, node, parent):
        for child in node:
            if child.tag == "default":
                name = child.get("class")
                if name is None:
                    self._walk(child, parent)
                else:
                    self._parent[name] = parent
                    self._walk(child, name)
            elif parent is not None:
                self._attributes.setdefault(parent, {}).setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The attributes of ``tag`` in a default class, following the class chain from the root down."""
        chain, name = [], class_name
        while name is not None and name not in chain:
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out

    def of(self, element, tag):
        """The defaults of ``element``'s class for ``tag``, overridden by the element's own attributes."""
        out = self.get(element.get("class"), tag)
        out.update(element.attrib)
        return out


def _range_of(attributes):
    """A ``(low, high)`` pair from a ``range``/``ctrlrange`` attribute, or ``None`` when it is absent."""
    value = attributes.get("range")
    if value is None:
        return None
    parts = value.split()
    if len(parts) < 2:
        return None
    low, high = float(parts[0]), float(parts[1])
    return (low, high) if low <= high else None


class _Opt:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class _Model:
    """The ``mujoco.MjModel`` members the bridge reads, derived from the MJCF tree of the card's model."""

    def __init__(self, root):
        defaults = _Defaults(root)
        joints = {}
        free_at = []
        qpos = qvel = count = 0
        # Only worldbody joints are real; a <joint> inside <default> is a declaration, not a body joint.
        for world in root.findall("worldbody"):
            for element in world.iter():
                if element.tag == "freejoint":
                    kind = "free"
                elif element.tag == "joint":
                    kind = defaults.of(element, "joint").get("type", "hinge")
                else:
                    continue
                if kind not in _QPOS:
                    raise ValueError(f"unsupported joint type {kind!r}")
                name = element.get("name")
                if name:
                    joints[name] = {"qpos": qpos, "qvel": qvel,
                                    "range": _range_of(defaults.of(element, "joint"))}
                if kind == "free":
                    free_at.append(qpos)
                qpos += _QPOS[kind]
                qvel += _QVEL[kind]
                count += 1

        ranges, limited, places = [], [], []
        for section in root.findall("actuator"):
            for element in section:
                if element.tag == "default":
                    continue
                attributes = defaults.of(element, element.tag)
                control_range = _range_of(attributes)
                inherit = attributes.get("inheritrange")
                target = joints.get(attributes.get("joint"))
                if control_range is not None:
                    low, high = control_range
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                elif inherit is not None and target is not None and target["range"] is not None:
                    # The default class gives this position actuator inheritrange; the control range follows
                    # the target joint range, scaled around its centre (MuJoCo's inheritrange semantics).
                    low, high = target["range"]
                    factor = float(inherit)
                    centre, half = (low + high) / 2.0, (high - low) / 2.0
                    low, high = centre - factor * half, centre + factor * half
                    is_limited = str(attributes.get("ctrllimited", "true")).lower() not in ("false", "0")
                else:
                    low, high = -_FLOAT_MAX, _FLOAT_MAX
                    is_limited = False
                ranges.append([low, high])
                limited.append(is_limited)
                places.append((target["qpos"], target["qvel"]) if target is not None else None)

        timestep = _TIMESTEP_DEFAULT
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nq, self.nv, self.na = qpos, qvel, 0
        self.njnt = count
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: placeholder: the qpos/qvel slots of each actuator's joint target; no MuJoCo transmission mapping
        self.actuator_joint = places
        #: placeholder: the qpos offset of each free joint, whose identity quaternion starts at offset + 3
        self.free_qpos = free_at

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class _Data:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0
        for offset in model.free_qpos:
            self.qpos[offset + 3] = 1.0                 # placeholder: identity orientation of a free joint


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = [0.0] * model.nq
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.time = 0.0
    for offset in model.free_qpos:
        data.qpos[offset + 3] = 1.0                     # placeholder: identity orientation of a free joint


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one step: each actuated joint moves by ``ctrl * _CTRL_TO_VELOCITY`` (placeholder)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index = place
        data.qvel[qvel_index] = data.ctrl[index] * _CTRL_TO_VELOCITY
        data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


def fake_mujoco(**_options):
    """The backend factory: an object with the ``mujoco`` module members the bridge uses."""
    return types.SimpleNamespace(
        MjModel=_Model,
        MjData=_Data,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_step=mj_step,
    )
