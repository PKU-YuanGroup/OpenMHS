OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Gymnasium e-stop latch and stop-attempt generation

GymnasiumBridge now gives each e-stop and each close a stop-attempt id, so only the latest attempt can clear an unconfirmed stop, and it latches effectful world calls until the safety reset. A confirmed stop still has an empty safety status. Reads stay available. This records BL-20 and BL-24. No passing package digest is intended to move.

Authored by Grok (grok-4.7, a model and not a human) on 2026-11-05 in `ext-p5-backlog-sdk--gym`. `reviewed_by` stays null. Nothing was taken from the stopped attempts. Their Gymnasium bridge, async helper, live-route note and bridge tests were byte-identical to this tree's base, and neither tree had a `P5-BACKLOG-SDK` change record.

## BL-20: only the latest stop attempt publishes

`_stop_generation` starts at 0 (`gymnasium.py` line 310). `_open_stop_attempt` (line 557) increments it under `_stop_state` and returns the new id. `_commit_stop_attempt` (line 563) writes `_stop_unconfirmed` only when the id is still current. A stale id returns false and leaves the newer record in place.

Each of these takes an id before it does native work:

- `_estop_owned` (line 658) and `_estop_hosted` (line 797);
- `_close_owned` (line 500), before the remote stop;
- host cleanup (line 449), before `ProcessHost.close`.

A failure path commits its reason under that id. Owned failures go through `fail` (line 664), which commits at line 666 and still raises `MHS.OUTCOME.UNKNOWN` when the commit is stale. Hosted `unknown` (line 801) commits the reason truncated to 300 characters, and the commit is a no-op when the id is stale. The success path commits `None` and, when that returns false, raises `MHS.OUTCOME.UNKNOWN` with "a newer stop attempt superseded this confirmation" (lines 716-718 and 837-838). It does not return the confirmed-stop dict. The server confirms a stop only when `estop` returns and `safety_status` does not report the safe state unachieved, so a superseded attempt must raise.

Paths that already returned `{}` without touching the flag still do that, after opening an id so an older in-flight attempt cannot clear afterwards: no remote stop and nothing owned; the environment was never built; a settled close; a host that never started. They do not write a provisional failure. A confirmed idle stop therefore still leaves `_stop_unconfirmed` empty. A real failure that is already recorded stays recorded.

Close commits a remote-stop `OwnedBusy`, `OwnedTimeout` or exception (lines 508-513) and does not clear the flag when the stop succeeds. A host close that is not exactly `settled` commits that outcome (line 456) and does not clear on success. `_closed` already makes `safety_status` report the safe state unachieved.

`_estop_hosted` had the same unconditional clear as `_estop_owned` (the old clear assigned `_stop_unconfirmed = None` after a confirmed read-back). Both now use the helper.

## BL-24: the bridge latch refuses a direct caller

`estop` (line 2034) advances the epoch, sets `_estop_latched`, and increments `_stop_paths_pending` under `_stop_state` (lines 2039-2042) before any native stop. The count drops in a `finally` (lines 2049-2051) after that call has published or returned. `call` (line 1371) captures the epoch and context before `_ensure_env` (line 1377). An effectful id in `_EFFECT_CALLS` (line 86: step, world reset, seed, restore) is fenced immediately (line 1379). `restore` refuses at line 1945, before `restore_admission`, when the latch is set. `_check_restore_stop` (line 1932) runs during admission (`restore_admission` calls it at line 1926). `restore_admission` reads the current `estop_epoch` at line 1919. An epoch mismatch on that path raises `MHS.SAFETY.ESTOP_ENGAGED` from `Bridge._refuse_if_estopped` (`base.py` line 1777). A later direct restore is refused with `MHS.SAFETY.ESTOP_ENGAGED` because the latch is set.

`_world_fence_exception` (line 576) raises `signals.Cancelled` when the admission's cancel event is set or its epoch no longer matches. Only then, when the latch is engaged and the epoch still matches, it raises `MHS.SAFETY.ESTOP_ENGAGED` with `preempted_by_estop`. The owned-loop guard (line 620) and the host guard (line 740) use the same order and set `mhs_bridge_outcome` so the caller does not relabel them as `MHS.DEVICE.FAULTED`. The synchronous step, physics step and integrating reset use the same fence before the first native call and between ticks (lines 1436, 1456, 1538, 1549, 1681, 1704), including when the caller passed no cancel event.

