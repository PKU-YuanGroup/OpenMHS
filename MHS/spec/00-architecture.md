# MHS-000 — OpenMHS Architecture Overview (informative)

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

| Field | Value |
|---|---|
| Document | MHS-000 (informative overview and decision record) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | informative: it wins nothing and constrains nothing ([README](README.md) §1) |
| Supersedes | Nothing. Informed by the Anthropic MHS research preview (Aug 2026, apply-only, no public wire specification) and by prior community artifacts catalogued in the project's private research notes. |
| Audience | Driver/bridge authors, instrument vendors, simulation maintainers, agent-harness authors, lab and factory integrators |

This document explains the object model, the wire protocol, the safety and fidelity
semantics, the driver and adapter model, the registry and the conformance ladder of
OpenMHS, and why they are shaped as they are. It is an **overview**: the rules are
in [core.md](core.md), [driver-profile.md](driver-profile.md) and chapters 01 to 10,
and where this file and one of them disagree, that document is right and this file is
in error. Section numbers here are stable because other documents cite them as
background. The normative text and its key words live elsewhere; this file contains
no requirements.

---

## 1. Mission and problem statement

### 1.1 Mission

MHS is an open, versioned, machine-checkable contract between **agents that
reason** and **equipment that acts**. It lets an AI agent — or a plain Python
program — discover a device it has never seen, understand what that device can
do and what those actions mean physically, execute actions under an enforced
safety envelope, and obtain verifiable evidence of what actually happened.

MHS is model-agnostic and harness-agnostic. It does not assume Claude, GPT, an
MCP client, or any particular agent loop. It composes with MCP, it does not
compete with it: MCP standardises how a model reaches *tools*, MHS standardises
what a *tool that moves matter* means.

### 1.2 The three failures MHS must fix

1. **Integration is bespoke.** Every instrument ships its own SDK, transport and
   vocabulary. A lab with twelve instruments writes twelve translators, and the
   translators do not compose. The Anthropic preview names this correctly but
   leaves the wire format unpublished, so no ecosystem can form around it.
2. **Agents cannot know what is safe.** An LLM can read a docstring and still not
   know that `set_power(500)` will destroy a laser, that the door interlock is
   open, or that the arm is already holding a plate. Semantics, limits, hazards
   and interlocks must be **in-band and machine-readable**, not in a PDF.
3. **Simulation and hardware are different universes.** Nearly all agent
   development for physical systems happens in simulators (this workspace alone
   contains 1,922 robotics repos, the majority of them simulators). A standard
   that only describes "a driver for a real device" cannot be adopted by the
   people who most need it, and a standard that pretends simulation *is* hardware
   will get someone hurt. MHS therefore makes the **sim/hardware duality** a
   first-class, explicitly declared property of every endpoint — same contract,
   different declared mode and fidelity.

### 1.3 Non-goals

MHS is **not**: a safety certification or a safety-rated control channel; a
real-time control bus (no hard real-time guarantees); a replacement for MCP,
ROS 2, SiLA 2, OPC UA, SCPI, EtherCAT or vendor SDKs; a device-driver warehouse;
a model-training or dataset format; a physical connector/pinout standard; a
marketplace or a certification authority. MHS is a thin, strict *semantic and
behavioural envelope* around all of those.

### 1.4 Relationship to the Anthropic research preview

In August 2026 Anthropic opened a research preview of a Model Hardware Standard (MHS) to selected labs and
manufacturers. It describes a standardised hardware driver, read/write primitives, standardised discovery,
per-device natural-language tags that produce a generated reference file, and three control mechanisms (MCP, CLI,
code files). That announcement is the reason this project exists. It is not a specification: the preview is closed
and apply-only, and no wire format, schema, message set or reference implementation has been published
([MHS-D](appendix-d-anthropic-mhs.md) §1). OpenMHS is therefore an independent, open specification that starts from
the same problem statement, not a reimplementation or a compatible dialect of the preview.

What OpenMHS adopts from the preview's framing: the integration-cost argument; physical knowledge held in
machine-readable metadata rather than in manuals; user-authored natural-language tags as first-class data; a
generated, model-readable reference view of each device; the three control mechanisms; and chaining commands into
code files so that long work leaves the agent's reasoning loop (here `mhs run`; a server-side composition method is
reserved and not implemented in 0.9).

What OpenMHS defines that the preview's written descriptions do not state: a JSON-RPC wire protocol, a receipt and
hash-chained evidence model, an endpoint-enforced safety envelope with permits and e-stop semantics, a declared
fidelity contract for simulated and hybrid devices, an adapter and driver model for existing SDKs and simulators, an
executable conformance ladder, a federated registry, and versioning and governance. These are this project's
choices, not claims about the preview's internals.

Two points need care. First, QuEra describes MHS as enforcing "device-declared bounds, interlocks, and emergency
stops at the hardware interface, independent of the model" ([MHS-D](appendix-d-anthropic-mhs.md) §3). OpenMHS
enforces the envelope at the endpoint, below the model, and asks for an independent hardware stop, but it refuses
the stronger claim: it is not a safety-rated channel and nothing here runs in a certified safety controller
(04 §10). Second, the preview's origin is a state dictionary in shared memory for co-located processes. OpenMHS 0.9
is a supervisory contract between an agent and an endpoint, not a real-time bus: state is read through sessions,
mutations are receipted capabilities, and a shared-memory fast path may exist inside one host as a deployment
property of an adapter or bridge, never as an MHS guarantee.

Terminology maps but does not bind: an "MHS driver" is here a **driver package**
([driver-profile.md](driver-profile.md)); the "reference file" is the generated `reference.json` and `REFERENCE.md`;
"tags" are the manifest's tags plus sourced facts; "read/write primitives" are `mhs.resource.read` and
`cap.device.configure.v1`; "control mechanisms" are the MCP, CLI and code-file surfaces ([core.md](core.md) §10).
The unqualified word "driver" means an OpenMHS driver package; a vendor's own software is "the native driver" or
"the upstream SDK".

Conformance, badges, reports and registry trust levels come only from this specification's rules
([MHS-001](01-conformance.md), [MHS-007](07-registry.md)). They are not Anthropic's safety evaluations or an
Anthropic endorsement, and they must not be described as "the Anthropic MHS" or as compatible with the research
preview. The preview's own caveats apply without qualification (it does not yet cover devices without a programmable
interface, agents still need expert oversight, its safety evaluations are still being built), and operators remain
responsible for independent hardware safety.

If Anthropic publishes a wire specification or opens the standard, the editors treat it as input to the RFC process
([MHS-010](10-governance.md) §2): align this document set with it, or, if the two cannot coexist under one name,
rename this project. Until then no document, website page, paper or registry record may claim compatibility,
equivalence or endorsement. The relationship is conceptual kinship under a shared problem statement, with credit to
the preview's authors and launch partners for the ideas above.

---

## 2. Design axioms

These ten axioms were chosen deliberately; each one rejects a simpler design
that fails at the scale this standard targets (thousands of heterogeneous
backends). The rejected alternative is recorded in §14.

- **A1. One contract, two worlds.** Physical devices and simulations share one
  object model; they differ only in the declared `mode` and the mandatory
  fidelity contract. Nothing in the core protocol branches on "sim vs real".
- **A2. Capabilities, not device classes.** The unit of interoperability is a
  typed capability bound to a resource, not a vendor product category. A robot
  arm and a microscope both expose `observe` and `actuate`; what differs is the
  capability class, its schema and its safety envelope.
