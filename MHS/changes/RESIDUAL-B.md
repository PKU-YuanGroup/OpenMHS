# RESIDUAL-B — open verifier issues of workflow B (WP-04, WP-05, WP-07)

This step works through the 22 issues the independent verifiers of WP-04,
WP-05 and WP-07 left open (the list kept in the private planning record;
7 of them blockers or majors). For each issue it did the following:

1. Reproduce it on the current tree, using a copy of the verifier probe
   re-pointed at the project root (`scratch/residual-b/probes/`).
2. If the issue was already fixed (most by the MERGE-B fix round), record the
   evidence and the regression test that guards it.
3. Otherwise, port the probe as a test in the owner's test directory, run the
   test against the unfixed code (it must fail), fix the issue in the owner's
   files, and run the test again.

Only WP-04, WP-05 and WP-07 files were edited. No foreign test needed a
change.

Scratch space was a temporary directory outside the repository.

## Status of every issue

| # | Step | Sev. | Issue | Status | Evidence / tests |
|---|---|---|---|---|---|
| 1 | WP-04/4a1 | major | e-stop confirmation not tied to the current attempt | already fixed (MERGE-B) | `s_confirm_race_nodelay.py 20`: 0/20 lost, 0/20 false confirmations. `s_confirm_race.py` 0.02/0.05/0.3: retried. `test_estop_latch.ConfirmationRaceTests` |
| 2 | WP-04/4a1 | minor | reset hold delays the retry of an e-stop pressed during the reset | already fixed (MERGE-B) | `s_hold_new_estop.py`: 2 retries while `bridge.reset()` runs. `ResetHoldTests` |
| 3 | WP-04/4a1 | minor | `_reassert_estop` hid a pending native e-stop | already fixed (MERGE-B) | `pending_attempts`. `ReassertPendingAttemptTests` |
| 4 | WP-04/4a1 | minor | the restore re-assert had no test | already fixed (MERGE-B) | `s_restore_reassert.py`: `[restore_enter, estop, restore_exit, estop]`. `LatchScopeTests.test_estop_during_bridge_restore_reasserts_the_stop_path` |
| 5 | WP-04/4a1 | minor | reset receipts `rejected` although `bridge.reset()` ran | **fixed here** | now `failed`; see A4 |
| 6 | WP-05 | blocker | numeric interlock parse fails open | already fixed (MERGE-B) | `r4_int_interlock.py`: every error reply reads `unknown`. `r5_server_int.py`: reset `rejected` `RESET_REFUSED`, no `HEAT 1`. `r6_pyobj_int.py` (with a stub `door_dev`): `unknown`, refused; control `'0'` resets. `tests/bridges/test_interlock_whole_reply.py` |
| 7 | WP-05 | minor | nested Gymnasium `Dict` unbounded | already fixed (MERGE-B); `Tuple` documented | `r1_gym_nested.py`: `action.arm.j[0]=500` refused `ENVELOPE_VIOLATION`. `Tuple` elements (top level or inside a `Dict`) stay unbounded, as documented in the `gymnasium.py` docstring and in `WP-05.md` (simulation only). `test_gym_nested_spaces.py` |
| 8 | WP-05 | minor | SCPI wording "no request follows the e-stop" | already fixed (MERGE-B) | `scpi.py` docstring: "no *actuating* request follows" |
| 9 | WP-05 | minor | SCPI interrupt window | already fixed (MERGE-B) | `begin_query()` clears the interrupt. `test_scpi_interrupt_window.py` |
| 10 | WP-07/07a | blocker | shared bridge fixes the device at wrap time | already fixed (MERGE-B) | `shared_bridge.py` sim-first and hw-first: `hw_native_moves=[]`, CON-031 pass. `test_harness_gate_attribution.SharedBridgeGateTests` |
| 11 | WP-07/07a | major | wrappers never checked as installed | already fixed (MERGE-B) | `silent_setattr.py`: every method uninstrumented, `blocks: False`, `native []`. `WrapperInstallCheckTests` |
| 12 | WP-07/07a | minor | offline `validate_report` accepts a downgraded report | already fixed (07b) | `forged_d.json` now has 1 error (`missing required property 'disclaimers'`); suites before 1.2.0 are refused. `test_limits_revisions` (forge d), `test_reports` |
| 13 | WP-07/07a | minor | SAFE-028 black-box limit | already fixed (MERGE-B, documented) | `docs/conformance.md`, SAFE-028 bullet |
| 14 | WP-07/07a | minor | `HARDWARE_DISABLED` reported as fail | already fixed (MERGE-B fix 3) | `_not_armed()`; `test_driver_gate` |
| 15 | WP-04/4d | major | stale `expected_revision` runs through the pre-call state read | **fixed here** | A1 |
| 16 | WP-04/4d | minor | readOnly state root; draft-07 `items: [...]` / `additionalItems` | **fixed here** | A2 |
| 17 | WP-04/4d | minor | hardware non-read operations not exclusive by default (plan 3.6 step 12) | **fixed here** | A3 |
| 18 | WP-04/4d | minor | dead `_state_changed` / `_device_state_digest` | **fixed here** | both deleted; nothing called them (grep) |
| 19 | WP-07/07b | blocker | SAFE-014 fails open on fields declared in `anyOf`/`oneOf` or admitted | **fixed here** | B1 |
| 20 | WP-07/07b | major | one fixture refusal covers a whole path | **fixed here** | B2 |
| 21 | WP-07/07b | minor | numeric allowed set gets one probe | **fixed here** | B3 |
| 22 | WP-07/07b | minor | OP-001 silently drops reads it cannot build | **fixed here** | B4 |

