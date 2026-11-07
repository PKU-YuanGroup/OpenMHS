OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.mattjax16/rigol-dho-mcp

Every fact cites the pinned clone at commit `f9ac7191869845ae46ca714de69a877c388b2530`. The selected source file
`rigol_dho_mcp/server.py` has SHA-256 `c2daec52a875c1eb910606695dab71af6d160d731ac7a14dc1437911e5651190`; gate G7
checks those bytes, the pin, the literal `@mcp.tool()` registration, the argument names and the literal defaults of
every selected tool without importing anything. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| The server creates one FastMCP instance named rigol-dho800 with DNS-rebinding transport security settings. | upstream_code | rigol_dho_mcp/server.py:79-88 |
| RIGOL_ENABLE_SCPI_RAW defaults to 0 (off). | upstream_code | rigol_dho_mcp/server.py:62 |
| The raw scpi_command tool is registered only when RIGOL_ENABLE_SCPI_RAW is true. | upstream_code | rigol_dho_mcp/server.py:608-611 |
| run_control writes one SCPI command (stop is :STOP) and returns the queried :TRIGger:STATus? text. | upstream_code | rigol_dho_mcp/server.py:211-220 |
| get_status returns trigger status, acquisition and timebase strings and stops listing channels at the first channel query error. | upstream_code | rigol_dho_mcp/server.py:161-190 |
| configure_channel writes only the supplied settings and returns no inversion readback. | upstream_code | rigol_dho_mcp/server.py:243-265 |
| Manual cursor positions are seconds for TIME and volts for AMPLitude; with no cursor_type the handler queries the retained type. | upstream_code | rigol_dho_mcp/server.py:378-385 |
| get_measurement writes :MEASure:ITEM before it queries the value; a nonfinite value or one above 9e37 in magnitude is flagged invalid. | upstream_code | rigol_dho_mcp/server.py:452-461 |
| measure_between returns the time offset between edges for Delay items and the phase deviation in degrees for PHase items. | upstream_code | rigol_dho_mcp/server.py:483-487 |
| Memory mode reads deep memory in RAW chunks of 250000 points; the docstring requires a stopped scope but the handler does not check it. | upstream_code | rigol_dho_mcp/server.py:507-545 |
| The returned arrays are decimated with step max(1, n // max_points); time is rounded to 12 and voltage to 6 decimals. | upstream_code | rigol_dho_mcp/server.py:576-582 |
| get_screenshot returns the :DISPlay:DATA? PNG block as an MCP image. | upstream_code | rigol_dho_mcp/server.py:592-600 |
| ScpiClient holds one lock for each single write, query or binary query. | upstream_code | rigol_dho_mcp/scpi.py:156-174 |

## Limits

| input | bound | source | ref |
|---|---|---|---|
| `channel` of configure_channel, get_measurement and get_waveform; `source_a`, `source_b` of measure_between | 1 to 4 | upstream_code | rigol_dho_mcp/server.py:230, 443, 478, 479, 512 (each `Field(ge=1, le=4)`) |
| `max_points` of get_waveform | 10 to 10000 | upstream_code | rigol_dho_mcp/server.py:517 (`Field(ge=10, le=10000)`) |
| scale, offset, probe ratio, trigger level, average count and every cursor coordinate | `Limit.operator_required` | none | the signatures give only descriptions (server.py:232-235, 270-271, 290, 319, 352-353), no enforced range |

The two upstream ranges are the tool's own argument validation, not an instrument specification. The average-count
description "power of 2, 2-65536" (server.py:319) is prose that the signature does not enforce, so it is not used as a
limit. `site-limits.example.json` shows an operator overlay that fills the operator-required bounds; its numbers are an
example bench's choice, not Rigol ranges.

## Scope

All thirteen default tools are bound (server.py:147-600). `configure_cursors` has four bindings: the plain one (mode,
type, sources, no coordinates) and three typed ones that carry coordinates with a unit: TIME in seconds, AMPLitude in
volts, and the retained-type variant, which follows the handler's own order (enter MANual, query the type, apply only
that axis's coordinates and omit `cursor_type`). The optional raw SCPI tool is not exposed.

`get_measurement`, `measure_between` and `get_waveform` write to the scope before they read, so they are declared
effectful. `get_waveform` memory mode needs a stopped acquisition: the binding reads a fresh `get_status` first and
refuses with `MHS.DEVICE.PRECONDITION_UNMET` unless `trigger_status` is `STOP`; it never sends a stop on the caller's
behalf. Waveform and cursor results are complete returned JSON results published as artifacts; the screenshot is a
PNG artifact. A waveform result is the server's decimated, rounded copy, not all raw memory samples.

The e-stop sends `run_control {"action": "stop"}` on the protective lane and then requires a fresh `get_status` with
`trigger_status` equal to `STOP` after every older request has retired. That proves the controlled peer's state only.

## Timing budgets

`request_timeout_ms` 500, `stop_timeout_ms` 500 and the 1000 ms `max_duration_ms` of `get_waveform` and
`get_screenshot` are placeholder budgets of the controlled peer (the `CONTROLLED_*` constants in `driver.py`), not
Rigol timings. The pinned server waits up to 30 s per deep-memory chunk, 15 s per screen read and 20 s for a screenshot
(server.py:544, 547, 599), its socket timeout defaults to 10 s (server.py:61), and one tool issues several SCPI calls.
A native profile would need its own reviewed budgets.

## Risk

R0, checked against the table of `MHS/spec/04-safety.md` section 2.1: R0 is data only with no physical effect, R1
begins with low-energy reversible physical actions. The tools do write instrument state, and R0 does not mean
read-only (same section). Every exposed write sets how the scope acquires, triggers, displays or measures its own
inputs (server.py:211-219, 243-256, 275-279, 296-304, 323-328, 371-390, 454, 493). None sources a signal, moves
anything or dispenses; no output or generator command is exposed, and the raw SCPI tool is off by default and not
bound. The worst outcomes are a wrong configuration, undone by reconfiguring, and the loss of an unsaved on-screen
acquisition (clear, run, single, autoset), which is data loss, not a physical effect.

The channel range 1 to 4 is the tool signature's and the same for every model; the source does not say how a model
with fewer analog channels answers a channel it lacks.

Tags: mcp, oscilloscope, scpi, controlled-peer, native-blocked