- **A3. Semantics in-band.** Every capability carries (a) a machine schema, (b)
  units, (c) physical effects and hazards, (d) human-readable semantic tags, (e)
  pre/post-conditions. The *device profile* an agent reads is
  **generated from the driver and manifest**, so it cannot drift from what the code does.
- **A4. Safety is enforced at the endpoint.** Limits, interlocks, permits, risk
  class and e-stop are properties of the equipment side. A client's claim about
  safety is advisory and is not trusted. The model is never the last line
  of defence.
- **A5. Every effect leaves a receipt.** A command is idempotent by
  `command_id`; state carries a monotone `revision` and a canonical
  `state_hash`; every accepted, rejected, failed, cancelled or unknown outcome
  is recorded and exportable as hash-chained evidence.
- **A6. No silent simulation.** `mode ∈ {hardware, simulated, hybrid, replay}` is
  declared in the device manifest and again in the session; a mismatch is an
  error, never a fallback. A simulator's identity is distinct from the physical
  device it models, and the link between them is explicit (`models`/`derived_from`).
- **A7. Bounded blocking.** Every request carries a deadline; long actions become
  operations with progress events and cancellation; no method may block
  unboundedly. Physical cancellation resolves to a declared safe state.
- **A8. Thin normative core, versioned ontology.** A small set of methods is
  mandatory; capability classes live in a separately versioned registry and
  extend without breaking the core. Implementers can ship a device in a day.
- **A9. Wrap, do not rewrite.** Existing SDKs, environments and protocols are
  integrated through a per-repository **Driver class** on reusable
  **bridge families** (or, optionally, a declarative **adapter**). The cost of MHS
  support is a short, checkable driver, not a new endpoint.
- **A10. Conformance is executable.** A claim of support is a level (CL0–CL5)
  backed by a suite-produced, machine-readable, hash-addressed report. Prose
  claims are not conformance.

---

## 3. Conceptual model

### 3.1 Layers

```text
┌────────────────────────────────────────────────────────────────────────┐
│ HOST PLANE            agent harness / OpenAI4S / MCP client / CLI      │
│                       policy, approvals, evidence ledger, replay      │
├────────────────────────────────────────────────────────────────────────┤
│ BINDING PLANE         MHS/JSON-RPC (stdio, HTTP, WS)                   │
│                       MCP projection · CLI · Python/JS code API        │
├────────────────────────────────────────────────────────────────────────┤
│ CONTRACT PLANE        endpoint · device · resource · capability        │
│                       session · command · operation · receipt          │
│                       safety envelope · permits · evidence             │
├────────────────────────────────────────────────────────────────────────┤
│ ADAPTER PLANE         Driver class (or mhs-adapter) + bridge runtime   │
│                       python-object · serial · scpi · gymnasium ·      │
│                       mujoco · replay (ros2, http, sila2 ... planned)  │
├────────────────────────────────────────────────────────────────────────┤
│ EQUIPMENT PLANE       hardware driver · simulator · SDK · protocol     │
└────────────────────────────────────────────────────────────────────────┘
```

The **contract plane** is what MHS standardises. The **adapter plane** is how
existing ecosystems join it. The **binding plane** is how programs talk to it.

### 3.2 Entities

| Entity | Identity | Role |
|---|---|---|
| **Endpoint** | `endpoint_id` = `mhs://host[:port][/prefix]` | A server that speaks MHS. Owns one or more devices, one safety domain, one evidence chain. |
| **Device** | `device_id` = URI under the endpoint; `instance_id` = ULID | A logical machine: a robot, an instrument, a simulated world. Declares mode, resources, capabilities, safety, fidelity, profile. |
| **Resource** | `resource_id` = local name | A stateful thing inside a device: arm, gripper, well-plate stage, camera, world. Has a state schema, a revision, a sampling model. |
| **Capability** | `capability_id` = `cap.<class>.v<major>` | The contract for one class of action on one resource: verb, input/output schemas, units, semantics, safety binding, determinism. |
| **Session** | `session_id` (opaque, prefixed `mhs_s_`) | A scoped lease: principal × device(s) × granted capabilities × mode × safety context × TTL. Every mutation happens inside a session. |
| **Command** | `command_id` (ULID, caller-generated) | The idempotent request to invoke a capability. |
| **Operation** | `operation_id` | Handle for a long-running command; exposes progress, cancellation, final receipt. |
| **Receipt** | `receipt_id` (ULID) | Immutable record of an outcome, chained into the evidence log. |
| **Permit** | `permit_id` | Approval artifact authorising a gated capability for a specific input digest, principal, scope and TTL. |
| **Driver** | `device_id` of its device; package `MHS/drivers/<track>/<owner>__<repo>/` | The per-repository deliverable: a Driver class, a fake backend, sourced limits and facts, a generated reference file ([driver-profile.md](driver-profile.md)). |
| **Adapter** | `adapter_id` | Optional declarative mapping from a repo/SDK/engine to one or more devices. |
| **Bridge** | `bridge_id` | Reusable runtime that executes the mapping of a driver or adapter for one family (python-object, serial, SCPI, Gymnasium, MuJoCo, replay). |
| **Registry** | `registry_id` | Federated index of packages, adapters, devices and conformance claims. |

### 3.3 State model

- Each device has a **revision**: a monotone `uint64` that advances when a
  command changes the device's state (a changed state hash). Reads and rejected
  commands never advance it ([core.md](core.md) CORE-095).
- Each resource exposes a **state document** validated by its schema. The device
  publishes `state_hash = "sha256:" + hex(SHA-256(JCS(state)))`, where JCS is
  RFC 8785 canonical JSON over the device's `state` object (resources keyed by
  `resource_id`, no volatile fields; timestamps and sequence numbers are
  excluded from the hash and listed in `hash_exclusions`).
- A **snapshot** is `{device_id, instance_id, revision, state_hash, state,
  mode, fidelity_digest, created_at}`. Restoring a snapshot is permitted only in
  `simulated` or `replay` mode and only when `fidelity.snapshot_restore` is true.
- Volatile telemetry (high-rate sensor streams) is **not** part of normative
  state. It travels on subscription streams with its own sequence numbers and is
  referenced from receipts by `telemetry_ref`.

### 3.4 Action lifecycle

```text
session.open ──► granted(session_id, capabilities, mode, ttl)
   │
   ├─ resource.read ──► {revision, state, state_hash}
   │
   ├─ command(command_id, capability, input, expected_revision?)
   │        │
   │        ├─ validate: the evaluation order of core.md §5 (grants ▸ latch ▸ limits ▸ permit ▸ interlocks ▸ revision)
   │        ├─ accepted  ──► receipt{status: accepted|running, operation_id?}
   │        ├─ completed ──► receipt{status: completed, state_revision_after, output, effects}
   │        ├─ rejected  ──► receipt{status: rejected, error}
   │        └─ unknown   ──► receipt{status: unknown, error: MHS.OUTCOME.UNKNOWN}
   │
   ├─ subscribe(streams) ──► notifications{seq, stream, payload}
   ├─ operations.get|cancel(operation_id)
   └─ session.close ──► receipt of session summary
```

Rules:

1. **Preconditions** are evaluated before any effect. A failed precondition
   returns `rejected` and changes neither state nor revision.
2. **Idempotency.** Replaying a `command_id` with the same `input_digest`
   returns the retained receipt with `replayed: true`. Reusing a `command_id`
   with a different input returns `MHS.CONFLICT.COMMAND_ID_REUSE` and no effect.
3. **Optimistic concurrency.** If `expected_revision` is supplied and does not
   equal the current revision, return `MHS.CONFLICT.REVISION` with
   `data.current_revision`; no effect.