## A. WP-04 (`MHS/sdk/src/mhs/server.py`)

### A1. The revision is checked again at dispatch (4d r3 major; SDK-07 / e7 a)

**Symptom.** `expected_revision` was checked after the device lock and when
the operation was registered. The worker then read the device state before
the call. That read is bounded by half the budget for a non-exclusive
command, and has no bound for an exclusive one. A command that completed
during the read moved the revision, and the stale command still ran:
`A(expected 0) completed 1 -> 2` (`probes3.py`, `test_r3_findings.py`).

**Fix.** The worker checks `expected_revision` once more, under `self._lock`,
after its state read and its cancel check and immediately before
`_call_native`. On a mismatch:
- it writes a `rejected` `MHS.CONFLICT.REVISION` receipt that carries the
  true `current_revision`;
- the revision does not advance;
- no bridge call is made;
- the reservation of the command id is released, so a retry runs (OP-005);
- a consumed permit is given back (`_start_operation(returnable_permit=...)`,
  `_return_permit`);
- an `unknown` receipt that was already claimed is reconciled, as on the
  `Busy` path.

**Tests.** `tests/safety/test_bindings_revisions.py` `DispatchRevisionTests`
(4 tests):
- non-exclusive and exclusive (the ported `test_r3_findings` cases);
- a permit given back after the dispatch refusal, then used by a retry that
  carries the right revision;
- a control: a current `expected_revision` still runs after a slow read.

The first 3 failed before the fix (`scratch/residual-b/failfirst_4d.log`).
The verifier's own `test_r3_findings.py` now passes (4/4).

### A2. Configure field rules (4d r3 minor)

`_check_configure_fields` now handles three more cases:
- **readOnly root.** A `readOnly` state root, in any branch, makes every key
  `MHS.RESOURCE.NOT_WRITABLE`.
- **Draft-07 tuple form.** In `items: [...]`, elements are read by position,
  then against `additionalItems`.
- **`false` schema.** A `false` schema admits nothing, so the field is
  `FIELD_UNKNOWN`. This is defence in depth: the served input refuses it
  first, with `INPUT_INVALID`.

`ConfigureReadOnlyGapsTests` has 4 tests. The root and tuple tests failed
before the fix. The remaining two are a guard for the forbidden-element case
(either refusal code, and no bridge call) and a writable tuple control.

### A3. Hardware and hybrid devices take the device lock by default (plan 3.6 step 12)

**Fix.** The new `_takes_device_lock(device, capability)` decides whether a
command takes the device lock:

| Binding | Device mode | Takes the lock |
|---|---|---|
| declared `exclusive` | any | yes |
| any other | simulated or replay | no (the declared flag is kept) |
| catalogued read class (`_is_read_capability`) | hardware or hybrid | no |
| declares `constraints.concurrency: "shared"` | hardware or hybrid | no |
| any other non-read binding | hardware or hybrid | yes |

An extension's own `verb: read` is not trusted, so on hardware an extension
read takes the lock.

Exempt: stop classes and `safe_state.achieved_by` actions never wait for the
lock (SAFE-029), as before.

The hello and `devices.list` device summaries now publish the lock the
runtime applies (`_device_summary`). On hardware or hybrid devices a summary
can therefore say `exclusive: true` where the binding did not declare it.
~~Full manifests are unchanged: they are the declaration, and they feed the
manifest digests.~~ Superseded in round 2 (C3): this left `devices.get`
saying `shared` where the runtime locks, and the invented `shared` opted a
rebuilt binding out of the lock. Full manifests now publish the concurrency
the runtime applies, and the class concurrency counts.

**Tests.** `HardwareDeviceLockTests` (5 tests):
- hardware and hybrid: a second non-read command during a running one is
  `rejected` `MHS.DEVICE.BUSY`;
- simulated keeps the declared flag;
- `concurrency: "shared"` opts out;
- reads and stops are never blocked;
- the summaries.

