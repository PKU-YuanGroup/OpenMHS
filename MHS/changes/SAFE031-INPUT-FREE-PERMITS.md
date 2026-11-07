OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# SAFE-031 for permit-gated capabilities without inputs (suite 1.4.1)

Conformance test SAFE-031 no longer skips a permit-gated binding whose input schema admits only the empty object. Suite 1.4.0 needed a second valid input to present the permit with, so a permit-gated action without inputs, such as a declared re-enable (CORE-086), capped its endpoint at CL2 and gate G8 failed. Such a binding has no second valid input: the test now records the distinct-input presentation as not applicable and tests what still applies. Every other binding is tested as before. The fix unblocks gh.ad-sdl/ur_module, whose permit-gated brake-release re-enable now passes the gate unchanged.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 in a private project copy
(`work/handoff-runs/claude-20261104/development/p3-safe031/project`, a byte copy of `snapshot-3`), as phase-3
item p3-safe031. Not integrated. No hardware, network, upstream code or human review is involved; every result
below is `contract_checked` on a fake.

## Why

The helper-wave-2 review blocked `MHS/drivers/labs/ad-sdl__ur_module` as `SDK_BUG`
(`review/decisions-helper-wave-2/ad-sdl__ur_module.json` in the batch directory). Its re-enable
`x-cap.ad-sdl.power_on.v1` (a dashboard brake release from POWER_OFF, BOOTING, POWER_ON or IDLE, only with
safety status NORMAL, confirmed RUNNING) is rightly permit-gated, and gate G8 failed on SAFE-031 alone:
`SAFE-031 skip: no distinct valid second input for x-cap.ad-sdl.power_on.v1 to test permit binding`.

In suite 1.4.0 (`snapshot-3`, `MHS/sdk/src/mhs/conformance/tests_core.py`), SAFE-031 is `safe_004`
(`:2647`). It tests the first gated write/invoke binding (`gated_binding`, `:587-593`), takes a valid input,
asks `alternate_input` for a second one and skips when there is none (`:2663-2665`), before sending anything.
The test is required at CL3 whenever a gated binding exists (`:3344-3351`), and a required skip caps the level
(CON-018). CORE-086 (`MHS/spec/core.md:202`) makes a declared re-enable accept the empty input, and the
decorated SDK publishes an action without inputs with the schema
`{"type": "object", "properties": {}, "additionalProperties": false}`; for such a binding `alternate_input`
can never find a second valid input. With `requires_permit` removed the package passed G8 (review decision),
so the skip was the only obstacle.

Reproduced first in the private copy with the unchanged `snapshot-3` SDK: the gate fails G8 with that skip and
the stable digest `sha256:657ce2bce321e6694e3c4ebb6bf8fb5969c1649f8fb6250c028a10b28041c841`, the digest the
actual tree records (`logs/baseline-ur-gate.txt` in the DEV directory).

## What SAFE-031 requires of a capability without inputs

The normative text (`MHS/spec/04-safety.md:426-433`): a permit MUST be bound to the exact `input_digest`;
presenting it with a different input MUST be rejected with `MHS.SAFETY.PERMIT_INVALID`; reusing a consumed
permit MUST be rejected the same way; the unused-check, the scope checks and the consumption are one atomic
transition; a pre-effect refusal (schema, limit, interlock, revision conflict) MUST NOT consume the permit.
The `input_digest` is `sha256(JCS({capability_id, resource, input}))` (PROTO-036,
`MHS/spec/02-wire-protocol.md:659-662`), and the core checks the structure of the input (CORE-060 step 7)
before the permit (step 10), refusing at the first failure, and "a refused command never consumes a permit"
(`MHS/spec/core.md:132-147`).

Decision, for a binding whose input schema admits only the empty object:

- The binding of the permit to the exact digest still holds and still matters, but no input other than `{}`
  reaches the permit check: the structure check refuses it first, with `MHS.CAPABILITY.INPUT_INVALID`. The
  clause "presenting a permit with a different input MUST be rejected with PERMIT_INVALID" therefore has no
  instance among the inputs the endpoint can accept. It is recorded as not applicable, with that reason, in the
  report entry (`evidence.note` and the detail), instead of a skip.
- What applies is tested: the refusal without a permit (SAFE-030, as for every gated binding); the presentation
  with another input, which must be refused before any effect and must not consume the permit (the last
  sentence of SAFE-031, CORE-060); the digest's other members, capability and resource, where the device has
  another gated binding that also takes only `{}`; acceptance for the bound input; single use.
