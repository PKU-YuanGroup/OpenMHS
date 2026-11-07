# Executable conformance suite (`mhs/conformance/`)

The suite tests a **driver behind an endpoint**, not the SDK runtime: it reads
the device manifests, resolves every binding against the capability catalogue
(verb, risk floor, effective limits, exactly as the runtime does) and probes the
driver through them. It emits a `conformance-report.json` whose
`report_digest` *and* `level_achieved` can be recomputed offline (MHS-001).

MHS conformance is a behavioural test result, not a safety certification;
every report says so (`disclaimers`).

```python
# In-process, against fresh endpoints (the way to gate a driver)
from mhs.conformance.inprocess import run_suite_inprocess

report = run_suite_inprocess(build_my_server, profile="MHS-Sim", level="CL3")

# Against a running endpoint
from mhs import connect
from mhs.conformance import run_suite, save_report

report = run_suite(connect("http://127.0.0.1:7400"), profile="MHS-Sim", level="CL4")
save_report(report, "conformance-report.json")
```

```bash
python3 -m mhs.conformance --factory my_pkg.driver:build_server --level CL3          # in-process
python3 -m mhs.conformance --reference conveyor --test-profile --level CL4          # reference fixture
python3 -m mhs.conformance --reference arm --noise --level CL4                      # seeded-noise arm
python3 -m mhs.conformance --reference replay --bundle reports/replay-bundle-conveyor.json --level CL4
python3 -m mhs.conformance --endpoint http://127.0.0.1:7400 --level CL4 --out r.json
python3 -m mhs.conformance --command "python3 -m mhs.reference arm --stdio" --level CL4
python3 -m mhs.conformance verify r.json --endpoint http://127.0.0.1:7400            # re-run and compare
```

Options: `--profile MHS-Sim|MHS-Device|MHS-Bridge`, `--level CL0..CL4`,
`--require-level` (default: the claimed level), `--allow-actuation`,
`--read-only`, `--fixtures FILE`, `--approvals FILE`, `--source-commit SHA`,
`--json`, `--out`; with `--reference`: `--test-profile` (conveyor),
`--noise`/`--seed N` (arm; `--seed` needs `--noise`), `--bundle FILE`
(replay, required).

Exit codes: `0` report produced and the required level achieved (or, for
`verify`, the report verifies), `1` no report could be produced or the report
does not verify, `2` usage error (including an unknown profile or level),
`3` transport error, `5` achieved level below the required level — including a
`CL0` requirement whose required CL0 tests failed (`achieved=none`). The
summary lists every failing test and the required tests that cap the level.

## In-process runs, fault injection

`run_suite_inprocess(factory, ...)` calls `factory()` once for the read-only
checks and once for each mutating group (`OP`, `SAFE`, `FID`), so no group sees
another group's state and repeated runs give identical verdicts. A device that
declares a terminal e-stop (`safety.estop.terminal`, CORE-087) cannot be reset
on the endpoint that stopped it, so the test after such an e-stop gets one more
`factory()` call (CON-022); a run against one shared endpoint instead runs the
tests that e-stop (`TSAFE-001`, `SAFE-028`, `SAFE-041`) after every other test
that sends a command. `TSAFE-001` also checks a declared re-enable
(`safety.estop.reenable`, CORE-086): refused while latched, accepted after the
reset and before the recovery command.
`mhs.conformance.inprocess` also exports the `Loopback` transport and the
`Harness`, which instruments every device bridge (by shadowing its
`call`/`write`/`read`/`estop`/`reset`/`interlocks`/... methods on the instance)
to record calls and inject faults at the bridge boundary:

| fault | used by |
|---|---|
| interlock forced `open` / `unknown` | `SAFE-011`, `SAFE-012`, `SAFE-041` |
| call delayed (cooperatively cancellable) | `PROTO-011`, `OP-011` |
| response dropped after the effect | `OP-013` |
| call raises | available to driver tests |

Over a plain client these tests fall back to the reference conveyor's
`x-cap.mhs-test.*` hooks when present (never on a hardware or hybrid device
without `--allow-actuation`: a hook actuates the device), otherwise they are
skipped (and, when required, cap the level): CL3 for an endpoint with
interlocks needs an in-process run or an equivalent hook. In-process,
`OP-011` cancels the harness delay that stands in for the native call, so it
checks the endpoint's cancellation plumbing, not the driver's own
cancellation; its detail says so.

