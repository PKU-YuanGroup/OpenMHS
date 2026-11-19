"""Fake ``mujoco`` module of the one_policy_to_run_them_all driver: a pure Python stand-in for the engine.

Why a stand-in: the driver is configuration only (a ``MujocoDriver``), the bridge imports ``mujoco`` on first use, and
MuJoCo is neither installed nor installable where the acceptance gate runs (no network, no pip).  ``backends["fake"]``
is therefore the module object this file provides: the bridge calls ``MjModel.from_xml_path`` on the card's model
(``one_policy_to_run_them_all/environments/anymal_b/data/anymal_b.xml``), then ``mj_resetData``, ``mj_forward`` and
``mj_step`` on it, and reads ``model.opt.timestep``, ``model.nq``, ``model.nv``, ``model.nu``,
``model.actuator_ctrlrange``, ``model.actuator_ctrllimited`` and the ``data.time``/``qpos``/``qvel``/``ctrl``/``act``
arrays.

The shape (joint order and kinds, the free base, the twelve torque motors and their default ctrlrange) is parsed from
the MJCF itself, so the derived contract comes from the card's model, not from constants of this file.  The integration
is a placeholder: each actuated hinge takes a velocity from a fixed gain times its control value and the free base is
held where the model puts it.  That is not MuJoCo's physics; the driver's fidelity ``gaps`` say so.  Nothing here talks
to a physical robot.
"""

import xml.etree.ElementTree as ET

#: placeholder: MuJoCo's own default model timestep when the MJCF has no <option timestep>; this model states none.
_DEFAULT_TIMESTEP = 0.002
#: placeholder: velocity per unit of control for one fake step (the model's motors take a torque, not a velocity).
_CONTROL_GAIN = 1e-3
#: qpos and qvel dimensions by MJCF joint type; a missing type means "hinge".
_QPOS_DIM = {"free": 7, "ball": 4, "hinge": 1, "slide": 1}
_QVEL_DIM = {"free": 6, "ball": 3, "hinge": 1, "slide": 1}


def _default_classes(root):
    """The MJCF default table: class name -> tag -> attributes, resolved through the nested <default> tree.

    A nested <default class="x"> inherits the per-tag attributes of its parent class; a later child element of the
    same tag overrides only the attributes it states.  The model's motors take their ctrlrange from the root (main)
    default, while its joints take type, damping and range from the body's ``childclass="anymal_b"``.
    """

    classes = {}
    main = None
    for child in root:
        if child.tag == "default":
            if main is not None:
                raise ValueError("the MJCF has more than one top-level <default> element")
            main = child

    def walk(node, name, inherited):
        table = {tag: dict(attributes) for tag, attributes in inherited.items()}
        for child in node:
            if child.tag == "default":
                continue
            table.setdefault(child.tag, {}).update(child.attrib)
        classes[name] = table
        for child in node:
            if child.tag == "default":
                child_name = child.get("class")
                if child_name:
                    walk(child, child_name, table)

    walk(main if main is not None else ET.Element("default"), "main", {})
    return classes


def _effective(tag, element, inherited_class, classes):
    """The attributes of ``element`` with the defaults of its class (``class``, else the inherited name) applied."""

    class_name = element.get("class") or inherited_class or "main"
    table = classes.get(class_name)
    if table is None:
        raise ValueError(f"the MJCF names the unknown default class {class_name!r} for <{tag}>")
    return {**table.get(tag, {}), **element.attrib}, class_name


def _floats(text, count, default):
    return [float(value) for value in (text or default).split()[:count]]


def _collect_joints(root, classes):
    """The joints in document order with their qpos/qvel offsets, plus the model dimensions."""

    joints = []
    qpos_size = 0
    qvel_size = 0

    def add_joint(kind, attributes, body):
        nonlocal qpos_size, qvel_size
        entry = {"kind": kind, "attributes": attributes, "body": body,
                 "qpos_offset": qpos_size, "qvel_offset": qvel_size}
        joints.append(entry)
        qpos_size += _QPOS_DIM[kind]
        qvel_size += _QVEL_DIM[kind]

    def walk_body(body, child_class):
        child_class = body.get("childclass", child_class)
        for child in body:
            if child.tag == "freejoint":
                add_joint("free", dict(child.attrib), body)
            elif child.tag == "joint":
                attributes, _class_name = _effective("joint", child, child_class, classes)
                add_joint(attributes.get("type", "hinge"), attributes, body)
            elif child.tag == "body":
                walk_body(child, child_class)

    worldbody = root.find("worldbody")
    if worldbody is None:
        raise ValueError("the MJCF has no <worldbody>")
    for body in worldbody.findall("body"):
        walk_body(body, None)
    return joints, qpos_size, qvel_size