- Not tested, as before for every binding: the atomicity of concurrent presentations and the logging of a
  mismatch.
- Not part of SAFE-031: expiry, session, device and resource scope (SAFE-033, `04-safety.md:451-458`) and
  revocation (SAFE-036, `:469-471`) apply to every permit whatever its input schema. The suite has no executable
  check for them for any binding (`applicability.json`: `not_verified`). Putting them under the SAFE-031 id would
  make the canonical SAFE-031 test check other requirements (CON-014, `01-conformance.md:190-195`), and a
  revocation by e-stop would turn SAFE-031 into an e-stopping test, which changes the runner's order and endpoint
  retirement for every endpoint with a terminal e-stop (CON-022, `TestCase.estops`). They are left as found, not
  fixed (below).

No normative text changes: SAFE-031, its hooks row (`04-safety.md:719`) and the mandatory negative row
(`01-conformance.md:244`, "permit replay") already describe what the corrected test checks.

## SDK change

`MHS/sdk/src/mhs/conformance/synth.py`:

- `UNDECLARED_FIELD = "__mhs_invalid_field__"` (`:1028`), the name PROTO-027 already sends as its undeclared
  field (`tests_core.py` `cap_005`, unchanged).
- `only_empty_input(binding)` (`:1031`) returns the reason when the binding provably admits only `{}`, else None.
  Every schema applied to the input is checked: the one the suite synthesizes from (`Binding.schema`), the
  binding's declared `input_schema` and, for a catalogued class, the class input schema (the endpoint serves
  binding ∩ class, CORE-060 step 7), each when it differs. Each must be a mapping with `type: object` (exactly;
  added by the integrator, see below) and without a top-level `$ref`, declare no `properties` and no
  `patternProperties`, and close the object with `additionalProperties: false` or an integer `maxProperties: 0`;
  the SDK's validator (`mhs.schema.validate`, the one that checks command inputs) must accept `{}` and refuse
  `{UNDECLARED_FIELD: ...}` and a value of every other JSON type, so a keyword the validator ignores never counts.
  A schema the validator cannot evaluate, an open object, a declared property or a `propertyNames` rule that
  only happens to refuse the probe name shows nothing. The `$ref` exclusion is conservative: the SDK validator
  applies `$ref` siblings, but a draft-07 reading would not.

`MHS/sdk/src/mhs/conformance/tests_core.py`:

- `safe_004` (SAFE-031, `:2647`): when `alternate_input` finds no second input, the valid input is `{}` and
  `only_empty_input` shows the schema admits nothing else, the test runs `_safe_031_input_free` (`:2671-2675`);
  in every other case it skips with the 1.4.0 text. The path with a second input is unchanged, line for line.
- `_safe_031_input_free` (`:2767`), in order: (1) the command without a permit must be refused with
  `PERMIT_REQUIRED`, `APPROVAL_REQUIRED` or `PERMIT_INVALID` (the 1.4.0 check and message); the permit is issued
  for `{}`; (2) the permit presented with `{UNDECLARED_FIELD: {"not": "allowed"}}` must be `rejected` (never a
  dispatched receipt, `failed` included) with a structure or permit refusal code, and must not reach the bridge
  as a call of the capability (in-process) (`:2810-2828`); (3) for each other gated input-free binding of the
  device (`_input_free_siblings`, `:2733`: at most the same capability on another
  resource and one other capability; never an ungated binding, a stop class, a `safe_state.achieved_by` action,
  which is exempt from permits (SAFE-029), a test hook or a replay device), the permit presented with `{}` must
  not be dispatched; a `PERMIT_INVALID`/`PERMIT_EXPIRED` refusal counts, a refusal before the permit check for
  another reason is reported and not counted (`:2830-2849`); (4) the permit must be accepted for `{}`, which shows
  that none of the refusals consumed it (`:2851-2858`); (5) presented again with `{}` it must be `rejected` with
  `PERMIT_INVALID` or `PERMIT_EXPIRED` (`:2860-2866`). The pass detail names each step and ends with the
  not-applicable reason, which is also the entry's `evidence.note`.
- `_calls_of` (`:2714`) counts only bridge `call` records of the presented capability, so a stop path that the
  endpoint retries in the background is never mistaken for the presented command; the receipt status is the
  dispatch check on every transport.

