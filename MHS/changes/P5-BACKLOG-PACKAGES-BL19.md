OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# BL-19: gh.squad-lab/qcdrivers e-stop confirmation

Repair of the passing package `MHS/drivers/labs/squad-lab__qcdrivers` (gh.squad-lab/qcdrivers, device `squad-ad75019-mux`, risk R1). Grok (grok-4.7, a model and not a human) did this repair on 2026-11-05, run `ext-p5-backlog-packages--bl19-20261105`. `authored_by` stays the re-author recorded in `driver.lock.json` (claude-opus-5-5, run `p3-reauthor-qcdrivers`, 2026-11-05). `reviewed_by` stays null. This is not a re-author: the package directory was not moved aside. The pre-change package is in `development/ext-p5-backlog-packages--bl19/originals/MHS/drivers/labs/squad-lab__qcdrivers/`. No SDK, schema, registry, override, or lock file changed.

## The defect

`*RST` in the clone's sketch runs `Clear` (prints `Clear complete`, `firmware.ino:111`), flushes both matrices, then prints `Reset complete` (`firmware.ino:51-56`). The previous driver read until that pair appeared, and stopped at four lines (`RST_MAX_LINES` in the pre-change `driver.py`). After a reset whose `*RST` read timed out, and a connect whose `SWITCH32` read also timed out, those three lines (`Clear complete`, `Reset complete`, `Route added 32x32`) sit unread and the route is closed. The e-stop's own `*RST` is already written. The first two lines are the earlier pair, so the old search confirmed while this `*RST` handler had not run (`REAUTHOR-PHASE-3.md`, review round 1, E3). The line lock is not FIFO; the fix does not depend on making it FIFO.

`viClear` is still not used. `send_command`'s retry calls `self.visa.handle.clear()`, an attribute the class never defines (`mux.py:87-90`), and the driver does not call `send_command`. The constructor does call `visa_handle.clear()` (`mux.py:58`). What a clear does to this sketch's parser, and to bytes already on the wire, is not in the clone, so a reset does not send one to drop unread lines.

## The confirmation rule

`loop` calls `ProcessInput` once per turn (`firmware.ino:43-44`). Each handler this driver uses prints a fixed number of lines before it returns:

| command | lines | sketch |
|---|---|---|
| `*IDN?` | 1 | `firmware.ino:48` |
| `SWITCH32` with two parameters | 1 | `firmware.ino:78` or `firmware.ino:84` |
| `STAT?` with two parameters | 2 | `firmware.ino:98-102` |
| `*RST` | 2 | `firmware.ino:111`, then `firmware.ino:55` |

`driver.py:74-77` names those counts. `firmware.ino:86` is the `SWITCH32` Usage line (line 87 is the closing brace). `STAT?` prints `16x16:` at `firmware.ino:98-99` and `32x32:` at `firmware.ino:101-102`. Before a write, `_write_and_read` (`driver.py:198-232`) asks for the lines still owed plus this command's lines. The `finally` sets `_mux_lines_owed` to the number requested minus the number read, so a timeout keeps the unread lines. A yield before the write leaves the debt unchanged. `_reset_matrix` (`driver.py:278-306`) discards that prefix and accepts only the next two lines when they are exactly `Clear complete` then `Reset complete` (`driver.py:300-305`). Those two lines are printed only after this handler has run `Clear` and both flushes. A pair inside the prefix is an earlier `*RST`. `_exchange` (`driver.py:228-263`) returns the same kind of suffix, so a later `SWITCH32`, `STAT?`, or `*IDN?` does not treat `Clear complete` as its reply. The count lives on the driver instance: releasing the latch does not clear it. A write that never left the host is counted too, and a later confirmation then fails closed.

`stop` (`driver.py:377-380`) is the same `_reset_matrix` with no cancel guard and with `preemptable=False`. `latency_ms` stays 5000. Lines already buffered are skipped with no extra VISA wait. A line that has not arrived still ends that read at the 2000 ms timeout (`mux.py:55`); the attempt fails and the debt remains for the retry. Connect and `reset_matrix` still call `check_cancelled()` under the line lock before they write.