The BUSY test failed before the fix (`failfirst_4d.log`).

### A4. Reset refusals decided after `bridge.reset()` are `failed` (4a1 minor)

**Before.** `estop_during_reset`, and `stop_path_pending` with
`details.bridge_reset: "completed"`, gave a `rejected` receipt, although
plan 3.7 reads `rejected` as "nothing was executed".

**Now.** Both give a `failed` receipt. Unchanged: the code is still
`MHS.SAFETY.RESET_REFUSED`, with `latched: true` and the same details. The
revision advances, as it does for a completed reset, because `bridge.reset()`
ran (an unknown change).

Refusals decided before `bridge.reset()` (`not_latched`, `operation_running`,
`stop_path_pending` before the call, `interlock_open`, `bridge_refused`) stay
`rejected`.

**Tests.** 4 assertions changed, all in WP-04-owned tests:
`test_reset.ResetRaceTests` (2), `ResetWhileStopPathRunsTests` (1) and
`test_estop_latch.ReassertPendingAttemptTests` (1). They failed before the
fix (`failfirst_reset.log`). A new assertion checks that the revision
advances.

### A5. Housekeeping

- `_device_state_digest` and `_state_changed` are deleted (dead since the
  `_StateRead` refactor).
- `MHS/sdk/docs/e2e-transcript.txt` was regenerated, with PASS.
  - Run in a scratch copy, then copied in; the transcript has no absolute
    paths.
  - The committed file was stale before this step: it still said
    `suite_version: "1.1.0"`, from before 07b.
  - After normalising ULIDs, digests, timestamps, session ids and clocks, the
    old and new files differ only in that line and in the run duration.

## B. WP-07 (`mhs/conformance/synth.py`, `tests_core.py`, docs, reports)

### B1. SAFE-014 probes every field a payload can carry (07b r3 blocker)

**Symptom.** `_declared()` looked only at the binding's top-level
`properties`, so a limit on any of these fields was missed:
- a field declared only inside `anyOf` / `oneOf`;
- a field listed only in `required`;
- a field the binding admits through open `additionalProperties`.

A class-only limit on such a field was put in `not_applicable` and never
probed. The class-blind heater (`n_anyof_class.py`, anyOf and `--oneof`)
accepted `target_temperature=500` and still passed SAFE-014 at CL3. With an
envelope limit, the same root cause gave a false gap
(`o_oneof_envelope.py`: the enforcing runtime was capped at CL2).

**Fix (`synth.py`).**
- `_branches()`. `_child()` / `schema_at()` merge the property from every
  `anyOf` / `oneOf` branch.
- `_reach()` sorts each path into one of three classes:

  | Class | Meaning |
  |---|---|
  | `declared` | in `properties` or in any branch |
  | `admitted` | not declared, but accepted: no `additionalProperties: false`; names only in `required`; `patternProperties`; an `additionalProperties` schema |
  | `refused` | undeclared, and the node, or every option of an `anyOf` / `oneOf`, admits no other property (`additionalProperties` or `unevaluatedProperties` false); or an index into a non-array. **Superseded in round 2 (C1):** `unevaluatedProperties` is ignored by `mhs.schema`, and the rule now has to be confirmed by validation |

  `_reachable()` also treats a numeric bound on an admitted field typed
  non-numeric as refused.
- An admitted field's leaf is built from the new `Binding.limit_schema` (the
  runtime's `plan.limit_schema`, the class input). The probe is sent only when
  the input that carries the field inside its limits is valid for the
  binding. Otherwise the result is a gap (`_UNBUILDABLE`), never "not
  applicable".
- Only a class-default limit on a refused field is `not_applicable`. A
  binding or envelope limit on a refused field is a gap on every side.

**Results.**
- Both `n_anyof_class.py` variants: the blind endpoint now fails SAFE-014
  (`target_temperature=301.0 returned completed`) and gets CL2. The runtime
  passes.
- `o_oneof_envelope.py`: the runtime passes, CL3.
- The lab: its bindings admit extra properties, so `volume` and
  `wavelength_min` are now probed (15 probes instead of 7). The runtime
  refuses them with `ENVELOPE_VIOLATION`. SAFE-014 still passes, and the lab
  stays at CL2.

**Tests.** `tests/conformance/test_safe014_reach.py`:
- `BranchDeclaredFieldTests` (2);
- `AdmittedFieldTests` (3: the lab; a class limit on a rejected field is
  n/a, but becomes probed when one branch is open; a declared limit on a
  rejected field is a gap on each side, and is probed when the field is
  admitted).

