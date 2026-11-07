# MHS-008 — Transport Bindings and the MCP Projection

| Field | Value |
|---|---|
| Document | MHS-008 (normative) |
| Status | OpenMHS 0.9 development draft (wire revision 1) |
| Editor | The OpenMHS Authors |
| Layer | core (stdio, HTTP, MCP projection, CLI, code API); the WebSocket binding and the SSE delivery rules belong to the Events profile ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §10 and §14; overview in [00-architecture.md](00-architecture.md) §5.4 (informative) |
| Data contracts | [`endpoint-descriptor.schema.json`](../schema/endpoint-descriptor.schema.json), [`../sdk/INTERFACE.md`](../sdk/INTERFACE.md) |

MHS/1.0 is JSON-RPC 2.0 transported over six bindings: T1 stdio (mandatory), T2
HTTP/SSE (mandatory), T3 WebSocket (optional, not implemented by the reference
SDK), T4 MCP projection (mandatory for the host profile), T5 CLI (recommended) and
T6 code API (recommended). The messages are identical across bindings; only
framing, authentication, discovery and delivery semantics differ. This document
details [core.md](core.md) §10 and §14 and MUST NOT change any method semantics in
[MHS-002](02-wire-protocol.md). The three control surfaces (T4 MCP, T5 CLI, T6 code
files) are thin clients: they hold only the authority of the session they open.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Binding model

**TPT-001.** Every binding MUST carry the same JSON-RPC request, response and
`mhs.event` notification payloads defined in [MHS-002](02-wire-protocol.md). A
binding MUST NOT add, remove or rename method parameters or result fields.

**TPT-002.** An endpoint MUST advertise its bindings truthfully:

- in `mhs.hello` features (`stdio`, `http`, `sse`, `ws`, `mcp`);
- in the endpoint descriptor `transports` object
  ([`endpoint-descriptor.schema.json`](../schema/endpoint-descriptor.schema.json));
- in `mhs.devices.get` only indirectly, through the endpoint.

A client that connects over a transport that is not advertised MUST be able to
distinguish "not implemented" from "misconfigured": the endpoint MUST answer
`hello` on any transport it accepts, or refuse the connection at the transport
level.

**TPT-003.** Method coverage is binding-independent except for T4/T5/T6
projections, which expose subsets (§9, §10, §11). The RPC methods of
[MHS-002](02-wire-protocol.md) §3 are available over T1, T2 and T3 without
restriction.

| Capability | T1 stdio | T2 HTTP/SSE | T3 WebSocket | T4 MCP | T5 CLI | T6 code API |
|---|---|---|---|---|---|---|
| All implemented RPC methods (24 in the reference SDK) | ✓ | ✓ | ✓ | subset | subset | ✓ |
| Server-initiated events | ✓ | ✓ (SSE) | ✓ | progress/resources | — | ✓ |
| Batch | ✓ | ✓ | ✓ | — | — | ✓ |
| Authentication | process identity | bearer/mTLS | bearer/mTLS or query | host-managed | token/env | as T1/T2 |
| Discovery descriptor | optional | REQUIRED | optional | via shim | via config | via config |

### 1.1 Discovery

An HTTP endpoint serves `/.well-known/mhs.json` (TPT-010). A client lists endpoints
from the environment variable `MHS_ENDPOINTS` (comma-separated `http://host:port`,
`mhs://host:port` with the default port 7400, and `stdio:<command>` entries whose
words are separated by spaces and which are listed but never launched by discovery)
and from the endpoints file `~/.mhs/endpoints.json` (or `$MHS_ENDPOINTS_FILE` or
`--file`), validated against
[`endpoints.schema.json`](../schema/endpoints.schema.json): a relative `token_file` or
`cwd` is resolved against the file's directory, and an invalid file is a usage error.
Every HTTP entry is probed with `GET /.well-known/mhs.json`. Discovered does not mean
trusted: discovery authenticates nothing, every entry is reported `trusted: false`,
and a discovered endpoint receives only the `token_file` of its own entry
([core.md](core.md) CORE-120 to CORE-122).

---

## 2. T1 — stdio (MUST)

### 2.1 Framing

**TPT-004.** T1 is newline-delimited JSON (NDJSON): exactly one UTF-8 JSON-RPC
message per line, `\n` terminated. Messages MUST NOT contain a BOM, MUST NOT be
pretty-printed across lines, and MUST NOT contain literal newlines inside a
string (JSON escapes them). An empty line MUST be ignored; a malformed line MUST
produce a parse error and MUST NOT desynchronise the stream.

