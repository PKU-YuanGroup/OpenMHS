# OpenMHS 0.9 — specification set

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview. It defines an open, versioned, machine-checkable contract between agents that reason and equipment that acts: a short normative core, a driver profile for per-repository drivers, optional profiles, the chapters that detail them, and executable conformance. Nothing here is a safety certification or an approved standard; it is a development draft, and the schemas, SDK, conformance suite, registry and website in this repository are its executable evidence.

| Field | Value |
|---|---|
| Document set | OpenMHS 0.9 (development draft) |
| Specification version | `0.9` (`spec_version` in `mhs.hello` and in every generated file) |
| Wire revision | `mhs_version` `1.0` (the first wire revision; method prefix `mhs.*`, error prefix `MHS.*`) |
| Authority | the order of §1 |
| Normative core | [`core.md`](core.md), [`driver-profile.md`](driver-profile.md), [`profiles.md`](profiles.md) |
| Data schemas | [`../schema/`](../schema/): JSON Schema 2020-12 |
| Machine-readable capability catalogue | [`capabilities.json`](capabilities.json) |
| Machine-readable error registry | [`errors.json`](errors.json) |
| SDK contract | [`../sdk/INTERFACE.md`](../sdk/INTERFACE.md) (generated) |

The key words MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, MAY and OPTIONAL in the normative documents are to be interpreted as described in RFC 2119 and RFC 8174. They are used only in `core.md`, `driver-profile.md`, chapters 01 to 10 and the appendices that already use them. [`00-architecture.md`](00-architecture.md) is informative and contains none of them.

## 1. Precedence and reading order

When two documents disagree, the one higher in this list wins:

1. **The schemas** in [`../schema/`](../schema/) and the registries they validate ([`capabilities.json`](capabilities.json), [`errors.json`](errors.json)).
2. [**`core.md`**](core.md): the object model, the read, write and action primitives, the reference file, limits, the evaluation order and the safety duties of the core, receipts and long-running work, modes, discovery, the control surfaces, principals and arming, strict and compatibility mode, persistence.
3. [**`driver-profile.md`**](driver-profile.md): the per-repository driver package, the Driver API, the acceptance gate, provenance and review, fakes, the sandbox.
4. **Chapters 01 to 10**, each tagged *core* or *optional profile* in its header ([`profiles.md`](profiles.md) §2 lists the tags). They detail the Core and the profiles; a chapter that disagrees with `core.md` is in error.
5. **The appendices** A to D. A and B are generated from the JSON registries; C is informative; D is informative and the only place that cites Anthropic's preview.
6. [**`00-architecture.md`**](00-architecture.md): informative. It explains the design and the reasons for it, wins nothing and constrains nothing.

A conflict between two levels is a defect, not a choice: it is fixed by an erratum to the lower document ([MHS-010](10-governance.md) GOV-005, GOV-010, GOV-011). Where the specification and the reference SDK disagree, the SDK's tests describe the 0.9 behaviour and the disagreement is reported against whichever side is wrong; both are never left in place.

Then read by role:

| If you are… | Read, in order |
|---|---|
| Writing a driver for one upstream repository | [`driver-profile.md`](driver-profile.md), `../sdk/docs/driver-authoring.md`, [`core.md`](core.md) §2 to §6, [`06`](06-adapters.md) |
| Implementing an endpoint or a bridge | [`core.md`](core.md), [`02`](02-wire-protocol.md), [`03`](03-capability-registry.md), [`04`](04-safety.md), [`06`](06-adapters.md) |
| Writing a host or agent harness | [`core.md`](core.md) §10 and §11, [`09`](09-host-profile.md), [`08`](08-transports.md), [`01`](01-conformance.md) |
| Building a registry or the website | [`07`](07-registry.md), [`03`](03-capability-registry.md), [MHS-A](appendix-a-capabilities.md) |
| Reviewing safety claims | [`core.md`](core.md) §4 to §6, [`04`](04-safety.md), [`05`](05-fidelity.md), [`01`](01-conformance.md) §7 |
| Positioning against the Anthropic preview | [MHS-D](appendix-d-anthropic-mhs.md), [`00`](00-architecture.md) §1.4 |
| Citing or extending the standard | [`10`](10-governance.md), [`profiles.md`](profiles.md) |

