# OpenAI4S × OpenMHS reference host

OpenMHS devices reached from [OpenAI4S](https://github.com/PKU-YuanGroup/OpenAI4S)
through **MCP**. OpenAI4S's `MCPManager` talks to one `mhs.mcp` stdio server per
OpenMHS endpoint; every discovery, read, command, safety action and evidence
export is an MCP `tools/call`. This directory is the reference host example of
OpenMHS 0.9. It is experimental and disabled by default.

What it needs from OpenAI4S:

| Part | OpenAI4S change | Without that change |
|---|---|---|
| MCP connector rows (`mcpconfig.py`) | none: a row is configuration | — |
| Governed host route: durable journal, host ledger, endpoint evidence, trusted e-stop (`hostroute.py`) | **required:** `openai4s-core.patch`, 2 core files (`openai4s/host/mcp.py`, `openai4s/host_dispatch.py`), 177 insertions and 7 deletions against upstream commit `f48f216c81fe400444857c8a5d84d7407398918c` (OpenAI4S 0.3.1) | MHS rows run through the stock `MCPService` path ungoverned: the e-stop sits behind the approval prompt, nothing is journaled |
| Direct entry points: `invoke`, `reconcile`, `emergency_stop`, `OperatorRoute` | none | — |
| Developer overlay auto-install | optional: `openai4s-mhs.patch` (one hook in `openai4s/__init__.py`) | call `openai4s_mhs.install()` yourself |

> **Experimental MCP integration — disabled by default.** OpenMHS is registered
> as ordinary OpenAI4S MCP connector(s), one row per endpoint, with
> `enabled: false`. The rows are visible in settings, but no projected `mhs__*`
> tool is reachable and no endpoint connection is opened until an operator
> enables the feature:
>
> ```bash
> python3 -m openai4s_mhs status    # {"kind": "mcp", "enabled": false, "experimental": true, ...}
> python3 -m openai4s_mhs enable    # flips the settings and connector rows on (~/.openai4s/mhs.json, 0600)
> python3 -m openai4s_mhs disable   # and off again
> ```
>
> `MHS_ENABLED=1` overrides the setting for one process (CI, demos). When
> `openai4s` is importable, `enable`/`disable` also upsert/patch the connector
> rows in OpenAI4S's own connector store (`store.upsert_connector`,
> `store.patch_connector`), so the switch is the normal connector toggle in
> settings. The normative rule is HOST-066…069 (an experimental MCP integration
> is off by default and needs an explicit operator action).

Everything here is **pure stdlib** (Python 3.10+). Nothing is installed: the
OpenMHS SDK and OpenAI4S are imported from the source trees of this workspace.

---

## 1. Layout

```
integration/openai4s/
├── openai4s_mhs/
│   ├── __init__.py        enable/disable/status, install(), public API
│   ├── config.py          MHSConfig / EndpointSpec (the settings document)
│   ├── mcpconfig.py       agent connector rows (enabled=false by default) and operator_argv()
│   ├── mcp_register.py    upsert/patch those rows in OpenAI4S's connector store
│   ├── connector_registry.py  process-local row -> settings fallback
│   ├── hostroute.py       the governed host route (called by the patched MCPService)
│   ├── emergency.py       HOST-002 trusted, device-bound e-stop
│   ├── operator_route.py  the host operator route: reset and permits (mhs.mcp --operator-tools)
│   ├── mcp_invoke.py      HOST-003 durable command id / UNKNOWN / in-flight / reconcile
│   ├── host_evidence.py   HOST-004 hash-chained host ledger + portable package
│   ├── corepatch.py       check / capture openai4s-core.patch (read-only git)
│   ├── host.py            MHSHost library (CLI, demo, overlay; not the MCP path)
│   ├── tools.py           developer overlay: eight Tool subclasses + dispatcher methods
│   ├── cli.py             python3 -m openai4s_mhs ...
│   └── __main__.py
├── demo/
│   ├── run_demo.py        acceptance demo (no LLM key)
│   ├── mcp_adapter.py     the demo's MCPManager adapter
│   └── demo-report.json   written by the demo
├── tests/                 unittest suite (section 7)
├── openai4s-core.patch    REQUIRED core change of the governed route (section 2)
├── openai4s-mhs.patch     optional overlay auto-install hook
├── DESIGN.md              design contract
└── README.md              this file
```