**TPT-005.** stdout is the protocol channel. Logs, progress text, warnings and
stack traces MUST go to stderr only. Writing a log line to stdout is a conformance
failure because it corrupts the protocol stream
([MHS-006](06-adapters.md) ADPT-032).

**TPT-006.** The maximum line length MUST be at least 1 MiB and MUST be enforced
by both sides; a sender exceeding it MUST fail with
`MHS.LIMIT.PAYLOAD_TOO_LARGE` rather than truncate.

### 2.2 Lifecycle

**TPT-007.** A stdio endpoint is launched by its host as a child process
(`lifecycle.start.command`, [MHS-006](06-adapters.md) §6). It MUST serve `hello`
within `lifecycle.ready.deadline_ms`; the host MUST treat a missed readiness
deadline as a startup failure and terminate the process group.

**TPT-008.** When stdin reaches EOF, the endpoint MUST stop accepting commands,
cancel running operations to their safe state, close its sessions, and exit with
status 0 within the declared stop grace. A non-zero exit MUST be treated by the
host as a crash and MUST be surfaced to the operator; it MUST NOT be retried
silently while a device may be actuated.

**TPT-009.** The host MUST send SIGTERM and wait `grace_s` before force-killing;
the endpoint MUST NOT ignore SIGTERM. Where the endpoint controls a device with no
stop path (for example a remote HTTP instrument), it MUST declare the limitation
in `safety.notes`.

---

## 3. T2 — HTTP and SSE (MUST)

### 3.1 Endpoints

**TPT-010.** An HTTP endpoint MUST serve:

| Path | Method | Purpose |
|---|---|---|
| `/mhs/v1/rpc` | POST | JSON-RPC request or batch (`application/json`). |
| `/mhs/v1/events` | GET | Server-Sent Events for subscriptions. |
| `/.well-known/mhs.json` | GET | Endpoint descriptor. |
| `/mhs/v1/schema/{ref}` | GET | Schema document addressed by `mhs.schema.get`. |

Additional paths MAY exist, but these four MUST be stable and MUST NOT require
authentication for the well-known descriptor beyond what the deployment declares
in it. Every route first checks the `Host` header, which MUST name `localhost`,
`127.0.0.1`, `[::1]`, the bound address or a configured allowed host
(case-insensitive, port ignored, a missing header refused), and an `Origin`
header, when present, MUST be the endpoint's own loopback origin or a configured
allowed origin (`null` is refused); otherwise the answer is 403
`MHS.AUTH.FORBIDDEN` and the connection is closed ([core.md](core.md) CORE-180).

**TPT-011.** `POST /mhs/v1/rpc` MUST require `Content-Type: application/json`
(parameters allowed); a missing, empty, form or text type MUST be rejected with HTTP
415 and a JSON body containing `data.mhs_code = "MHS.PROTOCOL.INVALID_REQUEST"`. A
GET to the RPC path MUST NOT execute a method: it MUST return 405. Every early
refusal closes the connection so that an unread body is never parsed as the next
request, and every connection has a socket timeout (default 30 s).

**TPT-012.** HTTP status codes are transport-level; a well-formed JSON-RPC request
that returns a JSON-RPC error still returns HTTP 200 with the error object. HTTP
4xx/5xx are reserved for: malformed HTTP, unsupported content type (415), body too
large (413), authentication failure (401/403), rate limiting (429), and server
failure before a JSON-RPC response exists (5xx). A client MUST surface both layers.

**TPT-013.** TLS is REQUIRED for every non-loopback HTTP endpoint; plain HTTP on a
non-loopback address MUST be refused by conformant clients. mTLS is RECOMMENDED
for device networks; bearer tokens are the minimum.

**TPT-014.** Authentication failures MUST return `401` `MHS.AUTH.UNAUTHENTICATED`
with `WWW-Authenticate: Bearer` (or the negotiated scheme). When tokens are
configured every route except `/.well-known/mhs.json` needs one, the e-stop
included, and the descriptor advertises `auth: ["bearer"]`. Tokens MUST NOT be
echoed in errors, logs, SSE comments or receipts. A token presented for one
principal MUST NOT be usable as another ([MHS-004](04-safety.md) SAFE-060;
[core.md](core.md) CORE-150, CORE-181). A non-loopback bind without tokens is
refused at start (`MHS.AUTH.TRANSPORT_INSECURE`, CORE-152).

**TPT-015.** Batch requests are accepted on `/mhs/v1/rpc`; the response is a JSON
array of response objects as specified in [MHS-002](02-wire-protocol.md) §1.3.
An empty array is a 400 with `MHS.PROTOCOL.INVALID_REQUEST`.

### 3.2 SSE stream

