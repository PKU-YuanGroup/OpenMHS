OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.sciencecorp/galago-tools

Every fact cites the pinned clone at commit `7ddf68c7bb7eda0243f6466cfbd6b97fdcfcf782`. Below, `driver.py` is
`tools/opentrons2/driver.py` and `server.py` is `tools/opentrons2/server.py`. The same facts are in the package's
`driver.py` (`facts = [...]`); the reference file is generated from it.

Tags: `opentrons`, `ot-2`, `liquid handler`, `pipetting`, `http`, `galago`.

Author: Claude (claude-opus-5-5, a model and not a human), 2026-11-05, re-authoring the blocked DeepSeek package
(user decision of 2026-11-05: Claude authors, Claude Sonnet reviews). Model-written; `reviewed_by` is null.

## Facts

| fact | source | ref |
|---|---|---|
| Ot2Driver keeps the robot address, the port (default 31950), the current run id, the base URL and the header Opentrons-Version: 2. | upstream_code | driver.py:10-18 |
| ping sends GET /health and raises unless the status code is 200. | upstream_code | driver.py:20-30 |
| upload_and_schedule_protocol posts the file as protocol.py to /protocols, then posts a run of that protocol to /runs and keeps its id as run_id. | upstream_code | driver.py:62-106 |
| start_run posts the run action play to /runs/<id>/actions. | upstream_code | driver.py:108-123 |
| pause_protocol and resume_protocol post the run actions pause and play for the current run. | upstream_code | driver.py:125-165 |
| cancel_protocol posts the run action stop, then deletes the run, only logging a failed delete, and forgets the run id. | upstream_code | driver.py:167-197 |
| get_run_status gets /runs/<id> with a 30 s timeout and returns the JSON body. | upstream_code | driver.py:199-214 |
| wait_for_completion reads data.status every 2 s: succeeded ends it, and stopped, failed or blocked-by-open-door raise. | upstream_code | driver.py:216-241 |
| close cancels an active run and only logs an error. | upstream_code | driver.py:308-315 |
| No requests call of Ot2Driver other than get_run_status passes a timeout. | upstream_code | driver.py:20-197 |
| ABCToolDriver answers any attribute it does not define with a function that returns None. | upstream_code | tools/base_server.py:28-34 |
| The OT-2 tool server's configure step leaves the Ot2Driver construction commented out, so its commands reach the ToolServer's ABCToolDriver. | upstream_code | server.py:24-27 |
| The tool server's RunProgram writes the script with injected variables to a temporary file and runs it with start_protocol. | upstream_code | server.py:98-121 |
| The pack's example OT-2 protocol loads a p300 single-channel pipette, picks up a tip and drops it. | upstream_code | tools/opentrons2/protocols/example.py:86-89 |

## Device choice

The card's earlier entries were the ALPS3000 sealer, the Bravo and the SpectraMax plate reader; the SpectraMax client
has no abort (the earlier review), the ALPS3000 tool has no stop command and the Bravo's shutdown kills the VWorks
process (the earlier package's notes). The pack's OT-2 tool is the one whose work has a stop with a read-back, so the
routing override `MHS/registry/overrides/p3-reauthor-routing.json` re-selects `tools.opentrons2.driver:Ot2Driver`.
Galago's own OT-2 tool server does not construct `Ot2Driver` at this commit (server.py:24-27); this package
constructs a port of it directly (native.py).

## Scope

| capability | requests (upstream lines) | note |
|---|---|---|
| `x-cap.sciencecorp.ot2_run_protocol.v1` (R2) | POST /protocols, POST /runs (62-106); POST /runs/<id>/actions play (108-123); GET /runs/<id> (199-214) | refused (BUSY) while this endpoint's previous run is not succeeded, stopped or failed; play is sent under the stop lock after a cancellation check |
| `x-cap.sciencecorp.ot2_stop_run.v1` (safe state, R2) | GET /runs/<id>; POST /runs/<id>/actions stop (175-181); GET until terminal | no DELETE; with no run of this endpoint, GET /health (20-30) |
| `run_id`, `run_status` (state reads) | GET /runs/<id> | empty strings before the first run |
| e-stop | as the stop action | confirmed by a terminal status within 8 s |

Not covered: pause and resume, toggle_light, take_picture (images), wait_for_completion, the gRPC tool server and every
other tool of the pack.

## Limits

The `protocol` input carries `Limit.operator_required`: the operator's site limits list the exact protocol files (an
allowed set of absolute paths on the driver host) a model may run; `site-limits.example.json` approves one example
path. Nothing else is numeric. The allowed set names paths, not file contents: the match is exact, so a relative path
or a `..` variant of an approved path is refused, but a file changed or replaced after the operator approved its path
runs as it then is. A deployment keeps the approved files where only the operator can write them.

## Safety and stop

R2 (pipetting, MHS/spec/04-safety.md). The e-stop and the safe-state action read the status of the run this endpoint
started; unless it is succeeded, stopped or failed, they send the run action stop and read the status every 0.25 s
until it is one of those, for at most 8 s; otherwise the stop fails, the runtime reports
`MHS.SAFETY.SAFE_STATE_UNREACHED`, keeps the latch and retries. The run is not deleted (`cancel_protocol` deletes it
right after the stop request, which would hide the status). A status of blocked-by-open-door is not terminal: the stop
is still sent. Only the run this endpoint created is stopped; a run of another client is not. `play` is sent under the
stop lock after a cancellation check, so the e-stop never runs between them (one package case checks the cancellation
check, another holds the lock and checks that no play is sent while it is held).

A run this endpoint created but never played (an e-stop during the upload cancels the play) is stopped the same way.
The clone shows neither the status word of a created, unplayed run (the fake's "idle" is a placeholder) nor whether the
robot server accepts `stop` for it. If the server refuses that stop and the run does not read succeeded, stopped or
failed, the stop fails closed (latch kept, retried) and `run_protocol` answers Busy until a stop of that run succeeds;
RESULT.json lists this for the human reviewer.

The upstream's requests have no timeout; the hardware backend is a port of `Ot2Driver` (native.py) that sends the same
requests with a connect and a read timeout and adds one method, `stop`, the first request of `cancel_protocol` alone.
Gate G7 reports `stop` as `MAYBE_ABSENT`: the upstream class does not define it, and because `ABCToolDriver` answers
any name with a no-op (base_server.py:33-34), calling `stop` on the upstream class itself would silently do nothing;
the status read-back would then fail the e-stop. The hardware backend never builds the upstream class.
