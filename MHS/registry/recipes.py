"""Family recipes for the OpenMHS registry: ``families/<family>.md`` (deterministic).

One recipe per registry family that appears in the records.  A recipe says
which Driver helper serves the family (``bridge_status``), how every driver
package is launched (one line: ``mhs serve <driver-dir>``), how native calls
map to catalogue classes, lifecycle and the e-stop, the family's hazards and
pitfalls, and which task cards come first.  Counts and examples come from the
generated records and cards; nothing here claims a recipe was executed.

Fixed mapping rules (REGQ-02, FIT-02, SIM-13, MISSED-5): setters map to
``cap.device.configure.v1`` unless a more specific write class fits;
construction, connection and teardown are lifecycle, never a capability; tip
pick-up and drop map to an ``x-cap.<owner>.<name>.v1`` extension until the
catalogue has a class; a Gymnasium ``close()`` is teardown, never a restore.
"""

from __future__ import annotations

import os
from collections import Counter

import taskcards as TC
import triage as T

#: registry family -> triage integration family (whose helper serves it)
HELPER_FAMILY = {
    "python-object": "python-object", "serial": "serial", "scpi-visa": "scpi", "gymnasium": "gymnasium",
    "mujoco": "mujoco", "ros1": "ros", "ros2": "ros", "gazebo": "ros", "http-api": "http", "opentrons": "http",
    "madsci": "http", "flowchem": "http", "pylabrobot": "pylabrobot", "sila2": "sila2", "qcodes": "qcodes",
    "bluesky-ophyd": "ophyd", "micromanager": "pymmcore-plus", "lerobot-real": "lerobot", "mcp-proxy": "mcp-client",
    "mavlink": "mavlink", "tag-bridge": "tag-bridge",
}
LAUNCH = "mhs serve <driver-dir>"
DONE = "python3 -m mhs.driver check <driver-dir> --backend fake"

DEVICE_ROWS = (
    ("Device(port=..., address=...)", "lifecycle: the native backend factory in driver.py",
     "construction and connection are never capabilities; addresses live in driver.py, not in launch flags"),
    ("device.get_<quantity>() / device.<quantity>",
     "@read: the measure class that fits (cap.measure.*), else cap.sensing.read.v1",
     "unit from the vendor documentation or the upstream code (UCUM); a read never changes the device revision"),
    ("device.set_<parameter>(value)",
     "@write: cap.device.configure.v1, or a write class that fits (cap.thermal.setpoint.v1, cap.imaging.illumination.v1)",
     "every limit cites source and file:line, or is Limit.operator_required"),
    ("device.move(...) / start() / acquire()",
     "@action: the catalogue class that fits, else x-cap.<owner>.<name>.v1 with an inline schema",
     "add a RESULT.json catalogue_requests entry for every x-cap id; declare long_running and cancellable for "
     "blocking calls"),
    ("device.stop() / abort() / output_off()", "@estop plus safe_state", "the e-stop is mhs.safety.estop, not a capability"),
    ("device.close() / disconnect()", "lifecycle: driver teardown", "never a capability (not self_test, not restore)"),
)
SIM_ROWS = (
    ("construct the environment or load the model", "lifecycle: construction (class attributes in driver.py)",
     "never cap.world.reset.v1"),
    ("reset(seed)", "cap.world.reset.v1",
     "output: the initial observation; a seed set with cap.world.seed.v1 applies at the next reset"),
    ("step(action)", "cap.world.step.v1 {ticks, action}", "the action space becomes the input schema with per-element limits"),
    ("get_state() / set_state()", "mhs.snapshot / mhs.restore (protocol methods)",
     "only when the engine restores the complete state; cap.world.snapshot.v1 and cap.world.restore.v1 are deprecated"),
    ("close()", "lifecycle: teardown", "never cap.world.restore.v1"),
)

ROS_PREFACE = ("OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, "
               "and not a reimplementation or compatible dialect of Anthropic's MHS research preview.")
ROS_ROWS = (
    ("topic observation", "`reads[field]`, or a read capability with `operation: subscribe`",
     "declare the topic, type, selected `path` and output schema; every package needs a capability, including sensors"),
    ("observational service", "read binding, or a service capability with `operation: read`",
     "source review must establish that the callback only observes; this flag does not make a command read-only"),
    ("effectful service", "`commands[capability]` or `writes[field]`",
     "declare the request and application `success` predicate; transport success alone is insufficient"),
    ("parameter access", "explicit service bindings only",
     "ROS 1 rosapi and ROS 2 node parameter services differ; there is no automatic parameter discovery or mapping"),
    ("topic publication", "command with `operation: publish`",
     "reports `published: true, confirmed: false`; transmission does not prove execution, target attainment or stopping"),
    ("native stop or safe state", "`safety_bindings.estop` or `.safe_state`",
     "fixed, input-free service or action binding; require application success and, for actions, a matching successful terminal"),
    ("native reset", "`safety_bindings.reset`",
     "fixed service binding with application success; action reset is unsupported"),
    ("ROS action goal, feedback, result or cancellation", "command with explicit ros1-actionlib or ros2-native profile",
     "require matching successful terminal status and application predicate; exact goal cancellation is separate from an acknowledged stop"),
    ("node launch, graph discovery or connection teardown", "operator setup / lifecycle",
     "the helper does not import ROS, start nodes or launch a simulator; closing a transport is not a stop"),
)
ROS_SCOPE = (
    "The implemented `RosDriver` is a configuration-only helper over rosbridge JSON topics, services and explicit action profiles. Set "
    "`ros_version` to the node's version; a C++ node does not need an invented Python native class. The operator "
    "runs upstream nodes and rosbridge separately. The optional WebSocket transport has no default endpoint; "
    "fake and offline sim backends provide their own transport and cannot fall back to a live WebSocket. "
    "A simulated class can use an explicit operator `simulation_deployment` through `backend=\"sim\"`; its endpoint, "
    "complete fidelity and separate deployment identity are validated before connecting (see "
    "[ROS driver deployment](../../sdk/docs/ros-driver.md#explicit-simulation-deployments)).\n\n"
    "Every binding carries `source_ref: path/in/clone:LINE` (or a bounded range) showing its endpoint and type at "
    "the pinned commit. Add `type_ref` when the type is declared elsewhere. For relative/private names, record "
    "the exact upstream token as `source_name` and configure the resolved absolute endpoint. The gate checks "
    "the same endpoint or a namespace-qualified suffix; it does not validate an operator's remapping or ROS graph. "
    "Use catalogue classes only when their semantics match; otherwise request an `x-cap` extension with an inline "
    "schema in `RESULT.json`. Numeric actuation limits need source evidence or `Limit.operator_required`.\n\n"
    "See the [ROS driver guide](../../sdk/docs/ros-driver.md) for binding syntax and the "
    "[Flatland exemplar](../../drivers/robots/avidbots__flatland/driver.py) for a ROS 1 clock observation and "
    "acknowledged pause/resume services. Flatland is a structural example, not evidence of live ROS 1 or ROS 2 "
    "compatibility. Its `/clock` is observation-only because the upstream publisher becomes silent while paused; "
    "automatic resource snapshots must not require a sample that a command can stop producing."
)
ROS_HAZARDS = (
    "Every ROS hardware backend, including R0 and human-authored packages, requires a schema-valid lock with a "
    "human `reviewed_by` entry of scope `hardware` before a backend factory or connection can run. Models keep "
    "`reviewed_by` null. The usual `allow_hardware=True` and persistent `state_dir` requirements still apply. "
    "A signed lock is a local review record, not cryptographic attestation or safety certification.\n\n"
    "Use a source-backed upstream stop service or fixed stop action and describe the resulting `safe_state`. Trace "
    "its callback, native synchronization and terminal ownership; the endpoint name or a client timeout does not "
    "prove prompt stopping. Service "
    "transport success and application success are distinct: an Empty response can use "
    "`success={\"path\": \"$\", \"equals\": {}}`; other services require their actual success field/code. "
    "An input-free `Action(safe_state=True)` service or fixed action has a separate bounded admission path during "
    "the latch; a raw command-map flag cannot grant that permission. An unresolved or erroneous action stop "
    "retains ownership and prevents another stop goal from preempting it. The helper fences queued actuating "
    "sends and interrupts pending ordinary requests when stopped. A timeout/disconnect after transmission has "
    "an unknown outcome; ordinary commands are not replayed. A historical safety fault permits a fresh bounded "
    "protective attempt only after prior stop owners and passive teardown ended safely; it still prevents "
    "achievement, reset and motion. See the ROS driver guide for the complete lifecycle and freshness rules. "
    "ROS is a transport, not a safety layer; the independent physical stop remains authoritative."
)
ROS_FIDELITY = (
    "Declare the deployed model's fidelity, not a simulator's generic capabilities or default timing. A "
    "`RecordingRosTransport` fake runs no physics and establishes only `contract_checked` evidence; mark "
    "invented observations as placeholders and describe absent dynamics and pacing in `gaps`. Model the actual "
    "upstream response shapes and negative cases, including service/application failures and stopping when "
    "exposed. Passing fake gates never establish an MHS-Device level, live ROS compatibility or hardware behavior."
)
ROS_PITFALLS = (
    "QoS configuration, authentication, graph discovery, hosting action servers, automatic reconnect/replay and "
    "fragment reassembly are outside this helper. Topic reads subscribe for a new arrival; explicit event IDs "
    "must match the active subscription, but an ID-less event cannot establish its original subscription or "
    "producer sample age. The message-size limit applies after receipt of a complete WebSocket frame, not before "
    "allocation. Action execution requires both native terminal success and an application predicate; uncertain goals "
    "block new mutations until terminal reconciliation and an acknowledged safety reset. ROS 2 native action "
    "deployments must test nonblocking goal handling and independent stop responsiveness. Large images and point "
    "clouds need an artifact path rather than inline payload claims."
)
ROS_SOURCES = (
    "[ROS binding, transport and review contract](../../sdk/docs/ros-driver.md).",
    "[Driver authoring](../../sdk/docs/driver-authoring.md), [model/human review](../../handoff/REVIEW.md), "
    "and [safety specification](../../spec/04-safety.md).",
    "[Flatland fake](../../drivers/robots/avidbots__flatland/fake.py), "
    "[tests](../../drivers/robots/avidbots__flatland/test_driver.py), "
    "[source facts](../../drivers/robots/avidbots__flatland/facts.md), "
    "and [result/evidence scope](../../drivers/robots/avidbots__flatland/RESULT.json).",
)