A served `invoke` reads `identity` (`*IDN?`) before and after the action (`Driver.read`, `base.py:470-488`, called from the server's state read). Those lines are the same debt. The direct-driver cases have three owed lines (`*RST` two, `SWITCH32` one). The served cases have seven: four `*IDN?` reads (identity before and after the reset, and before and after the connect), the `*RST` pair, and `SWITCH32`.

## Round 1: the owed-line drain must not hold `*RST`

Review round 1 blocked the package on SAFE-040 and SAFE-028. `_exchange` held `_mux_line_lock` for every owed line. `_reset_matrix` needs that same lock to write `*RST`. A served `client.read("main")` calls `Driver.read` with no cancel context (`server.py:3292` to `_read_state` at `server.py:3324`; `Driver.cancelled` at `base.py:356-364` is false when there is no context). Fifty successful reads at 150 ms each kept `*RST` off the wire until after the 5000 ms budget. The receipt was `MHS.SAFETY.SAFE_STATE_UNREACHED`, route `(1, 2)` was still closed, and `*RST` went out only after the drain finished.

`_yield_prefix_drain` (`driver.py:184-195`) runs while an ordinary exchange is still reading lines owed by earlier commands, and again after the last of those lines (`driver.py:219-227`). It raises `Cancelled` when `check_cancelled()` says so. It raises `_PrefixDrainYield("estop")` when `estop_epoch` has moved since the exchange started. `_engage_estop` (`base.py:584-586`, `bridge/base.py:1772-1775`) advances that epoch before `stop` waits for the lock. It raises `_PrefixDrainYield("hold")` when the prefix has held the line for `_ORDINARY_PREFIX_HOLD_S` (2.0 s, one VISA timeout, `mux.py:55`). `_exchange` (`driver.py:252-260`) turns a hold into `OutcomeUnknown` after an effectful write and `MHS.DEVICE.FAULTED` for a query, and turns the epoch yield into `Cancelled`. The `finally` in `_write_and_read` still sets the debt to the lines requested minus the lines read, once the write has been attempted. A yield before the write does not add this command's lines.

A connect with nothing owed still finishes `SWITCH32` and the `STAT?` read-back, so `*RST` does not fall between those two reads. Round 2, below, is the case where one owed line is left. The e-stop's `_reset_matrix` passes `preemptable=False` (`driver.py:300`). Its first `query` is `*RST`, so the command is transmitted as soon as the lock is free, and the reads after it are this stop's confirmation. A long confirmation can still outlast 5000 ms. The receipt is then unconfirmed, the latch stays, and the route is already clear because the sketch runs `Clear` when `*RST` is received. `latency_ms` stays 5000.

`development/ext-p5-backlog-packages--bl19/originals/` is still the snapshot-6 tree copied before the first edit. It was not overwritten with the round-0 bytes. `PATCH-INDEX.json` before-hashes stay those snapshot-6 digests.

## Round 2: the last owed line

Review round 2 blocked the package again on SAFE-040 and SAFE-028. The yield condition was `len(taken) < prefix`. When the read that finishes the prefix returns, `len(taken)` equals `prefix`, so the check did not run. A served connect whose pre-invoke `*IDN?` had timed out then kept the lock for that `SWITCH32` reply and for both `STAT?` lines. With each successful read at 1.6 s, under the 2000 ms VISA timeout, the 2.0 s hold did not fire either. `client.estop` returned `MHS.SAFETY.SAFE_STATE_UNREACHED` at about 5.1 s with no `*RST` sent and route `(1, 2)` still closed. `*RST` went out at about 6.4 s.

`driver.py:226` now checks when `prefix > 0` and `len(taken) <= prefix`. That is after the last owed line and before this command's own reply. `connect` (`driver.py:346-348`) also does not start `STAT?` when the operation is cancelled or `estop_epoch` has moved since the connect took the lock. The `SWITCH32` reply, if already written and not yet read, stays in the debt. The e-stop's `*RST` reads it as part of the prefix and still confirms on its own pair. The reviewer's fake reproducer, run read-only against this tree, recorded `*RST` at 1.605 s, an empty route, and a completed receipt. A `/tmp` copy that still checked `len(taken) < prefix` recorded `*RST` at 3.210 s on the same package test. That copy read the owed line and the `SWITCH32` reply before `connect` stopped for the new epoch, so `STAT?` did not start. The fixed tree stops before that reply.

## Tests

`test_driver.py`, 27 tests, `python3 -m unittest MHS.drivers.labs.squad-lab__qcdrivers.test_driver`, all passed in 8.814 s. The confirmation cases:

- `test_connect_reads_its_own_line_after_a_timed_out_rst` (`test_driver.py:223`). `driver.call` of reset times out with both `*RST` lines unread (`_mux_lines_owed` is 2). Connect then returns `Route added 32x32` and the route bit, and the debt is 0.
- `test_estop_does_not_confirm_before_its_own_rst_has_run` (`test_driver.py:424`). `_StaleRstThenRoute` (`test_driver.py:24`) runs the timed-out `*RST` and `SWITCH32` (the route ends as `{(1, 2)}`) and leaves `[Clear complete, Reset complete, Route added 32x32]`. The e-stop's `*RST` is written and its handler does not run. `driver.estop` raises `DriverFailed` `MHS.DEVICE.FAULTED`, the route stays `{(1, 2)}`, and two lines stay owed.
- `test_estop_confirms_only_after_its_own_rst_runs` (`test_driver.py:439`). The same prefix, and the handler runs when the third owed line is read. Until that read the route is `{(1, 2)}`. `driver.estop` returns `estop: engaged`, the route is empty, and the debt is 0.
- `test_served_estop_does_not_confirm_on_the_stale_pair` (`test_driver.py:477`) and `test_served_estop_confirms_only_after_its_own_rst_runs` (`test_driver.py:489`). `_WithholdEveryReply` (`test_driver.py:81`) hides every reply, including the `*IDN?` state reads. Reset fails `MHS.DEVICE.FAULTED` with debt 4. Connect is `MHS.OUTCOME.UNKNOWN` with debt 7 and route `{(1, 2)}`. The failure case calls `driver.estop`: a failed `client.estop` starts a background retry (`server.py:4774` sets `retrying`, `server.py:4889-4890` starts the supervisor, first delay `_ESTOP_RETRY_INITIAL_S = 0.25` at `server.py:176`), and that retry would send another `*RST`. The success case calls `client.estop` and the receipt is `completed` with `output.estop` `engaged` only after the handler runs on the seventh line.

The script applies the route when the timed-out `SWITCH32` is written, and runs the e-stop handler only after the owed lines have been read. That is the ordering BL-19 names: the earlier lines are readable, and this handler has not run. On the sketch, those earlier lines are printed before this handler returns, so once the handler has run its pair is after the prefix, which is the slot the driver checks.

Round 1 added three cases. `test_a_slow_reply_drain_does_not_delay_the_estop_rst` (`test_driver.py:502`) serves a completed connect of `(1, 2)`, then forty `driver.identity()` calls whose lines are withheld. A `client.read("main")` then delivers each owed line only after 0.15 s. `client.estop` is called once that read has entered. `*RST` is recorded at the start of its `query`, before the confirmation reads. Those later reads return at once. The receipt is `completed`, `output.estop` is `engaged`, the route is empty, the debt is 0, and `*RST` was transmitted in under 1 s. Forty slow lines with no yield would still be holding the lock when the 5000 ms budget ended. `test_an_ordinary_prefix_drain_releases_the_line_at_the_hold_bound` (`test_driver.py:567`) sets the prefix hold to 0.12 s and delivers twelve owed lines at 0.05 s each, with no e-stop. `identity` fails `MHS.DEVICE.FAULTED` in under 0.45 s, a debt remains, and the line lock can be taken. `test_a_cancelled_exchange_stops_reading_owed_lines` (`test_driver.py:607`) sets the cancel event from the first owed read of a connect. `driver.call` raises `Cancelled` before the eight owed lines are finished, a debt remains, and the lock is free.

Round 2 added `test_one_owed_line_does_not_let_a_served_connect_block_the_estop_rst` (`test_driver.py:646`). The served connect's pre-invoke `*IDN?` times out, leaving one owed line. `SWITCH32` then delivers each following line after 1.6 s. `client.estop` runs once that command has started. `*RST` is transmitted in under 3 s, the route is empty, and the receipt is `completed` with `output.estop` `engaged`. Four reads at 1.6 s would still be inside the lock when the 5000 ms budget ended.

Mutants of copies under `/tmp` (not the tree), each killed by one test:

| mutant | change | test | result |
|---|---|---|---|
| `skip_prior_removed` | `_reset_matrix` uses `prior = 0` | `test_estop_does_not_confirm_before_its_own_rst_has_run` | `DriverFailed` was not raised |
| `search_pair_anywhere` | accept the first `Clear complete`, `Reset complete` pair, as the old four-line search did | same test | `DriverFailed` was not raised |
| `exchange_ignores_debt` | `_exchange` reads only this command's lines and does not skip the prefix | `test_connect_reads_its_own_line_after_a_timed_out_rst` | `OutcomeUnknown`: `SWITCH32` reply was `Clear complete` |
| `off_by_one_skip` | skip `prior - 1` lines | `test_estop_confirms_only_after_its_own_rst_runs` | `DriverFailed`: the slot was `Route added 32x32`, `Clear complete` |
| `yield_removed` | `_yield_prefix_drain` returns immediately | `test_a_slow_reply_drain_does_not_delay_the_estop_rst` | failed in 5.134 s: `*RST` was not sent; the receipt was `MHS.SAFETY.SAFE_STATE_UNREACHED` |
| `final_owed_check_skipped` | the prefix check uses `len(taken) < prefix` | `test_one_owed_line_does_not_let_a_served_connect_block_the_estop_rst` | `*RST` was sent at 3.210 s, past the test's 3 s bound |

## Gate and records

`python3 -m mhs.driver check MHS/drivers/labs/squad-lab__qcdrivers --backend fake` passed G1-G9. Evidence is `contract_checked` on the fake only. No hardware, simulator, robot server, or upstream import was run. Round 2 ran that check again after the last-owed-line repair. G1-G9 passed in 5575.7 ms. The stable digest is `sha256:8d2080129ff09ec438d5e2e3feb09574afccb9df6cc1a2ca4ba0c830e19f8b87`, the same value as before this repair: the passing report's findings, backend, pin, and SDK version did not change. `python3 MHS/handoff/tools/collect.py --strict` on this package only, run again after that check: 1 of 1 passed, 0 warnings. `collect.py` runs the gate with `--no-report`, so the `check-report.json` in the package directory is the report from the explicit check above. `show_refs.py` reported 22 citations and 0 bad.

`python3 -m mhs.driver reference` rewrote `reference.json` and `REFERENCE.md` (G5 compares them to a fresh generation). The reset action text, its `lines` field, and `safe_state` now say the two lines after the owed prefix. The reference provenance manifest digest moved from `sha256:8cae92b59f6472ca6e9c79e2f81c5b8d08e70848e758dc673eb1a764aefa2267` to `sha256:26d2c422cb7f7159ec05ca99e7bf464d6eb9ca5d3931416106b415bea01a4486` because `driver.py` changed. That digest is not `RESULT.json` `gate.digest`. The status action stays R1 in the reference; the decorator still says R0 (`driver.py:355`). That floor was already there and this repair does not change it. `authored_by` in the reference stays the re-author. `reviewed_by` stays null. Round 2 did not regenerate the reference: G5 passed against the reference already on disk.

`RESULT.json` notes keep the Claude Sonnet paragraph byte for byte. The Grok paragraph was rewritten in place for this round. Its head is still `MODEL REVIEW (grok-4.7, a model and not a human, 2026-11-05; reviewed_by stays null):`. The author's text before the Sonnet paragraph cites `STAT?` as `firmware.ino:98-102` and no longer says the stale pair is accepted. Notes length 7647, under the schema maximum of 8000. Status stays `pass`. Risk stays R1. `publish_review` is required (AGPL-3.0); this repair does not publish the package.

`facts.md` states the same owed-line rule. `fake.py`, `native.py`, `driver.lock.json`, `task.json`, and `site-limits.example.json` are unchanged.

## Stopped attempts

The package trees at `development/p5-backlog-packages/project/MHS/drivers/labs/squad-lab__qcdrivers` and `development/ext-p5-backlog-packages.fast-stopped/project/MHS/drivers/labs/squad-lab__qcdrivers` match the pre-change originals file for file (11 files, equal sha256, no extras). Nothing was taken from either. The originals directory was left as that snapshot-6 copy on this round as well.

## Residuals

The Vrekrer parser behind `ProcessInput` is not in the clone. The counts above are the `println` calls in the handlers, which return only after those prints. An extra line from that parser would sit outside the count. A mismatch fails closed. An under-count that landed on a stale pair would confirm early; nothing in the clone shows such a line. `viClear` stays unused for the reason above. A line this driver did not write is outside the count; with a debt of 0 an unexpected line still fails the exchange (`test_an_unexpected_reply_is_an_unknown_outcome`, `test_driver.py:291`). The pair confirms that this `*RST` cleared both route buffers and shifted them out. The sketch does not sense the analog switches (`AD75019_24.cpp` `isRouted` reads the buffer). One `STAT?` pin is not the e-stop confirmation: one pin would not show every crosspoint open. The 16x16 bit for a pin above 15 remains the fake's placeholder.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/labs/squad-lab__qcdrivers/RESULT.json`
- `MHS/drivers/labs/squad-lab__qcdrivers/driver.py`
- `MHS/drivers/labs/squad-lab__qcdrivers/facts.md`
- `MHS/drivers/labs/squad-lab__qcdrivers/test_driver.py`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.
