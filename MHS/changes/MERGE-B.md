# MERGE-B — WP-04 + WP-05 + WP-07 merged into the project tree

This step merged three isolated workspaces back into the project root:

| Workspace | Work package | Steps it contains |
|---|---|---|
| `ws/wp04` | WP-04 (server safety core) | 4a1, 4a2, 4b, 4c, each with its fix rounds |
| `ws/wp05` | WP-05 (bridges) | three steps: the build and two verification-fix steps |
| `ws/wp07a` | WP-07 (conformance) | 07a and its two fix rounds |

It then checked GREEN, fixed three integration breakages between the packages, and re-ran each step's key acceptance checks on the merged tree.

## Procedure

1. Each workspace was diffed against the root with `diff -rq --exclude=__pycache__ --exclude=.DS_Store`, covering `MHS/`, `integration/` and the top-level files. A script did the same walk file by file and classified every path by owner, using the `files_owned` globs in `WORK_PACKAGES.json`.
   - The root had not changed since the workspaces were cut: nothing under `MHS/` or `integration/` was newer than 07:30, and the newest root files are the WP-02/WP-03 change logs at 07:19-07:20.
   - So every difference is a workspace edit.
   - No workspace deleted a file.
   - No top-level file and nothing under `integration/` differed.
2. Each workspace's paths that its WP owns were copied with metadata preserved (`shutil.copy2`, the same as `cp -p`).
   - `__pycache__` and `.DS_Store` were never copied.
   - Before copying, the root's previous versions were saved to a temporary directory outside the repository.
3. Paths a workspace changed but its WP does not own: there are two, and both are the forward-compatible, test-only one-line edits that the step reports list. Both were applied (see below). No other foreign path was changed in any workspace.
4. Conflicts: none. No file was changed by two workspaces.
5. A re-run of the classification after the copy shows no remaining difference for any owned path.

## Copied paths

### WP-04 (40)
- `MHS/changes/WP-04.md` (added)
- `MHS/sdk/docs/e2e-transcript.txt` (changed)
- `MHS/sdk/src/mhs/_server/__init__.py`, `_server/limits_plan.py`, `_server/strict.py` (added)
- `MHS/sdk/src/mhs/evidence.py`, `protocol.py`, `server.py` (changed)
- `MHS/sdk/tests/core/_device_server.py`, `_e2e_transcript.py`, `test_custom_device.py`, `test_server_client.py`, `test_server_strict.py` (changed)
- `MHS/sdk/tests/core/test_http_cli.py` (changed). Owned by WP-08: the listed one-line test-only edit, see below.
- `MHS/sdk/tests/remediation/core/test_fidelity_replay.py`, `test_round2_server.py`, `test_safety_authority.py` (changed)
- `MHS/sdk/tests/remediation/round2/fidelity/support.py` (changed)
- `MHS/sdk/tests/remediation/round2/safety_protocol/_fixtures.py`, `test_proto_004_deadline.py`, `test_safe_002_cumulative.py` (changed)
- `MHS/sdk/tests/safety/` (added, 19 files):
  - helpers: `__init__.py`, `_limits_support.py`, `_stdio_endpoint.py`, `_strict_support.py`, `_support.py`
  - tests: `test_endpoint_methods.py`, `test_estop_latch.py`, `test_estop_preempt.py`, `test_limits_engine.py`, `test_operation_ids.py`, `test_reset.py`, `test_safe_state_exemptions.py`, `test_session_expiry.py`, `test_strict_catalog.py`, `test_strict_hardware.py`, `test_strict_principals.py`, `test_strict_runtime.py`, `test_transport_http.py`, `test_transport_stdio.py`

### WP-05 (25)
- `MHS/changes/WP-05.md` (added)
- `MHS/sdk/src/mhs/bridge/__init__.py`, `base.py`, `bindings.py`, `gymnasium.py`, `mujoco.py`, `python.py`, `replay.py`, `serial.py` (changed)
- `MHS/sdk/src/mhs/bridge/scpi.py`, `transcript.py` (added)
- `MHS/sdk/tests/bridges/` (added, 10 files):
  - helpers: `__init__.py`, `support.py`
  - tests: `test_async_status.py`, `test_main_guards.py`, `test_python_object.py`, `test_safety_bindings.py`, `test_scpi_transcript.py`, `test_sim_bridges.py`, `test_verification_regressions.py`, `test_verification_round2.py`
