# MHS-002 — Wire Protocol

| Field | Value |
|---|---|
| Document | MHS-002 (normative) |
| Status | OpenMHS 0.9 development draft (wire revision `mhs_version` `1.0`) |
| Editor | The OpenMHS Authors |
| Layer | core; §5 Sessions and Permits; §8 and §12 Events; §14 Evidence; §15.1 Composition (reserved) ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md); overview in [00-architecture.md](00-architecture.md) §3–§5 (informative) |
| Data contracts | [`receipt.schema.json`](../schema/receipt.schema.json), [`defs.schema.json`](../schema/defs.schema.json), [`endpoint-descriptor.schema.json`](../schema/endpoint-descriptor.schema.json) |

This document is the method-by-method reference for MHS/1.0 (wire revision 1 of
OpenMHS 0.9): message framing, common parameters, the methods of §3, receipts,
operations, subscriptions, evidence, error structure and limits. It details
[core.md](core.md) and MUST NOT contradict it; transport bindings are in
[MHS-008](08-transports.md) and safety semantics in [MHS-004](04-safety.md).

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Base

### 1.1 Framing

**PROTO-001.** MHS/1.0 messages MUST be UTF-8 JSON-RPC 2.0 objects, exactly as
defined by the JSON-RPC 2.0 specification. A message MUST NOT contain a BOM and
MUST NOT contain trailing content after the JSON value on its framing unit.
Messages are RFC 8259 JSON: a `NaN`, `Infinity` or `-Infinity` literal is
`MHS.PROTOCOL.PARSE_ERROR` (HTTP 400 over HTTP; a number that overflows to infinity, as
`1e999`, and in-process parameters with a non-finite number are the same error), with one exception: an e-stop request is still
served, its non-finite values become `null` ([core.md](core.md) CORE-076,
CORE-183).

**PROTO-002.** The JSON-RPC `jsonrpc` member MUST be the string `"2.0"` on every
request, response and notification. A request missing it MUST be rejected with
`MHS.PROTOCOL.INVALID_REQUEST`.

**PROTO-003.** Method names are namespaced `mhs.*`. §3 lists the 26 methods of the
protocol; the reference endpoint implements 24 of them (`mhs.composition.run` is
reserved, §15.1, and `mhs.registry.search` is not an endpoint method, §15.2). An
endpoint MAY implement additional methods under `x-` prefixed names only as an
extension, and clients MUST NOT require them.

### 1.2 Requests, responses, notifications

```json
{"jsonrpc": "2.0", "id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4X",
 "method": "mhs.command",
 "params": {"session_id": "mhs_s_01J8ZQ3V6Y", "device_id": "mhs://localhost:7400/lab/conveyor-workcell",
            "capability_id": "cap.world.step.v1", "input": {"ticks": 10},
            "command_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4Y", "deadline_ms": 5000}}
```

```json
{"jsonrpc": "2.0", "id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4X",
 "result": {"receipt_id": "01J8ZQ3V6Y…", "status": "completed", "…": "…"}}
```

**PROTO-004.** A request `id` MUST be a string or an integer and MUST be unique
within the connection for the lifetime of the connection. Clients SHOULD use a
ULID. An endpoint MUST echo the `id` exactly in the response.

> **Bare receipts.** The `result` of every receipt-returning method (`mhs.command`,
> `mhs.resource.write`, `mhs.restore`, `mhs.operations.get`, `mhs.operations.cancel`,
> `mhs.safety.estop`, `mhs.safety.reset`) is the receipt object itself, with no
> `{"receipt": …}` wrapper ([core.md](core.md) CORE-093). The reference SDK's
> `client.invoke()` returns the same object ([`../sdk/INTERFACE.md`](../sdk/INTERFACE.md)).