FAMILY = {
    "python-object": dict(
        title="Python device SDKs as OpenMHS drivers (direct Driver class)",
        applicability=("A Python package with an AST-parsed device class (score at least 9, at least three device "
                       "API members) and device evidence: triage rule 10, `PY_SDK_WITH_ENTRY`. Exemplars: "
                       "tiagocoutinho/julabo (instruments) and xArm-Developer/xArm-Python-SDK (robot SDKs)."),
        rows=DEVICE_ROWS,
        hazards=("Importability says nothing about hazards. Heaters, motors, pumps, lasers and high-voltage outputs "
                 "are common; cite every limit from the vendor documentation or the upstream code, or use "
                 "Limit.operator_required."),
        fidelity=("A fake backend (a recording fake, or the upstream simulator when the repo ships one) yields "
                  "contract_checked evidence only."),
        pitfalls=("Constructors often open ports or start threads: keep them in the hardware backend factory. "
                  "Optional heavy imports belong in the backend module. Do not claim capabilities from class names "
                  "alone; confirm each native call in the code."),
    ),
    "serial": dict(
        title="Serial line instruments as SerialDriver command maps",
        applicability=("The repo imports pyserial (or an equivalent) and has no strong Python device class: triage "
                       "rule 9, `family:serial`. It copies the command-map structure of the sr860 exemplar."),
        rows=(
            ("serial port settings (port, baud, parity)", "lifecycle: transport configuration in driver.py",
             "never launch flags; a fake or a transcript replaces the port"),
            ("query command (for example `IN_PV_00`)", "reads: the measure class that fits, else cap.sensing.read.v1",
             "parse the reply; the unit comes from the manual"),
            ("set command (for example `OUT_SP_00 25.0`)", "writes: cap.device.configure.v1, or a write class that fits",
             "every limit cites its source"),
            ("a raw write(command)", "only as a named command-map entry",
             "never cap.actuation.gpio.v1 for an arbitrary command"),
            ("stop or output-off command", "safety_bindings: e-stop and safe state",
             "written under the short write lock; it aborts a pending reply wait"),
        ),
        hazards=("A serial line can drive pumps, heaters and motors. Port names and baud rates are deployment-specific "
                 "and are never guessed at run time."),
        fidelity="A transcript fake proves the framing and the command map, not the physics.",
        pitfalls="Line endings and checksums vary; unbounded reads hang; USB re-enumeration renames ports; error replies "
                 "are vendor-specific.",
    ),
    "scpi-visa": dict(
        title="SCPI and VISA instruments as ScpiDriver command maps",
        applicability=("The repo imports pyvisa, vxi11, usbtmc or pymeasure and is not a driver pack: triage rule 9, "
                       "`family:scpi`. Exemplar: thinksrs/srsinst.sr860."),
        rows=(
            ("`*IDN?`", "connect-time identity probe (`idn.expect`)",
             "not a capability; identity is published by mhs.devices.get"),
            ("measurement query (for example `MEAS:VOLT?`)",
             "reads: cap.measure.voltage.v1 or the measure class that fits",
             "parse to a number; the unit comes from the manual"),
            ("setting (for example `FREQ <value>`)", "writes: cap.device.configure.v1",
             "limits cite the manual or the upstream code"),
            ("`*RST`, `INIT`, `ABOR`", "lifecycle, or an action with a catalogue class", "never a configure write"),
            ("`SYST:ERR?`", "error_query mapped to DriverFailed codes", ""),
            ("output off / abort", "safety_bindings: e-stop and safe state", ""),
        ),
        hazards=("Sources, heaters, lasers and high-voltage supplies are common. Limits come from the instrument manual "
                 "or the upstream code, never from the SCPI command name."),
        fidelity="A transcript or a pyvisa-sim device file checks the command map; it cannot validate a measurement.",
        pitfalls="SCPI carries no units; drain the error queue; one instrument per session; VISA backends differ "
                 "(pyvisa-py versus a vendor VISA).",
    ),
    "gymnasium": dict(
        title="Gymnasium environments as GymnasiumDriver family-configs",
        applicability=("The code registers gym or gymnasium environments and needs no external simulator "
                       "application: triage rule 9, `family:gymnasium`. Exemplar: Farama-Foundation/Gymnasium "
                       "(CartPole-v1)."),
        rows=(
            ("`gymnasium.make(env_id, **kwargs)`", "lifecycle: construction (`env_id = \"...\"` on the family-config class)",
             "never cap.world.reset.v1"),
            ("`env.reset(seed=...)`", "cap.world.reset.v1", "output: the initial observation and the seed"),
            ("seed", "cap.world.seed.v1", "applies at the next reset"),
            ("`env.step(action)`", "cap.world.step.v1 {ticks, action}",
             "Discrete, Box, Dict, MultiDiscrete and Tuple spaces become the input schema; Box low/high become "
             "per-element limits"),
            ("`env.render()`", "not mapped", "GymnasiumDriver leaves cap.world.render.v1 unbound"),
            ("`env.close()`", "lifecycle: teardown", "never cap.world.restore.v1"),
            ("`get_state()` / `set_state()`", "mhs.snapshot / mhs.restore",
             "only when the environment restores its complete state"),
        ),
        hazards=("An environment's motion and manipulation classes keep their catalogue risk classes for the agent "
                 "contract even in simulation. `terminated` is not task success."),
        fidelity=("Fidelity is defined by the engine behind the environment; declare action space, control frequency, "
                  "horizon and seeding in the fidelity contract."),
        pitfalls="Wrappers clip or normalise actions; reset may not reseed every RNG; vectorised environments are not "
                 "one device; rendering may need a display or GPU.",
    ),
    "mujoco": dict(
        title="MuJoCo models and simulators as MujocoDriver family-configs",
        applicability=("A loadable MJCF scene or robot model with actuators, with a mujoco, dm_control or mujoco_py "
                       "import, or in a pure model repository: triage rule 9, `family:mujoco`. The card's `models` "
                       "names the model to load (the first entry is the main scene or robot model); object and "
                       "fixture assets, MJCF fragments and copies under examples or tests never qualify. "
                       "Environments that compose their MJCF at run time (robosuite, LIBERO) have no main model in "
                       "the clone and are recon cards. It copies the structure of the Gymnasium exemplar."),
        rows=(
            ("`mujoco.MjModel.from_xml_path(path)`", "lifecycle: construction (`model_path = \"...\"`)",
             "never cap.world.reset.v1"),
            ("`mujoco.mj_resetData(model, data)`", "cap.world.reset.v1", ""),
            ("`data.ctrl` and `mujoco.mj_step(model, data)`", "cap.world.step.v1 {ticks, action: {ctrl}}",
             "ctrl limits come from actuator_ctrlrange, operator_required where the model states none"),
            ("`mj_getState` / `mj_setState`", "mhs.snapshot / mhs.restore", "integration state, not qpos alone"),
            ("`mujoco.Renderer`", "not mapped", "only when the helper advertises cap.world.render.v1"),
            ("close", "lifecycle: teardown", ""),
        ),
        hazards=("A model of a real robot gives the hardware no lower risk class; the hardware device takes its floor "
                 "from the catalogue."),
        fidelity="The time step is declared in the MJCF; mesh and texture assets carry their own licences.",
        pitfalls="qpos-only snapshots miss controller, RNG and time state; mj_step counts are not wall-clock; rendering "
                 "needs a GL context.",
    ),
    "ros2": dict(
        title="ROS 2 topics, services and actions through RosDriver",
        preface=ROS_PREFACE, rows=ROS_ROWS,
        applicability=("ROS 2 packages (package.xml) in a repo whose main family is ROS: triage rule 9, "
                       "`family:ros`; set `ros_version = 2`. " + ROS_SCOPE),
        safety_requirements="Hardware at R1 or above needs a declared native stop and a non-empty safe state. ",
        hazards=ROS_HAZARDS, fidelity=ROS_FIDELITY,
        pitfalls="ROS 2 launch files can start hardware drivers; DDS domains are not an isolation boundary. " + ROS_PITFALLS,
        sources=ROS_SOURCES,
    ),
    "ros1": dict(
        title="ROS 1 topics, services and actions through RosDriver",
        preface=ROS_PREFACE, rows=ROS_ROWS,
        applicability="ROS 1 packages; set `ros_version = 1`. " + ROS_SCOPE,
        safety_requirements="Hardware at R1 or above needs a declared native stop and a non-empty safe state. ",
        hazards=ROS_HAZARDS, fidelity=ROS_FIDELITY,
        pitfalls="Older ROS 1 stacks may require Python 2; roslaunch files can start hardware drivers. " + ROS_PITFALLS,
        sources=ROS_SOURCES,
    ),
    "gazebo": dict(
        title="Gazebo ROS interfaces through RosDriver",
        preface=ROS_PREFACE, rows=ROS_ROWS,
        applicability=("Gazebo worlds/plugins with explicit ROS interfaces. Bind reset or stepping only when "
                       "the pinned service actually provides the catalogue operation; the helper does not infer "
                       "world control or speak native Gazebo Transport. " + ROS_SCOPE),
        safety_requirements="Hardware at R1 or above needs a declared native stop and a non-empty safe state. ",
        hazards=("Gazebo command topics can also drive real robots; mode is declared, never inferred from a topic. "
                 + ROS_HAZARDS),
        fidelity=ROS_FIDELITY,
        pitfalls="Gazebo Sim and Gazebo Classic expose different interfaces and plugin contracts. " + ROS_PITFALLS,
        sources=ROS_SOURCES,
    ),
}
_PLANNED = {
    "http-api": ("HTTP and JSON-RPC services (helper:http, planned)",
                 "GET endpoints become reads, settings become cap.device.configure.v1, run endpoints become actions, "
                 "stop endpoints become the e-stop and the safe state.",
                 "Lab services are often unauthenticated; retries must never duplicate a command.",
                 "No standard error vocabulary; idempotency keys are rare."),
    "opentrons": ("Opentrons robots and protocols (helper:http, planned)",
                  "Robot-server runs and commands: aspirate and dispense map to cap.fluid.aspirate.v1 and "
                  "cap.fluid.dispense.v1, transfer to cap.fluid.transfer.v1; tip pick-up and drop map to "
                  "x-cap.<owner>.tip_pickup.v1 and x-cap.<owner>.tip_drop.v1 until a class exists; protocol "
                  "simulation is the fake.",
                  "A real OT-2 or Flex pipettes and moves labware; tip tracking and contamination are the driver's job.",
                  "Protocol Engine versions differ; the simulator models deck logic, not liquid physics."),
    "madsci": ("MADSci nodes (helper:http, planned)",
               "Node actions map to catalogue classes or x-cap extensions; the workcell scheduler is a host, not a device.",
               "Safety comes from each device behind the node.", "A full workcell needs running services."),
    "flowchem": ("Flowchem components (helper:http, planned)",
                 "Each component's HTTP API maps reads, settings (cap.device.configure.v1) and actions; virtual "
                 "components are the fake.",
                 "Heated solvents and reactive chemistry: interlocks and operator limits are mandatory.",
                 "Units differ per component; virtual components are not chemistry models."),
    "micromanager": ("Micro-Manager through pymmcore-plus (helper:pymmcore-plus, planned)",
                     "snapImage maps to cap.imaging.capture.v1, the Z stage to cap.imaging.focus.v1, illumination to "
                     "cap.imaging.illumination.v1, other properties to cap.device.configure.v1; the demo "
                     "configuration is the fake.",
                     "Stages can collide; lasers can be dangerous and photobleach samples.",
                     "Properties are untyped strings; configurations are hardware-specific."),
    "lerobot-real": ("LeRobot robots (helper:lerobot, planned)",
                     "`get_observation()` becomes reads, `send_action()` maps to cap.motion.joint_position.v1, "
                     "`disconnect()` is teardown.",
                     "Real arms at R1 and above need an e-stop and a safe state.",
                     "Calibration files and joint order are robot-specific."),
    "mavlink": ("MAVLink vehicles (helper:mavlink, planned)",
                "Telemetry becomes reads; arm, take-off and land are actions on x-cap extensions until classes exist; "
                "return-to-launch or land is the safe state; SITL is the fake.",
                "Flying vehicles; the e-stop and the geofence come first.",
                "PX4 and ArduPilot differ; frame conventions must be declared."),
}
for _name, (_title, _mapping, _hazards, _pitfalls) in _PLANNED.items():
    FAMILY[_name] = dict(title=_title, rows=None, applicability=_mapping, hazards=_hazards,
                         fidelity="Bridge only; the fidelity belongs to the service, simulator or hardware behind it.",
                         pitfalls=_pitfalls)