- `MHS/sdk/tests/endpoints/test_bridges.py`, `MHS/sdk/tests/remediation/bridge/test_binding_contract.py`, `MHS/sdk/tests/remediation/round2/registry/test_bindings_external_validation.py` (changed)
- `MHS/sdk/tests/safety_lib/test_units.py` (changed). Owned by WP-03: the listed one-line test-only edit, see below.

### WP-07 (25)
- `MHS/changes/WP-07.md` (added)
- `MHS/sdk/docs/conformance.md`, `MHS/sdk/docs/reports/README.md` (changed)
- `MHS/sdk/src/mhs/conformance/__init__.py`, `__main__.py`, `applicability.json`, `report.py`, `requirements.py`, `suite.py`, `tests_core.py`, `traceability.json` (changed)
- `MHS/sdk/src/mhs/conformance/inprocess.py`, `model.py`, `static.py`, `synth.py` (added)
- `MHS/sdk/tests/conformance/` (added, 7 files):
  - helpers: `__init__.py`, `support.py`
  - tests: `test_applicability_tool.py`, `test_driver_gate.py`, `test_harness_synth.py`, `test_reports.py`, `test_runner.py`
- `MHS/sdk/tests/endpoints/test_conformance_suite.py`, `MHS/sdk/tests/remediation/round2/spec/test_presence_spec001.py` (changed)
- `MHS/sdk/tools/build_applicability.py` (added)

`MHS/conformance/**` was not changed in `ws/wp07a`: the published reports are regenerated in 07b.

## Foreign test-only edits applied (forward compatible, one line each)

- `MHS/sdk/tests/core/test_http_cli.py` (WP-08). In `HttpBindingTest.setUpClass`, the edit adds `cls.client.transport.start_events(session_id=cls.session["session_id"])`.
  - Reason: since WP-04 4a2, SSE is session-scoped, and the stock client does not send `session_id` yet.
  - Source: the WP-04 4a2 deviation and the 4a2 fix-round open issue "merge risk".
  - Once WP-08's client passes the session itself, this second `start_events()` call does nothing.
- `MHS/sdk/tests/safety_lib/test_units.py` (WP-03), line 196: `assertIn(base.convert_unit(50, "%", "1"), (50, 0.5))`.
  - Reason: under WP-05, `%` converts as 0.01.
  - Source: the WP-05 deviation, which the WP-05 report says the merge must carry.

## Integration fixes

GREEN right after the copy: SDK 1218 tests with 9 failures and 5 skipped; registry, integration and site all OK. The 1218 tests are the 683 baseline tests, plus 275 from WP-04, 148 from WP-05 and 112 from WP-07. The 9 failures fall into two groups (fixes 1 and 2). Fix 3 covers an interplay that GREEN does not catch; it was found by re-running the WP-07 verifier's open issue on the merged tree.

### 1. Bridges vs the new reset contract (WP-05 test; WP-04 contract)

- **Symptom.** `tests/bridges/test_verification_round2.py` `InterlockMalformedReplyTests.test_server_rejects_reset_and_actuation_on_a_malformed_reply` failed (3 subtests): it expected `MHS.SAFETY.INTERLOCK_OPEN` on the receipt of a refused `mhs.safety.reset`.
- **Cause.** Since WP-04 4a1 the server answers every refused reset with `MHS.SAFETY.RESET_REFUSED`, as `errors.json` defines it: "reset while interlock open/unknown or not latched". When the bridge's own `reset()` refuses, the server keeps the bridge's code as `details.bridge_code` (`MHS.SAFETY.INTERLOCK_OPEN`) and the interlock list as `error.interlocks`.
- **Fix (WP-05-owned test only).** The test now asserts `RESET_REFUSED`, `details.bridge_code == MHS.SAFETY.INTERLOCK_OPEN` and the interlock state `unknown`.
- **Unchanged.** The safety assertions are as before: the receipt is `rejected`, and neither `RST` nor `HEAT 1` reaches the wire.

### 2. Conformance CAP-017 vs the compat risk floor (WP-07 test fixture; WP-04 4b behaviour)

- **Symptom.** 6 failures:
  - `tests/conformance/test_runner.py` `CL0FailureTests` (2)
  - `tests/conformance/test_reports.py` `FailedCL0ReportTests` (3) and `CliTests.test_cli_exits_below_target_when_cl0_fails` (`r0_thermostat_factory`)
  - In each, the R0 thermostat no longer fails `CAP-017` at CL0.
