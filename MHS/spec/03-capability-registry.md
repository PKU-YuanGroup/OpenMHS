# MHS-003 — Capability Registry and Core Capability Classes

| Field | Value |
|---|---|
| Document | MHS-003 (normative, except where marked informative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | core ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §2 and §4; [`capability.schema.json`](../schema/capability.schema.json); overview in [00-architecture.md](00-architecture.md) §4 (informative) |
| Machine-readable companion | [`capabilities.json`](capabilities.json) (all core classes, normative data) |
| Generated appendix | [MHS-A](appendix-a-capabilities.md) (catalogue table, generated from `capabilities.json`) |

This document defines the MHS capability class format, the five verbs, the
versioning and lifecycle rules for classes, the unit and numeric rules, the
extension namespace rules, and the OpenMHS 0.9 core class catalogue. The catalogue
in §7 and the machine-readable file [`capabilities.json`](capabilities.json) are
generated from one source and MUST agree; where they disagree, the JSON file
wins and the Markdown is in error.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Why capabilities, not device types

An MHS device is a bag of typed capabilities bound to resources
([00-architecture.md](00-architecture.md) A2, informative). The unit of interoperability is therefore a
**capability class** — a versioned, schema-bearing description of one class of
action — plus a **binding** of that class to a concrete resource in a concrete
device manifest.

This split exists because device categories do not survive contact with reality.
A microscope and a robot arm both expose `observe` and `actuate`; what differs is
the capability class, its units and its safety envelope. Conversely, one product
category (say "liquid handler") spans devices whose pipetting semantics differ
in precision, tip coupling, volume range and error behaviour. Classes are shared;
bindings carry the vendor truth.

A capability class is **not** a driver method and **not** an MCP tool. It is the
contract that both must project faithfully. MCP tools, CLI subcommands and code
API methods are generated from the class plus binding; they do not add semantics.

---

## 2. Class identity and versioning

### 2.1 Identity

A capability class is identified by `capability_id`, which MUST match the
`capabilityId` pattern in [`defs.schema.json`](../schema/defs.schema.json)
(`^(cap|x-cap)\.[a-z0-9_.-]+\.v[0-9]+$`). The identifier has three parts:

```text
cap . fluid.aspirate . v1
 │      │                └─ class MAJOR version (integer, no MINOR)
 │      └─ class path: domain[.subdomain].name, lowercase, dot-separated
 └─ core namespace (cap) or extension namespace (cap.x / x-cap)
```

The class path is *not* a hierarchy that implies inheritance. `cap.fluid.transfer.v1`
does not "extend" `cap.fluid.dispense.v1`; any semantic relation is declared
explicitly through `supersedes` or `notes`.

**CAP-001.** A capability class identifier MUST contain exactly one `.v<major>`
suffix and that suffix MUST be the last dot-separated element.

**CAP-002.** A capability class identifier, once published in the MHS Capability
Registry, MUST NOT be reassigned to a different contract. Deleting and later
reusing a class id is prohibited.

### 2.2 MAJOR versioning of classes

Capability classes version independently of the wire protocol
([00-architecture.md](00-architecture.md) D7, informative). The class id carries the MAJOR version. A new
MAJOR is required when any of the following changes in a way that can break a
correct client:

1. an input property is removed, renamed, or made REQUIRED;
2. a property's type, unit, or meaning changes;
3. an output property that clients rely on is removed or retyped;
4. the verb changes;
5. the safety envelope semantics are tightened in a way that can reject inputs
   that were previously accepted *and* the class is advertised as stable;
6. the set of resource kinds the class binds to shrinks incompatibly.

A new MAJOR is *not* required for: adding an OPTIONAL input property, adding an
output property, adding tags, hazards, notes, an extra effect, or a relaxed
limit. These are MINOR changes recorded in the registry metadata (`since`,
`supersedes`, changelog); the class id does not change.

**CAP-003.** Every core class in this document is at MAJOR `v1`. The registry entry
for a class MUST list `since` as a semantic version: the OpenMHS specification release
(`MAJOR.MINOR.PATCH` of the catalogue's `spec_version`, `0.9.0` for every class of the
0.9 catalogue) that introduced the class in its current form. `since` is independent of
the class MAJOR (`v<major>` in the id) and of the wire revision (`mhs_version`), and is
never later than `spec_version`.

**CAP-004.** A class document MUST NOT declare `additionalProperties: true` at
the top level of `input_schema` or `output_schema` unless it also sets
`x-mhs-open: true`, and core classes MUST NOT do so.

### 2.3 Lifecycle and status

The same `status` vocabulary (`stable`, `experimental`, `deprecated`) is used by the
error registry ([MHS-B](appendix-b-errors.md)).

| `status` | Meaning | Client rule |
|---|---|---|
| `stable` | Current, supported. (`active` is the pre-0.9 spelling and is still accepted when a class document is read.) | Use freely. |
| `deprecated` | Superseded or scheduled for removal. | MAY use for at least the deprecation window in [MHS-010](10-governance.md) §5; SHOULD migrate to `supersedes`. |
| `experimental` | Draft class, schema may change without a MAJOR bump. | MUST NOT appear in a conformance claim as a REQUIRED class; clients MUST be able to tolerate change. |

**CAP-005.** An endpoint MUST NOT bind an `experimental` class to a resource
unless the device manifest also carries `"x-mhs-experimental": true` at device
level and `hello.features` contains `MHS.CAPABILITY.EXPERIMENTAL_PRESENT`.
Hosts MUST surface experimental status to the model.

**CAP-006.** A `deprecated` class MUST remain callable on endpoints that already
bind it for the duration of its deprecation window, and MUST continue to validate
against the same schema. Removal of a deprecated class is a MAJOR event handled by
[MHS-010](10-governance.md) §5, not by silently dropping the class from a
manifest.

### 2.4 Relation records

- `supersedes` names the previous class id that this class replaces. New
  bindings SHOULD use the superseding class.
- `notes` carries migration notes.
- A class MUST NOT supersede itself, and cycles are invalid.

**CAP-007.** If a device manifest binds both a class and its `supersedes`
predecessor, the endpoint MUST expose both and MUST map calls to the same physical
operation; it MUST NOT implement divergent behaviour under the two identifiers.

---

## 3. Class document format

The normative JSON Schema for a class document is
[`capability.schema.json`](../schema/capability.schema.json). A class document has
five parts:

| Field | Required | Content |
|---|---|---|
| `capability_id` | yes | Identity (§2). |
| `title` | yes | Short human title, ≤120 chars. |
| `verb` | yes | One of `read`, `write`, `invoke`, `subscribe`, `compose` (§4). |
| `resource_kinds` | yes | The resource `kind` values the class may bind to; a binding to a kind not listed is an `MHS.CAPABILITY.KIND_MISMATCH`. |
| `input_schema`, `output_schema` | yes | JSON Schema 2020-12 documents, closed by default (§2.2, CAP-004); `output_schema` may be an empty object for a class with no return value. |
| `summary` | yes | Model-readable description of what the action does in the physical or simulated world (10–800 chars). |
| `tags` | yes | At least three lowercase natural-language phrases describing the action; no vendor marketing claims. |
| `units` | no | Map of field name to UCUM unit for fields whose unit is not already carried by `x-mhs-unit`. |
| `effects`, `hazards` | no | Effect tokens from §6.4, and hazards a competent operator would consider. |
| `preconditions`, `postconditions` | no | Named preconditions and checkable postconditions. |
| `determinism`, `concurrency`, `risk_class` | no | Declared determinism kind, concurrency model and maximum risk class. |
| `typical_duration_ms`, `notes` | no | Typical duration and free-form migration/action-space notes. |
| `constraints` | no | `rate_limit`, `concurrency`, `max_duration_ms`, `cancellable`, `requires_session_mode`. |
| `safety` | no | `risk_class`, `limits`, `requires_permit`, `interlocks`. |
| `status`, `since`, `supersedes`, `conformance_tests` | no | Lifecycle and traceability. |

**CAP-008.** A class document MUST validate against
[`capability.schema.json`](../schema/capability.schema.json). Registry ingestion
MUST reject an invalid class document with `MHS.REGISTRY.RECORD_INVALID`.

The canonical shape is flat: semantic fields live on the class document, not in a
nested `semantics` object.

```json
{
  "capability_id": "cap.fluid.aspirate.v1",
  "title": "Aspirate liquid",
  "verb": "invoke",
  "resource_kinds": ["lab.liquid_handler", "lab.pipette"],
  "input_schema": {
    "type": "object",
    "properties": {
      "volume": {"type": "number", "minimum": 0, "maximum": 1000, "x-mhs-unit": "uL"}
    },
    "required": ["volume"],
    "additionalProperties": false
  },
  "output_schema": {
    "type": "object",
    "properties": {
      "volume_in_tip": {"type": "number", "x-mhs-unit": "uL"}
    },
    "required": ["volume_in_tip"],
    "additionalProperties": false
  },
  "summary": "Draw a specified volume of liquid from a labware well into a pipette tip.",
  "tags": ["liquid handling", "pipetting", "aspirate", "volume", "labware"],
  "units": {"volume": "uL", "volume_in_tip": "uL"},
  "effects": ["material.transfer", "consumable.use"],
  "hazards": ["cross_contamination", "spill", "bubble_formation", "volume_error"],
  "preconditions": ["tip_attached", "liquid_present", "labware_loaded"],
  "postconditions": ["volume_in_tip >= requested_volume * (1 - tolerance)"],
  "determinism": "exact",
  "typical_duration_ms": 2000,
  "notes": "Binding notes carry action-space or vendor details; migration notes live here too.",
  "constraints": {
    "rate_limit": {"max_per_minute": 60},
    "concurrency": "exclusive",
    "max_duration_ms": 30000,
    "cancellable": true
  },
  "safety": {
    "risk_class": "R1",
    "limits": {"volume": {"min": 0, "max": 1000, "unit": "uL"}}
  },
  "conformance_tests": ["CAP-FLUID-001", "SAFE-R1-002"]
}
```

**CAP-009.** `summary` MUST describe what the action does **in the physical
world**, not what the native API call is. It MUST be usable as model context
without the schema. `tags` MUST contain at least three lowercase phrases and MUST
NOT contain vendor marketing claims.

**CAP-010.** `effects` MUST be drawn from the effect vocabulary in §6.4
(extension tokens allowed only in an extension namespace) and MUST list every
kind of physical change the capability can cause, including consumption of a
consumable and emission of energy.

**CAP-011.** `hazards` MUST list hazards a competent operator would consider,
even when the safety envelope prevents them. An empty `hazards` array is
permitted only for classes whose maximum risk class is R0.

---

## 4. Verbs

| Verb | Meaning | Core method | Revision side effect | Receipt | Replay mode |
|---|---|---|---|---|---|
| `read` | Observe state or a computed quantity. | `mhs.resource.read` (resource state) or `mhs.command` (class read) | none | optional | allowed |
| `write` | Set a persisted operating parameter or safe setpoint. | `mhs.resource.write` (the class `cap.device.configure.v1`) | advances revision when the state changed | receipt REQUIRED | forbidden (`MHS.MODE.READ_ONLY`) |
| `invoke` | Execute a discrete operation with a physical effect. | `mhs.command` | advances revision when the state changed, whatever the outcome; a rejection never advances it | receipt REQUIRED | forbidden except `world.state`-family reads |
| `subscribe` | Deliver a stream whose rate is higher than request/response. | `mhs.subscribe` | none | none | allowed for recorded streams |
| `compose` | Run a named deterministic composition of other capabilities. | `mhs.composition.run` (reserved, not implemented in 0.9) | advances revision | receipt with child receipts | forbidden |

**CAP-012.** A class with verb `read` MUST NOT change device state, revision, or
any physical output as a side effect of a successful call; a catalogued read class
never advances the revision ([core.md](core.md) CORE-021, CORE-095). If observing requires
moving the device (for example an autofocus or a scan), the class MUST be `invoke`.

**CAP-013.** A class with verb `write` MUST declare the affected resource and MUST
have every accepted value inside its `safety.limits`; writes are mutations and obey
the same revision, receipt, idempotency and envelope rules as `invoke`.

**CAP-014.** Read classes SHOULD carry `constraints.concurrency: "shared"` so that
observation does not contend with actuation unless the device declares that
observation requires exclusive access.

**CAP-015.** A `subscribe` class MUST declare the stream name, its ordering
guarantee and its sampling model in `notes`; subscriptions are described
in [MHS-002](02-wire-protocol.md) §12.

---

## 5. Binding a class to a device

A device manifest lists **bindings**, not class documents
([`device.schema.json`](../schema/device.schema.json) `capabilities[]`). A binding
carries `capability_id`, `resource`, and optionally `input_schema`,
`output_schema`, `semantics`, `constraints`, `limits`, `determinism`, `exclusive`,
`requires_permit`, `native` ([MHS-006](06-adapters.md) §4).

**CAP-016.** A binding MUST NOT widen the class contract: a binding input schema
MUST be an equal or stricter schema than the class input schema, and a binding MUST
NOT accept values the class forbids. Endpoints MUST validate against the binding
schema, then against the class schema; a value valid for the binding but invalid
for the class is a server error (`MHS.INTERNAL.SCHEMA_DRIFT`).

**CAP-017.** A binding MUST NOT lower the class `safety.risk_class`. It MAY raise
it (for example a class-2 laser capability bound to a class-3B laser). The device's
declared risk class is the maximum over its bindings ([00-architecture.md](00-architecture.md) §6.1, informative).

**CAP-018.** A binding's numeric limits MUST be within the class limits; when the
class declares a limit and the binding declares none, the class limit applies. A
binding that cannot enforce a class limit MUST NOT be published; it is an adapter
defect, not a client responsibility.

**CAP-019.** A binding MAY weaken the class `determinism` (for example a seeded
simulator class bound to hardware is `statistical` in practice) and MUST declare
the weaker value. It MUST NOT strengthen determinism above the class value without
a validation record referenced by the class `notes` or the device profile.

**CAP-020.** `native` MUST be a human-readable reference to the exact native
symbol (module/class/function or register/command), not a code snippet. It is
documentation for reviewers and is not executed.

**CAP-045.** Motion and manipulation bindings SHOULD declare the *action-space
semantics* of their native interface in the binding's `semantics` annotation object or in the
device profile: mode (position/velocity/torque/cartesian), joint order and names,
scale and offset, controller gains, clipping, and whether cartesian targets are
delta or absolute. Different simulators expose identical array shapes with different
meaning; the MHS schema carries the shape, and the notes MUST carry the meaning. This
is a SHOULD, not a new REQUIRED manifest field, because the fidelity object and
capability schemas are closed in OpenMHS 0.9.


---

## 6. Units, numerics, time

### 6.1 Unit rules

**CAP-021.** Every numeric field that represents a physical quantity MUST carry
`"x-mhs-unit"` with a UCUM code string, at every nesting level, including array
items. A physical numeric without a unit is a schema error; ingestion MUST reject
it.

**CAP-022.** Units are UCUM codes as published by the Unified Code for Units of
Measure. The OpenMHS 0.9 core catalogue uses only the codes in Table 1. A bridge MUST
convert native units to the declared UCUM code at the boundary and MUST NOT expose
a unit it has not converted.

**CAP-023.** A capability MUST NOT declare an implicit conversion. If the native
API takes `mm` and the class takes `m`, the adapter converts; the schema field is
`m` and the bridge MUST NOT accept a bare number interpreted as `mm`.

**CAP-024.** Dimensionless quantities use UCUM `1`; percentages use `%`. Angles
use `rad` or `deg` as declared — an angle field MUST NOT be ambiguous between them.
Absolute temperature uses `K` or `Cel` as declared; temperature *differences* use
`K` and MUST NOT be declared `Cel`. Time durations use `s`, `ms` or `min` as
declared; timestamps use RFC 3339 strings in UTC, never a unit-bearing number.

**CAP-025.** Numeric ranges (`minimum`, `maximum`, `exclusiveMinimum`,
`exclusiveMaximum`) MUST be expressed in the field's declared unit. A class that
declares `x-mhs-unit: "uL"` and `maximum: 1000` means 1000 µL.

**CAP-026.** Floating-point equality MUST NOT be used as a physical success
criterion. Classes that need a tolerance MUST declare it as a property or in
`postconditions` (for example `volume_in_tip >= requested_volume * (1 - tolerance)`).

Table 1 — UCUM codes used by the OpenMHS 0.9 core catalogue.

| Quantity | Codes used | Notes |
|---|---|---|
| Length | `m`, `mm`, `um`, `nm` | Position, offset, range. |
| Angle | `rad`, `deg` | `deg` accepted at boundary; core classes prefer `rad`. |
| Time | `s`, `ms`, `min` | Durations only; wall clock is RFC 3339. |
| Rate per minute | `/min` | Revolutions or cycles per minute (centrifuge `rpm`, mixing `speed`). |
| Velocity | `m/s`, `rad/s` | Linear and angular. |
| Acceleration | `m/s2` | Deceleration profiles, IMU. |
| Temperature | `K`, `Cel`, `K/min` | `Cel` not for differences; `K/min` is a ramp rate. |
| Volume | `L`, `mL`, `uL` | Lab classes prefer `uL`. |
| Mass | `kg`, `g`, `mg` | |
| Force | `N` | |
| Torque | `N.m` | |
| Pressure | `Pa`, `kPa` | |
| Flow (volume) | `uL/s`, `mL/min` | Class declares one; bridge converts. |
| Voltage / current / resistance | `V`, `A`, `Ohm` | |
| Frequency / angular velocity | `Hz`, `rad/s` | |
| Illumination / intensity | `lx`, `cd`, `1`, `%` | |
| Power (optical) | `mW`, `W` | |
| Dimensionless | `1`, `%` | Counts and ratios. |

### 6.2 Numbers, identifiers, digests

**CAP-027.** Counts and indices use JSON integers. Revisions follow the
`revision` definition in [`defs.schema.json`](../schema/defs.schema.json):
monotone integers; endpoints above 2^53 emit decimal strings and clients MUST
accept both.

**CAP-028.** Identifiers in inputs use the forms defined by the class: a
`resource_id` ([`defs.schema.json`](../schema/defs.schema.json) `resourceId`), a
ULID, or an opaque handle declared with `x-mhs-handle: true`. A capability MUST
NOT require a caller to construct a vendor-specific identifier that the endpoint
could resolve itself.

**CAP-029.** Artifacts larger than 1 MiB (images, point clouds, spectra, logs)
MUST be returned as artifact references (`mhs+artifact://<endpoint>/<artifact_id>`)
or base64 with `"x-mhs-encoding": "base64"`, never as unbounded inline arrays.

### 6.3 Time and deadlines

**CAP-030.** `deadline_ms` is a duration from request receipt, not a wall-clock
instant ([00-architecture.md](00-architecture.md) §4.6, informative). Classes with
`constraints.max_duration_ms` MUST complete or return `accepted`+`operation_id`
within that budget when invoked without cancellation; the endpoint MUST enforce
`min(deadline_ms, max_duration_ms)`.

**CAP-031.** Classes whose real-world duration cannot be bounded (`invoke` with
`typical_duration_ms > constraints.max_duration_ms`) MUST be advertised as
operations: the endpoint MUST return a receipt with `status: "accepted"` and an
`operation_id` and MUST deliver progress notifications ([MHS-002](02-wire-protocol.md) §11).

### 6.4 Effect vocabulary

Effects are tokens in `effects`. The core vocabulary is:

| Token | Meaning |
|---|---|
| `motion.joint` | Joint-space motion. |
| `motion.cartesian` | Cartesian or task-space motion. |
| `motion.mobile` | Base translation/rotation. |
| `manipulation.grasp` | Grasp/contact with an object. |
| `manipulation.release` | Release of a grasped object. |
| `material.transfer` | Movement of material between containers. |
| `material.move` | Movement of a sample/labware object. |
| `consumable.use` | Consumable consumed (tip, seal, reagent). |
| `energy.emission` | Optical or other emitted energy. |
| `energy.heating` | Thermal energy added. |
| `energy.cooling` | Thermal energy removed. |
| `sample.state_change` | Sample state changed (temperature, lysis, incubation). |
| `measurement.capture` | A measurement or image acquired. |
| `simulation.advance` | Simulated time advanced or world state mutated. |
| `configuration.write` | A persisted operating parameter changed. |
| `computation.execute` | External compute or bounded process executed. |
| `safety.estop` | Emergency stop engaged; motion/outputs inhibited. |
| `safety.reset` | Interlock/e-stop latched state cleared. |

**CAP-032.** Extension effect tokens MUST be namespaced `x-<vendor>.<token>` and
MUST be documented in the class `notes`. Core tokens MUST NOT be
redefined.

---

## 7. OpenMHS 0.9 core capability catalogue

This section is **generated** from [`capabilities.json`](capabilities.json) by
`python3 MHS/sdk/tools/spec_doctest.py --write-catalogue` and checked by
`--check-catalogue` (never edit it by hand). Each entry gives the class identifier,
verb, risk class, resource kinds, session modes, `since` (the OpenMHS specification
release that introduced the class), the lifecycle status when it is not `stable`,
`requires permit` when the class is gated, summary, tags, constraints and the normative
input and output JSON Schema. `cap.device.configure.v1` is the class behind
`mhs.resource.write` ([core.md](core.md) CORE-022); `x-mhs-replaced-by` names the
protocol method that replaces a deprecated class. The catalogue is the
source for [MHS-A](appendix-a-capabilities.md), for the registry ingestion, for
the SDK's generated tool descriptions and for the website capability browser.

Domain codes used below: `world` (simulation), `motion`, `manipulation`,
`sensing`, `fluid`, `sample`, `imaging`, `optics`, `measure`, `thermal`,
`actuation`, `compute`, `process`, `device`.

<!-- BEGIN GENERATED: catalogue (python3 MHS/sdk/tools/spec_doctest.py --write-catalogue) -->

### 7.1 World (7 classes)

#### `cap.world.reset.v1` — Reset a simulated world
`invoke` · **R0** · determinism `seeded` · `exclusive` · modes `simulated`, `hybrid` · since 0.9.0 — Reset the simulated world to a scenario start state and return the initial observation. When a seed is supplied the endpoint records it in the receipt; otherwise the endpoint's declared default seed applies.
Kinds `world.sim`. Effects `simulation.advance`. Hazards none. Tags `world reset`, `simulation start`, `scenario initialisation`, `seeded reset`, `episode start`. Constraints `cancellable` `false`, `max_duration_ms` `30000`. Notes: A reset advances the device revision. For determinism kind 'seeded', seed_control='reset_required' means the seed MUST be supplied here.
Input `{"additionalProperties":false,"properties":{"options":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"scenario":{"maxLength":120,"type":"string"},"seed":{"minimum":0,"type":"integer"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"observation":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"revision":{"minimum":0,"type":"integer"},"seed":{"minimum":0,"type":"integer"}},"required":["observation","seed"],"type":"object"}`
#### `cap.world.step.v1` — Advance a simulated world
`invoke` · **R0** · determinism `exact` · `exclusive` · modes `simulated`, `hybrid` · since 0.9.0 — Advance the simulated world by a bounded number of fixed timesteps, optionally applying an action for each step, and return the resulting observation and terminal flags.
Kinds `world.sim`. Effects `simulation.advance`. Hazards none. Tags `simulation step`, `advance time`, `apply action`, `physics tick`, `reinforcement learning step`. Units `reward`: `1`. Constraints `cancellable` `false`, `max_duration_ms` `5000`, `rate_limit` `{"max_per_second": 100, "burst": 10}`. Notes: ticks counts fixed simulated timesteps (fidelity.timestep_ms). The receipt's state_hash_after is the state hash after the last tick.
Input `{"additionalProperties":false,"properties":{"action":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"ticks":{"maximum":10000,"minimum":1,"type":"integer"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"observation":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"reward":{"type":"number","x-mhs-unit":"1"},"state_hash":{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"},"terminated":{"type":"boolean"},"tick":{"minimum":0,"type":"integer"},"truncated":{"type":"boolean"}},"required":["observation","tick","state_hash"],"type":"object"}`
#### `cap.world.state.v1` — Read a simulated world state
`read` · **R0** · determinism `exact` · `shared` · modes `simulated`, `hybrid`, `replay` · since 0.9.0 · status `deprecated` — Return the complete normative state of a simulated world together with its revision and canonical state hash.
Kinds `world.sim`. Effects `measurement.capture`. Hazards `none`. Tags `world state`, `simulation observation`, `state snapshot`, `read world`, `deterministic state`. Constraints `cancellable` `false`, `max_duration_ms` `2000`. Replaced by `mhs.resource.read`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.resource.read. The class stays valid and callable for its deprecation window; new drivers use the protocol method.
Input `{"additionalProperties":false,"properties":{"fields":{"items":{"maxLength":64,"type":"string"},"maxItems":64,"type":"array"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"revision":{"minimum":0,"type":"integer"},"sampled_at":{"type":"string"},"state":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"state_hash":{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"}},"required":["state","state_hash","revision"],"type":"object"}`
#### `cap.world.snapshot.v1` — Take a world snapshot
`invoke` · **R0** · determinism `exact` · `shared` · modes `simulated`, `hybrid` · since 0.9.0 · status `deprecated` — Capture a restorable snapshot of the complete world state, including the revision and state hash, for deterministic restore later.
Kinds `world.sim`. Effects `simulation.advance`. Hazards none. Tags `snapshot`, `save state`, `checkpoint`, `restore point`, `deterministic capture`. Constraints `cancellable` `false`, `max_duration_ms` `10000`. Replaced by `mhs.snapshot`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.snapshot (Sim profile). The class stays valid and callable for its deprecation window; new drivers use the protocol method. Requires fidelity.snapshot_restore = true; otherwise MHS.MODE.SNAPSHOT_UNSUPPORTED.
Input `{"additionalProperties":false,"properties":{},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"revision":{"minimum":0,"type":"integer"},"snapshot":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"snapshot_digest":{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"}},"required":["snapshot","snapshot_digest","revision"],"type":"object"}`
#### `cap.world.restore.v1` — Restore a world snapshot
`invoke` · **R0** · determinism `exact` · `exclusive` · modes `simulated`, `hybrid` · since 0.9.0 · status `deprecated` — Restore the world to a previously captured snapshot, replacing the current state; the device revision advances and the state hash MUST equal the snapshot's.
Kinds `world.sim`. Effects `simulation.advance`. Hazards none. Tags `restore`, `load state`, `rollback`, `checkpoint restore`, `deterministic rewind`. Constraints `cancellable` `false`, `max_duration_ms` `30000`. Replaced by `mhs.restore`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.restore (Sim profile). The class stays valid and callable for its deprecation window; new drivers use the protocol method. Only valid in simulated or replay mode and only when fidelity.snapshot_restore is true.
Input `{"additionalProperties":false,"properties":{"snapshot":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["snapshot"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"revision":{"minimum":0,"type":"integer"},"state_hash":{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"}},"required":["revision","state_hash"],"type":"object"}`
#### `cap.world.render.v1` — Render a simulation frame
`invoke` · **R0** · determinism `exact` · `shared` · modes `simulated`, `hybrid` · since 0.9.0 — Render the current simulated world through a named camera and return an image artifact reference. Rendering does not advance simulated time.
Kinds `world.sim`. Effects `measurement.capture`. Hazards none. Tags `render`, `camera`, `visualisation`, `image capture`, `headless rendering`. Constraints `cancellable` `false`, `max_duration_ms` `30000`.
Input `{"additionalProperties":false,"properties":{"camera":{"maxLength":64,"type":"string"},"format":{"enum":["png","jpeg","rgb_array"],"type":"string"},"height":{"maximum":8192,"minimum":1,"type":"integer"},"width":{"maximum":8192,"minimum":1,"type":"integer"}},"required":["width","height"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"height":{"minimum":1,"type":"integer"},"image_ref":{"type":"string"},"media_type":{"type":"string"},"width":{"minimum":1,"type":"integer"}},"required":["image_ref","width","height"],"type":"object"}`
#### `cap.world.seed.v1` — Set the world RNG seed
`write` · **R0** · determinism `exact` · `exclusive` · modes `simulated`, `hybrid` · since 0.9.0 — Set the seed used by the simulated world's random number generators for subsequent steps, without resetting the world. The accepted seed is echoed in the receipt.
Kinds `world.sim`. Effects `simulation.advance`. Hazards none. Tags `seed`, `random seed`, `reproducibility`, `determinism control`, `rng`. Constraints `cancellable` `false`, `max_duration_ms` `2000`. Notes: Only meaningful when fidelity.determinism.seed_control is parameter or reset_required.
Input `{"additionalProperties":false,"properties":{"seed":{"minimum":0,"type":"integer"}},"required":["seed"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"accepted":{"type":"boolean"},"seed":{"minimum":0,"type":"integer"}},"required":["seed","accepted"],"type":"object"}`

### 7.2 Motion (9 classes)

#### `cap.motion.joint_position.v1` — Move joints to positions
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Command one or more actuated joints to target positions in joint space, optionally over a declared duration, and report whether the target was reached within tolerance.
Kinds `robot.arm`, `motion.axis`. Effects `motion.joint`. Hazards `pinch`, `collision`, `unexpected_contact`. Tags `joint motion`, `move arm`, `joint position`, `trajectory`, `position control`. Units `duration_s`: `s`, `joint_positions`: `rad`, `tolerance_rad`: `rad`. Class limits `{"joint_positions":{"reason":"joint travel limits are declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `120000`. Notes: Position limits, velocity limits and joint-order conventions MUST be declared per binding in safety.envelope.
Input `{"additionalProperties":false,"properties":{"block":{"type":"boolean"},"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"joint_positions":{"items":{"type":"number","x-mhs-unit":"rad"},"maxItems":64,"minItems":1,"type":"array"}},"required":["joint_positions"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"duration_ms":{"minimum":0,"type":"integer"},"joint_positions":{"items":{"type":"number","x-mhs-unit":"rad"},"type":"array"},"reached":{"type":"boolean"},"tolerance_rad":{"minimum":0,"type":"number","x-mhs-unit":"rad"}},"required":["reached","joint_positions"],"type":"object"}`
#### `cap.motion.joint_velocity.v1` — Command joint velocities
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Command continuous joint velocities for a bounded duration. The operation stops at the end of the duration or when cancelled.
Kinds `robot.arm`, `motion.axis`. Effects `motion.joint`. Hazards `pinch`, `collision`. Tags `joint velocity`, `velocity control`, `continuous motion`, `jog`, `bounded motion`. Units `duration_s`: `s`, `joint_velocities`: `rad/s`. Class limits `{"joint_velocities":{"reason":"velocity limits are declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `60000`.
Input `{"additionalProperties":false,"properties":{"duration_s":{"maximum":60,"minimum":0,"type":"number","x-mhs-unit":"s"},"joint_velocities":{"items":{"type":"number","x-mhs-unit":"rad/s"},"maxItems":64,"minItems":1,"type":"array"}},"required":["joint_velocities","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"applied":{"type":"boolean"},"joint_velocities":{"items":{"type":"number","x-mhs-unit":"rad/s"},"type":"array"}},"required":["applied"],"type":"object"}`
#### `cap.motion.joint_torque.v1` — Command joint torques
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` · **requires permit** — Apply commanded joint torques for a bounded duration for compliant or force-controlled motion. Torque magnitude is bounded by the binding safety envelope.
Kinds `robot.arm`. Effects `motion.joint`. Hazards `pinch`, `high_force`, `collision`. Tags `torque control`, `compliance`, `force control`, `joint torque`, `impedance`. Units `duration_s`: `s`, `joint_torques`: `N.m`. Class limits `{"joint_torques":{"reason":"torque limits are declared per binding; exceeding them is MHS.SAFETY.ENVELOPE_VIOLATION"}}`. Constraints `cancellable` `true`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"duration_s":{"maximum":10,"minimum":0,"type":"number","x-mhs-unit":"s"},"joint_torques":{"items":{"type":"number","x-mhs-unit":"N.m"},"maxItems":64,"minItems":1,"type":"array"}},"required":["joint_torques","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"applied":{"type":"boolean"},"joint_torques":{"items":{"type":"number","x-mhs-unit":"N.m"},"type":"array"}},"required":["applied"],"type":"object"}`
#### `cap.motion.cartesian_pose.v1` — Move to a Cartesian pose
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Move the tool centre point to a Cartesian position and orientation in a named frame. The endpoint solves inverse kinematics; an unreachable target is rejected before motion.
Kinds `robot.arm`. Effects `motion.cartesian`. Hazards `pinch`, `collision`, `unreachable_target`. Tags `cartesian motion`, `move to pose`, `inverse kinematics`, `tool centre point`, `waypoint`. Units `duration_s`: `s`, `orientation.pitch`: `rad`, `orientation.roll`: `rad`, `orientation.yaw`: `rad`, `position.x`: `mm`, `position.y`: `mm`, `position.z`: `mm`, `tolerance_mm`: `mm`. Class limits `{"position":{"reason":"workspace bounds are declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"frame":{"enum":["base","tool"],"type":"string"},"orientation":{"additionalProperties":false,"properties":{"pitch":{"type":"number","x-mhs-unit":"rad"},"roll":{"type":"number","x-mhs-unit":"rad"},"yaw":{"type":"number","x-mhs-unit":"rad"}},"required":["roll","pitch","yaw"],"type":"object"},"position":{"additionalProperties":false,"properties":{"x":{"type":"number","x-mhs-unit":"mm"},"y":{"type":"number","x-mhs-unit":"mm"},"z":{"type":"number","x-mhs-unit":"mm"}},"required":["x","y","z"],"type":"object"}},"required":["position"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"position":{"additionalProperties":false,"properties":{"x":{"type":"number","x-mhs-unit":"mm"},"y":{"type":"number","x-mhs-unit":"mm"},"z":{"type":"number","x-mhs-unit":"mm"}},"type":"object"},"reached":{"type":"boolean"},"tolerance_mm":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"required":["reached"],"type":"object"}`
#### `cap.motion.cartesian_twist.v1` — Command a Cartesian twist
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Move with a commanded linear and angular velocity for a bounded duration, in a named frame.
Kinds `robot.arm`. Effects `motion.cartesian`. Hazards `pinch`, `collision`. Tags `velocity motion`, `twist`, `cartesian velocity`, `teleoperation`, `servo`. Units `angular.x`: `rad/s`, `angular.y`: `rad/s`, `angular.z`: `rad/s`, `duration_s`: `s`, `linear.x`: `m/s`, `linear.y`: `m/s`, `linear.z`: `m/s`, `stopped_position.x`: `mm`, `stopped_position.y`: `mm`, `stopped_position.z`: `mm`. Class limits `{"linear":{"reason":"speed limits are declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `60000`.
Input `{"additionalProperties":false,"properties":{"angular":{"additionalProperties":false,"properties":{"x":{"type":"number","x-mhs-unit":"rad/s"},"y":{"type":"number","x-mhs-unit":"rad/s"},"z":{"type":"number","x-mhs-unit":"rad/s"}},"required":["x","y","z"],"type":"object"},"duration_s":{"maximum":60,"minimum":0.01,"type":"number","x-mhs-unit":"s"},"frame":{"enum":["base","tool"],"type":"string"},"linear":{"additionalProperties":false,"properties":{"x":{"type":"number","x-mhs-unit":"m/s"},"y":{"type":"number","x-mhs-unit":"m/s"},"z":{"type":"number","x-mhs-unit":"m/s"}},"required":["x","y","z"],"type":"object"}},"required":["linear","angular","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"applied":{"type":"boolean"},"stopped_position":{"additionalProperties":false,"properties":{"x":{"type":"number","x-mhs-unit":"mm"},"y":{"type":"number","x-mhs-unit":"mm"},"z":{"type":"number","x-mhs-unit":"mm"}},"type":"object"}},"required":["applied"],"type":"object"}`
#### `cap.motion.mobile_base.v1` — Drive a mobile base
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Drive a mobile base with a commanded linear and angular velocity for a bounded duration, or to a target pose. Obstacle and zone limits are enforced by the binding safety envelope.
Kinds `robot.mobile_base`. Effects `motion.mobile`. Hazards `collision`, `person_in_workspace`, `tip_over`. Tags `mobile robot`, `base motion`, `drive`, `navigation`, `differential drive`. Units `angular_velocity`: `rad/s`, `distance_m`: `m`, `duration_s`: `s`, `heading_rad`: `rad`, `linear_velocity`: `m/s`. Class limits `{"angular_velocity":{"reason":"maximum turn rate is declared per binding"},"linear_velocity":{"reason":"maximum transit speed is declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `300000`.
Input `{"additionalProperties":false,"properties":{"angular_velocity":{"type":"number","x-mhs-unit":"rad/s"},"duration_s":{"maximum":300,"minimum":0,"type":"number","x-mhs-unit":"s"},"linear_velocity":{"type":"number","x-mhs-unit":"m/s"}},"required":["linear_velocity","angular_velocity","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"distance_m":{"minimum":0,"type":"number","x-mhs-unit":"m"},"heading_rad":{"type":"number","x-mhs-unit":"rad"},"stopped":{"type":"boolean"}},"required":["distance_m","heading_rad"],"type":"object"}`
#### `cap.motion.stop.v1` — Stop motion safely
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Stop all motion on the resource with a declared deceleration profile and report the stopping position. This capability is always cancellable=false and is exempt from rate limiting.
Kinds `robot.arm`, `robot.mobile_base`, `motion.axis`. Effects `motion.joint`. Hazards `collision`. Tags `stop`, `halt`, `decelerate`, `safe stop`, `emergency deceleration`. Units `deceleration`: `m/s2`. Constraints `cancellable` `false`, `max_duration_ms` `5000`. Notes: motion.stop is the declared safe-state achievement for many devices; endpoints MUST NOT rate-limit or permit-gate it.
Input `{"additionalProperties":false,"properties":{"deceleration":{"minimum":0,"type":"number","x-mhs-unit":"m/s2"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"stopped":{"type":"boolean"},"stopped_at":{"type":"string"},"stopped_position":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["stopped"],"type":"object"}`
#### `cap.motion.home.v1` — Home the axes
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Drive axes to their declared home position or reference switch, establishing the coordinate reference needed by other motion capabilities.
Kinds `robot.arm`, `motion.axis`. Effects `motion.joint`. Hazards `pinch`, `collision`. Tags `homing`, `reference`, `calibration motion`, `home position`, `axis setup`. Units `joint_positions`: `rad`, `speed_scale`: `1`. Constraints `cancellable` `true`, `max_duration_ms` `300000`. Notes: Homing moves are motion; they are NOT a substitute for mhs.safety.reset and MUST be rejected while the device is latched.
Input `{"additionalProperties":false,"properties":{"axes":{"items":{"maxLength":64,"type":"string"},"maxItems":32,"type":"array"},"speed_scale":{"maximum":1,"minimum":0,"type":"number","x-mhs-unit":"1"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"axes":{"items":{"maxLength":64,"type":"string"},"type":"array"},"homed":{"type":"boolean"},"joint_positions":{"items":{"type":"number","x-mhs-unit":"rad"},"type":"array"}},"required":["homed"],"type":"object"}`
#### `cap.motion.estop.v1` — Engage the device emergency stop
`invoke` · **R0** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `deprecated` — Engage the device-level emergency stop: motion stops within the declared latency, outputs transition to the declared safe state, and the device latches until mhs.safety.reset.
Kinds `robot.arm`, `robot.mobile_base`, `motion.axis`, `world.sim`. Effects `safety.estop`. Hazards `collision`, `person_in_workspace`, `unexpected_energy`. Tags `emergency stop`, `e-stop`, `halt device`, `safety stop`, `latch`. Constraints `cancellable` `false`, `max_duration_ms` `2000`. Replaced by `mhs.safety.estop`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.safety.estop; endpoints route it to the same latch. The class stays valid and callable for its deprecation window; new drivers use the protocol method. motion.estop is the capability-level expression of mhs.safety.estop. Both MUST reach the same latch. MHS is never a safety-rated channel (MHS-000 6.3).
Input `{"additionalProperties":false,"properties":{"reason":{"maxLength":500,"minLength":1,"type":"string"}},"required":["reason"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"engaged":{"type":"boolean"},"latched":{"type":"boolean"},"latency_ms":{"minimum":0,"type":"integer"},"safe_state_achieved":{"type":"boolean"}},"required":["engaged","latched"],"type":"object"}`

### 7.3 Manipulation (4 classes)

#### `cap.manipulation.grasp.v1` — Grasp an object
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Close the gripper on a target object with a bounded force and report the achieved grasp width. A failed grasp is a completed operation with grasped=false, not a silent success.
Kinds `robot.gripper`, `robot.arm`. Effects `manipulation.grasp`. Hazards `pinch`, `object_damage`, `collision`. Tags `grasp`, `gripper close`, `pick object`, `force grasp`, `contact`. Units `force`: `N`, `width`: `mm`, `width_mm`: `mm`. Class limits `{"force":{"reason":"grasp force limit is declared per binding"}}`. Constraints `cancellable` `true`, `max_duration_ms` `30000`.
Input `{"additionalProperties":false,"properties":{"approach":{"enum":["top","side","front"],"type":"string"},"force":{"minimum":0,"type":"number","x-mhs-unit":"N"},"width":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"grasped":{"type":"boolean"},"width_mm":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"required":["grasped"],"type":"object"}`
#### `cap.manipulation.release.v1` — Release a grasped object
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Open the gripper to release the held object, optionally to a declared opening width, and report the achieved width.
Kinds `robot.gripper`. Effects `manipulation.release`. Hazards `object_damage`, `drop`. Tags `release`, `gripper open`, `drop object`, `ungrasp`, `place handoff`. Units `open_width`: `mm`, `width_mm`: `mm`. Constraints `cancellable` `true`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"open_width":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"released":{"type":"boolean"},"width_mm":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"required":["released"],"type":"object"}`
#### `cap.manipulation.place.v1` — Place an object at a target
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Place the held object at a declared target location with an approach height, release the gripper and verify the object is no longer held.
Kinds `robot.arm`, `robot.gripper`. Effects `manipulation.grasp`, `material.move`. Hazards `collision`, `object_damage`, `sample_loss`. Tags `place`, `put down`, `deposit`, `assembly`, `position object`. Units `placement_height`: `mm`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"placement_height":{"minimum":0,"type":"number","x-mhs-unit":"mm"},"release_after":{"type":"boolean"},"target":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["target"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"placed":{"type":"boolean"},"target_revision":{"minimum":0,"type":"integer"}},"required":["placed"],"type":"object"}`
#### `cap.manipulation.pick.v1` — Pick an object from a source
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Move to a declared source, grasp the object, lift it by a declared clearance and verify the grasp still holds. Combines cartesian motion and grasp under one receipt.
Kinds `robot.arm`, `robot.gripper`. Effects `manipulation.grasp`, `motion.cartesian`. Hazards `collision`, `object_damage`, `sample_loss`. Tags `pick`, `pick and place`, `retrieve`, `lift object`, `bin picking`. Units `lift_clearance`: `mm`. Constraints `cancellable` `true`, `max_duration_ms` `180000`.
Input `{"additionalProperties":false,"properties":{"approach":{"enum":["top","side","front"],"type":"string"},"lift_clearance":{"minimum":0,"type":"number","x-mhs-unit":"mm"},"source":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["source"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"grasped":{"type":"boolean"},"lifted":{"type":"boolean"},"object_id":{"maxLength":128,"type":"string"}},"required":["grasped"],"type":"object"}`

### 7.4 Sensing (5 classes)

#### `cap.sensing.read.v1` — Read a sensor
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Read the current value of one or more sensor channels and return the values with a sampling timestamp and a monotone sequence number. Volatile channels are also available by subscription.
Kinds `sensor`, `sensor.imu`, `sensor.force_torque`. Effects `measurement.capture`. Hazards none. Tags `sensor read`, `telemetry`, `measurement`, `observation`, `channel value`. Constraints `cancellable` `false`, `max_duration_ms` `2000`.
Input `{"additionalProperties":false,"properties":{"fields":{"items":{"maxLength":64,"type":"string"},"maxItems":64,"type":"array"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"sampled_at":{"type":"string"},"sequence":{"minimum":0,"type":"integer"},"values":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["values","sampled_at"],"type":"object"}`
#### `cap.sensing.image.v1` — Capture an image
`invoke` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Capture a single image from a named camera with a declared resolution and exposure and return an image artifact reference.
Kinds `sensor.camera`. Effects `measurement.capture`. Hazards `privacy`. Tags `camera`, `image capture`, `snapshot`, `vision`, `photograph`. Units `exposure_ms`: `ms`. Constraints `cancellable` `false`, `max_duration_ms` `30000`.
Input `{"additionalProperties":false,"properties":{"camera":{"maxLength":64,"type":"string"},"exposure_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"format":{"enum":["png","jpeg","raw"],"type":"string"},"height":{"maximum":8192,"minimum":1,"type":"integer"},"width":{"maximum":8192,"minimum":1,"type":"integer"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"exposure_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"height":{"minimum":1,"type":"integer"},"image_ref":{"type":"string"},"media_type":{"type":"string"},"width":{"minimum":1,"type":"integer"}},"required":["image_ref","width","height"],"type":"object"}`
#### `cap.sensing.point_cloud.v1` — Capture a point cloud
`invoke` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Capture a depth point cloud over a declared range and return a point-cloud artifact reference with the point count and coordinate frame.
Kinds `sensor.depth`. Effects `measurement.capture`. Hazards `privacy`. Tags `point cloud`, `depth`, `lidar`, `3d scan`, `range image`. Units `max_range`: `mm`, `min_range`: `mm`. Constraints `cancellable` `false`, `max_duration_ms` `60000`.
Input `{"additionalProperties":false,"properties":{"frame":{"maxLength":64,"type":"string"},"max_points":{"maximum":10000000,"minimum":1,"type":"integer"},"max_range":{"minimum":0,"type":"number","x-mhs-unit":"mm"},"min_range":{"minimum":0,"type":"number","x-mhs-unit":"mm"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"artifact_ref":{"type":"string"},"frame":{"maxLength":64,"type":"string"},"point_count":{"minimum":0,"type":"integer"}},"required":["artifact_ref","point_count"],"type":"object"}`
#### `cap.sensing.force_torque.v1` — Read a force/torque sensor
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Read the current force and torque vector in a declared frame and return the wrench with its sampling timestamp.
Kinds `sensor.force_torque`. Effects `measurement.capture`. Hazards `high_force`. Tags `force torque`, `wrench`, `contact force`, `load cell`, `six axis`. Units `force`: `N`, `torque`: `N.m`. Constraints `cancellable` `false`, `max_duration_ms` `2000`.
Input `{"additionalProperties":false,"properties":{"axes":{"items":{"enum":["x","y","z","rx","ry","rz"],"type":"string"},"maxItems":6,"type":"array"},"frame":{"enum":["tool","base"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"force":{"items":{"type":"number","x-mhs-unit":"N"},"maxItems":3,"minItems":3,"type":"array"},"sampled_at":{"type":"string"},"saturated":{"type":"boolean"},"torque":{"items":{"type":"number","x-mhs-unit":"N.m"},"maxItems":3,"minItems":3,"type":"array"}},"required":["force","torque","sampled_at"],"type":"object"}`
#### `cap.sensing.imu.v1` — Read an IMU
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Read linear acceleration, angular velocity and orientation from an inertial measurement unit, with the declared reference frame and timestamp.
Kinds `sensor.imu`. Effects `measurement.capture`. Hazards none. Tags `imu`, `accelerometer`, `gyroscope`, `orientation`, `inertial`. Units `angular_velocity`: `rad/s`, `linear_acceleration`: `m/s2`, `orientation.w`: `1`, `orientation.x`: `1`, `orientation.y`: `1`, `orientation.z`: `1`. Constraints `cancellable` `false`, `max_duration_ms` `2000`. Notes: Quaternion components are dimensionless (UCUM 1); the unit is carried here, not implied by convention.
Input `{"additionalProperties":false,"properties":{"frame":{"enum":["body","world"],"type":"string"}},"required":["frame"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"angular_velocity":{"items":{"type":"number","x-mhs-unit":"rad/s"},"maxItems":3,"minItems":3,"type":"array"},"linear_acceleration":{"items":{"type":"number","x-mhs-unit":"m/s2"},"maxItems":3,"minItems":3,"type":"array"},"orientation":{"additionalProperties":false,"properties":{"w":{"type":"number","x-mhs-unit":"1"},"x":{"type":"number","x-mhs-unit":"1"},"y":{"type":"number","x-mhs-unit":"1"},"z":{"type":"number","x-mhs-unit":"1"}},"required":["x","y","z","w"],"type":"object"},"sampled_at":{"type":"string"}},"required":["linear_acceleration","angular_velocity","sampled_at"],"type":"object"}`

### 7.5 Fluid (6 classes)

#### `cap.fluid.aspirate.v1` — Aspirate liquid
`invoke` · **R1** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Draw a specified volume of liquid from a declared labware well into a pipette tip, with a bounded flow rate and an optional liquid-level offset.
Kinds `lab.liquid_handler`, `lab.pipette`. Effects `material.transfer`, `consumable.use`. Hazards `cross_contamination`, `spill`, `bubble_formation`, `volume_error`. Tags `liquid handling`, `pipetting`, `aspirate`, `volume`, `labware`. Units `aspirated_volume`: `uL`, `flow_rate`: `uL/s`, `liquid_level_mm`: `mm`, `liquid_level_offset`: `mm`, `volume`: `uL`. Class limits `{"volume":{"max":1000,"min":0,"reason":"pipette tip capacity; bindings declare their actual range","unit":"uL"}}`. Constraints `cancellable` `true`, `max_duration_ms` `60000`. Notes: Preconditions: tip attached, liquid present, labware loaded. Errors: MHS.DEVICE.PRECONDITION_UNMET with details.precondition.
Input `{"additionalProperties":false,"properties":{"flow_rate":{"minimum":0,"type":"number","x-mhs-unit":"uL/s"},"liquid_level_offset":{"type":"number","x-mhs-unit":"mm"},"source":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"tip":{"maxLength":64,"type":"string"},"volume":{"maximum":1000,"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["volume","source"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"aspirated_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"liquid_level_mm":{"type":"number","x-mhs-unit":"mm"},"tip":{"maxLength":64,"type":"string"}},"required":["aspirated_volume"],"type":"object"}`
#### `cap.fluid.dispense.v1` — Dispense liquid
`invoke` · **R2** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Dispense a specified volume from the pipette into a declared labware well, with optional blowout and mixing after dispense.
Kinds `lab.liquid_handler`, `lab.pipette`. Effects `material.transfer`. Hazards `cross_contamination`, `spill`, `volume_error`. Tags `liquid handling`, `dispense`, `pipette`, `well`, `reagent addition`. Units `dispensed_volume`: `uL`, `flow_rate`: `uL/s`, `target_volume_after`: `uL`, `volume`: `uL`. Class limits `{"volume":{"max":1000,"min":0,"reason":"pipette tip capacity","unit":"uL"}}`. Constraints `cancellable` `true`, `max_duration_ms` `60000`.
Input `{"additionalProperties":false,"properties":{"blowout":{"type":"boolean"},"flow_rate":{"minimum":0,"type":"number","x-mhs-unit":"uL/s"},"mix_cycles":{"maximum":100,"minimum":0,"type":"integer"},"target":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"volume":{"maximum":1000,"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["volume","target"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"dispensed_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"target_volume_after":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["dispensed_volume"],"type":"object"}`
#### `cap.fluid.transfer.v1` — Transfer liquid between wells
`invoke` · **R2** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Aspirate a volume from a source well and dispense it into a target well as one receipted operation, so a failed transfer cannot leave an untracked half-state.
Kinds `lab.liquid_handler`, `lab.pipette`. Effects `material.transfer`, `consumable.use`. Hazards `cross_contamination`, `spill`, `sample_loss`. Tags `transfer`, `pipetting`, `liquid movement`, `plate to plate`, `reagent transfer`. Units `flow_rate`: `uL/s`, `source_volume_after`: `uL`, `target_volume_after`: `uL`, `transferred_volume`: `uL`, `volume`: `uL`. Class limits `{"volume":{"max":1000,"min":0,"reason":"pipette tip capacity","unit":"uL"}}`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"flow_rate":{"minimum":0,"type":"number","x-mhs-unit":"uL/s"},"mix_cycles":{"maximum":100,"minimum":0,"type":"integer"},"source":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"target":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"tip":{"maxLength":64,"type":"string"},"volume":{"maximum":1000,"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["volume","source","target"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"source_volume_after":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"target_volume_after":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"transferred_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["transferred_volume"],"type":"object"}`
#### `cap.fluid.mix.v1` — Mix the contents of a well
`invoke` · **R1** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Mix the contents of a declared well by repeated aspiration and dispense cycles at a bounded volume and speed.
Kinds `lab.liquid_handler`, `lab.pipette`. Effects `material.transfer`. Hazards `cross_contamination`, `bubble_formation`, `sample_loss`. Tags `mix`, `homogenise`, `resuspend`, `agitation`, `well mixing`. Units `speed`: `/min`, `volume`: `uL`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"cycles":{"maximum":100,"minimum":1,"type":"integer"},"speed":{"description":"Mixing rate in aspirate/dispense cycles per minute.","minimum":0,"type":"number","x-mhs-unit":"/min"},"target":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["target","cycles"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"cycles":{"minimum":0,"type":"integer"},"mixed":{"type":"boolean"}},"required":["mixed"],"type":"object"}`
#### `cap.fluid.wash.v1` — Wash a well or tip
`invoke` · **R1** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Wash a declared well or the pipette tip with a bounded volume of wash solution, discarding waste to a declared waste container.
Kinds `lab.liquid_handler`. Effects `material.transfer`, `consumable.use`. Hazards `cross_contamination`, `spill`, `chemical_exposure`. Tags `wash`, `rinse`, `tip wash`, `well wash`, `decontamination`. Units `volume`: `uL`, `waste_volume`: `uL`. Constraints `cancellable` `true`, `max_duration_ms` `180000`.
Input `{"additionalProperties":false,"properties":{"cycles":{"maximum":20,"minimum":1,"type":"integer"},"target":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"type":"object"},"volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"waste":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"}},"required":["labware"],"type":"object"}},"required":["cycles","volume","waste"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"washed":{"type":"boolean"},"waste_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["washed"],"type":"object"}`
#### `cap.fluid.level.v1` — Read a liquid level
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Detect and report the liquid level and estimated volume in a declared container using a declared detection method.
Kinds `lab.liquid_handler`, `lab.labware`. Effects `measurement.capture`. Hazards `cross_contamination`. Tags `liquid level`, `volume estimate`, `meniscus`, `capacitance detection`, `pressure detection`. Units `confidence`: `1`, `level_mm`: `mm`, `volume_uL`: `uL`. Constraints `cancellable` `false`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"container":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"},"well":{"maxLength":32,"type":"string"}},"required":["labware","well"],"type":"object"},"method":{"enum":["capacitance","pressure","image"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"confidence":{"maximum":1,"minimum":0,"type":"number","x-mhs-unit":"1"},"detection":{"enum":["capacitance","pressure","image"],"type":"string"},"level_mm":{"minimum":0,"type":"number","x-mhs-unit":"mm"},"volume_uL":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["level_mm","detection"],"type":"object"}`

### 7.6 Sample (6 classes)

#### `cap.sample.move.v1` — Move a sample or labware
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Move a sample, plate or other labware object from one declared location to another using the device's transport mechanism.
Kinds `lab.sample`, `lab.labware`. Effects `material.move`. Hazards `sample_loss`, `drop`, `collision`. Tags `move plate`, `transfer labware`, `sample transport`, `plate mover`, `carrier`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"carrier":{"maxLength":64,"type":"string"},"from":{"additionalProperties":false,"properties":{"location":{"maxLength":128,"type":"string"}},"required":["location"],"type":"object"},"sample_id":{"maxLength":128,"type":"string"},"to":{"additionalProperties":false,"properties":{"location":{"maxLength":128,"type":"string"}},"required":["location"],"type":"object"}},"required":["sample_id","from","to"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"location":{"maxLength":128,"type":"string"},"moved":{"type":"boolean"},"sample_id":{"maxLength":128,"type":"string"}},"required":["moved","location"],"type":"object"}`
#### `cap.sample.incubate.v1` — Incubate samples
`invoke` · **R2** · determinism `none` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Hold samples at a declared temperature, and optionally a declared atmosphere, for a declared duration. The achieved temperature and duration are reported in the output and receipt.
Kinds `lab.incubator`. Effects `energy.heating`, `sample.state_change`. Hazards `thermal_burn`, `sample_loss`, `biohazard`. Tags `incubate`, `temperature hold`, `cell culture`, `thermal protocol`, `environmental control`. Units `actual_duration_s`: `s`, `actual_temperature`: `Cel`, `atmosphere.co2_percent`: `%`, `duration_s`: `s`, `temperature`: `Cel`. Class limits `{"temperature":{"max":80,"min":0,"reason":"incubator safe operating range; bindings narrow it","unit":"Cel"}}`. Constraints `cancellable` `true`, `max_duration_ms` `86400000`.
Input `{"additionalProperties":false,"properties":{"atmosphere":{"additionalProperties":false,"properties":{"co2_percent":{"maximum":100,"minimum":0,"type":"number","x-mhs-unit":"%"}},"type":"object"},"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"sample_ids":{"items":{"maxLength":128,"type":"string"},"maxItems":384,"minItems":1,"type":"array"},"temperature":{"type":"number","x-mhs-unit":"Cel"}},"required":["sample_ids","temperature","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"actual_duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"actual_temperature":{"type":"number","x-mhs-unit":"Cel"},"incubated":{"type":"boolean"}},"required":["incubated","actual_temperature"],"type":"object"}`
#### `cap.sample.centrifuge.v1` — Centrifuge samples
`invoke` · **R2** · determinism `none` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · **requires permit** — Spin declared samples at a target speed for a declared duration, optionally at a controlled temperature, then report the achieved speed and duration.
Kinds `lab.centrifuge`. Effects `sample.state_change`. Hazards `centrifuge_imbalance`, `aerosol`, `sample_loss`, `rotor_failure`. Tags `centrifuge`, `spin`, `pellet`, `phase separation`, `rpm`. Units `duration_s`: `s`, `duration_s_actual`: `s`, `rpm`: `/min`, `rpm_actual`: `/min`, `temperature`: `Cel`. Class limits `{"rpm":{"max":15000,"min":0,"reason":"rotor and sample balance limits are declared per binding","unit":"/min"}}`. Constraints `cancellable` `false`, `max_duration_ms` `7200000`. Notes: Cancellation is not offered while spinning: stopping a centrifuge mid-run is itself a hazard. Use mhs.safety.estop for emergency stops.
Input `{"additionalProperties":false,"properties":{"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"rpm":{"maximum":15000,"minimum":0,"type":"number","x-mhs-unit":"/min"},"sample_ids":{"items":{"maxLength":128,"type":"string"},"maxItems":384,"minItems":1,"type":"array"},"temperature":{"type":"number","x-mhs-unit":"Cel"}},"required":["sample_ids","rpm","duration_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"completed":{"type":"boolean"},"duration_s_actual":{"minimum":0,"type":"number","x-mhs-unit":"s"},"rpm_actual":{"minimum":0,"type":"number","x-mhs-unit":"/min"}},"required":["completed","rpm_actual"],"type":"object"}`
#### `cap.sample.seal.v1` — Seal a plate
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Apply a declared seal type to a microplate and report completion; the seal consumable is recorded as a consumable use.
Kinds `lab.plate_sealer`. Effects `consumable.use`, `material.move`. Hazards `thermal_burn`, `plate_damage`. Tags `seal plate`, `foil seal`, `adhesive seal`, `plate preparation`, `consumable`. Constraints `cancellable` `false`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"plate":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"}},"required":["labware"],"type":"object"},"seal_type":{"enum":["foil","adhesive","heat","cap_mat"],"type":"string"}},"required":["plate","seal_type"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"seal_type":{"enum":["foil","adhesive","heat","cap_mat"],"type":"string"},"sealed":{"type":"boolean"}},"required":["sealed"],"type":"object"}`
#### `cap.sample.unseal.v1` — Unseal a plate
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Remove the seal from a microplate so that the wells are accessible, reporting completion.
Kinds `lab.plate_sealer`. Effects `material.move`. Hazards `plate_damage`, `cross_contamination`, `aerosol`. Tags `unseal`, `remove seal`, `peel`, `plate preparation`, `open plate`. Constraints `cancellable` `false`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"plate":{"additionalProperties":false,"properties":{"labware":{"maxLength":128,"type":"string"}},"required":["labware"],"type":"object"}},"required":["plate"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"unsealed":{"type":"boolean"}},"required":["unsealed"],"type":"object"}`
#### `cap.sample.store.v1` — Store samples
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Place samples into a declared storage location at a declared temperature and record the storage location in the output so later retrieval is unambiguous.
Kinds `lab.storage`, `lab.sample`. Effects `material.move`, `sample.state_change`. Hazards `sample_loss`, `frost_damage`, `biohazard`. Tags `store`, `archive`, `cold storage`, `sample inventory`, `freezer`. Units `temperature`: `Cel`. Constraints `cancellable` `true`, `max_duration_ms` `600000`.
Input `{"additionalProperties":false,"properties":{"location":{"additionalProperties":false,"properties":{"slot":{"maxLength":64,"type":"string"},"system":{"maxLength":64,"type":"string"}},"required":["system","slot"],"type":"object"},"sample_ids":{"items":{"maxLength":128,"type":"string"},"maxItems":384,"minItems":1,"type":"array"},"temperature":{"type":"number","x-mhs-unit":"Cel"}},"required":["sample_ids","location"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"location":{"additionalProperties":false,"properties":{"slot":{"maxLength":64,"type":"string"},"system":{"maxLength":64,"type":"string"}},"type":"object"},"stored":{"type":"boolean"}},"required":["stored","location"],"type":"object"}`

### 7.7 Imaging (3 classes)

#### `cap.imaging.capture.v1` — Capture a microscope image
`invoke` · **R0** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Acquire a microscope image of the current field of view for a declared channel, exposure, binning and region of interest, returning an image artifact.
Kinds `instrument.microscope`. Effects `measurement.capture`. Hazards `photobleaching`, `privacy`. Tags `microscope`, `imaging`, `fluorescence`, `brightfield`, `camera acquisition`. Units `exposure_ms`: `ms`. Constraints `cancellable` `false`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"binning":{"maximum":16,"minimum":1,"type":"integer"},"camera":{"maxLength":64,"type":"string"},"channel":{"maxLength":64,"type":"string"},"exposure_ms":{"maximum":600000,"minimum":0,"type":"number","x-mhs-unit":"ms"},"roi":{"additionalProperties":false,"properties":{"height":{"minimum":1,"type":"integer"},"width":{"minimum":1,"type":"integer"},"x":{"minimum":0,"type":"integer"},"y":{"minimum":0,"type":"integer"}},"required":["x","y","width","height"],"type":"object"},"save_as":{"maxLength":128,"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"exposure_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"height":{"minimum":1,"type":"integer"},"image_ref":{"type":"string"},"width":{"minimum":1,"type":"integer"}},"required":["image_ref","width","height"],"type":"object"}`
#### `cap.imaging.focus.v1` — Focus the microscope
`invoke` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Move the focus axis to a target Z position or run an autofocus search over a declared range, returning the achieved Z position and focus score.
Kinds `instrument.microscope`. Effects `motion.cartesian`. Hazards `collision`, `slide_damage`. Tags `focus`, `autofocus`, `z stage`, `focal plane`, `sharpness`. Units `score`: `1`, `search_range`: `um`, `target_z`: `um`, `z_um`: `um`. Constraints `cancellable` `true`, `max_duration_ms` `120000`.
Input `{"additionalProperties":false,"properties":{"method":{"enum":["autofocus","manual","none"],"type":"string"},"search_range":{"minimum":0,"type":"number","x-mhs-unit":"um"},"target_z":{"maximum":1000000,"minimum":-1000000,"type":"number","x-mhs-unit":"um"}},"required":["method"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"focused":{"type":"boolean"},"score":{"minimum":0,"type":"number","x-mhs-unit":"1"},"z_um":{"type":"number","x-mhs-unit":"um"}},"required":["focused","z_um"],"type":"object"}`
#### `cap.imaging.illumination.v1` — Set illumination
`write` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Set the illumination channel and intensity used for subsequent imaging or observation, with an optional bounded on-duration after which the light is turned off.
Kinds `instrument.microscope`, `light.source`. Effects `energy.emission`, `configuration.write`. Hazards `photobleaching`, `eye_exposure`. Tags `illumination`, `light source`, `led`, `fluorescence excitation`, `brightness`. Units `duration_ms`: `ms`, `intensity`: `%`. Class limits `{"intensity":{"max":100,"min":0,"reason":"emission power limits are declared per binding","unit":"%"}}`. Constraints `cancellable` `false`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"duration_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"intensity":{"maximum":100,"minimum":0,"type":"number","x-mhs-unit":"%"}},"required":["channel","intensity"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"applied":{"type":"boolean"},"channel":{"maxLength":64,"type":"string"},"intensity":{"type":"number","x-mhs-unit":"%"}},"required":["applied"],"type":"object"}`

### 7.8 Optics (3 classes)

#### `cap.optics.set_power.v1` — Set optical output power
`write` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` · **requires permit** — Set the emitted optical power of a laser or light source to a declared setpoint, optionally ramping over a declared duration. Bindings for class 3B+ sources raise the risk class to R3.
Kinds `optics.laser`, `optics.source`. Effects `energy.emission`, `configuration.write`. Hazards `laser_radiation`, `eye_exposure`, `burns`. Tags `laser power`, `optical power`, `excitation`, `setpoint`, `emission control`. Units `power`: `mW`, `ramp_ms`: `ms`, `set_power_mw`: `mW`. Class limits `{"power":{"max":1000,"min":0,"reason":"class-dependent maximum emission; the binding MUST narrow this","unit":"mW"}}`. Constraints `cancellable` `false`, `max_duration_ms` `30000`. Notes: Requires a permit for R2 and above on hardware. The permit is bound to the exact input_digest.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"power":{"minimum":0,"type":"number","x-mhs-unit":"mW"},"ramp_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"}},"required":["power"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"ramped":{"type":"boolean"},"set_power_mw":{"minimum":0,"type":"number","x-mhs-unit":"mW"}},"required":["set_power_mw"],"type":"object"}`
#### `cap.optics.shutter.v1` — Open or close an optical shutter
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` — Open or close a mechanical or electronic shutter in the optical path, reporting the resulting state and, for an open shutter, the open duration.
Kinds `optics.shutter`. Effects `energy.emission`. Hazards `laser_radiation`, `eye_exposure`. Tags `shutter`, `beam block`, `optical path`, `exposure control`, `safety shutter`. Units `open_duration_ms`: `ms`. Constraints `cancellable` `false`, `max_duration_ms` `5000`. Notes: Closing a shutter is the declared safe state for optical sources; it MUST NOT require a permit.
Input `{"additionalProperties":false,"properties":{"state":{"enum":["open","closed"],"type":"string"}},"required":["state"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"open_duration_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"state":{"enum":["open","closed"],"type":"string"}},"required":["state"],"type":"object"}`
#### `cap.optics.align.v1` — Align an optical element
`invoke` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `experimental` · **requires permit** — Adjust an optical element along declared axes until a target coupling or position is reached, reporting the achieved offset and alignment quality.
Kinds `optics.stage`, `optics.mirror`. Effects `motion.cartesian`, `energy.emission`. Hazards `laser_radiation`, `eye_exposure`, `misalignment`. Tags `alignment`, `optical alignment`, `coupling`, `mirror adjustment`, `beam steering`. Units `offset_mm`: `mm`, `quality`: `1`, `target`: `mm`. Constraints `cancellable` `true`, `max_duration_ms` `600000`.
Input `{"additionalProperties":false,"properties":{"axis":{"enum":["x","y","z","theta","phi"],"type":"string"},"method":{"enum":["hill_climb","manual","lookup"],"type":"string"},"target":{"type":"number","x-mhs-unit":"mm"}},"required":["axis","target"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"aligned":{"type":"boolean"},"offset_mm":{"type":"number","x-mhs-unit":"mm"},"quality":{"maximum":1,"minimum":0,"type":"number","x-mhs-unit":"1"}},"required":["aligned","offset_mm"],"type":"object"}`

### 7.9 Measure (9 classes)

#### `cap.measure.voltage.v1` — Measure voltage
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure a DC or RMS voltage on a declared channel or terminal pair and return the value with its sampling timestamp and measurement range.
Kinds `instrument.dmm`, `instrument.smu`, `sensor`. Effects `measurement.capture`. Hazards `high_voltage`. Tags `voltage`, `dmm`, `electrical measurement`, `potential difference`, `read channel`. Units `range_v`: `V`, `voltage`: `V`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"dc":{"type":"boolean"},"range_v":{"minimum":0,"type":"number","x-mhs-unit":"V"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"range_v":{"minimum":0,"type":"number","x-mhs-unit":"V"},"sampled_at":{"type":"string"},"saturated":{"type":"boolean"},"voltage":{"type":"number","x-mhs-unit":"V"}},"required":["voltage","sampled_at"],"type":"object"}`
#### `cap.measure.current.v1` — Measure current
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure current on a declared channel and return the value with its timestamp and range.
Kinds `instrument.dmm`, `instrument.smu`, `sensor`. Effects `measurement.capture`. Hazards `high_voltage`, `overcurrent`. Tags `current`, `amperage`, `dmm`, `electrical measurement`, `read channel`. Units `current`: `A`, `range_a`: `A`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"range_a":{"minimum":0,"type":"number","x-mhs-unit":"A"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"current":{"type":"number","x-mhs-unit":"A"},"range_a":{"minimum":0,"type":"number","x-mhs-unit":"A"},"sampled_at":{"type":"string"},"saturated":{"type":"boolean"}},"required":["current","sampled_at"],"type":"object"}`
#### `cap.measure.resistance.v1` — Measure resistance
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure resistance or impedance on a declared channel and return the value with its timestamp and excitation method.
Kinds `instrument.dmm`, `sensor`. Effects `measurement.capture`. Hazards `high_voltage`. Tags `resistance`, `ohmmeter`, `impedance`, `continuity`, `electrical measurement`. Units `resistance`: `Ohm`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"four_wire":{"type":"boolean"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"four_wire":{"type":"boolean"},"resistance":{"minimum":0,"type":"number","x-mhs-unit":"Ohm"},"sampled_at":{"type":"string"}},"required":["resistance","sampled_at"],"type":"object"}`
#### `cap.measure.spectrum.v1` — Acquire a spectrum
`invoke` · **R0** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Acquire an optical or mass spectrum over a declared wavelength or mass range and return the axis and intensity arrays, or an artifact reference for large spectra.
Kinds `instrument.spectrometer`, `instrument.spectrophotometer`. Effects `measurement.capture`. Hazards `laser_radiation`, `sample_loss`. Tags `spectrum`, `spectroscopy`, `absorbance`, `wavelength scan`, `spectral acquisition`. Units `integration_ms`: `ms`, `intensities`: `1`, `step_nm`: `nm`, `wavelength_max`: `nm`, `wavelength_min`: `nm`, `wavelengths`: `nm`. Class limits `{"wavelength_min":{"max":2500,"min":200,"reason":"detector range is declared per binding","unit":"nm"}}`. Constraints `cancellable` `true`, `max_duration_ms` `300000`.
Input `{"additionalProperties":false,"properties":{"artifact":{"type":"boolean"},"integration_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"step_nm":{"minimum":0.0001,"type":"number","x-mhs-unit":"nm"},"wavelength_max":{"minimum":0,"type":"number","x-mhs-unit":"nm"},"wavelength_min":{"minimum":200,"type":"number","x-mhs-unit":"nm"}},"required":["wavelength_min","wavelength_max"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"artifact_ref":{"type":"string"},"intensities":{"items":{"type":"number","x-mhs-unit":"1"},"type":"array"},"sampled_at":{"type":"string"},"wavelengths":{"items":{"type":"number","x-mhs-unit":"nm"},"type":"array"}},"required":["sampled_at"],"type":"object"}`
#### `cap.measure.intensity.v1` — Measure intensity
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure optical or radiant intensity at a declared wavelength or channel and return the value with its unit and integration time.
Kinds `instrument.spectrometer`, `sensor.optical`. Effects `measurement.capture`. Hazards `laser_radiation`. Tags `intensity`, `photometry`, `optical power`, `fluorescence intensity`, `detector count`. Units `integration_ms`: `ms`, `intensity`: `1`, `wavelength_nm`: `nm`. Constraints `cancellable` `false`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"integration_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"wavelength_nm":{"minimum":0,"type":"number","x-mhs-unit":"nm"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"integration_ms":{"minimum":0,"type":"number","x-mhs-unit":"ms"},"intensity":{"type":"number","x-mhs-unit":"1"},"sampled_at":{"type":"string"},"saturated":{"type":"boolean"}},"required":["intensity","sampled_at"],"type":"object"}`
#### `cap.measure.mass.v1` — Measure mass
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure the mass on a balance or load cell and report the value and stability flag.
Kinds `instrument.balance`, `sensor`. Effects `measurement.capture`. Hazards `sample_loss`. Tags `mass`, `weighing`, `balance`, `gravimetry`, `load cell`. Units `mass`: `mg`. Constraints `cancellable` `false`, `max_duration_ms` `30000`.
Input `{"additionalProperties":false,"properties":{"channel":{"maxLength":64,"type":"string"},"settle":{"type":"boolean"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"mass":{"type":"number","x-mhs-unit":"mg"},"sampled_at":{"type":"string"},"stable":{"type":"boolean"}},"required":["mass","stable","sampled_at"],"type":"object"}`
#### `cap.measure.temperature.v1` — Measure temperature
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure temperature at a declared location and return the value with its timestamp and stability flag.
Kinds `instrument.thermometer`, `sensor.temperature`, `instrument.incubator`. Effects `measurement.capture`. Hazards `thermal_burn`. Tags `temperature`, `thermometer`, `thermal measurement`, `probe`, `sensor`. Units `temperature`: `Cel`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"location":{"maxLength":64,"type":"string"},"probe":{"maxLength":64,"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"sampled_at":{"type":"string"},"stable":{"type":"boolean"},"temperature":{"type":"number","x-mhs-unit":"Cel"}},"required":["temperature","sampled_at"],"type":"object"}`
#### `cap.measure.pressure.v1` — Measure pressure
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure absolute, gauge or differential pressure at a declared port and return the value with its reference and timestamp.
Kinds `sensor.pressure`, `instrument.gauge`. Effects `measurement.capture`. Hazards `pressure_hazard`, `chemical_exposure`. Tags `pressure`, `gauge`, `vacuum`, `baratron`, `process sensor`. Units `pressure`: `Pa`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"port":{"maxLength":64,"type":"string"},"reference":{"enum":["absolute","gauge","differential"],"type":"string"}},"required":["reference"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"pressure":{"type":"number","x-mhs-unit":"Pa"},"reference":{"enum":["absolute","gauge","differential"],"type":"string"},"sampled_at":{"type":"string"}},"required":["pressure","sampled_at"],"type":"object"}`
#### `cap.measure.flow.v1` — Measure flow
`read` · **R0** · determinism `statistical` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Measure volumetric or mass flow at a declared line and optionally the accumulated volume since a declared instant.
Kinds `sensor.flow`, `instrument.flowmeter`. Effects `measurement.capture`. Hazards `pressure_hazard`, `spill`. Tags `flow`, `flow rate`, `flowmeter`, `liquid flow`, `gas flow`. Units `flow_rate`: `uL/s`, `total_volume`: `uL`. Constraints `cancellable` `false`, `max_duration_ms` `5000`.
Input `{"additionalProperties":false,"properties":{"line":{"maxLength":64,"type":"string"},"quantity":{"enum":["volume","mass"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"flow_rate":{"type":"number","x-mhs-unit":"uL/s"},"sampled_at":{"type":"string"},"total_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["flow_rate","sampled_at"],"type":"object"}`

### 7.10 Thermal (1 class)

#### `cap.thermal.setpoint.v1` — Set a thermal setpoint
`write` · **R2** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Set the target temperature of a thermal zone and optionally wait for the zone to reach the setpoint within a declared tolerance.
Kinds `thermal.zone`, `instrument.incubator`, `lab.thermal_block`. Effects `energy.heating`, `energy.cooling`, `configuration.write`. Hazards `thermal_burn`, `sample_loss`, `overheating`. Tags `temperature control`, `setpoint`, `heater`, `thermal zone`, `ramp`. Units `actual_temperature`: `Cel`, `rate`: `K/min`, `setpoint`: `Cel`, `target_temperature`: `Cel`, `tolerance`: `K`. Class limits `{"target_temperature":{"max":300,"min":-50,"reason":"device thermal limits; bindings narrow them","unit":"Cel"}}`. Constraints `cancellable` `true`, `max_duration_ms` `3600000`.
Input `{"additionalProperties":false,"properties":{"rate":{"minimum":0,"type":"number","x-mhs-delta":true,"x-mhs-unit":"K/min"},"target_temperature":{"type":"number","x-mhs-unit":"Cel"},"tolerance":{"minimum":0,"type":"number","x-mhs-delta":true,"x-mhs-unit":"K"},"wait":{"type":"boolean"}},"required":["target_temperature"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"actual_temperature":{"type":"number","x-mhs-unit":"Cel"},"reached":{"type":"boolean"},"setpoint":{"type":"number","x-mhs-unit":"Cel"}},"required":["setpoint"],"type":"object"}`

### 7.11 Actuation (3 classes)

#### `cap.actuation.gpio.v1` — Drive a digital or analog output
`write` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Drive a general-purpose output pin to a declared digital or analog value, reporting the applied value. The pin's electrical limits are declared per binding.
Kinds `io.gpio`, `io.digital`. Effects `configuration.write`. Hazards `high_voltage`, `unexpected_actuation`. Tags `gpio`, `digital output`, `relay`, `trigger`, `analog output`. Units `value`: `1`. Constraints `cancellable` `false`, `max_duration_ms` `2000`.
Input `{"additionalProperties":false,"properties":{"mode":{"enum":["digital","analog","pwm"],"type":"string"},"pin":{"minimum":0,"type":"integer"},"value":{"type":"number","x-mhs-unit":"1"}},"required":["pin","value"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"applied":{"type":"boolean"},"pin":{"minimum":0,"type":"integer"},"value":{"type":"number","x-mhs-unit":"1"}},"required":["pin","value","applied"],"type":"object"}`
#### `cap.actuation.valve.v1` — Set a valve position
`write` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Open, close or position a valve to a declared state, reporting the achieved position. The port routing map is declared per binding.
Kinds `actuation.valve`, `fluid.valve`. Effects `configuration.write`, `material.transfer`. Hazards `chemical_exposure`, `spill`, `overpressure`. Tags `valve`, `open valve`, `close valve`, `fluid routing`, `flow control`. Units `position`: `%`. Constraints `cancellable` `false`, `max_duration_ms` `10000`.
Input `{"additionalProperties":false,"properties":{"outlet":{"maxLength":64,"type":"string"},"position":{"maximum":100,"minimum":0,"type":"number","x-mhs-unit":"%"},"state":{"enum":["open","closed"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"position":{"maximum":100,"minimum":0,"type":"number","x-mhs-unit":"%"},"state":{"enum":["open","closed"],"type":"string"}},"required":["position"],"type":"object"}`
#### `cap.actuation.pump.v1` — Run a pump
`invoke` · **R1** · determinism `statistical` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Run a pump at a declared flow rate for a declared duration or volume in a declared direction, reporting the volume moved.
Kinds `actuation.pump`, `fluid.pump`. Effects `material.transfer`, `energy.emission`. Hazards `chemical_exposure`, `spill`, `overpressure`. Tags `pump`, `infuse`, `withdraw`, `flow control`, `dosing`. Units `dispensed_volume`: `uL`, `duration_s`: `s`, `flow_rate`: `uL/s`, `volume`: `uL`. Class limits `{"flow_rate":{"max":10000,"min":0,"reason":"pump and tubing limits are declared per binding","unit":"uL/s"}}`. Constraints `cancellable` `true`, `max_duration_ms` `3600000`.
Input `{"additionalProperties":false,"properties":{"direction":{"enum":["forward","reverse"],"type":"string"},"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"},"flow_rate":{"minimum":0,"type":"number","x-mhs-unit":"uL/s"},"volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"}},"required":["flow_rate","direction"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"dispensed_volume":{"minimum":0,"type":"number","x-mhs-unit":"uL"},"duration_s":{"minimum":0,"type":"number","x-mhs-unit":"s"}},"required":["dispensed_volume"],"type":"object"}`

### 7.12 Compute (2 classes)

#### `cap.compute.submit.v1` — Submit a bounded compute job
`invoke` · **R1** · determinism `none` · `serialized` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Run a bounded command-line computation on the device host with a declared timeout and return exit code and stdout/stderr artifact references. Always R1 or higher.
Kinds `compute.node`, `host.process`. Effects `computation.execute`. Hazards `arbitrary_code`, `resource_exhaustion`. Tags `compute job`, `run command`, `analysis`, `script execution`, `bounded process`. Units `timeout_s`: `s`. Constraints `cancellable` `true`, `max_duration_ms` `86400000`. Notes: The endpoint MUST NOT accept shell metacharacter expansion; command is an argv vector. The binding MUST declare which executable allowlist applies.
Input `{"additionalProperties":false,"properties":{"command":{"items":{"maxLength":4096,"type":"string"},"maxItems":256,"minItems":1,"type":"array"},"cwd":{"maxLength":4096,"type":"string"},"env":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"input_refs":{"items":{"maxLength":512,"type":"string"},"maxItems":256,"type":"array"},"timeout_s":{"maximum":86400,"minimum":1,"type":"number","x-mhs-unit":"s"}},"required":["command","timeout_s"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"duration_ms":{"minimum":0,"type":"integer"},"exit_code":{"minimum":-256,"type":"integer"},"stderr_ref":{"type":"string"},"stdout_ref":{"type":"string"}},"required":["exit_code"],"type":"object"}`
#### `cap.compute.cancel.v1` — Cancel a compute job
`invoke` · **R0** · determinism `none` · `shared` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · status `deprecated` — Cancel a previously submitted compute job and report the signal used and whether the job terminated.
Kinds `compute.node`, `host.process`. Effects `computation.execute`. Hazards `resource_exhaustion`. Tags `cancel job`, `kill process`, `abort compute`, `interrupt`, `stop analysis`. Units `grace_s`: `s`. Constraints `cancellable` `false`, `max_duration_ms` `60000`. Replaced by `mhs.operations.cancel`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.operations.cancel. The class stays valid and callable for its deprecation window; new drivers use the protocol method.
Input `{"additionalProperties":false,"properties":{"grace_s":{"maximum":300,"minimum":0,"type":"number","x-mhs-unit":"s"},"target_job_id":{"maxLength":128,"type":"string"}},"required":["target_job_id"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"cancelled":{"type":"boolean"},"signal":{"maxLength":32,"type":"string"}},"required":["cancelled"],"type":"object"}`

### 7.13 Process (1 class)

#### `cap.process.run.v1` — Run a process recipe
`invoke` · **R2** · determinism `none` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Execute a named, versioned process recipe on a process controller with declared parameters and return the exit status and a report artifact.
Kinds `process.controller`. Effects `computation.execute`, `configuration.write`. Hazards `sample_loss`, `thermal_burn`, `pressure_hazard`. Tags `process recipe`, `unit operation`, `batch process`, `recipe execution`, `process control`. Constraints `cancellable` `true`, `max_duration_ms` `86400000`. Notes: The recipe is content-addressed: recipe_ref MUST resolve to an immutable document whose digest is recorded in the receipt.
Input `{"additionalProperties":false,"properties":{"dry_run":{"type":"boolean"},"parameters":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"recipe_ref":{"maxLength":512,"type":"string"}},"required":["recipe_ref"],"type":"object"}` · Output `{"additionalProperties":false,"properties":{"exit_code":{"minimum":-256,"type":"integer"},"measurements":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true},"report_ref":{"type":"string"}},"required":["exit_code"],"type":"object"}`

### 7.14 Device (4 classes)

#### `cap.device.describe.v1` — Describe the device
`read` · **R0** · determinism `exact` · `shared` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 · status `deprecated` — Return the device's generated profile, identity, mode, capability list and the digest of its manifest, so an agent can re-orient without re-discovering the endpoint.
Kinds `device`, `world.sim`, `robot.arm`, `instrument`. Effects `measurement.capture`. Hazards none. Tags `device description`, `capabilities`, `self description`, `manifest`, `orientation`. Constraints `cancellable` `false`, `max_duration_ms` `5000`. Replaced by `mhs.devices.get`. Notes: Deprecated in 0.9: Duplicate of the protocol method mhs.devices.get (and the generated reference file). The class stays valid and callable for its deprecation window; new drivers use the protocol method. The manifest digest allows a host to detect that a device profile changed under it between sessions.
Input `{"additionalProperties":false,"properties":{"detail":{"enum":["summary","full"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"capabilities":{"items":{"type":"string"},"type":"array"},"device_id":{"type":"string"},"instance_id":{"type":"string"},"manifest_digest":{"pattern":"^sha256:[0-9a-f]{64}$","type":"string"},"mode":{"enum":["hardware","simulated","hybrid","replay"],"type":"string"},"profile":{"additionalProperties":true,"properties":{},"type":"object","x-mhs-open":true}},"required":["device_id","mode","manifest_digest","capabilities"],"type":"object"}`
#### `cap.device.calibrate.v1` — Calibrate the device
`invoke` · **R1** · determinism `none` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 · **requires permit** — Run the device's calibration procedure against a declared reference or standard and return a calibration artifact reference and validity window.
Kinds `robot.arm`, `instrument`, `sensor`, `optics.laser`. Effects `configuration.write`. Hazards `misalignment`, `sample_loss`. Tags `calibration`, `reference standard`, `zeroing`, `accuracy`, `metrology`. Constraints `cancellable` `true`, `max_duration_ms` `3600000`.
Input `{"additionalProperties":false,"properties":{"notes":{"maxLength":1000,"type":"string"},"standard_ref":{"maxLength":512,"type":"string"},"targets":{"items":{"maxLength":64,"type":"string"},"maxItems":64,"type":"array"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"calibrated":{"type":"boolean"},"calibration_ref":{"type":"string"},"valid_until":{"type":"string"}},"required":["calibrated","calibration_ref"],"type":"object"}`
#### `cap.device.self_test.v1` — Run a device self-test
`invoke` · **R1** · determinism `none` · `exclusive` · modes `hardware`, `simulated`, `hybrid`, `replay` · since 0.9.0 — Run the device's built-in self-test and return a pass/fail verdict with per-check results and a report artifact reference. Self-test does not certify safety.
Kinds `device`, `instrument`, `robot.arm`. Effects `computation.execute`. Hazards `unexpected_actuation`. Tags `self test`, `diagnostics`, `bist`, `health check`, `fault detection`. Constraints `cancellable` `false`, `max_duration_ms` `600000`. Notes: A passing self-test is evidence about the device's own checks, not an MHS safety certification.
Input `{"additionalProperties":false,"properties":{"level":{"enum":["basic","full"],"type":"string"}},"type":"object"}` · Output `{"additionalProperties":false,"properties":{"checks":{"items":{"additionalProperties":false,"properties":{"id":{"maxLength":64,"type":"string"},"status":{"enum":["pass","fail","skip","warn"],"type":"string"}},"required":["id","status"],"type":"object"},"type":"array"},"passed":{"type":"boolean"},"report_ref":{"type":"string"}},"required":["passed","checks"],"type":"object"}`
#### `cap.device.configure.v1` — Configure named device parameters
`write` · **R1** · determinism `exact` · `exclusive` · modes `hardware`, `simulated`, `hybrid` · since 0.9.0 — Write one or more named parameters of a resource (setpoints, ranges, modes, gains) as a partial patch and report what was applied. The binding's effective input schema is derived from the writable properties of the bound resource's state_schema.
Kinds `*`. Effects `state.write`. Hazards none. Tags `configure`, `set parameter`, `write setting`, `named parameter`, `setpoint`. Constraints `cancellable` `false`, `max_duration_ms` `30000`. Notes: Served by mhs.resource.write: a write is routed to the cap.device.configure.v1 binding of the target resource and its receipt carries this class id. The effective input schema of a binding is the set of state_schema properties that are not readOnly; each keeps its type, x-mhs-unit and bounds, and binding limits are keyed by state paths. A patch key outside the state schema fails with MHS.RESOURCE.FIELD_UNKNOWN; a readOnly key with MHS.RESOURCE.NOT_WRITABLE. resource_kinds '*' means any resource kind the device declares. The class floor is R1; a binding raises the risk to that of its most hazardous parameter.
Input `{"additionalProperties":true,"minProperties":1,"properties":{},"type":"object","x-mhs-open":true}` · Output `{"additionalProperties":false,"properties":{"applied":{"additionalProperties":true,"description":"The parameters as applied, keyed like the patch (values after any device rounding).","properties":{},"type":"object","x-mhs-open":true},"revision":{"minimum":0,"type":"integer"}},"required":["applied","revision"],"type":"object"}`

<!-- END GENERATED: catalogue -->

**CAP-033.** Every endpoint claiming CL1 or above MUST bind at least one class
from this catalogue or from a registered extension namespace, and MUST serve the
class document via `mhs.schema.get` for every class it binds.

**CAP-034.** The classes in this section are the REQUIRED vocabulary of OpenMHS 0.9 in
the sense that hosts and bridges MUST understand them; they are not all required
to be implemented by every device. A device binds the subset it can honestly
support.

## 8. Extension namespaces

**CAP-035.** A class that is not in this catalogue MUST live in an extension
namespace: `cap.x.<vendor>.<class>.v1` for a vendor-domain class published in the
MHS registry, or `x-cap.<vendor>.<class>.v1` for a private class that is not
published. `<vendor>` MUST be a stable lowercase DNS-derived token (for example
`acme`, `pku-yuangroup`).

**CAP-036.** An extension class MUST NOT redefine, shadow, or re-version a core
class path. `cap.x.acme.fluid.aspirate.v1` is allowed; `cap.fluid.aspirate.v2`
by a vendor is not.

**CAP-037.** A device manifest that binds an extension class MUST include the
class document's digest in the binding (`x-mhs-schema-digest`, `sha256:…`) so
hosts can pin the contract they reviewed.

**CAP-038.** Private `x-cap.*` classes MUST NOT appear in a registry claim or a
conformance report as evidence of core conformance. They MAY appear in the
device manifest with a `notes` statement that the class is
vendor-specific.

**CAP-039.** Extension classes are subject to the same schema, unit, safety and
lifecycle rules as core classes. "Extension" is a namespace statement, not a
weaker contract.

---

## 9. Deprecation

**CAP-040.** Deprecation is announced by setting `status: "deprecated"`, naming
the replacement in `supersedes` on the replacement (or `x-mhs-replaced-by` on the
deprecated document), and publishing the deprecation in the registry with a
`deprecated_at` date and a removal date no earlier than the window in
[MHS-010](10-governance.md) §5.

**CAP-041.** During the window, endpoints MUST keep serving the deprecated class
document and MUST keep accepting it; hosts SHOULD warn the operator and SHOULD
prefer the replacement when both are bound.

**CAP-042.** A class MUST NOT be removed from the core registry while any
published conformance claim at CL2 or above names it. Removal requires either the
window to expire or every claim to be re-issued against the replacement.

---

## 10. Generated artifacts and their consumers

| Artifact | Location | Consumer |
|---|---|---|
| Class catalogue (data) | [`capabilities.json`](capabilities.json) | Website capability browser, registry capability mapping, SDK tool descriptions. |
| Class catalogue (table) | [MHS-A](appendix-a-capabilities.md) | Human review, diffing, citation. |
| Class schema documents | the `input_schema` and `output_schema` of each entry of [`capabilities.json`](capabilities.json), served by `mhs.schema.get` for a capability id | `mhs.schema.get`, generated code APIs, MCP tool schemas. |
| Registry capability index | `MHS/registry/capabilities.json` (registry pipeline) | Search by class, coverage statistics. |

**CAP-043.** The catalogue JSON and this document MUST be regenerated in the same
commit. CI MUST fail if [`capabilities.json`](capabilities.json) does not
byte-match the generator output (canonical JSON) or if [MHS-A](appendix-a-capabilities.md)
does not match the table generated from it.

**CAP-044.** The `units` map in [`capabilities.json`](capabilities.json) MUST equal
the set of `x-mhs-unit` annotations discovered in `input_schema` and
`output_schema`, keyed by field path (dotted for nested objects, for example
`position.x`; array-valued fields use the field name). If two different units
share a path inside one class, the class is invalid.

---

## 11. Requirements traceability

Conformance test IDs equal requirement IDs ([MHS-001](01-conformance.md) §4). The
test areas relevant to this chapter are `CAP` (class documents and bindings) and
`REG` (catalogue publication). The tests that MUST exist in the suite:

| Requirement | Test | What it checks |
|---|---|---|
| CAP-004 | CAP-004 | Top-level input/output schemas are closed; `x-mhs-open` absent on core classes. |
| CAP-008 | CAP-008 | Every class served by `mhs.schema.get` validates against `capability.schema.json`. |
| CAP-016 | CAP-016 | A binding cannot accept an input that the class rejects (probe with an invalid value). |
| CAP-017 | CAP-017 | Device `safety.risk_class` ≥ max binding risk class. |
| CAP-021 | CAP-021 | Every numeric physical field carries `x-mhs-unit`; validator flags a stripped unit. |
| CAP-033 | CAP-033 | Every bound class is retrievable via `mhs.schema.get`. |
| CAP-034 | CAP-034 | All bound class ids match the core catalogue or a registered extension. |
| CAP-043 | CAP-043 | `capabilities.json` digest matches the published catalogue digest in `hello.features` / registry claim. |

---

## 12. Informative: choosing between classes

This section is informative.

- If the native call moves a robot to a joint configuration, use
  `cap.motion.joint_position.v1`; do not invent `cap.motion.move.v1`.
- If the native call transfers material between containers, use
  `cap.fluid.transfer.v1` (fluid) or `material.move` in `cap.sample.move.v1`
  (labware/sample object), depending on what actually moves.
- If the native call executes a user-supplied command line, use
  `cap.process.run.v1` or `cap.compute.submit.v1` and declare R1+ risk; never map
  an arbitrary shell to a read class.
- If the native call only reports a value and has no side effect, use a `read`
  class. "It warms up the sensor" is a side effect.
- If a class is missing, prefer an extension class over overloading a core class
  with a different meaning. Overloading is how device vocabularies rot.