# --- exemplars-pyobj (2026-11-04): the QCoDeS and classic Ophyd families with their exemplar packages ---
_FAMILY_STOP = "Hardware at R1 or above needs a native stop (`safety_bindings.estop`) and a non-empty safe state. "
FAMILY["bluesky-ophyd"] = dict(
    title="Classic Ophyd Devices through OphydDriver",
    preface=ROS_PREFACE,
    applicability=(
        "Classic (synchronous) Ophyd Devices: triage rule 9, `family:ophyd`. `OphydDriver` is a configuration-only "
        "helper over the Python-object bridge. Each field is a `Field` in `parameters` plus one `signal_bindings` "
        "entry: `signal` (a direct Component attribute of the card's entry class), `get: True`, `set` (equal to "
        "`Field.writable`), `profile`, `get_kwargs`, `timeout_ms` (1..60000) and `source_ref` (the `path:LINE` of the "
        "Component assignment). Profiles: `classic_epics_v1` (`Component(EpicsSignal, ...)`: get, and a set that "
        "waits for its Status), `classic_epics_ro_v1` (`Component(EpicsSignalRO, ...)`: get only) and "
        "`classic_soft_v1` (`Component(Signal, ...)`, `get_kwargs` `{}`). Both EPICS profiles read with "
        "`get(use_monitor=False)` and require exactly that `get_kwargs`. Gate G7 proves each declaration in the "
        "pinned source without importing Ophyd, and refuses any other dotted member the fake or the driver touches "
        "(`OPHYD_UNPROVEN_MEMBER`).\n\n"
        "The [apstools exemplar](../../drivers/labs/bcda-aps__apstools/driver.py) is a read-only R0 monitor: seven "
        "EpicsSignalRO fields of `ApsMachineParametersDevice`, one observational `x-cap` capability whose native is "
        "the proven `current.get`, a source-shaped fake and a hardware factory that builds the upstream Device. It "
        "shows the declaration grammar, the fake and the facts; it does not demonstrate a write, a Status or a native "
        "stop. The [Ophyd driver guide](../../sdk/docs/ophyd-driver.md) gives the complete contract."),
    rows=(
        ("`Component(EpicsSignal, \"PV\")`", "a `parameters` Field and a `signal_bindings` entry, "
         "`profile: classic_epics_v1`", "a write calls `Signal.set` and waits for the returned Status within "
         "`timeout_ms`; raw `put` is never compiled; every numeric write cites a source line or is "
         "`Limit.operator_required`"),
        ("`Component(EpicsSignalRO, \"PV\")`", "a get-only binding, `profile: classic_epics_ro_v1`",
         "a fresh `get(use_monitor=False)`; `set: True` is refused"),
        ("`Component(Signal, ...)` (soft signal)", "a binding with `profile: classic_soft_v1`",
         "the value lives in the Python process, not in an IOC"),
        ("a read-only Device", "a capability: a catalogue read class that fits, else an `x-cap` read action "
         "(`commands` and `actions`) whose native is a bound `<signal>.get`",
         "resource reads alone are not a capability; request the `x-cap` id in `RESULT.json`"),
        ("`stop()`, `trigger()`, `stage()`, a positioner's `move()`", "`commands`/`actions` or `safety_bindings`, "
         "only with source evidence of what the method does", "a done Status does not prove that its callbacks "
         "ended; no exemplar demonstrates a native stop yet"),
        ("EPICS engineering units", "`Field(unit=...)` only when the source states the unit, else `unit_bindings` "
         "with an explicit operator option, or no unit", "never infer a unit from a PV name"),
        ("Device construction, `wait_for_connection()`", "lifecycle: the `native.py` factory",
         "the gate never imports it; PV prefixes are deployment data"),
        ("nested Components, `FormattedComponent`, `DynamicDeviceComponent`, custom Signal classes, ophyd-async "
         "Devices", "not expressible", "G7 reports `OPHYD_COMPONENT_SOURCE` or `OPHYD_IDENTITY_UNRESOLVED`: stop "
         "`blocked` with the finding in the notes"),
    ),
    safety_requirements=_FAMILY_STOP,
    hazards=("Ophyd Devices front motors, shutters, detectors and high-voltage supplies: risk follows the hazard "
             "table of the safety specification, not the card's floor, and a model-authored R2 or R3 package never "
             "runs its hardware backend before a human signs `reviewed_by`. A Device's generic `stop()` is not "
             "evidence that anything physical stopped. EPICS drive limits, validators and PV metadata read at run "
             "time are not sourced limits."),
    fidelity=("A source-shaped fake holds one stand-in object per bound Component that implements only the calls "
              "the driver makes (`get(use_monitor=...)`, and `set(value)` returning a Status for a writable "
              "binding); its values are placeholders and it runs no IOC. It yields `contract_checked` evidence "
              "only: Channel Access, PV connection and record processing are not modelled."),
    pitfalls=("EPICS PV names are deployment-specific; area detectors produce large arrays (`NEEDS_ARTIFACTS`); "
              "startup-script profile collections are not Device classes. A class body with executable statements, "
              "decorators, metaclasses, reflection or receiver escapes fails the source proof even when its "
              "Components look simple."),
    sources=("[Ophyd driver contract](../../sdk/docs/ophyd-driver.md) and "
             "[driver authoring](../../sdk/docs/driver-authoring.md).",
             "[apstools exemplar fake](../../drivers/labs/bcda-aps__apstools/fake.py), "
             "[tests](../../drivers/labs/bcda-aps__apstools/test_driver.py), "
             "[source facts](../../drivers/labs/bcda-aps__apstools/facts.md) "
             "and [result/evidence scope](../../drivers/labs/bcda-aps__apstools/RESULT.json)."),
)
FAMILY["qcodes"] = dict(
    title="QCoDeS instruments through QcodesDriver",
    preface=ROS_PREFACE,
    applicability=(
        "QCoDeS instrument classes: triage rule 9, `family:qcodes`. `QcodesDriver` is a configuration-only helper "
        "over the Python-object bridge. Each field is a `Field` in `parameters` plus one `parameter_bindings` entry: "
        "`parameter` (the attribute path of a Parameter), `get: True`, `set` (equal to `Field.writable`), "
        "`timeout_ms` (1..60000) and `source_ref` (the `path:LINE[-END]` of its constructor). Gate G7 proves a "
        "`self.<name> = Parameter(...)` assignment in `__init__` of the card's entry class or its in-clone ancestry, "
        "with `Parameter` imported from `qcodes.parameters` and an explicit `get_cmd` (and `set_cmd` for a write); "
        "a same-file factory needs `factory_ref`. Parameters created by `add_parameter`, channel lists, submodules "
        "or dynamic factories are not provable today, and most QCoDeS drivers use `add_parameter`: such a card stops "
        "`blocked` with the G7 finding `QCODES_PARAMETER_SOURCE`.\n\n"
        "The [PM100D exemplar](../../drivers/labs/qcodes__qcodes_contrib_drivers/driver.py) serves a Thorlabs PM100D "
        "optical power meter (R1): seven Parameters, two writes through `cap.device.configure.v1` (one "
        "`Limit.operator_required`), the stop `write(\"ABOR\")` (the abort command the source sends before it "
        "re-initializes a measurement), and a source-cited reason for every Parameter it does not serve. The [QCoDeS driver guide](../../sdk/docs/qcodes-driver.md) "
        "gives the complete contract."),
    rows=(
        ("`Parameter.get()`", "a `parameters` Field and a `parameter_bindings` entry with `get: True`",
         "every read is a new native get; `cache` and `get_latest` are never substituted"),
        ("`Parameter.set(value)`", "a writable Field (`set: True`), served as `cap.device.configure.v1`",
         "the whole setter is awaited, steps and delays included; a QCoDeS validator becomes a sourced `Limit` only "
         "where it bounds the device, else `Limit.operator_required`"),
        ("Parameter `unit`, `scale`, `get_parser`, `val_mapping`", "the Field's type and unit follow what `get()` "
         "returns after the parsers", "a unit OpenMHS does not know (dB) goes into the description, not `unit`; a "
         "`scale` without a `get_parser` makes the upstream get fail on the reply string"),
        ("the instrument's `write()` / `ask()`", "a native stop: `safety_bindings.estop` with `invoke: write` and a "
         "stop or abort command the source itself sends", "the stop shares the VISA session with a running call; "
         "prefer a write that expects no reply"),
        ("`Instrument.close()`", "`native_close = \"close\"`", "teardown, never a capability"),
        ("construction with a VISA address", "lifecycle: the `native.py` factory",
         "QCoDeS constructors talk to the instrument before they return; disclose those commands"),
        ("`add_parameter`, channels, submodules, `ArrayParameter`", "not expressible",
         "G7 reports `QCODES_PARAMETER_SOURCE` or `QCODES_UNDECLARED_MEMBER`: stop `blocked`"),
    ),
    safety_requirements=_FAMILY_STOP,
    hazards=("Sources, heaters, magnets and RF outputs: parameter validators are not safety limits, risk follows the "
             "hazard table of the safety specification, and a model-authored R2 or R3 package never runs its "
             "hardware backend before a human signs `reviewed_by`. Cancelling a Parameter set is not a stop "
             "acknowledgement."),
    fidelity=("A source-shaped fake holds one stand-in per bound Parameter (`get()`, and `set()` where the upstream "
              "has a `set_cmd`) plus the instrument methods the driver calls, with placeholder values typed as the "
              "upstream parsers return them. It yields `contract_checked` evidence only: VISA timing, SCPI error "
              "queues and instrument state machines are not modelled."),
    pitfalls=("Contributed drivers vary in quality: check every parser, scale and `set_cmd` placeholder against the "
              "source. A `MEAS:...?` read reconfigures the instrument; a constructor that writes settings belongs to "
              "the hardware factory, not to a capability."),
    sources=("[QCoDeS driver contract](../../sdk/docs/qcodes-driver.md) and "
             "[driver authoring](../../sdk/docs/driver-authoring.md).",
             "[PM100D exemplar fake](../../drivers/labs/qcodes__qcodes_contrib_drivers/fake.py), "
             "[tests](../../drivers/labs/qcodes__qcodes_contrib_drivers/test_driver.py), "
             "[source facts](../../drivers/labs/qcodes__qcodes_contrib_drivers/facts.md) "
             "and [result/evidence scope](../../drivers/labs/qcodes__qcodes_contrib_drivers/RESULT.json)."),
)
# --- end exemplars-pyobj ---