**Fail-first.** The pre-fix suite no longer exists on disk, so it was
reconstructed in `scratch/residual-b/pre07/` by reverse-applying this step's
edits. It reproduces the verifier's result: the anyOf blind endpoint passes
CL3. The new file failed there with 21 failures and 6 errors over 12 of its
13 tests (`failfirst_07b_final.log`). The 13th, `test_a_fixture_gets_the_read_sent`,
is a control. The reconstruction copies `server.py` as it was mid-step (A1 to
A3 applied), so only the conformance suite differs.

### B2. A fixture refusal covers only its own element and side (07b r3 major)

**Symptom.** Without a base input, one `out_of_envelope` refusal at
`points[0].z` covered `points[*].z` entirely. A tail-blind endpoint reached
CL3 (`p2_fixture_whole_path_cl3.py`).

**Fix.**
- `Gap` gains `kind` (`max` / `min` / `allowed`).
- Every gap now names a concrete element and a side. When there is no base
  input, a refused field or a container that cannot be built, the gap is
  expanded over `_element_paths()` × `_sides()`.
- `tests_core.safe_005` keys fixture coverage by `(concrete path, side)`,
  through the new `synth.fixture_sides()` and `synth.violated_sides()`.
- When `valid_input()` fails, `synth.base_from_fixture()` derives a base
  input from the `out_of_envelope` inputs: each out-of-limit value is put
  back inside its limit, and the result is checked with `binding.valid`. The
  normal element and side probes then run from that base, and a note says so.
- Uncovered gaps are listed per element with their sides, for example
  `points[2].z (max/min: no valid base input ...)`.

**Results.** `p2_fixture_whole_path_cl3.py`: the tail-blind endpoint fails
on `points[2].z=11.0` and `-1.0`, and gets CL2. The runtime passes.

**Tests.** `FixtureCoverageTests` (3):
- the derived base;
- with no derivable base (`base_from_fixture` patched to return None), an
  element-0-only refusal leaves `points[2].z` max/min and `points[0].z` min
  open, so SAFE-014 skips;
- the plan's per-element and per-side gaps, `fixture_sides` and
  `base_from_fixture` (unit level).

Two assertions in `test_safe014_completeness` (WP-07) changed for the new gap
wording. Its `ApplicabilityTests` follow B1.

### B3. Numeric allowed sets: above, below and between the members (07b r3 minor)

**Fix.** `_allowed_numbers()` builds the candidates:
- `max(allowed)+step` and `min(allowed)-step`, where the step is `multipleOf`
  or 1;
- one value inside the range, taken in this order: an `enum` member between
  the extremes that is not allowed; else the next grid or integer value after
  a member; else a midpoint.

It keeps only the candidates the leaf schema accepts once its `enum` /
`const` are set aside (the runtime strips those for a limited field), so an
enforcing endpoint answers with its limit check. If none is kept, it falls
back to the former single value above the set.

For `[1, 3, 5]` on an integer 0..10, the probes are `6`, `0` and `2`.

**Tests.** `NumericAllowedSetTests` (3). Endpoints that enforce the set as a
range (`step_range`) or only its upper side (`step_upper`) now fail, and the
runtime passes. A unit test covers the schema filter.

### B4. OP-001 names the reads it could not send (07b r3 minor)

**Fix.** `SuiteContext.read_probes` records each skipped read in the new
`SuiteContext.unsent_reads`. `cap_001` wraps the former body (`_cap_001`) and
adds a note: "N read-verb command(s) not sent, so not held to the read
revision rule: ...; supply a fixture (valid) for them". The verdict is
unchanged.

**Tests.** `UnsentReadTests` (2: the note, and the fixture control).

### B5. Docs, reports and change-log wording

- `docs/conformance.md`: the SAFE-014 paragraph (reach rule, numeric allowed
  sets, per-element and per-side gaps, fixture-derived base, the lab
  correction) and the OP-001 paragraph (unsent reads).
  - The false claims "`SAFE-014` never passes with a limited path unprobed"
    and "nothing can be sent" (for the lab) are gone.
  - Not applicable is now stated precisely: a class-default limit on a field
    the binding's schema rejects.
- `MHS/conformance/reports/lab-cl2.json` was regenerated with the documented
  command; it exits 5, as expected for CL2 below its CL4 claim.
  - Unchanged: level CL2, the file name and every verdict.
  - Changed: the SAFE-014 detail lists the 15 probes, and the stale "nothing
    to send" note is gone.
  - It validates, and `verify --reference lab` exits 0.
- The other four reports differ from a re-run only in run-specific details
  (PROTO-030 / EVID ids and timings). They were left unchanged, and each
  verifies (exit 0).
- `WP-07.md` gets an erratum section (the earlier claims are superseded).

## Behavioural changes (summary)

- **Revision check at dispatch.** A command whose `expected_revision` went
  stale during its pre-call state read is `rejected` `MHS.CONFLICT.REVISION`
  instead of running.