The `Harness` is also the actuation gate of an in-process run (CON-031).
Without `allow_actuation`, every `call`/`write`/`restore`/`safe_state` that
reaches the bridge of a hardware or hybrid device is refused *before the driver* with
`MHS.AUTH.HARDWARE_DISABLED` and recorded with `faulted="blocked"` and the id
of the test that sent it; catalogued read classes pass through (an extension's
declared `read` verb is not trusted there).
`Harness(server, allow_actuation=False)` is fail-closed by default, and the
suite sets the run's policy through `Harness.gate(...)`.

One bridge object may serve several devices. The harness wraps it once and
tracks every device that shares it: a call is recorded under the device its
`ctx.device_id` names (a shared bridge without that records its first
hardware device), and without `allow_actuation` every `call`/`write`/`restore`/`safe_state`
on a bridge shared with a hardware or hybrid device is refused, whichever
device the call names, because the same object drives the hardware.

The recorder's evidence fails closed: a bridge method the harness cannot
shadow (a read-only attribute, a property, a `__setattr__` guard that raises
or silently drops the write) is listed in `Harness.uninstrumented`. A wrapper
counts as installed only when the bridge then resolves the method name to it.
For such a bridge `CON-031` is inconclusive (`skip`) for a hardware device and
the "no bridge call" checks of `SAFE-011`, `SAFE-012` and `SAFE-014` fail
instead of passing vacuously. Such a bridge cannot be gated, so on hardware
without `--allow-actuation` the negative tests are not sent to it at all.

An endpoint whose devices have different modes gets one suite session per
mode (an MHS session has a single mode), and every command, read, e-stop,
reset, permit and operation query goes through the session of its target
device's mode.

## How the suite chooses what to test

* **Probe.** The command tests use one *probe* binding chosen by catalogue verb,
  never by declaration order: a `write` or `invoke` binding with at least one
  input, no permit, not a safe-state (`achieved_by`) action, not a stop class,
  not a deprecated class and not a test hook. Ties are broken by a fixed ranking
  (`world.step`, `motion.joint_position`, `fluid.transfer` first), then required
  inputs, catalogue before extension, and capability id. A fixture file may name
  the probe. A device without a probe (read-only) skips the command tests as not
  applicable, except `OP-001`, which then sends its read commands and checks
  that they keep the revision (plan 3.7).
* **Limits.** The effective limits of every binding are the runtime's own
  (`mhs._server.limits_plan`) intersected with what the endpoint publishes in
  `devices.get` (`x-mhs-effective-limits`, including the operator overlay), so
  synthesized inputs stay inside an overlay the manifest does not show and
  `SAFE-014` probes it.
* **Inputs.** Fixture file, then the class `examples` (projected onto the fields
  the binding declares), then synthesis from the input schema that honours the
  effective limits element by element. Strings constrained by `pattern` or
  `format` are never invented: without a fixture the test is skipped with that
  reason (for `SAFE-014`, every limited path of such a binding stays unprobed,
  so the test skips and caps the level; supply `valid` or `out_of_envelope`
  inputs). When no distinct valid second input exists, tests that need one skip
  (`TCAP-003` for a write probe, `SAFE-031`); an invoke probe's `TCAP-003` then
  relies on a non-empty output; `OP-004` uses a schema-different input because
  the `command_id` lookup precedes validation (plan 3.6). The exception is a
  gated binding whose input schema admits only the empty object (suite 1.4.1,
  below): no second valid input exists there, so `SAFE-031` records the
  distinct-input presentation as not applicable and tests the rest.
