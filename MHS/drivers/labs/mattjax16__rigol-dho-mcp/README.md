# Exemplar: gh.mattjax16/rigol-dho-mcp (a config-only McpClientDriver)

The MCP-client family exemplar. The upstream repository is a FastMCP server for Rigol DHO800/DHO900 oscilloscopes
(`rigol_dho_mcp/server.py`); its thirteen default tools become sixteen finite `McpClientDriver` bindings. The
package declares an R0 `hardware` device and runs on its fake backend only: `McpClientDriver` refuses every
non-fake backend before any import, process start or connection, so the evidence is `contract_checked` and never
an MHS-Device level. `driver.lock.json` keeps `authored_by` kind `model` and `reviewed_by: null`. The declaration
follows the structure of the SDK's controlled fixture `MHS/sdk/tests/fixtures/mcp_rigol` for the same pinned source;
this package adds the real task card and clone, `x-cap.mattjax16.*` ids, source facts, an example overlay and
repository tests.

## Run the gate

```sh
PYTHONPATH=MHS/sdk/src python3 -m mhs.driver check MHS/drivers/labs/mattjax16__rigol-dho-mcp --backend fake
```

## What it demonstrates

| Pattern | Where |
|---|---|
| `mcp_config.source`: one exact source file, its SHA-256, the pinned commit and the literal decorator receiver (`mcp` of `@mcp.tool()`); G7 proves registration, argument names and literal defaults from these bytes | `CONFIG` in `driver.py` |
| One `tools` entry per selected tool: closed input schema, complete output contract (`json`, `text` or `png`), `effectful`, `source_ref` inside the tool function, literal `defaults` | `TOOLS` |
| Effects read from the code, not from the tool name: `get_measurement`, `measure_between` and `get_waveform` write before they read | `EFFECTS` |
| Exactly one primary command per tool, an explicit `Action` per command with the same output schema | `commands`, `actions` |
| Argument projection (`arguments` with `input` / `const`) and a source-cited typed selection (`select`) to give one source argument separate unit-bearing bindings | `CURSOR_TIME`, `CURSOR_AMPLITUDE`, `CURSOR_CURRENT` |
| A source-documented precondition as a fresh read-only observation (`prerequisite`), never an implicit stop | `TOOLS['get_waveform']['prerequisite']` |
| Upstream limits from the tool's own argument validation (`Field(ge=1, le=4)`), and `Limit.operator_required` where the signature gives only a description | `channel()`, `numeric()`, `site-limits.example.json` |
| Large complete results as artifacts: JSON (`artifact: true`, `array_counts`, `arrays_if`) and PNG (`kind: png`) | `get_waveform`, `get_cursor_values`, `get_screenshot` |
| The protective transaction: a declared stop tool plus a read-only observation whose fresh value proves the safe state | `CONFIG['safety']` |
| A read-only resource field from an argument-free JSON tool | `reads` |
| A controlled peer that answers `tools/list` and `tools/call` with upstream tool behaviour, and test hooks for error text, discovery drift and a scope that ignores stop | `fake.py`, `test_driver.py` |
| A native factory that refuses | `native.py` |

## Adapting it to another MCP server

Copy the structure, not the content. Read the server's source and list every registered tool; keep the complete
primary result of each (arrays, images) or stop with `NEEDS_ARTIFACTS`. Write each input schema from the function
signature, set `effectful` from what the function body does, cite the function, and bound each number by a line that
shows the bound or by `Limit.operator_required`. Declare `safety` only for a stop tool and a fresh read-only
observation that the code itself provides. The helper proves tools registered by a literal `@<receiver>.tool()`
decorator on a top-level function in one file; other registration styles (`add_tool`, a low-level `Server` with a tool
table) and arbitrary-code tools are outside it today. See `RESULT.json` notes for what this package does not cover.

## Files

| File | Role |
|---|---|
| `task.json` | the registry task card (input; a copy of `MHS/registry/tasks/labs/mattjax16__rigol-dho-mcp.json`) |
| `driver.py` | the `RigolDhoMcp` declaration: `mcp_config`, `commands`, `actions`, `reads`, facts |
| `fake.py` | `ControlledPeer`, the controlled MCP peer used by the fake backend |
| `native.py` | the hardware factory; it refuses |
| `facts.md` | facts, limits and scope with their sources |
| `site-limits.example.json` | an example operator overlay for the operator-required bounds |
| `test_driver.py` | the gate call plus eight repository cases (seven through the stock loader and server, one native refusal) |
| `driver.lock.json` | pinned upstream, install, backends, `authored_by`, `reviewed_by` |
| `reference.json`, `REFERENCE.md` | generated: `python3 -m mhs.driver reference <dir>` |
| `RESULT.json` | `pass` with the gate digest, notes and catalogue requests |

## Honest limits of this package

- The fake speaks the SDK's controlled MCP profile. A real FastMCP server lists pydantic-generated input schemas
  (titles, `anyOf` with null, defaults) and can add `structuredContent` to string results; the bridge refuses both, so
  this package cannot drive the real server as it is. The native path also lacks server-process ownership, whole-tool
  retirement and an instrument-level stop readback beyond the tool's own status query.
- `run_control stop` plus a fresh `trigger_status` of `STOP` is the safe state the controlled peer can show. Whether
  a real DHO stops acquisition on `:STOP` was not run.
- The fake's numbers (channel settings, samples, the 3 x 2 PNG) are placeholders, not Rigol captures; a real screen
  capture and a deep-memory waveform are far larger.
- The timing budgets (500 ms per request and stop, 1000 ms for a waveform or screenshot operation) are the
  controlled peer's placeholders. The pinned server allows up to 30 s per deep-memory chunk and 20 s per screenshot
  (server.py:544, 599); a native profile needs its own budgets.
- R0 is argued in `facts.md` (Risk): the tools write instrument settings, but none sources a signal or moves
  anything.
- `check-report.json` is regenerated by every gate run and is not part of the package.