4. **Unknown outcomes are first-class.** A lost response after an irreversible
   effect surfaces as `MHS.OUTCOME.UNKNOWN`; the receipt remains retrievable
   by `command_id` and the client observes state before retrying. A deadline
   bounds only the wait for the response; a command that outlives it keeps running
   and its final receipt reconciles the `unknown` one ([core.md](core.md) CORE-100).
5. **Cancellation** is best-effort. A cancelled physical action transitions
   to the device's declared `safe_state`; the receipt records `cancelled` plus
   `effects` observed and `safe_state_achieved: true|false`.
6. **Concurrency.** A capability declares `concurrency: exclusive|shared|
   serialized`. Exclusive capabilities hold the device for the operation;
   conflicting requests receive `MHS.DEVICE.BUSY` rather than queueing
   indefinitely.

---

## 4. Capability ontology

### 4.1 Shape

A capability class is defined once, in the MHS Capability Registry, and bound to
resources in a device manifest.

```json
{
  "capability_id": "cap.fluid.aspirate.v1",
  "title": "Aspirate liquid",
  "verb": "invoke",
  "resource_kinds": ["lab.liquid_handler", "lab.pipette"],
  "input_schema": { "$ref": "https://mhs.openai4s.org/schema/0.9/cap/fluid.aspirate.v1.input.json" },
  "output_schema": { "$ref": "https://mhs.openai4s.org/schema/0.9/cap/fluid.aspirate.v1.output.json" },
  "summary": "Draw a specified volume of liquid from a labware well into a pipette tip.",
  "tags": ["liquid handling", "pipetting", "aspirate", "volume", "labware"],
  "units": { "volume": "uL", "flow_rate": "uL/s", "position": "mm" },
  "effects": ["material.transfer", "consumable.tip_used"],
  "hazards": ["cross_contamination", "spill", "bubble_formation", "volume_error"],
  "preconditions": ["tip_attached", "liquid_present", "labware_loaded"],
  "postconditions": ["volume_in_tip >= requested_volume * (1 - tolerance)"],
  "determinism": "exact",
  "constraints": { "rate_limit": { "max_per_minute": 60 }, "concurrency": "exclusive" },
  "safety": { "risk_class": "R1", "limits": { "volume": { "min": 0, "max": 1000 } } },
  "conformance_tests": ["CAP-FLUID-001", "SAFE-R1-002"]
}
```

### 4.2 Verbs

| Verb | Meaning | Core method | Notes |
|---|---|---|---|
| `read` | Observe a resource's state or a computed quantity | `mhs.resource.read` | No side effect on the physical world. |
| `write` | Set a declared, persisted operating parameter or safe setpoint | `mhs.resource.write` | Still a mutation: a command of the `cap.device.configure.v1` binding, revision-bound, limit-checked. |
| `invoke` | Execute a discrete operation with a physical effect | `mhs.command` | The workhorse. Idempotent, receipted, cancellable. |
| `subscribe` | Receive a stream (state, telemetry, events, log, progress) | `mhs.subscribe` | Sequenced; gaps are explicit. |
| `compose` | Run a named, versioned, deterministic composition of capabilities | `mhs.composition.run` | Reserved in 0.9, not implemented; code files run on the client instead. |

### 4.3 Initial capability classes (v1.0 core set)

The catalogue ([`capabilities.json`](capabilities.json), [03](03-capability-registry.md) §7,
[appendix A](appendix-a-capabilities.md)) is authoritative: it holds the classes of the 0.9 core set, and the list
below is a sketch of its domains. Class schemas are served by `mhs.schema.get`.

**World / simulation** (mode `simulated` or `hybrid` only): `world.reset`,
`world.step`, `world.state`, `world.snapshot`, `world.restore`, `world.render`,
`world.seed`.

**Motion**: `motion.joint_position`, `motion.joint_velocity`,
`motion.joint_torque`, `motion.cartesian_pose`, `motion.cartesian_twist`,
`motion.mobile_base`, `motion.stop`, `motion.home`, `motion.estop` (device-level).

**Manipulation**: `manipulation.grasp`, `manipulation.release`,
`manipulation.place`, `manipulation.pick`.

**Sensing**: `sensing.read`, `sensing.image`, `sensing.point_cloud`,
`sensing.force_torque`, `sensing.imu`.

**Lab: fluid**: `fluid.aspirate`, `fluid.dispense`, `fluid.transfer`, `fluid.mix`,
`fluid.wash`, `fluid.level`.

**Lab: sample**: `sample.move`, `sample.incubate`, `sample.centrifuge`,
`sample.seal`, `sample.unseal`, `sample.store`.

**Lab: imaging / optics**: `imaging.capture`, `imaging.focus`,
`imaging.illumination`, `optics.set_power`, `optics.shutter`, `optics.align`.

**Instruments / measurement**: `measure.voltage`, `measure.current`,
`measure.resistance`, `measure.spectrum`, `measure.intensity`, `measure.mass`,
`measure.temperature`, `measure.pressure`, `measure.flow`.

**Actuation / thermal**: `thermal.setpoint`, `actuation.gpio`,
`actuation.valve`, `actuation.pump`.

**Compute / process**: `compute.submit`, `compute.cancel`, `process.run`
(bounded CLI execution; always R1+ unless declared read-only).

**Generic**: `device.describe`, `device.calibrate`, `device.self_test`, and `device.configure`, the class behind
`mhs.resource.write` (named parameters of any resource).

### 4.4 Semantic tags

Every capability and device carries `tags`: lowercase natural-language
phrases describing *what it does in the world*, together with a prose
`summary` and `notes` for model consumption. Tags are not free-form marketing
text; they are indexed by the registry and used for capability search (e.g.
"move a plate between instruments"). This is the machine-readable version of the
preview's "write what you know about your hardware in natural language" idea,
with the crucial addition that tags are attached to a typed contract.

### 4.5 Extensions

Vendor- or domain-specific classes are namespaced `x-cap.<owner>.<name>.v<N>` (or
`cap.x.<vendor>.<class>.v<N>` once published in the registry), carry an inline schema and never redefine core classes. `additionalProperties` is permitted only
inside `input_schema` objects marked `x-mhs-open: true`; core schemas are closed.

### 4.6 Units, numbers, time

- Units are UCUM codes (`m`, `mm`, `rad`, `deg`, `s`, `ms`, `K`, `Cel`, `L`,
  `uL`, `N`, `V`, `A`, `Hz`, `Pa`, `kg`, `lx`, `cd`, `%`).
- Numeric fields carry `x-mhs-unit`; bridges convert at the boundary and
  never guess. Ambiguous fields without a unit are a schema error.
- Time: RFC 3339 UTC strings for wall clock, plus an optional monotone
  `mono_ms`; `deadline_ms` is a duration from receipt, not a wall-clock instant.
- Identifiers: ULID. Digests: `sha256:<64 hex>`. Large payloads: artifact
  references `mhs+artifact://<endpoint>/<artifact_id>` or base64 with
  `x-mhs-encoding`.

---

## 5. Wire protocol

### 5.1 Base

MHS/1.0 (wire revision 1 of OpenMHS 0.9) is **JSON-RPC 2.0** (UTF-8 JSON, single or
batch) over a transport binding. Method names are namespaced `mhs.*`. Notifications are
used for subscription events (`mhs.event`), which carry progress and safety alerts.
The `result` of a receipt-returning method is the receipt itself, with no wrapper
([core.md](core.md) CORE-093).