* **Hardware.** The gate fails closed (CON-031). Without the operator's
  `--allow-actuation`, hardware and hybrid subjects get:
  * no *actuating* test (`OP-001`, `TCAP-*`, `OP-003/004`, e-stop, permit,
    replay, ...), so the level is capped at CL1 whenever such a device binds a
    write/invoke capability, including when every one of them is permit-gated
    (`OP-001` is then required and skipped); a hardware device that binds only
    read capabilities is not capped;
  * *negative* tests (`OP-005`, `PROTO-027`, `SAFE-011`, `SAFE-012`,
    `SAFE-014`) only in-process, where the harness blocks every write/invoke
    at the hardware bridge. They send valid-looking commands that the device
    would execute if the endpoint failed to refuse them (a stale revision, a
    wrongly typed field, an injected open interlock, an out-of-envelope value),
    so over a plain client, or with a bridge the harness cannot instrument,
    they are skipped with a CON-031 reason. An unarmed endpoint (a strict
    endpoint arms no hardware by default) refuses them with
    `MHS.AUTH.HARDWARE_DISABLED` at plan 3.6 step 6, before the check they
    target; such a `rejected` receipt makes the test `skip` ("check not
    reached"), which still caps the level, instead of failing it;
  * *inert* tests (`PROTO-014` unknown capability, the `TPROTO-902/903`
    presence probes with unknown capability and operation ids, `MODE-005` on
    replay devices), which no device can execute;
  * a send guard: the suite never sends a bound write/invoke capability, an
    e-stop, a reset or a restore to such a device unless the harness blocks it
    at the bridge, and records anything it withheld in `CON-031`'s detail.

  Test hooks are not invoked on them either. When the endpoint dispatches a
  negative test's command to hardware instead of refusing it, nothing reaches
  the device (the harness blocks it), the test fails and `CON-031` fails,
  naming the test and the capability; over any transport a receipt other than
  `rejected` for such a command fails `CON-031` too.
  `mhs.safety.estop` is sent only to `software`/`both` e-stops (CON-032).
  Permits are never self-issued on hardware; pass operator approvals with
  `--approvals`. Replay (`FID-016`, `FID-025`) is not tested on hardware and
  does not cap its level (CON-017; `MODE_EXEMPTIONS`).
* **Resources.** Every command aimed at a binding names the binding's
  `resource` (plan 3.6 step 3: bindings are keyed by `(capability_id,
  resource)`).
* **Read-only.** `--read-only` sends no command at all (CON-022): only
  `none` tests run, so no `mhs.command`, `mhs.operations.cancel`, e-stop,
  reset, permit or restore is sent (the `TPROTO-902/903` presence probes are
  skipped too) and no CL2+ level is awarded.

Fixture file:

```json
{
  "probe": "cap.thermal.setpoint.v1",
  "capabilities": {
    "cap.thermal.setpoint.v1": {
      "valid": {"target_temperature": 37},
      "alternate": {"target_temperature": 38},
      "out_of_envelope": [{"target_temperature": 81}]
    }
  }
}
```

## Levels and profiles

Only endpoint profiles are accepted (`MHS-Sim`, `MHS-Device`, `MHS-Bridge`;
CON-004) and levels `CL0`..`CL4` (CON-006); anything else is a usage error.
`TCON-001` fails when the profile does not match the device modes
(`MHS-Device` needs hardware or hybrid devices — a fake backend gives
`contract_checked` evidence only) or the manifests' `conformance.profile`.
`CL0` runs the static checks only.

A level is **achieved** only when every *required* test at or below it
**passes**; a required `fail`, `warn` or `skip` stops the ladder (CON-018,
CON-027). Optional tests (`required: false`) run for coverage and never demote
the level.

When a required **CL0** test fails, no level is achieved at all. The report
schema has no "none" value, so such a report still carries `level_achieved:
CL0` as its floor, but its first `limitations` entry starts with `NO LEVEL
ACHIEVED:` and names the failing tests, `mhs.conformance.report.level_awarded()`
returns `None`, the summary prints `achieved=none` and the CLI exits `5`. A
report of this suite version that hides the failure (the line removed) does
not validate.

## Test IDs (stable)

Canonical test ids are requirement ids; grouped tests use `T<AREA>-NNN` and are
listed with the requirements they check in
[`src/mhs/conformance/traceability.json`](../src/mhs/conformance/traceability.json).
`TCAP-001` (output) and `TCAP-002` (resource kind) check no numbered
requirement; they cite the spec section instead (`sections`) and are not
counted as requirement checks in the inventory. Every report entry carries
`required` and `spec_ref`.

| level | tests |
|---|---|
| CL0 (static) | `ADPT-005` manifests validate, `TCON-001` profile vs subject/modes, `CAP-035` catalogue or extension classes, `CAP-017` risk floors, `CAP-016` drift *(advisory)*, `TCAP-002` resource kinds *(advisory)*, `CON-031`/`CON-032` suite self-checks |
| CL1 | `TPROTO-901`, `PROTO-013`, `PROTO-021`, `PROTO-023`, `PROTO-024`, `SESS-001`, `MODE-002`, `MODE-005` (replay) |
| CL2 | `TPROTO-902`, `OP-001`, `TCAP-001` output vs `output_schema`, `TCAP-003` observable effect, `OP-003`, `OP-004`, `OP-005`, `PROTO-027`, `PROTO-014`, `PROTO-030`/`PROTO-011`/`OP-013` *(optional)* |
| CL3 | `TPROTO-903`, `SAFE-001`, `SAFE-045`, `SAFE-029`, `TSAFE-001` → `[SAFE-040, SAFE-042, SAFE-048]`, `SAFE-028` e-stop reaches the device, `SAFE-011`, `SAFE-012`, `SAFE-041` *(advisory)*, `SAFE-031`, `SAFE-014`, `SAFE-050`, `OP-011`, `SESS-005` *(optional)* |
| CL4 | `EVID-015`, `EVID-016`, `EVID-010`, `FID-005`, `FID-016`, `FID-025` |

Notes on suite 1.4.1 (`MHS/changes/SAFE031-INPUT-FREE-PERMITS.md`; a PATCH version under GOV-026: it fixes
a test bug, adds no test and checks no new requirement):

* `SAFE-031` keeps its id, name, level, `required` rule and `spec_ref` (`SAFE-030, SAFE-031`; CON-013). Suite
  1.4.0 skipped it whenever it could build no second valid input for the gated binding, so a permit-gated action
  without inputs (a declared re-enable, CORE-086, or any other input-free action) capped the endpoint at CL2.
  When the binding's input schema provably admits only the empty object (every schema applied to it is an object
  schema, `type: object`, without a top-level `$ref`, declares no property or pattern property and sets
  `additionalProperties: false` or `maxProperties: 0`, and the SDK's validator accepts `{}` and refuses an
  undeclared field and a value of every other JSON type), no second valid input exists: another input is refused
  by the structure check (CORE-060 step 7) before the permit check (step 10). The distinct-input presentation is
  then recorded as not applicable
  (`evidence.note` and the detail), and the test checks what applies, in this order: refused without a permit
  (SAFE-030); the permit presented with an undeclared field is refused before any effect (`rejected` or a
  JSON-RPC error, and no bridge call of the capability in-process) and is not consumed; where the device has another
  gated binding that also takes only `{}` (the same capability on another resource, or another capability), the
  permit presented for it is refused by the permit check (the digest of `{capability_id, resource, input}`
  differs), and a refusal there for another reason is reported and not counted; the permit is accepted for its
  bound input; the consumed permit is refused on reuse (single use).