- **Cause.** WP-04 4b: a compatibility `MHSServer` raises a risk class below the class floor to the floor. It warns `risk-floor`, and strict mode refuses the device. So the served manifest says R2, and CAP-017, which reads the served manifest, correctly passes.
- **Fix (WP-07-owned fixture only).** `tests/conformance/support.thermostat_server` restores the declared `risk_class` after construction. The fixture thereby models an endpoint that publishes a below-floor class, so CAP-017's detection and the "failed CL0 is never an award" semantics stay covered. The server's limit plans keep the raised floor. The docstring explains this.
- **Unchanged.** No suite code changed for this.

### 3. Conformance vs strict arming: `MHS.AUTH.HARDWARE_DISABLED` (WP-07 suite; WP-04 4b arming)

- **Symptom.** This is the WP-07 07a fix-round-2 open issue, reproduced on the merged tree with `scratch/merge-b/repros/strict_unarmed_conformance.py`.
  - Subject: a strict endpoint (WP-04 4b; it arms no hardware by default) run in-process without opt-in.
  - `OP-005`, `PROTO-027`, `SAFE-011`, `SAFE-012` and `SAFE-014` were reported as **required failures** with a misleading detail such as "returned MHS.AUTH.HARDWARE_DISABLED, expected MHS.CONFLICT.REVISION".
  - Nothing moved: the endpoint refused every one of them at plan 3.6 step 6 (arming), before the check each test targets.
  - This configuration is the default of every strict hardware endpoint, which WP-06's in-process driver gate (G8) will run.
- **Fix (`MHS/sdk/src/mhs/conformance/tests_core.py`, WP-07).** New `_not_armed()` / `_not_reached()`.
  - When the endpoint itself returns a `rejected` receipt with `MHS.AUTH.HARDWARE_DISABLED`, these five negative tests now report `skip`, with the detail "check not reached ... hardware actuation is not armed ...".
  - "Endpoint itself" means: no harness block was recorded since the test's mark, and it was not the suite's own CON-031 send guard.
  - `SAFE-014` and `SAFE-011/012` skip only when no probe or target failed. A failing probe still fails the test.
- **Level impact.** None. A skipped required test still caps the level, so a level can never rise through this path.
- **Tests (written first; 5 subtests failed before the fix).** Two new tests in `tests/conformance/test_driver_gate.py` `HardwareGateTests`:
  - `test_strict_unarmed_hardware_negative_tests_are_not_reached`
  - the control `test_strict_armed_hardware_negative_tests_reach_their_checks`: armed strict hardware, where all five pass in-process with zero actuations
- **Fixture.** `tests/conformance/support.heater_server` gained `resource_kind=` and `server_options=` (keyword-only, with defaults). A strict heater needs a kind both bound classes accept: `instrument.incubator`.
- **Docs.** `MHS/sdk/docs/conformance.md` (Hardware bullet) documents the rule.

## GREEN

| Suite | Before merge | After copy | Final |
|---|---|---|---|
| SDK (Python 3.14) | 683 OK (4 skipped) | 1218, 9 failures (5 skipped) | **1220 OK (5 skipped)** |
| SDK (Python 3.10.21) | n/a | 1218 OK (10 skipped), after fixes 1–2 | **1220 OK (10 skipped)** |
| Registry | 27 OK | 27 OK | 27 OK |
| Integration | 93 OK | 93 OK | 93 OK |
| Site check | OK, 1 warning | OK, 1 warning | OK, 1 warning |

The site warning is the same in all three runs: stale downloads, 16 inputs changed. It was there before this step.

## Acceptance re-run on the merged tree

Commands run from the project root with `PYTHONDONTWRITEBYTECODE=1`. The probe script (kept outside the repository) reported 19/19 passed.

**WP-04 (server safety core)**
- `unittest discover -s MHS/sdk/tests/safety` gives 275 OK.
- stdio priority: an e-stop sent 0.2 s into a 4 s non-cancellable `world.step` on the reference conveyor was answered in **5.1 ms**. The next motion command got `rejected` `MHS.SAFETY.ESTOP_ENGAGED`.
- Hung `bridge.estop`, which sleeps 3 s (sdk-core e12):
  - the device was latched after **0.17 ms**;
  - the receipt is `failed` with `MHS.SAFETY.SAFE_STATE_UNREACHED` and `latched: true`;
  - the next motion command got `rejected` `ESTOP_ENGAGED`.