# --- exemplars-service (2026-11-04): the McpClientDriver family page (was the planned mcp-proxy recipe) ---
MCP_EXEMPLAR = "../../drivers/labs/mattjax16__rigol-dho-mcp"
MCP_ROWS = (
    ("a tool registered by a literal `@<receiver>.tool()` on a top-level function of the pinned source file",
     "one `mcp_config[\"tools\"]` entry, one primary `commands[cap] = {\"tool\": name}` and an explicit `Action`",
     "closed input schema from the signature, the literal default of every optional argument, `source_ref` inside "
     "the function; G7 proves name, arguments, defaults, file bytes and pin"),
    ("a tool body that writes to the device, including select-then-query measurements",
     "`effectful: true`; an `x-cap.<owner>.<tool>.v1` action unless a catalogue class has the same output",
     "effects come from the body, never from the tool name, description or annotations"),
    ("an argument-free read-only tool that returns a JSON object",
     "`reads[field] = {\"tool\": ..., \"path\": ...}` beside its command", "a read never replaces the tool's command"),
    ("a numeric argument",
     "`Limit(..., source=\"upstream_code\", ref=...)` when the signature enforces it (`Field(ge=1, le=4)`), else "
     "`Limit.operator_required`", "a docstring range or a description is not an enforced bound"),
    ("a large JSON result or an MCP image",
     "`output.artifact: true` (`artifact_ref`, `media_type`) or `kind: png` (`image_ref`, `width`, `height`, "
     "`media_type`)", "the complete returned result; `array_counts` and `arrays_if` check array lengths"),
    ("a documented precondition (\"the scope must be stopped\")",
     "`prerequisite`: a fresh read-only observation with `path` and `equals`, cited inside the tool",
     "refuses with PRECONDITION_UNMET; never performs the precondition itself"),
    ("one argument whose unit depends on another", "extra commands with `arguments` (`input`/`const`) or a cited "
     "`select` over one read-only observation", "each binding declares its unit; the wire schema stays the source's"),
    ("a stop tool plus a status readback", "`mcp_config[\"safety\"]`: `command`, `arguments`, `observe`, `path`, `equals`",
     "the e-stop sends the command on the protective lane and needs a fresh matching observation after older "
     "requests retired"),
    ("raw command, code execution, file path or URL tools", "not exposed",
     "no caller-supplied code, SCPI program, endpoint, credential or path"),
    ("server start, transport, `tools/list`", "lifecycle outside the package",
     "discovery is a compatibility check, never authority; every non-fake backend refuses"),
)
MCP_SCOPE = (
    "Repositories whose device interface is an MCP server: triage rule 9, `family:mcp-client`. The implemented "
    "`McpClientDriver` is a configuration-only, finite tool contract over an injected controlled peer. It does not "
    "talk to a live MCP server: every non-fake backend refuses before any import, process start or connection, so a "
    "package passes on its fake (`contract_checked`) and states its native gaps in `RESULT.json` notes. Exemplar: "
    f"[gh.mattjax16/rigol-dho-mcp]({MCP_EXEMPLAR}/README.md) (thirteen tools of a Rigol oscilloscope server as "
    "sixteen bindings).\n\n"
    "Configuration surface. `mcp_config[\"source\"]` names one file, its SHA-256, the pinned commit and the decorator "
    "receiver. `mcp_config[\"tools\"]` has one entry per selected tool: `input` (closed object schema; every array has "
    "`maxItems`, every free string `maxLength`), `output` (`kind` `json` with `schema`, `text`, or `png`, each with "
    "`max_bytes`), `effectful`, `source_ref`, `defaults`, and optionally `error_prefixes`, `result_matches` and "
    "`prerequisite`. Optional `safety` declares the protective transaction; `request_timeout_ms`, `stop_timeout_ms`, "
    "`max_message_bytes` and `owned_transport` bound the client. On the class: `commands` (every tool needs exactly one "
    "primary command; `arguments` and `select` add projections), an explicit `Action` per command whose inline output "
    "schema equals the tool's, `reads` with `parameters`, `mode = \"hardware\"`, and `backends = {\"fake\": "
    "\".fake:connect\", \"hardware\": \".native:connect\"}`. The fake returns a peer with "
    "`exchange(message, *, timeout_ms, lane)` that answers `tools/list` and `tools/call`; `native.py` refuses. No "
    "`writes`, `safety_bindings`, `safe_state=True` action, `estop_physical_ref` or method overrides; numeric inputs "
    "need a sourced or operator-required `Limit`. See [the MCP client guide](../../sdk/docs/mcp-client.md).\n\n"
    "What it cannot express today: a hardware device at R2 or R3 (SAFE-045 wants a physical-stop reference or a "
    "safe-state action, and McpClientDriver allows neither), tools registered with `add_tool(...)` or through a "
    "low-level `Server` tool table (G7 proves literal decorators only), list or mixed content results (a JPEG preview "
    "beside metadata), tools that run caller-supplied code, and primary data the server itself drops before "
    "returning. Stop with blocked "
    "`HELPER_MISSING` or `NEEDS_ARTIFACTS` and name the source lines, or record a source-verified DEVIATION FROM THE "
    "CARD to another helper that matches the device's real interface."
)
FAMILY["mcp-proxy"] = dict(
    title="MCP servers through McpClientDriver (finite controlled tool contract)",
    preface=ROS_PREFACE, rows=MCP_ROWS, applicability=MCP_SCOPE,
    safety_requirements=("Hardware at R1 or above needs the `mcp_config[\"safety\"]` protective transaction (it is the "
                         "e-stop; `@estop` methods are not allowed) and a non-empty safe state; R2 and R3 cannot pass "
                         "SAFE-045 with this helper today. "),
    hazards=("Risk follows the device behind the server (MHS/spec/04-safety.md hazard table), never the tool names. "
             "Remote descriptions, titles and annotations are untrusted text and grant no authority. A successful-looking "
             "reply, MCP cancellation, a closed pipe or a process exit is not a device stop: the safe state is only the "
             "declared protective command plus a fresh matching observation, and an unconfirmed effect blocks new "
             "effects until an e-stop and reset settle it."),
    fidelity=("A controlled peer yields `contract_checked` evidence only. The SDK's controlled profile is not FastMCP's "
              "native wire: FastMCP lists pydantic-generated schemas and can add `structuredContent` beside string "
              "results, which the bridge refuses; numbers in the fake are placeholders."),
    pitfalls=("Tools named get_* can write (select, then query). One tool issues several device calls, so timeouts do "
              "not retire it. Error text often comes back as normal content (`error_prefixes`). Summaries can replace "
              "the primary array. Optional raw-command tools stay unexposed."),
    sources=("[MCP client guide](../../sdk/docs/mcp-client.md) and [driver authoring](../../sdk/docs/driver-authoring.md).",
             f"[Rigol exemplar driver]({MCP_EXEMPLAR}/driver.py), [fake]({MCP_EXEMPLAR}/fake.py), "
             f"[tests]({MCP_EXEMPLAR}/test_driver.py), [facts]({MCP_EXEMPLAR}/facts.md) and "
             f"[result notes]({MCP_EXEMPLAR}/RESULT.json)."),
)
# --- end exemplars-service ---
# --- PyLabRobot helper (plr-liquid-handler-v1): replaces the planned pylabrobot entry ---
FAMILY["pylabrobot"] = dict(
    title="PyLabRobot liquid handlers through PyLabRobotDriver (profile plr-liquid-handler-v1)",
    preface=ROS_PREFACE,  # integration (2026-11-05): the independence sentence, as on the other helper pages
    rows=(
        ("the upstream object or `LiquidHandler(backend=..., deck=...)`",
         "lifecycle: the backend factory (`fake.py`; `native.py` for hardware)",
         "`plr_profile.handler` is the attribute path to the LiquidHandler, cited at `handler_ref`"),
        ("`setup()`", "lifecycle: `plr_profile.setup`, run when the driver opens",
         "on hardware it initializes the instrument (it moves)"),
        ("`stop()` / `teardown()`", "lifecycle: `plr_profile.close`", "PyLabRobot `Machine.stop` is teardown, never the e-stop"),
        ("`pick_up_tips`, `aspirate`, `dispense`, `discard_tips`", "`x-cap.<owner>.transfer.v1` (kind `transfer`, R2)",
         "fresh tips from tip tracking; one well per channel, one column per call; no cleanup motion after a failure"),
        ("the same with repeated `aspirate`/`dispense`", "`x-cap.<owner>.mix.v1` (kind `mix`, R2)",
         "`cycles_limit` is sourced or `Limit.operator_required`; a per-operation `volume_limit` cites its own line"),
        ("a step error other than a bookkeeping error", "`unknown` `MHS.OUTCOME.UNKNOWN` with the completed steps",
         "it may have reached the device; new effects are fenced until a confirmed stop and an operator reset"),
        ("`well.tracker.get_used_volume()`", "`x-cap.<owner>.tracked_volumes.v1` (kind `tracked_volumes`, read, R0)",
         "PyLabRobot bookkeeping, never a liquid-level measurement"),
        ("deck resources by name", "`PlrLabware(name, kind, ref)`, kind `plate` or `tip_rack`",
         "only names a pinned line states; the input enums are this allowlist"),
        ("a native stop the source shows", "`plr_profile.stop = PlrStop(native, ref, description)`",
         "never a teardown; R2 hardware also needs `estop_physical_ref`; without a stop the package is blocked"),
    ),
    applicability=(
        "An upstream whose control interface is a PyLabRobot `LiquidHandler` front end, used directly or held by an "
        "upstream object (a digital twin's `env.lh`). The package sets one `plr_profile = PlrProfile(...)` and no "
        "methods; every capability is generated. Exemplar: oelemento/star-sim (simulated STARlet twin). Other "
        "PyLabRobot machines (plate readers, incubators, spectrophotometers, scanners) use a direct `Driver` or "
        "`PythonObjectDriver`; a class that only borrows PyLabRobot method names, a firmware protocol or a remote "
        "service without a PyLabRobot front end uses a direct `Driver` (`DEVIATION FROM THE CARD`). A card whose "
        "entry symbols do not include the class the package drives needs a maintainer override first "
        "(`G7.NOT_AN_ENTRY_SYMBOL`). Single-step aspirate/dispense and the cap.fluid.transfer.v1 / "
        "cap.fluid.mix.v1 / cap.fluid.level.v1 classes are not bound by this profile (see the helper guide)."),
    hazards=(
        "Pipetting and gantry motion are R2 (MHS-004 hazard table); the composite operations carry R2 in every mode. "
        "A hardware backend without `plr_profile.stop` is refused before its factory runs and gate G3 refuses the "
        "package: stop with `blocked` rather than invent a stop or use `stop()`/`teardown`. A `PlrStop` description "
        "says what it does not stop (a firmware halt may let the running sequence complete) and must be safe to repeat: "
        "the server retries it in the background until it confirms. The bridge sends no PyLabRobot step after an "
        "e-stop, cancellation or session close; a step in progress continues. After a failure or an e-stop the tips "
        "stay mounted and v1 has no operation that clears them: an operator clears the head (a simulated twin "
        "restarts). The loader refuses an unreviewed model-written R2/R3 hardware backend."),
    fidelity=(
        "A package fake composes `mhs.testing.pylabrobot` (tip and volume bookkeeping only: no motion, timing, "
        "liquid classes or physics); its capacities and starting liquid are placeholders. Evidence stays "
        "contract_checked; a fake gate never establishes an MHS-Device level or PyLabRobot behaviour."),
    pitfalls=(
        "PyLabRobot tip tracking is off unless the upstream switches it on: fresh-tip selection needs the cited "
        "`set_tip_tracking(True)` line. Vendored PyLabRobot copies differ by version. Deck layouts often live in "
        "scripts or operator code; only labware a pinned line names can be declared. Upstream protocols often discard "
        "tips in a `finally` block; the helper deliberately does not. The gate reads every profile reference as code "
        "(`ast`, one line, operation spans of at most 40 lines). The gate's conformance suite repeats one payload, so "
        "give every operation an `alternate` fixture. A deck of more than about ten plate names exceeds the "
        "2048-byte tool budget (G8.TOOL_SIZE)."),
    sources=(
        "[PyLabRobot helper guide](../../sdk/docs/pylabrobot-helper.md).",
        "[star-sim exemplar driver](../../drivers/labs/oelemento__star-sim/driver.py), "
        "[fake](../../drivers/labs/oelemento__star-sim/fake.py), "
        "[tests](../../drivers/labs/oelemento__star-sim/test_driver.py) and "
        "[result/evidence scope](../../drivers/labs/oelemento__star-sim/RESULT.json).",
    ),
)
# --- end PyLabRobot helper ---