The overlay package is the top-level `openai4s_mhs` (not `openai4s.mhs`). It
imports OpenAI4S only in `tools.py`, `mcp_invoke.py` (the MCP client) and the
tests; the CLI's endpoint verbs work without it.

---

## 2. The OpenAI4S core patch

`openai4s-core.patch` is the change the governed route needs in two OpenAI4S
core files:

- `openai4s/host/mcp.py`: `MCPService.call` hands an MHS connector row (one
  whose command runs `mhs.mcp`) to `openai4s_mhs.hostroute.governed_call`, and
  `mhs__estop` to `hostroute.trusted_emergency_stop`, over the row's own
  `MCPManager` call; it adds `is_trusted_estop` and `emergency_stop`. An MHS
  row whose integration is not importable is refused, never run ungoverned.
- `openai4s/host_dispatch.py`: the named `mhs_emergency_stop` action, and the
  device-bound `mcp_call` → `mhs__estop` exception from the approval prompt
  (HOST-002).

The patch was captured read-only from `work/openai4s-src`, a checkout of
upstream `main` at the base commit with the change uncommitted
(`git --no-optional-locks diff --full-index HEAD`). Its header records
`Upstream`, `Base-Commit`, `OpenAI4S-Version`, `Files` and `Stat`. Check it:

```bash
export PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src
python3 -m openai4s_mhs core-patch check              # applies at Base-Commit; no drift from the checkout
python3 -m openai4s_mhs core-patch check --worktree   # the same against a full checkout
python3 -m openai4s_mhs core-patch check --overlay    # the optional overlay hook
```

`check` clones the checkout with `git clone --shared` into a temporary
directory, runs `git apply --check` there at `Base-Commit`, and compares the
patch with the checkout's current diff (`"matches"`). It never writes to the
checkout. Exit 0 when the patch applies and has not drifted, 1 otherwise, 2
when git or the checkout is missing.

To use it with your own OpenAI4S clone:

```bash
git -C <your OpenAI4S clone> checkout f48f216c81fe400444857c8a5d84d7407398918c
git -C <your OpenAI4S clone> apply "$PWD/integration/openai4s/openai4s-core.patch"
```

When the core files in `work/openai4s-src` change, record the new diff with
`python3 -m openai4s_mhs core-patch capture --write`.

---

## 3. Prerequisites and settings

```bash
export PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src
python3 -c "import openai4s_mhs, openai4s, mhs; print('ok')"
```

- OpenAI4S: `work/openai4s-src` in this workspace (0.3.1 at the base commit,
  with `openai4s-core.patch` applied as uncommitted changes).
- OpenMHS SDK: `MHS/sdk/src`, or the `openmhs` distribution installed from
  `MHS/sdk` (import name `mhs`).
- Reference endpoints: `python3 -m mhs.reference lab --port 7401`.

Configuration is resolved in this order: explicit `MHSConfig`, `MHS_CONFIG`,
`~/.openai4s/mhs.json`, then `MHS_ENDPOINTS`. Example:

```jsonc
// ~/.openai4s/mhs.json
{
  "enabled": false,
  "endpoints": [
    {"id": "lab",      "url": "http://127.0.0.1:7401", "label": "lab bench"},
    {"id": "conveyor", "command": ["python3", "-m", "mhs.reference", "conveyor", "--stdio"],
     "label": "conveyor workcell"}
  ],
  "evidence_log": "~/.openai4s/mhs-evidence.jsonl",
  "allow_hardware": false,
  "auto_permit_risk": ["R0", "R1"],
  "session_ttl_s": 900,
  "command_timeout_ms": 60000,
  "operator_token_file": "~/.openai4s/mhs-operator.token"
}
```

`allow_hardware: false` means hardware devices are discovered but their
capability, read, operations and permit calls are refused. Listing an
instrument in a config file must not be enough to drive it.

Only a JSON `true` turns `enabled` or `allow_hardware` on, in `MHSConfig` and in
`mhs.mcp` alike. A quoted `"true"` or `"false"`, or `1`, reads as false, and
`status` lists it under `notices`.