**TPT-016.** `GET /mhs/v1/events` (with `Accept: text/event-stream`) MUST deliver
subscription events as SSE events with:

```text
id: <subscription_id>:<seq>
event: mhs.event
data: {"jsonrpc":"2.0","method":"mhs.event","params":{…}}
```

`id` MUST be unique per delivered event and MUST encode the subscription and the
`seq` so that resumption is possible. The SSE `retry:` field SHOULD be sent on
connect (default 3000 ms). Comment heartbeats (`: keepalive`) MAY be sent every
15–30 s; clients MUST ignore comments.

**TPT-017.** A subscription over SSE MUST be opened by `mhs.subscribe` on
`/mhs/v1/rpc` first; the SSE connection MUST then name its session with
`?session_id=` (a missing id is 400; an unknown or expired session, or a
token-bound session of another principal, is 403) and receives only that session's
subscriptions; an optional `?subscription_id=` MUST belong to the session (else
404). An SSE connection MUST NOT deliver events for a subscription that belongs to
a different session or principal. A principal MAY hold at most 4 concurrent
streams; the fifth is refused with 429 `MHS.LIMIT.CONNECTION_LIMIT`. The stream
ends when the client disconnects, the session ends or the endpoint shuts down
([core.md](core.md) CORE-184).

**TPT-018.** `Last-Event-ID` resumption: on reconnect, the client MAY send
`Last-Event-ID`; the endpoint MUST resume at `seq+1` when it can, and MUST send a
control gap event when the requested `seq` is no longer buffered
([MHS-002](02-wire-protocol.md) EVT-008). Resumption is best-effort; absence of
resumption MUST NOT be treated as a gap by the client if it re-reads state.

**TPT-019.** SSE responses MUST NOT be buffered by intermediaries in a way that
delays events; endpoints/proxies SHOULD disable response buffering and compression
for this route. A slow client MUST receive backpressure rather than cause
unbounded buffering ([MHS-002](02-wire-protocol.md) EVT-006).

### 3.3 Limits

**TPT-020.** The endpoint MUST enforce and advertise `max_request_bytes`
(default 1 MiB), `max_batch` (default 64), a request rate per principal and a
concurrent-connection limit. Requests over the limits MUST return the
corresponding `MHS.LIMIT.*`/`MHS.PROTOCOL.*` code with `Retry-After` where
applicable. Latency targets for `hello`, `resource.read` and `safety.status` are in
[MHS-001](01-conformance.md) §6.6; exceeding them is reported as `warn`, not as a
functional failure.

---

## 4. T3 — WebSocket (MAY)

**TPT-021.** The WebSocket binding is `GET /mhs/v1/ws` upgraded to WebSocket with
subprotocol `mhs.v1`. Frames MUST contain one JSON-RPC message each; binary frames
are invalid. Notifications and responses are multiplexed on the same connection
and correlated by `id`/`subscription_id`.

**TPT-022.** The endpoint MUST implement ping/pong keepalive and MUST close with a
defined close code on protocol violation (`1002`), authentication failure
(`1008`), policy violation or shutdown (`1001`). A client MUST treat an unexpected
close as a transport failure and follow §7.

**TPT-023.** Authentication for WebSocket MUST use the same bearer/mTLS scheme as
T2. Tokens MUST NOT be put in URLs except as a one-time ticket; long-lived tokens
in query strings are prohibited.

**TPT-024.** WebSocket subscriptions use the same `mhs.subscribe` methods; the
endpoint MUST be able to multiplex several subscriptions on one connection and
MUST apply the same sequence and gap rules as SSE.

---

## 5. T4 — MCP projection (MUST for host profile)

An MHS endpoint can be projected as an MCP server so that any MCP-speaking agent
harness can drive hardware without an MHS-specific client. The projection is a
**shim process** (for example `mhs serve --mcp`, reference: `mhs.mcp`) that speaks
MCP on stdio and MHS to the endpoint. It holds the sessions and the host policy
(`enabled`, `allow_hardware`, `operator_tools`, `allow_external_sessions`:
[core.md](core.md) CORE-130); the model only sees tools.

### 5.1 Tool naming

**TPT-030.** Each bound capability MUST be exposed as an MCP tool named:

```text
mhs__<device_slug>__<capability_slug>
```

Slug rules:

1. `device_slug` = the last two non-empty segments of the device URI path
   (or the last segment plus a 4-character digest if only one), lowercased, with
   every character outside `[a-z0-9]` replaced by `_`, collapsed runs of `_`,
   trimmed, truncated to 24 characters.