- Array and nested limits, each with zero bridge calls:
  - `[90, 0]` against a ±45 envelope gives `ENVELOPE_VIOLATION`, path `joints[0]`;
  - on the reference arm narrowed to ±45, the same input gives path `joint_positions_deg[0]`;
  - the out-of-range reference arm command `[170, 0]` gives `ENVELOPE_VIOLATION` with bound 135, not `INPUT_INVALID`;
  - a nested leaf, `ch1.voltage` 48 V against a 5 V limit, gives `ENVELOPE_VIOLATION`.
- Operation ids:
  - 10,000 concurrently generated operation ids are distinct;
  - the end-to-end test with 10,000 concurrent commands, `test_operation_ids`, is part of the safety suite;
  - `grep -nF 'ulid()[:' MHS/sdk/src/mhs/server.py` prints nothing.
- After the standalone SDK suite run, the Python 3.10 run and the final combined GREEN run, `find -L remediation-round2/ -newer <marker>` printed nothing. See the note on the one exception below.

**WP-05 (bridges)**
- `unittest discover -s MHS/sdk/tests/bridges` gives 147 OK (1 skipped: pyvisa-sim is not installed).
- `python -m mhs.bridge.$b --adapter /nonexistent` exits **2** for each of python, gymnasium, mujoco, serial, replay and scpi.
- `convert_unit(50, "%", "1")` returns `0.5`.

**WP-07 (conformance)**
- `unittest discover -s MHS/sdk/tests/conformance` gives 114 OK.
- `python3 MHS/sdk/tools/build_applicability.py --check` exits 0, `stale: false`.
- A null driver at MHS-Device CL3 reaches **CL1**, both over a client and simulated in-process.
- A thermostat with a declared envelope reaches the same level (CL2) with its setpoint listed first or last.
- A hardware heater run without `allow_actuation` gets zero native write/invoke calls, in-process (3 fresh endpoints, CON-031 pass) and over a plain client.
- Three in-process runs on fresh instances give identical results: conveyor CL4, lab CL2, arm CL4.
- The forged-report `verify` check and the no-op e-stop check fail as intended (`test_reports`, `test_driver_gate`).

**Cross-package probe** (`scratch/merge-b/repros/achieved_by_vs_hung_estop.py`). This answers the WP-04 4a1 follow-up "bridges must tolerate a `call()` of a safe-state action running concurrently with `estop()`".
- Setup: a WP-05 `PythonObjectBridge` whose native e-stop hangs.
- Its `safe_state.achieved_by` action ran at the declared 200 ms latency while the native e-stop hung.
- The heater went off.
- The receipt is truthfully `failed` with `SAFE_STATE_UNREACHED`.

## Open issues carried forward (not fixed here; status on the merged tree)

> **Superseded by the fix round below.** The WP-05 blocker, the WP-04 4a1
> major, both WP-07 harness defects and most of the minors listed here were
> fixed in the MERGE-B fix round. The list is kept as it stood at the first
> merge.

The step reports end with verification findings that were still open. This merge step does not fix them. Their state on the merged tree, re-checked with copies of the verifier probes under `scratch/merge-b/repros/` (pointed at the root), is:

- **WP-05 blocker: numeric interlock parse fails open.**
  - **Still present.** `r4_int_interlock.py` reads `'ERR 0'`, `'E0: unknown command'`, `'0,"No error"'` and `'-0.0'` as closed when `closed_when` is 0.
  - In `r5_server_int.py`, the reply `'E0 unknown command'` gives a completed reset, and `HEAT 1` goes out on the wire.
  - Owner: WP-05, `bridge/base.py`, `serial.py`, `scpi.py`, `python.py`. Apply the anchored or full-match parse for interlock reads.
- **WP-07 blocker: harness gate with one bridge shared by a simulated and a hardware device.**
  - On the merged tree `shared_bridge.py` records **no hardware moves**, because the WP-04 endpoint now refuses these commands: they come back `MHS.SESSION.MODE_MISMATCH`, and the negative tests are skipped.
  - The harness defect itself is unchanged: device attribution is fixed when a bridge is wrapped.
  - Owner: WP-07, `inprocess.py`.
