# MHS-009 — MHS-Host Profile

| Field | Value |
|---|---|
| Document | MHS-009 (normative; annex A informative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | optional profile: Host ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §10 and §11; overview in [00-architecture.md](00-architecture.md) §11 (informative) |
| Reference host | OpenAI4S (`PKU-YuanGroup/OpenAI4S`), described in [annex A](#annex-a-the-openai4s-reference-host-informative) (informative) |

A **host** is the agent harness that consumes MHS: it discovers endpoints,
opens least-privilege sessions, gates permits through human or policy approval,
executes commands, records evidence and presents mode, risk and fidelity honestly
to the model and the operator. This document is host-neutral: it defines what an
MHS-Host must do whatever its architecture. How the OpenAI4S reference host does it is
described in [annex A](#annex-a-the-openai4s-reference-host-informative), which is
informative. It details [core.md](core.md) §10 and §11; wire semantics remain in
[MHS-002](02-wire-protocol.md).

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Scope and conformance

**HOST-001.** A host claiming MHS-Host conformance MUST satisfy the level matrix
of [MHS-001](01-conformance.md) §5.2 and MUST satisfy the requirements in this
document for that level. Host conformance is about behaviour of the harness, not
of the endpoints it talks to.

**HOST-002.** A host MUST be tested against at least one endpoint with a valid
CL3-or-higher report; a host tested only against mocks is a self-test and MUST
label its report accordingly ([MHS-001](01-conformance.md) §3.4).

**HOST-003.** The host MUST NOT claim that MHS replaces hardware safety, MUST
display `MHS.SAFETY.NOT_CERTIFIED` and the device's mode/fidelity gaps before
actuation, and MUST NOT present a simulated endpoint as hardware
([MHS-004](04-safety.md) SAFE-051, [MHS-005](05-fidelity.md) FID-043).

---

## 2. Discovery and configuration

### 2.1 Endpoint sources

**HOST-010.** The host MUST discover endpoints from all configured sources, in a
deterministic precedence order, and MUST record which source produced each
endpoint:

1. explicit configuration: `MHS_ENDPOINTS` (comma-separated) and
   `~/.mhs/endpoints.json`;
2. a local registry index the host maintains;
3. endpoint well-known descriptors: `GET /.well-known/mhs.json` at a configured
   base URL;
4. federated registries, only when the operator enabled them
   ([MHS-007](07-registry.md) §8).

Registry-provided and discovered endpoints MUST be treated as untrusted until
authenticated ([core.md](core.md) CORE-122). The host MUST NOT auto-connect to an endpoint
that appeared only because a model asked to "find more devices".

**HOST-011.** The host MUST authenticate each endpoint according to its declared
`auth` and MUST keep credentials per endpoint, not global. A stdio endpoint
launched as a child process inherits the host's identity and MUST be recorded as
`auth: "local"`.

**HOST-012.** The host MUST cache device profiles and manifests as host artifacts
keyed by `(endpoint_id, device_id, instance_id, manifest_digest)`, so that a
changed manifest is detectable and evidence references the exact profile the model
saw. A cached profile without a digest MUST be discarded at session open.

### 2.2 What must be presented

**HOST-013.** For every device the host MUST present to the model: `mode`,
`risk_class`, a one-line summary, the capability list and, for simulated/hybrid
devices, `determinism.kind` and `fidelity.gaps`. This is the machine-readable
version of "write what you know about your hardware in natural language"
([00-architecture.md](00-architecture.md) §4.4, informative) and MUST be generated from
the manifest and the reference file ([core.md](core.md) CORE-030).

**HOST-014.** The host MUST display the endpoint's conformance claim, its trust
level (`self` vs `verified`) and the trust of the registry record that supplied it
([MHS-007](07-registry.md) §5). A missing claim MUST be shown as "no claim", not
as an implied pass.

**HOST-015.** The host MUST NOT hide fidelity gaps behind a link or a tooltip
that the model cannot read. Gaps MUST be in the model's context whenever the
device profile is, and MUST be repeated at the approval surface (§6).

---

## 3. The "one call" property

**HOST-020.** For any MHS endpoint — a Rust conveyor workcell, a Python
liquid-handler simulator, a MuJoCo arm, a microscope — the same host code path
MUST execute a command. The host MUST NOT branch on device type, repository or
vendor outside the adapter plane. Differences live in the manifest
([00-architecture.md](00-architecture.md) §11.3, informative).

```python
# runnable
from mhs.adapter import load
from mhs.reference import build_endpoint, build_server
from mhs.run import lab

thermostat = load("MHS/sdk/examples/thermostat", backend="fake")        # a driver package on its fake backend
conveyor = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=False),
                        log_ready=False)                               # a reference simulator

with lab(thermostat, conveyor, ledger=False) as bench:                  # two endpoints, one transport API
    for name, capability, payload in (("tutorial-thermostat", "cap.thermal.setpoint.v1", {"target_temperature": 30}),
                                      ("conveyor-workcell", "cap.world.step.v1", {"ticks": 3})):
        receipt = bench[name].invoke(capability, payload)               # the same call for every device
        assert receipt["status"] == "completed", receipt
thermostat.close()
conveyor.close()
```

**HOST-021.** The host MUST treat every endpoint uniformly in its policy layer:
risk class, mode, permits and evidence are properties of the session and receipt,
not of a hard-coded device registry. Adding a new device family MUST require an
adapter manifest, not a host code change.

**HOST-022.** A host MAY add device-family ergonomics (for example a "pipetting"
macro), but any such macro MUST lower to capability calls with normal receipts and
MUST NOT bypass sessions, permits or the envelope.

---

## 4. The tool surface

A host exposes MHS to the model through the MCP projection of
[MHS-008](08-transports.md) §5: one tool per bound capability, device- and
capability-scoped, plus the fixed tools `mhs__devices`, `mhs__inspect`, `mhs__read`,
`mhs__safety`, `mhs__operations`, `mhs__evidence` and `mhs__estop` (TPT-044). The
operator tools `mhs__reset` and `mhs__permit` are not part of the model's tool
surface: in 0.9 permits and resets go only through the host's operator route
(an operator-enabled console, or the projection started with `--operator-tools` for a
connector a human drives), never through a tool the model can call
([core.md](core.md) CORE-130). There is no generic "control any hardware" tool.

**HOST-030.** Tool descriptions MUST be generated from the capability schemas and
semantic tags, not hand-written prose, and MUST be regenerated when a manifest
digest changes. A description that drifts from the schema is a conformance failure.

**HOST-031.** Each capability tool's input schema MUST be the binding's input schema
with only the optional control fields of TPT-033; a host that offers one generic
command tool instead MUST make its input schema a union of the bound capability input
schemas discriminated by `capability_id`, with `device_id`, `resource`,
`expected_revision` and a description of the permit requirement. The host MUST
validate the call against the endpoint's schema before sending.

**HOST-032.** The host MUST mark the capability tools (or its generic command tool)
and the operator tools (`mhs__reset`, `mhs__permit`) as requiring approval according
to policy; a host that auto-approves a capability call for R2+ hardware is
non-conformant for CL3. The
emergency stop is the exception: a narrowly scoped, operator-enabled, endpoint-
and device-bound trusted stop action MUST bypass *ordinary action approval* so a
denied or pending approval cannot block the stop ([MHS-004](04-safety.md) SAFE-029). The
exception MUST NOT broaden into a general MCP-call exemption: connector
authorization, endpoint allow-listing and device binding still apply, and the
action MUST be recorded in the host audit/evidence ledger.

**HOST-033.** Tool output MUST include the full receipt (status, revisions, state
hash, effects, error) and MUST NOT summarise away a `rejected`/`failed`/`unknown`
status. A model that only sees "ok" cannot reason about physical risk
([MHS-002](02-wire-protocol.md) PROTO-028).

---

## 5. Sessions and least privilege

**HOST-034.** The host MUST open a session per task/device scope, request only the
capabilities the task needs, and close it when the task ends. A long-lived
all-capability session is non-conformant.

**HOST-035.** The session `principal.kind` MUST be `agent` for model-driven calls
and the approvals MUST name `human` principals for R3 permits
([MHS-004](04-safety.md) §6.2). The host MUST NOT let the model supply a principal
identity.

**HOST-036.** The host MUST refresh sessions with `session.heartbeat` before
`expires_at` (when the endpoint implements it) and MUST handle expiry by
re-opening a session, re-reading state and re-checking permits. It MUST NOT retry
the failed command on the new session without re-establishing preconditions.

**HOST-037.** The host MUST enforce deadlines on the endpoint calls and MUST
surface `MHS.OUTCOME.UNKNOWN` to the model as an unresolved physical outcome that
requires observation, never as a retryable infrastructure error. The `deadline_ms`
it sends MUST be shorter than the timeout of its own transport, so that the endpoint's
answer (a `running` or `unknown` receipt, [core.md](core.md) CORE-100) arrives before
the transport gives up and kills the connector.

---

## 6. Approval UX requirements

Approvals are the human control point that MHS cannot replace with a policy engine
for R3 actions. The following requirements are normative for host UI.

**HOST-040.** Before requesting a permit, the host MUST display, in one surface:

1. device `display_name`, `device_id`, `mode`, and `risk_class`;
2. the capability summary and semantic tags;
3. the exact input in human-readable form, with units;
4. the `input_digest` (or a checksum-derived short form) that the permit will bind;
5. the resource and expected state/revision context;
6. the permit TTL and single-use nature;
7. for simulated/hybrid devices, the mode and the relevant `fidelity.gaps`;
8. `MHS.SAFETY.NOT_CERTIFIED` and the hardware e-stop statement.

**HOST-041.** The human MUST approve the *same* input digest that is sent in the
command. If the input changes after approval (even a formatting change that
changes the digest), the permit MUST be considered void and approval re-requested
([MHS-004](04-safety.md) SAFE-031).

**HOST-042.** The approval surface MUST be rendered by the host's trusted UI, not
from model-generated text. A model message that claims "the operator approved" is
not approval evidence; the approval record MUST be created by the UI/policy
component with `principal`, `method`, `approved_at` and `evidence_ref`.

**HOST-043.** Deny-by-default: a missing approval, an unavailable policy engine,
an expired session, an unknown interlock or an unknown risk class MUST result in
refusal. The host MUST NOT "fail open" because the operator is not available.

**HOST-044.** The host MUST support at least `human_click` and `policy_rule`
approval methods and SHOULD support `dual_control` for R3. The approval record's
`method` MUST be recorded exactly; a policy rule MUST NOT be recorded as a human
click.

**HOST-045.** Approval decisions MUST be logged into the host's evidence ledger
(§7) with the rendered input digest, the approver principal, the decision, the
timestamp and any denial reason. Denials are as important as approvals: they show
that the envelope worked.

**HOST-046.** Emergency stop MUST be available on the same surface as approvals and
MUST take at most one action: for a device with a software/both e-stop, the host
calls `mhs.safety.estop`; for hardware-only devices it must present the physical
stop location (`estop.physical_ref`) and MUST NOT claim to stop the device itself.

**HOST-047.** The operator MUST be able to see and revoke outstanding permits. A
revoked permit MUST be treated as invalid by the host even if the endpoint has not
yet observed the revocation (the host MUST not send it).

---

## 7. Evidence ledger design

### 7.1 What the host records

**HOST-050.** The host MUST maintain an append-only ledger that contains at least:

1. every receipt received from every endpoint, in receipt order, with the
   endpoint's `evidence{seq, prev_digest, digest}`;
2. every session lifecycle event (`open`, `heartbeat`, `close`, `expired`);
3. every approval decision (approve/deny, principal, method, input digest);
4. every tool call issued by the model that produced a command (name, arguments
   digest, `command_id`), without secrets;
5. every evidence export/verify operation and its result;
6. every mode/risk/fidelity disclosure shown to the model (profile digest).

**HOST-051.** The ledger MUST be append-only and tamper-evident: each entry
carries `seq`, `prev_digest`, `digest` computed over
`sha256(JCS(entry without digest) || prev_digest)`; a genesis entry anchors the
ledger. The ledger MUST be exportable as a bundle verifiable offline, and the host
MUST be able to export the endpoint-side MHS evidence bundles alongside its own
ledger so a reviewer can cross-check them.

**HOST-052.** The host MUST NOT rewrite a receipt to fit its ledger schema. It MAY
wrap it (`{"source": "mhs", "receipt": {...}, "received_at": "…"}`) and MUST
preserve the original bytes' digest relationship: the endpoint's `digest` MUST be
recorded verbatim and the wrapper's own digest MUST be over the wrapper.

### 7.2 Verification

**HOST-053.** The host MUST implement verification of both chains: its ledger and
each endpoint evidence bundle ([MHS-004](04-safety.md) §8.2). A verification
failure MUST be surfaced as `MHS.EVIDENCE.CHAIN_BROKEN` to the operator and MUST
block export of a "verified" package.

**HOST-054.** The host's exported session package MUST include the ledger, the
endpoint bundles, the manifests referenced (by digest), the session transcript and
a `manifest_sha256` over the package manifest, so that a recipient can verify
without contacting the host.

**HOST-055.** The host MUST state in every export what is *not* proven: that the
endpoint was honest, that the device was safe, that the experiment succeeded.
Hash chains prove internal consistency and tamper evidence relative to the
anchors, not truth ([MHS-004](04-safety.md) EVID-022).

**HOST-056.** Retention and privacy: the ledger MUST follow the host's retention
policy (at least the endpoint's receipt retention), MUST redact per the adapter's
`redaction` rules, and MUST NOT contain bearer tokens, credentials, or personal
data beyond approver identities required for audit.

### 7.3 Replay integration

**HOST-057.** The host SHOULD record enough to reproduce a plan against an MHS
replay endpoint: command sequence with inputs and `command_id`s, seeds, manifest
digests, and the resulting state hash sequence. The host's replay must not
re-execute hardware commands; hardware replays are evidence playback only
([MHS-005](05-fidelity.md) §5).

---

## 8. Host integration through MCP connectors

A host integrates MHS **MCP-first**: one projection process per endpoint
([MHS-008](08-transports.md) §5), registered in the host as an ordinary MCP connector
that is disabled by default and enabled by the operator in the host's settings. The
host's existing MCP client then drives MHS with no change to its core. A native-tool
overlay may exist as a developer aid; host conformance never depends on it. Which
components of a particular host do what is described, for the OpenAI4S reference host,
in [annex A](#annex-a-the-openai4s-reference-host-informative).

**HOST-060.** The integration MUST NOT patch the host's generic MCP client, its tool
registry, its permission broker or its evidence code to make MHS work; it MUST work
through MCP connector configuration and the host's existing extension points. A
required change to a core module (for example, to journal commands durably on the
governed path of §8.3) MUST be proposed upstream, shipped as a reviewable patch and
recorded as a deviation in the host report.

**HOST-061.** The MHS integration MUST be represented as ordinary MCP connector
row(s): stable connector id, launch command, `transport`, and an `enabled` flag.
No host-specific MCP code may be required to connect; the connector row is the
integration unit. When the host-integration package for the configured host cannot be
imported, the integration answers `MHS.HOST.ADAPTER_MISSING` (the deprecated alias
`MHS.HOST.OPENAI4S_MISSING` is handled identically and is removed in 0.10).

**HOST-062.** The MCP projection MUST expose (a) discovery and read tools,
(b) one tool per bound capability, device- and capability-scoped, (c) safety
status and an e-stop, (d) evidence export and verification, and, only when the
operator enables them, (e) reset and permit issuance for gated capabilities
([core.md](core.md) CORE-130). It MUST NOT expose a generic "control any hardware"
tool. A capability refusal MUST return a receipt with `isError: false`; only
transport, protocol, policy and session faults are `isError: true`.

**HOST-063.** The host's MCP client framing limits and transport behaviour (frame
size, timeout classes, connector killed on timeout; common clients use 4 MiB frames)
MUST be matched by the MHS MCP projection ([MHS-008](08-transports.md) TPT-047); a
mismatch that causes silent truncation or an unbounded call is a conformance failure.

### 8.0 Orchestration (CL5)

**HOST-080.** A CL5 host MUST drive more than one endpoint in one task through
the same code path (§3), keeping sessions per endpoint and never sharing a
`session_id` across endpoints.

**HOST-081.** Multi-endpoint operations MUST record a parent action in the host
ledger with the child receipts from each endpoint, so the physical sequence is
reconstructable across devices.

**HOST-082.** The host MUST handle per-endpoint backpressure, gaps and reconnects
independently; a stalled subscription on one endpoint MUST NOT silently stop
evidence capture from another.

**HOST-083.** A CL5 host MUST publish or point to its conformance report from the
registry claim mechanism ([MHS-007](07-registry.md) §4.4) when it makes a public
claim.

**HOST-084.** A CL5 host MUST support composition execution (`mhs.composition.run`)
and MUST preserve parent and child receipts in its ledger, including the
composition digest. Composition is reserved in 0.9 ([profiles.md](profiles.md) §1): no
0.9 endpoint implements the method, so this requirement cannot be exercised against
one.

**HOST-085.** A CL5 host MUST be able to drive an endpoint in `replay` mode for
verification and MUST label the resulting session and evidence as replay, never
as live execution.

### 8.1 What the host must expose to the model

**HOST-064.** The host MUST include in the model's context, for each connected
endpoint: endpoint id and trust; device id, display name, mode, risk class,
capability summaries and tags; determinism kind and fidelity gaps for simulated
devices; and the instruction that MHS is not a safety channel. This is the
host-side half of the "semantics in-band" axiom
([00-architecture.md](00-architecture.md) A3, informative).

**HOST-065.** The host MUST NOT summarise a capability as "works like the SDK
call X" without the physical summary and units; the model acts on physical meaning,
not on native API names.

### 8.2 Experimental surfaces MUST be off by default

**HOST-066.** MHS is exposed in a host through a **standard MCP connector** and is
an **experimental integration**. The connector MUST default to disabled and MUST
require an explicit, recorded operator action to enable it. Installing,
upgrading, discovering an endpoint or starting the host for the first time MUST
NOT enable it.

**HOST-067.** The enablement state MUST be visible in the host's settings or
status surface, together with the fact that the feature is experimental. The
operator MUST be able to disable it again, and disabling MUST remove the surface
at the next installation/activation boundary at the latest.

**HOST-068.** While the integration is disabled the host MUST NOT activate the
MHS MCP connector: no projected tool is reachable, no endpoint connection is
opened by the feature, and the model MUST NOT be told that MHS is available. The
connector rows MAY remain listed in settings with `enabled: false` so the
operator can turn them on. Operator-facing CLI or SDK entry points for
diagnostics MAY remain, provided they require an explicit human invocation and
are never auto-invoked by the agent.

**HOST-069.** The integration MUST use the MCP projection
([MHS-008](08-transports.md) §5) as its agent-facing surface so that any MCP
harness can use MHS once enabled without host-specific code. Enabling and
disabling MUST apply to every MHS surface together, MUST update the connector
`enabled` flag, and SHOULD be recorded in the host's audit or evidence ledger as
an operator action.

### 8.3 Governed MCP host path (normative)

The MCP connector row is the integration unit; the bare generic
`CallMCPTool` route is transport interoperability only and MUST NOT be described
as a governed host path. A governed MCP host implementation MUST provide the
following, layered on the connector:

**HOST-090.** The connector MUST carry the deployment policy into the MCP
projection (a trusted `--config` file). Given a policy document the projection MUST
default to `enabled=false` and `allow_hardware=false`, and only a JSON `true`
enables a flag (a direct launch of the projection without a document is enabled with
every other flag false, [core.md](core.md) CORE-130); while disabled all tool calls
MUST be refused, and for hardware devices capability tools, reads and operations MUST
be refused with `MHS.AUTH.HARDWARE_DISABLED` before any session is opened. Discovery,
safety status, evidence and the trusted e-stop MUST remain available for an
authorized connector; reset and permit issuance exist only on the operator route.

**HOST-091.** The host MUST allocate and durably journal a `command_id` before
dispatch. A post-send transport timeout or lost reply MUST be surfaced as
`MHS.OUTCOME.UNKNOWN` with that `command_id`, and a new command MUST be blocked
until a read/operation reconciliation has run; a same-id retry MUST return the
retained receipt with `replayed: true` and MUST NOT execute twice. A pre-send
failure is a safe retry and MUST be distinguished from the ambiguous case. A
`running`, `accepted` or `unknown` receipt keeps the device's gate shut: the host
MUST NOT issue another effectful command to that device until the earlier command is
settled by its final receipt or by reconciliation.

**HOST-092.** The host MUST maintain an append-only, hash-chained ledger for the
governed path: for every invocation it records the connector/endpoint, device,
capability, command id, intent/action digest, approval or denial, receipt digest,
outcome and timestamp. The chain link is
`sha256(JCS(record without digest) || prev_digest)`, and the first record uses a
declared genesis digest.

**HOST-093.** The host MUST export a portable package containing the host ledger
and the endpoint evidence bundle, and MUST offer offline verification that
recomputes the host chain and verifies the endpoint bundle. A durable-store
failure MUST be visible to the operator, not silently dropped.

**HOST-094.** The trusted emergency-stop action MUST be operator-enabled,
endpoint- and device-allow-listed, and recorded as a pair of audit records
(request and receipt) in the host ledger. A host that cannot provide this
narrow exception MUST NOT claim a governed emergency-stop path for its MCP
route.

---

## 9. What the host is not allowed to do

**HOST-070.** The host MUST NOT cache a permit and reuse it for a later command,
even with an identical digest, if the endpoint's permit was single-use
([MHS-004](04-safety.md) SAFE-031).

**HOST-071.** The host MUST NOT send `mhs.safety.reset` automatically after an
e-stop. Reset is a human decision that requires cleared interlocks and a new start.

**HOST-072.** The host MUST NOT hide endpoint errors from the model or the
operator; an `MHS.LIMIT.*`, `MHS.SAFETY.*` or `MHS.TRANSPORT.*` error MUST be
visible with its `mhs_code` and remediation.

**HOST-073.** The host MUST NOT connect to an endpoint whose manifest failed
validation, whose conformance claim is missing at CL2+, or whose mode/risk
disclosure it cannot render. Fail closed.

---

## 10. Requirements traceability

| Area | Requirement range | Level introduced |
|---|---|---|
| Discovery, presentation | HOST-010 … HOST-015 | CL1 |
| Uniform code path, tool surface | HOST-020 … HOST-022, HOST-030 … HOST-033 | CL1–CL2 |
| Sessions, deadlines, unknown outcomes | HOST-034 … HOST-037 | CL2 |
| Approvals and disclosure | HOST-040 … HOST-047 | CL3 |
| Evidence ledger and replay | HOST-050 … HOST-057 | CL4–CL5 |
| MCP connector integration | HOST-060 … HOST-065 | CL1–CL5 |
| Prohibitions | HOST-070 … HOST-073 | CL2–CL3 |
| Experimental skill gating | HOST-066 … HOST-069 | CL1–CL3 |
| Orchestration | HOST-080 … HOST-085 | CL5 |

The suite tests `HOST` ids through a host adapter (a scripted host that drives the
endpoint and asserts the UI/ledger artefacts). The reference host's tests are in
`integration/openai4s/tests`. The endpoint-side requirements the host relies on are in
[MHS-002](02-wire-protocol.md) and [MHS-004](04-safety.md); the MCP projection it
may use is in [MHS-008](08-transports.md) §5.

---

## Annex A. The OpenAI4S reference host (informative)

This annex is informative. It describes how the reference host, OpenAI4S
(`PKU-YuanGroup/OpenAI4S`), does what §1 to §9 ask. The integration package is
`integration/openai4s/openai4s_mhs` and is experimental and disabled by default.

| MHS host concern | OpenAI4S component | Integration |
|---|---|---|
| MCP client, framing, deadlines, child-process lifecycle | `openai4s/mcp_client.py` (`MCPConnection`, `MCPManager`) | MHS is reached as an MCP server: connector command `python3 -m mhs.mcp --endpoint …` (or `--command …`). No client code is added to OpenAI4S. |
| MCP HTTP/SSE (optional) | `openai4s/mcp_http.py`, `openai4s/mcp_protocol.py` (`MAX_FRAME_BYTES`) | The stdio binding is the default. |
| Connector registration and settings | `openai4s/storage/connectors.py`, `openai4s/store.py` | `openai4s_mhs` generates one connector row per endpoint (`connector_id = mhs-<endpoint>`, `command`, `transport: "stdio"`, `enabled: false`) and upserts it; enabling it is the operator action (HOST-066 to HOST-069). |
| Tool surface | `openai4s/tools/mcp.py` | The model sees the projection's `mhs__*` capability and discovery tools, each device-bound (`mhs__devices`, `mhs__inspect`, `mhs__read`, `mhs__safety`, `mhs__operations`, `mhs__evidence`, `mhs__estop`). `mhs__reset` and `mhs__permit` are not on the agent connector. |
| Approvals, reset | `openai4s_mhs.operator_route` (`OperatorRoute`) | Permits and resets go through the host operator route, a separate connector started with `mhs.mcp --operator-tools` that a human drives; the agent connector never lists them (CORE-130). |
| Safety | `mhs__safety`, `mhs__estop`, the host action `mhs_emergency_stop` | The e-stop is reachable through MCP and never sits behind an approval prompt; a hardware e-stop remains mandatory and independent. |
| Evidence | `mhs__evidence`, `openai4s_mhs.host_evidence` | The host stores the exported bundle and head digest, keeps its own hash-chained ledger and verifies both chains offline. |
| Governed path | `openai4s_mhs.hostroute.governed_call`, `openai4s_mhs.mcp_invoke` | Called from the host's `MCPService.call` over the connector's own `MCPManager`; it persists intent and a durable `command_id` before the effect and appends the host-ledger record and the endpoint evidence after the outcome. |
| Trusted stop | `mcp_call` with tool `mhs__estop` on an enabled MHS connector; the named host action `mhs_emergency_stop` | Both bypass only the ordinary `PermissionBroker.gate`; connector enablement, endpoint and device mapping, `estop_devices`, hardware policy, the host ledger and the host audit log still apply. Non-MHS connectors and ordinary commands are unchanged. |

The governed path needs a change to two OpenAI4S core files
(`openai4s/host/mcp.py` and `openai4s/host_dispatch.py`), shipped as
`integration/openai4s/openai4s-core.patch` against upstream commit
`f48f216c81fe400444857c8a5d84d7407398918c` (HOST-060). The direct entry points
(`invoke`, `reconcile`, `emergency_stop`, `OperatorRoute`) need no OpenAI4S change, and
the developer overlay (`openai4s_mhs.install()`, optionally hooked by
`openai4s-mhs.patch`) is not the MCP path.