2. `capability_slug` = the capability id with the leading `cap.`/`x-cap.` and
   the trailing `.v<major>` removed, dots replaced by `_`, lowercased, truncated
   to 20 characters.
3. If either slug was truncated, append `_` plus the first 6 hex characters of
   the JCS digest of the full identifier.
4. The total tool name MUST be at most 63 characters and match
   `^[A-Za-z_][A-Za-z0-9_-]{0,63}$`; if it is longer, truncate both slugs to 12
   characters each and append the 6-character digest.

Example: device `mhs://localhost:7400/lab/conveyor-workcell`, capability
`cap.world.step.v1` → `mhs__lab_conveyor_workcell__world_step`.

**TPT-031.** Protocol-internal classes (`cap.internal.*`) MUST NOT be projected,
and protocol methods MUST NOT be projected as tools except where this chapter
specifies a projection. The tool surface is the capability surface plus
discovery/safety/evidence tools (§5.5).

**TPT-032.** Tool names MUST be stable across endpoint restarts and sessions for
the same device/capability tuple; a slug collision between two tuples MUST cause
the projection to start fail-closed rather than silently rename one.

### 5.2 Tool schema

**TPT-033.** The tool `inputSchema` MUST be the capability's binding input schema
([MHS-003](03-capability-registry.md) §5), projected without loss: required fields
stay required, units keep `x-mhs-unit`, enums keep values, and closed objects stay
closed. The projection MAY add OPTIONAL *control* properties that select or bound
the call rather than describe the physical action: `session_id` (string),
`command_id` (string, the idempotency key), `expected_revision` (integer),
`permit_id` (string) and `deadline_ms` (integer). Control properties MUST be
optional, MUST be documented as such, and MUST NOT be forwarded into the
capability input document — the projection strips them before schema validation
and maps `command_id` to the MHS `command_id` of the invocation. No other added
properties are permitted and none may be required. The control fields apply to
the call only; the endpoint, not the projection, enforces limits, interlocks,
permits and the latch ([core.md](core.md) CORE-131).

**TPT-034.** Each tool MUST carry a description that contains, at minimum: the
capability summary, the mode(s), the risk class, the determinism claim (for
simulated devices), the units, and the fidelity gaps (for simulated/hybrid
devices). The description MUST NOT be a paraphrase of the native API call; it
describes physical meaning ([MHS-003](03-capability-registry.md) CAP-009).

Example description fragment:

```text
Advance the simulated world by a bounded number of fixed timesteps. Mode: simulated.
Risk: R0. Determinism: exact. Units: ticks (count). Fidelity gaps: no fluid dynamics;
rigid contacts only; no camera noise model. Simulation only — not hardware.
```

**TPT-035.** The projection MUST annotate tool metadata with the risk class and
the device mode in a machine-readable extension (for example
`"x-mhs": {"risk_class": "R1", "mode": "simulated", "capability_id": "cap.…"}`) so
hosts can gate tools without parsing prose.

### 5.3 `tools/call` mapping

**TPT-036.** `tools/call` MUST map to exactly one `mhs.command`:

- `name` selects the device/capability/resource tuple;
- `arguments` minus `session_id` are the capability `input`, validated against
  the capability schema before the MHS call;
- the projection MUST generate a fresh ULID `command_id` per MCP request unless
  the MCP request carries a retry token (`_meta.retryToken`) or a `command_id` that
  is not a ULID, in which case the `command_id` is the deterministic ULID formed
  from the first 16 bytes of `sha256(tool_name + "\n" + token)`, so that the same
  token on the same tool replays the first receipt and the same token with another
  input is refused by the endpoint (`COMMAND_ID_REUSE`). The mapping is scoped by
  tool name only, so a token reused in another conversation replays the earlier
  receipt (it never acts twice): callers use a fresh token for every new intent;
- the projection MUST open (or reuse) a least-privilege session of the principal
  `{kind: "agent", id: "agent:mcp/<clientInfo.name>"}`: one session per
  (device, capability) for commands and one per device for reads, with a TTL of
  3600 s. It MUST send a heartbeat before a call when less than a third of the TTL
  is left and open a new session after `MHS.SESSION.EXPIRED`, `UNKNOWN` or `CLOSED`;
  reads are retried once on the new session and commands never are.