`reset` (the safety reset) captures `estop_epoch` at line 2074, before any hook. `_refuse_pending_stop` (line 540) raises `MHS.SAFETY.RESET_REFUSED` with `details.reason` `stop_path_pending` while `_stop_paths_pending` is non-zero. That check runs before any host `unfence` (line 2080, and again at line 2121). The latch clears only at the end, under `_stop_state`, when the epoch is still the captured value and no stop path for that epoch is pending (lines 2136-2141). A newer e-stop during the reset leaves the latch set and `reset` still returns `{}`, so the endpoint can reassert. On a hosted bridge, an epoch change before `unfence` returns `{}` without clearing the latch (lines 2117-2119). `cap.world.reset.v1` stays refused while the latch is set, because that world reset can resume the simulator (SAFE-042). `bridge.reset()` is the safety reset and is the call that clears the latch.

`safety_status` is unchanged (line 1996). A confirmed stop still returns `{}` from `safety_status` when nothing is owned and `_stop_unconfirmed` is empty. The latch is not copied into `safety_status` as `achieved: false` or `latched: true`. The pending count is not copied into `safety_status`, `describe`, `async_status` or `host_status`. `operating_notes` are unchanged.

## What stayed out of this edit

`server.py`, `base.py`, `gym_async.py`, `sim_host.py`, `INTERFACE.md`, `REVIEW.md`, registry overrides and the historical `MHS/changes/GYM-LIVE-ROUTES.md` are unchanged. The living note `MHS/sdk/docs/gym-live-routes.md` now describes the latch, the epoch fence and the attempt id.

## Tests

`tests/bridges/test_gym_estop_latch.py` covers the slow-confirm race, the close overlap, a later confirm that clears, the hosted read-back race, a direct caller (step, world reset, seed, restore refused; read, `world_state` and `cap.world.state.v1` admitted), an in-flight synchronous multi-tick step with no cancel event, and an e-stop during safety reset. `PendingStopResetTests` covers a direct `reset` during owned stop submission, during the hosted stop-to-read-back gap, and during synchronous `safe_state`. Each expects `MHS.SAFETY.RESET_REFUSED` with `reason` `stop_path_pending`, a step that stays `ESTOP_ENGAGED`, and a latch that is still set when `estop` returns. The hosted case also expects the fence to stay up. `test_software_latch_without_remote_stop_is_honest` now expects the post-estop call to be `ESTOP_ENGAGED` with no step started, then safety-resets, then runs the owned-work case. `test_estop_stops_reads_back_and_reset_unfences` refuses one step before the safety reset and still expects tick 2 afterwards.

These mutants of `gymnasium.py` were applied one at a time and restored. Each made the named test fail:

| mutant | killed by |
| --- | --- |
| unconditional clear of `_stop_unconfirmed` | `test_a_slower_confirming_estop_cannot_clear_a_newer_failure` |
| no generation increment | same |
| latch not set in `estop` | `test_effectful_calls_are_refused_and_reads_stay_available` |
| call fence ignores the latch | same |
| safety reset clears the latch after a newer e-stop | `test_an_estop_during_safety_reset_keeps_the_latch` |
| synchronous fence checks only the cancel event | `test_an_in_flight_sync_step_is_cancelled_and_a_later_call_stays_latched` |
| safety reset never clears the latch | `test_effectful_calls_are_refused_and_reads_stay_available` |
| close reuses the current attempt id | `test_a_close_failure_survives_a_slower_confirmation` |
| close does not record a remote-stop exception | same |
| a confirming attempt never clears the flag | `test_a_later_confirmed_estop_clears_the_unconfirmed_flag` |
| a superseded owned confirmation returns the success dict | `test_a_slower_confirming_estop_cannot_clear_a_newer_failure` |
| a superseded hosted confirmation returns the success dict | `test_a_slower_hosted_confirmation_cannot_clear_a_newer_readback_failure` |
| e-stop does not mark `_stop_paths_pending` | `PendingStopResetTests` (3 failures) |
| reset ignores a pending stop and still clears the latch | `PendingStopResetTests` (3 failures) |