`MHS/sdk/src/mhs/conformance/report.py`: `SUITE_VERSION` 1.4.0 → 1.4.1 (`:46-52`).

Example, the SAFE-031 entry of gh.ad-sdl/ur_module after the change (`DEV/logs/ur-safe031-entry-final.txt`):
required, `pass`, `spec_ref` `SAFE-030, SAFE-031`, detail "permit
required, accepted for the bound input, rejected on reuse (MHS.SAFETY.PERMIT_INVALID); presented first with an
undeclared field, it was refused before any effect (MHS.CAPABILITY.INPUT_INVALID) and not consumed; the device
has no other gated binding that takes only the empty object; distinct-input check not applicable:
x-cap.ad-sdl.power_on.v1 on main: its input schema admits only the empty object (no declared property,
additionalProperties: false): ...".

## Suite version and inventory (CON-013, GOV-026)

- `SAFE-031` keeps its id, name, level, `required` rule, group and `spec_ref` (`SAFE-030, SAFE-031`);
  `traceability.json` is unchanged (no test added, retired or re-scoped). On every manifest on which suite 1.4.0
  ran SAFE-031, its assertions and detail are byte-identical (the heater case of the new tests; the conveyor
  reference report). The only verdict that changes is the 1.4.0 skip on a binding whose schema provably admits
  only `{}`: that skip asked for an input that cannot exist and capped a conformant endpoint, a test bug, not an
  untestable check (CON-013: the same check; no assertion of the general case changed).
- GOV-026 (`MHS/spec/10-governance.md:167-169`): "A suite PATCH version fixes test bugs", so 1.4.0 → 1.4.1.
  CON-028 needs a new version because a report of such an endpoint differs between the two.
- `MHS/sdk/src/mhs/conformance/applicability.json` regenerated with `MHS/sdk/tools/build_applicability.py`: only
  the 268 `basis` strings that name the suite version changed (1.4.0 → 1.4.1); the counts are unchanged (582
  normative ids, 52 executable, 268 not_verified, 153 out_of_profile, 64 editorial, 41 report_process, 4
  level_not_claimed); `--check` passes.
- The five reference reports were regenerated as 1.4.1 runs with the commands of `MHS/conformance/README.md`
  and `MHS/sdk/docs/reports/README.md`: levels, test sets and order, statuses, `required` flags, `spec_ref`s,
  `mhs_code`s and manifest digests are unchanged; only run-specific ids, digests and evidence differ (PROTO-030,
  EVID-015, EVID-016 details; PROTO-013, OP-001 and EVID-015 evidence, which also differ between two runs of the
  same suite). Each `verify` exits 0. The 1.4.0 runs were copied first to
  `DEV/archive/sdk-docs-reports/suite-1.4.0/` (outside the project, because `_archive/` is private material);
  at integration they belong in `_archive/sdk-docs-reports/suite-1.4.0/` with five README rows
  (`DEV/archive/sdk-docs-reports/ARCHIVE-ROWS.json`).
- Docs: `MHS/sdk/docs/conformance.md` (the inputs paragraph, notes on suite 1.4.1, the report and reference
  sections), `MHS/conformance/README.md`, `MHS/sdk/docs/reports/README.md`. `MHS/sdk/INTERFACE.md` is unchanged
  (`--print-interface` gives the same file).

## Tests

`MHS/sdk/tests/conformance/test_safe031_input_free.py`, 26 tests (21 of this item, 5 of the integrator):

- what counts (8): closed empty schemas are shown (three shapes); twelve other schemas show nothing (open object,
  empty schema, declared property, pattern property, top-level `$ref`, a required field, `minProperties`, a
  boolean and a non-zero `maxProperties`, an array type, an `additionalProperties` schema, `propertyNames` only);
  every applied schema must be closed (an open declared schema, a class schema with a property); a validator
  that ignores the keyword, and one that cannot evaluate the schema, show nothing; a schema without
  `type: object` (no type, or a list of types, as the binding, declared or class schema) shows nothing, with the
  real validator and with one that refuses every non-object; a validator that admits a non-object shows nothing.