The same document is the `--config` of every agent connector row, so it must
not set `operator_tools` or `allow_external_sessions`. `status` (and
`MHSConfig.warnings`) reports either one. `enable`, `mcp-config --write` and an
enabled `mcp-config` listing refuse to write or enable agent rows while either
is set (`MHS.HOST.CONFIG_REQUIRED`, exit 2), and the host route refuses the
operator tools anyway. `operator_token_file` is read only by the host operator
route (section 4.3).

`MHS_ENDPOINTS` is a comma-separated list of URLs and `stdio:<command>`
entries whose words are separated by spaces, for example
`MHS_ENDPOINTS="http://127.0.0.1:7401,stdio:python3 -m mhs.reference arm --stdio"`.

---

## 4. MCP connector rows — the agent path

The labels HOST-001…004 in this section and in the test names are the four
host fixes this integration carries (policy, trusted e-stop, governed
invocation, host evidence); they are not requirement ids of
`MHS/spec/09-host-profile.md`.

`mhs.mcp` is the SDK's stdio MCP server fronting one endpoint. Generate one
OpenAI4S connector row per endpoint:

```bash
python3 -m openai4s_mhs mcp-config --json
```

```json
{"connectors":[
  {"id":"mhs-lab","name":"lab bench","transport":"stdio","enabled":false,
   "command":["/usr/bin/python3","-m","mhs.mcp","--endpoint","http://127.0.0.1:7401",
              "--config","/home/operator/.openai4s/mhs.json"],
   "env":{"PYTHONPATH":"/abs/MHS/sdk/src"}},
  {"id":"mhs-conveyor","name":"conveyor workcell","transport":"stdio","enabled":false,
   "command":["/usr/bin/python3","-m","mhs.mcp","--command","python3 -m mhs.reference conveyor --stdio",
              "--config","/home/operator/.openai4s/mhs.json"],
   "env":{"PYTHONPATH":"/abs/MHS/sdk/src"}}
], "enabled": false, "experimental": true, ...}
```

- `--config` is how the deployment policy (`enabled`, `allow_hardware`)
  reaches the projection. Dropping it was HOST-001, where enabling the
  connector silently discarded the hardware restriction. `connector_entry`
  always emits it.
- OpenAI4S starts every MCP connector with a least-privilege environment (no
  inherited `PYTHONPATH`). When `mhs` is imported from a source tree, the row
  carries `env.PYTHONPATH` with that tree; with an installed `openmhs` it
  carries none.
- A row never carries `--operator-tools`: `mhs__reset` and `mhs__permit` are
  not listed to the model.

Add the rows to OpenAI4S's connector store (`mcp-config --write`, or `enable`).
OpenAI4S then sees one tool per (device, capability), named
`mhs__<device>__<capability>` (for example
`mhs__lab_liquid_handler__fluid_transfer`), plus `mhs__devices`,
`mhs__inspect`, `mhs__read`, `mhs__safety`, `mhs__operations`,
`mhs__evidence` and `mhs__estop`. The projection opens its own sessions with
the principal `agent:mcp/openai4s` and refuses a `session_id` it did not open
(`MHS.SESSION.UNKNOWN`). Its tool table and flags are in
`MHS/sdk/docs/mcp-projection.md`.

### 4.1 Policy enforced by `mhs.mcp` (HOST-001)

`mhs.mcp --config <settings.json>` loads the same document as `MHSConfig`.
Defaults are fail-closed: missing `enabled` means disabled; missing
`allow_hardware` means hardware is refused.

| Tool | `enabled=false` | `enabled=true`, `allow_hardware=false`, device `mode=hardware` | `allow_hardware=true` |
|---|---|---|---|
| capability tool `mhs__<device>__<cap>` | refused `MHS.AUTH.FORBIDDEN` | refused `MHS.AUTH.HARDWARE_DISABLED` | may proceed (endpoint limits, permits, interlocks still apply) |
| `mhs__read` | refused | refused | allowed |
| `mhs__operations` | refused | refused (device-scoped, and endpoint-wide when a hardware device exists) | allowed |
| `mhs__devices`, `mhs__inspect` | refused | allowed (discovery) | allowed |
| `mhs__safety` | refused | allowed (observation) | allowed |
| `mhs__estop` | refused | allowed (software safety envelope) | allowed |
| `mhs__evidence` | refused | allowed (summary; the bundle is the resource `mhs://<endpoint>/evidence`) | allowed |
| `mhs__reset`, `mhs__permit` on an agent row | not listed; refused `MHS.AUTH.FORBIDDEN` | not listed; refused `MHS.AUTH.FORBIDDEN` | not listed; refused `MHS.AUTH.FORBIDDEN` |
| `mhs__reset` on the operator route (4.3) | refused | allowed | allowed |
| `mhs__permit` on the operator route (4.3) | refused | refused `MHS.AUTH.HARDWARE_DISABLED` | allowed |
| `tools/list` | empty | tools advertised; hardware capability tools carry `x-mhs.hardware_disabled` | all advertised |
| `resources/read` | refused | hardware resource refused | allowed |