The source hash after each restore matched the hash taken before that mutant. Round 1 restored `gymnasium.py` to `sha256:116a526906e50f833f1a07154db061241daff2b67b5b4ba33c038444f4e5878d`.

## Left on purpose

A newer attempt that has taken an id and has not yet published an outcome does not set a provisional `_stop_unconfirmed`. A concurrent `safety_status` in that gap can still be empty when nothing is owned. The generation stops the false-safe clear after a failure has been recorded. Early `{}` returns do not clear an older failure and do not invent one. The pending count is separate: `reset` is refused until `estop` returns, including in that unpublished gap.

If `unfence` runs and an e-stop lands before the reset observes the new epoch, the host may be unfenced while the latch stays set. Direct callers remain refused. The next e-stop fences the host again. The pending count closes the gap where the e-stop has already set the latch and has not returned. It does not hold `_stop_state` across native I/O.

## Checks

`python3 MHS/handoff/tools/collect.py --strict` over the 729 packages whose `RESULT.json` status is pass exited 1 after 725 gates passed. No row reported `RESULT_DIGEST_STALE`. `amsikking/thorlabs_mcm3000` still records `sha256:19df2a3625d1993d9edfc1c1a63bc246eee3ce8ee01febeb757cb4d51336350b`, which matches this run. Strict also warns `UNVERIFIABLE_CITATION` there because `reviewed_by` is null and a fact cites `MCM3000_Direct_Serial_Communication.pdf:2`.

A second gate run of the four failures reproduced the same findings. `mattjax16/rigol-dho-mcp` fails G6 with `MHS.CAPABILITY.OUTPUT_INVALID: MCP result is invalid` on `x-cap.mattjax16.get_screenshot.v1`. `misterblue/ros2_raspicam_node` and `christianrauch/raspicam2_node` fail G6 with `MHS.CAPABILITY.NOT_BOUND: compressed ROS images require the optional openmhs[images] decoder`. `lightwheelai/lw-benchhub` fails G1 with `G1.CLONE_MODIFIED` on the shared clone file `lw_benchhub/utils/X7S/urdf/X7S/X7S.usd`. This unit did not edit those packages, their `RESULT.json` files, or that clone. No passing digest was re-recorded.

After the pending-stop fix, `python3 MHS/handoff/tools/collect.py --strict` ran again over the same 729 packages and exited 1 after 3327.98s. 725 gates passed. No row reported `RESULT_DIGEST_STALE`. `amsikking/thorlabs_mcm3000` records `sha256:19df2a3625d1993d9edfc1c1a63bc246eee3ce8ee01febeb757cb4d51336350b`. The four `RESULT_UNTRUSTED` rows are `mattjax16/rigol-dho-mcp` G6, `christianrauch/raspicam2_node` G6, `lightwheelai/lw-benchhub` G1, and `misterblue/ros2_raspicam_node` G6. No `RESULT.json` was edited.

The review-round related suite ran 97 tests in 21.154s, OK. Gym-named discover ran 137 tests in 12.215s, OK. Dropping the pending increment, and making reset ignore a pending stop, each failed `PendingStopResetTests` with 3 failures. `gymnasium.py` was restored to `sha256:116a526906e50f833f1a07154db061241daff2b67b5b4ba33c038444f4e5878d`.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-06 while composing the phase-5 units onto snapshot-7. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged every non-generated change from this unit:

- `MHS/sdk/src/mhs/bridge/gymnasium.py`
- `MHS/sdk/docs/gym-live-routes.md`
- `MHS/sdk/tests/bridges/test_gym_async.py`
- `MHS/sdk/tests/bridges/test_gym_estop_latch.py`
- `MHS/sdk/tests/bridges/test_sim_host.py`
- this change record

Snapshot-6 and snapshot-7 were the same bytes on each of those paths. `CHANGELOG.md` is regenerated and was not copied. Nothing from this unit was left out.
