# Declared re-enable after a reset, and a declared terminal e-stop

A device may now declare how it recovers from an e-stop. `safety.estop.reenable` names the one command that re-enables a device whose stop leaves it disabled: the latch refuses it, the reset of such a device only releases the latch, and conformance test TSAFE-001 sends it after the reset and before its recovery command. `safety.estop.terminal` states why a device's native stop cannot be undone without a new native session: after that stop the endpoint refuses every reset with `terminal_estop` and keeps the latch, and the conformance runner gives every later test a new endpoint. A reset may re-establish communication only when that changes nothing on the device. A device that declares neither field behaves exactly as before.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 in a private project copy
(`work/handoff-runs/claude-20261104/development/b2-safety-contract/`), in two rounds: the first added the two
declarations; the second follows the review of that change by a second model (Claude Sonnet, review s7, in
`work/handoff-runs/claude-20261104/sonnet-review/s7/`) and the orchestrator's decisions on it. Not integrated. No
hardware, ROS graph, DLL or human review is involved anywhere below.

## Why

Two packages were blocked on `SDK_BUG` with no honest package-only fix:

- `robots/frankarobotics__franka_ros2`: the e-stop switches the spine off (`~/switch_off`), and after an accepted
  reset the drive stays `SwitchedOff`, so TSAFE-001's recovery probe (`MoveAbsolute`) failed. Re-arming inside the
  reset had been rejected by the earlier review (SAFE-042: releasing the e-stop must not restart anything). The
  upstream has its own `~/switch_on` service (`spine_action_server.py:90-95`, callback `:242-248`), but nothing in
  the contract let a package say "this is the new start command".
- `labs/thorlabs__light_analysis_examples`: the e-stop closes the TLBC2 session, which the upstream says must be
  reinitialized before reuse (`TLBC2.py:229-239`). The package's `@reset` refused every reset, so TSAFE-001 failed
  (`bridge_refused`), and SAFE-014 then ran on the same SAFE-group endpoint whose session was closed. Reopening the
  session from the reset would have been a faked recovery.

## Design

Re-enable (CORE-086, SAFE-042):

- Declared on the action: `@action(..., reenable=True)` or `Action(..., reenable=True)`; published as
  `safety.estop.reenable` (a capability id). One action, bound to exactly one resource, accepting an empty input
  (the empty object must validate against its input schema, checked with the SDK's own JSON-schema validator, so a
  requirement in `oneOf`, `anyOf`, `allOf`, `minProperties` or a non-object type counts), never a read, a stop class
  or a `safe_state.achieved_by` action. The driver model refuses a malformed declaration (gate G3), `MHSServer`
  refuses a malformed manifest at start-up in every mode, whatever produced it, and a device with a malformed
  declaration that is put into `server.devices` after start is refused on its first use
  (`MHS.ADAPTER.MANIFEST_INVALID`, `details.reason` `estop_recovery_invalid`, already at `mhs.session.open`; the
  e-stop still reaches it).
- The re-enable is an ordinary effectful command: the latch refuses it (`MHS.SAFETY.ESTOP_ENGAGED`, CORE-075), and
  arming, permits, limits and interlocks apply. It can never be exempt from the latch, because the exempt kinds are
  refused as declarations, and a declaration that names one is never reported as the re-enable.
- A reset of such a device only releases the latch; any native recovery the device needs after a stop, fault
  clearing included, belongs in the re-enable. What the SDK enforces, at definition, at start-up and in gate G3:
  a decorated driver that declares a re-enable has no `@reset` hook (the model refuses it; the start-up check
  refuses a declaring device whose driver bridge reports a hook, `Driver.reset_hook`), and a family driver's
  `safety_bindings.reset` does not call the re-enable's native target (the target members of the reset binding and
  of the re-enable's `commands` entry, compared exactly as declared; a ROS name is already absolute and normalised
  by the bridge validator). What stays an author obligation, checked by review: a family reset binding that
  re-arms the device through another target, or through the same one spelled differently. A completed reset names
  the re-enable in `output.reenable`.
