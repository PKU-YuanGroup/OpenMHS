# MCP projection (`mhs/mcp.py`)

`python3 -m mhs.mcp` is a stdlib-only stdio MCP server in front of one MHS
endpoint. Any MCP host (Claude Code, Cursor, an agent framework, OpenAI4S's
`MCPManager`) drives the endpoint's capabilities through it. The projection
holds the MHS sessions and the host policy; the model only sees tools.

OpenMHS is an independent open-source project, not affiliated with or endorsed
by Anthropic.

## Launch

```bash
export PYTHONPATH=MHS/sdk/src
python3 -m mhs serve MHS/sdk/examples/thermostat --mcp           # a driver directory, served in the same process
python3 -m mhs.mcp --reference conveyor --test-profile          # built-in reference endpoint
python3 -m mhs.mcp --command "python3 -m mhs.reference conveyor --stdio"
python3 -m mhs.reference conveyor --port 7400 &                  # an HTTP endpoint ...
python3 -m mhs.mcp --endpoint http://127.0.0.1:7400 --config ~/.openai4s/mhs.json   # ... behind a host policy
```

`mhs serve <driver-dir|mhs-adapter.json|conveyor|lab|arm|replay> --mcp` loads
the driver in strict mode (fake backend unless `--backend`; see
[cli.md](cli.md)) and serves the projection on stdin/stdout. Its policy
options are `--mcp-config PATH`, `--operator-tools` and
`--allow-external-sessions`, with the meanings below. `--allow-hardware` only
lets a hardware backend start; the projection still refuses hardware
actuation unless its policy document sets `allow_hardware: true`.

| Option (`python3 -m mhs.mcp`) | Meaning |
|---|---|
| `--endpoint URL` / `--command CMD` / `--reference NAME` | the endpoint (exactly one) |
| `--config PATH` | host policy document (below). Without it: enabled, every other flag false |
| `--operator-tools` | list `mhs__reset` and `mhs__permit` (a connector a human operator drives) |
| `--allow-external-sessions` | accept a `session_id` the projection did not open |
| `--token-file PATH` | bearer token for `--endpoint`; the endpoint binds the session principal to it |

stdout carries one JSON-RPC object per line (at most 4 MiB); diagnostics go to
stderr. Both launchers describe every input property (type, unit, enforced
limit).

## Host policy

The `--config` document is the integration settings JSON. Only a JSON `true`
enables a flag; a missing document means every flag is false.

| Flag | When false (default) |
|---|---|
| `enabled` | every `tools/call` is refused with `MHS.AUTH.FORBIDDEN`, `tools/list` is empty, `resources/read` is refused; no endpoint call is made |
| `allow_hardware` | on `mode: "hardware"` devices the capability tools, `mhs__read` and `mhs__operations` refuse with `MHS.AUTH.HARDWARE_DISABLED`; discovery, `mhs__safety`, `mhs__estop` and `mhs__evidence` stay available |
| `operator_tools` | `mhs__reset` and `mhs__permit` are not listed and refuse with `MHS.AUTH.FORBIDDEN` (`policy: "operator_tools=false"`). Resetting an e-stop and approving a permit are human decisions |
| `allow_external_sessions` | a `session_id` argument the projection did not open is refused with `MHS.SESSION.UNKNOWN` |

The endpoint enforces its own rules in addition (limits, interlocks, permits,
arming, operator-only reset in strict mode). `MHS_ENABLED=0|1` overrides
`enabled` for one process.

## Tools

Capability tools are named `mhs__<device_slug>__<capability_slug>` (MHS-008
TPT-030 slug rules, at most 63 characters, collisions fail closed). The names
are stable: `MHS/sdk/tests/surfaces/test_mcp_tools.py` holds the snapshot for
the conveyor, lab and arm reference endpoints.

| Tool | What it does | Annotations |
|---|---|---|
| `mhs__<device>__<capability>` | one `mhs.command`; returns the receipt | `readOnlyHint` for read verbs; `destructiveHint` for non-read calls on R2/R3 or hardware/hybrid devices; `idempotentHint` for read and write verbs; `openWorldHint` on hardware/hybrid |
| `mhs__devices` | compact list: id, name, mode, risk class, resources, tool names | read-only |
| `mhs__inspect` | one device's manifest with its reference file and `x-mhs-effective-limits` | read-only |
| `mhs__read` | one resource's state (`device_id` optional when the resource id is unique) | read-only |
| `mhs__safety` | risk class, e-stop latch, interlocks, permits, safe state | read-only |
| `mhs__operations` | list this connector's operations; `operation_id` (+ `wait_ms` <= 60000) reads one; `cancel_operation_id` cancels one | |
| `mhs__evidence` | `count`, `head_digest`, `valid`, `verify`, the last `last_n` receipts (default 10, max 50) or the receipts of one `command_id`, and `uri` of the full bundle | read-only |
| `mhs__estop` | latch the e-stop of one device; never waits for a session or an approval | |
| `mhs__reset` | operator tool: reset the latch | listed only with `operator_tools` |
| `mhs__permit` | operator tool: issue a permit bound to the exact input | listed only with `operator_tools` |