**PROTO-005.** A notification is a request without `id`; the endpoint MUST NOT send
a response to a notification. Notifications are used only for `mhs.event`
([§12](#12-subscriptions-and-notifications)); a client MUST NOT send an effectful
method as a notification because that would make the outcome unreceiptable. The
effectful methods are `mhs.command`, `mhs.resource.write`, `mhs.restore`,
`mhs.safety.reset`, `mhs.safety.permit` and `mhs.composition.run`: an endpoint
drops such a notification, logs it and never executes it. The one exception is
`mhs.safety.estop` (and `mhs.command` on `cap.motion.estop.v1`), which still
latches ([core.md](core.md) CORE-183).

**PROTO-006.** Server-originated notifications MUST have method `mhs.event` and
MUST NOT reuse a client-request `id`.

### 1.3 Batches

**PROTO-007.** A batch is a non-empty JSON array of requests and/or
notifications. The endpoint MUST respond with an array of responses in any
order; each response MUST correspond to one request in the batch. An empty array
MUST be rejected with `MHS.PROTOCOL.INVALID_REQUEST`.

**PROTO-008.** A batch MUST be treated as a sequence of independent requests for
validation purposes, but the endpoint MUST apply them in order for methods that
mutate the same device; an endpoint MAY reject a batch that mixes mutations to
different devices when it cannot order them safely (`MHS.PROTOCOL.BATCH_NOT_ATOMIC`).

**PROTO-009.** A batch whose individual requests share a `command_id` is a
client error; the endpoint MUST process the first and reject the rest as
`MHS.CONFLICT.COMMAND_ID_REUSE` or return the retained receipt with
`replayed: true`, consistently with §10.2.

### 1.4 Common parameters

| Parameter | Type | Required on | Meaning |
|---|---|---|---|
| `trace_id` | string | optional everywhere | W3C `traceparent`-compatible trace identifier, propagated into receipts' `x-vendor`/logs, never used for routing. |
| `deadline_ms` | integer ≥ 1 | blocking methods (§5.1 flag **D**) | Maximum time the caller will wait, measured from receipt of the request. Absent on a blocking method is `MHS.PROTOCOL.DEADLINE_INVALID`. |
| `session_id` | string `mhs_s_…` | every method except `hello`, discovery and registry | The lease within which the call happens. |
| `device_id` | `mhs://…` | when the session covers more than one device | Target device. A single-device session MAY omit it. |
| `expected_revision` | integer | optional on mutations | Optimistic concurrency guard (§10.4). |
| `command_id` | ULID | every mutation | Idempotency key (§10.2). |
| `permit_id` | string | gated capabilities | Approval artifact ([MHS-004](04-safety.md) §6). |
| `lease` | string | optional on commands | Opaque concurrency lease returned by a prior accepted operation. |

**PROTO-010.** A blocking method invoked without `deadline_ms` MUST be rejected
with JSON-RPC `-32602` and `data.mhs_code = "MHS.PROTOCOL.DEADLINE_INVALID"`; the
endpoint MUST NOT substitute a server default.

**PROTO-011.** `deadline_ms` bounds only the wait for the response. The
monotonic budget starts when the endpoint receives the request and includes
preparation, waiting, bridge calls and result assembly; it applies to every method
flagged **D** in §3, not only `mhs.command`. It never cancels or shortens an
execution: execution is bounded by the `max_duration_ms` of the binding's
`constraints` (else of the class), counted from dispatch. When the deadline passes
before a command has completed, a `long_running` binding answers the current
non-terminal `running` receipt with its `operation_id`, and any other command
answers an `unknown` receipt `MHS.OUTCOME.TIMEOUT` with `retryable: false`; in both
cases the command keeps running ([core.md](core.md) CORE-100, which also states the
`max_duration_ms` rules; OP-010 is the receipt-side view of this rule). A read that
exceeds its budget MUST fail with a structured timeout; an effectful method
(`restore`, `safety.reset`) MUST return a truthful timeout / UNKNOWN carrying the
pre-assigned `command_id` so the effect can be reconciled, and MUST NOT report a
late success. `mhs.safety.estop` is exempt from the `deadline_ms` gate and never
answers `MHS.OUTCOME.TIMEOUT` ([core.md](core.md) CORE-076, CORE-077).

### 1.5 Identifiers and digests

Identifiers follow [`defs.schema.json`](../schema/defs.schema.json):
`endpoint_id` (`mhs://host[:port][/prefix]`), `device_id` (a URI below an endpoint),
`instance_id` (ULID), `session_id` (opaque; `mhs_s_` + a ULID + a random suffix),
`operation_id` (`op_` + a full ULID), `command_id`/`receipt_id` (ULID),
`capability_id`, `resource_id`, `permit_id`. Clients treat ids minted by the
endpoint as opaque ([core.md](core.md) CORE-011). Digests are `sha256:<64 lowercase hex>`
over RFC 8785 JCS bytes (PROTO-012).

**PROTO-012.** Every digest an endpoint emits MUST be computed over JCS bytes and
MUST carry the `sha256:` prefix. An endpoint MUST NOT accept a digest it cannot
recompute.

---

## 2. Version negotiation

**PROTO-013.** `mhs.hello` is the first call on every new connection. The client
sends supported protocol versions; the server MUST select the highest version it
supports that the client lists and MUST return it as `mhs_version`. If there is no
common MAJOR version, the server MUST fail with
`MHS.PROTOCOL.VERSION_UNSUPPORTED` and MUST NOT continue.

**PROTO-014.** Capability classes are versioned separately
([MHS-003](03-capability-registry.md) §2). A client that requests a class MAJOR it
does not know MUST treat the class as unknown; an endpoint MUST reject a command
whose class MAJOR it does not implement with a `rejected` receipt
(`MHS.CAPABILITY.UNKNOWN`), not a protocol error.

**PROTO-015.** The negotiated `mhs_version` MUST be echoed in every subsequent
`hello`-adjacent result that reports conformance, and MUST be recorded in receipts'
`mode`-adjacent metadata through the endpoint profile; it is not repeated per
message.

---

## 3. Method summary

Flags: **M** mandatory, **S** should, **O** optional for endpoints; **D** requires
`deadline_ms`; **Idem** idempotent by `command_id`; **Receipt** returns a receipt
(may be `rejected`).

| # | Method | Level | D | Idem | Receipt | Result is |
|---|---|---|---|---|---|---|
| 1 | `mhs.hello` | M | – | – | – | server info |
| 2 | `mhs.devices.list` | M | – | – | – | device summaries/manifests |
| 3 | `mhs.devices.get` | M | – | – | – | device manifest |
| 4 | `mhs.schema.get` | M | – | – | – | JSON Schema or class document |
| 5 | `mhs.session.open` | M | – | – | – | session grant |
| 6 | `mhs.session.heartbeat` | S | – | – | – | lease extension |
| 7 | `mhs.session.close` | M | – | – | summary | session summary |
| 8 | `mhs.resource.read` | M | ✓ | – | – | state document |
| 9 | `mhs.resource.write` | S | ✓ | ✓ | ✓ | receipt (`cap.device.configure.v1`) |
| 10 | `mhs.command` | M | ✓ | ✓ | ✓ | receipt |
| 11 | `mhs.operations.get` | M | ✓ | – | ✓ | receipt + progress |
| 12 | `mhs.operations.list` | S | – | – | – | operation list |
| 13 | `mhs.operations.cancel` | M | ✓ | – | ✓ | receipt |
| 14 | `mhs.subscribe` | M | ✓ | – | – | subscription grant |
| 15 | `mhs.unsubscribe` | M | – | – | – | sequence end |
| 16 | `mhs.snapshot` | S | ✓ | – | – | snapshot |
| 17 | `mhs.restore` | S | ✓ | ✓ | ✓ | receipt |
| 18 | `mhs.safety.status` | M | ✓ | – | – | safety status |
| 19 | `mhs.safety.estop` | S (M CL3+) | – (exempt) | – | ✓ | receipt (`output.latency_ms`) |
| 20 | `mhs.safety.reset` | S (M CL3+) | ✓ | – | ✓ | receipt |
| 21 | `mhs.safety.permit` | S (M gated) | – | – | – | permit |
| 22 | `mhs.evidence.export` | M | – | – | – | evidence bundle |
| 23 | `mhs.evidence.verify` | S | – | – | – | verification report |
| 24 | `mhs.conformance.report` | S | – | – | – | conformance report |
| 25 | `mhs.composition.run` | O (reserved, not implemented in 0.9) | ✓ | ✓ | ✓ | receipt with child receipts |
| 26 | `mhs.registry.search` | not an endpoint method (§15.2) | – | – | – | – |

**PROTO-016.** An endpoint MUST implement every **M** method for its profile; a
method listed **M** that returns `MHS.PROTOCOL.METHOD_NOT_FOUND` caps the
endpoint's achievable level at CL0 ([MHS-001](01-conformance.md) §5).

**PROTO-017.** A **S** method that is not implemented MUST return
`MHS.PROTOCOL.METHOD_NOT_FOUND` with `data.details.supported = false`, not a
partial result.

---

## 4. Discovery methods

### 4.1 `mhs.hello`

Params: `client{name,version}`, `protocol_versions[]`, `features[]`,
`trace_id?`.

Result: `server{name,version}`, `implementation{name,version}` (the SDK distribution,
for example `openmhs`), `spec_version` (the OpenMHS specification line, `0.9`),
`mhs_version`, `protocol_versions[]`, `endpoint_id`, `devices[]` summaries,
`limits{max_request_bytes, max_batch, max_subscriptions, max_rate_per_s,
session_max_ttl_s, receipt_retention_days, max_receipt_retention_s, receipt_store,
max_command_deadline_ms}`, `time{now, mono_ms?}`, `started_at`,
`conformance[{profile, level, report_digest?}]` (only the devices' own claims; `[]`
when none is made), `features[]` and `safety{certified, notice}`. The two retention
members state one retention in two units (default 30 days, EVID-018);
`receipt_store` is `memory` or `state_dir` and says whether receipts, the
idempotency store and the e-stop latch survive a restart ([core.md](core.md) CORE-170,
CORE-186).

```json
{"jsonrpc":"2.0","id":"01J8ZQ3V6Y","method":"mhs.hello","params":{
  "client":{"name":"openai4s","version":"2.4.0"},
  "protocol_versions":["1.0"],
  "features":["batch","sse","mcp"]}}
```

```json
{"jsonrpc":"2.0","id":"01J8ZQ3V6Y","result":{
  "server":{"name":"mhs-reference-server","version":"0.9.0.dev0"},
  "implementation":{"name":"openmhs","version":"0.9.0.dev0"},
  "spec_version":"0.9",
  "mhs_version":"1.0",
  "protocol_versions":["1.0"],
  "endpoint_id":"mhs://localhost:7400",
  "devices":[{"device_id":"mhs://localhost:7400/lab/conveyor-workcell",
              "instance_id":"01J8ZQ3V6Y7M2N4P6R8S0T2V4W",
              "display_name":"Deterministic conveyor workcell (simulated)",
              "mode":"simulated","risk_class":"R1"}],
  "limits":{"max_request_bytes":1048576,"max_batch":64,"max_subscriptions":64,
            "max_rate_per_s":50,"session_max_ttl_s":86400,"receipt_retention_days":30,
            "max_receipt_retention_s":2592000,"receipt_store":"memory",
            "max_command_deadline_ms":600000},
  "time":{"now":"2026-10-20T07:45:00Z","mono_ms":102334},
  "conformance":[],
  "features":["MHS.SAFETY.NOT_CERTIFIED","batch","sse"],
  "safety":{"certified":false,"notice":"MHS.SAFETY.NOT_CERTIFIED"}}}
```

**PROTO-018.** `hello.features` MUST contain `MHS.SAFETY.NOT_CERTIFIED`
([MHS-004](04-safety.md) §9). It MUST NOT contain a feature the endpoint does not
implement.

**PROTO-019.** `hello` MUST NOT require a session and MUST be callable at any time
on a live connection. Its `devices` list MUST be consistent with
`mhs.devices.list` at the same revision.

### 4.2 `mhs.devices.list`

Params: `detail ∈ {summary, full}?` (default `summary`), `filter{mode?,
risk_class?, capability?, tag?}?`.

Result: `devices[]` — summaries `{device_id, instance_id, display_name, mode,
risk_class, profile{title, tags}}` or, when `detail: "full"`, complete device
manifests ([`device.schema.json`](../schema/device.schema.json)).

**PROTO-020.** Every `device_id` returned MUST be a valid URI under the
endpoint's `endpoint_id`; an endpoint MUST NOT list devices it cannot serve.

### 4.3 `mhs.devices.get`

Params: `device_id`, `include_state?` (default `true` in CL1+ endpoints).

Result: the device manifest. When `include_state` is false, `resources[].state`
MAY be omitted.

**PROTO-021.** When the manifest changes (capabilities, safety, fidelity),
`devices.get` MUST return the new manifest with a digest; the digest MUST equal
the one reported by `cap.device.describe.v1` if bound
([MHS-003](03-capability-registry.md) §7.14).

### 4.4 `mhs.schema.get`

Params: `ref` — either a schema reference (a shipped schema file name such as
`device.schema.json`, or a schema `$id` such as
`https://mhs.openai4s.org/schema/0.9/device.schema.json`) or a
`capability_id`; optional `device_id` and `resource` select the binding whose
effective schema is wanted.

Result: `{schema, digest, ref, media_type}`. When `ref` is a capability id, the
class document ([`capability.schema.json`](../schema/capability.schema.json)) is
returned as `schema` with its own `input_schema`/`output_schema`; when `ref` is a
schema URI the addressed JSON Schema document is returned.

**PROTO-022.** `schema.get` MUST serve the exact schema the endpoint validates
against, byte-identical modulo JSON whitespace; `digest` MUST be the JCS digest of
`schema`. If an endpoint cannot resolve a `ref`, it MUST return
`MHS.PROTOCOL.INVALID_PARAMS` with `data.details.ref` set, not an empty schema.
An endpoint serves only the classes it binds and the schemas shipped with the
package; a path, `..`, `~`, a drive letter or a URL that is not a known `$id` is
refused, and a document a local caller loaded is never served ([core.md](core.md)
CORE-185).

---

## 5. Session methods

### 5.1 `mhs.session.open`

Params: `principal{id,kind,display_name?,contact?}`, `device_ids[]`,
`capabilities[]` (class ids or patterns, or objects `{capability_id, resource?}`
that grant one binding), `mode`, `ttl_s`, `client_info{name,version,transport}`,
`approvals[]?` (for R3 hardware sessions). When the endpoint authenticated the
caller, the session takes the authenticated principal and `principal` is kept only
as a claim ([core.md](core.md) CORE-150).

Result: `session_id`, `granted[{device_id, capability_id, resource?}]` (one entry
per granted binding, [core.md](core.md) CORE-024),
`expires_at`, `safety_context{risk_class, estop{engaged,latching,kind,latency_ms},
interlocks[], permits[]}`, `mode`, `limits{max_open_operations,
max_subscriptions, max_rate_per_s}`.

```json
{"jsonrpc":"2.0","id":"01J8ZQ3V6Z","method":"mhs.session.open","params":{
  "principal":{"id":"agent:openai4s/session-7","kind":"agent","display_name":"OpenAI4S"},
  "device_ids":["mhs://localhost:7400/lab/conveyor-workcell"],
  "capabilities":["cap.world.*.v1","cap.actuation.valve.v1"],
  "mode":"simulated","ttl_s":600,
  "client_info":{"name":"openai4s","version":"2.4.0","transport":"http"}}}
```

**SESS-001.** `session.open` MUST grant the intersection of the requested
capabilities with the device's access policy and MUST reject the whole request if
no capability is grantable (`MHS.SESSION.CAPABILITY_NOT_GRANTED`). A grant MUST
NOT be widened after open; the client MUST re-open
([core.md](core.md) CORE-024).

**SESS-002.** The session's `mode` MUST equal the device's declared `mode`;
otherwise the endpoint MUST return `MHS.SESSION.MODE_MISMATCH` and MUST NOT open
a session ([MHS-005](05-fidelity.md) §3).

**SESS-003.** `ttl_s` MUST be bounded by `hello.limits.session_max_ttl_s`.
A session opened with `mode: "hardware"` on a device whose risk class is R3 MUST
carry `approvals[]` naming a responsible human principal; otherwise
`MHS.SAFETY.APPROVAL_REQUIRED`.

**SESS-004.** A session MUST expire at `expires_at`. On expiry the endpoint MUST
release its leases, transition every running operation to cancellation-to-safe-state,
and reject further calls with `MHS.SESSION.EXPIRED`, a heartbeat included. An
endpoint MUST NOT extend a session implicitly. Expiry is driven by a timer, not by
the next call: the endpoint cancels the session's operations, releases its permits
and subscriptions and runs the `safe_state.achieved_by` actions of the devices it was
driving, relying on cooperative cancellation ([core.md](core.md) CORE-085).

### 5.2 `mhs.session.heartbeat`

Params: `session_id`. Result: `expires_at`, `safety_context`.

**SESS-005.** Heartbeat MUST succeed only for a live session and MUST NOT change
the session's grants or mode. An endpoint MAY refuse repeated heartbeats faster
than the session's declared rate (`MHS.LIMIT.RATE_EXCEEDED`).

### 5.3 `mhs.session.close`

Params: `session_id`, `reason?`. Result: `closed_at`,
`summary{commands, completed, rejected, failed, cancelled, receipts_head}`.

**SESS-006.** Closing MUST release leases, close subscriptions, and stop accepting
new commands. Running operations MUST be cancelled to the declared safe state
before `close` returns, or the result MUST report `summary.cancellation_pending:
true` with the affected `operation_id`s.

---

## 6. Resource methods

### 6.1 `mhs.resource.read`

Params: `session_id`, `resource_id`, `device_id?`, `fields[]?`, `deadline_ms`.

Result: `revision`, `state`, `state_hash`, `sampled_at`.

**PROTO-023.** `state_hash` MUST equal
`sha256(JCS(state))` with `hash_exclusions` applied
([00-architecture.md](00-architecture.md) §3.3, informative), and `revision` MUST
equal the device revision at sampling. A read MUST NOT advance the revision.

**PROTO-024.** Reads MUST be served from the device's current state; an endpoint
MUST NOT return a cached state older than the last accepted mutation except on a
replay endpoint, which MUST return the recorded revision and MUST identify itself
as `mode: "replay"`.

### 6.2 `mhs.resource.write`

Params: `session_id`, `resource_id`, `device_id?`, `patch` (object), `command_id`,
`expected_revision?`, `deadline_ms`, `permit_id?`.

Result: the receipt of the resource's `cap.device.configure.v1` binding
([core.md](core.md) CORE-022); a completed receipt's `output` is `{applied,
revision}`, where `applied` is what the bridge reports as applied, else the patched
parameters as the state reads back.

**PROTO-025.** A write MUST follow the same envelope, permit, revision and
receipt rules as `mhs.command`; it MUST validate the patch against the resource
state schema and MUST reject unknown fields (`MHS.RESOURCE.FIELD_UNKNOWN`) and
`readOnly` fields (`MHS.RESOURCE.NOT_WRITABLE`, `data.details.fields`). Both checks
apply at any depth, through `allOf`, `anyOf`, `oneOf`, `then`, `else`, local `$ref`,
`patternProperties` and the draft-07 tuple form of `items`; a `readOnly` root or an
unresolvable `$ref` is `NOT_WRITABLE` ([core.md](core.md) CORE-022).

**PROTO-025a.** `resource.write` is not a generic state-mutation escape hatch. It
is a command of the `cap.device.configure.v1` binding of the target resource, and
the endpoint MUST run that binding's input schema (the writable properties of the
resource's `state_schema`), envelope limits, required interlocks, permit rules and
`expected_revision` exactly as for `mhs.command`. If the resource has no configure
binding, or the request names a `capability_id` other than
`cap.device.configure.v1`, the endpoint MUST reject with the JSON-RPC error
`MHS.RESOURCE.NOT_WRITABLE` (`data.details.reason` `configure_unbound` or
`write_class_not_configure`) and MUST NOT write state: a patch is never passed as the
input of another class. Every write receipt, a refusal included, carries
`capability_id` `cap.device.configure.v1`.

**PROTO-026.** A write MUST NOT create or delete resources and MUST NOT change
`resource_id`, `kind`, or `state_schema`.

---

## 7. Command and operation methods

### 7.1 `mhs.command`

Params: `session_id`, `device_id?`, `capability_id`, `resource?`, `input`,
`command_id`, `expected_revision?`, `deadline_ms`, `permit_id?`, `lease?`.

Result: a receipt ([§10](#10-receipts)), returned bare as the JSON-RPC `result`
([core.md](core.md) CORE-093). When the class is bound to several resources of the
device, `resource` is required (`MHS.PROTOCOL.INVALID_PARAMS`, `data.details.reason`
`resource_required`); a resource the class is not bound to is a `rejected` receipt
`MHS.CAPABILITY.NOT_BOUND`.

**PROTO-027.** `input` MUST be validated against the binding's input schema and
then against the class input schema; schema-invalid input MUST produce a
`rejected` receipt with `error.mhs_code = "MHS.CAPABILITY.INPUT_INVALID"` and
`data.details.errors[]`, and MUST NOT produce a JSON-RPC error.

**PROTO-028.** Errors that occur before a receipt can exist are JSON-RPC errors:
parse/framing (`MHS.PROTOCOL.*`), authentication (`MHS.AUTH.*`), session-level
failures (`MHS.SESSION.*`), transport (`MHS.TRANSPORT.*`). Errors that are an
outcome of a well-formed command are receipts with `status` `rejected`, `failed`
or `unknown`. Implementations MUST NOT move a physical rejection into the
JSON-RPC error channel.

**PROTO-029.** The endpoint MUST evaluate the envelope in the order of
[core.md](core.md) CORE-060 (see [MHS-004](04-safety.md) §3) before executing, and
MUST record the receipt before returning it for any terminal status.

### 7.2 `mhs.operations.get`

Params: `session_id`, `operation_id`, `deadline_ms`. Result: receipt plus
`progress{percent, ticks, message}` (the receipt schema carries `progress`).

**PROTO-030.** `operations.get` MUST return the current receipt snapshot of the
operation and MUST remain valid until the receipt retention window expires. An
unknown operation id MUST return `MHS.OPERATION.UNKNOWN`.

### 7.3 `mhs.operations.list`

Params: `session_id`, `device_id?`, `state?` (any receipt status). Result:
`operations[{operation_id, device_id, capability_id, state, progress, accepted_at}]`.

**PROTO-031.** Listing MUST include operations accepted by this session and MAY
include operations of the same principal on the same device that are still
running; it MUST NOT reveal another principal's operations.

### 7.4 `mhs.operations.cancel`

Params: `session_id`, `operation_id`, `deadline_ms`. Result: the operation's
receipt: its `cancelled` final receipt when it stopped within the deadline, else a
`running` snapshot with `cancellation{requested_at, requested_by, reason,
safe_state_achieved}`; the retained final receipt when the operation had already
finished. An operation of another principal is `MHS.OPERATION.UNKNOWN` in strict
mode ([core.md](core.md) CORE-151).

**PROTO-032.** Cancellation MUST be best-effort and bounded by `deadline_ms`. A
cancellation result MUST NOT claim that the physical effect stopped until the
worker or the endpoint's stop path has acknowledged it; while a cancellation is
still pending the receipt MUST remain non-terminal (`status: "running"`,
`cancellation.safe_state_achieved: false`). If
the operation has not reached its safe state by the deadline, the receipt MUST
have `status: "running"`, `cancellation.safe_state_achieved: false`, and the
endpoint MUST continue cancellation; the client MUST poll `operations.get`. Once
cancelled, the receipt MUST have `status: "cancelled"`.

**PROTO-033.** Cancelling a completed operation MUST return the retained receipt
with `cancellation.requested_at` absent and MUST NOT return
`MHS.OPERATION.ALREADY_FINISHED` as a receipt status change.

---

## 8. Subscription methods

### 8.1 `mhs.subscribe`

Params: `session_id`, `streams[]` (each `{stream, device_id?, resource_id?,
capability_id?}`), `filter?`, `rate_hz?`, `deadline_ms`.

`stream` ∈ `state`, `telemetry`, `events`, `log`, `progress`. Result:
`subscription_id`, `seq_start`, `streams[]`, `expires_at`.

**EVT-001.** `subscribe` MUST return a `subscription_id` and the first `seq`
(`seq_start`). Sequences MUST be strictly increasing per subscription and MUST
NOT be reused within the session. `seq` is a JSON integer; endpoints above 2^53
MUST emit decimal strings.

**EVT-002.** `rate_hz` is a maximum, not a guarantee; a stream whose native rate
is lower MUST deliver at its native rate. An endpoint MUST NOT coalesce across
different `resource_id` values when the subscriber requested them separately.

**EVT-003.** A subscription MUST expire with its session unless the endpoint
declares otherwise in `expires_at`.

### 8.2 `mhs.unsubscribe`

Params: `session_id`, `subscription_id`. Result: `seq_end`, `delivered`,
`dropped`.

**EVT-004.** After `unsubscribe` returns, the endpoint MUST NOT deliver further
events for that subscription; events in flight MAY be dropped but MUST be
reported in `dropped` if the endpoint can count them.

### 8.3 The `mhs.event` notification

```json
{"jsonrpc":"2.0","method":"mhs.event","params":{
  "subscription_id":"sub_01J8ZQ3W0A",
  "seq":1042,
  "ts":"2026-10-20T07:46:59.221Z",
  "stream":"state",
  "device_id":"mhs://localhost:7400/lab/conveyor-workcell",
  "resource_id":"world",
  "revision":77,
  "state_hash":"sha256:…",
  "payload":{"tick":77,"door":"closed","estop":"released"}}}
```

**EVT-005.** Every notification MUST be `mhs.event` with `subscription_id`, `seq`,
`ts`, `stream`, and `payload`. `payload` MUST be validated by the stream's
declared schema; a malformed payload is a conformance failure, not a client
burden. Safety events (an e-stop engaged or confirmed, a reset) are delivered on the
`control` stream with `type: "safety"`; the `safety` stream name is not
subscribable ([core.md](core.md) CORE-184). `mhs.event` is the only notification
an endpoint sends. Events reach only the session that owns the subscription, and
`mhs.unsubscribe` works only for that session (another session's subscription id is
reported like an unknown one).

**EVT-006.** A consumer that cannot keep up MUST receive
`MHS.LIMIT.BACKPRESSURE` from `subscribe` (or a later `mhs.event` with
`stream: "control"`, `type: "backpressure"`) rather than unbounded buffering.
Endpoints MUST bound per-session subscription buffers and MUST report the drop
count. A bounded queue MUST NOT grow after overflow: dropped sequences are
coalesced into at most one `{"stream":"control","type":"gap"}` control event,
which occupies the same buffer budget and is delivered before the surviving
events. Dropping samples without a gap event is non-conformant. Delivery order
MUST remain strictly increasing in `seq`: a coalesced gap control event is
placed in sequence order after the surviving records it precedes, its `from`/`to`
range MUST NOT include an event that is still delivered, and a gap already
delivered by a drain MUST NOT be re-emitted by a later publication.

**EVT-007.** On reconnect, a client MUST subscribe again and MUST reconcile state
via `mhs.resource.read` before trusting post-reconnect deltas; a transport
binding MAY offer resumption by `subscription_id` and last `seq`, but absence of
resumption MUST NOT be treated as a gap.

**EVT-008.** A detected sequence gap MUST be delivered as an explicit control
event `{"stream":"control","type":"gap","from":a,"to":b}`. Silently dropping
samples is non-conformant. A client MUST treat the state after a gap as unknown
until it has re-read or been sent a fresh state event.

**EVT-009.** An endpoint MUST enforce a maximum number of concurrent
subscriptions per session (`hello.limits.max_subscriptions`) and MUST return
`MHS.LIMIT.SUBSCRIPTION_LIMIT` when exceeded.

---

## 9. Snapshot methods

### 9.1 `mhs.snapshot`

Params: `session_id`, `device_id`, `deadline_ms`. Result:
`{device_id, instance_id, revision, state_hash, state, snapshot, mode,
fidelity_digest, snapshot_digest, created_at}`. `snapshot` is the canonical
`{resource_id: state}` document and `state` its wire alias (at least one MUST be
present); both are validated by [`snapshot.schema.json`](../schema/snapshot.schema.json).

**PROTO-034.** `mhs.snapshot` MUST be rejected with `MHS.MODE.SNAPSHOT_UNSUPPORTED`
unless the device mode is `simulated` or `replay` and
`fidelity.snapshot_restore` is true. A snapshot MUST be self-consistent: its
`state_hash` MUST recompute from `state` under the device's `hash_exclusions`.

### 9.2 `mhs.restore`

Params: `session_id`, `device_id`, `snapshot`, `command_id`, `deadline_ms`.
Result: receipt for `cap.internal.restore.v1`.

**PROTO-035.** `restore` MUST reject a snapshot whose `device_id`, `instance_id`,
`mode` or `fidelity_digest` differs from the target device, or whose `mode` is
`hardware`, with `MHS.MODE.RESTORE_UNSUPPORTED` (or
`MHS.CONFLICT.SNAPSHOT_MISMATCH` when the snapshot belongs to another
device/instance/fidelity configuration). Those metadata fields are REQUIRED: a
snapshot that omits any of them MUST be rejected rather than accepted with a
weaker identity check. `state_hash` MUST recompute from the snapshot's own
submitted `state` document; a mismatch is rejected pre-effect with
`MHS.CONFLICT.STATE_HASH`. A successful restore MUST advance the revision, MUST
set `state_hash_after` to the hash recomputed from the *actual post-restore
state*, and MUST be receipted like any mutation. The endpoint MUST verify the
post-restore state; if the bridge does not reproduce the declared
`state_hash`, the receipt MUST NOT be `completed`. If the endpoint can roll back
to the pre-restore state it MUST report `failed` with the discrepancy and zero
net effect; otherwise it MUST report `unknown` with the observed state hash.

**PROTO-035a (replay).** A replay device is read-only: `restore` MUST return a
`rejected` receipt with `MHS.MODE.READ_ONLY`, and seeking MUST use
`mhs.resource.read` with `filter.revision`. A replay endpoint MUST advertise the
`replay.seek` feature in `hello.features`; a read for a recorded revision MUST
return that frame's state, that revision and its recorded `state_hash`, and an
unrecorded revision MUST fail with `MHS.RESOURCE.UNKNOWN` naming the recorded
revisions. This supersedes any earlier description of restore-as-seek.

---

## 10. Receipts

### 10.1 Shape

A receipt is validated by [`receipt.schema.json`](../schema/receipt.schema.json).
Required fields: `receipt_id`, `command_id`, `session_id`, `endpoint_id`,
`device_id`, `capability_id`, `input_digest`, `status`, `mode`, `accepted_at`.
Additional fields include `operation_id`, `principal`, timing, revisions,
`state_hash_after`, `output`, `effects[]`, `progress`, `telemetry_ref`,
`artifacts[]`, `error`, `approvals[]`, `cancellation`, `replayed`, `seed`,
`evidence{seq, prev_digest, digest}`, `redacted_fields`.

**PROTO-036.** `input_digest` MUST be
`sha256(JCS({capability_id, resource, input}))`. The same digest binds permits
([MHS-004](04-safety.md) §6) and the idempotency store. `input_digest` MUST NOT
include `command_id`, `session_id` or `deadline_ms`.

**PROTO-037.** `effects[]` MUST describe what physically happened, with
`reversible` and `severity`; an irreversible effect MUST carry an
`irreversible_reason`. A completed receipt with an empty `effects` array MUST be
justified by the capability's class effects being `none`.

### 10.2 Status and idempotency

| Status | Terminal | Meaning | Must carry |
|---|---|---|---|
| `accepted` | no | Validated and queued; not yet started. | `operation_id` |
| `running` | no | Executing. | `operation_id` |
| `completed` | yes | Effect achieved (or deliberately not, per output). | `output`, `state_hash_after` when state changed |
| `failed` | yes | Attempted and failed after acceptance. | `error` |
| `rejected` | yes | Refused before any effect; revision unchanged. | `error` |
| `cancelled` | yes | Cancelled; safe state attempted. | `cancellation` |
| `unknown` | interim (final only when nothing can reconcile it) | Outcome not observable in time (a deadline passed on a command that keeps running, a lost response, an endpoint restart). The execution's final receipt reconciles it (`x-vendor.reconciles`); after a restart it stays the outcome. | `error.mhs_code` `MHS.OUTCOME.UNKNOWN` or `MHS.OUTCOME.TIMEOUT` |

How the outcome of the native call becomes a receipt (the signals are defined in
[core.md](core.md) CORE-071):

| Native outcome | Receipt |
|---|---|
| a result | `completed` (strict mode validates `output` against the class output schema; a mismatch is `failed` `MHS.CAPABILITY.OUTPUT_INVALID`) |
| `DriverFailed(code, message, native_code)` | `failed` with that code and `native_code` |
| `Busy` | `rejected` `MHS.DEVICE.BUSY`, retryable, `retry_after_ms`; the revision does not move |
| `OutcomeUnknown` | `unknown` `MHS.OUTCOME.UNKNOWN` |
| `Cancelled`, `asyncio.CancelledError`, `concurrent.futures.CancelledError` | `cancelled` |
| any other exception | `failed` `MHS.ADAPTER.SHIM_FAILED`, message `driver raised <Type>`, `details.exception_type`; the native message is never forwarded |
| a failure of the endpoint's own post-call code | `failed` `MHS.INTERNAL.ERROR`, exception type only |

An input with no canonical JSON form (an integer beyond 2^53−1) never reaches the
bridge: it is the protocol error `MHS.CAPABILITY.INPUT_INVALID` with
`data.details.reason` `not_canonical_json`.

**OP-001.** Every command MUST be recorded as exactly one receipt per
`receipt_id`, and the receipt MUST be retrievable by `command_id` and
`receipt_id` for the retention period. At most one execution runs per `command_id`
and it has exactly one final receipt (`completed`, `failed` or `cancelled`); a
`rejected` receipt records a refusal, is not that outcome and does not reserve the
id ([core.md](core.md) CORE-091).

**OP-002.** A `rejected` receipt MUST NOT change state or revision and MUST be
retained as long as accepted receipts.

**OP-003.** Replaying a `command_id` with the same `input_digest` MUST return the
retained receipt with `replayed: true` and MUST NOT re-execute. A replay of a
non-terminal receipt MUST return the current state of the operation.

**OP-004.** Reusing a `command_id` with a different `input_digest` MUST be
rejected with `MHS.CONFLICT.COMMAND_ID_REUSE`, MUST NOT execute, and MUST NOT
overwrite the retained receipt.

**OP-005.** When `expected_revision` is supplied and differs from the current
revision, the endpoint MUST return a `rejected` receipt with
`MHS.CONFLICT.REVISION` and `data.current_revision`; no effect, no revision
advance. The idempotency store MUST NOT record that attempt as the command's
outcome.

**OP-006.** The idempotency scope is `(endpoint_id, device_id, command_id)`. The
store MUST survive session close and connection loss for at least
`hello.limits.receipt_retention_days`. With a `state_dir` it also survives an
endpoint restart: a completed id replays byte for byte, and a command that was in
flight when the process died gets an `unknown` receipt (`details.reason`
`endpoint_restarted`) instead of running again ([core.md](core.md) CORE-172);
`hello.limits.receipt_store` says which of the two applies.

### 10.3 Example

The receipt below is valid against [`receipt.schema.json`](../schema/receipt.schema.json); digests that
are `sha256:` followed by zeros are placeholders.

```json
{
  "receipt_id": "01J8ZQ3W1B7M2N4P6R8S0T2V4Z",
  "command_id": "01J8ZQ3V6Y7M2N4P6R8S0T2V4Y",
  "session_id": "mhs_s_01J8ZQ3V6Y",
  "endpoint_id": "mhs://localhost:7400",
  "device_id": "mhs://localhost:7400/lab/conveyor-workcell",
  "capability_id": "cap.world.step.v1",
  "resource_ids": ["world"],
  "input_digest": "sha256:0b57d3a0f13f8f4d6f0b6e2a8f5f9c7d2a4e6b8c0d1f3a5b7c9d1e3f5a7b9c1d",
  "status": "completed",
  "mode": "simulated",
  "principal": {"id": "agent:openai4s/session-7", "kind": "agent"},
  "accepted_at": "2026-10-20T07:46:58.900Z",
  "started_at": "2026-10-20T07:46:58.902Z",
  "ended_at": "2026-10-20T07:46:59.221Z",
  "state_revision_before": 76,
  "state_revision_after": 77,
  "state_hash_after": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "output": {"tick": 77, "state_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"},
  "effects": [
    {"kind": "simulation.advance", "summary": "simulated 1 ms tick", "reversible": false,
     "severity": "R0", "irreversible_reason": "simulated time cannot be un-spent, though restore can rewind"}
  ],
  "progress": {"ticks": 1, "percent": 100},
  "replayed": false,
  "seed": 0,
  "evidence": {"seq": 812, "prev_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000", "digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000"}
}
```

### 10.4 Revision rules

**OP-007.** The device revision MUST advance by exactly one for a command that
changed the device's state (its state hash differs before and after, or cannot be
computed); the receipt MUST report `state_revision_before` and
`state_revision_after` such that `after = before + 1`. A command that changes
multiple resources still advances the device revision once, and a command that
leaves the state unchanged, a `failed` or `cancelled` one included, does not
advance it ([core.md](core.md) CORE-095).

**OP-008.** Every read, subscription, `safety.status`, `evidence.*`,
`operations.get` and `session.open/close` MUST keep the revision, and so does every
`rejected` receipt. Other commands advance it only on a state change (OP-007).

**OP-009.** After a successful mutation, the endpoint MUST compute
`state_hash_after` over the device state *after* the mutation and MUST include it
in the receipt. A receipt with `status: "completed"` and no state change MUST set
`state_revision_after = state_revision_before` and MUST explain in `output`. A
state read that cannot be answered counts as a change (fail closed).

### 10.5 Deadlines and unknown outcomes

**OP-010.** The receipt-side view of PROTO-011 ([core.md](core.md) CORE-100): when a
command is not completed within `deadline_ms`, the endpoint answers the current
`running` receipt with `operation_id` for a `long_running` binding and otherwise an
`unknown` receipt `MHS.OUTCOME.TIMEOUT` (`retryable: false`), and the command keeps
running; nothing is cancelled by the deadline. Until the execution's final receipt
exists, `operations.get`, `operations.list` and a replay of the `command_id` report
the live `running` receipt. When the transport loses the response, the client MUST
observe state via `resource.read` before retrying, and the endpoint MUST be able to
answer `operations.get` for the command.

**OP-011.** A cancelled physical action MUST transition to the device's declared
`safe_state`; the receipt MUST record `status: "cancelled"`, `effects` observed,
and `cancellation.safe_state_achieved: true|false`. A cancelled action MUST still
advance the revision if it changed state.

**OP-012.** A command whose `deadline_ms` expires before it is dispatched (for
example during a slow interlock read) MUST be answered with a `rejected` receipt
`MHS.OUTCOME.TIMEOUT` (`details.reason` `deadline_exceeded_before_dispatch`,
`retryable: true`): nothing is dispatched and a permit it had consumed is given back.
A blocking method that is not a command and cannot answer within its deadline fails
with the JSON-RPC error `MHS.OUTCOME.TIMEOUT`, and one that cannot prove it had no
effect answers an `unknown` receipt.

**OP-013.** A lost response after an irreversible effect MUST surface as
`MHS.OUTCOME.UNKNOWN`; the receipt MUST be retrievable by `command_id`, and the
client MUST observe state before retrying ([00-architecture.md](00-architecture.md)
§3.4, informative).

**OP-014.** The endpoint MUST NOT report `completed` for an effect it did not
observe. "Command sent, response not read" is `unknown`, never `completed`.

---

## 11. Safety methods

These methods are specified in detail in [MHS-004](04-safety.md); the wire forms
are:

### 11.1 `mhs.safety.status`

Params: `session_id?`, `device_id?`, `deadline_ms`. Result: `risk_class`,
`estop{engaged, latching, kind, latency_ms}`, `interlocks[]` (`id`, `state`,
`description?`), `permits[{permit_id, capability_id, expires_at}]`,
`safe_state{description, achieved_by[]}`, `cumulative?`.

**SAFE-001.** `safety.status` MUST be callable without a session by an
authenticated principal and MUST NOT be gated by permits; an operator must be
able to see the interlock state before opening a session.

### 11.2 `mhs.safety.estop`

Params: `reason`, `device_id?`, `session_id?`, `deadline_ms?`. A session, a prior
`mhs.hello`, a valid `deadline_ms` and a ULID `command_id` are all optional
([core.md](core.md) CORE-076). Without `device_id` the stop covers the single device of
the session, the only device of the endpoint or, on an endpoint that serves several
devices, all of them. Result: the receipt ([core.md](core.md) CORE-093); `output` has
`estop`, `latched`, `latency_ms`, `latch_latency_ms`, `safe_state_achieved`, `safe_state`
and `cancelled_operations`. A stop of several devices answers with one receipt (the first
that is not `completed`, else the first) whose `x-vendor.estop.devices` lists the receipt of
every device. A request with a defective envelope (`jsonrpc` other than `"2.0"`, an `id`
that is not a string or an integer, `params` that are not an object) is served as well; its
answer is the error of the defect, with `error.data.details.estop_served` and the receipt.

**SAFE-002.** The endpoint MUST engage the e-stop within the declared
`latency_ms`. The receipt is `completed` with
`effects: [{kind: "safety.estop", …}]` only when the whole stop path succeeded, and
it MUST record whether the safe state was achieved; an unconfirmed stop is a
`failed` receipt `MHS.SAFETY.SAFE_STATE_UNREACHED`, never `completed` and never
`MHS.OUTCOME.TIMEOUT` ([core.md](core.md) CORE-074, CORE-077).

### 11.3 `mhs.safety.reset`

Params: `session_id`, `device_id`, `deadline_ms`. Result: the receipt; `output` has
`reset`, `estop`, `latched`, `cleared_interlocks[]` and `resumed` (always `false`), and
`reenable` when the device declares one ([core.md](core.md) CORE-086).

**SAFE-003.** `reset` MUST clear a latched e-stop only when every hard interlock
reads `closed`; otherwise it MUST return a `rejected` receipt with
`MHS.SAFETY.RESET_REFUSED` and the offending interlocks. The other refusals
(`not_latched`, `operation_running`, `stop_path_pending`, `estop_during_reset`,
`terminal_estop`), the failed receipts of a refusal after the bridge reset ran, and the
operator-only rule for hardware are in [core.md](core.md) CORE-080 to CORE-083 and
CORE-087. Reset MUST NOT start any motion and MUST NOT run a declared re-enable
(CORE-086).

### 11.4 `mhs.safety.permit`

Params: `session_id`, `capability_id`, `resource?`, `input_digest`, `ttl_s`,
`approvals[]`. Result: `permit_id`,
`scope{device_id, capability_id, resource?, input_digest, principal}`, `expires_at`,
`single_use: true`.

**SAFE-004.** A permit MUST be single-use by default, scoped to the exact
`input_digest`, and MUST expire. A permit presented with a different input, a
different principal, an expired TTL, or for a second time MUST be rejected with
`MHS.SAFETY.PERMIT_INVALID` ([MHS-004](04-safety.md) §6).

---

## 12. Subscriptions and notifications

Covered in §8. Binding-specific delivery rules are in
[MHS-008](08-transports.md): HTTP/SSE uses the event stream; WebSocket multiplexes
by `subscription_id`; stdio interleaves notifications with responses on the same
line-delimited channel. In all bindings, responses MUST NOT be blocked behind
notifications; a client MUST be able to correlate by `id`.

**EVT-010.** Over stdio, an endpoint MUST write at most one JSON message per line
and MUST NOT interleave bytes of two messages. Over SSE, each event's `data:` MUST
contain exactly one JSON message.

---

## 13. Receipt class mapping

Some protocol methods produce receipts but are not invocations of a catalogue
capability. Their receipts MUST carry a **protocol-internal** `capability_id` from
the table below. (`mhs.resource.write` is not in the table: it is a command of the
catalogue class `cap.device.configure.v1`, CORE-022.) Internal classes are not published in the capability catalogue,
MUST NOT be bound in device manifests, MUST NOT be granted in sessions, and MUST
NOT be requested via `mhs.command`.

| Method | `capability_id` in receipt |
|---|---|
| `mhs.restore` | `cap.internal.restore.v1` |
| `mhs.safety.estop` | `cap.internal.safety_estop.v1` |
| `mhs.safety.reset` | `cap.internal.safety_reset.v1` |
| `mhs.operations.cancel` | `cap.internal.operation_cancel.v1` |
| `mhs.composition.run` | `cap.internal.composition_run.v1`; child receipts keep their own class ids |

**PROTO-038.** The `cap.internal` namespace is reserved by this document. The
identifiers match the `capabilityId` pattern in
[`defs.schema.json`](../schema/defs.schema.json) and are the only way to satisfy
[`receipt.schema.json`](../schema/receipt.schema.json)'s required
`capability_id` for methods that are not capability invocations.

---

## 14. Evidence methods

### 14.1 `mhs.evidence.export`

Params: `session_id?`, `device_id?`, `since_receipt?` (receipt ULID), 
`include_telemetry?`. Result: evidence bundle.

```json
{
  "bundle_version": "1.0.0",
  "endpoint_info": {
    "endpoint_id": "mhs://localhost:7400",
    "mhs_version": "1.0",
    "server": {"name": "mhs-reference", "version": "1.0.0"},
    "genesis_digest": "sha256:…"
  },
  "created_at": "2026-10-20T07:50:00Z",
  "receipts": [ {"…": "receipt objects, in evidence order"} ],
  "head_digest": "sha256:…",
  "telemetry": [ {"…": "optional artifact references, never raw streams"} ],
  "truncation": null,
  "signature": null
}
```

**EVID-001.** `receipts` MUST be ordered by `evidence.seq`, contiguous from the
requested start to the head, and MUST be accompanied by the endpoint's genesis
record metadata. `head_digest` MUST equal the last receipt's `evidence.digest`.

**EVID-002.** `export` MUST NOT require a session when the caller is an
authenticated principal with evidence-read permission; device state secrets MUST
be redacted according to the adapter's `redaction` rules.

### 14.2 `mhs.evidence.verify`

Params: `bundle` or `bundle_ref`. Result: `valid`, `checked`, `head_digest`,
`errors[]` where each error has `seq`, `mhs_code`, `detail`.

**EVID-003.** `verify` MUST recompute the chain offline
(`digest_i = sha256(JCS(receipt_i \ {evidence}) || digest_{i-1})`) and MUST return
`valid: false` with `MHS.EVIDENCE.CHAIN_BROKEN` when a link, a sequence number or
a receipt body does not match.

**EVID-004.** `verify` MUST validate every receipt against
[`receipt.schema.json`](../schema/receipt.schema.json) and MUST report schema
failures separately from chain failures.

### 14.3 `mhs.conformance.report`

Params: `profile?`, `level?`. Result: a conformance report
([`conformance-report.schema.json`](../schema/conformance-report.schema.json)).

An endpoint returns the last report stored with `record_conformance_report` (its
digest MUST recompute and its `subject.id` MUST be the endpoint or one of its
devices), verbatim. When none was stored it returns a schema-valid **not-run**
report: every suite test `skip` with detail `not_run` (the verdict enum has no
`not_run`), `level_achieved` `CL0`, `coverage.passed` 0 and the disclaimers
`not_certified` and `self_issued`. An endpoint MUST NOT answer with a level it has not
run ([core.md](core.md) CORE-190).

---

## 15. Composition and registry methods

### 15.1 `mhs.composition.run` (reserved)

**Reserved.** No 0.9 endpoint implements this method; the reference endpoint
answers `MHS.PROTOCOL.METHOD_NOT_FOUND`. The method, its internal class and the
requirements COMP-001 to COMP-004 are kept so that a later profile can fill them
without renumbering ([profiles.md](profiles.md) §1). Multi-step procedures in 0.9 are
code files ([core.md](core.md) §10.3).

Params: `session_id`, `composition_ref` (content-addressed reference),
`inputs` (object), `command_id`, `deadline_ms`, `permit_id?`.

Result: receipt for `cap.internal.composition_run.v1` whose `output` contains
`child_receipts[]` in execution order and `composition_digest`.

**COMP-001.** A composition MUST be a deterministic, versioned document; the
endpoint MUST record `composition_digest` in the receipt and MUST execute exactly
the children declared. Children inherit the parent session's grants and MUST NOT
exceed them.

**COMP-002.** A failed child MUST stop the composition unless the composition
declares `continue_on_failure: true`; the parent receipt MUST be `failed` with
the failed child's receipt embedded, never `completed`.

**COMP-003.** Cancelling the parent MUST cancel every running child and MUST
respect each child's safe state.

**COMP-004.** A composition MUST NOT be run in `replay` mode; replay serves the
recorded parent and child receipts instead.

### 15.2 `mhs.registry.search`

Params: `query{capability?, tags?, mode?, vendor?, text?, limit?}`. Result:
`registry_id`, `took_ms`, `results[]` where each result is a registry record
summary with `trust` and `links`.

**PROTO-039.** `mhs.registry.search` is not an endpoint method. The registry is a
separate service ([MHS-007](07-registry.md), reference: `mhs.registry`) and an
endpoint answers `MHS.PROTOCOL.METHOD_NOT_FOUND`. A proxy that does query a
configured registry MUST NOT return devices as controllable endpoints before
authentication ([MHS-007](07-registry.md) §9).

---

## 16. Errors and limits

### 16.1 Error object

Every JSON-RPC error MUST be:

```json
{"jsonrpc":"2.0","id":"…","error":{
  "code":-32010,
  "message":"Interlock open: safety door",
  "data":{
    "mhs_code":"MHS.SAFETY.INTERLOCK_OPEN",
    "retryable":false,
    "current_revision":41,
    "interlocks":[{"id":"door_closed","state":"open"}],
    "remediation":"Close the safety door and call mhs.safety.reset."
  }}}
```

**PROTO-040.** `data.mhs_code` MUST be a code from [MHS-B](appendix-b-errors.md);
`error.code` is the coarse JSON-RPC structural code and clients MUST NOT branch on
`error.message` ([00-architecture.md](00-architecture.md) §5.1, informative). Receipt errors use the same
object as `receipt.error`.

**PROTO-041.** `data.retryable` MUST be present. An error is retryable only if
retrying the identical request cannot duplicate a physical effect; `unknown`
outcomes are never blindly retryable.

**PROTO-042.** An endpoint MUST NOT include secrets, credentials, raw device
paths outside the workspace, or personal data in `error.data`; it MUST apply the
adapter's `redaction` rules.

### 16.2 Limits

| Limit | Default | Enforcement |
|---|---|---|
| Request size | 1 MiB | `MHS.LIMIT.PAYLOAD_TOO_LARGE`, request rejected unread beyond the limit. |
| Batch size | 64 | `MHS.PROTOCOL.BATCH_TOO_LARGE`. |
| Subscriptions per session | 64 | `MHS.LIMIT.SUBSCRIPTION_LIMIT`. |
| Requests per second per principal | declared in `hello.limits.max_rate_per_s` | `MHS.LIMIT.RATE_EXCEEDED`, with `data.details.retry_after_ms`. |
| Concurrent operations per session | declared | `MHS.LIMIT.OPERATION_LIMIT`. |
| Evidence export size | declared | `MHS.EVIDENCE.EXPORT_TOO_LARGE`; client MUST page by `since_receipt`. |

**PROTO-043.** Limits MUST be advertised in `hello.limits`; an endpoint MUST NOT
return a limit error for a value it did not advertise.

---

## 17. Requirements traceability

| Area | Requirements in this document |
|---|---|
| `PROTO` | PROTO-001 … PROTO-043 |
| `SESS` | SESS-001 … SESS-006 |
| `OP` | OP-001 … OP-014 |
| `EVT` | EVT-001 … EVT-010 |
| `EVID` | EVID-001 … EVID-004 (method level; chain construction in [MHS-004](04-safety.md) §8) |
| `COMP` | COMP-001 … COMP-004 |
| `SAFE` | SAFE-001 … SAFE-004 (wire forms; semantics in [MHS-004](04-safety.md)) |

The conformance suite MUST check each requirement that is runtime-observable;
[MHS-001](01-conformance.md) §4.3 lists the mandatory negative set. Error codes
referenced here are defined in [MHS-B](appendix-b-errors.md).
