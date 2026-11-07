# MHS-001 — Conformance: Levels, Profiles, Test Suite and Claims

| Field | Value |
|---|---|
| Document | MHS-001 (normative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | core (levels, profiles, suite, reports) ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §15; overview in [00-architecture.md](00-architecture.md) §10 (informative) |
| Data contract | [`conformance-report.schema.json`](../schema/conformance-report.schema.json) |

This document defines what it means to claim MHS conformance: the levels CL0–CL5,
the five conformance profiles, the executable suite's behaviour, the test-case
identifier scheme, the report format and digest, and the rules for self-tested and
verified claims. It details [core.md](core.md) §15 and does not create a
new conformance model.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Principle

**CON-001.** A claim of MHS support MUST be a level from this document, for a
named profile, backed by a machine-readable report that a third party can
recompute. Prose, logos, badges without a report, and "MHS-compatible" claims
without a level are not conformance.

**CON-002.** A conformance report MUST validate against
[`conformance-report.schema.json`](../schema/conformance-report.schema.json) and
MUST be obtainable from the subject (endpoint or package) or from the registry
claim that cites it. A report that cannot be re-derived from the published suite
version is not evidence.

**CON-003.** MHS conformance means *behaviour under test*, not safety, quality,
clinical validity, regulatory approval, or fitness for a particular experiment.
Every report MUST include the disclaimer strings in §8.5.

---

## 2. Subjects and profiles

A conformance **subject** is the thing tested. The report schema allows
`endpoint`, `package`, `adapter`, `host`, `registry`.

| Profile | Subject kind | What is being tested | Levels defined |
|---|---|---|---|
| **MHS-Device** | endpoint | A hardware-backed endpoint and the devices it serves. | CL0–CL4 |
| **MHS-Sim** | endpoint | A simulated or hybrid endpoint, including its fidelity contract and determinism. | CL0–CL4 |
| **MHS-Bridge** | package / adapter / endpoint | An adapter manifest plus the endpoint(s) a bridge launches from it. | CL0–CL5 (see §3.3) |
| **MHS-Host** | host | An agent harness that consumes MHS. | CL1–CL5 (see §3.4) |
| **MHS-Registry** | registry | A registry deployment's records, trust and search. | CL1–CL5 (see §3.5) |

**CON-004.** The profile in a report MUST be one of the five values above and
MUST match the subject kind: an `endpoint` subject MUST use `MHS-Device`,
`MHS-Sim` or `MHS-Bridge`; a `package`/`adapter` subject MUST use `MHS-Bridge`; a
`host` subject MUST use `MHS-Host`; a `registry` subject MUST use `MHS-Registry`.

**CON-005.** An endpoint's declared profile MUST appear in the device manifest's
`conformance.profile` ([`device.schema.json`](../schema/device.schema.json)) and
in the endpoint descriptor's `conformance[]`
([`endpoint-descriptor.schema.json`](../schema/endpoint-descriptor.schema.json)).
A profile that appears in one place and not the other is a conformance defect.

**CON-006.** MHS-Device and MHS-Sim subjects are limited to CL4 by the profile
table of §2 (no replay requirement for hardware; simulated devices are tested through
CL4; [00-architecture.md](00-architecture.md) §10.2 gives the rationale, informative). Orchestration requirements, CL5, are assessed
only for MHS-Bridge, MHS-Host and MHS-Registry subjects.

---

## 3. Levels

### 3.1 Level definitions (expanded)

The following table defines the levels ([00-architecture.md](00-architecture.md)
§10.1 gives the informative overview) and binds each level to the documents that
define its requirements.

| Level | Name | MUST hold | Requirement areas exercised |
|---|---|---|---|
| **CL0** | Declared | Valid adapter/device manifests against the OpenMHS 0.9 schemas; no runtime required. Static checks only. | `ADPT`, `CAP`, `REG` (schema validity) |
| **CL1** | Observable | T1 and/or T2 transport; `hello`, `devices.list/get`, `schema.get`, `resource.read`, `subscribe`/`unsubscribe`; stable revisions and state hashes. | `PROTO`, `TPT`, `CAP`, `EVT` |
| **CL2** | Actuating | `session.open/close`, `command` with idempotency and receipts, `operations.get/cancel`, revision conflicts, deadlines, mode match. | `PROTO`, `SESS`, `OP`, `MODE` |
| **CL3** | Governed | `safety.status/estop/reset`, envelope enforcement, risk classes, permits for gated capabilities, session TTL/heartbeat, safe-state on cancel, `MHS.SAFETY.NOT_CERTIFIED` disclosure. | `SAFE`, `SESS`, `MODE` |
| **CL4** | Reproducible | Evidence export/verify (hash chain); for simulated/replay devices a deterministic replay test (same seed ⇒ identical `state_hash` sequence). | `EVID`, `FID` |
| **CL5** | Orchestrated | Composition execution with child receipts, multi-device sessions, backpressure and gap semantics, registry publication, and a published conformance report. | `COMP`, `EVT`, `REG`, `CON` |

**CON-007.** A report for level `CLn` MUST contain at least one `pass` result for
every requirement introduced at that level in §3.2 and MUST contain no `fail`
result for any requirement at `CLn` or below. `skip` is permitted only where §6.3
allows it; a skipped requirement does not count as passed for the level's
mandatory set unless §6.3 names it as skippable.

### 3.2 Requirement coverage by level

Legend: **●** every relevant test in the area MUST run and pass; **◐** a subset
defined by the level's mandatory suite is REQUIRED; **—** not required.

| Area | CL0 | CL1 | CL2 | CL3 | CL4 | CL5 |
|---|---|---|---|---|---|---|
| `ADPT` adapter/manifest | ● | ◐ | ◐ | ◐ | ◐ | ● |
| `CAP` classes and bindings | ● | ● | ● | ◐ | ◐ | ◐ |
| `REG` registry publication | ● | — | — | — | ◐ | ● |
| `PROTO` framing/methods | — | ● | ● | ● | ◐ | ◐ |
| `TPT` transports | — | ● | ● | ◐ | ◐ | ◐ |
| `SESS` sessions | — | ◐ | ● | ● | ◐ | ◐ |
| `OP` operations/idempotency | — | — | ● | ● | ◐ | ● |
| `MODE` mode declaration | — | ● | ● | ● | ● | ◐ |
| `EVT` subscriptions | — | ● | ● | ◐ | ◐ | ● |
| `SAFE` safety | — | — | ◐ | ● | ● | ◐ |
| `FID` fidelity/determinism | — | ◐ (sim) | ◐ (sim) | ◐ (sim) | ● (sim/replay) | ◐ |
| `EVID` evidence | — | — | ◐ | ◐ | ● | ● |
| `COMP` compositions | — | — | — | — | — | ● |
| `CON` meta | ● | ● | ● | ● | ● | ● |

**CON-008.** `CON` tests (report validity, digest recomputation, claim
consistency) are always REQUIRED and are the only tests that MAY run without a
reachable endpoint at CL0. A CL0 report MUST contain at least one test result
(the schema requires `tests.minItems: 1`), at least one of which MUST be a
schema-validation test of every manifest the subject publishes.

**CON-009.** An MHS-Sim or MHS-Bridge subject running a simulated device MUST
include `FID` tests at every level at which it makes runtime claims, because
mode/identity disclosure applies from CL1 upward.

### 3.3 MHS-Bridge levels

| Level | Meaning for a bridge |
|---|---|
| CL0 | Adapter manifest validates; devices declared; evidence state at least `declared`. |
| CL2 | The bridge launches at least one endpoint from the adapter and that endpoint achieves CL2. CL1 is implied, not claimed separately. |
| CL3 | The produced endpoint achieves CL3. |
| CL4 | The produced endpoint achieves CL4 (evidence + determinism where applicable). |
| CL5 | The produced endpoint achieves CL5 and the bridge publishes its report in the registry. |

**CON-010.** An MHS-Bridge report MUST name the endpoint(s) it started in
`environment.endpoint_ids` and MUST include the endpoint-level test results it
relies on. A bridge claim MUST NOT exceed the level achieved by its endpoint.

### 3.4 MHS-Host levels

| Level | Meaning for a host |
|---|---|
| CL1 | Discovers endpoints, reads devices and state, honours mode/fidelity disclosure. |
| CL2 | Opens least-privilege sessions, invokes commands, handles receipts, deadlines and cancellation. |
| CL3 | Enforces approval flow for permits, surfaces risk/fidelity/trust, handles e-stop and unknown outcomes. |
| CL4 | Maintains an append-only evidence ledger and can export and verify it. |
| CL5 | Orchestrates multiple endpoints and compositions, and records child receipts. |

**CON-011.** A host report MUST be produced against an endpoint that holds a
valid CL3-or-higher report, and the host report MUST cite that endpoint report's
digest. A host tested only against mocks is a self-test and MUST be labelled
`issuer.kind: "self"` with a `limitations` entry saying so.

### 3.5 MHS-Registry levels

| Level | Meaning for a registry |
|---|---|
| CL1 | All records validate; index loads; records are addressable by id. |
| CL2 | Search returns correct results for capability, tag, mode, vendor and keyword queries with bounded latency. |
| CL3 | Trust levels and signatures are verified and displayed; unsigned records are not presented as verified. |
| CL4 | Index digest is reproducible: the published `index.json` digest equals the digest recomputed from the shard files. |
| CL5 | Federation: at least two registry deployments interoperate, and search latency bounds in §6.6 are met. |

**CON-012.** A registry MUST publish `index.json` with a `registry_version`,
`generated_at`, and a digest over the record set, and MUST make the digest
recomputable from the published records ([MHS-007](07-registry.md) §8).

---

## 4. Test-case identifiers

### 4.1 Scheme

Test ids are `AREA-NNN` or `T<AREA>-NNN`, where `AREA` matches `[A-Z]+` and `NNN`
is a zero-padded three-digit integer; both forms match the report schema pattern
`^[A-Z]+-[0-9]{3}$`. A test that is the canonical executable check for a
requirement uses the requirement's id ([spec README](README.md) §3), so a report is
directly a requirement trace for those tests. Grouped or auxiliary tests use the
`T`-prefixed form (for example `TCAP-001` checks several capability requirements)
and MUST NOT reuse a number already assigned to a requirement in that area; the
suite's `traceability.json` maps every test id to the requirement id(s) it checks.

**CON-013.** Test ids MUST be stable across suite versions for the same check. A
changed assertion gets a new id and the old id is retired, never reused for a
different assertion.

**CON-014.** A test MUST cite the requirement id(s) it checks. When it is the
canonical check for one requirement its `id` MUST be that requirement id; when it
is grouped it MUST use `T<AREA>-NNN` and MUST appear in `traceability.json`. A
grouped test that checks several requirements reports the full requirement list in
that file, and a requirement MUST NOT be left without at least one test at the
level that introduces it.

### 4.2 Areas

| Area | Range owner | Tests on… |
|---|---|---|
| `PROTO` | [MHS-002](02-wire-protocol.md) | JSON-RPC framing, method presence, params/result shape, error mapping, batches, notifications. |
| `SESS` | [MHS-002](02-wire-protocol.md) | Session open/heartbeat/close, grants, expiry, principal binding. |
| `CAP` | [MHS-003](03-capability-registry.md) | Class documents, input validation, units, binding limits. |
| `SAFE` | [MHS-004](04-safety.md) | Envelope order, interlocks, permits, e-stop latch/reset, safe state, disclosure. |
| `MODE` | [MHS-005](05-fidelity.md) | Mode declaration, mode mismatch rejection, read-only replay. |
| `FID` | [MHS-005](05-fidelity.md) | Fidelity contract presence, determinism claims, replay equality, gap disclosure. |
| `EVID` | [MHS-002](02-wire-protocol.md), [MHS-004](04-safety.md) | Receipt chain, export, verify, tamper detection, retention markers. |
| `OP` | [MHS-002](02-wire-protocol.md) | Idempotency, revision conflicts, operations, cancellation, deadlines, unknown outcome. |
| `EVT` | [MHS-002](02-wire-protocol.md) | Subscription sequencing, gaps, backpressure, unsubscribe. |
| `COMP` | [MHS-002](02-wire-protocol.md) | Composition runs, child receipts, abort semantics. |
| `TPT` | [MHS-008](08-transports.md) | Each transport binding and the MCP projection. |
| `ADPT` | [MHS-006](06-adapters.md) | Adapter manifest validity, mapping rules, packaging, licensing refusal. |
| `REG` | [MHS-007](07-registry.md) | Record validity, trust, signing, search, federation. |
| `HOST` | [MHS-009](09-host-profile.md) | Host discovery, sessions, approvals, disclosure, ledger. |
| `CON` | this document | Report validity, digest, claim consistency. |
| `GOV` | [MHS-010](10-governance.md) | Process requirements; verified editorially, not in the suite. |

**CON-015.** The suite MUST include, for each level it claims to test, at least
one negative test per rejection code in the level's mandatory set. A suite that
only tests success paths cannot award a level.

### 4.3 Mandatory negative tests

The following negative behaviours MUST be tested before a level can be awarded;
the ids are the requirement ids they check.

| Requirement | Negative behaviour |
|---|---|
| `PROTO-010` | Request missing `deadline_ms` on a blocking method is rejected with `INVALID_PARAMS`. |
| `PROTO-017` | Unknown or unimplemented method returns `METHOD_NOT_FOUND`; implementation does not crash. |
| `OP-003` | Replayed `command_id` with same input returns retained receipt with `replayed: true`, no new effect. |
| `OP-004` | Reused `command_id` with different input returns `MHS.CONFLICT.COMMAND_ID_REUSE`, no effect. |
| `OP-005` | Stale `expected_revision` returns `MHS.CONFLICT.REVISION` with `data.current_revision`, no effect. |
| `OP-011` | Cancellation reaches declared safe state or reports `safe_state_achieved: false`. |
| `OP-013` | Irreversible action interrupted by lost response surfaces `MHS.OUTCOME.UNKNOWN`, not success. |
| `SESS-004` | Session expiry releases leases and cancels running operations to safe state. |
| `SESS-008` | A capability not granted at open is rejected with `MHS.SESSION.CAPABILITY_NOT_GRANTED`. |
| `MODE-002` | Session requesting an undeclared mode is rejected with `MHS.SESSION.MODE_MISMATCH`. |
| `MODE-005` | Mutation in `replay` mode returns `MHS.MODE.READ_ONLY`, no state change. |
| `SAFE-011` | Interlock `open` blocks actuation with `MHS.SAFETY.INTERLOCK_OPEN`, revision unchanged. |
| `SAFE-012` | Interlock `unknown` blocks actuation (fail closed). |
| `SAFE-014` | Envelope violation is rejected before any effect (`MHS.SAFETY.ENVELOPE_VIOLATION`), with the violated limit, value and unit, also where the schema repeats the bound. |
| `SAFE-030` | Gated capability without permit returns `MHS.SAFETY.PERMIT_INVALID`. |
| `SAFE-031` | Permit for a different `input_digest` is rejected (permit replay). |
| `SAFE-040` | E-stop engages within declared latency; device latches. |
| `SAFE-041` | Reset with an open hard interlock is refused (`MHS.SAFETY.RESET_REFUSED`). |
| `SAFE-042` | Release of e-stop does not restart motion; a new command is required; a declared re-enable is refused while latched (`MHS.SAFETY.ESTOP_ENGAGED`). |
| `SAFE-048` | Reset after a declared terminal e-stop is refused (`MHS.SAFETY.RESET_REFUSED`, `terminal_estop`) and the latch is kept. |
| `FID-010` | Simulated device without a fidelity contract fails CL0/CL1 validation. |
| `FID-025` | Replay with the same seed and commands yields an identical `state_hash` sequence; a mismatch is a failure, not a warning. |
| `EVID-010` | Tampering with one receipt breaks chain verification with `MHS.EVIDENCE.CHAIN_BROKEN`. |
| `EVT-006` | Slow consumer receives `MHS.LIMIT.BACKPRESSURE` rather than unbounded buffering. |
| `EVT-008` | An induced sequence gap produces an explicit gap event, never silent drops. |
| `SAFE-050` | `hello.features` omits `MHS.SAFETY.NOT_CERTIFIED` ⇒ CL3 fails. |

**CON-016.** The negative tests in the table above MUST be present in the suite
for the levels that introduce the requirement. They MUST NOT be skipped because
a device is simulated; simulated endpoints are the main place these semantics are
verified.

### 4.4 Coverage of SAFE-014

SAFE-014 ([MHS-004](04-safety.md) §3.3) can pass only when every limited path is shown
refused. The suite probes each limit that reaches an input: a field is probed when it
is declared (in `properties` or in any `anyOf`/`oneOf` branch) or admitted by the
schema; both sides of a range are probed; for an `allowed` set, a value outside it, and
for a numeric set the values above, below and between its members; the first and the
last element of an array and every element of a per-element bound. A gap is reported per
element and side, so a fixture refusal covers only what it names. A fixture
(`fixtures/conformance.json`, `out_of_envelope`) may supply the probes the suite cannot
synthesise (a pattern string, an allowed string set), and a base input may be derived
from those inputs. A limit that the class carries by default on a field the binding's
schema rejects for every input is *not applicable*: the schema, read with the validator's
own keywords, must reject every input that carries the field and, given a base input, no
input that carries it inside its limits may validate; keywords the validator ignores, or
that only add constraints, never count as a refusal. Limits apply to permit-gated
bindings, to stop classes and to `safe_state.achieved_by` actions, and are checked before
the permit. A read the suite could not send is noted under OP-001.

---

## 5. Test matrix

### 5.1 Endpoint matrix (MHS-Device, MHS-Sim)

| Level | Required areas | Representative mandatory ids | Skippable |
|---|---|---|---|
| CL0 | `ADPT`, `CAP`, `REG`, `CON` | `ADPT-001`–`ADPT-004`, `CAP-004`, `CAP-008`, `CAP-021`, `REG-002`, `CON-008` | Nothing for schema checks. |
| CL1 | + `PROTO`, `TPT`, `EVT`, `MODE`, `SESS` (open only) | `PROTO-001`–`PROTO-020`, `TPT-001`, `TPT-010`, `CAP-033`, `EVT-001`–`EVT-006`, `MODE-001`–`MODE-003` | `SESS-*` beyond open/close. |
| CL2 | + `SESS`, `OP`, `EVID` (receipts) | `PROTO-027`–`PROTO-043`, `SESS-001`–`SESS-008`, `OP-001`–`OP-014`, `EVID-001`–`EVID-004` | `SAFE-*`, `COMP-*`. |
| CL3 | + `SAFE` | `SAFE-001`–`SAFE-060`, `SESS-010`–`SESS-012`, `MODE-002`, `MODE-005` | `SAFE-016` (cumulative budgets) where the device declares none. |
| CL4 | + `FID`, `EVID` (full) | `EVID-010`–`EVID-018`, `FID-001`–`FID-030` (sim/replay), `OP-010`–`OP-012` | `FID-040`+ (validation methodology) where no validation record is claimed. |
| CL5 | — for this subject | — | — |

**CON-017.** A simulated endpoint claiming CL4 MUST pass `FID-025` (deterministic
replay) and MUST publish the replay transcript in its evidence bundle. A
hardware endpoint MUST NOT be tested for `FID-025`; the suite MUST mark it `skip`
with a reason, and the skip MUST NOT affect the level.

### 5.2 Bridge, host, registry matrix

| Level | MHS-Bridge required | MHS-Host required | MHS-Registry required |
|---|---|---|---|
| CL0 | `ADPT-001`–`ADPT-020` | — | — |
| CL1 | implied by endpoint | `HOST-001`–`HOST-003`, `HOST-010`–`HOST-015` | `REG-001`–`REG-010` |
| CL2 | endpoint CL2 + `ADPT-030` | `HOST-020`–`HOST-022`, `HOST-030`–`HOST-037` | `REG-011`–`REG-018` |
| CL3 | endpoint CL3 + `ADPT-031` | `HOST-040`–`HOST-047`, `HOST-070`–`HOST-073` | `REG-019`–`REG-026` |
| CL4 | endpoint CL4 + `ADPT-032` | `HOST-050`–`HOST-056` | `REG-027`–`REG-030` |
| CL5 | endpoint CL5 + `ADPT-033`, `ADPT-040` | `HOST-057`, `HOST-080`–`HOST-085` | `REG-031`–`REG-034` |

**CON-018.** The suite MUST NOT award a level when a required test is `fail`,
`warn` or `skip`. `warn` is a non-blocking observation recorded for the reviewer
and MUST be accompanied by a `detail` string; it is never a waiver. Award MUST be
computed from the machine-readable requirement matrix
(`mhs/conformance/requirements.py` plus the required cases), not from whichever
files happen to be registered: the matrix's mandatory methods are probed for
presence one level at a time (`TPROTO-901` for CL1, `TPROTO-902` for CL2,
`TPROTO-903` for CL3) and a `METHOD_NOT_FOUND` for any of them caps the level at
the level that does not require it (PROTO-016). A presence probe MUST be
method-specific, syntactically valid and non-mutating, MUST carry `deadline_ms`
for a blocking method, and MUST NOT count a generic pre-dispatch rejection
(deadline or JSON-RPC envelope validation) as evidence that the method exists.
Cancellation (`OP-011`) is required whenever the endpoint declares a
`constraints.cancellable: true` binding; a required `fail`, `warn` or `skip` caps
the level.

**CON-019.** A report's `level_achieved` MUST be the highest level for which all
required tests pass, and MUST NOT exceed `level_claimed`. A claim above the
achieved level is invalid and MUST be rejected by the registry. A report MUST
also state, in `limitations`, the counts from the machine-readable applicability
inventory
(`mhs/conformance/applicability.json`): numbered requirements total,
`checked`, `tested`, `dispositioned` (with its profile/level/editorial
breakdown) and `not_verified`. Requirements with no executable check, and
requirements excluded by profile or level, MUST NOT be counted as checked, and
`level_achieved` MUST NOT be presented as full coverage of the numbered
requirements. `checked + dispositioned + not_verified` MUST equal the numbered
total; `tested` is the subset of `checked` whose checks ran in the report.

---

## 6. Suite behaviour

### 6.1 Invocation and isolation

**CON-020.** The suite MUST be runnable from the command line as `python -m
mhs.conformance [run] --endpoint <url> --profile <profile> --level <CLn> --out
report.json` (`run` is the default subcommand; `--command`, `--factory` and
`--reference` select other subjects), with `python -m mhs.conformance verify
<report> --endpoint <url>` re-running a report and comparing it, and as a library call
`run_suite(client, profile, level) -> dict` in the reference SDK (`mhs conform` is the
same suite behind the `mhs` command, [MHS-008](08-transports.md) TPT-050). Both entry
points MUST produce byte-identical report content for the same run (apart from
`environment.date` and durations).

**CON-021.** The suite MUST open its own sessions, with its own principal (for
example `{id: "mhs-conformance", kind: "service"}`), and MUST close every session
it opens, including on failure. It MUST NOT rely on the host's session.

**CON-022.** Tests MUST be ordered so that no test depends on a previous test's
state except through declared fixtures; each test MUST either restore the
fixture or be marked `serialized` in the suite metadata. The suite MUST be safe to
run against a device in production only when invoked with `--read-only` (no
CL2+ tests are then run). A test that engages a declared terminal e-stop
([core.md](core.md) CORE-087) cannot restore its fixture: an in-process run MUST give
every later test a new endpoint, and a run over one shared endpoint MUST run the
tests that e-stop after every other test that sends a command.

### 6.2 Deadlines, retries and timeouts

**CON-023.** Every suite request MUST carry `deadline_ms`; the suite MUST treat a
missing response within `deadline_ms + 1000` as a failure of the test, not as a
hang, and MUST attempt to cancel any operation it started.

**CON-024.** The suite MUST NOT retry a request whose outcome is
`MHS.OUTCOME.UNKNOWN`; it MUST first observe state and then report the test as
`fail` with the observed state and the receipt, or as `warn` if the test is
explicitly marked outcome-tolerant.

**CON-025.** For tests that intentionally trigger failure paths (revision
conflicts, interlock open, envelope violation), the suite MUST verify both the
error and the absence of the forbidden effect (revision unchanged, no new
receipt with `completed` for that command id).

### 6.3 Skips

**CON-026.** A test MAY be skipped only when: (a) the capability under test is not
bound by the subject and the profile permits its absence; (b) the transport
required by the test is not offered and the profile does not require it; or (c)
the test is `FID-025` on a hardware subject. Every skip MUST include a `detail`
reason and a machine-readable `mhs_code` when the reason is an error.

**CON-027.** Skipping a test that is REQUIRED at the claimed level MUST cap
`level_achieved` at the level that does not require it. A report MUST NOT claim a
level on the basis of skips. `OP-011` is optional only when the endpoint declares
no `constraints.cancellable: true` binding; otherwise it is required.

### 6.4 Determinism and environment

**CON-028.** The report MUST record the suite version, MHS protocol version
negotiated, OS string, Python or runtime version (when applicable), date, and the
endpoint ids used. The suite version MUST be a semantic version; the spec
couples to suites by MAJOR.

**CON-029.** For reproducibility, each test result SHOULD carry
`evidence.request_digest` and `evidence.response_digest`, computed as SHA-256
over the JCS canonical form of the request and response. These digests are what a
verifier replays.

**CON-030.** For non-deterministic devices, the suite MUST record the seed or
observed variance in the test `detail`; it MUST NOT report a nondeterministic
success as a determinism pass.

### 6.5 Safety of the test run

**CON-031.** The suite MUST refuse to actuate a device whose mode is `hardware` or
`hybrid` unless the operator supplies `--allow-actuation`: the gate is by mode, at
every risk class, and the actuating tests are withheld and reported as skipped.
Without the option the suite MUST also not send the negative tests (commands the
endpoint must refuse) to a hardware device over a transport, because nothing would stop
such a command before the device if the endpoint failed to refuse it; in process the
harness blocks hardware write and invoke calls at the bridge, and any call it saw
fails CON-031 and names the test. A required test that is skipped caps the level. The
suite MUST NOT invent permits; `mhs.safety.permit` requires approval evidence from the
host.

**CON-032.** Tests that require physical motion MUST use the smallest motion the
capability permits, MUST honour `safety.safe_state` for their setup, and MUST send
`mhs.safety.estop` only to devices whose declared e-stop is `software` or `both`;
a `hardware`-only e-stop MUST be exercised by a human.

### 6.6 Latency bounds

**CON-033.** For local loopback transports, the suite MUST measure and report
`hello` and `resource.read` latency percentiles. The following bounds are targets
for a `pass` on `TPT-020`; exceeding them is a `warn`, not a structural failure:

| Measurement | Target p50 | Target p99 |
|---|---|---|
| `hello` over stdio or loopback HTTP | ≤ 50 ms | ≤ 250 ms |
| `resource.read` (single resource) | ≤ 20 ms | ≤ 100 ms |
| `safety.status` | ≤ 20 ms | ≤ 100 ms |
| Registry search (local index) | ≤ 10 ms | ≤ 100 ms |

**CON-034.** The suite MUST report measured latency in the test `detail`; claims
about latency MUST cite a report.

---

## 7. Report format

### 7.1 Example

The following report is valid against
[`conformance-report.schema.json`](../schema/conformance-report.schema.json):

```json
{
  "report_version": "1.0.0",
  "suite_version": "1.0.0",
  "profile": "MHS-Sim",
  "subject": {
    "kind": "endpoint",
    "id": "mhs://localhost:7400",
    "mhs_version": "1.0"
  },
  "level_claimed": "CL4",
  "level_achieved": "CL4",
  "tests": [
    {
      "id": "CAP-008",
      "name": "served class documents validate",
      "status": "pass",
      "level": "CL1",
      "duration_ms": 12.4
    },
    {
      "id": "SAFE-011",
      "name": "open interlock blocks actuation",
      "status": "pass",
      "level": "CL3",
      "duration_ms": 41.0,
      "mhs_code": "MHS.SAFETY.INTERLOCK_OPEN"
    },
    {
      "id": "FID-025",
      "name": "deterministic replay state-hash sequence",
      "status": "pass",
      "level": "CL4",
      "detail": "seed 42, 120 ticks, 12 state hashes compared, all equal"
    }
  ],
  "environment": {
    "os": "macOS 15.6 arm64",
    "python": "3.12.8",
    "date": "2026-10-20T07:40:00Z",
    "suite": "openmhs 0.9.0.dev0",
    "endpoint_ids": ["mhs://localhost:7400"]
  },
  "coverage": { "required": 3, "passed": 3, "failed": 0, "skipped": 0 },
  "report_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "issuer": { "kind": "self", "name": "OpenMHS reference SDK" },
  "limitations": [
    "Report covers the endpoint as configured at the stated date only."
  ],
  "disclaimers": [
    { "id": "not_certified", "text": "MHS conformance is a behavioural test result, not a safety certification; MHS.SAFETY.NOT_CERTIFIED." },
    { "id": "not_affiliated", "text": "OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic." },
    { "id": "self_issued", "text": "This report was issued by the subject's own operator, not verified by a third party." },
    { "id": "simulation_only", "text": "Simulation conformance does not establish equivalence to the physical device; see the fidelity gaps in the device manifest." }
  ]
}
```

In a real report `report_digest` is computed (§7.2) and `sha256:000…` is never
used; the zero digest above is a placeholder. `disclaimers` is required and MUST
contain `not_certified`; a report that only ran on a fake or simulator backend adds
`contract_checked_only` or `simulation_only`, and one the operator issued itself
`self_issued`. An endpoint that has run nothing answers `mhs.conformance.report` with a
`CL0` report in which every test is `skip` with the detail `not_run`
([MHS-002](02-wire-protocol.md) §14.3). The full transcripts behind
the digests are in [MHS-C](appendix-c-examples.md).

### 7.2 Report digest

**CON-035.** `report_digest` MUST be `"sha256:" + hex(SHA-256(JCS(report_body)))`
where `report_body` is the report object with `report_digest` removed and
`issuer.signature` removed, serialized with RFC 8785 JCS. The digest therefore
covers every test result, every environment field and the issuer identity, but not
the signature over itself.

**CON-036.** A verifier MUST recompute `report_digest` before looking at
`level_achieved`; a mismatch makes the report invalid and the claim void with
`MHS.EVIDENCE.CHAIN_BROKEN`.

### 7.3 Issuer and signature

`issuer.kind` is `self` or `verified`.

- **self** — the subject ran the suite on itself, or its maintainer did. The
  signature is optional. A self claim MAY be published, MUST be labelled
  "self-tested", and MUST NOT use a verification badge.
- **verified** — a third party ran the suite and signed the report. `issuer.name`
  and `issuer.key_id` are REQUIRED; `issuer.signature` is a detached JWS over the
  `report_digest` using `EdDSA` or `ES256`. The verifier's public key MUST be
  resolvable from the registry ([MHS-007](07-registry.md) §5).

**CON-037.** A report with `issuer.kind: "verified"` and no signature, or whose
signature does not verify against the named key, MUST be treated as `self` by
every consumer and MUST be flagged `MHS.EVIDENCE.SIGNATURE_INVALID` when verified.

**CON-038.** `verified` does not mean "more conformant"; it means "the same tests
were run by a party other than the subject". The level is set by the tests, not
the issuer.

---

## 8. Claims and badges

### 8.1 The claim record

A conformance claim is the registry-side pointer to a report
([`registry-record.schema.json`](../schema/registry-record.schema.json);
[00-architecture.md](00-architecture.md) §10.3 gives the overview):

```json
{
  "package_or_endpoint": "mhs://localhost:7400",
  "profile": "MHS-Sim",
  "level": "CL4",
  "suite_version": "1.0.0",
  "report_digest": "sha256:…",
  "issued_at": "2026-10-20T07:40:00Z",
  "issuer_kind": "self"
}
```

**CON-039.** A claim MUST be no stronger than its report: same profile, same
level, same `report_digest`, same `issuer_kind`. A claim without a retrievable
report is invalid.

**CON-040.** A claim MUST state the MHS protocol version and the endpoint ids or
package id it covers. A claim that covers a moving target (a `master` branch, a
device in an unknown firmware state) MUST say so in the record's `limitations`
and MUST be re-issued when the manifest digest changes.

### 8.2 Validity

**CON-041.** A claim MUST be re-issued when any of the following occurs:

1. any covered device manifest changes its `device_id`, `capabilities`,
   `safety`, or `fidelity` blocks (manifest digest change);
2. the suite MAJOR version changes;
3. the MHS protocol MAJOR version changes;
4. the issuer's key is revoked.

**CON-042.** A claim SHOULD be re-verified at least every 12 months. The registry
MUST display the `issued_at` date and MUST mark claims older than 18 months as
`stale` in search results. `stale` does not mean false; it means "not recently
demonstrated".

### 8.3 Badge text

**CON-043.** Displayed claims MUST use the following forms and no others:

| Issuer | Badge text | Colour guidance (informative) |
|---|---|---|
| self | `MHS CL3 · MHS-Sim · self-tested · 2026-10-20` | neutral |
| verified | `MHS CL3 · MHS-Sim · verified by <issuer> · 2026-10-20` | accent, with link to report |
| stale self | `MHS CL3 · MHS-Sim · self-tested · stale` | muted |
| CL0 | `MHS CL0 · declared` | muted |

**CON-044.** A badge MUST link to the report (or a stable page containing it)
and MUST show trust level next to any capability description that cites it
([MHS-007](07-registry.md) §5).

### 8.4 Prohibited claims

**CON-045.** A subject MUST NOT claim or imply, in any material: MHS
certification; that MHS makes a device safe; a safety integrity level; regulatory
approval; that a level applies to capabilities or transports not tested; or a
level for a profile other than the one tested. The phrases "MHS certified",
"MHS safety certified" and "MHS approved" are prohibited.

**CON-046.** A claim MUST NOT be transferred between packages, adapters or
endpoints. A bridge claim covers the bridge and the endpoints it launched; it does
not cover every device the package could theoretically expose.

### 8.5 Disclaimer strings

Every report, claim and badge page MUST carry, verbatim or with an equivalent
meaning that keeps the negation:

1. `MHS conformance is a behavioural test result, not a safety certification.`
2. `MHS.SAFETY.NOT_CERTIFIED` — MHS is not a safety-rated channel; an independent
   hardware emergency stop is required.
3. For simulated subjects: `Simulation conformance does not establish equivalence
   to the physical device; see the fidelity gaps in the device manifest.`

**CON-047.** The suite MUST fail CL3 and above when the endpoint does not report
`MHS.SAFETY.NOT_CERTIFIED` in `mhs.hello` features
([MHS-004](04-safety.md) SAFE-050).

---

## 9. Requirements list (this document)

**CON-001** Claim = level + profile + recomputable report.
**CON-002** Report validates against the schema; evidence re-derivable.
**CON-003** Conformance ≠ safety; disclaimers mandatory.
**CON-004** Profile matches subject kind.
**CON-005** Profile consistent between manifest and endpoint descriptor.
**CON-006** Device/Sim capped at CL4; CL5 only for Bridge/Host/Registry.
**CON-007** Level requires all level requirements passing, none failing.
**CON-008** CL0 report still contains schema tests; `tests.minItems` honoured.
**CON-009** Simulated subjects test FID from CL1 upward.
**CON-010** Bridge claim bounded by endpoint level; endpoint ids recorded.
**CON-011** Host tested against a CL3+ endpoint; mocks only self-labelled.
**CON-012** Registry publishes a reproducible index digest.
**CON-013** Test ids stable, never reused.
**CON-014** One test ↔ one requirement citation.
**CON-015** Negative test per mandatory rejection code.
**CON-016** Mandatory negative set present and not skipped for simulators.
**CON-017** Sim CL4 requires deterministic replay; hardware skips it formally.
**CON-018** No level on fail/warn.
**CON-019** `level_achieved` ≤ `level_claimed` and correct.
**CON-020** CLI and library entry points produce equivalent reports.
**CON-021** Suite owns its sessions; closes on failure.
**CON-022** Test-independence and read-only mode.
**CON-023** Every request deadline-bounded; hangs are test failures.
**CON-024** No blind retry of unknown outcomes.
**CON-025** Failure-path tests verify absence of effect.
**CON-026** Skip only for the three named reasons, with reason recorded.
**CON-027** Skipped required tests cap the achieved level.
**CON-028** Environment pinned in report.
**CON-029** Request/response digests recorded.
**CON-030** Nondeterminism recorded, never reported as determinism pass.
**CON-031** R2/R3 actuation gated on operator opt-in and permits.
**CON-032** Minimal motion; hardware e-stop by human only.
**CON-033** Latency measured and reported.
**CON-034** Latency claims cite reports.
**CON-035** Digest definition.
**CON-036** Digest recomputed before level is trusted.
**CON-037** Verified requires a valid signature; otherwise self.
**CON-038** Verified is about who ran it, not a higher level.
**CON-039** Claim no stronger than report.
**CON-040** Claim states protocol version and covered ids.
**CON-041** Re-issue triggers.
**CON-042** 12-month re-verification, 18-month stale marking.
**CON-043** Badge text forms.
**CON-044** Badge links to report; trust shown.
**CON-045** Prohibited claims.
**CON-046** No claim transfer.
**CON-047** CL3 requires `MHS.SAFETY.NOT_CERTIFIED` disclosure.

---

## 10. Informative: what a reviewer should check

This section is informative.

1. Recompute `report_digest`; check it matches the claim.
2. Open the report and confirm `level_achieved` equals the claimed level and that
   no required test is `skip` or `fail`.
3. Check that every test id in the report exists in the suite version named; a
   report citing unknown ids is fabricated or from a different suite.
4. For a simulated subject, read `fidelity.gaps` and the replay transcript; a
   CL4 sim claim without a determinism transcript is incomplete.
5. For a hardware subject, confirm the endpoint declares a hardware e-stop and
   that the report does not imply MHS is a safety channel.
6. Check `issued_at` and the manifest digest; a report older than the current
   manifest is a claim about a different device.