- **WP-07 major: wrappers that were never installed (silent `__setattr__`).**
  - On the merged tree `silent_setattr.py` gives `native []`: no moves, and the negative tests are skipped.
  - The missing install check (`getattr(bridge, name) is wrapper`) is still missing.
  - Owner: WP-07.
- **WP-04 4a1 major: e-stop confirmation not tied to the current attempt.**
  - **Still present.** `s_confirm_race_nodelay.py` shows 19/20 FALSE_CONFIRMED.
  - Owner: WP-04, `server.py` `_confirm_estop` / `_supervise_estop`.
- All minors listed in the step reports are unchanged. They include:
  - WP-04 4a1: reset hold, `_reassert_estop` pending attempts, the restore re-assert test, and reset receipts whose status is `rejected` although `bridge.reset()` ran;
  - WP-04 4a2: `loads_strict` RecursionError, stdio FIFO lanes, SSE ownership, the e-stop envelope, expiry, the docstring;
  - WP-04 4b and 4c minors;
  - WP-05: Gymnasium nested Dict, SCPI wording and the interrupt window;
  - WP-07: the offline downgrade check and the SAFE-028 limit.

  The WP-07 minor "HARDWARE_DISABLED is reported as fail" is **fixed** here (integration fix 3).

## Notes

- **`remediation-round2/` mtime.** During the second combined GREEN run, `remediation-round2/team/fidelity/tmp` got a new mtime (15:17:13), and that run's SDK suite was the only one in progress at the time.
  - The cause is outside the project tree. The pre-WP-04 `tests/remediation/round2/fidelity/support.py` creates its temp directories exactly there. That old copy is still in `ws/wp05`, `ws/wp07a` and `ws/wp10`, whose `remediation-round2` is a symlink to the root's.
  - `ws/wp10` was active during this step: files there changed after this step's start marker.
  - The merged root uses the system temp dir (WP-04). The standalone SDK run, the Python 3.10 run and the final combined GREEN run each left `remediation-round2/` untouched.
- **`ws/wp10` holds pre-merge copies** of the WP-04/05/07 files. Its later merge must copy only WP-10-owned paths.
- **Stale e2e transcript.** `MHS/sdk/docs/e2e-transcript.txt` (WP-04) still PASSes when regenerated against the merged tree in scratch. With timestamps, ids and digests normalised, it differs only in the line number of one `MHSStrictWarning` (`server.py:4856`, now 4869) and the run duration. It was left as is; regenerate it in WP-04 4f.
- **`__pycache__`.** The integration suite's child processes still write `__pycache__` (a new `MHS/sdk/src/mhs/_server/__pycache__` appeared). This is the existing WP-08 follow-up: pass `PYTHONDONTWRITEBYTECODE` to the children.

## Follow-ups

- **WP-05**
  - Fix the interlock fail-open blocker (above).
  - Its remaining minors.
- **WP-07**
  - The harness: shared-bridge attribution and the wrapper install check.
  - TSAFE-001: when `mhs.safety.reset` returns a non-success receipt, report it. Examples are a strict hardware `MHS.AUTH.FORBIDDEN` for a non-operator, or `RESET_REFUSED` `stop_path_pending`. Today TSAFE-001 says "e-stop is still engaged after a *successful* reset".
  - 07b: decide how a strict hardware subject run with `allow_actuation` gets an operator principal and an armed endpoint. Today the effect tests are refused with `HARDWARE_DISABLED` / `FORBIDDEN` and fail.
- **WP-04**
  - The 4a1 confirmation-race major and the remaining 4a/4b/4c minors.
  - 4f: regenerate `docs/e2e-transcript.txt`.
- **WP-08**
  - `client.py` must pass `session_id` to SSE; after that the `test_http_cli.py` line is redundant.
  - The integration tests must pass `PYTHONDONTWRITEBYTECODE` to child processes.
- **WP-06** (G8, `mhs.driver.check`): with fix 3, an in-process run of a strict, unarmed hardware driver without opt-in reports the five negative tests as "check not reached" (skip), and the level stays capped at CL1. Arm the endpoint for the negative checks to run.
- **Merge of WP-10**: copy only WP-10-owned paths from `ws/wp10`. Its copies of `tests/remediation/round2/fidelity/support.py` and of the WP-04/05/07 files predate this merge.

## Fix round (after the independent MERGE-B verification)