**TPT-037.** The MCP result MUST be:

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
{
  "content": [{"type": "text", "text": "<complete receipt JSON, plus a one-line human summary>"}],
  "structuredContent": {"receipt": {…}, "mhs_error": null},
  "isError": false
}
```

The first text block MUST contain the complete receipt (status, revisions, state hash,
effects, error) — not a summary that drops fields — because several MCP hosts
(including the OpenAI4S MCP client) consume
only text content and ignore `structuredContent` and notifications. A text-only host
must still be able to tell `rejected` from `completed` and to read the `mhs_code`.

**TPT-038.** `isError` MUST be true only when no MHS receipt exists — transport,
protocol, authentication, policy or session-level failures, or `arguments` that do
not match the input schema (the text is `MHS.CAPABILITY.INPUT_INVALID: <field
reasons>` and nothing is sent). A `rejected`, `failed`, `cancelled`, `unknown` or
`running` **receipt** MUST be returned as a successful tool call (`isError: false`)
with the receipt in `structuredContent`, because a physical rejection is an
outcome, not a tool malfunction ([`../sdk/INTERFACE.md`](../sdk/INTERFACE.md)). A
value outside an enforced limit is sent to the endpoint and answered by a
`rejected` receipt `MHS.SAFETY.ENVELOPE_VIOLATION`, which stays in the evidence; the
projection describes limits but does not enforce them. A receipt with an operation
id also gets `structuredContent.operation` (`operation_id`, `status`, and
`long_running`, `deadline_ms`, `max_duration_ms`, `unknown_receipt_id` when stated).

**TPT-039.** When `isError` is true, `structuredContent` MUST contain
`mhs_error` with the `data` object from the MHS JSON-RPC error (including
`mhs_code`, `retryable`, `remediation`) and the human text MUST start with the
`mhs_code`. The projection MUST NOT invent MCP error codes; a generic MCP error
MAY carry the MHS error in `data`.

### 5.4 Progress and cancellation

**TPT-040.** When the MCP request carries `_meta.progressToken`, the projection
MUST forward MHS progress (`mhs.event` on `progress`, or `operations.get`
polling) as MCP `notifications/progress` with `progressToken`, `progress`,
`total` (when known) and `message`. The projection MUST NOT emit progress for
operations the caller did not request progress for.

**TPT-041.** MCP `notifications/cancelled` for an in-flight `tools/call` MUST map
to `mhs.operations.cancel` for the operation behind that call, and the call MUST
return the cancellation receipt (with `safe_state_achieved`), not a generic
cancelled error. If the projection has not yet received an `operation_id`, it MUST
return the accepted receipt and record the cancellation request for that
`command_id`. `mhs__estop`, `ping` and `notifications/cancelled` are served on a
priority path and are answered while a `tools/call` is still in flight on the same
connection; every other request is served in order ([core.md](core.md) CORE-079,
CORE-132).

**TPT-042.** The projection MUST honour MHS `deadline_ms` from the MCP request
timeout when one is available, and MUST otherwise use the declared default. It
MUST NOT allow an MCP call to hang past the MHS deadline.

### 5.5 Resources and discovery

**TPT-043.** The projection SHOULD expose MCP resources with `mhs://` URIs:

| URI | Content |
|---|---|
| `mhs://<endpoint>/devices` | list of device summaries (JSON). |
| `mhs://<endpoint>/devices/<device-path>` | device manifest. |
| `mhs://<endpoint>/devices/<device-path>/resources/<resource_id>` | current resource state. |

`resources/list` MUST paginate with MCP cursors; `resources/read` MUST map to
`mhs.devices.get`/`mhs.resource.read` and MUST return the same JSON. Resources are
read-only; mutations stay tools.

**TPT-044.** Besides the capability tools, the projection exposes the following
fixed tools. They MUST never bypass the envelope. This is the one table of the
projection (reference: `mhs.mcp`, pinned by `MHS/sdk/tests/surfaces/test_mcp_tools.py`):

| Tool | What it does | Listed |
|---|---|---|
| `mhs__<device>__<capability>` | one `mhs.command`; returns the receipt | per binding |
| `mhs__devices` | compact list: id, name, mode, risk class, resources, tool names | always |
| `mhs__inspect` | one device's manifest with its reference file and `x-mhs-effective-limits` | always |
| `mhs__read` | one resource's state (`device_id` optional when the resource id is unique) | always |
| `mhs__safety` | risk class, e-stop latch, interlocks, permits, safe state | always |
| `mhs__operations` | list this connector's operations; `operation_id` (and `wait_ms` up to 60000) reads one; `cancel_operation_id` cancels one | always |
| `mhs__evidence` | `count`, `head_digest`, `valid`, `verify`, the last `last_n` receipts (default 10, at most 50) or those of one `command_id`, and the `uri` of the full bundle; the accepted but unlisted argument `include_bundle: true` also returns the bundle, for hosts whose transport has only `tools/call` | always |
| `mhs__estop` | latch the e-stop of one device; never waits for a session or an approval | always |
| `mhs__reset` | operator tool: reset the latch | only with `operator_tools` |
| `mhs__permit` | operator tool: issue a permit bound to the exact input | only with `operator_tools` |