def _joint_qpos0(joint):
    """The model-default qpos values of one joint: the free body pose or the joint reference value."""

    if joint["kind"] == "free":
        body = joint["body"]
        return _floats(body.get("pos"), 3, "0 0 0") + _floats(body.get("quat"), 4, "1 0 0 0")
    if joint["kind"] == "ball":
        return _floats(joint["attributes"].get("ref"), 4, "1 0 0 0")
    if joint["kind"] in ("hinge", "slide"):
        raw = joint["attributes"].get("ref")
        return [float(raw)] if raw is not None else [0.0]
    raise ValueError(f"the fake does not model the joint type {joint['kind']!r}")


class _Options:
    """``model.opt``: the bridge reads ``timestep``."""

    def __init__(self, timestep):
        self.timestep = timestep


class MjModel:
    """The ``mujoco.MjModel`` members the bridge reads, compiled from the MJCF tree of the card's model."""

    def __init__(self, root):
        self.name = root.get("model")
        classes = _default_classes(root)
        joints, self.nq, self.nv = _collect_joints(root, classes)
        self.qpos0 = []
        joint_offsets = {}
        for joint in joints:
            self.qpos0.extend(_joint_qpos0(joint))
            name = joint["attributes"].get("name")
            if name:
                joint_offsets[name] = (joint["kind"], joint["qpos_offset"], joint["qvel_offset"])

        self.actuator_joints = []
        self.actuator_ctrlrange = []
        self.actuator_ctrllimited = []
        actuator_root = root.find("actuator")
        if actuator_root is not None:
            for element in actuator_root:
                if element.tag == "default":
                    continue
                attributes, _class_name = _effective(element.tag, element, None, classes)
                self.actuator_joints.append(joint_offsets.get(attributes.get("joint")))
                low, high = _floats(attributes.get("ctrlrange"), 2, "0 0")
                self.actuator_ctrlrange.append([low, high])
                self.actuator_ctrllimited.append(
                    str(attributes.get("ctrllimited", "false")).lower() in ("true", "1"))
        self.nu = len(self.actuator_ctrlrange)
        if len(self.qpos0) != self.nq:
            raise ValueError("the parsed qpos0 does not match the parsed joint dimensions")

        timestep = _DEFAULT_TIMESTEP
        for option in root.findall("option"):
            if option.get("timestep") is not None:
                timestep = float(option.get("timestep"))
        self.opt = _Options(timestep)

    @classmethod
    def from_xml_path(cls, path):
        return cls(ET.parse(str(path)).getroot())

    @classmethod
    def from_xml_string(cls, xml):
        return cls(ET.fromstring(xml))


class MjData:
    """``mujoco.MjData``: the arrays the bridge reads and writes, as plain Python lists."""

    def __init__(self, model):
        self.qpos = list(model.qpos0)
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act = []
        self.time = 0.0


def mj_resetData(model, data):
    """Restore the data to the model defaults (the bridge calls this before the first step and on reset)."""

    data.qpos[:] = list(model.qpos0)
    data.qvel[:] = [0.0] * model.nv
    data.ctrl[:] = [0.0] * model.nu
    data.act[:] = []
    data.time = 0.0


def mj_forward(model, data):
    """Placeholder: the stand-in computes no derived quantities."""


def mj_step(model, data, nstep=1):
    """Advance the stand-in: each actuated hinge takes a placeholder velocity from its control value."""

    timestep = float(model.opt.timestep)
    for _ in range(int(nstep)):
        for index, entry in enumerate(model.actuator_joints):
            if entry is None:
                continue
            kind, qpos_offset, qvel_offset = entry
            if kind not in ("hinge", "slide"):
                continue
            data.qvel[qvel_offset] = float(data.ctrl[index]) * _CONTROL_GAIN
            data.qpos[qpos_offset] += data.qvel[qvel_offset] * timestep
        data.time += timestep


class FakeMujoco:
    """The stand-in ``mujoco`` module; ``backends["fake"]`` names this class (the SDK's own tests do the same)."""

    __version__ = "fake-mujoco"

    def __init__(self, **_options):
        self.MjModel = MjModel
        self.MjData = MjData
        self.mj_resetData = mj_resetData
        self.mj_forward = mj_forward
        self.mj_step = mj_step
