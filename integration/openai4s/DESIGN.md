# OpenAI4S × OpenMHS reference host — design contract

This is the design the reference host implements. It has two layers: **MCP
connector rows** that work on unpatched OpenAI4S, and a **governed host
route** (journal, host ledger, endpoint evidence, trusted e-stop) that needs a
small OpenAI4S core change, recorded in `openai4s-core.patch`. The host is an
informative example for OpenMHS 0.9: another MCP host can follow the same
pattern without any of this code.

## 0. Facts verified against the OpenAI4S source (`work/openai4s-src`)

The checkout is upstream `https://github.com/PKU-YuanGroup/OpenAI4S.git`,
`main` at `f48f216c81fe400444857c8a5d84d7407398918c` (OpenAI4S 0.3.1), with
the change of `openai4s-core.patch` uncommitted. This project only reads it.

- `openai4s/mcp_client.py`: `MCPManager`, `MCPConnection`. The stdio handshake
  is `initialize {protocolVersion: "2024-11-05", capabilities,
  clientInfo: {name: "openai4s", version: "1.0.0"}}`, then
  `notifications/initialized`; `tools/list -> {"tools": [...]}`;
  `tools/call {name, arguments} -> {content: [{type: "text", text}], isError}`;
  `resources/list`, `resources/read {uri}`. Frames up to 4 MiB. A connector
  child gets a least-privilege environment (`PATH`, `HOME`, locale, temp and
  TLS variables, `PYTHONUNBUFFERED`) plus the row's own `env`; `PYTHONPATH` is
  not inherited.
- `openai4s/tools/registry.py`: `REGISTRY` is an ordered list of `Tool`
  objects (`name`, `host_method`, `description`, `parameters`,
  `requires_approval`, `read_only`, `side_effect_class`, `needs_network`,
  `resource_key_prefix`, `execute(runtime, arguments)`).
- `openai4s/host_dispatch.py`: `HostDispatcher` implements the host methods
  tools invoke; `openai4s/permissions.py` `broker().gate(...)` is the approval
  choke point. `CallMCPTool` (`openai4s/tools/mcp.py`) declares
  `requires_approval=True`.
- `openai4s/host/mcp.py`: `MCPService.call` resolves a connector row and calls
  `MCPManager.call_tool`.
- The package is pure stdlib, so the integration is stdlib-only too.

## 1. MCP connector rows — the agent path (no core change)

`mhs.mcp` (in the SDK) is a stdio MCP server that fronts one OpenMHS endpoint.

```jsonc
// ~/.openai4s/mhs.json (integration settings; also the projection's --config)
{"enabled": true, "allow_hardware": false,
 "endpoints": [{"id": "lab", "url": "http://127.0.0.1:7401"}]}
```

```jsonc
// generated OpenAI4S connector row (one per endpoint)
{"connectors": [{
  "id": "mhs-lab",
  "command": ["python3", "-m", "mhs.mcp", "--endpoint", "http://127.0.0.1:7401",
              "--config", "/home/operator/.openai4s/mhs.json"],
  "env": {"PYTHONPATH": "/abs/MHS/sdk/src"},
  "enabled": true
}]}
```

- `--config` is required: `mhs.mcp` reads `enabled` and `allow_hardware` from
  it and refuses hardware capability, read, operations and permit calls unless
  the operator allowed hardware.
- `env.PYTHONPATH` is emitted only when the SDK is a source tree (OpenAI4S does
  not pass `PYTHONPATH` to connector children).
- A row never carries `--operator-tools`, and the settings document must not
  set `operator_tools` or `allow_external_sessions` (both are reported as
  settings warnings). The model therefore never sees `mhs__reset` or
  `mhs__permit`, and a `session_id` the projection did not open is refused.

OpenAI4S's `MCPManager` then discovers tools named
`mhs__<device_slug>__<capability_slug>` plus the discovery and safety tools,
and the model calls them with `call_mcp_tool`. This layer works on unpatched
OpenAI4S, but it is not governed: an `mhs__estop` waits for the ordinary
approval prompt, and nothing is journaled on the host side.

## 2. The governed host route (`openai4s-core.patch`)

The governed route needs OpenAI4S core changes in two files, recorded as
`openai4s-core.patch` (177 insertions, 7 deletions) against the base commit
above:

| Core file | Change |
|---|---|
| `openai4s/host/mcp.py` | `MCPService.call` sends an MHS row (its command runs `mhs.mcp`) to `openai4s_mhs.hostroute.governed_call`, and `mhs__estop` to `hostroute.trusted_emergency_stop`, over the row's own `MCPManager` call; new `is_trusted_estop` and `emergency_stop`; an MHS row whose integration is not importable is refused, never run ungoverned |
| `openai4s/host_dispatch.py` | the named `mhs_emergency_stop` action (audited as `external_write`) and the device-bound `mcp_call` → `mhs__estop` exception from the approval prompt |

`python3 -m openai4s_mhs core-patch check` shows that the patch applies at the
base commit (`git apply --check` in a temporary `git clone --shared`) and still
equals the checkout's diff; `core-patch capture --write` records it again. The
optional `openai4s-mhs.patch` (developer overlay auto-install, one hook in
`openai4s/__init__.py`) is separate and not needed by the governed route.

On the governed route (`hostroute.py`, `mcp_invoke.py`, `emergency.py`,
`host_evidence.py`):

1. **Capability calls** go through `mcp_invoke.invoke_via`: the command id and
   intent are journaled before dispatch; the outcome is a receipt, a tool
   error, UNKNOWN, or in flight. UNKNOWN (a lost reply, an `unknown` receipt,
   or an `isError` result with `may_have_effect: true`) and in-flight work
   (`running`/`accepted` receipts) close the device's gate until they are
   reconciled; in-flight work is settled through `mhs__operations` on the same
   connection.