[MHS-C](appendix-c-examples.md) holds end-to-end transcripts that run against the SDK: the fastest orientation.

## 2. Document status

| Doc | Title | Layer | Status |
|---|---|---|---|
| [`core.md`](core.md) | OpenMHS Core | core | Normative. |
| [`driver-profile.md`](driver-profile.md) | OpenMHS Driver Profile | driver profile | Normative. |
| [`profiles.md`](profiles.md) | OpenMHS Optional Profiles | index | Normative index. |
| [00](00-architecture.md) | Architecture overview | informative | Informative. |
| [01](01-conformance.md) | Conformance: levels, profiles, suite, reports | core | Normative. |
| [02](02-wire-protocol.md) | Wire protocol: methods, errors, receipts, operations, subscriptions | core | Normative. |
| [03](03-capability-registry.md) | Capability registry and core classes | core | Normative; §7 generated. |
| [04](04-safety.md) | Safety, permits, sessions, evidence, threat model | core | Normative. |
| [05](05-fidelity.md) | Modes, fidelity contract, determinism, replay | optional profile | Normative. |
| [06](06-adapters.md) | Adapters, bridges, mapping rules | driver profile companion | Normative. |
| [07](07-registry.md) | Registry records, federation, trust, search | optional profile | Normative. |
| [08](08-transports.md) | Transport bindings and the MCP projection | core | Normative. |
| [09](09-host-profile.md) | Host profile | optional profile | Normative; the OpenAI4S mapping is an informative annex. |
| [10](10-governance.md) | RFC process, versioning, deprecation, licensing | optional profile | Normative process. |
| [MHS-A](appendix-a-capabilities.md) | Core capability catalogue | appendix | Generated; normative content. |
| [MHS-B](appendix-b-errors.md) | Error code registry | appendix | Generated; the stable vocabulary, machine-readable in [`errors.json`](errors.json). |
| [MHS-C](appendix-c-examples.md) | End-to-end transcripts | appendix | Informative; never overrides a requirement. |
| [MHS-D](appendix-d-anthropic-mhs.md) | Relationship to the Anthropic research preview | appendix | Informative. |

## 3. Requirement identifiers

Requirements in the chapters are numbered `AREA-NNN` (for example `SAFE-012`, `PROTO-004`) and stay stable: they are never renumbered. The Core and the Driver Profile define their own rules as `CORE-nnn` (in `core.md`) and `DRV-nnn` (in `driver-profile.md`); each id is defined once, in one place, and a rule that restates an existing requirement cites its id instead of redefining it. A definition starts a paragraph, as `**SAFE-012.**` in a chapter and as `**CORE-012:**` or `**DRV-012:**` in the Core and the Driver Profile. A conformance test that is the canonical executable check for a requirement uses the same identifier as its test id; grouped or auxiliary tests use `T<AREA>-NNN` so they can never collide with a requirement id. Both forms match the report schema's test-id pattern `^[A-Z]+-[0-9]{3}$` ([`../schema/conformance-report.schema.json`](../schema/conformance-report.schema.json)), and the suite publishes a `traceability.json` that maps every test id to the requirement id(s) it checks ([MHS-001](01-conformance.md) §4). The areas are:

| Area | Document | Subject |
|---|---|---|
| `CORE` | [`core.md`](core.md) | The Core |
| `DRV` | [`driver-profile.md`](driver-profile.md) | The Driver Profile |
| `CON` | [01](01-conformance.md) | Conformance process, reports, claims |
| `PROTO` | [02](02-wire-protocol.md) | JSON-RPC framing, methods, deadlines, receipts |
| `SESS` | [02](02-wire-protocol.md), [04](04-safety.md) | Sessions, grants, TTL, principals |
| `CAP` | [03](03-capability-registry.md) | Capability classes, schemas, bindings, units |
| `SAFE` | [04](04-safety.md) | Envelope, interlocks, permits, e-stop, audit |
| `MODE` | [05](05-fidelity.md) | Mode declaration and mode mismatch |
| `FID` | [05](05-fidelity.md) | Fidelity contract, determinism, replay |
| `EVID` | [02](02-wire-protocol.md), [04](04-safety.md) | Evidence export and chain verification |
| `OP` | [02](02-wire-protocol.md) | Operations, idempotency, revisions, cancellation |
| `EVT` | [02](02-wire-protocol.md), [08](08-transports.md) | Subscriptions, sequencing, gaps, backpressure |
| `COMP` | [02](02-wire-protocol.md) | Compositions (reserved) |
| `TPT` | [08](08-transports.md) | Transport bindings and MCP projection |
| `ADPT` | [06](06-adapters.md) | Adapter manifests, bridges, mapping, packaging |
| `REG`, `PRIV` | [07](07-registry.md) | Registry records, federation, trust, search, privacy |
| `HOST` | [09](09-host-profile.md) | Host behaviour |
| `GOV` | [10](10-governance.md) | Process requirements (editorial, not runtime) |
| `ERR` | [MHS-B](appendix-b-errors.md) | The error vocabulary |