- An e-stop that lands while a command of a device that declares a re-enable is in flight (dispatched, not yet
  returned): such a command may land after the native stop and enable the device again, either the re-enable itself
  or an upstream cancel path that re-arms after its own quick-stop (the Franka spine, `spine_controller.py:404-434`).
  The stop path runs at once, waits for every effectful command of the device still in flight then (stop,
  safe-state and read actions excepted; a read is what the latch counts as one, so a hung catalogued read does not
  delay the confirmation) to settle, and runs again. Until that second run succeeds the e-stop is not confirmed: the
  receipt is `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` with `details.reason` `command_in_flight` (and
  `awaiting_operations`), the latch stays, a reset is refused (`stop_path_pending`), and the background retry
  (CORE-077) records the confirmation once the stop after those commands succeeded. Commands that settle inside the
  e-stop budget give a `completed` receipt whose stop ran after them. A device without a declared re-enable keeps
  the single run. The physical stop stays the independent path (SAFE-045, SAFE-046), and the receipt never claims
  more than was reached (SAFE-044). Round 2 waited for the re-enable only (`reenable_in_flight`); round 3 widened
  the rule as the orchestrator decided; round 4 excepted reads (review s7 re-check, N-01).
- Consequences, by design (review s7 re-check, N-02). The wait has no upper bound: a command that never settles keeps
  the e-stop unconfirmed and the device unresettable (`stop_path_pending`) until the endpoint restarts, the same
  fail-safe outcome as a native stop that never returns, and the physical stop stays the way to stop the device.
  Hosts see a `failed` `SAFE_STATE_UNREACHED` receipt with `command_in_flight` for every e-stop issued during
  motion on such a device, although the first native stop succeeded, until the cancelled command settled and the
  background retry recorded the confirmation; so do TSAFE-001 and SAFE-028 on a shared endpoint that still has a
  long-running operation of an earlier test.
- TSAFE-001, for a device that declares one: the re-enable sent while latched must be a `rejected`
  `ESTOP_ENGAGED` with no bridge call; after the reset and the unchanged no-auto-resume reads it must complete; then
  the recovery probe runs as before. A permit-gated re-enable whose permit the suite cannot obtain (a hardware
  device without `--approvals`; an e-stop revokes every permit, SAFE-036, so the permit cannot be taken before the
  e-stop) skips the test before anything is sent; a permit failure after the e-stop and the reset is a failure,
  never a skip.

Terminal e-stop (CORE-087, SAFE-048):

- Declared as one sentence: the class attribute `estop_terminal`; published as `safety.estop.terminal`. It needs a
  stop path (a declared native stop, a bound `cap.motion.estop.v1` or a safe-state action) and excludes `reenable`;
  both are checked by the model and at start-up, and the schema refuses the pair.
- A new native session is any reconnection, reopening or re-initialisation that may change the device (energise
  it, enable motion, or start a process that may initialise hardware). Re-establishing communication that changes
  nothing on the device is not one and may be a reset step.
- When the endpoint starts the stop path of such a device (`_start_estop_attempt`, under the endpoint lock, before
  any bridge I/O) it records the terminal stop. Every later `mhs.safety.reset` of that device on that endpoint is a
  `rejected` `MHS.SAFETY.RESET_REFUSED` with `details.reason` `terminal_estop`, `details.terminal` the declared
  sentence, `details.latched: true` and a `remediation`, without calling the bridge. The flag is re-checked under
  the lock right before the bridge reset, and again after it (a stop path that started inside the bridge reset gives
  a `failed` refusal of the same reason); the latch is never released then. `mhs.safety.status` reports
  `estop.terminated: true`.