* Every other gated binding is tested as in 1.4.0, byte for byte (the detail of the conveyor report is
  unchanged). A fixture that gives a non-empty `valid` input for such a binding keeps the 1.4.0 skip.
* Expiry and session scope (SAFE-033) and revocation (SAFE-036) apply to every permit whatever its input
  schema; they are not part of `SAFE-031` and still have no executable check (`applicability.json`).
* Verdicts, levels, test sets and manifest digests of the five reference reports are unchanged; they were
  regenerated as 1.4.1 runs (only run-specific ids, digests and evidence differ).

Notes on suite 1.4.0 (`MHS/changes/RE-ENABLE-AND-TERMINAL-STOP.md`; a MINOR version under GOV-026,
because the suite now checks the new requirements CORE-086, CORE-087 and SAFE-048):

* `TSAFE-001` keeps its id (CON-013): on a device that declares neither `safety.estop.reenable` nor
  `safety.estop.terminal`, every assertion and the detail text are those of 1.3.0. On a device that declares a
  re-enable it also checks that the re-enable is refused `MHS.SAFETY.ESTOP_ENGAGED` while latched without
  reaching the bridge, and sends it after the reset and before the recovery command; when that re-enable needs a
  permit the suite cannot obtain (a hardware device without `--approvals`), the test is skipped before anything is
  sent, and a permit failure after the e-stop and the reset is a failure, never a skip. On a device that declares a
  terminal e-stop it checks the `terminal_estop` refusal, the declared reason, that the bridge was not called, and
  the retained latch.
* `SAFE-041` skips a device with a terminal e-stop (its reset is refused by design).
* The runner gives the test after a terminal e-stop a new endpoint (CON-022), or runs the e-stop tests last on a
  shared endpoint.