- the suite (10): an input-free gated action passes SAFE-031 with the note and the endpoint reaches CL3; the
  ur_module shape (a permit-gated declared re-enable) passes SAFE-031 and TSAFE-001 and reaches CL3; the
  counterfactual with the new rule switched off gives exactly the 1.4.0 skip and CL2; another gated capability
  and another resource of the same capability refuse the permit (`PERMIT_INVALID`) and the bridge sees only the
  accepted call; a permit-gated `safe_state.achieved_by` action is never presented the permit; a refusal before
  the permit check is reported and not counted; a fixture with a non-empty `valid` input keeps the 1.4.0 skip; an
  input-carrying gated binding gets the 1.4.0 detail byte for byte and no note; the suite version.
- broken endpoints (8), each failing SAFE-031 with the step it breaks: a reusable permit; a refusal that spends
  the permit; an endpoint that drops the undeclared field, so the permit of `{}` is honoured for another input; a
  dispatched `failed` receipt naming `INPUT_INVALID`; a permit honoured for another capability; a permit
  honoured for another resource; a `rejected` receipt for the undeclared field after the capability reached the
  bridge; a permit presented for another gated binding answered `completed` without a bridge call.

Mutation check (`DEV/scripts/mutants.py`; fresh copies of the SDK source with one rule removed each, the new
module run against each; summary in `DEV/scratch/mut-4/summary.json`, the run on the final bytes): 14 of 14
mutants caught: open objects counted, no validator probe, top-level `$ref` allowed, the declared and class
schemas ignored, no `{}` payload guard, no undeclared-field step, a dispatched refusal accepted, no sibling
step, any refusal counted as the permit check's, ungated siblings, `achieved_by` siblings, no acceptance step,
no reuse step, the input-free path switched off.