Without `operator_tools`, `mhs__reset` and `mhs__permit` are not listed and refuse
`MHS.AUTH.FORBIDDEN` (`policy` `operator_tools=false`): resetting an e-stop and
approving a permit are human decisions ([core.md](core.md) CORE-130).

**TPT-045.** MCP `initialize` MUST negotiate an MCP protocol version the shim
supports (the reference shim answers the requested version when it is one of
`2024-11-05`, `2025-03-26`, `2025-06-18` and `2025-11-25`, otherwise the latest,
`2025-11-25`) and advertise `capabilities.tools`, `capabilities.resources` and, when
implemented, `capabilities.logging`; `serverInfo.name` MUST identify the shim and
endpoint (`mhs-mcp:<endpoint id>`). The shim MUST handle
`notifications/initialized`, `ping`, and unknown optional methods by returning
the MCP method-not-found error.

### 5.6 Security and limits

**TPT-046.** The MCP projection is an authority-bearing shim: it holds the MHS
principal and session. It MUST run locally on behalf of the host, MUST NOT expose
its MCP port to untrusted networks without authentication, and MUST restrict its
tool set to the capabilities the deployment grants (a read-only projection MUST
expose only read/invoke-read classes and evidence tools).

**TPT-047.** The projection MUST enforce MCP frame limits
(`MAX_FRAME_BYTES` defaults to 4 MiB in common MCP clients) and MUST not return
unbounded receipts; large artifacts MUST be returned as `mhs+artifact://` URIs.

**TPT-048.** The projection MUST NOT trust the model's `session_id` to elevate
scope: a `session_id` argument selects only among sessions the projection itself
opened for this connection, and MUST be rejected with `MHS.SESSION.UNKNOWN`
otherwise, unless the operator has set `allow_external_sessions` in the host
policy. The projection's own principal is an `agent`; it never accepts a
`principal` from the model.

---

## 6. T5 — CLI (SHOULD)

**TPT-050.** The `mhs` CLI (`python3 -m mhs`, `mhs`, `openmhs`) MUST provide these
commands, which are thin clients of an endpoint:

| Command | What it does |
|---|---|
| `serve <target>` | serve a driver directory, an `mhs-adapter.json` or a reference fixture; always in strict mode, fake backend by default; `--stdio`, `--port`, `--mcp`, `--backend`, `--allow-hardware`, `--arm`, `--state-dir`, `--site-limits`, `--token-file`, `--operator-token-file` |
| `driver check\|reference\|new\|export\|catalog` | the driver package tools, the same as `python3 -m mhs.driver` |
| `validate <dir or file>` | a quick static check of a driver directory, or of a JSON document against its schema |
| `devices`, `hello` | one line per device, and the negotiation result |
| `describe` (alias `inspect`) | per device: mode, risk, trust, e-stop, safe state, interlocks, verbs, effective limits, fidelity gaps and facts |
| `read <resource>`, `write <resource> --patch JSON`, `call -c <capability> -i JSON` | the three primitives; `write` and `call` print the receipt |
| `session` | open a session that outlives the command |
| `estop [REASON]` | engage the e-stop; no session and no mode; every device unless `--device` |
| `status` | e-stop latch and interlocks (`safety` is the deprecated spelling of `status`, `estop` and `reset`) |
| `reset --operator-token-file FILE` | release a latched e-stop; an operator at an interactive terminal only |
| `evidence [--verify] [--ledger FILE]` | export and verify the evidence bundle, and check a code-file ledger against it |
| `run script.py [args]` | run a code file and write its ledger ([core.md](core.md) §10.3) |
| `discover` | list endpoints from `MHS_ENDPOINTS` and the endpoints file and probe them (§1.1) |
| `conform <dir>` / `conform -e URL` | run the conformance suite and print the failing and the capping test ids |
| `registry`, `version` | query a local registry index; print the SDK, specification and protocol versions |

`describe` MUST print the manifest summary, mode, risk class, fidelity gaps and trust
level. `reset` needs the operator's token file and a person at an interactive
terminal; with stdin not a terminal it sends nothing and exits 4 ([core.md](core.md)
CORE-083). `conform` runs a driver directory in process on its fake backend, or an
endpoint (`-e`, `--command`, `--reference`); on hardware or hybrid devices actuating
tests need the operator's `--allow-actuation`.