2. **The host ledger** chains every intent and outcome, the trusted e-stops and
   the operator actions, and records the verified head of the endpoint
   evidence after every command.
3. **The trusted e-stop** skips the approval prompt only: connector
   enablement, the settings document, the endpoint/device allow-list and the
   hardware-only refusal still apply, and the stop is audited.
4. **Operator tools** (`mhs__reset`, `mhs__permit`) are refused on any MHS row
   with `MHS.AUTH.FORBIDDEN` before an endpoint call.
5. Discovery, read, safety, operations and evidence tools and every non-MHS
   connector keep the stock path.

## 3. The host operator route

A reset releases an e-stop latch and a permit approves an action: both are
human decisions. `openai4s_mhs.operator_route.OperatorRoute` opens a dedicated
`mhs.mcp ... --operator-tools` connection for a named operator; it is never a
connector row, so `CallMCPTool` cannot reach it. With `operator_token_file` it
authenticates as the operator (`--token-file`), which a strict hardware
endpoint requires for a reset. Every step is in the host ledger. A permit is
bound to the requesting session and principal, so a permitted command runs on
the same operator connection (`OperatorRoute.invoke`, governed like the agent
route). The CLI form `python3 -m openai4s_mhs safety reset DEVICE --operator
NAME` also requires an interactive terminal and a typed `reset`. That is a guard
against accidental or non-interactive use, not authentication; the operator
token is the control on hardware.

## 4. Optional developer overlay (CLI/debugging)

The `openai4s_mhs` package also carries a native-tool overlay for debugging
the same host API outside MCP:

| File | Responsibility |
|---|---|
| `openai4s_mhs/__init__.py` | `enable`/`disable`/`status`, `install()` (idempotent registration of the tools and dispatcher methods while enabled) |
| `openai4s_mhs/config.py` | `MHSConfig`/`EndpointSpec`: the settings document |
| `openai4s_mhs/host.py` | `MHSHost`: sessions, permits, hardware gate, evidence ledger over the SDK client |
| `openai4s_mhs/tools.py` | 8 `Tool` subclasses (`mhs_devices`, `mhs_inspect`, `mhs_read`, `mhs_command`, `mhs_operations`, `mhs_safety` with `status`/`estop` only, `mhs_evidence`, `mhs_connect`) and the matching `HostDispatcher` methods |
| `openai4s_mhs/cli.py` | `python3 -m openai4s_mhs devices`, `inspect`, `read`, `call`, `safety`, `evidence`, `endpoints`, `mcp-config`, `core-patch`, `enable`, `disable`, `status`, `demo` |

The whole feature is an **experimental MCP integration, disabled by default**
(HOST-066…069): the generated rows carry `enabled: false`, no projected tool is
reachable and no endpoint connection is opened until an operator enables the
feature. Enabling and disabling is an explicit operator action recorded in
settings and, when reachable, in OpenAI4S's connector store.

Rules the host enforces (`MHS/spec/09-host-profile.md`):

1. **Least privilege.** The projection opens one session per (device,
   capability) as the principal `agent:mcp/<client>`; the grant is re-validated
   per command.
2. **Permits and resets** come from the operator (section 3); the overlay's
   `MHSHost` approves only R0/R1 simulated capabilities on its own and binds
   each permit to the command's `input_digest`.
3. **Mode disclosure.** Every tool description and device listing carries
   `mode` and the fidelity gaps; a simulator is never presented as hardware.
4. **Evidence.** Every receipt is chained at the endpoint and recorded in the
   host ledger; both verify offline.
5. **Unknown outcomes** are a hard stop: re-read state and reconcile before any
   retry. No blind auto-retry.
6. **Deadlines.** The endpoint deadline is shorter than the transport timeout,
   so `running` and `unknown` receipts arrive; a deadline never cancels work.

## 5. The demo that defines "unified call"

`integration/openai4s/demo/run_demo.py` (stdlib, no LLM key):

1. Launch reference endpoints: `mhs.reference lab` and `arm` over HTTP, the
   conveyor over stdio (spawned by its connector).
2. Through **one** OpenAI4S `MCPManager` (operator-route connectors, because the
   demo issues a permit and resets an e-stop): discover all devices; read
   state; run a pipette → plate-reader workflow; step the conveyor; actuate a
   permit-gated diverter; move the arm; lose a receipt and re-read state;
   e-stop, be refused, reset, resume.
3. Export every evidence bundle (MCP `resources/read`) and verify it offline.
4. Replay the lab transfer through a second `MCPManager` connection by
   `command_id`.
5. Write `integration/openai4s/demo/demo-report.json` (repository-relative
   paths only).

Acceptance: `python3 integration/openai4s/demo/run_demo.py` exits 0 and the
report shows 3 endpoints, at least 6 capabilities, a rejected safety case, and
verified evidence chains.

## 6. Install (documented, never global)

```bash
export PYTHONPATH=integration/openai4s:MHS/sdk/src:work/openai4s-src

# Connector rows only (no core change): print them, or enable and write them to OpenAI4S's store
python3 -m openai4s_mhs mcp-config --json
python3 -m openai4s_mhs enable

# The governed route: the core patch must apply at its base commit
python3 -m openai4s_mhs core-patch check

# The developer overlay (registers nothing while the integration is disabled)
MHS_ENABLED=1 python3 -c "from openai4s_mhs import install; print(install())"
```

A distribution applies `openai4s-core.patch` (required for the governed route)
and, optionally, `openai4s-mhs.patch` to its OpenAI4S tree at the base commit.