# --- tag-bridge helper (2026-11-04): begin. TagDriver landed; this replaces the planned entry. ---
TAG_ROWS = (
    ("register, PV or Alpaca property read", "`reads[field]` (resource state) or an observation command "
     "`{\"read\": {...}}`; cap.sensing.read.v1 only for a sensor kind",
     "cite the line that shows the address; an x-cap observation declares `verb=\"read\"` and takes no input"),
    ("setpoint or configuration write", "`writes[field]`: cap.device.configure.v1",
     "a sourced `Limit` or `Limit.operator_required`; a register's codec range is not a device limit; a write-only "
     "point shows the last acknowledged value"),
    ("on/off, mode or start write sequence", "`commands[capability]` with `steps`, `confirm` and `result`",
     "fixed values or action inputs; confirmations are fresh reads; an x-cap.<owner>.<name>.v1 extension unless a "
     "catalogue class fits"),
    ("Alpaca method (PUT)", "`commands[capability]` with an `invoke` step",
     "only the Alpaca errors that state no effect (0x400, 0x401, 0x407-0x409, 0x40B, 0x40C) are refusals; others, "
     "and a confirmation that does not hold, are unknown outcomes"),
    ("output off, abort or stop write", "`safety_bindings[\"estop\"]` plus an input-free `Action(safe_state=True)`",
     "fixed steps and at least one confirmation read; say what the stop leaves running"),
    ("port, host, unit id, PV prefix, Alpaca server", "lifecycle: options of the `native.py` factory",
     "deployment data, never Facts or points"),
    ("OPC UA, Tango, ADS, S7, subscriptions, discovery", "not supported by this helper version",
     "a direct driver, recon or HELPER_MISSING; never write an undeclared address"),
)
FAMILY["tag-bridge"] = dict(
    title="Tag, register and PV devices through TagDriver (Modbus, EPICS Channel Access, ASCOM Alpaca)",
    preface=ROS_PREFACE, rows=TAG_ROWS,
    applicability=(
        "Devices a server exposes by register number, PV name or Alpaca member: triage rule 9, `family:tag-bridge`. "
        "The implemented `TagDriver` is a configuration-only helper with three profiles, `modbus`, `epics-ca` and "
        "`alpaca`: a finite `tag_config.points` table where every address carries `source_ref: path/in/clone:LINE` "
        "(or a bounded range) that shows it at the pinned commit, plus `parameters`, `reads`, `writes`, "
        "`commands`, `actions` and `safety_bindings`. `native` names the upstream class that shows the map; it is "
        "parsed, never imported. Gate G7 accepts a register only as the address argument of a Modbus call or as a "
        "register constant on the cited lines, with the call's table and direction matching the point. "
        "Read the [tag-bridge helper guide](../../sdk/docs/tag-bridge.md) for the grammar, "
        "the codecs and the transport interface, and copy the structure of the "
        "[labmastro exemplar](../../drivers/labs/josuablejeru__labmastro/driver.py) (a Modbus RTU bench supply: "
        "state reads, write-only setpoints with operator-required limits, confirmed output commands and a confirmed "
        "stop), never its registers, facts or limits.\n\n"
        "Check the card's shape first. Triage files a repository here when it imports a tag library anywhere; "
        "when the device itself speaks serial, SCPI or a Python SDK and the tag protocol is only a service layer "
        "or an example (an OPC UA mailbox, a Tango or Lima plugin, a Modbus demo for another device), write that "
        "device's shape and record DEVIATION FROM THE CARD, or stop with blocked HELPER_MISSING. A repository whose "
        "PV names come from a deployment file absent from the clone cannot cite its addresses: stop."),
    safety_requirements=("Hardware at R1 or above needs a declared native stop and a non-empty safe state. "),
    hazards=(
        "Any write or effectful command requires `safety_bindings[\"estop\"]`: fixed writes or Alpaca methods "
        "followed by at least one confirmation read; R2+ hardware also needs an input-free `Action(safe_state=True)` "
        "with fixed steps and confirmation. Without a real, source-backed stop route a tag device may only observe "
        "(R0 reads). An acknowledgement alone never proves a stop, and a confirmation proves what the device reports, "
        "not physical quiescence: say in `safe_state` what stays energized or running.\n\n"
        "Every TagDriver hardware backend, at every risk class and for every author, requires a schema-valid lock "
        "with a human `reviewed_by` entry of scope `hardware` before any factory or connection runs; models keep "
        "`reviewed_by` null. A lost, unacknowledged or unconfirmed write is an unknown outcome: the point leaves the "
        "state and ordinary effects are refused until a confirmed stop; a write-only setpoint whose write was lost "
        "then keeps commands refused until it is written again. Values a register cannot represent exactly are "
        "refused, never rounded. Industrial servers can front dangerous equipment; never write an undeclared tag."),
    fidelity=(
        "A `RecordingTagTransport` fake is a deterministic point store: it establishes only `contract_checked` "
        "evidence. Mark its seeded values as placeholders, model only the device behaviour the cited source shows "
        "(a written output read back), and say in RESULT.json notes what the fake does not model (regulation, "
        "timing, Modbus exceptions, server errors)."),
    pitfalls=(
        "Address maps, unit ids and PV prefixes are deployment-specific; keep them in the backend options. Upstream "
        "helpers often scale, split or combine registers in ways the source must show (decimals, word order, "
        "two separate single-register writes are not one atomic value). Upstream code may swallow protocol errors; "
        "the package's transport must not. Multi-word writes, arrays, subscriptions and long-running commands are "
        "outside this helper version."),
    sources=(
        "[TagDriver grammar, transport and runtime rules](../../sdk/docs/tag-bridge.md).",
        "[Driver authoring](../../sdk/docs/driver-authoring.md), [model/human review](../../handoff/REVIEW.md), "
        "and [safety specification](../../spec/04-safety.md).",
        "[labmastro fake](../../drivers/labs/josuablejeru__labmastro/fake.py), "
        "[tests](../../drivers/labs/josuablejeru__labmastro/test_driver.py), "
        "[source facts](../../drivers/labs/josuablejeru__labmastro/facts.md), "
        "and [hardware factory](../../drivers/labs/josuablejeru__labmastro/native.py).",
    ),
)
# --- tag-bridge helper (2026-11-04): end ---
# --- w1-waiting-routing (2026-11-05): the Sila2Driver family page (was the planned sila2 recipe) ---
SILA_EXEMPLAR = "../../drivers/labs/anguyen-23__sila-testing"
SILA_ROWS = (
    ("an unobservable FDL `Command`", "`commands[cap] = {\"member\": name}` and an explicit `Action` with the exact "
     "FDL input and output fields", "an effectful command is permit-bound, R2 or R3, and every input carries "
     "`Limit.operator_required`; FDL constraints are protocol bounds, never physical limits"),
    ("an observable FDL `Command`", "the same, with `long_running`, a bounded `max_duration_ms` and `cancellable` only "
     "where the declaration allows it", "confirmation, info, intermediate and final result stay separate; "
     "`reads` with `execution` expose the last known UUID, progress and intermediate value"),
    ("an FDL `Property`", "`reads[field] = {\"member\": name, \"field\": name}` with a matching `parameters` Field",
     "a fresh property request on every read; it is not an atomic multi-property snapshot"),
    ("a `Binary` property (an icon)", "a command with `artifact` and `media_type`, output `artifact_ref`, "
     "`media_type`, `size_bytes`", "complete bytes through the stock artifact store; an icon is not acquired data"),
    ("the feature's `Stop` command", "`safety_bindings = {\"estop\": {\"member\": \"Stop\"}}` and its "
     "`safe_state=True` Action with output `{\"stopped\": boolean}`", "only the controlled peer's fresh observation "
     "proves retirement; a native Stop acknowledgement and a cached idle state do not"),
    ("`Connect` (a host or address input)", "a permit-bound action; the gate prepares it only through "
     "`fixtures/gate-prerequisites.json` (profile `sila2-controlled-phenix-connect-v1`)", "the operator overlay "
     "names the one allowed host; the preparation is never a stop, reset or safety proof"),
    ("server start, gRPC channel, certificates, `SimulationController`", "lifecycle outside the package",
     "every non-fake backend refuses before any factory, import or connection"),
)
SILA_SCOPE = (
    "SiLA 2 features: triage rule 9, `family:sila2`. The implemented `Sila2Driver` is a configuration-only, finite "
    "typed contract over an injected controlled peer (`mhs-sila2-controlled-v1`). It does not implement a SiLA "
    "gRPC/protobuf client: every non-fake backend refuses before any factory, import or connection, so a package "
    "passes on its fake (`contract_checked`) and states its native gaps in `RESULT.json` notes. Exemplar: "
    f"[gh.anguyen-23/sila-testing]({SILA_EXEMPLAR}/README.md) (the complete PhenixImager feature: eight commands, "
    "seven properties and the Stop binding).\n\n"
    "Configuration surface. `sila2_config` (usually a `declarations.py` CONFIG) fixes `peer_format`, "
    "`runtime_profile`, an opaque `endpoint`, the feature FQI, the pinned commit, the exact FDL, generated proto and "
    "implementation paths with their SHA-256, the complete member table (kind, input, output, intermediate, errors, "
    "effect, completion, `source_ref` of each FDL block), `stop`, the request, execution and stop timeouts and "
    "`unsafe_properties`. On the class: `native` (the implementation class), `commands`, an explicit `Action` per "
    "command, `reads` with `parameters`, `safety_bindings`, `mode = \"hardware\"`, `risk` R2 or R3, and `backends = "
    "{\"fake\": \".fake:connect\", \"hardware\": \".native:connect\"}`. The fake factory receives a `PeerLease`, "
    "registers its peer before setup and answers `describe`, `observe`, `invoke`, `property`, `subscribe`, `next`, "
    "`unsubscribe`, `result` and the binary operations; `native.py` refuses. No method overrides, no "
    "`estop_physical_ref`. See [the controlled SiLA 2 profile](../../sdk/docs/sila2-controlled-profile.md).\n\n"
    "What it cannot express today: gate G7 has one static source profile, the PhenixImager feature at commit "
    "`0b572380e06977c1920510773b4bfee7bcd0eec5` (`MHS/sdk/src/mhs/driver/sila2_check.py`), and the gate prerequisite "
    "profile is the same feature's Connect. Any other feature, pin, or a feature generated at run time (UniteLabs "
    "CDK connectors ship no FDL), a C# server, or a device below R2 fails `SILA_SOURCE_UNPROVEN` or the class "
    "check. Record a source-verified DEVIATION FROM THE CARD to a direct Driver over the repository's own client "
    "class, or stop `blocked` `HELPER_MISSING` with the source lines. The model review of 2026-11-05 routed the other "
    "four SiLA cards of this registry to direct drivers for that reason "
    "(`MHS/registry/overrides/waiting-routing.json`). Triage rule 9 still tags every repository that imports `sila2`, "
    "`sila_python` or `unitelabs` as family sila2: until a second source profile exists such a card needs a reviewed "
    "override, and `validate.py` and the registry tests refuse any other dispatchable sila2 card."
)
FAMILY["sila2"] = dict(
    title="SiLA 2 features through Sila2Driver (controlled peer, one pinned Phenix source profile)",
    preface=ROS_PREFACE, rows=SILA_ROWS, applicability=SILA_SCOPE,
    safety_requirements=("Sila2Driver accepts only a `hardware` declaration at R2 or R3: every effectful route needs a "
                         "stock input-bound permit and an operator envelope on each input, and the e-stop is the "
                         "feature's explicit Stop command (`safety_bindings`), never an `@estop` method. "),
    hazards=("Risk follows the instrument behind the server (MHS/spec/04-safety.md hazard table), never the feature "
             "names. A SiLA command's confirmation, a subscription's end, an expired execution UUID or a closed channel "
             "is not a device stop: a Stop acknowledgement and a cached idle property prove nothing about the "
             "instrument, and an acquisition can keep running after its caller gave up. A model-authored package "
             "never runs a native backend; every one refuses."),
    fidelity=("A controlled peer yields `contract_checked` evidence only: no gRPC, protobuf, metadata headers, TLS, "
              "server lifetime or instrument timing is modelled, and the peer's `observe` retirement contract has no "
              "native SiLA equivalent. Numbers and strings in the fake are placeholders."),
    pitfalls=("Servers of one repository often start in simulation mode (`SimulationController`); feature definitions "
              "differ per vendor; observable commands outlive their callers; a Binary property may arrive in chunks "
              "that must be deleted; licences of instrument wrappers are often unstated."),
    sources=("[Controlled SiLA 2 profile](../../sdk/docs/sila2-controlled-profile.md) and "
             "[driver authoring](../../sdk/docs/driver-authoring.md).",
             f"[sila-testing exemplar driver]({SILA_EXEMPLAR}/driver.py), [declarations]({SILA_EXEMPLAR}/declarations.py), "
             f"[fake]({SILA_EXEMPLAR}/fake.py), [tests]({SILA_EXEMPLAR}/test_driver.py), [facts]({SILA_EXEMPLAR}/facts.md) "
             f"and [result notes]({SILA_EXEMPLAR}/RESULT.json)."),
)
# --- w1-waiting-routing (2026-11-05): end ---
_NONE = {
    "dm-env": "dm_env and dm_control tasks", "pybullet": "PyBullet simulators", "isaac-sim": "Isaac Sim applications",
    "isaac-lab": "Isaac Lab task suites", "isaac-gym": "Isaac Gym environments", "webots": "Webots worlds",
    "unity": "Unity simulators", "sapien": "SAPIEN and ManiSkill environments", "drake": "Drake simulations",
    "brax-mjx": "Brax and MJX simulators", "habitat": "Habitat and iGibson environments", "airsim": "AirSim simulators",
    "cli-process": "command-line tools", "docker": "containerised services", "replay": "recorded-data replay",
    "other": "other engines and protocols",
}
_NONE_PITFALLS = {
    "isaac-sim": "Needs a GPU and a separate process; extension APIs change between releases.",
    "isaac-lab": "Designed for thousands of parallel environments; one device session needs num_envs=1.",
    "isaac-gym": "A preview-era package pinned to old Python and CUDA versions.",
    "unity": "Closed binaries, Windows or macOS builds and a GPU; ML-Agents protocol versions differ.",
    "airsim": "Upstream AirSim is archived; Cosys-AirSim is the maintained fork; Unreal version coupling.",
    "habitat": "Large scene datasets and GPU rendering.",
    "drake": "Contact solver parameters change results; AdvanceTo is duration-based.",
    "brax-mjx": "Batched JAX simulation conflicts with an exclusive single-device session.",
    "dm-env": "TimeStep semantics differ from Gymnasium; converting with shimmy is a recon decision.",
    "pybullet": "Action modes must be declared; GUI mode fails headless.",
    "webots": "Controllers are separate processes; the supervisor API is needed for state.",
    "sapien": "Vulkan GPU; asset licences differ from the code licence.",
    "cli-process": "Never pass model input to a shell; exit codes are not receipts.",
    "docker": "Image provenance; device passthrough is a deployment risk.",
    "replay": "Never replay into a live device automatically.",
    "other": "The family groups heterogeneous projects; treat it as needing design.",
}
for _name, _what in _NONE.items():
    FAMILY[_name] = dict(
        title=f"{_what[0].upper() + _what[1:]} (no helper planned)",
        rows=SIM_ROWS if _name not in ("cli-process", "docker", "replay", "other") else None,
        applicability=(f"Repos the catalogue files as {_what}. No Driver helper is planned before or after the pilot, "
                       "so their cards are recon-only (wave 4) or last (wave 6: GPU, Windows or an engine licence). "
                       "A simulator family needs a structural marker in the code, never only a README or name match."),
        hazards="The risk floor of every class still comes from the catalogue.",
        fidelity="Engine-specific; nothing here claims fidelity.",
        pitfalls=_NONE_PITFALLS.get(_name, ""),
    )