**TPT-051.** Every command MUST support `--json` returning machine-readable
output; the JSON shape MUST be stable within a MAJOR version and documented in
`MHS/sdk/README.md`. Human output MUST NOT be parsed by scripts; the `--json` flag
is the contract.

**TPT-052.** Exit codes MUST be one table for every command: `0` success (a
`completed` receipt, or `accepted`/`running` work); `1` the command ran but the
receipt is `rejected`, `failed`, `cancelled` or `unknown`, or the endpoint answered
another error (`MHS.DEVICE.UNKNOWN`, an invalid document, a strict-mode refusal);
`2` usage error (bad flags, `--input` that is not a JSON object, a missing file, an
unsupported endpoint form); `3` transport error (nothing was sent:
`MHS.TRANSPORT.UNAVAILABLE`; or the response was lost: `MHS.OUTCOME.TIMEOUT` and
`MHS.OUTCOME.UNKNOWN`, where the command may have run); `4` authentication or
authorisation (`MHS.AUTH.*`, a `reset` without an interactive operator, a hardware
backend without `--allow-hardware`); `5` `conform` did not reach the required level;
`130` interrupted. A receipt maps to 0 or 1 by its status whatever its error code,
except a refusal whose `error.mhs_code` is `MHS.AUTH.*`, which is 4 (an
operator-only reset sent with the client token, `MHS.AUTH.HARDWARE_DISABLED`); codes
3 and 4 otherwise come from errors raised without a receipt. A multi-device `estop`
exits 0 only when every device has a `completed` receipt, otherwise with the code
all its failures share (3 or 4), else 1. Scripts MUST be able to distinguish a
physical rejection from a transport failure. With `--json` an error is printed on
stdout as `{"error": {"mhs_code", "message", "retryable", "data", "remediation"}}`
and stdout holds only the JSON result ([core.md](core.md) CORE-137).

**TPT-053.** `mhs serve --mcp` MUST start the MCP projection (§5) on stdio, with the
host policy options `--mcp-config PATH`, `--operator-tools` and
`--allow-external-sessions`; `mhs serve` MUST otherwise start the endpoint's
configured transport (HTTP on port 7400 by default, `--stdio`). Anything but a
loopback `--host` needs `--token-file`; when a token file is configured every HTTP
request except `/.well-known/mhs.json` needs the token. The ready line
(`{"mhs_ready": true, "url": …}`) goes to stdout for HTTP and to stderr for `--stdio`.
`mhs conform` MUST run the suite of [MHS-001](01-conformance.md) and write the report
(`-o`).

---

## 7. T6 — Code API (SHOULD)

**TPT-054.** The reference Python API is `mhs` ([`../sdk/INTERFACE.md`](../sdk/INTERFACE.md)):
`connect(endpoint_or_argv)`, context-managed sessions, `invoke` returning a
receipt, `read`, `subscribe`, `events`, `cancel`, `snapshot`, `restore`,
`safety_status`, `estop`, `reset`, `permit`, `export_evidence`. A per-device typed
binding generator is OPTIONAL and MUST be generated from the capability schemas,
not hand-written.

**TPT-055.** The code API MUST NOT hide receipts, retry physical commands
implicitly, or translate a `rejected` receipt into an exception. It MUST raise
`MHSError` only for transport, protocol, authentication and session-level
failures, matching the wire split defined in [MHS-002](02-wire-protocol.md)
PROTO-028. The one exception is the code-file helper `mhs.run.lab(...)`, which with
its default `check=True` raises `MHSRejected` (an `MHSError` carrying the receipt) for
any receipt other than `completed` or `running`, so that a script stops at the first
refusal; `check=False` returns the receipts ([core.md](core.md) CORE-140).

**TPT-056.** The code API MUST expose the negotiated `mhs_version`, the device
mode, risk class, fidelity gaps and conformance claim to the caller, and MUST
default deadlines to a finite value. "Fire and forget" helpers MUST NOT exist for
mutating methods.

**TPT-057.** A code API connection MUST be usable from a worker thread or async
task without shared mutable transport state; the reference SDK uses one transport
per client and documents the concurrency model.

---

## 8. Authentication model

**TPT-058.** Transport authentication maps to an MHS principal
([MHS-004](04-safety.md) §7). The endpoint MUST NOT accept a principal identity
from the request body as authenticated. Authentication methods:

| Method | Transport | Notes |
|---|---|---|
| Process identity | T1 | stdio endpoint inherits the launching process's identity; the descriptor declares `auth: ["local"]`. |
| Bearer token | T2/T3 | Opaque, revocable, scoped to at least one endpoint and principal; `Authorization: Bearer <token>`. |
| mTLS | T2/T3 | Client certificate mapped to a principal; preferred for device networks. |
| One-time ticket | T3 | For browser WebSocket; exchanged for the connection, never reused. |