- **Configure writes.** These are refused now:
  - every key of a readOnly state root;
  - readOnly positions of draft-07 tuple arrays and their `additionalItems`.
- **Hardware and hybrid concurrency.**
  - Non-read bindings run exclusively by default. A concurrent second command
    gets `MHS.DEVICE.BUSY`, which is retryable.
  - Opt out per binding with `constraints.concurrency: "shared"`.
  - Device summaries publish the effective `exclusive`.
- **Resets.** A reset refused after `bridge.reset()` ran is `failed`, not
  `rejected`, still `RESET_REFUSED` with `latched: true`. Its revision
  advances.
- **SAFE-014 coverage.** More is probed:
  - fields declared in branches, or admitted;
  - numeric allowed sets on both sides and inside;
  - from a fixture-derived base.

  Endpoints that ignored such limits now fail where they used to pass, and
  gaps are reported per element and side.
- **OP-001.** It notes the reads it could not send.

## Compatibility notes

- `Capability.exclusive` keeps its default (False). Only the runtime rule on
  hardware and hybrid devices changed. Existing explicit `exclusive=True`
  bindings behave as before.
- `Gap(limit_path, path, reason)` still works positionally; `kind` defaults to
  None. `_UNDECLARED` is kept as an alias of `_REFUSED`, with new wording.
- New in `mhs.conformance.synth`:
  - the public functions `base_from_fixture`, `fixture_sides` and
    `violated_sides`;
  - the field `Binding.limit_schema`, with a default;
  - the `schema=` keyword of `_element_paths` (private).

  `_not_allowed` (private) now returns a list of values.
- `SUITE_VERSION` stays 1.3.0: verdicts of the published reference reports
  are unchanged, and only the lab report's details changed (it was
  regenerated).

## GREEN

Before this step (Python 3.14):

| Suite | Result |
|---|---|
| SDK | 1439 OK (5 skipped) |
| Registry | 27 OK |
| Integration | 93 OK |
| Site | OK, 1 warning (stale downloads) |

`MHS/drivers/EXEMPLARS.txt` and `MHS/sdk/examples/thermostat` do not exist
yet, so the driver-check line of GREEN does not apply.

After this step:

| Suite | Python 3.14 | Python 3.10 |
|---|---|---|
| SDK | **1465 OK (5 skipped)**, +26 tests | **1465 OK (10 skipped)** |
| Registry | 27 OK | — |
| Integration | 93 OK | — |
| Site | OK, the same stale-downloads warning | — |

The 26 new SDK tests:
- `tests/safety/test_bindings_revisions.py`: `DispatchRevisionTests` (4),
  `ConfigureReadOnlyGapsTests` (4), `HardwareDeviceLockTests` (5);
- `tests/conformance/test_safe014_reach.py`: 13 tests.

Other checks:
- `tools/build_applicability.py --check`: rc 0, `stale: false`.
- Every published report verifies by re-run (exit 0).
- No forbidden or research directory changed. `find -L <dir> -newer
  <marker>` lists only `labs/.../site.less`, a symlink to `/dev/null`.
- The integration children wrote `MHS/sdk/src/mhs/{,schema/,_server/}__pycache__`
  (the known WP-08 item). These directories did not exist before this step,
  and they were removed.

Verifier probes re-run on the final tree (copies in
`scratch/residual-b/probes/`):
- `s_confirm_race_nodelay.py 20`: 0/20 lost, 0/20 false confirmations.
- `s_confirm_race.py` 0.02, 0.05, 0.3: retried.
- `s_hold_new_estop.py`: 2 retries during the reset. Its reset now reads
  `failed estop_during_reset` (A4).
- `s_restore_reassert.py`: the stop is re-asserted after the restore.
- `r4_int_interlock.py`, `r5_server_int.py`, `r6_pyobj_int.py`: every error
  reply reads `unknown`; the reset is refused; no `HEAT 1`.
- `r1_gym_nested.py`: nested `Dict` refused. The `Tuple` residual is
  documented.
- `shared_bridge.py`, `silent_setattr.py`: 0 hardware moves.
- `test_r3_findings.py`: 4/4 pass.
- `n_anyof_class.py` (anyOf and oneOf): the blind endpoint fails SAFE-014
  (CL2); the runtime passes.
- `o_oneof_envelope.py`: the runtime passes (CL3).
- `p2_fixture_whole_path_cl3.py`: the tail-blind endpoint fails on
  `points[2].z` (CL2); the runtime passes.

## Follow-ups