* Verdicts of the five reference reports are unchanged; they were regenerated as 1.4.0 runs and the 1.3.0 runs
  were copied to `_archive/sdk-docs-reports/suite-1.3.0-final/` first.

Notes on suite 1.3.0 (WP-07 milestone 07b), still in force:

* `SAFE-014` resolves the effective limits exactly like the runtime: the
  suite hands the published manifest to the server's own plan compiler
  (`mhs._server.limits_plan.compile_binding`: class ∩ binding ∩ envelope,
  patterns included, through `mhs.limits`) and intersects the result with the
  limits the endpoint publishes for the binding in `devices.get`
  (`x-mhs-effective-limits`, which carry the operator overlay
  `site-limits.json`). An endpoint that publishes a wider limit than its
  manifest declares gets a note; the declared limit is still probed. Every
  limited write/invoke binding is probed, also a permit-gated one (class or
  binding `requires_permit`, e.g. `cap.optics.set_power.v1`,
  `cap.sample.centrifuge.v1`, `cap.motion.joint_torque.v1`), a
  `safe_state.achieved_by` action and a stop class: plan 3.6 checks the limits
  (step 8) before the permit (step 10), and safe-state actions are exempt from
  the latch, not from limits. The probes carry no permit, and a `PERMIT_*`
  refusal fails the test (the limit check is missing or comes too late).
  Every limited path gets shape-correct values just outside both sides of its
  bound and outside its allowed set (inside the schema range, and on the
  `multipleOf` grid, when the schema allows one): every nested leaf
  (`position.z`), *every* element of an array with a per-element (vector)
  bound, and the first and the last element of every other array on the path,
  whether the path names the array (`joint_positions` with a scalar bound) or
  a leaf inside it (`points[*].z`). The last element is the array's fixed
  length (`minItems == maxItems`, or `prefixItems` with `items: false`);
  otherwise the probe grows the array to at least two elements when
  `maxItems` allows, so an endpoint that checks only the first element fails.
  An allowed set on a `pattern` string is probed with a same-shape mutation of
  an allowed value that the pattern and the field schema accept (`gear=loa`
  for `^[a-z]+$` and `[low, mid]`); a `format` string never gets an invented
  value. A numeric allowed set is probed above it, below it and between two
  of its members (`[1, 3, 5]` on an integer 0..10: `6`, `0` and `2`), with
  the values the field schema accepts once its `enum` is set aside. Every
  probe is mandatory; elements are taken breadth-first (the first element of
  every limited path, then the next ones) up to 256 per binding. A limited
  field is probed wherever a payload can carry it to the endpoint: the
  binding declares it in `properties` or in any `anyOf` / `oneOf` branch, or
  admits it without declaring it (no `additionalProperties: false`; names
  listed only in `required`; `patternProperties`). An admitted field's value
  is built from the class input schema. `SAFE-014` does not pass while a
  side of a limited element is unprobed: a limited binding without a valid
  base input (a required `pattern` string with no fixture or class example),
  a side without a buildable out-of-limit value, an admitted field for which
  no valid input can be built, a binding or envelope limit on a field the
  binding's schema rejects, and elements beyond the 256-element budget make
  it skip (required at CL3, so the level stops at CL2), naming each element
  and side and asking for a fixture, unless a probe that was sent found a
  violation (then it fails). A fixture's `out_of_envelope` inputs are sent
  first, also for a binding without a valid base input. When the suite cannot
  build a valid base input, it derives one from those inputs (each value
  outside its limit put back inside) and runs the normal probes from it.
  Otherwise a fixture refusal covers only the element and side each named
  violation proves (`points[0].z` above its maximum), never the whole path,
  and a refused probe at another element never covers an unprobed one. Only
  a class-default limit on a field no valid input of the binding can carry
  is not applicable, and the detail notes it. Both checks must agree: the
  schema, read with the keywords `mhs.schema` applies, rejects every input
  that carries the field (`additionalProperties: false` with no matching
  property or pattern, a type that cannot hold it, in every `anyOf` /
  `oneOf` option or in one `allOf` member), and, when there is a base input,
  no input built from it that carries the field inside its limits validates.
  Keywords the validator ignores (`unevaluatedProperties`) or that only add
  constraints (`not`, `if` / `then` / `else`) never make a field refused;
  such a field is a gap when no valid input carrying it can be built. The lab's
  `cap.fluid.*` `volume` and `cap.measure.spectrum.v1` `wavelength_min` are
  admitted by its bindings, so they are probed and the runtime refuses them.
  Each probe must be `rejected` with `MHS.SAFETY.ENVELOPE_VIOLATION` (legacy
  `LIMIT_EXCEEDED`), leave the revision unchanged (the receipt and the next
  read) and, in-process, reach no bridge method except a state read (`call`,
  `write`, `restore`, `estop`, `reset`, `snapshot` and `safe_state` fail it).
  `MHS.CAPABILITY.INPUT_INVALID` no longer counts, also where the schema
  repeats the bound: plan 3.5 checks the limits before the remaining schema
  bounds, so an out-of-range arm command is a safety refusal. A probe the
  endpoint refused for another path is noted.