A capability tool description (at most 2048 bytes) states the mode and risk
class, the limits the endpoint enforces (`ticks 1..10000`), the interlocks the
call needs, the permit requirement, long-running behaviour and the device
facts, all from `mhs.devices.get` (the reference file). Per-element bounds are
listed by position (`a [-1..1, -2..2]`) or, when that is shorter, by value with
the element indices that share it (`action.ctrl[0-3,22-25] -87..87, [21] 0..255`;
`action.ctrl[*] -1..1` when every element has the same bounds), and rules on
single elements of one array (`action.ctrl[7]`) are merged the same way, so a
model with a hundred actuators stays within the bound. `x-mhs` and
`_meta["openmhs/capability"]` carry `{capability_id, device_id, resource, verb,
risk_class, mode, determinism, requires_permit, mhs_version}`.

`inputSchema` is the capability input schema plus five optional control fields:
`session_id`, `command_id`, `expected_revision`, `permit_id` and `deadline_ms`.
The served projection (`python3 -m mhs.mcp`) gives every input property a
description with its type, unit and enforced limit; `MCPProjection(client)` in
process keeps the schema as the driver wrote it (`describe_inputs=False`), which
is what the driver gate (G8) checks.

## Calls and results

| Situation | Result |
|---|---|
| any receipt (`completed`, `rejected`, `failed`, `cancelled`, `unknown`, `running`) | `isError: false`, `structuredContent.receipt`; `mhs_error` is the receipt's error |
| input that does not match the schema | `isError: true`, text `MHS.CAPABILITY.INPUT_INVALID: <field reasons>`; nothing is sent |
| a value outside an enforced limit | sent; the endpoint answers a `rejected` receipt `MHS.SAFETY.ENVELOPE_VIOLATION` (kept in the evidence) |
| policy refusal | `isError: true`, `MHS.AUTH.FORBIDDEN` or `MHS.AUTH.HARDWARE_DISABLED` |
| the projection's session lapsed | `isError: true`, `MHS.SESSION.EXPIRED` (or `MHS.SESSION.UNKNOWN`, `MHS.SESSION.CLOSED`); the call was not executed and is not retried. `session_renewed` says whether a new session is open (false when reopening failed); re-read state, then call again |
| transport failure | `isError: true`, `mhs_error` with `command_id` (and `may_have_effect`) |
| unknown tool name | JSON-RPC error `-32602` |

A `running`, `accepted` or `unknown` receipt also gets
`structuredContent.operation` (`operation_id`, `status`, and `long_running`,
`deadline_ms`, `max_duration_ms`, `unknown_receipt_id` when the receipt states
them); poll it with `mhs__operations {operation_id, wait_ms}`.

Retries: `_meta.retryToken`, or a `command_id` that is not a ULID, becomes the
deterministic ULID `retry_command_id(token, tool_name)` (the first 16 bytes of
`sha256(tool_name + "\n" + token)`). The same token on the same tool replays
the first receipt instead of acting twice; the same token with another input is
refused by the endpoint. The mapping is scoped by tool name only, and the
endpoint's replay key is `(device_id, command_id)`. A token reused later, in
another conversation or by another agent, therefore replays the earlier receipt
(it never acts twice). Use a fresh token for every new intent.

Sessions: the projection opens one session per (device, capability) for
commands and one device-wide session per device for reads, with principal
`{"kind": "agent", "id": "agent:mcp/<clientInfo.name>"}` and a TTL of 3600 s.
It sends `mhs.session.heartbeat` before a call when less than a third of the
TTL is left, and opens a new session after `MHS.SESSION.EXPIRED`,
`MHS.SESSION.UNKNOWN` or `MHS.SESSION.CLOSED`. Reads (`mhs__read`,
`resources/read`) are retried once on the new session; commands never are.

## Protocol

| MCP method | Behaviour |
|---|---|
| `initialize` | answers the requested `protocolVersion` when it is one of `2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`, otherwise `2025-11-25`; `serverInfo.name = "mhs-mcp:<endpoint_id>"` |
| `ping` | `{}` |
| `tools/list` | the tools above |
| `tools/call` | see above |
| `resources/list` | `mhs://<endpoint>/devices`, `mhs://<endpoint>/evidence`, per device `…/devices/<path>` (manifest) and `…/devices/<path>/reference`, per resource `…/devices/<path>/resources/<id>` (state) |
| `resources/read` | the same documents; works before `resources/list`. The evidence bundle fails once it exceeds the 4 MiB frame |
| `notifications/cancelled` | forwarded to `mhs.operations.cancel`; a call still in flight is found by its `command_id` |
| `_meta.progressToken` | one `notifications/progress` for a receipt with an operation id |

`mhs__estop`, `ping` and `notifications/cancelled` are served on a priority
path: they are answered while a `tools/call` is still in flight on the same
connection. Every other request is served in order.

## Hosts without `resources/read`

`mhs__evidence {"include_bundle": true}` also returns the full bundle as
`bundle`. The argument is accepted but not listed in the tool's `inputSchema`,
so the model only sees the bounded summary. The OpenAI4S reference host uses it
on its governed host route, whose transport has only `tools/call`; its direct
entry points read the resource. The bundle grows with every receipt, so prefer
`resources/read` of `uri`.