- **WP-09 (spec).**
  - A reset refused after `bridge.reset()` ran is a `failed` receipt
    (`RESET_REFUSED`, `latched: true`) and advances the revision.
  - Plan 3.6 step 12, as implemented: non-read bindings of hardware and
    hybrid devices are exclusive unless they declare
    `constraints.concurrency: "shared"`; summaries publish the effective
    `exclusive`. (Refined in round 2, C3: the class concurrency counts too,
    and a binding is never weaker than its class.)
  - `expected_revision` is re-checked immediately before dispatch.
  - The configure field rules for a readOnly root and draft-07 tuple arrays.
  - The SAFE-014 reach and coverage rule: per element and side; a fixture
    refusal covers what it names; a fixture-derived base input.
  - Numeric allowed-set probes.
  - The OP-001 note on unsent reads.
- **WP-06 (`docs/driver-authoring.md`, gate G8).**
  - A limited binding without a buildable base input still needs a `valid`
    fixture or an `out_of_envelope` input from which the suite can derive
    one.
  - Hardware drivers whose non-read bindings may run concurrently must
    declare `constraints.concurrency: "shared"`. (Refined in round 2, C3:
    this works only for an extension or a class whose own concurrency is
    `shared`.)
- **WP-08 (known).** The integration children still write `__pycache__`
  under `MHS/sdk/src`. The directories this step's runs created were removed
  afterwards.
- **WP-05 (residual, unchanged).** Gymnasium `Tuple` elements (top level or
  inside a `Dict`) get structure but no limits. This is simulation only and
  is documented.

## Round 2 — open issues of the RESIDUAL-B verifier

The independent verifier of this step re-ran every probe of the 22 issues
(all fixed) but found one blocker and three minors. Its probes are in
a temporary verification directory
(read-only). Scratch for this round:
a second temporary directory.

| # | Sev. | Issue | Status | Tests |
|---|---|---|---|---|
| C1 | blocker | SAFE-014 "not applicable" fails open (`v_uneval.py`, `v_pattern_branch.py`) | **fixed** | `test_safe014_reach.ValidatorProvenReachTests` (5) |
| C2 | minor | the dispatch-time revision refusal kept the cumulative-budget draws (`v_dispatch_budget.py`) | **fixed** | `DispatchRevisionTests` (+1) |
| C3 | minor | full manifests published an invented `concurrency: "shared"`; the class concurrency was ignored (`v_manifest_concurrency.py`) | **fixed** | `HardwareDeviceLockTests` (+3; hybrid added to the summary test) |
| C4 | minor | a reset refused after `bridge.reset()` advances the revision unconditionally | rule kept; plan deviation stated below | — |

Fail-first: the final new tests were run against a copy of the tree with the
pre-round `synth.py`, `tests_core.py` and `server.py`
(`scratch/residual-b2/pre/`): 20 failures and 2 errors over 8 of the 9 new
tests (`failfirst_final.log`). The 9th,
`test_a_refusal_only_validation_shows_is_a_gap_never_a_pass`, is a guard
that already held, as did the hybrid case added to the summary test.

### C1. "Not applicable" must be proven, also by validation (synth.py)

**Symptom.** `_reach()` / `_refuses()` / `_reachable()` called a field
refused from the schema's shape alone:

- `unevaluatedProperties: false` counted as a refusal, but `mhs.schema`
  ignores that keyword, so the endpoint accepts the field;
- a field matched by a string-typed `patternProperties` in one `anyOf`
  option was refused for a number, although the other option admits one.

The class-default limit on `target_temperature` was then "not applicable".
The class-blind endpoint completed `target_temperature=500` (class max 300)
yet passed SAFE-014 at CL3, in-process and over a client.

**Fix.**

- `_refused(schema, tokens, root, numeric=)` is the structural rule. It
  reads only keywords the validator applies, the way it applies them:
  - `additionalProperties: false` next to the node's own `properties` and
    `patternProperties` (`re.search`);
  - a `type` that cannot hold the value: no `object` for a property, no
    `array` for an index, and at a numeric leaf no `number` / `integer`;
  - `maxItems`, `prefixItems` with `items: false`, and draft-07
    `items: [...]` with `additionalItems: false`;
  - a local `$ref`, one `allOf` member, or every `anyOf` / `oneOf` option.

  Every subschema a matched property must satisfy is followed. Keywords
  that only add constraints (`not`, `if` / `then` / `else`,
  `dependentSchemas`, `propertyNames`, `enum` / `const`) and ignored ones
  (`unevaluatedProperties`) are never a reason. A subschema the validator
  cannot read (boolean, unknown type name, bad pattern, unresolvable `$ref`)
  is never refused.
- `_reach()` applies `_refused()` first, also to declared paths (a branch
  that types the field as a string; a `$ref` to a closed object with a
  sibling `properties`). Then it sorts into declared or admitted as before.