A requirement that cannot be checked by an automated test says so in its text and is marked *(process)*; it is verified editorially. Everything else is expected to appear in the suite and in a report. `python3 MHS/sdk/tools/spec_doctest.py MHS/spec` runs every runnable code block of this set against the SDK and lints the identifiers (one meaning per id, none defined twice, none referenced but undefined).

## 4. Versioning of the document set

The document set is versioned `0.9`, a development draft whose name stays `0.9-draft` until the pilot has frozen the Driver API. The specification version (`spec_version`, `0.9`) is the OpenMHS release; the wire revision (`mhs_version`, `1.0`) is the first revision of the JSON-RPC contract and is negotiated by `mhs.hello`; capability classes version independently inside their identifiers ([MHS-003](03-capability-registry.md) §2). The rules for changing each, and for a MAJOR, MINOR or PATCH release, are in [MHS-010](10-governance.md) §3. Generated files ([`capabilities.json`](capabilities.json), [MHS-A](appendix-a-capabilities.md), [MHS-B](appendix-b-errors.md), the conformance applicability inventory) are regenerated in the same change and checked by CI.

## 5. Where the executable parts live

| Artifact | Location |
|---|---|
| JSON Schemas (device, capability, adapter, bindings, receipt, reference, site limits, driver lock and result, check report, registry record, conformance report, endpoint descriptor, shared definitions) | [`../schema/`](../schema/) |
| Example documents: `examples/*.json` and `examples/valid/` validate against their schemas; `examples/invalid/` fail as `examples/invalid/expected-failures.json` lists | [`../schema/examples/`](../schema/examples/) |
| Reference SDK (client, server, bridges, drivers, reference endpoints, conformance suite, MCP projection, CLI, code files) and its guides | [`../sdk/`](../sdk/) |
| Driver packages and the four exemplars | [`../drivers/`](../drivers/) |
| The per-repository handoff kit | [`../handoff/`](../handoff/) |
| Registry (records, task cards, family recipes, index) | [`../registry/`](../registry/) |
| Static website and playground | [`../site/`](../site/) |
| Per-work-package change notes | [`../changes/`](../changes/) |

The repository-level [README](../README.md) covers how to run the reference endpoints and the conformance suite.

## 6. Editing rules and fixed names

The editorial rules are [MHS-010](10-governance.md) §9 (GOV-080 to GOV-087): RFC 2119 keywords only in normative text, stable requirement ids, relative cross-references, examples that validate or are labelled abridged, generated files that are never edited by hand, and documents that state their normative base and do not duplicate a requirement. Two rules come from the tools that read these files: a code fence has at most one word after the backticks (the form every Markdown reader treats alike), and a JSON example that must validate names its schema in the sentence directly above it ("... is valid against [`receipt.schema.json`](../schema/receipt.schema.json)"), which `spec_doctest.py` reads. A change to a normative statement goes through the RFC process of [MHS-010](10-governance.md) §2.

The protocol uses these identifier names everywhere, in prose, wire, schemas and code: `session_id`, `command_id`, `operation_id`, `receipt_id`, `permit_id`, `device_id`, `endpoint_id`, `resource_id`, `capability_id`, `adapter_id`, `bridge_id`, `registry_id`. A new identifier kind requires an RFC (GOV-084).