Request:

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
{"jsonrpc": "2.0", "id": "01J8Z…", "method": "mhs.command", "params": {…}}
```

Every `params` object may carry `trace_id` (W3C trace context string) and carries
`deadline_ms` for methods that can block (`command`, `resource.read`,
`mhs.resource.write`, `mhs.operations.*`, `mhs.snapshot`, `mhs.restore`, `mhs.safety.*`;
the e-stop needs none).

Response: standard `result` or `error`. Errors are:

```json
{"jsonrpc": "2.0", "id": "01J8Z…", "error": {
  "code": -32010,
  "message": "Interlock open: safety door",
  "data": {
    "mhs_code": "MHS.SAFETY.INTERLOCK_OPEN",
    "retryable": false,
    "current_revision": 41,
    "interlocks": [{"id": "door_closed", "state": "open"}],
    "remediation": "Close the safety door and call mhs.safety.reset."
  }
}}
```

JSON-RPC `code` is structural; `data.mhs_code` is the stable semantic code.
Implementations branch on `data.mhs_code`, never on `message`.

### 5.2 Methods

The protocol has 26 methods. [02](02-wire-protocol.md) §3 is the table with their parameters, results and
conformance levels; this overview only groups them. The reference endpoint implements 24 of the 26:
`mhs.composition.run` is reserved and `mhs.registry.search` is not an endpoint method
([02](02-wire-protocol.md) §15).

| Group | Methods |
|---|---|
| Discovery | `mhs.hello`, `mhs.devices.list`, `mhs.devices.get`, `mhs.schema.get` |
| Sessions | `mhs.session.open`, `mhs.session.heartbeat`, `mhs.session.close` |
| Resources | `mhs.resource.read`, `mhs.resource.write` (a receipt of `cap.device.configure.v1`) |
| Commands and operations | `mhs.command`, `mhs.operations.get`, `mhs.operations.list`, `mhs.operations.cancel` |
| Subscriptions | `mhs.subscribe`, `mhs.unsubscribe` |
| Snapshots (simulated and replay devices only) | `mhs.snapshot`, `mhs.restore` |
| Safety | `mhs.safety.status`, `mhs.safety.estop`, `mhs.safety.reset`, `mhs.safety.permit` |
| Evidence and conformance | `mhs.evidence.export`, `mhs.evidence.verify`, `mhs.conformance.report` |
| Reserved, or not on an endpoint | `mhs.composition.run`, `mhs.registry.search` |

Subscription notification (JSON-RPC notification, no `id`):

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
{"jsonrpc":"2.0","method":"mhs.event","params":{
  "subscription_id":"sub_…","seq":1042,"ts":"2026-10-20T14:03:59.221Z",
  "stream":"state","device_id":"mhs://lab-01/robot/ur5e-1",
  "resource_id":"arm","revision":77,"state_hash":"sha256:…","payload":{…}}}
```

`seq` is strictly increasing per subscription. A detected gap is
delivered as `{"stream":"control","type":"gap","from":a,"to":b}` — silently
dropping samples is non-conformant. Slow consumers receive
`MHS.LIMIT.BACKPRESSURE` on `subscribe` rather than unbounded buffering.

### 5.3 Receipt

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
{
  "receipt_id": "01J8ZQ3V6Y…",
  "command_id": "01J8ZQ3V6X…",
  "session_id": "mhs_s_…",
  "endpoint_id": "mhs://lab-01.lab.local:7331",
  "device_id": "mhs://lab-01.lab.local:7331/robot/ur5e-1",
  "capability_id": "cap.motion.joint_position.v1",
  "resource_ids": ["arm"],
  "input_digest": "sha256:…",
  "status": "completed",
  "mode": "simulated",
  "accepted_at": "2026-10-20T14:03:58.900Z",
  "started_at": "2026-10-20T14:03:58.902Z",
  "ended_at": "2026-10-20T14:03:59.221Z",
  "state_revision_before": 76,
  "state_revision_after": 77,
  "state_hash_after": "sha256:…",
  "output": { "reached": true, "joint_positions": [0.0, -1.2, 0.7, …] },
  "effects": [
    {"kind": "motion.joint", "summary": "arm moved to target", "reversible": true, "severity": "R1"},
    {"kind": "consumable", "summary": "none", "reversible": true, "severity": "R0"}
  ],
  "progress": {"ticks": 240, "percent": 100},
  "telemetry_ref": "mhs+artifact://lab-01/01J8ZQ…/trace",
  "error": null,
  "approvals": [{"permit_id": "permit_…", "principal": "human:alice", "approved_at": "…"}],
  "replayed": false,
  "evidence": {"seq": 812, "prev_digest": "sha256:…", "digest": "sha256:…"}
}
```

`status` ∈ `accepted | running | completed | failed | rejected | cancelled |
unknown`. A `rejected` receipt has no `state_revision_after` change and is
retained for the same duration as accepted ones. Receipts produced by methods
that are not a catalogue capability invocation (restore, safety.estop,
safety.reset, operations.cancel, composition.run) use the reserved capability ids
`cap.internal.<operation>.v1`, which are never bound to a device capability;
`mhs.resource.write` receipts carry the catalogue class `cap.device.configure.v1`.

### 5.4 Transport bindings

| Binding | Status | Details |
|---|---|---|
| **T1 stdio** | mandatory | Newline-delimited JSON-RPC on stdin/stdout; logs on stderr only; one message per line; UTF-8; no BOM. Launched by the host as a child process. |
| **T2 HTTP** | mandatory | `POST /mhs/v1/rpc` (single or batch, `application/json`); `GET /mhs/v1/events` (Server-Sent Events for subscriptions); `GET /.well-known/mhs.json` (endpoint descriptor); `GET /mhs/v1/schema/{ref}`. TLS is required when the endpoint is not loopback (the reference endpoint serves loopback, or non-loopback only with bearer tokens behind a TLS proxy); `Authorization: Bearer <token>` or mTLS. |
| **T3 WebSocket** | optional (not implemented by the reference SDK) | `/mhs/v1/ws`, JSON-RPC frames, subscription notifications multiplexed by `subscription_id`. |
| **T4 MCP projection** | mandatory (host profile) | Each bound capability is exposed as an MCP tool named `mhs__<device_slug>__<capability_slug>`; the tool's `inputSchema` is the capability input schema plus optional `session_id`; `tools/call` maps to `mhs.command`, `isError` maps from MHS errors with `structuredContent.mhs_error`; resources map to `mhs://` URIs; progress maps to MCP progress notifications. Discovery, `hello` and session management are handled by the projection shim, not by the model. |
| **T5 CLI** | recommended | `mhs` CLI: `serve`, `driver`, `validate`, `devices`, `describe`, `read`, `write`, `call`, `session`, `estop`, `status`, `reset`, `evidence`, `run` (code files), `discover`, `conform`, `registry`. Commands are thin clients with `--json` output ([08](08-transports.md) §6). |
| **T6 Code API** | recommended | Reference Python package `mhs`: `mhs.connect(endpoint)`, typed client, `client.invoke(...)`, context-managed sessions, and `mhs.run.lab(...)` for code files. Generated per-device bindings are optional. |

HTTP endpoints reject requests whose `Content-Type` is not JSON, enforce request size
limits, check the `Host` and `Origin` headers, and accept GET only for the well-known
descriptor, the schema route and the event stream ([core.md](core.md) §14).

### 5.5 Version negotiation

- `mhs.hello` negotiates `mhs_version`. Client sends supported versions;
  server picks the highest mutually supported and returns it. Negotiation of a
  MAJOR version mismatch fails closed with `MHS.PROTOCOL.VERSION_UNSUPPORTED`.
- Capability classes are versioned independently; unknown class with known MAJOR
  is usable only if the endpoint declared it; unknown MAJOR is rejected.
