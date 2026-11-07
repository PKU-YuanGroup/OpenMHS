# MHS-010 — Governance: RFC Process, Versioning, Deprecation, Disclosure and Licensing

| Field | Value |
|---|---|
| Document | MHS-010 (normative process) |
| Status | OpenMHS 0.9 development draft (`0.9-draft`) |
| Editor | The OpenMHS Authors |
| Layer | optional profile: Governance |
| Normative base | [core.md](core.md); the order of precedence is [README](README.md) §1 |
| Applies to | The OpenMHS document set, the schemas, the capability registry, the conformance suite, the driver packages and the registry format |

This document defines how OpenMHS changes: how a proposal becomes normative text, how
versions are assigned, how capability classes and protocol features are deprecated,
how security and safety defects are disclosed, how the artifacts are licensed, and
the editorial rules that keep the document set testable and internally consistent.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Governance model

**GOV-001.** OpenMHS is developed by an open group of maintainers
(**The OpenMHS Authors**, called "the editors" below) and reviewed in public. The editors maintain
the normative document set, the schemas, the capability registry and the
conformance suite. There is no certification body: conformance is executable and
claims are self-tested or third-party verified ([00-architecture.md](00-architecture.md)
decision D8, informative; [MHS-001](01-conformance.md) §8). OpenMHS is independent
of any vendor and is not affiliated with or endorsed by Anthropic
([MHS-D](appendix-d-anthropic-mhs.md)).

**GOV-002.** No single vendor controls the normative text. A change that is
motivated by one vendor's product MUST state the general problem it solves, and
MUST NOT make a core requirement conditional on a vendor-specific feature.
Extensions live in extension namespaces ([MHS-003](03-capability-registry.md) §8).

**GOV-003.** Decisions are recorded. Every accepted change has a public
**decision record** naming the RFC, the requirement ids affected, the review
comments and their resolution, and the effective version. Decisions are made by
rough consensus of the editors; a formal vote is held on request of any editor or
of two implementers, and the vote result is recorded.

**GOV-004.** Appeals: a rejected proposal MAY be re-submitted with new evidence.
A rejected safety-related proposal MAY be escalated to the security response team
(§7) if the proposer believes the rejection creates a hazard. Security and safety
reports are never closed as "won't fix" without a written rationale.

**GOV-005.** The order of precedence is: (1) the schemas in `../schema/` and the
registries they validate, (2) [core.md](core.md), (3)
[driver-profile.md](driver-profile.md), (4) chapters 01 to 10, each tagged *core* or
*optional profile* ([profiles.md](profiles.md) §2), (5) the appendices, (6)
[00-architecture.md](00-architecture.md), which is informative and wins nothing. The
editors MUST NOT accept a change that makes a lower level contradict a higher one,
and where two levels disagree the higher wins until an erratum or an RFC lands
([README](README.md) §1).

---

## 2. The RFC process

### 2.1 Stages

| Stage | Entry | Exit | Timebox (target) |
|---|---|---|---|
| **Proposal** | Public issue describing the problem, use cases and affected requirements. | An editor shepherds it; template completed. | 4 weeks of discussion |
| **Draft** | Pull request adding/modifying documents, schemas, catalogue and tests. | Editors agree the draft is complete and testable. | 4 weeks |
| **Review** | Public comment period; implementer review; conformance-suite prototype. | All blocking comments resolved; at least one independent implementation reports it can implement the change. | 4 weeks |
| **Accepted** | Decision record merged; requirement ids allocated. | Implementation in the reference SDK and suite. | — |
| **Released** | Version bumped; changelog published. | — | At the next MINOR/MAJOR window |

**GOV-006.** An RFC MUST include: problem statement, use cases, normative text
(using RFC 2119 keywords), requirement ids added/changed/removed, schema or
catalogue changes with validation, conformance tests, compatibility and migration
notes, and security/safety considerations. A draft without tests is not reviewable
and MUST NOT be accepted for a runtime behaviour.

**GOV-007.** An RFC that changes a requirement MUST also change the conformance
suite in the same release cycle. An RFC that adds a test id MUST add it to the
suite before the version is released; an RFC that changes an assertion MUST retire
the old id and introduce a new one ([MHS-001](01-conformance.md) CON-013).