- Recovery is a new endpoint: a latch it restores from `state_dir` was not engaged by its own stop path, so an
  operator resets it as usual, until a stop path starts on that endpoint; a replay of the latching e-stop's
  `command_id` reruns the stop path (CORE-171), and from then on that endpoint refuses the resets too (review s7,
  S7-05; the behaviour was already so, the text now says it). The terminal record is per endpoint and is not
  persisted.
- TSAFE-001, for a device that declares one: after the e-stop and the latched refusal, the reset must be that
  refusal with the declared sentence and no bridge `reset` call, the status must stay engaged, and the probe must
  still be refused `ESTOP_ENGAGED`. SAFE-041 skips such a device before it e-stops it (every reset is refused, so an
  interlock refusal cannot be told apart).
- Runner (CON-022): a test that engages a declared terminal e-stop cannot restore its fixture. In-process, the
  context of that endpoint is retired after the test and the next test of the group gets a new `factory()` call;
  over one shared endpoint, the tests that e-stop (`TestCase.estops`: TSAFE-001, SAFE-028, SAFE-041) run after
  every other test that sends a command. The report says which tests engaged it.

Reset policy (SAFE-042, CORE-087; the orchestrator's decision on the open items of the reset scan): a reset may
re-establish communication (reconnect a socket, re-attach a client object, reopen a handle) only when that changes
nothing on the device. Anything that may energise the device, enable motion or start a process that may initialise
hardware is a declared re-enable (CORE-086), or the ordinary command that follows the reset, and never a reset step;
a device whose stop cannot be undone within the endpoint declares a terminal e-stop (CORE-087).

Guarantees that do not weaken: the e-stop is never refused; the latch is set first; a reset never resumes anything;
the re-enable is never latch-exempt; a terminal refusal only adds refusals and never releases a latch; and every
manifest, reference file, receipt and conformance verdict of a device that declares neither field is unchanged (the
new keys are published only when declared, and the TSAFE-001 detail of an undeclared device is byte-identical). That
a reset never re-arms a device that declares a re-enable is enforced as far as the SDK can see (no decorated
`@reset` hook; no family reset binding on the re-enable's native target); beyond that it is a review obligation.

## Normative text

In the precedence of `MHS/spec/README.md`:

- Schemas: `device.schema.json` and `reference.schema.json` `safety.estop` gain the optional `reenable`
  (`capabilityId`) and `terminal` (1 to 500 characters) and refuse both together; mirrored to `mhs/_data/schema`.
- `core.md`: CORE-086 (re-enable: the empty-input rule by validation, late devices, the reset releases the latch
  only, what the SDK enforces and what review checks, an e-stop while commands are in flight) and CORE-087
  (terminal e-stop: what a new native session is, the restored latch until a stop path starts there) in §6.3;
  CORE-077 adds the failure reason `command_in_flight`; CORE-080 lists `terminal_estop`; CORE-082 and CORE-093 name
  `output.reenable`; CORE-160 holds CORE-086 and CORE-087 in both modes.
- `driver-profile.md`: DRV-010 lists `estop_terminal`; the `@reset` row (communication only; not beside a
  re-enable) and the `@action` paragraph (`reenable=True`, no `@reset`); DRV-012 states the reset policy, the
  decorated rule, the family rule and the review obligation.
- `02-wire-protocol.md` §11.3: the reset output and refusals (SAFE-003).
- `04-safety.md`: SAFE-040 adds `command_in_flight`; SAFE-042 (the reset policy, the declared re-enable, what the
  SDK refuses and what review checks); §5.3 SAFE-048 (terminal e-stop; a new native session as in CORE-087; the
  restored latch); §11 hooks.
- `01-conformance.md`: CON-022 (new endpoint after a terminal e-stop, ordering on a shared endpoint); the mandatory
  negative-test table rows for SAFE-042 and SAFE-048.
- Generated: `mhs/conformance/traceability.json` (TSAFE-001 → SAFE-040, SAFE-042, SAFE-048),
  `mhs/conformance/applicability.json` (582 normative ids, 52 executable; regenerated for suite 1.4.0 and the
  shifted line numbers), `MHS/sdk/INTERFACE.md`.
- Docs: `MHS/sdk/docs/driver-authoring.md` (recovery after an e-stop), `MHS/sdk/docs/conformance.md` (notes on
  suite 1.4.0, report and reference tables), `MHS/conformance/README.md` and `MHS/sdk/docs/reports/README.md`.

## SDK changes

Round 1: `mhs/driver/spec.py` (`Action.reenable`), `decorators.py` (`action(reenable=)`), `model.py` (binding flag,
`estop_terminal`, manifest keys, definition checks), `families.py` (pass-through, reset-binding check), `base.py`
(declaration and docs), `server.py` (start-up check, terminal record, reset refusal and its re-checks, reset
`output.reenable`, status `estop.terminated`), `reference_file.py` (reference keys and REFERENCE.md lines),
`conformance/model.py` (`TestCase.estops`), `conformance/tests_core.py` (TSAFE-001, SAFE-041, probe exclusion of the
re-enable, terminal tracking), `conformance/suite.py` (retirement, shared-endpoint ordering, notes).

Round 2 (review s7):

- `model.py`: `empty_input_problem` (the empty object validated with `mhs.schema.validate`), and the rule that a
  decorated driver declaring a re-enable has no `@reset` hook (S7-01, S7-03).
- `base.py`: `Driver.reset_hook`, the decorated hook a driver bridge runs on a reset (None for family drivers).
- `server.py`: the start-up check refuses a declaring device whose bridge reports a reset hook and validates the
  empty input (S7-01, S7-03); `_check_late_recovery` runs the start-up check once per device object on first use,
  in every mode (S7-02); `_estop_reenable` reports a declaration only when it names a capability bound exactly once
  and exempt from nothing (S7-02); `_start_estop_attempt` and `_EstopAttempt` (`awaiting`, `resent`): the stop path
  waits for an in-flight re-enable, runs again, and the receipt reason `reenable_in_flight` (S7-04; widened in
  round 3).
- `families.py`: the reset-binding check's message and docstring name the re-enable's native target and say what
  is compared (S7-06).
- `conformance/tests_core.py`: `_reenable_permit_unavailable`; TSAFE-001 decides before the e-stop whether the
  re-enable's permit can be obtained, and fails on a later permit failure (S7-07).
- `conformance/report.py`: `SUITE_VERSION` 1.3.0 → 1.4.0 (see Decisions).

Round 3: `server.py` `_start_estop_attempt` waits, on a device that declares a re-enable, for every command in
flight when the stop path starts (stop and safe-state actions excepted), and the receipt reason is
`command_in_flight`; devices without a declared re-enable keep the single run. Round 4 (review s7 re-check, N-01):
reads are excepted too, with the latch's own predicate (`_is_read_capability` of the operation's binding).

Tests: `tests/safety/test_estop_recovery_declarations.py`, 49 methods (32 in round 1, 15 in round 2, 2 in round 3: a
move whose cancel path re-arms the drive after the first stop, and its counterfactual on a device without a declared
re-enable, where the stop is confirmed while the drive is on; 2 in round 4: a hung catalogued read does not delay
the confirmation, a hung effectful command still does; 51 methods in all). Round 2's 15: the reset-hook
rule at definition, at start-up in both modes, and probe A of review s7; late devices in both modes; the validated
empty input for six schema shapes; an e-stop during an in-flight re-enable, outside and inside the budget, with the
counterfactual of an undeclared switch-on; the replayed e-stop on a new endpoint; the permit-gated re-enable before
and after the e-stop). `tests/endpoints/test_conformance_suite.py` expects the new TSAFE-001 trace.