- `MHS_PROTOCOL_VERSION` is a JSON-RPC-adjacent constant in code APIs; it is not
  duplicated per message.

---

## 6. Safety and governance

### 6.1 Risk classes

| Class | Meaning | Examples |
|---|---|---|
| **R0** | Observational. No physical effect; data only. | temperature read, camera capture, sim state read |
| **R1** | Low-energy, reversible, bounded. | small joint motion in free space, LED/illumination, valve open/close |
| **R2** | High-energy, irreversible or destructive if wrong. | pipetting into a plate, centrifuge, laser above class 1, mobile base transit, plate transfer |
| **R3** | Hazardous to people, environment or samples; requires human presence and/or permit. | high-force contact, biological/radiological handling, high voltage, class 3B+ laser, heating above safe limits |

A device's declared `risk_class` is the maximum over its bound capabilities.
Sessions requested with mode `hardware` on an R3 device require an
`approval_context` naming a responsible human principal.

### 6.2 Envelope enforcement

The endpoint evaluates every command in a fixed order **before** executing, and
refuses at the first failure with no side effect: principal, session and grants,
binding, `command_id`, the e-stop latch, mode and arming, structure, limits (every array
element and nested leaf), the remaining schema bounds, permit and cumulative budgets,
interlocks (`closed|open|unknown`; only `closed` permits actuation), and finally the
device lock and `expected_revision`. The order and every refusal code are in
[core.md](core.md) §5 (CORE-060). A violation returns `rejected` with the
corresponding `MHS.SAFETY.*` or `MHS.CONFLICT.*` code; nothing is actuated and the
revision does not advance.

### 6.3 E-stop

- Every device manifest declares `safety.estop`: `{kind: hardware|software|both,
  latching: bool, reset: "mhs.safety.reset", latency_ms: int, physical_ref?}`.
- `mhs.safety.estop` takes effect within `latency_ms`: it latches the device first,
  then cancels running operations, stops the native device and brings outputs to
  `safe_state` (declared per resource). An unconfirmed stop is a `failed` receipt
  `MHS.SAFETY.SAFE_STATE_UNREACHED`, never a success ([core.md](core.md) CORE-074 to CORE-077).
- Release/close/reset does not restart equipment. `mhs.safety.reset` succeeds
  only when all hard interlocks read `closed`, nothing is running and no stop attempt is
  pending; a new start command is still required ([core.md](core.md) CORE-080 to CORE-083).
- **MHS is never a safety-rated channel.** The specification asks that a hardware
  e-stop exist independently and in addition to any MHS path. Endpoints report
  `MHS.SAFETY.NOT_CERTIFIED` in `hello` (`features` array) and hosts display
  this warning to the operator.

### 6.4 Permits and approvals

- `requires_permit` lists capability patterns (e.g. `cap.optics.*` on R3).
- A permit is issued by `mhs.safety.permit` after the host's policy engine
  collects approvals; approvals are opaque records with `principal`, `method`
  (`human_click`, `policy_rule`, `dual_control`) and `evidence_ref`.
- Permits are single-use by default, scoped to the `input_digest`, and expire.
- Reuse or replay of a permit with a different input returns
  `MHS.SAFETY.PERMIT_INVALID`.

### 6.5 Sessions, principals, least privilege

- `principal` = `{id, kind: human|agent|service, display_name}`. Endpoints
  authenticate the transport caller and map it to a principal (a bearer token
  carries its own; an operator is a `human` with `x-meta.role` `operator`). Local stdio
  endpoints may treat the launching process as the principal.
- `session.open` grants the intersection of requested capabilities with the
  device's `access` policy; grants are minimal and per binding.
- Sessions expire (`ttl_s`, refreshed by heartbeat). Expiry releases leases and
  transitions any running operation to cancellation-to-safe-state.
- One session does not observe another session's private resources; for
  simulators, session isolation is best done as an independent world instance.

### 6.6 Audit and evidence

- Every receipt is appended to the endpoint's evidence log: tamper-evident hash
  chain `digest_i = sha256(JCS(receipt_i \ {evidence}) || digest_{i-1})`, with
  `digest_0` from an endpoint genesis record.
- `mhs.evidence.export` returns the bundle plus endpoint metadata; 
  `mhs.evidence.verify` re-derives the chain offline. Optional detached JWS
  signature (`EdDSA` or `ES256`) binds the head digest to an endpoint key
  published in the registry.
- Evidence is retained for at least 30 days (configurable) and is not
  deletable through the protocol without a `MHS.EVIDENCE.TRUNCATED` marker.

---

## 7. Modes and the fidelity contract

### 7.1 Mode

`mode` is declared in the device manifest and requested again in every session.

| Mode | Meaning | Mutations | Restore | Notes |
|---|---|---|---|---|
| `hardware` | Real equipment | yes | no | Fidelity contract not required. |
| `simulated` | Model-only world | yes, in the model | if supported | A fidelity contract is mandatory. |
| `hybrid` | Digital twin: model follows real state or vice versa | yes, with declared authority | only for model side | A fidelity contract is mandatory; `authority` declares which side is truth for which resource. |
| `replay` | Recorded evidence/session, read-only | no (except seek) | yes | Fidelity contract inherited from the recording; `MHS.MODE.READ_ONLY`. |

Rules ([core.md](core.md) §8): a session requesting a mode other than the device's declared mode is
rejected (`MHS.SESSION.MODE_MISMATCH`). A simulator never claims to be a
hardware device; it declares `models: [device_id]` when it models one, and its
`device_id`/`instance_id` differ. Switching sim→hardware is a different
endpoint and device, never a flag on an existing session.

### 7.2 Fidelity contract

