# MHS-007 — The Registry: Records, Federation, Trust and Search

| Field | Value |
|---|---|
| Document | MHS-007 (normative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | optional profile: Registry ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §9 (discovery is not trust); overview in [00-architecture.md](00-architecture.md) §8 and §13 (informative) |
| Data contracts | [`registry-record.schema.json`](../schema/registry-record.schema.json), [`defs.schema.json`](../schema/defs.schema.json) `trust` |

The registry is a static, signed, searchable index of MHS-capable packages,
devices, adapters and conformance claims. It is a **catalogue, not a control
plane**: it never proxies commands, never stores device state, and never
authenticates devices. It details [core.md](core.md) §9 and follows
from axiom D10 (a broker is a single point of failure and a privacy hazard; static
JSON can be mirrored, signed and deployed on air-gapped networks).

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. What the registry is for

1. **Discovery for humans**: find the adapter for a repository or a device model.
2. **Discovery for hosts**: find endpoints and adapters for a capability, mode or
   vendor, with the trust level attached.
3. **Evidence anchor**: make conformance claims independently checkable by
   binding a claim to a report digest and an issuer key.
4. **Coverage accounting**: state honestly which repositories are integrated to
   which state — declared, packaged, runnable, conformant, certified — and what
   the next action is.

**REG-001.** A registry MUST NOT be required for an MHS endpoint to operate. An
endpoint that cannot start without the registry is non-conformant; the registry is
an index of what exists, not a dependency of the protocol.

**REG-002.** A registry MUST NOT expose device state, telemetry, sessions,
receipts or approvals. Those belong to endpoints and evidence bundles; the
registry holds only public catalogue metadata ([00-architecture.md](00-architecture.md) §15, informative).

---

## 2. Record types

The registry is a set of **records**. Each record has a `record_type`
discriminator. OpenMHS 0.9 defines five record types. Only the `package` record has a
published JSON Schema ([`registry-record.schema.json`](../schema/registry-record.schema.json));
the other shapes are normative in this document and will be schematised in a
later MINOR revision without changing field names.

| `record_type` | One record per | Schema | Purpose |
|---|---|---|---|
| `package` | repository / package | [`registry-record.schema.json`](../schema/registry-record.schema.json) | The primary coverage record: what the repo is, which adapter family, tier, ring, evidence, next action. |
| `device` | device model/type | §4.2 | Vendor/model capabilities, manifests, known limits, firmware constraints. |
| `adapter` | published adapter | §4.3 | Adapter metadata plus where to get it; joins package to devices. |
| `claim` | published conformance claim | §4.4 | Profile, level, suite version, report digest, issuer, trust. |
| `registry` | registry deployment | §4.5 | Registry identity, keys, shards, digests, federation peers. |

**REG-003.** Every record MUST have `record_type`, a stable `id`, a `registry_id`
of the publishing registry, `updated_at`, and a `trust` value from
[`defs.schema.json`](../schema/defs.schema.json). Unknown fields MUST be rejected
by validators that have a schema; for schemaless types, validators MUST reject
fields outside the type's declared set.

**REG-003a.** For a `package` record, `id` MUST equal `package_id` and
`registry_id` MUST identify the publishing registry: a DNS name, or a single
lowercase label ending in `-registry` (the reference registry uses the stable
identifier `openmhs-registry`). The envelope is part of
[`registry-record.schema.json`](../schema/registry-record.schema.json), so a
record without either field is invalid.

**REG-003a.1.** [`registry-record.schema.json`](../schema/registry-record.schema.json)
validates any RFC 1123 DNS name in `registry_id` and MUST NOT hard-code the
reference publisher. A deployment MAY pin the publisher it expects in
deployment-local validation — the reference corpus does so in
`MHS/registry/validate.py` (override with `$MHS_REGISTRY_ID`) — and a record
whose `registry_id` differs from that local policy is invalid for that
deployment only, not against the shared schema. This is what makes REG-034 (no
privileged central registry) and REG-035 (retain the originating
`registry_id`/`trust`) implementable for independent publishers.

**REG-004.** Identifier stability: `package_id` MUST be
`gh.<owner>/<repo>` (lowercase); `device` ids MUST be
`mhsdevice:<vendor>:<model>`; `adapter` ids MUST reuse `adapter_id`; `claim` ids
MUST be `<subject_id>@<report_digest>`; `registry` ids MUST be a DNS name or
`mhs://` endpoint id. Identifiers MUST NOT be reused for different subjects.

**REG-005.** A registry MUST publish records as JSON Lines shards, sharded by the
first character of the record id (`0-9`, `a`–`z`, `_`), one shard file per
character per record type. A registry MAY expose a single `index.json` in
addition for convenience. Both MUST carry the same records.

---

## 3. Package records

A package record is the primary coverage artifact. Its schema is
[`registry-record.schema.json`](../schema/registry-record.schema.json); the table
below explains the fields that need editorial rules beyond the schema.

| Field | Rule |
|---|---|
| `package_id` | `gh.<owner>/<repo>`, lowercase; must match the record's `repo_url`. |
| `track` | `labs`, `robots`, `shared` — which corpus the package belongs to. |
| `family`/`families` | MHS adapter families, most specific first; must be consistent with `adapter.bridge`. |
| `tier` | A/B/C/D/X per [MHS-006](06-adapters.md) §9; D/X records MUST NOT claim capabilities. |
| `ring` | 0 runtime-verified, 1 agent-reviewed manifest, 2 static manifest, 3 recipe only ([00-architecture.md](00-architecture.md) §13, informative). |
| `modes` | Declared modes of the devices the package can expose; a package that only simulates MUST NOT list `hardware`. |
| `interfaces` | Detected integration interfaces (ROS 2, PyVISA, Gymnasium, MCP, HTTP, …). Detection evidence belongs in `evidence`. |
| `license` | Upstream licence string as detected; `unknown` is allowed but MUST be explicit. |
| `adapter` | `{present, manifest_ref, state, bridge, entry_points[], shim_required}`; `manifest_ref` MUST resolve inside the registry. |
| `capabilities_offered` | Classes the package can plausibly expose; empty for tier D/X. |
| `conformance` | Claim pointer; `issuer_kind: "none"` when no claim exists. |
| `integration` | `{recipe, effort, estimated_days, blockers[], next_action, scenario_required}`. |
| `evidence` | `{state, read_by, files_read, notes, verified_at, provenance_refs[]}`. |
| `trust` | Trust of this record, not of the package's code. |

**REG-006.** `evidence.state` values are `declared | static_scan | agent_read |
runtime_tested`; they MUST reflect the strongest evidence actually recorded. A
record with `evidence.state: "runtime_tested"` MUST cite a conformance report or
runtime log in `provenance_refs`.

**REG-007.** `integration.next_action` MUST be actionable by a maintainer or an
integrator ("add mhs/bindings.json mapping cap.measure.voltage.v1 to
`DMM.read_voltage`; run conformance CL2") — not "investigate". `blockers[]` MUST
name concrete blockers (missing licence, hardware required, no entry point).

**REG-008.** A package MUST NOT be described as "supported" or "MHS-compatible"
without an `adapter.state` of at least `runnable` and an evidence record. The
registry MUST render tier/ring/evidence next to every package name.

**REG-009.** The registry MUST publish coverage statistics (by track, family, tier,
ring, mode, licence) and MUST include rows without local clones or without
catalogue entries in its coverage report rather than silently dropping them.

---

## 4. Other record types

### 4.1 Common envelope

All record types share: `record_type`, `id`, `registry_id`, `title`, `updated_at`,
`trust`, `signatures[]?`, `x-vendor?`.

### 4.2 Device record

```json
{
  "record_type": "device",
  "id": "mhsdevice:acme:conveyor-500",
  "registry_id": "openmhs-registry",
  "vendor": {"name": "Acme", "url": "https://acme.example"},
  "model": "conveyor-500",
  "firmware": {"min": "2.3.0", "max": "2.9.x", "constraints": ["no fieldbus mode"]},
  "capabilities": ["cap.world.step.v1", "cap.actuation.valve.v1"],
  "manifests": ["mhs+registry://…/devices/acme__conveyor-500.json"],
  "known_limits": {"speed_mm_s": {"max": 800}, "temperature_Cel": {"min": 5, "max": 40}},
  "safety": {"risk_class": "R1", "estop": "hardware", "requires_permit": ["cap.actuation.*"]},
  "updated_at": "2026-10-20T07:00:00Z",
  "trust": "manufacturer_signed",
  "signatures": [{"key_id": "acme-2026", "jws": "…"}]
}
```

**REG-010.** A device record MUST NOT include device state, serial numbers of
installed units, credentials or customer identifiers. Limits are catalogue
metadata; a manifest published by the device itself is authoritative at runtime,
and the record MUST say so.

### 4.3 Adapter record

```json
{
  "record_type": "adapter",
  "id": "org.example.robosuite-lift",
  "registry_id": "openmhs-registry",
  "package_id": "gh.arise-initiative/robosuite",
  "adapter_url": "mhs+registry://…/adapters/gh.arise-initiative__robosuite__lift.json",
  "manifest_digest": "sha256:…",
  "family": "mujoco",
  "devices": ["mhsdevice:acme:conveyor-500"],
  "states_supported": ["simulated"],
  "evidence_state": "runnable",
  "license": "MIT",
  "updated_at": "2026-10-20T07:00:00Z",
  "trust": "self_signed"
}
```

**REG-011.** `manifest_digest` MUST be the JCS digest of the adapter manifest the
record describes; a host that fetches a manifest MUST verify it against the record
before using it.

### 4.4 Claim record

```json
{
  "record_type": "claim",
  "id": "mhs://localhost:7400@sha256:9f2c…",
  "registry_id": "openmhs-registry",
  "subject": {"kind": "endpoint", "id": "mhs://localhost:7400", "profile": "MHS-Sim"},
  "level": "CL4",
  "suite_version": "1.0.0",
  "mhs_version": "1.0",
  "report_digest": "sha256:9f2c…",
  "report_url": "mhs+registry://…/reports/mhs-reference-conveyor.json",
  "issued_at": "2026-10-20T07:40:00Z",
  "issuer": {"kind": "self", "name": "MHS reference SDK", "key_id": null},
  "limitations": ["endpoint as configured on 2026-10-20"],
  "updated_at": "2026-10-20T07:40:00Z",
  "trust": "self_signed"
}
```

**REG-012.** A claim record MUST NOT exist without a retrievable report whose
JCS digest equals `report_digest` and whose contents match the claim (same
subject, profile, level, issuer). The registry MUST verify this at ingest and
MUST reject inconsistent claims (`MHS.REGISTRY.RECORD_INVALID`).

**REG-013.** A claim record with `issuer.kind: "verified"` MUST carry a valid
signature over the report digest and MUST reference an issuer key that was valid
at `issued_at`. An unverifiable claim MUST be downgraded to `self` trust and
flagged, not deleted.

**REG-014.** Claims MUST be marked stale per [MHS-001](01-conformance.md) §8.2
(18 months) in search results and in the record's rendered status; staleness is a
retrieval-time judgement, not a record edit.

### 4.5 Registry record

```json
{
  "record_type": "registry",
  "id": "openmhs-registry",
  "url": "https://registry.openmhs.invalid",
  "mhs_version": "1.0",
  "generated_at": "2026-10-20T07:00:00Z",
  "shards": [{"record_type": "package", "prefix": "a", "digest": "sha256:…", "count": 143}],
  "index_digest": "sha256:…",
  "keys": [{"key_id": "registry-2026", "alg": "EdDSA", "public_key": "…", "valid_from": "2026-01-01T00:00:00Z", "revoked_at": null}],
  "federation": [{"registry_id": "registry.example.org", "url": "https://registry.example.org", "trust": "registry_verified"}],
  "updated_at": "2026-10-20T07:00:00Z",
  "trust": "registry_verified"
}
```

**REG-015.** A registry MUST publish its own record, including key material and
shard digests, and MUST sign it with a key it owns.

---

## 5. Trust and signatures

### 5.1 Levels

Trust values are defined by [`defs.schema.json`](../schema/defs.schema.json):

| Value | Meaning | Host rule |
|---|---|---|
| `unsigned` | No signature; integrity unknown. | Display as unsigned; never elevate privilege or auto-install. |
| `self_signed` | Signed by the publisher's own key. | Display as self-signed; may install after operator confirmation. |
| `registry_verified` | Signature checked by the hosting registry against a key it recognises. | Display verified; still not a safety endorsement. |
| `manufacturer_signed` | Signed by a key bound to the vendor identity. | Display with manufacturer; still not a safety endorsement. |

**REG-016.** Hosts MUST NOT elevate privileges based on an unsigned claim and MUST
show the trust level next to any capability description
([00-architecture.md](00-architecture.md) §8.3, informative). Install/allow-list decisions MUST be the
operator's; the registry MUST NOT push.

### 5.2 Signing

**REG-017.** Signatures are detached JWS compact serialisations over the JCS
digest of the record body (the record without `signatures`). Algorithms are
`EdDSA` or `ES256`. The `key_id` MUST resolve to a key in a registry or a
well-known key document.

**REG-018.** A key MUST be revoked by publishing `revoked_at` in the registry
record. Records signed after revocation or by a revoked key MUST be treated as
unsigned. Revocation MUST NOT rewrite history; the verification result at
`updated_at` is what is recorded.

**REG-019.** `registry_verified` means "this registry checked the signature against
a key it recognises", not "the content is true". `manufacturer_signed` requires the
registry to have bound the key to the vendor (domain-verified or contractually);
the registry MUST document how binding was established.

**REG-020.** A conformance claim's trust MUST NOT exceed the trust of the key that
signed the report. A self-signed report cannot become `registry_verified` without
the registry re-running or re-attesting at least the report digest and identity.

---

## 6. Search semantics

**REG-021.** Search MUST accept the query fields defined in
this section (search is a registry service, not an endpoint method, [MHS-002](02-wire-protocol.md) PROTO-039):
`capability`, `tags[]`, `mode`, `vendor`, `family`, `track`, `tier`, `ring`,
`license`, `text`, `trust`, `limit`, `cursor`.

**REG-022.** `capability` matching is exact on `capability_id`, or by class prefix
when the query ends in `.*` (for example `cap.fluid.*`). Version suffixes are
matched literally; `cap.fluid.*` does not imply `v2` matches `v1`.

**REG-023.** `tags` are ANDed; each tag is matched case-insensitively against the
record's tags as whole phrases (substring matches are allowed only when the query
tag ends with `*`). Empty tag list means "no tag filter".

**REG-024.** `text` is a case-insensitive search over `title`, `description`,
`owner`, `repo`, `tags` and device `vendor`/`model`; it MUST NOT search inside
manifests, receipts or linked code.

**REG-025.** Result ordering MUST be deterministic: (1) exact capability matches,
(2) number of matched tags, (3) tier rank A<B<C<D<X, (4) ring descending,
(5) `package_id` lexicographic. Ties MUST be broken by `package_id`, never by
insertion order or score drift.

**REG-026.** Pagination MUST use an opaque `cursor` derived from the last result's
sort key; `limit` defaults to 25 and MUST NOT exceed 200. Results MUST include
`total` (or `total_estimate` when the index is sharded and expensive to count) and
must be stable for a given `generated_at`.

**REG-027.** Local registry search latency bounds for a CL2+ registry are in
[MHS-001](01-conformance.md) §6.6: p50 ≤ 10 ms, p99 ≤ 100 ms on a local index. The
registry MUST report measured `took_ms` per query.

**REG-028.** Every search result MUST carry `trust`, `tier`, `ring`,
`evidence.state`, and, when present, `conformance{level, issuer_kind}` so a host
can filter without a second request.

---

## 7. Static deployment

**REG-029.** The canonical deployment is static files: shards (`.jsonl`),
`index.json`, `registry.json` (the registry record), a `keys/` directory with
public keys, and a `coverage.md`. Any static host, object store or CDN MAY serve
it; no server-side query API is required.

**REG-030.** `index.json` MUST contain `registry_version`, `generated_at`,
`stats`, `shards[]` (with digests and counts), and `records` summaries. Its
`index_digest` MUST be recomputable from the shard files by a verifier
([MHS-001](01-conformance.md) §3.5).

**REG-031.** Shards MUST be immutable once published: a regeneration writes new
shards (content-addressed or date-versioned) and a new `index.json`. Clients MUST
be able to detect a changed shard by digest.

**REG-032.** The registry MUST be usable offline: a consumer can mirror the
static bundle, verify `index_digest` and shard digests, and search locally. The
protocol MUST NOT require a network call to a registry authority.

**REG-033.** Caching: static files SHOULD be served with long cache lifetimes and
digest-based invalidation; the registry MUST publish `generated_at` so clients can
decide whether their copy is stale.

---

## 8. Federation

**REG-034.** Federation is peer-to-peer between static registries: a registry MAY
list peer registries in its `federation[]`, and a client MAY merge results from
several registries. There MUST be no privileged central registry.

**REG-035.** Merged results MUST retain the originating `registry_id` and the
trust as computed by that registry; a client MUST NOT upgrade trust because two
registries agree. Duplicate records (same `id`) MUST be merged only when their
body digests match; otherwise both MUST be shown with a conflict flag.

**REG-036.** A federation query MUST degrade gracefully: unreachable peers MUST
produce partial results with `peers_unavailable[]`, not an error, unless the client
asked for `require_all_peers: true`.

**REG-037.** Cross-registry claims are independent: registry A's verification of a
key does not make the same key trusted in registry B. Each registry MUST publish
its key acceptance policy.

---

## 9. Publishing flow

**REG-038.** Publishing a package record MUST follow this order:

1. **generate** the record from the scanner/adapter evidence (no hand-edited
   facts above the evidence state);
2. **validate** against [`registry-record.schema.json`](../schema/registry-record.schema.json),
   with adapter/device references resolving;
3. **attach evidence** (`evidence.state`, `read_by`, provenance refs);
4. **attach claims** only with a report whose digest matches;
5. **sign** with the publisher key;
6. **stage** the shard, then **publish** the new `index.json` and `registry.json`;
7. **announce** `generated_at` and `index_digest`.

**REG-039.** A record update MUST preserve the previous record's digest in the
registry's change log; deleting a record is a tombstone (`x-mhs-tombstone`) with a
reason and date, never a silent disappearance.

**REG-040.** The registry MUST expose, for every published claim, a stable URL to
the report and its digest; a claim whose report cannot be served is `stale` and
MUST be flagged.

---

## 10. Privacy rules

**PRIV-001.** (There is no separate privacy document; this section is normative.) Registry records MUST NOT
contain: device state, telemetry, receipt contents, session identifiers, principal
identifiers of real people, end-user customer names, network addresses beyond
public endpoints, credentials, unpublished protocols or sample identities.

**PRIV-002.** Package descriptions MUST be derived from public metadata (repo
description, docs) and MUST NOT quote private issue trackers, internal commits or
customer data.

**PRIV-003.** Maintainer names and contact addresses MAY appear only when they are
already published by the upstream project; the registry SHOULD link to the
upstream page instead of copying personal data.

**PRIV-004.** Endpoint ids in claim records MUST be public endpoint ids chosen by
the publisher; a private lab endpoint MUST be claimed through a redacted alias
(`mhs+registry://claims/<id>`) rather than the internal address.

**PRIV-005.** Take-down: a publisher MUST be able to request removal of its own
records. Removal MUST leave a tombstone without personal data and MUST NOT alter
other records' digests. Registries MUST document their take-down contact in the
registry record.

---

## 11. Requirements traceability

| Requirement | Suite/validation | Checks |
|---|---|---|
| REG-001 | REG-001 | Endpoint starts without registry access. |
| REG-002/PRIV-001 | REG-002 | Registry data contains no state/telemetry/secrets. |
| REG-003 | REG-003 | Every record has the common envelope. |
| REG-005 | REG-005 | Shards parse; single-character sharding correct. |
| REG-010 | REG-010 | Device records contain no state or serial numbers. |
| REG-012 | REG-012 | Bad claim/report digest rejected at ingest. |
| REG-015 | REG-015 | Registry self-record and keys present. |
| REG-021–028 | REG-021…REG-028 | Search semantics, ordering, pagination, latency, trust columns. |
| REG-030 | REG-030 | `index_digest` recomputes from shards. |
| REG-034–037 | REG-034…REG-037 | Federation merge, partial failure, trust retained. |
| REG-039/040 | REG-039 | Tombstones and report URLs present. |

Level assignment for these tests is in [MHS-001](01-conformance.md) §5.2. Error
codes used by registry ingestion and verification are in
[MHS-B](appendix-b-errors.md).