Every refusal is a coded MCP tool error (`isError=true` with
`structuredContent.mhs_error.mhs_code`), never a transport error, and is made
before a session is opened.

### 4.2 Trusted emergency stop (HOST-002, needs the core patch)

1. `mcp_call` with `tool="mhs__estop"` on an enabled MHS connector is exempt
   from `PermissionBroker.gate`, so a denied or unavailable ordinary approval
   does not block it. The named `mhs_emergency_stop` host action is the same
   route.
2. `MCPService` still requires the connector row to exist, be enabled and
   launch `mhs.mcp`. The adapter resolves the settings document named by the
   row and requires the endpoint to be configured and the device to be on
   `estop_devices` (or discovered on that configured endpoint).
3. Only `mhs__estop` is exempt. Ordinary MHS commands, discovery and read
   tools, and every non-MHS connector keep the ordinary approval gate; a
   non-MHS connector naming `mhs__estop` is not trusted.
4. The request and result are appended to the hash-chained host ledger, and
   the dispatcher's `host_call_log` records the action as `external_write`.
5. A hardware-only e-stop is refused: the host must present the `physical_ref`
   and must not claim to stop it.

`openai4s_mhs.emergency_stop(endpoint_id, device_id, reason, config=None)`
uses the same policy and ledger code without the core patch.

### 4.3 The host operator route: resets and permits

Releasing an e-stop latch and approving a permit are human decisions, so the
model never gets them:

- agent rows never carry `--operator-tools`, so `mhs.mcp` does not list
  `mhs__reset` or `mhs__permit`;
- the governed host route refuses both on an MHS row with
  `MHS.AUTH.FORBIDDEN` (`policy: "operator_route_only"`) before any endpoint
  call, even if the settings document sets `operator_tools`;
- the developer overlay's `mhs_safety` tool has no `reset` action.