Required for `simulated` and `hybrid` devices:

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
"fidelity": {
  "engine": "mujoco|pybullet|gazebo|isaac|webots|unity|drake|genesis|custom|analytic",
  "fidelity_level": "F0|F1|F2|F3",
  "determinism": {"kind": "exact|seeded|statistical|none",
                   "seed_control": "parameter|reset_required|none",
                   "notes": "..."},
  "timestep_ms": 2.0,
  "realtime_factor": 1.0,
  "clock": "lockstep|free_running|external",
  "reset": "full|partial|none",
  "snapshot_restore": true,
  "validation": {"against_device": "…", "metrics": {"pose_rmse_m": 0.004},
                 "evidence_ref": "sha256:…", "validated_at": "2026-08-01"},
  "gaps": ["no fluid dynamics", "rigid contacts only", "no camera noise model"]
}
```

- **F0**: kinematic/analytic (no dynamics). **F1**: rigid-body dynamics with
  contacts. **F2**: actuator, sensor and noise dynamics modeled. **F3**: validated
  against the referenced physical device with reported metrics.
- `determinism.kind = exact` is needed for CL4 replay claims on simulated
  devices; `seeded` records the seed in the receipt and echoes it through
  `world.seed`.
- `realtime_factor` is reported and hosts do not assume wall-clock pacing;
  `clock` says who advances simulated time.
- `gaps` is listed whenever non-empty and is shown to the agent in the profile.
  Hiding a fidelity gap is a conformance failure.

---

## 8. Discovery and registry

### 8.1 Endpoint discovery

1. **Well-known descriptor** — HTTP endpoints serve
   `GET /.well-known/mhs.json` without authentication:

   ```json
   {"mhs_version": "1.0", "endpoint_id": "mhs://lab-01.lab.local:7331", "display_name": "Lab bench 1",
    "transports": {"http": "/mhs/v1/rpc", "sse": "/mhs/v1/events"},
    "auth": ["bearer"],
    "devices": ["mhs://lab-01.lab.local:7331/robot/ur5e-1"],
    "features": ["MHS.SAFETY.NOT_CERTIFIED", "batch", "sse"], "conformance": []}
   ```

2. **Explicit configuration** — hosts read `MHS_ENDPOINTS` (comma-separated
   endpoint URLs, `stdio:<command>` entries included) and `~/.mhs/endpoints.json`
   (`mhs discover` probes them; [core.md](core.md) §9).
3. **Local registry** — a host may keep a local registry index.
4. **Registry federation** — a registry may return endpoints; hosts treat
   registry-provided endpoints as untrusted until authenticated. Discovered does not
   mean trusted.
5. mDNS/DNS-SD (`_mhs._tcp`) is optional.

### 8.2 Registry

A registry is a static, searchable index; it is **not** a control plane. Records:

- **Package**: a repo/package that provides MHS adapters (`package_id`, repo
  URL, license, family, tier, adapters, capabilities, conformance, evidence).
- **Device**: a declared device type/model (`vendor`, `model`, `capabilities`,
  manifests, known limits, firmware constraints).
- **Adapter**: adapter manifest metadata + where to get it.
- **Conformance claim**: endpoint/package, profile, level, suite version,
  report digest, issuer (`self` or `verified`), timestamp.
- **Registry document** is JSON Lines shardable by first letter of key; the
  website explorer is a static projection of the same records.

### 8.3 Trust

Records carry `trust: unsigned | self_signed | registry_verified |
manufacturer_signed` and optional `signatures[]` (JWS detached, key in
`keys[]`). Hosts do not elevate privileges based on an unsigned claim, and
show the trust level next to any capability description.

---

## 9. Adapter and bridge model

### 9.1 The per-repository deliverable

The default deliverable for an upstream repository is a **driver package**
([driver-profile.md](driver-profile.md)): one `Driver` class (or a config-only subclass
of a family driver) that declares what the device reads, writes and does, with
sourced limits and facts, plus a fake backend; the SDK runtime enforces everything
else and a gate (`python3 -m mhs.driver check <dir> --backend fake`) says when the
package is finished. The earlier design, a declarative `mhs-adapter.json` with a
`bindings.json` read by a bridge, remains valid and optional ([06](06-adapters.md)).
Either way a **bridge family** runs the mapping: a generic runtime per kind of native
interface.

An adapter may declare several devices (e.g., a workcell simulator exposing
robot + plate reader + liquid handler).

### 9.2 Adapter manifest (example)

The manifest below is the shipped example `MHS/schema/examples/adapter.gymnasium-cartpole.json`. It is valid against
[`adapter.schema.json`](../schema/adapter.schema.json), whose objects are closed: bindings live in a separate
`mhs/bindings.json` ([06](06-adapters.md) §4), not inside the device capabilities.

```json
{
  "$schema": "https://mhs.openai4s.org/schema/0.9/adapter.schema.json",
  "mhs_adapter": "1.0",
  "adapter_id": "com.example.gymnasium-cartpole",
  "title": "Gymnasium CartPole as an MHS simulated device",
  "family": "gymnasium",
  "source": {
    "repo": "https://github.com/Farama-Foundation/Gymnasium",
    "commit": "5f2f9d3",
    "license": "MIT",
    "redistributable": true,
    "path": "mhs/"
  },
  "runtime": {
    "kind": "python",
    "python": ">=3.10",
    "install": ["pip install gymnasium==1.0.0"],
    "entry": "mhs.bridge.gym:main",
    "requirements": ["gymnasium"],
    "gpu": false
  },
  "lifecycle": {
    "start": {"kind": "process", "command": ["python", "-m", "mhs.bridge.gym", "--adapter", "mhs/mhs-adapter.json"]},
    "ready": {"method": "mhs.hello", "deadline_ms": 30000},
    "stop": {"kind": "terminate", "grace_s": 5}
  },
  "devices": [
    {
      "$schema": "https://mhs.openai4s.org/schema/0.9/device.schema.json",
      "mhs_version": "1.0",
      "device_id": "mhs://localhost:7401/gym/CartPole-v1",
      "instance_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4X",
      "display_name": "CartPole-v1 (Gymnasium simulator)",
      "mode": "simulated",
      "profile": {
        "title": "Cart-pole balancing",
        "summary": "Classic control benchmark: push a cart left or right to keep a pole upright. Demonstrates the MHS world.* capability family and seeded determinism.",
        "tags": ["classic control", "cartpole", "reinforcement learning", "benchmark", "seeded simulation"]
      },
      "resources": [
        {
          "resource_id": "world",
          "kind": "world.sim",
          "title": "CartPole world",
          "revision": 0,
          "hash_exclusions": ["/mono_ms"],
          "state_schema": {
            "type": "object",
            "required": ["cart_position", "pole_angle", "terminated", "truncated"],
            "properties": {
              "cart_position": {"type": "number", "x-mhs-unit": "m"},
              "cart_velocity": {"type": "number", "x-mhs-unit": "m/s"},
              "pole_angle": {"type": "number", "x-mhs-unit": "rad"},
              "pole_angular_velocity": {"type": "number", "x-mhs-unit": "rad/s"},
              "terminated": {"type": "boolean"},
              "truncated": {"type": "boolean"}
            }
          },
          "state": {
            "cart_position": 0,
            "cart_velocity": 0,
            "pole_angle": 0,
            "pole_angular_velocity": 0,
            "terminated": false,
            "truncated": false
          }
        }
      ],
      "capabilities": [
        {
          "capability_id": "cap.world.step.v1",
          "resource": "world",
          "native": "gym.make('CartPole-v1').step(action)",
          "input_schema": {
            "type": "object",
            "required": ["action"],
            "properties": {"action": {"type": "integer", "enum": [0, 1]}}
          },
          "output_schema": {"type": "object", "required": ["observation", "reward", "terminated", "truncated"]},
          "constraints": {"concurrency": "exclusive", "max_duration_ms": 1000},
          "determinism": "seeded",
          "exclusive": true
        },
        {
          "capability_id": "cap.world.reset.v1",
          "resource": "world",
          "native": "gym.make('CartPole-v1').reset(seed=seed)",
          "input_schema": {"type": "object", "properties": {"seed": {"type": "integer", "minimum": 0}}},
          "output_schema": {"type": "object", "required": ["observation"]},
          "determinism": "seeded"
        },
        {
          "capability_id": "cap.world.state.v1",
          "resource": "world",
          "native": "env.unwrapped.state",
          "input_schema": {"type": "object", "properties": {}},
          "output_schema": {"type": "object"},
          "determinism": "seeded"
        }
      ],
      "safety": {
        "risk_class": "R0",
        "envelope": {},
        "interlocks": [],
        "estop": {"kind": "software", "latching": false, "latency_ms": 10, "reset": "mhs.safety.reset"},
        "safe_state": {"description": "Simulation paused; no physical effect", "achieved_by": []}
      },
      "fidelity": {
        "engine": "gymnasium-classic-control",
        "fidelity_level": "F0",
        "determinism": {
          "kind": "seeded",
          "seed_control": "reset_required",
          "notes": "Seed must be supplied on reset; no internal RNG isolation."
        },
        "timestep_ms": 20,
        "realtime_factor": 0,
        "reset": "full",
        "snapshot_restore": false,
        "gaps": ["Rigid-body approximation only", "No actuator saturation model", "Observation noise not modeled"]
      }
    }
  ],
  "conformance_target": {"profile": "MHS-Sim", "level": "CL2"},
  "evidence": {
    "state": "declared",
    "read_by": "static_analysis",
    "entry_points": [
      "gymnasium/envs/classic_control/cartpole.py:CartPoleEnv.step",
      "gymnasium/envs/classic_control/cartpole.py:CartPoleEnv.reset"
    ]
  },
  "stability": "stable",
  "tier": "A",
  "redaction": [],
  "registry": {
    "package_id": "gh.farama-foundation/gymnasium",
    "homepage": "https://gymnasium.farama.org",
    "maintainers": ["Farama Foundation"]
  }
}
```

### 9.3 Bridge families

The 0.9 SDK implements these bridge families as runtimes with a Driver class
(`PythonObjectDriver`, `SerialDriver`, `ScpiDriver`, `GymnasiumDriver`,
`MujocoDriver`) and a read-only `replay` bridge: `python-object` (import a
class/function), `serial`, `scpi` (stdlib socket, optional `pyvisa`), `gymnasium`,
`mujoco` and `replay`. The adapter schema also names families that are planned
after the pilot: `ros2` (rclpy / rosbridge), `http-api`, `sila2`, `opentrons`,
`micromanager`, `flowchem`, `madsci`, `bluesky-ophyd`, `qcodes`, `pylabrobot`,
`lerobot`, `mavlink`, the tag bridges (Modbus, OPC UA, EPICS, Tango, Alpaca) and
`mcp-proxy`. A bridge is generic per family; the driver or adapter supplies the
mapping.

### 9.4 Mapping rules

Declarative transforms are limited to: field path mapping, unit conversion,
enumeration mapping, constant injection, clamps (which reject and never
truncate), and error-code mapping. Anything else becomes a **shim** (Python/JS),
recorded as `binding.kind: "shim"` with a file reference. Adapters declare
`native` symbols precisely (module/class/function) and do not rely on
undocumented internals; when they do, `stability: fragile` is declared.

### 9.5 Integration tiers and effort

| Tier | Definition | Typical effort |
|---|---|---|
| **A** | Runnable backend with a clear entry point; adapter manifest + bridge flags get you to CL2. | 0.5–2 dev-days |
| **B** | Wrap-able library/SDK; needs a thin shim or bridge family support. | 2–5 dev-days |
| **C** | Engine or asset only; needs a scenario/model to become a device. | 5–15 dev-days |
| **D** | Peripheral/tooling; not a device (visualizer, docs, dataset, CI helper). Not targeted. | — |
| **X** | Not integrable (empty upstream or inaccessible). | — |

Adapters move through states: `declared → packaged → runnable → conformant →
certified`, each backed by evidence.

---

## 10. Conformance

### 10.1 Levels

| Level | Name | Requires |
|---|---|---|
| **CL0** | Declared | Valid `mhs-adapter.json`/device manifest against the OpenMHS 0.9 schemas; no runtime required. |
| **CL1** | Observable | T1/T2 transport; `hello`, `devices.list/get`, `schema.get`, `resource.read`, `subscribe`/`unsubscribe`; stable revisions. |
| **CL2** | Actuating | `session.open/close`, `command` with idempotency, receipts, `operations.get/cancel`, revision conflicts, deadlines. |
| **CL3** | Governed | `safety.status/estop/reset`, envelope enforcement, risk classes, permits for gated capabilities, session TTL/heartbeat, safe-state on cancel, `MHS.SAFETY.NOT_CERTIFIED` disclosure. |
| **CL4** | Reproducible | Evidence export/verify (hash chain), and for simulated/replay devices a deterministic replay test (same seed ⇒ identical state_hash sequence). |
| **CL5** | Orchestrated | Composition execution with child receipts (reserved in 0.9), multi-device sessions, backpressure/gap semantics, registry publication, and a published conformance report. CL5 is assessed for the MHS-Bridge, MHS-Host and MHS-Registry profiles; MHS-Device and MHS-Sim top out at CL4 (see MHS-001). |

### 10.2 Profiles

- **MHS-Device** (hardware): CL0–CL4 as applicable (no replay requirement).
- **MHS-Sim**: CL0–CL4; the fidelity contract and the CL4 replay test are mandatory.
- **MHS-Bridge**: adapter manifest + at least one device at CL2.
- **MHS-Host**: consumes MHS; the behaviours are in [09](09-host-profile.md)
  (discovery, least privilege, approvals, evidence ledger, mode disclosure).
- **MHS-Registry**: record schema validity, signing, search latency bounds.

### 10.3 Executable conformance

- The suite (`python3 -m mhs.conformance`, versioned with the spec) runs test cases against
  an endpoint and emits a `conformance-report.json`, here a minimal report that is valid against
  [`conformance-report.schema.json`](../schema/conformance-report.schema.json)
  ([01](01-conformance.md) §7.1 shows a fuller one):

```json
{"report_version": "1.0.0", "suite_version": "1.0.0", "profile": "MHS-Sim",
 "subject": {"kind": "endpoint", "id": "mhs://localhost:7400", "mhs_version": "1.0"},
 "level_claimed": "CL3", "level_achieved": "CL3",
 "tests": [{"id": "SAFE-014", "status": "pass", "level": "CL3",
            "mhs_code": "MHS.SAFETY.ENVELOPE_VIOLATION"}],
 "environment": {"os": "macOS 15.6 arm64", "date": "2026-10-20T07:40:00Z", "suite": "openmhs 0.9.0.dev0"},
 "report_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
 "issuer": {"kind": "self"},
 "disclaimers": [{"id": "not_certified",
                  "text": "MHS conformance is a behavioural test result, not a safety certification."}]}