- `_reachable(binding, bound, concrete, base, index)` confirms a refusal by
  validation:
  - `_carriers()` builds inputs from the base that carry the field inside
    its limits. The leaf comes from the limit schema or the binding's
    schema, and is also set to each of `_inside_values()`: the allowed
    members, else the bound ends, the integers next to them, the midpoint
    and 0.
  - Under a numeric bound, only a number at the leaf counts.
  - If any carrier validates against the binding's schema, the field is
    `admitted` and probed.
- `_probes_at()` sends an admitted field's probes from the first valid
  carrier. When there is none, it records an `_UNBUILDABLE` gap.
- `envelope_probe_plan()` decides per element. `not_applicable` lists the
  path when every element is refused, and otherwise each refused element.
- Wording:
  - `_REFUSED` now reads "the binding's input schema rejects every input
    that carries it";
  - the SAFE-014 note now says "no valid input of the binding can carry";
  - the `safe_005` docstring and the `docs/conformance.md` SAFE-014
    paragraph were updated.

  The false sentence "no payload can carry it" is gone.

**Results.**

- `v_uneval.py` and `v_pattern_branch.py`, in-process and over a client:
  - the plan probes `target_temperature` max and min;
  - the class-blind endpoint fails SAFE-014 (`target_temperature=301.0
    returned completed`) and gets CL2;
  - the runtime passes, at CL3.
- `probes/adversarial_reach.py` (17 schemas) shows 0 fail-open cases.
  - Genuinely refused fields stay not applicable, and the blind endpoint
    refuses them `INPUT_INVALID` when called directly: `allOf` closed,
    `additionalProperties` string, pattern-typed string, `$ref` closed with
    a sibling.
  - A refusal only validation can show (`not`, `if` / `then`,
    `propertyNames`, `maxProperties`) is a gap, so SAFE-014 skips and never
    passes. This is conservative: a runtime with such a schema stops at CL2
    unless a fixture covers the gap.

**Behaviour change.** A class-only limit on a field that is declared but
cannot hold a number (a string-typed branch, or `$ref` to a closed object
with a sibling) is now not applicable. Before, it was probed, and the
runtime itself failed with `INPUT_INVALID` / `MANIFEST_INVALID`. A binding or
envelope limit there is a gap on every side.

**Reports.** I re-ran all five published reports in scratch:

- verdicts and `subject.manifest_digest` are identical;
- the SAFE-014 details are identical, and only PROTO-030 / EVID-015 / EVID-016
  differ, by run ids and timings;
- `verify` exits 0 for each.

No report was regenerated. `SUITE_VERSION` stays 1.3.0.

### C2. A dispatch refusal releases the cumulative draws (server.py)

`_start_operation(reservations=...)` receives the command's cumulative-budget
reservations. The worker's `moved_to` branch calls `_release_cumulative`
next to `_return_permit`, so it behaves like the registration-path
`_refuse`.

`v_dispatch_budget.py`: the stale `dose=6` is refused `CONFLICT.REVISION`
with no bridge call, and a fresh `dose=6` now completes. The new test also
checks that the retry draws only its own amount: 6 + 4 fits the budget of
10 per rolling hour, and a further 1 is `CUMULATIVE_LIMIT`.

A bridge `Busy` rejection and a pre-dispatch cancellation still keep the
draws. This is unchanged and fail-safe: the bridge's word, or a non-rejected
outcome.

### C3. Manifests publish the concurrency the runtime applies (server.py)

**Runtime rule.** `_effective_concurrency()` applies on hardware and hybrid
devices. Simulated and replay devices keep the declared `exclusive` flag.

| Binding | Effective |
|---|---|
| `exclusive=True` | `exclusive` |
| catalogued read class | `shared`, unless the binding declares `exclusive` / `serialized` (CAP-014) |
| other | the stricter of the binding's `constraints.concurrency` and the class `concurrency` (spec 00 section 6; ADPT-025: never weaker than the class); `exclusive` when neither declares one |

`_takes_device_lock()` returns true unless the effective concurrency is
`shared`, so `serialized` also holds the lock. Stops and `achieved_by`
actions stay exempt (SAFE-029).

**New on hardware.**

- An invoke class whose class concurrency is `shared` (`cap.compute.cancel.v1`,
  `cap.sensing.image.v1`, ...) runs beside a running command.
- A binding that declares `shared` for an `exclusive` class (`grasp`) is
  `MHS.DEVICE.BUSY`.

**Publication.** `Capability.published_constraints(concurrency)` is new, and
`Capability.manifest()` / `Device.manifest()` take a keyword-only
`concurrency`. `MHSServer._device_manifest()` passes `_published_concurrency()`
to `devices.get`, to `devices.list detail=full`, to the reference-file
manifest and to `schema.get`. What gets published:

- **Hardware and hybrid:** the effective value. A stop or `achieved_by`
  action publishes `shared`.