* `OP-001` checks the revision rule of plan 3.7. The probe (write/invoke) must
  advance the device revision when any resource state changed and must keep
  it when none did (every resource of the device is read before and after).
  Every read-verb command that needs no permit must never advance the
  revision, whatever its outcome (TESTS-04: a measurement must not invalidate
  an `expected_revision`): each catalogued read class (deprecated reads such as
  `cap.world.state.v1` included) and each extension (`x-cap.*` or an
  uncatalogued id) that declares `verb: read` in its manifest or in the
  endpoint's device summary (`hello.devices[].capabilities[].verb`), the
  probe's device first; its input must validate against the published input
  schema. An extension's verb is the driver's own claim, so, like the
  runtime's latch and arming, the hardware gate does not trust it: extension
  reads are sent only to devices the suite may actuate, and the in-process
  gate and the send guard let only catalogued reads through to a hardware or
  hybrid device without `--allow-actuation`. A read-only endpoint is checked
  with its reads alone (the first must complete), and `OP-001` is then required unless a
  hardware device without `--allow-actuation` gates the run. A read whose
  input the suite cannot build (a required `pattern` string) is not sent;
  the `OP-001` note names it and asks for a `valid` fixture.
* `OP-011` ignores replay-mode devices: they refuse every command before any
  effect (FID-024), so they have nothing to cancel.
* `TCAP-001` requires the output to validate against the binding
  `output_schema` and not to be empty where the class requires output fields
  (a skeleton binding `output_schema` inherits the class output; no binding
  waives a required class field). Other mismatches with the class output are
  an advisory note until the reference fixtures are realigned.
* `SAFE-011`/`SAFE-012` require the device not to be latched before the probe
  and an injected interlock to be refused with `MHS.SAFETY.INTERLOCK_OPEN`; an
  `ESTOP_ENGAGED` refusal is not interlock evidence (over the hook path it
  counts only when opening the door is what latched the device).
* `TCAP-003` checks that the probe command has an observable effect. A write
  probe: two different writes leave different resource states. An invoke
  probe: the resource state changes, or the outputs of two distinct valid
  inputs differ (`no observable effect` when both are empty or identical and
  the state is unchanged). It is required for write probes and for invoke
  probes without a class output contract (an extension, or a class that
  requires no output field), where `TCAP-001` has nothing to enforce;
  otherwise it is advisory.