`openai4s_mhs.operator_route.OperatorRoute` is the host operator route: a
dedicated `mhs.mcp --operator-tools` connection that host code opens for a
named operator. It is never a connector row. With `operator_token_file` set,
it authenticates to an HTTP endpoint with that bearer token (`--token-file`),
so an endpoint that binds principals to tokens attributes the reset to the
operator; a strict hardware endpoint lets only an authenticated operator reset.
Every request, result and refusal goes to the host ledger (`operator_*`
records with the operator's name).

```python
from openai4s_mhs import MHSConfig
from openai4s_mhs.operator_route import OperatorRoute

config = MHSConfig.load()
with OperatorRoute("lab", config, operator="human:alice") as route:
    route.reset("liquid-handler", reason="spill cleaned up")
    permit = route.permit("liquid-handler", "cap.fluid.transfer.v1",
                          {"source_well": "A1", "destination_well": "B1", "volume_ul": 25})
    route.invoke("liquid-handler", "cap.fluid.transfer.v1",
                 {"source_well": "A1", "destination_well": "B1", "volume_ul": 25},
                 permit_id=permit["permit"]["permit_id"])
```

A permit is bound to the session and principal that requested it, so the
permitted command runs on the same operator connection (`route.invoke`, with
the same journal and ledger as the agent route). On the CLI:

```bash
python3 -m openai4s_mhs safety reset liquid-handler --endpoint lab --operator human:alice
```

It shows the target and asks the operator to type `reset`. Without an
interactive terminal it exits 4 and sends nothing; an unconfirmed reset exits
1; a completed reset exits 0. Without `--endpoint` the device is looked up on
every configured endpoint, as `safety estop` does.

The terminal check and the typed `reset` guard against accidental and
non-interactive use. They are not authentication: any pty-backed shell, an
agent's included, passes them. On a hardware endpoint the control is the
operator token. Set `operator_token_file` and serve the endpoint with that
operator token (strict mode refuses resets from anyone else). A missing or
unreadable `operator_token_file` is a settings error (`MHS.HOST.CONFIG_REQUIRED`,
exit 2), and nothing is sent.

### 4.4 Governed invocation and host evidence (HOST-003/HOST-004, needs the core patch)

For an MHS connector row, the stock `CallMCPTool` → `HostDispatcher` →
`MCPService.call` route is governed at that seam: `openai4s/host/mcp.py` calls
`openai4s_mhs.hostroute`, which wraps the row's **own** `MCPManager.call_tool`
(not a second connection). Non-MHS connectors and the MHS discovery, read and
e-stop tools keep their ordinary path.

- **Journal:** `allocated → prepared → dispatching → terminal`
  (`completed`/`receipt`/`tool_error`/`pre_send_error`), `unknown`, or
  `in_flight`. The reconciliation gate runs for generated *and*
  caller-supplied command ids; only a verified same-id/same-action/same-device
  replay is exempt. A `dispatching` record with no terminal record is
  reconstructed as UNKNOWN after a reload or a crash. A torn or corrupt tail
  fails closed with `MHS.HOST.JOURNAL_CORRUPT`.
- **UNKNOWN:** a lost MCP reply after dispatch, an `unknown` receipt, and an
  `isError` result whose `mhs_error` says `may_have_effect: true` (or whose
  code is `MHS.OUTCOME.TIMEOUT`/`MHS.OUTCOME.UNKNOWN`: the projection sent the
  command and lost the answer) are UNKNOWN: `reconcile_required`, never
  `retry_safe`. An `isError` result for a call that never ran (a policy
  refusal, a lapsed session the projection renewed) stays a retry-safe tool
  error.
- **Long-running work:** a `running` or `accepted` receipt is journaled
  `in_flight` with its `operation_id`, and the model gets the receipt with its
  operation handle. No new command on that device starts until the operation
  is settled: the next governed call on the same connection reads it with
  `mhs__operations {operation_id}` and closes it when it is final
  (`command_reconcile`, `source: "operations.get"`); otherwise `reconcile()`
  closes it from the endpoint evidence. The `deadline_ms` sent to the endpoint
  is 20 % (at least 250 ms) shorter than the transport timeout, so a
  `running` or `unknown` receipt arrives before the MCP client gives up.
- **Reconciliation:** `reconcile()` takes two observations and closes a
  command only when both show the same terminal receipt or operation. The
  endpoint evidence chain (session independent) is checked first; operations
  are a fallback. Anything less is `inconclusive` and the gate stays shut.
- **Host ledger:** append-only `seq`/`prev_digest`/`digest` chain over
  `sha256(JCS(record without digest) || prev_digest)`, recording endpoint,
  device, capability, command id, input digest, approvals/denials, receipt
  digest and timestamp (including `unknown`, `in_flight` and `pre_send_error`
  outcomes). Writes are serialized by a file lock keyed by the normalized path
  (plus a per-path thread lock). A corrupt chain fails closed
  (`MHS.EVIDENCE.CHAIN_BROKEN`) without rewriting bytes.
- **Endpoint evidence:** after every governed host-route command, the
  endpoint evidence bundle is exported through the same transport
  (`mhs__evidence {"include_bundle": true}`; the host route's transport has no
  `resources/read`), verified, and its head, count and digest are appended to
  the host ledger (`endpoint_evidence`). The direct entry points read the
  bundle as the MCP resource `mhs://<endpoint>/evidence` and verify it locally.
  `openai4s_mhs.hostroute.export_host_package()` combines the host chain and
  the endpoint bundle for offline `verify_package()`.

A `.lock` sidecar appears beside each journal and ledger file; it is not part
of the chain.

> **Idempotent replay.** `mhs.mcp` declares `command_id` in each capability
> tool's `inputSchema`; replaying the same command with the same input returns
> the retained receipt instead of executing a second action. A `retryToken` or
> a `command_id` that is not a ULID is mapped to a deterministic ULID.

---

## 5. Optional developer overlay (CLI/debugging; not the integration path)

```bash
# PYTHONPATH as in section 3.  install() is idempotent, registers nothing while
# the integration is disabled, and never connects at import time.
MHS_ENABLED=1 python3 -c "from openai4s_mhs import install; print(install())"
```

To install the overlay automatically in a distribution, apply the optional
hook to an OpenAI4S clone at the base commit (never to `work/openai4s-src`):

```bash
git -C <your OpenAI4S clone> apply "$PWD/integration/openai4s/openai4s-mhs.patch"
```

`install()` registers eight `Tool` subclasses and the matching
`HostDispatcher` `_m_mhs_*` methods, then extends
`BUILTIN_CONTROL_HOST_METHODS` in both `openai4s.tools.registry` and
`openai4s.host_dispatch` (the dispatcher's conflict rule needs both). Each
dispatcher gets its own lazy `MHSHost`; nothing connects until the first call.

| Tool | Mutating | Approval | Side effect | Purpose |
|---|---|---|---|---|
| `mhs_devices` | no | — | `read_only` | Every device, with endpoint, mode, risk, capabilities and fidelity gaps |
| `mhs_inspect` | no | — | `read_only` | Full manifest: safety envelope, permit patterns, resources |
| `mhs_read` | no | — | `read_only` | Resource state under a one-capability session |
| `mhs_command` | yes | **yes** | `high_risk` | Invoke a capability; returns the receipt |
| `mhs_operations` | yes | — | `external_write` | `get` / `list` / `cancel` an operation |
| `mhs_safety` | yes | **no** | `high_risk` | `status` / `estop` (an e-stop is never approval-gated; no reset) |
| `mhs_evidence` | yes | — | `workspace_write` | `export` / `verify` / `ledger` |
| `mhs_connect` | no | — | `read_only` | List endpoints / discovery only |

What the descriptions teach the model:

- every result carries **mode** (`simulated` / `hardware` / `replay`) and the
  manifest's **fidelity gaps**; a simulator is never presented as hardware;
- a command returns a **receipt** (`completed` / `rejected` / `failed` /
  `accepted` / `running` / `unknown`); a refusal is evidence, not a transport
  error;
- `status: "unknown"` is a hard stop: re-read state (`mhs_read`) and reconcile
  before any retry. The host never retries automatically;
- `requires_permit` capabilities are approved by the host policy (`R0`/`R1`
  simulated only by default), then a permit is issued bound to the exact
  `input_digest`.

### CLI

```bash
export PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src
python3 -m openai4s_mhs devices
python3 -m openai4s_mhs inspect liquid-handler
python3 -m openai4s_mhs read liquid-handler --resource plate
python3 -m openai4s_mhs call liquid-handler cap.fluid.level.v1 --input '{"well_ids":["A1","B1"]}'
python3 -m openai4s_mhs safety status liquid-handler
python3 -m openai4s_mhs safety estop liquid-handler --reason "operator stop"
python3 -m openai4s_mhs safety reset liquid-handler --operator human:alice   # asks you to type: reset
python3 -m openai4s_mhs evidence export --endpoint lab --out /tmp/lab-evidence.json
python3 -m openai4s_mhs evidence verify --endpoint lab --bundle /tmp/lab-evidence.json
python3 -m openai4s_mhs evidence ledger --limit 20
python3 -m openai4s_mhs endpoints
python3 -m openai4s_mhs mcp-config
python3 -m openai4s_mhs core-patch check
```

Every verb except `demo` accepts `--json` for a single-line result; the
endpoint and settings verbs take `--config PATH`, and the endpoint verbs
`--endpoint ID-or-URL`. Exit codes:

| Verb | 0 | 1 | 2 | 3 | 4 |
|---|---|---|---|---|---|
| endpoint, settings and evidence verbs | ok | — | any error (`mhs_code` on stderr, or `{"error", "mhs_code"}` with `--json`) | — | — |
| `safety reset` | latch released | reset receipt not `completed`, or not confirmed | usage or settings error | connector or endpoint unreachable | no interactive operator, `MHS.AUTH.*` |
| `core-patch check` | applies, no drift | does not apply, or drifted | git or checkout missing | — | — |

An interrupt exits 130. `safety reset` needs the OpenAI4S MCP client and
`core-patch` needs git; the other verbs talk to `MHSHost` directly and do not
import OpenAI4S (the `read` fallback loads `openai4s_mhs.tools` only for
domain-only manifests).

---

## 6. Acceptance demo

```bash
python3 integration/openai4s/demo/run_demo.py
```

No LLM key and no environment variables. The demo plays the operator: it
writes its own temporary settings document, launches `mhs.reference lab
--port 0` and `arm --port 7400` (falling back to a free port), configures the
conveyor as a stdio endpoint spawned by its connector, and drives all three
through **one** OpenAI4S `MCPManager` whose connectors use the operator
route's command line (`--operator-tools`), because it issues a permit and
resets an e-stop:

1. discovers 3 endpoints / 5 devices / 27 capabilities and discloses modes,
   fidelity gaps and risk classes;
2. reads pipette, mover, reader, conveyor and arm state;
3. runs a lab workflow: pipette transfer A1→B1 25 µL, plate moved to the
   reader, absorbance measured on B1;
4. steps the conveyor, runs a permit-gated diverter actuation, and moves the
   arm to `[25, 40]` degrees;
5. injects a lost receipt, receives `status: "unknown"`, and re-reads state
   before any retry;
6. e-stops the conveyor, receives a **rejected** receipt for the next step,
   resets, and shows that operation resumed;
7. exports (MCP `resources/read`) and verifies all three evidence chains
   offline;
8. replays the lab transfer through a second `MCPManager` connection,
   matching the receipt by `command_id`.

Expected tail:

```
[PASS] mcp_interop: same lab endpoint via MCPManager: mhs__lab_liquid_handler__fluid_transfer returned the native command_id 01...
[PASS] evidence_verified: three endpoint evidence chains exported and verified offline
[PASS] receipt_ledger: host ledger holds 12 receipts; demo recorded 12
checkpoints: 17/17 passed
receipts: 12 | evidence head: sha256:...
ACCEPTANCE: PASS
```

Exit code 0 means every checkpoint passed. `demo/demo-report.json` holds
`endpoints`, `devices`, `tool_calls`, `receipts` (with `command_id`,
`receipt_id`, `status`, evidence digest), `evidence` heads per endpoint, `ok`
and `checkpoints`, with repository-relative paths only. A missing SDK piece is
reported as a failed checkpoint; every wait is bounded.

---

### 6.1 With a model: the OpenAI4S simulated lab

The acceptance demo above needs no model. OpenAI4S's optional
`openai4s/mhs_lab` package (OpenAI4S 1.0, which pins this repository as the
`third_party/OpenMHS` submodule) runs the same
reference host with a model in the loop: two simulated instruments written as
`mhs.driver` packages (an enzyme-inhibition assay workstation and a flow
reactor with inline HPLC) and the registry driver
`MHS/drivers/robots/xarm-developer__xarm-python-sdk` on its fake backend,
reached through three access paths at once (MCP connector over HTTP, native
`mhs_*` tools over HTTP, MCP connector over stdio). Its workbench shows a Lab
tab beside the Notebook that reads every endpoint's `--state-dir` evidence
chain and lets the human operator e-stop and reset. Any package of the device
market (`MHS/drivers/market.json`) can be added with `openai4s lab add <id>`,
through either the MCP connector or the native tools. See OpenAI4S's
`docs/openmhs.md`, section "Simulated lab and the Lab panel".

## 7. Tests

```bash
python3 -m unittest discover -s integration/openai4s/tests -t integration/openai4s -v
```

No environment variables are needed: `tests/__init__.py` puts the three
source trees on `sys.path` and exports them on `PYTHONPATH` for child
processes, sets `PYTHONDONTWRITEBYTECODE=1` for the whole run, isolates
`OPENAI4S_DATA_DIR`, drops `MHS_CONFIG`/`MHS_ENABLED`/`MHS_ENDPOINTS`, and
opts into the documented headless approval policy
(`OPENAI4S_UNATTENDED_APPROVAL=allow`). OpenAI4S starts MCP connectors with a
least-privilege environment, so test rows declare `PYTHONPATH` and
`PYTHONDONTWRITEBYTECODE` in their `env` (`host_remediation_support.connector_env`).
The project's GREEN gate runs the same suite as
`PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src python3 -m unittest discover -s integration/openai4s/tests -t integration/openai4s`.

- `test_install.py`: idempotent install, tool names/schemas/flags, both
  `BUILTIN_CONTROL_HOST_METHODS` frozensets, lazy host property;
- `test_config.py`: settings parsing, endpoint selection, connector rows;
- `test_host.py`: hardware gate, approval and permit bound to `input_digest`,
  unknown outcome, e-stop rejection receipt, ledger and evidence chain;
- `test_dispatcher.py`: `d("mhs_*", [spec])` through `HostDispatcher` against
  an in-process fake endpoint, including the refused `mhs_safety` reset;
- `test_cli.py`: `mcp-config`, `endpoints`, unreachable endpoints, settings
  verbs;
- `test_mcp_interop.py`: real `MCPManager` against `mhs.mcp`, replay by
  `command_id`;
- `test_host_policy.py`: HOST-001 matrix over raw MCP for agent rows and the
  operator route's command line;
- `test_emergency_stop.py`: HOST-002 trusted e-stop under a denying approval,
  allow-list refusals, agent reset refused, operator reset;
- `test_stock_host_route.py`: HOST-002/003/004 on the patched production
  `HostDispatcher`/`MCPService` with a real `mhs.mcp` child (skipped, with the
  reason, on an OpenAI4S tree without the core patch);
- `test_operator_route.py`: operator route reset/permit/ledger, the operator
  token, host-route refusal of the operator tools, CLI terminal rules;
- `test_core_patch.py`: patch header, applies at the base commit (temporary
  `clone --shared`), no drift, overlay hook;
- `test_governed_outcomes.py`: `may_have_effect` errors are UNKNOWN, renewed
  sessions stay retry-safe, `running`/`accepted` receipts are in flight,
  endpoint deadline margin (scripted transport);
- `test_long_running.py`: a real long-running endpoint through `mhs.mcp`:
  in-flight gate, settlement through `operations.get`, reconcile from evidence;
- `test_mcp_invoke.py`, `test_host_journal_recovery.py`,
  `test_host_ledger_concurrency.py`, `test_host_evidence.py`: HOST-003/004
  journal, recovery, ledger concurrency and evidence package.

The SDK suite tests the projection itself (`MHS/sdk/tests/surfaces/`).

---

## 8. Security notes

- **Approval.** An ordinary MHS capability call through `CallMCPTool` is
  approval-gated by OpenAI4S's permission broker; only the device-bound
  `mhs__estop` is exempt (section 4.2). Headless runs fail closed unless the
  operator sets `OPENAI4S_UNATTENDED_APPROVAL=allow` or records a standing rule.
- **Operator decisions.** Resets and permits exist only on the host operator
  route (section 4.3). The CLI reset asks for a typed `reset` at an interactive
  terminal, a guard against accidents rather than authentication; on hardware
  the endpoint's operator token (`operator_token_file`) is the control.
- **Hardware gating.** `mode: "hardware"` devices are refused unless
  `allow_hardware=true`: capability, read, operations and permit calls fail
  with `MHS.AUTH.HARDWARE_DISABLED` before a session is opened; discovery,
  safety status and the software e-stop stay available.
- **Mode disclosure.** Device listings and every tool description expose mode,
  risk and fidelity gaps. A simulated receipt is not a hardware claim.
- **Evidence.** Endpoint bundles are hash-chained and verified offline; the
  host ledger is hash-chained too. A rejected or unknown receipt is chained
  exactly like a success.
- **Unknown outcomes.** No blind retries: an UNKNOWN or in-flight command
  closes the device's gate until it is reconciled.
- **Transport.** stdio endpoints are child processes; HTTP endpoints should
  stay on loopback. MCP connectors get a least-privilege environment plus the
  row's declared `env`; never put credentials in tool results.
- **Safety rating.** The software e-stop is not a safety-rated channel
  (`MHS.SAFETY.NOT_CERTIFIED`); a hardware e-stop stays mandatory.

---

## 9. SDK issues this integration surfaced (fixed in the SDK)

1. **Rejected safety receipts.** The server raised errors for
   e-stop/interlock/permit refusals instead of returning a chained `rejected`
   receipt. The demo's `safety_rejection` checkpoint checks the receipt.
2. **Evidence genesis digest.** An earlier build published the receipt head as
   the genesis digest, so every non-empty bundle failed offline verification.
   `evidence_verified` is the regression check.
3. **MCP `command_id`.** The projection read the idempotency key only from
   `params._meta`, which OpenAI4S cannot send. It now declares
   `arguments.command_id`, so the replay reconciles.