**GOV-008.** Normative text MUST be testable ([GOV-002](#9-editorial-rules)
below), unless it is explicitly a process requirement marked *(process)*.

### 2.2 Document changes

**GOV-009.** Every document in the set carries a status line and is edited only
through the RFC process. The generated artifacts
([`capabilities.json`](capabilities.json), [MHS-A](appendix-a-capabilities.md))
are regenerated, never hand-edited; CI MUST fail on drift
([MHS-003](03-capability-registry.md) CAP-043).

**GOV-010.** An **erratum** is a change that fixes a typo, a broken link, a
formatting defect or a contradiction that can be resolved without changing any
requirement's observable behaviour. Errata are allowed as PATCH releases, are
recorded in the changelog, and MUST NOT be used to "clarify" a requirement in a way
that changes a test's expected outcome. Anything that changes behaviour is an RFC.

**GOV-011.** Conflicting text is a defect. If two documents disagree, the reporter
files an erratum that changes the lower-precedence document to match the higher
one (GOV-005); if the higher document is itself inconsistent, the fix is an RFC
that amends it.

---

## 3. Versioning

### 3.1 The version identifiers

| Artifact | Identifier | Policy |
|---|---|---|
| Protocol | `mhs_version` (`MAJOR.MINOR`), `1.0` in 0.9: wire revision 1 | §3.2. |
| OpenMHS specification | `spec_version` (`MAJOR.MINOR`), `0.9`; the document set is the development draft `0.9-draft` | §3.2 and §3.6. |
| JSON Schemas | `$id` URL with a versioned path (`https://mhs.openai4s.org/schema/0.9/…`, a placeholder base); schemas are additive within a MINOR | §3.3. |
| Capability classes | `capability_id` contains class `v<MAJOR>`; MINOR changes are registry metadata | [MHS-003](03-capability-registry.md) §2. |
| Adapter format | `mhs_adapter` (`1.0`) | MINOR additive; MAJOR incompatible. |
| Conformance suite | `suite_version` (semver), coupled to protocol MAJOR | §3.4. |
| Capability catalogue | `mhs_capabilities` (`1.0`) | Regenerated; version bump rules in §3.5. |
| Registry | `registry_version` and `generated_at` | [MHS-007](07-registry.md) §7. |
| SDK | distribution `openmhs`, Python `__version__` (`0.9.0.dev0`) | Independent release cadence; MUST declare supported protocol versions (`hello.implementation`, `hello.spec_version`). |
| Driver API | `mhs.driver` | Frozen after the pilot (additive changes only); [driver-profile.md](driver-profile.md). |

### 3.2 Protocol MAJOR / MINOR / PATCH

**GOV-020.** A **MAJOR** version change is REQUIRED when: a method is removed or
renamed; a parameter or result field is removed or changes type; an error code
changes meaning or is removed; a required manifest field is added or removed; the
meaning of `mode`, receipt status or evidence chain changes; or negotiation with
the previous MAJOR is impossible. Major versions MAY coexist on one endpoint only
through separate paths/transports; a single connection uses one version.

**GOV-021.** A **MINOR** version change is REQUIRED for additive, compatible
changes: a new OPTIONAL parameter, a new result field, a new OPTIONAL manifest
field, a new method, a new error code, a new capability class, a new transport
feature. A client that does not understand a MINOR addition MUST ignore it
(unknown fields in responses MUST be tolerated), and a server MUST NOT require a
new OPTIONAL field.

**GOV-022.** A **PATCH** version fixes errors without changing requirements,
schemas' semantics or conformance expectations. Patch releases MUST be
implementable by any already-conformant implementation without code change.

**GOV-023.** Version negotiation is `mhs.hello` ([MHS-002](02-wire-protocol.md)
§2). A server MUST select the highest mutual MAJOR.MINOR and MUST reject a MAJOR
mismatch (fail closed). A server MUST NOT accept a MINOR it did not advertise.

### 3.3 Schema versioning

**GOV-024.** Schemas are versioned by the document set: from 1.0 the schemas of a
MAJOR version are frozen at their published `$id` URLs for the life of that MAJOR
version. A MINOR release MAY add schemas or OPTIONAL fields but MUST NOT remove or
retype fields. A breaking schema change is a MAJOR release with new `$id` paths
(for example `/schema/2/…`). The 0.9 schemas live under the placeholder base
`https://mhs.openai4s.org/schema/0.9/`; documents written with the legacy prefix of
earlier drafts are accepted for reading only, until 0.10, and are never written.

**GOV-025.** A schema change MUST be validated against every example in
[`../schema/examples/`](../schema/examples/) and against the registry records in
CI: the documents in `examples/*.json` and `examples/valid/` MUST validate, and the
documents in `examples/invalid/` MUST fail exactly as
`examples/invalid/expected-failures.json` lists. An example or record that does not
behave so blocks the release.

### 3.4 Conformance suite coupling

**GOV-026.** A suite MAJOR version tests one protocol MAJOR version. A suite MINOR
version adds tests for new requirements and MUST keep existing test ids and their
assertions. A suite PATCH version fixes test bugs.

**GOV-027.** A report produced by a suite whose MAJOR is older than the current
protocol MAJOR MUST NOT be accepted for a current claim; re-testing is the only
path. Reports from an older suite MINOR/PATCH remain valid evidence of the
requirements they tested.

### 3.5 Capability catalogue versioning

**GOV-028.** Adding a class is a MINOR change to `mhs_capabilities`; changing a
class's MAJOR is a new class id; removing a class requires the deprecation window
(§5). The catalogue version is independent of the protocol MINOR but MUST be
regenerated and re-digested with every change
([MHS-003](03-capability-registry.md) CAP-043). The `since` member of a class and
of an error code is the OpenMHS specification release (`MAJOR.MINOR.PATCH` of
`spec_version`) that introduced it, not the wire or registry revision.

### 3.6 Versioning of the 0.9 draft

OpenMHS 0.9 is a development draft, named `0.9-draft`: the specification line is
`spec_version` `0.9`, the SDK is `0.9.0.dev0`, and the wire revision stays `mhs_version`
`1.0`, so that existing endpoints, clients and reports interoperate. The Driver API
(`mhs.driver`) is frozen once the pilot of the handoff kit has run, and only additive
changes follow. The compatibility mode of the endpoint constructor
([core.md](core.md) CORE-160) changes to strict by default after the pilot; that flip
is recorded in the changelog as a behaviour change. The version numbers of the
project are defined once, in the identifier module of the SDK, and every other file
imports or regenerates them.

---

## 4. Capability registry governance

**GOV-030.** Core classes (namespace `cap.*`) are owned by the editors (The OpenMHS Authors).
Anyone MAY propose a class. The proposal MUST include: the resource kinds, the
verb, closed input/output JSON Schemas with units, semantics (summary, tags,
effects, hazards, preconditions, postconditions, determinism), a risk class with
reasoning, safety limits, a binding example from a real device, and at least one
conformance test. A class without a real implementation is `experimental`.

**GOV-031.** A proposed class MUST be rejected if it duplicates an existing class's
physical meaning, if its schema is not closed, if it has no units, or if it encodes
a vendor product model rather than a class of physical action. The review checklist
is derived from [MHS-003](03-capability-registry.md) CAP-008 … CAP-021.

**GOV-032.** Extension classes (`cap.x.*`) are owned by their publishers and
registered in the registry. They follow the same schema and safety rules; the
editors review only for collisions and core-adjacent semantics
([MHS-003](03-capability-registry.md) §8).

**GOV-033.** The registry of classes MUST be publicly mirrored as
[`capabilities.json`](capabilities.json) with a digest; a registry claim or a device
manifest that references an unknown class MUST fail validation rather than be
accepted on the producer's word.

**GOV-034.** Naming: core class paths use the physical domain (`world`, `motion`,
`manipulation`, `sensing`, `fluid`, `sample`, `imaging`, `optics`, `measure`,
`thermal`, `actuation`, `compute`, `process`, `device`) and a verb-like action
name. Vendor names, product names and acronyms MUST NOT appear in core class ids.

---

## 5. Deprecation windows

**GOV-040.** Deprecation is announced in the document set, the schema comments and
the registry, with a replacement (if any), a rationale and a removal date. The
minimum windows are:

| Artifact | Minimum window after deprecation | Notes |
|---|---|---|
| Capability class | 12 months, and not before two protocol MINOR releases | [MHS-003](03-capability-registry.md) CAP-040. |
| Protocol method or parameter | 12 months | Removal only in a MAJOR release. |
| Manifest field | 12 months | Removal only in a MAJOR release. |
| Error code | 12 months | Code may be retired but must not be reused with another meaning. |
| Adapter manifest format | 6 months | Adapters are regenerated from the registry pipeline. |
| Conformance test id | Not removed while any published claim names it | Retirement only with report re-issue. |
| Transport binding | 12 months | A MUST binding cannot be deprecated without a replacement MUST binding. |
| Registry record field | 12 months | Shards are immutable; deprecation is an index-level annotation. |

**GOV-041.** During the window, implementations MUST keep accepting the deprecated
form and SHOULD emit a warning (`warn` in a report, a log entry or a
`hello.features` marker). The warning MUST NOT be an error that breaks existing
clients.

**GOV-042.** A deprecation MAY be shortened only for a security or safety defect,
with a published rationale and a migration path; shortening still requires an RFC
and MUST be recorded as an exception in the changelog.

**GOV-043.** Removal of a class or field while a conformance claim at CL2+ names it
is prohibited ([MHS-003](03-capability-registry.md) CAP-042); the registry MUST
block a core release that would do so.

---

## 6. Security and safety defect handling

**GOV-050.** The project MUST publish a security contact and a machine-readable
security policy (for example `SECURITY.md` and a `/.well-known/security.txt` on the
project site). Reports MUST be acknowledged within 5 business days.

**GOV-051.** Reports are handled privately for an embargo of up to **90 days** from
acknowledgement, extended only by agreement with the reporter. The fix, an
advisory and a CVE (when applicable) are published together at the end of the
embargo. A report that a deployed system is exposing hardware to harm MAY shorten
the embargo and trigger an out-of-band advisory.

**GOV-052.** Safety defects — an endpoint that claims a physical protection it does
not provide, a false `MHS.SAFETY.NOT_CERTIFIED` omission, a false e-stop declaration,
a hidden fidelity gap that could mislead an operator — MUST be treated with the
same process as security defects and MUST result in a conformance-test addition so
the defect is detectable in future claims.

**GOV-053.** Advisories MUST name the affected MHS versions, the affected
requirement ids, the impact, the fixed version and the workaround. Downplaying or
silent fixes are prohibited; a fixed defect without an advisory is itself a
process defect.

**GOV-054.** The editors MUST maintain a public list of known conformance-test
limitations (what the suite does not test). That list is part of the standard: it
is the honest boundary of a claim ([MHS-001](01-conformance.md) §10).

---

## 7. Licensing and IPR

**GOV-060.** The normative document set (`MHS/spec/`, including this document and
the appendices) is licensed **CC-BY-4.0**. Reuse, translation and redistribution
are permitted with attribution to "OpenMHS 0.9 (independent draft), by The OpenMHS
Authors" and a link to the canonical source. Quotations of third-party material,
including the citations of Anthropic's public material in
[MHS-D](appendix-d-anthropic-mhs.md), are not licensed by this project.

**GOV-061.** Schemas, example documents, the reference SDK, the conformance suite
and all code in this repository are licensed **MIT**. The permissive licence is
intentional: implementers must be able to build MHS endpoints, bridges and hosts
without a royalty.

**GOV-062.** Registry data (`MHS/registry/`, published index and shards) is licensed
**CC-BY-4.0**, with the caveat that the upstream package metadata and licences
remain those of their owners. A registry record MUST NOT relicense upstream code.

**GOV-063.** Conformance reports and evidence bundles are owned by the subject and
the issuer. Publication in the registry grants consumers the right to verify,
quote and redistribute the report with attribution; it does not license the
device's design or the report's underlying data beyond that purpose.

**GOV-064.** Marks and badges: "OpenMHS", "MHS" and the conformance badge text of
[MHS-001](01-conformance.md) §8.3 MUST NOT be used to imply safety certification,
product approval, endorsement by Anthropic or any vendor, or anything beyond the
tested claim. The badge
MAY be used only with a link to the report and the issuer kind.

**GOV-065.** No contributor licence agreement is required for editorial comments;
code contributions use the repository's standard contribution process and the
MIT inbound licence. A contributor MUST disclose patents they know to be
essential; the editors will not accept a normative requirement known to be
encumbered without a royalty-free commitment.

### 7.1 Governance files

The repository root carries the files that make these rules concrete. They are not
part of the specification text, but a release that lacks one fails the release
checklist (§10):

| File | Purpose |
|---|---|
| `LICENSE`, `NOTICE` | MIT for code, schemas, examples, tests and tooling (GOV-061); the copyright holder named in `LICENSE` is PKU-YUAN-Lab. |
| `LICENSE-docs` | CC-BY-4.0 for the specification text and the registry data (GOV-060, GOV-062), with the carve-out for third-party quotations in appendix D. |
| `SECURITY.md` | The private reporting channel and the 90-day coordinated disclosure policy (GOV-050 to GOV-053); safety defects are handled like security defects. |
| `CODE_OF_CONDUCT.md` | Contributor Covenant 2.1. |
| `CONTRIBUTING.md` | The per-repository driver checklist, identical to the acceptance gate and the pull-request rules of [driver-profile.md](driver-profile.md) (one driver directory per pull request; CI re-runs the gate; a driver pull request never edits the SDK), and the rules for changes to the SDK, the spec, the schemas and the registry. |
| `CHANGELOG.md` | The audit trail of GOV-086, compiled from the per-work-package fragments in `MHS/changes/`. |

---

## 8. Adoption rings and evidence language

**GOV-070.** The registry's coverage language MUST distinguish **declared**,
**packaged**, **runnable**, **conformant** and **certified** ([MHS-006](06-adapters.md)
§10) and MUST NOT describe an adapter as "supported" without a demonstrated
evidence state ([MHS-007](07-registry.md) REG-008).

**GOV-071.** The adoption rings of [MHS-007](07-registry.md) §3 (the `ring` field:
Ring 0 runtime-verified, Ring 1 agent-reviewed manifests, Ring 2 static manifests,
Ring 3 family recipes only) MUST be recorded for every package record, and the site
MUST render them.

**GOV-072.** Coverage statistics MUST include the honest negatives: packages
without clones, packages whose licence blocks adaptation, packages whose entry
points could not be found. A coverage report that only counts successes is
misleading and MUST be rejected by the editors.

---

## 9. Editorial rules

**GOV-080.** Normative text uses RFC 2119/8174 keywords in uppercase. Informative
text MUST NOT use them; it is marked "informative" at section level and MAY use
"should" in lowercase prose only if the sentence is clearly explanatory.

**GOV-081.** Requirements are numbered `AREA-NNN`, stable forever, one observable
behaviour per requirement, and each is traceable to a conformance test or marked
*(process)*. Renumbering is prohibited; retirement of an id is allowed only with
a changelog entry and a reason.

**GOV-082.** Cross-references use relative Markdown links for documents
(`02-wire-protocol.md`) and relative paths for schemas (`../schema/…`). External
URLs are citations, never requirements. A requirement MUST be understandable
without fetching an external page.

**GOV-083.** Examples MUST validate against the schemas they claim to follow, and
abbreviated examples MUST be labelled "abridged". Placeholder digests MUST be
obviously placeholders (`sha256:000…`) and MUST NOT be presented as real evidence.

**GOV-084.** Consistency: identifiers keep the names fixed in
[the document-set README](README.md) §6; field names match the schemas; the same
concept has the same name in prose, wire, schemas and code. A new name for an
existing concept is an erratum at least.

**GOV-085.** Generated files MUST be marked as generated, MUST be regenerated by a
committed generator, and MUST be checked in CI. Hand edits to generated files are
prohibited.

**GOV-086.** The changelog of the document set MUST list, for every release: the
version, the date, the RFCs included, the requirement ids added/changed/removed,
the schema and catalogue digests, and the suite version. The changelog is the
audit trail for claims ([MHS-001](01-conformance.md) CON-041).

**GOV-087.** Every document in the set MUST state its normative base (the Core
section, schema or chapter it expands) and its layer ([profiles.md](profiles.md) §2),
and MUST NOT silently duplicate a requirement defined elsewhere; it
cross-references instead. Duplicated prose drifts and is
the most common source of contradictions in standards.

---

## 10. Release checklist

Before a release, the editors MUST confirm:

1. every normative document validates against the style rules of §9;
2. [`capabilities.json`](capabilities.json) and [MHS-A](appendix-a-capabilities.md)
   are regenerated and identical to generator output;
3. every example in `MHS/schema/examples/` behaves as GOV-025 says (`examples/*.json` and `examples/valid/` validate, `examples/invalid/` fail as listed in `expected-failures.json`);
4. the conformance suite passes against the reference endpoints at their claimed
   levels, and the produced reports validate against the report schema;
5. the registry validates every record and manifest and publishes a reproducible
   `index_digest`;
6. the changelog names RFCs, requirement ids, suite version and digests;
7. breaking changes are in a MAJOR release and the migration guide is written;
8. security advisories and known-limitation lists are current;
9. the website and docs cite the released version, not "latest";
10. `python3 MHS/sdk/tools/spec_doctest.py MHS/spec` passes (every runnable code
    block runs against the SDK and the identifier lint is clean) and
    `python3 MHS/sdk/tools/build_applicability.py --check` and
    `python3 MHS/sdk/tools/gen_appendices.py --check` report no drift.

**GOV-090.** A release that fails any checklist item MUST NOT be published; a
release candidate MAY be published with the failing items listed in `limitations`,
clearly marked as a draft.

---

## 11. Requirements list (this document)

These are **process** requirements. They are verified editorially (release
checklist, CI, review) rather than by the runtime conformance suite.

**GOV-001** Open maintainers (The OpenMHS Authors); no certification body; independence.
**GOV-002** No single vendor controls the text; extensions live in extension namespaces.
**GOV-003** Decisions are recorded in public decision records.
**GOV-004** Appeals; safety-related rejections may be escalated.
**GOV-005** Order of precedence of the document set.
**GOV-006** RFCs contain problem, text, ids, tests, compatibility, security.
**GOV-007** Requirement changes update the suite in the same cycle.
**GOV-008** Normative text is testable or marked process.
**GOV-009** Generated artifacts are regenerated, never hand-edited.
**GOV-010** Errata fix defects without changing observable behaviour.
**GOV-011** Contradictions are defects resolved by the order of precedence.
**GOV-020** MAJOR change triggers.
**GOV-021** MINOR additive changes and unknown-field tolerance.
**GOV-022** PATCH does not change requirements.
**GOV-023** Negotiation rules; no silent MINOR acceptance.
**GOV-024** Schemas frozen per MAJOR; breaking changes use new `$id` paths.
**GOV-025** Schema changes validate examples and records in CI.
**GOV-026** Suite MAJOR ↔ protocol MAJOR coupling.
**GOV-027** Old-suite reports invalid for a new protocol MAJOR.
**GOV-028** Catalogue versioning and regeneration.
**GOV-030** Core class proposal requirements.
**GOV-031** Rejection criteria for classes.
**GOV-032** Extension class ownership and review scope.
**GOV-033** Public class catalogue mirror with digest.
**GOV-034** Core naming rules.
**GOV-040** Minimum deprecation windows.
**GOV-041** Deprecated forms keep working with warnings.
**GOV-042** Shortened deprecation only for security/safety, by RFC.
**GOV-043** No removal while claims name the class/field.
**GOV-050** Security contact, 5-day acknowledgement.
**GOV-051** 90-day embargo; coordinated advisory.
**GOV-052** Safety defects same process; add a test.
**GOV-053** Advisory content; no silent fixes.
**GOV-054** Public known-limitations list.
**GOV-060** Spec text CC-BY-4.0.
**GOV-061** Code and schemas MIT; permissive, royalty-free.
**GOV-062** Registry data CC-BY-4.0; upstream licences untouched.
**GOV-063** Report/evidence ownership and licence.
**GOV-064** Mark and badge usage limits.
**GOV-065** Patent disclosure; no knowingly encumbered requirement.
**GOV-070** Evidence-state language.
**GOV-071** Adoption rings recorded.
**GOV-072** Honest negatives in coverage.
**GOV-080** RFC 2119 usage and informative marking.
**GOV-081** Stable requirement ids, one behaviour each.
**GOV-082** Relative cross-references.
**GOV-083** Examples validate or are labelled.
**GOV-084** Identifier consistency.
**GOV-085** Generated files marked and checked.
**GOV-086** Changelog content.
**GOV-087** Documents state their normative base; no duplication.
**GOV-090** Release checklist is blocking.

---

## 12. Informative: how to contribute in one page

This section is informative.

1. **Read** [core.md](core.md) and the chapter you are changing. If the change touches the
   object model, wire or safety semantics, read the relevant schema too.
2. **Open an issue** describing the physical problem, not the API shape you
   prefer. Include a real device or simulator that would benefit.
3. **Draft an RFC** using the template in §2.1: requirement ids, normative text,
   schema diff, tests, compatibility, security/safety.
4. **Implement it** in a fork: the reference SDK, a reference endpoint and the
   conformance suite are small; an implementation is the strongest review.
5. **Review others**' RFCs; an independent implementation report is required before
   a runtime behaviour can be accepted.
6. **Never edit generated files**; run the generator and include its output.
7. **Report defects privately** if they are security or safety relevant (§6);
   everything else is a public issue.