Mutation check of round 2 (`DEV/scratch/mut-s7/make.py`, copies of the source with one rule removed each; tests
that fail, with their failing subtests): no model hook rule (1 test, 2 subtests), no start-up hook check (1, 2), no
late-device check (1, 2), the old two-key empty-input check (1, 5), no wait for the in-flight re-enable (2), the
TSAFE-001 permit decided after the e-stop (1), an unchecked re-enable reported (1, 3). No mutant survives. Review s7
reported its seven mutants of round 1 all caught. Round 3 (`DEV/scratch/mut-r3/make.py`, fresh copies, the 49
methods): the seven again, plus the round-2 rule that waits for the re-enable only (fails the cancel-path case); 8 of
8 caught. Round 4: waiting for reads too fails the hung-read case.

## Packages

- `robots/frankarobotics__franka_ros2`: binds `~/switch_on` as `x-cap.frankarobotics.spine_switch_on.v1` with
  `Action(reenable=True)` (no reset binding, so the reset re-arms nothing); five cited switch-on Facts; the fake
  answers the service; six new package cases. After review s7 (S7-08) the docstring and notes also say that a
  successful `~/halt` (`spine_controller.py:318-334`) and a cancelled move (`:404-434`) re-arm the drive too; both
  are refused while latched. Round 3: `test_safety_freshness.py` gains two cases. In the first, the e-stop's first
  run is held at its safe-state read while the fake's cancel path re-arms the drive (`rearm_cancelled_motion`,
  `finish_cancelled_motion`); the stop path then runs again and the drive ends `SwitchedOff`, and the receipt says
  `command_in_flight`. The second is the counterfactual without the rule: the e-stop answers before the move
  settled, and only the ROS bridge's own guards (a pending goal, or native activity after a stop, keeps the safe
  state unconfirmed) make the background retry stop the drive again. The stock case now sends its e-stop from a
  thread, because the answer no longer comes before the cancelled move ends. 27 cases pass. G1-G9 pass with no
  finding, digest `sha256:ac2616df9ac90d9d7989c50feefd504010dadac7ca59d3ee333bcfc21f7b90ae`.