**TPT-059.** Tokens MUST be rotatable without restarting the endpoint, MUST NOT
appear in URLs (except one-time tickets), logs, error messages, receipts, evidence
or registry records. A leaked token MUST be revocable; revocation MUST be
effective for new requests immediately and for open sessions at expiry.

**TPT-060.** Read-only projections (dashboards, monitors) MUST use a principal
with read-only grants; the endpoint MUST enforce grants even if the transport is
trusted ([MHS-004](04-safety.md) SESS-008).

---

## 9. Reconnection and gap semantics

**TPT-061.** A transport disconnect MUST NOT close the MHS session immediately;
the session lives until `expires_at` ([MHS-002](02-wire-protocol.md) SESS-004).
The client MUST be able to reconnect and continue with the same `session_id`
(while unexpired) or open a new session.

**TPT-062.** Commands in flight at disconnect: the client MUST NOT assume
failure. It MUST query `mhs.operations.get`/`mhs.resource.read` on reconnect; an
unresolvable command MUST be reported as `unknown` with
`MHS.OUTCOME.UNKNOWN`, never retried blindly.

**TPT-063.** Subscription continuity: on reconnect the client MUST re-subscribe or
resume (SSE `Last-Event-ID`, WebSocket session-scoped subscription). When the last
delivered `seq` and the first new `seq` are not contiguous, the endpoint MUST
deliver a control gap event, and the client MUST treat state as unknown until it
re-reads. Silent drops are prohibited.

**TPT-064.** The client MUST apply exponential backoff with jitter to reconnect
attempts, cap the retry interval, and stop after a declared attempt budget; the
endpoint MAY return `MHS.LIMIT.RATE_EXCEEDED` with `retry_after_ms`.

---

## 10. Requirements traceability

| Requirement | Conformance test | Checks |
|---|---|---|
| TPT-004 | TPT-004 | stdio NDJSON: no BOM, one message per line, malformed line recovers. |
| TPT-005 | TPT-005 | Protocol stream clean; logs only on stderr. |
| TPT-008 | TPT-008 | stdin EOF → safe shutdown and exit 0. |
| TPT-010 | TPT-010 | All four HTTP paths answered. |
| TPT-011 | TPT-011 | Wrong content type → 415; GET on RPC → 405. |
| TPT-012 | TPT-012 | JSON-RPC error over HTTP 200; 401 unauthenticated. |
| TPT-013 | TPT-013 | Non-loopback plaintext refused. |
| TPT-016 | TPT-016 | SSE event framing, ids, heartbeats. |
| TPT-018 | TPT-018 | Resume by `Last-Event-ID`; gap event when not possible. |
| TPT-020 | TPT-020 | Limits advertised and enforced; latency measured. |
| TPT-021 | TPT-021 | WebSocket subprotocol and multiplexing. |
| TPT-030 | TPT-030 | Tool names match the scheme and the 63-character bound. |
| TPT-033 | TPT-033 | Projected inputSchema equals the class schema plus optional control properties (session_id, command_id, expected_revision, permit_id, deadline_ms), stripped before input validation. |
| TPT-034 | TPT-034 | Tool description carries mode/risk/gaps/units. |
| TPT-036 | TPT-036 | `tools/call` → exactly one `mhs.command`; command_id per call. |
| TPT-038 | TPT-038 | `rejected` receipt → `isError: false`; receipt inside structuredContent. |
| TPT-039 | TPT-039 | Transport failure → `isError: true` with `mhs_error`. |
| TPT-040 | TPT-040 | Progress notifications correlate with MHS progress. |
| TPT-041 | TPT-041 | MCP cancellation reaches `operations.cancel`; safe-state receipt returned. |
| TPT-043 | TPT-043 | Resources list/read map to device manifests and state. |
| TPT-045 | TPT-045 | MCP initialize/version/capabilities handshake. |
| TPT-050–052 | TPT-050…052 | CLI commands, `--json`, the one exit-code table (0 to 5, 130). |
| TPT-054–056 | TPT-054…056 | Code API receipts, errors, disclosure, deadlines. |
| TPT-061–064 | TPT-061…064 | Reconnect, unknown outcome, gap events, backoff. |

The mandatory negative set is in [MHS-001](01-conformance.md) §4.3. The reference
implementation of the MCP projection is `MHS/sdk/src/mhs/mcp.py`; its behaviour is
specified here and its interop is tested against the OpenAI4S MCP client
([MHS-009](09-host-profile.md) annex A).