The verifier's checks of the merge itself all passed: the copied paths, the
two foreign one-line edits, no conflicts, GREEN, and the three integration
fixes. It failed the step on the carried safety defects. This round fixed
every blocker and major issue, and the cheap minors, inside WP-04, WP-05 and
WP-07 files. Each verifier probe was ported as a test first and failed on the
merged tree (or under a mutation), then was fixed. The details are in the
"MERGE-B fix round" sections of `WP-04.md`, `WP-05.md` and `WP-07.md`.

### Fixed

| Severity | Finding | Fix (owner, file) | Tests |
|---|---|---|---|
| blocker | A numeric interlock read an error reply as closed (`'ERR 0'`, `'E1 bad'`), the reset completed and `HEAT 1` reached the wire | Interlock reads parse the whole reply: `parse_text(..., whole=True)` uses `re.fullmatch` for `int`/`float`/`regex` (WP-05: `bridge/base.py`, `serial.py`, `scpi.py`, `python.py`) | `tests/bridges/test_interlock_whole_reply.py` (9) |
| major | The e-stop confirmation was not tied to the current attempt: `confirmed: true` after a failed later e-stop, and the later e-stop's retry was lost | Confirm only the current attempt; the supervisor serves newer attempts and deregisters when it ends; the confirmation read is bounded (WP-04: `server.py`) | `test_estop_latch.ConfirmationRaceTests` (4) |
| major | The harness fixed a shared bridge's device at wrap time, so a hardware call passed the gate | Track every device that shares a bridge; attribute each call by `ctx.device_id`; refuse an actuating call on any bridge shared with hardware (WP-07: `conformance/inprocess.py`) | `test_harness_gate_attribution.SharedBridgeGateTests` (4) |
| major | Wrappers were never checked as installed (a silent `__setattr__` or a data descriptor) | A wrapper is installed only if `getattr(bridge, name) is wrapper`; otherwise the method is uninstrumented (WP-07: `inprocess.py`) | `WrapperInstallCheckTests` (2) |
| minor | A mixed-mode endpoint failed checks on the suite's own session `MODE_MISMATCH` | One suite session per device mode; operations use the session that started them (WP-07: `tests_core.py`) | `MixedModeSessionTests` (1) |
| minor | The 4a1 reset hold also delayed a new e-stop | `reset_seq`; an e-stop during the reset lifts the hold (WP-04) | `ResetHoldTests` (1) |
| minor | 4a1 `_reassert_estop` hid a pending native e-stop | `pending_attempts`, checked by `_stop_path_pending` (WP-04) | `ReassertPendingAttemptTests` (1) |
| minor | 4a1: the restore re-assert had no test | Regression test (behaviour already correct) | `LatchScopeTests` (+1) |
| minor | 4a2: a `loads_strict` RecursionError killed the stdio endpoint | `PARSE_ERROR`; the reader never dies on a decode error (WP-04: `protocol.py`, `server.py`) | `test_transport_stdio` (+1) |
| minor | 4a2: the `validate_deadline` docstring named a legacy code | Docstring (WP-04: `protocol.py`) | — |
| minor | 4b: hello, well-known and the default `session.open` listed a refused late device | `_served_devices()` (WP-04: `server.py`) | `test_strict_hardware` (+1) |
| minor | 4b: compatibility receipts kept top-level `authenticated` / `role` | Dropped (WP-04: `_server/strict.py`) | `test_strict_principals` (+1) |
| minor | 4c: the stale-plan check had no test | Test (mutation E makes it fail) | `test_limits_engine` (+1) |
| minor | Stale e2e transcript | Regenerated, PASS (WP-04: `docs/e2e-transcript.txt`) | — |
| minor | WP-05: nested Gymnasium `Dict` actions were unbounded | Recursive schema, limits and native conversion; over-deep Dicts are refused (WP-05: `gymnasium.py`) | `test_gym_nested_spaces.py` (3) |
| minor | WP-05: SCPI interrupt window between write and read | Interrupt cleared in `begin_query()` (WP-05: `scpi.py`) | `test_scpi_interrupt_window.py` (2) |
| minor | WP-05: SCPI wording | "No *actuating* request follows the e-stop" | — |
| minor | WP-07: TSAFE-001 said "successful reset" for a refused reset | The detail names the refusal; the verdict is unchanged (WP-07: `tests_core.py`) | `test_driver_gate` (+1) |
| minor | WP-07: SAFE-028 black-box limit | Documented (`docs/conformance.md`) | — |