- `labs/thorlabs__light_analysis_examples`: declares `estop_terminal` and drops the `@reset` hook that refused every
  reset; `session.py` is unchanged, so the closing state stays irreversible. After review s7 (S7-09) the declared
  sentence separates the upstream facts (a closed session must be reinitialized, `TLBC2.py:229-239`; `open()` resets
  the instrument and sends it initialization commands, `TLBC2.py:201-208`, a new Fact) from the package policy (only
  a new native session on a new endpoint recovers it). G1-G9 pass with no finding, digest
  `sha256:a4cce3c3758cf72b6f7629e3501772c14ac97275dbf7fea757abfc2ce32c3704`.
- `robots/itheima1__mcp_robot` (R2): its `@reset` re-enabled the torque of servos 1 to 6 (`sync_enable_torque`). The
  hook is removed; the torque comes back only through the declared re-enable `x-cap.itheima1.enable_all_torque.v1`
  (`servo_control_standalone.py:828-863`, the call of the upstream's `arm_tighten` tool, `mcp_server.py:333-347`).
  It already fits the round-2 rule (no `@reset` hook). Digest unchanged,
  `sha256:ee501c3edf6f781fd224e46b380f93e4847c195903c31ea6306cd0f24e830a13`.
- `robots/xarm-developer__xarm-python-sdk` (the R2 robot exemplar, authored by claude-sonnet-5-5): its `@reset` ran
  `clean_error`, `clean_warn`, `motion_enable(True)`, `set_mode(0)` and `set_state(0)`. The hook is removed; the new
  declared re-enable `x-cap.xarm-developer.enable_motion.v1` runs all five (`xarm_api.py:1588-1604`, `:1590`;
  `example/wrapper/xarm7/2001-move_joint.py:44-46`) and stops at the first non-zero code. Three Facts, five new or
  rewritten cases (22 pass), README row. Digest unchanged,
  `sha256:06a985ed0d5193814c80f0e4f9258a7d02f66a943d49d6e611b98259270e369d`.
- `labs/opntec__open-spectrometer-python` (R1): its `@reset` called `poweron()` (PV1 = 5), re-energising the CCD
  supply the e-stop turns off. The hook is removed; `poweron` (`TCD1304.py:50-52`) is the declared re-enable
  `x-cap.opntec.power_on.v1`. One Fact; `facts.md` also corrects the risk it stated (R1, not R0); four new cases
  (7 pass). Digest unchanged, `sha256:a452833ba7f7b8f38cfaca009f8149910377b0f26a2bdc0a9e0be92595e9dfe7`.
- `labs/dgretton__pyhamilton` (R2): its `@reset` called `HamiltonInterface.start()`, which relaunches the OEM
  process the e-stop terminated (`pyhamilton/interface.py:578-611`); the clone does not say whether that start moves
  the instrument, so under the reset policy it is not a reset step. The hook is removed; `start()` is the declared
  re-enable `x-cap.dgretton.start_interface.v1`. One Fact; four new cases (9 pass). Digest unchanged,
  `sha256:83f0ebd06b8c7adddc9f4f9881bcb52abae4b89a7839891bb099620ad14c5dd2`.

All six keep their source pins, authorship and `driver.lock.json` (`reviewed_by: null`); `RESULT.json` is `pass`
with a MODEL REVIEW paragraph (the new extensions are in `catalogue_requests`). A digest that did not move is
correct: the stable digest identifies the gate's findings (none before or after), not the package content. Franka
and Thorlabs cards still say `blocked`; the registry rebuild and `prepare.py --sync` at integration update them.
Against the unchanged SDK both fail (Franka: G3 `Action(reenable=...)` is unknown; Thorlabs: G8 TSAFE-001 and
SAFE-014 on the closed session).

Reset scan of every passing package (round 1: 17 `@reset` hooks and 3 family reset bindings in 20 packages, counted
after the `mcp_robot` correction; 14 hooks remain after the three corrections of round 2):
`labs/mabuchilab__instrumental` (reopens an R1 camera session), `labs/andmorifa__instrument-control-python` (a TCP
reconnect) and `labs/angli339__tecan-fluent-api` (re-attaches a client object) keep their resets: they re-establish
communication only, which the reset policy allows. `labs/eta-systems__labor-gpib` and
`labs/smithsonian__rxlab-instruments` send `*RST`, whose effect on the output state their clones do not state: they
stay listed for a human check of the instrument manuals. The remaining hooks are benign (state bookkeeping) or
belong to simulators.

## Decisions

- TSAFE-001 keeps its id and name (CON-013): on every manifest that suite 1.3.0 could test (a device that declares
  neither field) its assertions and detail text are unchanged; the added checks apply only to the new declarations,
  which no earlier suite could see.
- `SUITE_VERSION` 1.3.0 → 1.4.0. GOV-026 makes a suite that adds tests for new requirements a MINOR version, and the
  suite now checks CORE-086, CORE-087 and SAFE-048 (and TSAFE-001's permit handling changed, S7-07); CON-028 needs
  the version to name the suite that produced a report. The round-1 decision to keep 1.3.0 (no published verdict
  changed) is withdrawn. The five reference reports were regenerated as 1.4.0 runs with unchanged verdicts, levels
  and manifest digests (only run-specific ids and digests in PROTO-030, EVID-015 and EVID-016 differ), and each
  `verify` exits 0. The 1.3.0 runs were copied first to `DEV/archive/sdk-docs-reports/suite-1.3.0-final/` (outside
  the private project, because `_archive/` is private material that the open-source tree and its tests do not
  have). The actual tree keeps one folder per superseded suite version (`_archive/sdk-docs-reports/suite-1.1.0/`,
  `suite-1.3.0/`), names a published report `conformance-reports-<file>` and lists every file in
  `_archive/sdk-docs-reports/README.md` (file, was, why). Its `suite-1.3.0/` already holds earlier 1.3.0 runs under
  three of the same names, with other content, so at integration the five files belong in
  `_archive/sdk-docs-reports/suite-1.3.0-final/` with five README rows; they are byte-identical to the reports the
  actual tree publishes now. `test_published_reports` checks only the two moved duplicates at the top of that
  folder, so it still passes.
  `MHS/sdk/docs/e2e-transcript.txt` is a dated transcript of a suite 1.3.0 run and was not regenerated.
- The re-enable is an ordinary command that the session's grants decide, like any new start command; it is not
  made operator-only like the reset (CORE-083).
- A terminal e-stop is per endpoint and is not persisted; persistence of the latch itself is unchanged (CORE-171).
- Round 3: the wait applies to every command in flight on a device that declares a re-enable (its stop leaves it
  disabled), not only to the re-enable; a device without one keeps the single run of the stop path.
- The author kit (`MHS/handoff/PROMPT.md` step 3, `PLAYBOOK.md` section 8, `REVIEW.md` checklist item 5) now states
  the reset rule, the re-enable and the terminal declaration in one or two sentences each.
- No registry, recipe or family-page change: the generated ROS recipes do not yet mention the two declarations.

## Review s7 and how each finding was settled

- S7-01 (major): fixed. A decorated driver that declares a re-enable and an `@reset` hook is refused by the model,
  by the start-up check and by gate G3 (`G3.DEFINITION`, checked on a copy of the xArm package with its old hook);
  probe A of the review can no longer be built, so probe A2 (TSAFE-001 passing it) cannot happen.
- S7-02: fixed (late devices checked on first use; `_estop_reenable` reports only a usable declaration).
- S7-03: fixed (validation of the empty object, in the model and at start-up).
- S7-04: fixed for the declared re-enable in round 2, widened in round 3 to every command in flight on a device that
  declares a re-enable (`command_in_flight`).
- S7-05: text fixed in CORE-087 and SAFE-048; a test pins the behaviour.
- S7-06: wording fixed; the comparison stays exact and the rest is a review obligation.
- S7-07: fixed (permit decided before the e-stop; failure after it); suite version bumped.
- S7-08, S7-09: package texts fixed (Franka, Thorlabs).
- S7-10: the new tests were added for S7-01, S7-02 and S7-03.

## Found, not fixed

- Arming when the backend opens (review s7 re-check, N-04). The xArm driver's `setup()` runs the start sequence
  (`motion_enable(True)`, `set_mode(0)`, `set_state(0)`), pyhamilton's `setup()` starts the Hamilton interface, and
  the spectrometer's upstream constructor powers the CCD on (`TCD1304.py:45-48`). None of these is a reset, but each
  arms a newly opened device without a command, and after a restart with a restored latch the same call runs
  before any operator action. Recorded as found, not fixed, by the orchestrator's decision.
- A reset that re-establishes communication must change nothing on the device (CORE-087, SAFE-042); the SDK cannot
  test that, so it rests on review (review s7 re-check, N-03).
- A family reset binding that re-arms through another target is not detected (review obligation, CORE-086).
- `labs/eta-systems__labor-gpib` and `labs/smithsonian__rxlab-instruments`: `*RST` in the reset, output state
  unstated (human check of the manuals).
- The generated ROS and family recipes do not describe the declarations yet (the author kit does since round 3). The
  xArm exemplar is what `mhs.driver new --like` copies (`driver.py` and `fake.py`; not its README, facts or tests), so
  a new package copied from it now gets the re-enable shape.

## Result

Run on 2026-11-05 in the private project with the validated Python 3.14.7 environment and
`PYTHONDONTWRITEBYTECODE=1`, on a host shared with other agents.

Round 1 (kept for the record): the full SDK suite passed (3,244 tests, 6 skipped, after the applicability counts
were updated and with MCP stdio timeouts under load in two earlier runs); `collect.py --strict` over 683 packages
passed with no digest change; `validate.py --no-corpus --allow-stale-cards` passed with the expected stale-card
warnings; registry suite 309 of 310 (the same stale-card check).

Round 2:

- Test directories: safety 525 OK, endpoints 78 OK (4 skipped), conformance 198 OK. The recovery module: 47 OK,
  three runs.
- `spec_doctest.py`: ok, 698 requirement ids, 0 errors, 0 warnings. `build_applicability.py --check`: not stale
  (582 normative ids, 52 executable). `sync_data.py --check`: 22 files in sync.
- Full SDK suite, 3,259 tests (3,244 of round 1 plus the 15 new). Run 1: one failure,
  `tests.handoff.test_tools` `test_the_shipped_changelog_lists_every_fragment`: the changelog's generated block
  still had this record's old first paragraph; rebuilt with `tools/build_changelog.py`. Run 2: OK, 6 skipped
  (the sixth is `test_mcp_projection`, which skips without `work/openai4s-src`), 588 s.
- Gates: the six packages above pass G1-G9 with no finding and an unchanged digest; `collect.py --strict` over them:
  6 of 6, 0 warnings. `collect.py --strict` over every passing package (the 681 of round 1 and the two
  repaired ones, 683): 683 pass the gate; the only warning is the existing, unaccepted MCM3000 binary citation; no
  gate digest differs from its `RESULT.json`, and none of the 681 differs from the `validation-2` baseline.
- `validate.py --no-corpus --allow-stale-cards`: PASS, 0 errors, with the four expected stale card/record warnings
  of Franka and Thorlabs.
- `tools/build_changelog.py`: the generated block was rebuilt for this record's new first paragraph; `--check` OK.
  `MHS/sdk/INTERFACE.md`: regenerated output identical, unchanged.
- Conformance reports: five regenerated, verdicts unchanged, five `verify` runs exit 0.

Round 3:

- Test directories: safety 527 OK, endpoints 78 OK (4 skipped), conformance 198 OK, handoff 87 OK, spec 68 OK. The
  recovery module: 49 OK. Mutation check: 8 of 8 caught.
- `spec_doctest.py`: ok, 698 ids. `build_applicability.py --check`: not stale (582 normative ids, 52 executable).
  `sync_data.py --check`: 22 files in sync. `tools/build_changelog.py --check`: OK.
- Full SDK suite: 3,261 tests (3,259 plus the 2 new), OK, 6 skipped, 501 s.
- Gates: the six packages pass G1-G9 with no finding and an unchanged digest (Franka: 27 package cases; a first gate
  run failed G3 because a counterfactual case patched the SDK with `mock.patch`, which the gate's static scan
  forbids in package code; it now removes the declaration from the served manifest instead). `collect.py --strict`
  over the six: 6 of 6, 0 warnings. Over every passing package (683): 683 pass the gate; the only warning is the
  existing, unaccepted MCM3000 binary citation; no gate digest differs from its `RESULT.json`, and none of the 681
  differs from the `validation-2` baseline.
- `validate.py --no-corpus --allow-stale-cards`: PASS, 0 errors, the four expected stale card/record warnings.

Round 4 (review s7 re-check: accepted; N-01 to N-04):

- `MHS/sdk/docs/pylabrobot-helper.md` now names `command_in_flight` (N-03); CORE-077 and SAFE-040 are the only other
  places that list the reasons, and both already do.
- Test directories: safety 529 OK, endpoints 78 OK (4 skipped), conformance 198 OK; the recovery module 51 OK,
  three runs. `spec_doctest.py` ok (698 ids); `build_applicability.py --check` not stale; `sync_data.py --check`
  in sync; `tools/build_changelog.py --check` OK.
- Gates: the six packages pass G1-G9 with no finding and an unchanged digest; `collect.py --strict` over them: 6 of
  6, 0 warnings.

Not run: `build_registry.py` (rebuild and `--check`), `prepare.py --sync`, `dispatch.py --check-pilot`, the
OpenAI4S integration suite, `tools/oss_export_check.py`, and a second-model review of rounds 2 and 3.