```

- A registry claim is `{package_or_endpoint, profile, level, suite_version,
  report_digest, issued_at, issuer_kind}`. `issuer_kind: self|verified`.
- Test IDs are stable and requirements-traced; the suite includes negative
  tests (interlock open, revision conflict, duplicate command id, deadline
  exceeded, cancellation, mode mismatch).

---

## 11. Host profile

### 11.1 MHS-Host behaviours

A host (agent harness) claiming MHS-Host conformance ([09](09-host-profile.md)):

1. discovers endpoints from all configured sources and authenticates;
2. opens least-privilege sessions and refreshes/closes them correctly;
3. obtains approvals before calling `requires_permit` capabilities;
4. presents `mode`, `fidelity.gaps`, `risk_class` and trust level to the model;
5. enforces deadlines and cancellation, and never retries an `unknown` outcome blindly;
6. records all receipts into an append-only evidence ledger and exports/verifies it;
7. never claims or implies that MHS replaces hardware safety;
8. exposes capabilities to the model through at least one of MCP tools, native
   tools, or a code API, and keeps tool descriptions in sync with schemas.

### 11.2 The OpenAI4S reference host

OpenAI4S (`PKU-YuanGroup/OpenAI4S`) is the reference host. The integration is
MCP-first: one `mhs.mcp` projection per endpoint, registered as an ordinary connector
that is disabled until an operator enables it, with permits and resets on a separate
operator route. How its components map to the host behaviours is described in
[09](09-host-profile.md) annex A (informative).

### 11.3 The "one call" property

For any MHS endpoint — a Rust conveyor workcell, a Python liquid-handler
simulator, a MuJoCo arm, a driver package on its fake backend — the same host code
path runs. This example drives two different endpoints through one helper; it runs
against the SDK:

```python
# runnable
from mhs.adapter import load
from mhs.reference import build_endpoint, build_server
from mhs.run import lab

thermostat = load("MHS/sdk/examples/thermostat", backend="fake")
conveyor = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=False),
                        log_ready=False)

