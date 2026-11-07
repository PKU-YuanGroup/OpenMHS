"""Stand-in ``mujoco`` module for the ToddlerBot 2XC scene driver.

Why a stand-in: the package is a ``MujocoDriver`` (configuration only), the bridge loads ``mujoco`` when the model is
first opened, and MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).
``backends["fake"]`` is therefore this module object: the bridge calls ``MjModel.from_xml_path`` on the card's MJCF
scene, then ``mj_resetData``/``mj_forward``/``mj_step`` on the data, and reads ``model.opt.timestep``, ``model.nu``,
``model.nq``, ``model.nv``, ``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and
``data.time``/``qpos``/``qvel``/``ctrl``.

The model shape is read from the MJCF text itself, not hard-coded here: ``_load`` parses the XML and expands its
``<include>`` elements, ``_Defaults`` resolves the MJCF default classes, and ``_Model`` takes the joint dimensions, the
actuator control ranges and the option time step from that tree.  The card's scene is
``toddlerbot/descriptions/toddlerbot_2xc/scene.xml`` (line 2-3): it includes ``toddlerbot_2xc.xml``, whose main default
class sets ``<motor ctrlrange="-10 10"/>`` (line 31) and whose actuator block declares 30 motors (lines 562-593), with
the free joint ``torso_freejoint`` on the torso body (line 35).

What this is not: MuJoCo.  It loads no mesh, texture or height field, resolves no contact, equality, tendon or sensor,
applies no gear ratio or actuator dynamics, and its integration is a placeholder motion of each actuated hinge
proportional to its control value.  All of that is listed in the driver's fidelity ``gaps``.  Nothing here talks to a
device.

The numbers below marked ``# placeholder`` are test data of the stand-in, not facts about the model or a device.
"""

import xml.etree.ElementTree as ET
from pathlib import Path

_FLOAT_MAX = 1.7976931348623157e308  # placeholder: the largest finite float, used for an unlimited ctrl range
_TIMESTEP_DEFAULT = 0.002  # placeholder: a MuJoCo library default; the card's scene states no <option timestep>
_VELOCITY_PER_CTRL = 0.01  # placeholder: stand-in joint velocity per unit of control, not a physical coefficient
_QPOS = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}  # placeholder: MuJoCo's joint layout
_QVEL = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}  # placeholder: MuJoCo's joint layout


def _expand(node, base):
    """Replace every ``<include file=...>`` of ``node`` by the children of the included file."""
    index = 0
    while index < len(node):
        child = node[index]
        if child.tag == "include":
            target = (base / str(child.get("file"))).resolve()
            included = ET.parse(str(target)).getroot()
            _expand(included, target.parent)
            node.remove(child)
            for offset, item in enumerate(list(included)):
                node.insert(index + offset, item)
            index += len(included)
        else:
            _expand(child, base)
            index += 1


def _load(path):
    """The MJCF tree of ``path`` with includes expanded (paths relative to the file that names them)."""
    resolved = Path(path).resolve()
    root = ET.parse(str(resolved)).getroot()
    _expand(root, resolved.parent)
    return root


class _Defaults:
    """The MJCF ``<default>`` classes: global attributes, class inheritance and per-tag defaults."""

    def __init__(self, root):
        self._parent = {}
        self._attributes = {}
        self._global = "main"
        sections = root.findall("default")
        for index, section in enumerate(sections):
            name = section.get("class") or "main"
            if index == 0:
                self._global = name
            self._walk(section, name, None)
        self._attributes.setdefault(self._global, {})

    def _walk(self, section, name, parent):
        self._parent.setdefault(name, parent)
        target = self._attributes.setdefault(name, {})
        for child in section:
            if child.tag == "default":
                nested = child.get("class")
                if nested:
                    self._walk(child, nested, name)
            else:
                target.setdefault(child.tag, {}).update(child.attrib)

    def get(self, class_name, tag):
        """The defaults of ``tag`` in ``class_name``, from the global section down the class chain."""
        name = class_name or self._global
        chain = []
        seen = set()
        while name and name not in seen:
            seen.add(name)
            chain.append(name)
            name = self._parent.get(name)
        out = {}
        for item in reversed(chain):
            out.update(self._attributes.get(item, {}).get(tag, {}))
        return out