* `SAFE-028` requires the e-stop receipt to report `safe_state_achieved: true`
  (make the safe state observable through `safety_status` or a
  `safe_state.achieved_by` action), no `safe_state.achieved: false` in
  `mhs.safety.status` after the e-stop (the bridge's own report, under
  `status.safe_state`, or `safe_state`), and, in-process, the driver's
  `estop()` to be invoked and its `safety_status()` not to report the safe
  state unreached; the inherited no-op `Bridge.estop` fails it. The check is
  black-box: a driver that overrides `estop()` with its own no-op, declares a
  no-op `achieved_by` action and reports no safe state at all still passes it.
  It relies on the driver reporting honestly; showing the native stop itself
  (the driver gate's Recorder, WP-06) is outside the suite.
* `SAFE-045` accepts `estop.kind: hardware`, `kind: both` with a
  `physical_ref`, or a non-empty `safe_state.achieved_by`; a `software`
  e-stop is never a stop path, with or without a `physical_ref`.
* `CAP-016` and `TCAP-002` run but are advisory until the reference fixtures
  are realigned with their classes. `SAFE-041` stays advisory: the runtime now
  refuses resets with an open interlock, but the check forces the interlock
  open only in-process, so requiring it would cap every over-the-wire run of a
  device with interlocks (the conveyor's test profile included).

## Report

`report_version 1.1.0`, `suite_version 1.4.1`, `subject {kind, id, mhs_version,
manifest_digest, source_commit?}`, `level_claimed`, `level_achieved`, `tests[]`
(id, name, status, level, `required`, `spec_ref`, `duration_ms`, optional
`detail`/`mhs_code`/`evidence`), `environment` (with the run options in
`notes`), `coverage` (`required` counts the required tests), `issuer`,
`limitations` (including the applicability counts) and `disclaimers`
(`not_certified`, `not_affiliated`, `self_issued`, and `simulation_only` /
`contract_checked_only` when they apply). `disclaimers` is required by
`conformance-report.schema.json` and must contain `not_certified`.

`report_digest = "sha256:" + hex(SHA-256(JCS(report_body)))` where
`report_body` is the report without `report_digest` and `issuer.signature`.
`subject.manifest_digest` digests the device contracts under test (without
instance ids, state, revisions and conformance claims), so a report cannot be
reused for a different driver.

`validate_report()` checks the schema and digest, recomputes `level_achieved`
from the `required` flags and the level table, and refuses unknown test ids,
cleared `required` flags on always-required tests, missing `required` flags,
required tests missing from the report, a missing `not_certified`
disclaimer, a wrong `coverage.required`, a missing `subject.manifest_digest`
and a hidden CL0 failure. Every report is validated this way: the last
reports of the lenient suites (before 1.2.0) were regenerated in milestone
07b, and a report that claims a suite older than 1.2.0 is refused, so
rewriting the version string does not relax validation offline.
`python3 -m mhs.conformance verify` adds a re-run and compares the suite and
report versions, levels (including whether any level was awarded), test sets,
required verdicts and the manifest digest (missing is a mismatch).

## Requirement inventory

[`src/mhs/conformance/applicability.json`](../src/mhs/conformance/applicability.json)
records every numbered requirement with its executable checks or a disposition.
It is generated; re-run the generator after editing `MHS/spec/*.md` or
`traceability.json`:

```bash
python3 MHS/sdk/tools/build_applicability.py          # regenerate
python3 MHS/sdk/tools/build_applicability.py --check  # CI: exit 1 when stale
```

## Reference reports in this repository

Suite 1.4.1 runs, in-process against fresh reference endpoints. The file names
under `MHS/conformance/reports/` carry the achieved level; each report is
reproduced by the command in [`MHS/conformance/README.md`](../../conformance/README.md)
and re-checked with `python3 -m mhs.conformance verify <report> --reference ...`.

| report | subject | claimed / achieved | notes |
|---|---|---|---|
| [`MHS/conformance/reports/conveyor-cl4.json`](../../conformance/reports/conveyor-cl4.json) | conveyor (normal profile) | CL4 / **CL4** | the harness injects the `door_closed` interlock (no test hooks) |
| [`MHS/conformance/reports/lab-cl4.json`](../../conformance/reports/lab-cl4.json) | lab (3 devices) | CL4 / **CL4** | was `lab-cl2.json` until WP-06 06c bound the plate reader's `achieved_by` correctly (`SAFE-029`) |
| [`MHS/conformance/reports/arm-cl4.json`](../../conformance/reports/arm-cl4.json) | arm (exact) | CL4 / **CL4** | was `arm-cl3.json` (claimed at CL3) until WP-06 06c |
| [`reports/conformance-arm-2dof-seeded.json`](reports/conformance-arm-2dof-seeded.json) | arm `--noise` | CL4 / **CL4** | seeded replay (`FID-025`) |
| [`reports/conformance-replay-recorded.json`](reports/conformance-replay-recorded.json) | replay of a recorded conveyor | CL4 / **CL2** | read-only enforcement (`MODE-005`); CL3 needs `SAFE-014`, which has no limited actuating binding to probe |

The conveyor and lab copies that used to sit in `reports/` were byte-identical
duplicates of the `MHS/conformance/reports/` files; they were moved to
`_archive/sdk-docs-reports/` with the superseded suite 1.1.0 runs.

Reports are self-issued (`issuer.kind = "self"`); they are not a safety
certification and do not lift `MHS.SAFETY.NOT_CERTIFIED`.