- **Simulated and replay:** the declared constraints, plus `exclusive` for
  an `exclusive` binding.
  - Nothing is invented: a binding without constraints publishes
    `constraints: {}` (before: `{"concurrency": "shared"}`).
  - A simulated manifest rebuilt into a hardware device therefore keeps the
    default lock.
- **Summaries:** on hardware and hybrid devices, `exclusive` is
  `published != "shared"`.

`v_manifest_concurrency.py` now gives:

- `devices.get` constraints `{'concurrency': 'exclusive'}` for both bindings;
- summaries `exclusive: true`;
- a second command `MHS.DEVICE.BUSY`.

The reference devices declare their constraints, so their manifests and
digests are unchanged.

### C4. Failed reset after `bridge.reset()`: the revision rule (deviation stated)

A reset refused after `bridge.reset()` ran (`estop_during_reset`, or
`stop_path_pending` with `bridge_reset: "completed"`) is `failed` and
advances the revision unconditionally. This is a **deviation from plan
3.7**, which says that `failed` increments only when the state hash changed.

It is kept on purpose. The reset path reads no state around
`bridge.reset()`. The completed reset already bumps unconditionally
("unknown counts as moved"). A missed bump would let a stale
`expected_revision` run after a device reset. WP-09 is asked to state it in
the spec. Hybrid mode was added to
`test_the_device_summary_publishes_the_lock_the_runtime_applies`.

### Compatibility (round 2)

- `synth`:
  - `_refuses` (private) is gone;
  - `_reach(numeric=)` and `_reachable(base, index)` gain parameters;
  - `_refused`, `_carriers`, `_carrier` and `_inside_values` are new
    (private);
  - the text of `_REFUSED` changed, and `test_safe014_completeness` now
    compares with `_synth._REFUSED`.
- Manifests: the digest changes for a simulated device with a binding that
  has no constraints, which now publishes `{}`. The published reference
  reports are unaffected (re-run digests are equal).
- The e2e transcript was regenerated in a scratch layout (with
  `MHS/conformance`). It gives PASS and differs from the committed
  `MHS/sdk/docs/e2e-transcript.txt` in 0 lines after normalising
  ids, digests and times, so it was left unchanged.

### GREEN (round 2)

Before this round (Python 3.14; `scratch/residual-b2/before_*.log`):

| Suite | Result |
|---|---|
| SDK | 1465 OK (5 skipped) |
| Registry | 27 OK |
| Integration | 93 OK |
| Site | OK, 1 warning (stale downloads) |

After this round (`after_*.log`):

| Suite | Python 3.14 | Python 3.10 |
|---|---|---|
| SDK | **1474 OK (5 skipped)**, +9 tests | **1474 OK (10 skipped)** |
| Registry | 27 OK | — |
| Integration | 93 OK | — |
| Site | OK, the same stale-downloads warning | — |

The driver-check line of GREEN does not apply: `MHS/drivers/EXEMPLARS.txt`
and `MHS/sdk/examples/thermostat` do not exist.

The 9 new tests:
- `ValidatorProvenReachTests` (5);
- `DispatchRevisionTests.test_a_command_refused_at_dispatch_gives_back_its_cumulative_budget`;
- `HardwareDeviceLockTests` (3).

Other checks:
- every published report verifies by re-run (`verify`, exit 0, 5/5);
- `tools/build_applicability.py --check`: rc 0, `stale: false`;
- the verifier's four probes give the results above (`final_v_probes.log`);
- edits are only in WP-04 / WP-07 files and this note;
- no forbidden directory changed (`find -newer` on `labs`, `robots`, `work`,
  `clone_audit_2026-10-12`, the catalog sources, `OpenAI4S-Playground` and
  `_backup` is empty);
- the integration children's `MHS/sdk/src/mhs/{,schema/,_server/}__pycache__`
  were removed.

### Follow-ups (round 2)

- **WP-09 (spec).**
  - C3 rules. Hardware and hybrid effective concurrency comes from the
    binding and the class, never weaker than the class (ADPT-025);
    `serialized` holds the device lock. Manifests publish the effective
    value, and simulated manifests invent nothing.
  - The SAFE-014 not-applicable rule (C1).
  - The C4 deviation: a failed reset after `bridge.reset()` advances the
    revision.
- **WP-06 (`docs/driver-authoring.md`).**
  - `constraints.concurrency: "shared"` opts a hardware binding out of the
    lock only for an extension or a class that is itself `shared`.
  - A schema refusal that only `not` / `if` / `propertyNames` express makes
    SAFE-014 skip; use `additionalProperties: false` or supply a fixture.
- **WP-08 (known).** The integration children still write `__pycache__`
  under `MHS/sdk/src`. The directories this round's runs created were
  removed.