with lab(thermostat, conveyor, ledger=False) as bench:            # one transport API
    for name, capability, payload in (("tutorial-thermostat", "cap.thermal.setpoint.v1", {"target_temperature": 30}),
                                      ("conveyor-workcell", "cap.world.step.v1", {"ticks": 3})):
        receipt = bench[name].invoke(capability, payload)         # one command call for every device
        assert receipt["status"] == "completed"
        state = bench[name].read(bench[name].manifest()["resources"][0]["resource_id"])   # one read
        assert state["revision"] == 1
thermostat.close()
conveyor.close()
```

No per-repo branches in the host. The differences live in the adapter plane.

---

## 12. Document map

| Doc | Subject |
|---|---|
| `README.md` | Precedence, reading order, requirement identifiers |
| `core.md` | The normative core: object model, primitives, reference file, limits, evaluation order, safety duties, receipts, modes, discovery, surfaces, principals, strict mode, persistence |
| `driver-profile.md` | The per-repository driver package, the Driver API, the gate, review, fakes, the sandbox |
| `profiles.md` | Index of the optional profiles |
| `00-architecture.md` | This file: the informative overview |
| `01-conformance.md` | Levels, profiles, test suite, report format |
| `02-wire-protocol.md` | Full method-by-method reference, errors, examples |
| `03-capability-registry.md` | Capability class definitions, versioning, extension rules |
| `04-safety.md` | Envelopes, interlocks, permits, e-stop, audit, threat model |
| `05-fidelity.md` | Mode and fidelity contract, validation protocol, replay |
| `06-adapters.md` | Adapter manifest, bridge families, mapping rules, recipes |
| `07-registry.md` | Package/device/claim records, federation, trust, search |
| `08-transports.md` | T1–T6 bindings, MCP projection details, auth |
| `09-host-profile.md` | Host requirements; annex A describes the OpenAI4S reference host |
| `10-governance.md` | RFC process, versioning, deprecation, licensing |
| `appendix-a-capabilities.md` | Core capability catalogue (generated) |
| `appendix-b-errors.md` | Error code registry (generated) |
| `appendix-c-examples.md` | Runnable end-to-end examples (conveyor, lab, arm, hybrid, MCP) |
| `appendix-d-anthropic-mhs.md` | Relationship to the Anthropic research preview |

---

## 13. Adoption path for the corpus

The workspace catalogues 2,975 repos (1,045 lab, 1,922 robotics, 8 unlisted) and
clones 2,967. They are not adopted by hand: each becomes, at most, one driver package,
produced from a generated task card by a model and checked by a gate, one repository
at a time ([driver-profile.md](driver-profile.md), `MHS/handoff/`). The order of work:

1. **Wave 0 — reference endpoints and four exemplar drivers.** The reference
   conveyor, lab, arm and replay endpoints prove the protocol end to end and produce
   CL2–CL4 conformance reports; four exemplar driver packages (an async bath, a SCPI
   lock-in amplifier, a robot arm SDK, a Gymnasium environment) show the pattern.
2. **Wave 1 — a pilot of 20 repositories** (direct Python instruments, serial/SCPI
   devices, Gymnasium/MuJoCo environments, robot SDK drivers on fakes). The exit
   criterion is that at least 15 pass the gate without any change to the SDK; after it
   the Driver API is frozen.
3. **Waves 2 and 3 — the dispatchable cards**, strict-ready ones first.
4. **Wave 4 — reconnaissance only** for the untriaged cards: a model proposes a
   decision and entry symbols, a maintainer decides.
5. **Waves 5 and 6 — after the post-pilot bridges** (ROS, HTTP, PyLabRobot, SiLA2,
   QCoDeS, ophyd, Micro-Manager, LeRobot, MAVLink, tag bridges, MCP client) and an
   artifact store exist, and for repositories that need a GPU or a proprietary engine.

Every repo record in the registry states its tier, ring, evidence and next action
([07](07-registry.md)); a passing package is `contract_checked`, a statement about a
fake and never about hardware. No repo is silently marked "supported".

---

## 14. Decision log (alternatives considered)

| # | Decision | Alternative rejected | Why |
|---|---|---|---|
| D1 | JSON-RPC 2.0 core | REST resources; gRPC-only; MCP-only | JSON-RPC is trivially embeddable in stdio/HTTP/WS, batch and notification semantics are already specified, and it has a native mapping to MCP. REST forces verb soup; gRPC blocks stdlib hosts; MCP-only excludes direct code APIs and is tool-shaped, not device-shaped. |
| D2 | Sessions as leases | Stateless per-call | Simulators are stateful, hardware needs attribution and exclusive leases, and cancellation needs a scope to act on. |
| D3 | Receipts + revisions + state hash | Simple `{"ok": true}` responses | Without receipts, an agent cannot distinguish "not done" from "unknown", and evidence is impossible. This is the single largest gap in the preview. |
| D4 | Endpoint-enforced safety | Host-enforced policy | Any model can be prompt-injected or buggy; a host is the wrong trust boundary for limits. |
| D5 | Sim and hardware in one model with explicit mode | Separate sim standard | Thousands of adopters only have simulators; two standards double the work. But conflating them silently is unsafe — hence mode + fidelity contract and no runtime switching. |
| D6 | A Driver class per repository on generic bridge families, with a mechanical gate (reversed in 0.9; the declarative adapter stays optional) | A declarative adapter + bindings as the only deliverable | The original decision wrote a manifest and a bindings file per repository. Review of the first design found that too hard for a model to produce and check mechanically; a short decorated Driver class with a fake backend, sourced limits and one gate command is. The runtime, not the driver, enforces safety, so the driver stays a translation. |
| D7 | Capability classes versioned separately | Monolithic protocol version | Hardware vocabulary evolves faster than the wire format; separate versioning avoids breaking the wire to add a pipetting nuance. |
| D8 | Executable conformance levels | Certification body | Adoption requires self-service; a registry claim plus reproducible suite is enough to start, with room for third-party verification. |
| D9 | Natural-language tags attached to typed capabilities | Docs/wiki only | The preview's tags idea is right, but unstructured prose cannot be validated or searched; attaching tags to schemas keeps both. |
| D10 | Registry as static index | Central live broker | Lab networks are air-gapped; static JSON that can be signed and mirrored is deployable; a broker is a single point of failure and a privacy hazard. |

---

## 15. Security and privacy (summary)

The rules are in [core.md](core.md), [04](04-safety.md) and [08](08-transports.md). In brief:

- Transport authentication is required outside loopback; tokens are opaque and
  never logged; stdio endpoints inherit the process identity; HTTP checks `Host` and
  `Origin` and the content type.
- Capability grants are least-privilege and per binding; a session does not gain
  capabilities after open without re-opening.
- `input_digest` binds permits to exact arguments; the approval UI shows the
  human-readable rendering of the same input.
- Evidence contains no secrets; adapters declare `redaction` rules for
  credentials and PII fields.
- Endpoints rate-limit and size-limit requests (`MHS.LIMIT.*`).
- Registry records are public by design; device *state* and telemetry are never
  published to the registry.
- Supply chain: adapter manifests and driver locks pin source commits and
  licences. Upstream code runs locally whatever its licence and is never vendored or
  redistributed; a licence class gates publication of a package, not its execution
  ([driver-profile.md](driver-profile.md) DRV-042).

---

## 16. What MHS deliberately leaves to others

- Model training, prompting, planning and skill learning.
- Real-time control loops (MHS is a supervisory contract; bridges may use EtherCAT,
  CAN, ROS control or vendor RT APIs underneath).
- Physical safety certification, risk assessment and regulatory compliance.
- Device discovery on the factory floor (mDNS/DNS-SD/OPC UA GDS may be used).
- Data storage and analysis of scientific results.

These are integration points, and the MHS documents state them explicitly so
that no one mistakes MHS conformance for a safety or quality certificate.