def bridge_status(family: str) -> tuple[str, str | None, str | None, str | None]:
    """(bridge_status, helper class, prerequisite, exemplar) of a registry family.

    ``available``: a pilot helper serves it; ``planned``: a post-pilot helper
    (cards carry ``blocked_on: helper:<name>``); ``none``: no helper is planned.
    """
    fam = T.FAMILIES.get(HELPER_FAMILY.get(family) or "")
    if fam is None:
        return "none", None, None, None
    if fam.helper:
        return "available", fam.helper, None, fam.exemplar
    return "planned", None, fam.prerequisite, None


def recipe_paths(records, out_dir: str) -> list[str]:
    return [os.path.join(out_dir, f"{family}.md") for family in sorted({r["families"][0] for r in records})]


def _examples(cards, records, family, limit=5):
    chosen = [cards[r["package_id"]] for r in records if r["families"][0] == family and r["package_id"] in cards]
    chosen.sort(key=lambda c: (c["wave"], c["rank"], c["package_id"]))
    return chosen[:limit]


def render_recipes(records, cards, recipe_notes, out_dir: str, build_ts: str) -> dict[str, str]:
    """``{path: markdown}`` for every family present in the records (``recipe_notes`` is unused provenance)."""
    del recipe_notes  # recon excerpts were pasted into unrelated families before (SIM-13); they stay in work/recon
    out = {}
    for path in recipe_paths(records, out_dir):
        family = os.path.basename(path)[:-3]
        meta = FAMILY.get(family) or FAMILY["other"]
        fam_records = [r for r in records if r["families"][0] == family]
        fam_cards = [cards[r["package_id"]] for r in fam_records if r["package_id"] in cards]
        status, helper, prerequisite, exemplar = bridge_status(family)
        strategies = Counter(c["decision"] for c in fam_cards)
        waves = Counter(c["wave"] for c in fam_cards)
        modes = Counter(m for r in fam_records for m in r["modes"])
        lines = [meta["preface"], ""] if meta.get("preface") else []
        lines += [f"# OpenMHS family: {family}", "", f"**{meta['title']}**", "",
                 f"_Generated by `MHS/registry/build_registry.py` on {build_ts} from {len(fam_records)} registry "
                 "records and their task cards. A plan, not a conformance claim._", ""]
        lines += ["- bridge_status: `" + status + "`" + (f" (`blocked_on: {prerequisite}`)" if prerequisite else ""),
                  f"- helper: `{helper}`" if helper else "- helper: none",
                  f"- exemplar: `{exemplar}`" if exemplar else "- exemplar: none", ""]
        lines += ["## Launch", "", "Every driver package starts the same way; per-repo configuration (environment id, "
                  "model path, port, baud rate, VISA resource) lives in the package's `driver.py`, never in launch "
                  "flags:", "", "```", LAUNCH, "```", "",
                  f"A package is done when `{DONE}` exits 0 (evidence `contract_checked`; a fake never yields an "
                  "MHS-Device level).", ""]
        lines += ["## Registry coverage", "",
                  f"- Repos: **{len(fam_records)}**",
                  "- Decisions: " + (", ".join(f"{k} {v}" for k, v in sorted(strategies.items())) or "none"),
                  "- Waves: " + (", ".join(f"{k}: {v}" for k, v in sorted(waves.items())) or "none"),
                  "- Dispatchable now: " + str(sum(1 for c in fam_cards if TC.dispatchable_now(c))),
                  "- Modes: " + (", ".join(f"{m} {n}" for m, n in sorted(modes.items())) or "none"), ""]
        lines += ["## Applicability", "", meta["applicability"], ""]
        lines += ["## Capability mapping", ""]
        rows = meta.get("rows")
        if rows:
            lines += ["| native call | OpenMHS target | notes |", "|---|---|---|"]
            for native, target, note in rows:
                lines.append(f"| {native} | {target} | {note} |")
        elif status == "planned":
            lines.append("The mapping is fixed when the helper lands; the applicability section lists its rules.")
        else:
            lines.append("No mapping is fixed for this family; recon cards decide per repo.")
        lines += ["", "Class ids come from `python3 -m mhs.driver catalog search <words>`. The deprecated classes "
                  "cap.device.describe.v1, cap.world.state.v1, cap.world.snapshot.v1 and cap.world.restore.v1 are "
                  "replaced by the protocol methods mhs.devices.get, mhs.resource.read, mhs.snapshot and mhs.restore.",
                  ""]
        lines += ["## Safety", "", "The risk floor of a device is the highest catalogue `risk_class` of its classes "
                  "(CAP-017); a driver may declare a higher risk, never a lower one. "
                  + meta.get("safety_requirements", "Hardware at R1 or above needs an `@estop` and a non-empty safe state. ")
                  + meta["hazards"], ""]
        lines += ["## Fidelity", "", meta["fidelity"], ""]
        if meta.get("pitfalls"):
            lines += ["## Pitfalls", "", meta["pitfalls"], ""]
        lines += ["## First task cards", ""]
        examples = _examples(cards, records, family)
        if examples:
            for card in examples:
                lines.append(f"- `{card['package_id']}`: {card['decision']}, wave {card['wave']}, rank "
                             f"{card['rank']}, `{TC.card_path_for(card)}`")
        else:
            lines.append("- none")
        lines += ["", "## Sources", "",
                  "- Task cards: `MHS/registry/tasks/<track>/<owner>__<repo>.json` (`schema/taskcard.schema.json`).",
                  "- Triage rules and the helper table: `MHS/registry/triage.py`; curated decisions: "
                  "`MHS/registry/overrides/`.",
                  "- Driver API and gate: `MHS/sdk/docs/driver-authoring.md`; exemplars: `MHS/drivers/`."]
        lines += ["- " + source for source in meta.get("sources", ())]
        out[path] = "\n".join(lines).rstrip() + "\n"
    return out