Integrator edits (integrator-v3, claude-opus-5-5, 2026-11-05, at the orchestrator's request after the Claude
Sonnet review of this item): `only_empty_input` also requires `type: object` (review F4: a closed schema without
a type admits a string, null or a list, each a second valid input) and probes the validator with a value of
every other JSON type; and two tests kill the two mutants of the review's safety lens that survived this module
(F1: step 2 without its bridge-call check, step 3 without its receipt-status check). The integrator's mutation
run (`development/integrator-v3/scripts/safe031_mutants.py`: the review's ten mutants and three of the new rule)
kills 13 of 13. No reason text changed, so the reports and the ur_module digest below are unchanged.

## Package: gh.ad-sdl/ur_module

- Copied from the actual tree at 2026-11-05T20:18:15Z, after the helper-wave-2 review (Claude Opus repair
  paragraph and Claude Sonnet verification paragraph in its notes); the file hashes are in
  `DEV/originals/actual-tree/ad-sdl__ur_module.sha256`, the files in `DEV/originals/actual-tree/`.
  `check-report.json` was not copied (generated). `task.json` was refreshed from the `snapshot-3` card with
  `prepare.py --sync`; the actual tree's card differs only in `package_status`, `blocked_on`, `wave`, `rank`
  and `publish_review` (the helper-wave-2 override sets `publish_review: required`), none of which a gate reads.
- No package code changed: `driver.py`, `fake.py`, `native.py`, `test_driver.py`, `facts.md`, `reference.json`,
  `REFERENCE.md`, `driver.lock.json` (`reviewed_by` null) and `site-limits.example.json` are byte-identical to
  the reviewed package, so `x-cap.ad-sdl.power_on.v1` stays permit-gated.
- Gate on the fake with the fixed SDK: G1-G9 pass; G6 keeps its `G6.NOT_EXERCISED` warning (the permit-gated
  re-enable's in-range call is left to G8); G8: SAFE-031 passes as above and TSAFE-001 passes ("the declared
  re-enable x-cap.ad-sdl.power_on.v1 was refused while latched and accepted after the reset, a new command
  recovered", with a permit taken after the reset). Stable digest
  `sha256:8d5db7c99dc6ddbe40cbc5ef479af11fbfb4f83b6c62381d8b7df130c369c61e`. The 13 cases of `test_driver.py`
  pass. `collect.py --strict` passes it (the G6 warning is a note).
- `RESULT.json`: status `pass`, `blocked_on` `[]`, the gate digest above; `catalogue_requests` gain
  `x-cap.ad-sdl.power_off.v1` (the safe-state action) and now describe `power_on` (the permit-gated brake
  release) and `stop_program` (an ordinary latched command), as the review asked; a MODEL REVIEW paragraph
  (claude-opus-5-5) records the unblocking. The notes stay at 7,990 characters: as `apply_review.py` does, only
  the author's text before the first MODEL REVIEW paragraph was shortened (by 881 characters, marked `[...]`);
  both review paragraphs are kept whole, and the full original is in `DEV/originals/actual-tree/`. The new
  paragraph (871 characters) points at the publication condition that both earlier paragraphs state instead of
  repeating it, to leave room in the 8,000-character notes for the review of this change.
- Integration: the actual tree's card for this package says `blocked` (`SDK_BUG`); after the package files are
  applied, the registry rebuild and `prepare.py --sync` update it. `publish_review: required` stays: the package
  is not published or merged into a published tree before the owner decides.

## Found, not fixed

- SAFE-033 (expiry, session, device and resource scope) and SAFE-036 (revocation by e-stop, session close and
  expiry) have no executable check for any permit (`applicability.json` `not_verified`). A grouped test (a new
  `T`-id with its `traceability.json` entry, a MINOR suite version) is the route; it was not added here, so that
  no other verdict moves.
- SAFE-031 tests one gated binding, the first by device and capability id (`gated_binding`), as before; it does
  not leave out a permit-gated `safe_state.achieved_by` action, which the endpoint exempts from permits
  (SAFE-029), so such a declaration fails SAFE-031 as well as the static SAFE-029 test. Unchanged.
- PROTO-027 (`cap_005`) still spells the undeclared field as a literal; it equals `synth.UNDECLARED_FIELD`.

## Result

Run on 2026-11-05 in the private project with the validated Python 3.14.7 environment and
`PYTHONDONTWRITEBYTECODE=1`, on a host shared with other agents.

- Full SDK suite on the final code (`python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk`, 10 min 43 s):
  3,447 tests (the phase-2 final checks of the actual tree ran 3,426; the difference is the 21 new ones), 5
  skipped, 1 failure:
  `tests.bridges.test_ros_actions.RosActionTests.test_stock_estop_latches_while_action_is_running`
  (`ros2-native`), whose `wait_for` gives a cancelled operation 1 s (`test_ros_actions.py:106-112`) on a host
  shared with other agents. Re-run on its own it passes, and so does its module (26 tests); it does not touch the
  conformance package. An earlier full run, started before the step-2 revision comparison was removed from
  `_safe_031_input_free`, was stopped partway and is not used.
- On the final bytes (one docstring edited during that run, an unused import removed after it):
  `tests/conformance` (219 tests) and the conformance-suite, re-enable and driver CLI modules (69,
  `INTERFACE.md` included) pass.
- The generator checks of CI pass: `sync_data.py --check`, `gen_errors.py --check`, `gen_appendices.py --check`,
  `build_applicability.py --check`, `--print-interface` against `INTERFACE.md`, `spec_doctest.py MHS/spec`,
  `tools/build_changelog.py --check`. The five published reports verify (`python3 -m mhs.conformance verify`,
  exit 0 each) and `test_published_reports` passes.
- Registry: `validate.py --no-corpus --allow-stale-cards` (CI's form) passes with one warning, the new package's
  card and record not rebuilt yet; `build_index.py --check` finds no stale aggregate. The registry suite runs 329
  tests with 1 failure, `test_validator_passes_without_the_corpus`, which runs `validate.py` without
  `--allow-stale-cards` and reports exactly those two entries (card `package_status` `none` against `pass`,
  record evidence `static_scan` against `contract_checked`). `build_registry.py --check` reports five generated
  files, all from the new pass: `repos/labs/ad-sdl__ur_module.json`, `tasks/labs/ad-sdl__ur_module.json`,
  `families/python-object.md`, `README.md` and `coverage.md`. The registry rebuild and `prepare.py --sync` at
  integration update them, as for the Franka and Thorlabs packages of phase 2.
- `collect.py --strict` over every package whose `RESULT.json` says `pass` (`DEV/scripts/collect_all.py`, 8
  chunks): 689 of 689 pass the gate; the only strict warning is the known `UNVERIFIABLE_CITATION` of
  gh.amsikking/thorlabs_mcm3000 (its chunk exits 1, as in phases 1 and 2). The 688 packages that passed in
  `snapshot-3` give and record the digest `snapshot-3` records (rule 14: no digest moved); the one new pass is
  gh.ad-sdl/ur_module with `sha256:8d5db7c99dc6ddbe40cbc5ef479af11fbfb4f83b6c62381d8b7df130c369c61e`, which its
  `RESULT.json` records.
- OpenAI4S integration tests (`integration/openai4s`): 129 OK.