class _Opt:
    """``model.opt``: the bridge reads only ``timestep``."""

    def __init__(self, timestep):
        self.timestep = float(timestep)


class _Model:
    """``mujoco.MjModel``: the dimensions, actuator ranges and option the bridge reads."""

    def __init__(self, root):
        defaults = _Defaults(root)
        compiler = root.find("compiler")
        autolimits = (compiler is not None and str(compiler.get("autolimits", "false")).lower() in ("true", "1"))

        self.nq, self.nv, self.na = 0, 0, 0
        self.njnt = 0
        self._joint_places = {}
        self._qpos_default = []
        # MuJoCo assigns qpos/qvel slots in joint declaration order (document order under worldbody).
        worldbody = root.find("worldbody")
        parent_of = {child: parent for parent in worldbody.iter() for child in parent} if worldbody is not None else {}
        for element in worldbody.iter() if worldbody is not None else ():
            if element.tag not in ("freejoint", "joint"):
                continue
            kind = "free" if element.tag == "freejoint" else element.get("type", "hinge")
            dim_q, dim_v = _QPOS.get(kind, 1), _QVEL.get(kind, 1)
            name = element.get("name") or f"joint_{self.njnt}"
            self._joint_places[name] = (self.nq, self.nv, kind)
            if kind in ("hinge", "slide"):
                self._qpos_default.append(float(element.get("ref", "0")))
            elif kind == "ball":
                self._qpos_default.extend([1.0, 0.0, 0.0, 0.0])
            else:  # free joint: start at the body pose, as MuJoCo's defaults do
                body = parent_of.get(element)
                position = [float(value) for value in (body.get("pos", "0 0 0") if body is not None else "0 0 0").split()]
                quat = [float(value) for value in (body.get("quat", "1 0 0 0") if body is not None else "1 0 0 0").split()]
                self._qpos_default.extend(position + quat)
            self.nq += dim_q
            self.nv += dim_v
            self.njnt += 1

        section = root.find("actuator")
        ranges, limited, targets = [], [], []
        for node in list(section) if section is not None else []:
            attributes = defaults.get(node.get("class"), node.tag)
            ctrlrange = node.get("ctrlrange") or attributes.get("ctrlrange")
            if ctrlrange:
                low, high = (float(value) for value in ctrlrange.split()[:2])
            else:
                low, high = -_FLOAT_MAX, _FLOAT_MAX
            explicit = node.get("ctrllimited") or attributes.get("ctrllimited")
            if explicit is not None:
                is_limited = str(explicit).lower() in ("true", "1")
            else:
                is_limited = bool(autolimits and ctrlrange)
            ranges.append([low, high])
            limited.append(is_limited)
            joint = node.get("joint")
            place = self._joint_places.get(joint) if joint else None
            targets.append(place)

        timestep = _TIMESTEP_DEFAULT
        for option in root.iter("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))

        self.opt = _Opt(timestep)
        self.nu = len(ranges)
        self.actuator_ctrlrange = ranges
        self.actuator_ctrllimited = limited
        #: The qpos/qvel slot each actuator drives (a placeholder first-order target, not MuJoCo's actuator model)
        self.actuator_joint = targets

    @classmethod
    def from_xml_path(cls, path):
        return cls(_load(path))

    @classmethod
    def from_xml_string(cls, xml):
        root = ET.fromstring(xml)
        _expand(root, Path.cwd())
        return cls(root)


class _Data:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model._qpos_default)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Reset the data to the stand-in defaults (the bridge calls this before the first step and on reset)."""
    data.qpos[:] = list(model._qpos_default)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in has no derived quantities to compute."""
    del model, data


def mj_step(model, data):
    """Advance the stand-in one time step (placeholder dynamics, not MuJoCo's equations of motion)."""
    dt = float(model.opt.timestep)
    for index, place in enumerate(model.actuator_joint):
        if place is None:
            continue
        qpos_index, qvel_index, kind = place
        if kind in ("hinge", "slide"):
            data.qvel[qvel_index] = data.ctrl[index] * _VELOCITY_PER_CTRL
            data.qpos[qpos_index] += data.qvel[qvel_index] * dt
    data.time += dt


class FakeMujoco:
    """The stand-in ``mujoco`` module object; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    def __init__(self, **_options):
        self.MjModel = _Model
        self.MjData = _Data
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