No file outside WP-04, WP-05 and WP-07 ownership was edited, and no foreign
test needed a change in this round.

### Not fixed (carried; owners in the WP logs)

- **4a2 stdio FIFO lane** (WP-04, 4f or later): a latched refusal waits
  behind a blocking command, bounded by its deadline. This round's stdio
  probe: the e-stop is answered in 0.6 ms, but the next motion's
  `ESTOP_ENGAGED` comes after 3.8 s. A safe fast path needs per-device worker
  pools; a refusal beside the lane could otherwise reorder a command
  pipelined behind a reset.
- **4a1 reset receipt status** (WP-09): `rejected` with `bridge_reset:
  completed`.
- **4a2 (WP-04 later and WP-09):**
  - SSE ownership;
  - the e-stop envelope gate;
  - the expiry gaps;
  - the HTTP status of `1e999`.
- **WP-05 residual:** Gymnasium `Tuple` elements have no limits
  (simulation only; documented).
- **WP-07 07b:** the `validate_report` downgrade path, plus the 07b items.
- **WP-08:** the `client.py` SSE `session_id`, and `PYTHONDONTWRITEBYTECODE`
  for the integration child processes. Those children refreshed the existing
  `.pyc` files of the edited `server.py`, `protocol.py` and `_server/strict.py`
  in `MHS/sdk/src/mhs/**/__pycache__`. This round wrote no new `__pycache__`
  directory.

### GREEN (fix round)

| Suite | Before this round | After |
|---|---|---|
| SDK (Python 3.14) | 1220 OK (5 skipped) | **1253 OK (5 skipped)** |
| SDK (Python 3.10) | 1220 OK (10 skipped), the verifier's run | **1253 OK (10 skipped)** |
| Registry | 27 OK | 27 OK |
| Integration | 93 OK | 93 OK |
| Site check | OK, 1 warning | OK, 1 warning (the same stale-downloads warning) |

The SDK suite gained 33 tests:

| Package | Before | After |
|---|---|---|
| bridges | 147 | 161 |
| conformance | 114 | 122 |
| safety | 275 | 286 |

### Acceptance re-run (fix round, merged tree)

- `scratch/merge-b/acceptance.py`: 19/19 PASS. Log:
  `scratch/merge-b-fix/acceptance.log`.
  - stdio e-stop answered after 1.7 ms during a 4 s step; the next motion is
    `ESTOP_ENGAGED`.
  - Hung `bridge.estop`: latched after 0.19 ms; the receipt is `failed`
    `SAFE_STATE_UNREACHED`.
  - Array and nested `ENVELOPE_VIOLATION` with zero bridge calls.
  - The null driver reaches CL1 at most.
  - A hardware subject without opt-in has zero actuations.
- Verifier probes, re-run on the fixed tree:
  - `v_interlock_numeric.py`: every error reply reads `unknown`, the reset is
    rejected and `HEAT 1` is never written. Control: `'1'` resets.
  - `r4_int_interlock.py` and `r5_server_int.py`: unknown, refused.
  - `s_confirm_race_nodelay.py 20`: 0/20 lost retries, 0/20 false
    confirmations.
  - `s_confirm_race.py` at 0.02, 0.05 and 0.3 s: retried.
  - `s_hold_new_estop.py`: 2 retries while `bridge.reset()` runs.
  - `s_restore_reassert.py`: the stop path runs again after the restore.
  - `shared_bridge.py`, sim-first and hw-first: 0 hardware moves; SAFE-014
    and CON-031 pass.
  - `silent_setattr.py`: every method uninstrumented, `blocks: False`,
    0 moves, CON-031 inconclusive.
  - `v_mixed_modes.py`: SAFE-014 passes for the mixed endpoint.
  - `v_null.py`: at most CL1.
  - `v_hung_and_limits.py` and `v_hung2.py`: unchanged (pass).
  - `v_stdio.py`: e-stop in 0.6 ms (the FIFO lane minor is carried).
- Bridge mains (`python -m mhs.bridge.$b --adapter /nonexistent`): rc 2 for
  python, gymnasium, mujoco, serial, replay, scpi, base, bindings and
  transcript.
- `tools/build_applicability.py --check`: rc 0, `stale: false`.
- No forbidden or research directory was touched (`find -newer` on the
  marker gives 0 entries).
