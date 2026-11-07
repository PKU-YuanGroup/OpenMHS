#!/usr/bin/env python3
"""Regenerate appendices MHS-A and MHS-B from the normative JSON data.

* ``MHS/spec/appendix-a-capabilities.md`` is rendered from
  ``MHS/spec/capabilities.json`` (class tables, resource kinds, inventory).
* ``MHS/spec/appendix-b-errors.md`` is rendered from ``MHS/spec/errors.json``
  (area table, one registry table per area, the driver subset and the
  deprecated codes) around the fixed normative prose kept in this file.

The JSON files are the sources; edit them (or the prose below) and rerun:

    python3 MHS/sdk/tools/gen_appendices.py            # rewrite both appendices
    python3 MHS/sdk/tools/gen_appendices.py --check    # exit 1 if either is stale

Output is deterministic (no dates, stable ordering).  Exit codes: 0 ok,
1 stale (``--check``), 2 unreadable inputs.  Standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MHS_ROOT = HERE.parent.parent
SPEC = MHS_ROOT / "spec"
CAPABILITIES = SPEC / "capabilities.json"
ERRORS = SPEC / "errors.json"
APPENDIX_A = SPEC / "appendix-a-capabilities.md"
APPENDIX_B = SPEC / "appendix-b-errors.md"


def _cell(value: str) -> str:
    """Escape a value for a Markdown pipe-table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# MHS-A
# ---------------------------------------------------------------------------
def render_appendix_a(catalogue: dict) -> str:
    """Return appendix MHS-A for ``catalogue`` (capabilities.json)."""
    classes = catalogue["capabilities"]
    domains: list[str] = []
    for entry in classes:
        if entry["domain"] not in domains:
            domains.append(entry["domain"])
    per_domain = Counter(entry["domain"] for entry in classes)
    out: list[str] = []
    add = out.append
    add("# MHS-A — Core Capability Catalogue")
    add("")
    add("| Field | Value |")
    add("|---|---|")
    add("| Document | MHS-A (generated; informative in presentation, normative in content) |")
    add("| Generated from | [`capabilities.json`](capabilities.json) by `python3 MHS/sdk/tools/gen_appendices.py` — do not edit by hand |")
    add("| Layer | appendix of the core: the capability catalogue ([profiles.md](profiles.md) §2) |")
    add(f"| Classes | {len(classes)} |")
    add(f"| Specification | OpenMHS {catalogue.get('spec_version', '0.9')} (wire revision 1) |")
    add("")
    add("This appendix is a generated projection of [`capabilities.json`](capabilities.json).")
    add("The JSON file is the machine-readable registry source; this table is its reviewable")
    add("rendering. Chapter [MHS-003](03-capability-registry.md) §7 describes the catalogue; the")
    add("JSON carries the full input and output schemas, units, limits and one example input")
    add("per class. If this table and the JSON disagree, the JSON wins and this file MUST be")
    add("regenerated.")
    add("")
    add("Column meanings: **Class** — `capability_id`; **Verb** — `read` (never changes state or")
    add("the revision), `write` (sets named parameters) or `invoke` (an action); **Status** —")
    add("`stable`, `experimental` (binding requires `x-mhs-experimental`) or `deprecated` (still")
    add("valid; see the replacement below); **Profile** — `core`, or `sim` for Sim/Fidelity")
    add("profile classes that only simulated, hybrid or replay devices bind; **Resource kinds**")
    add("— resource `kind` values the class may bind to (`*`: any kind the device declares);")
    add("**Risk** — class-level risk floor (a binding MAY raise it, never lower it); **Since** —")
    add("the OpenMHS specification release (`spec_version`, as MAJOR.MINOR.PATCH) that introduced")
    add("the class in its current form, independent of the class MAJOR and of the wire revision.")
    add("Tags are the registry search keys. Fields marked `x-mhs-delta` in the JSON (a tolerance")
    add("or a rate in `K`, `K/min`) are temperature differences: conversions never apply the")
    add("Kelvin/Celsius offset to them.")
    add("")
    add("Distribution: " + ", ".join(f"{domain} {per_domain[domain]}" for domain in domains) + ".")
    for domain in domains:
        members = [entry for entry in classes if entry["domain"] == domain]
        noun = "class" if len(members) == 1 else "classes"
        add("")
        add(f"## {domain.capitalize()} ({len(members)} {noun})")
        add("")
        add("| Class | Verb | Status | Profile | Resource kinds | Summary | Tags | Risk | Since |")
        add("|---|---|---|---|---|---|---|---|---|")
        for entry in members:
            add("| " + " | ".join([
                f"`{entry['capability_id']}`",
                entry["verb"],
                entry["status"],
                entry["profile"],
                _cell(", ".join(entry["resource_kinds"])),
                _cell(entry["summary"]),
                _cell(", ".join(entry["tags"])),
                entry["risk_class"],
                entry["since"],
            ]) + " |")
    deprecated = [entry for entry in classes if entry["status"] == "deprecated"]
    add("")
    add(f"## Deprecated classes ({len(deprecated)})")
    add("")
    add("These classes duplicate protocol methods. They stay valid and callable for their")
    add("deprecation window ([MHS-003](03-capability-registry.md) CAP-006, CAP-040); new drivers")
    add("use the replacement.")
    add("")
    add("| Class | Replaced by |")
    add("|---|---|")
    for entry in deprecated:
        add(f"| `{entry['capability_id']}` | `{entry.get('x-mhs-replaced-by', '')}` |")
    kinds = catalogue.get("resource_kinds") or []
    add("")
    add(f"## Resource kinds ({len(kinds)})")
    add("")
    add("The normative resource-kind vocabulary used by the classes above. A binding whose")
    add("resource kind is not in its class's `resource_kinds` is `MHS.CAPABILITY.KIND_MISMATCH`.")
    add("Overlapping kinds are cross-referenced; prefer one of them consistently.")
    add("")
    add("| Kind | Title | See also |")
    add("|---|---|---|")
    for item in kinds:
        see = ", ".join(f"`{other}`" for other in item.get("see_also", []))
        add(f"| `{item['kind']}` | {_cell(item['title'])} | {see} |")
    verbs = Counter(entry["verb"] for entry in classes)
    statuses = Counter(entry["status"] for entry in classes)
    profiles = Counter(entry["profile"] for entry in classes)
    risks = Counter(entry["risk_class"] for entry in classes)
    add("")
    add("## Generated inventory")
    add("")
    add("| Metric | Value |")
    add("|---|---|")
    add(f"| Classes | {len(classes)} |")
    for verb in ("read", "write", "invoke"):
        add(f"| `{verb}` | {verbs.get(verb, 0)} |")
    for status in ("stable", "experimental", "deprecated"):
        add(f"| status `{status}` | {statuses.get(status, 0)} |")
    for profile in ("core", "sim"):
        add(f"| profile `{profile}` | {profiles.get(profile, 0)} |")
    for risk in ("R0", "R1", "R2"):
        add(f"| {risk} | {risks.get(risk, 0)} |")
    add(f"| R3 (class-level floor; bindings may elevate) | {risks.get('R3', 0)} |")
    add(f"| Requiring a permit at class level | {sum(1 for e in classes if e.get('requires_permit'))} |")
    add(f"| With declared safety limits | {sum(1 for e in classes if e.get('limits'))} |")
    add(f"| Resource kinds | {len(kinds)} |")
    add("")
    add("**CAP-046.** Every class listed here MUST resolve via `mhs.schema.get` on an")
    add("endpoint that binds it, and the returned class document MUST match the entry in")
    add("[`capabilities.json`](capabilities.json) for that `capability_id`.")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# MHS-B
# ---------------------------------------------------------------------------
B_HEAD = """\
# MHS-B — Error Code Registry

| Field | Value |
|---|---|
| Document | MHS-B (normative; tables generated from [`errors.json`](errors.json)) |
| Status | OpenMHS 0.9 development draft (wire revision 1) |
| Editor | The OpenMHS Authors |
| Layer | appendix of the core: the error vocabulary ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §7; [MHS-002](02-wire-protocol.md) §16 |
| Data contract | [`errors.json`](errors.json) ([`errors.schema.json`](../schema/errors.schema.json)); error objects: [`defs.schema.json`](../schema/defs.schema.json) `error` (`mhs_code` pattern `^MHS\\.[A-Z]+\\.[A-Z0-9_]+$`) |

Every failure carries a stable semantic code `MHS.<AREA>.<CODE>` inside
`error.data.mhs_code` (JSON-RPC errors) or `receipt.error.mhs_code` (receipt
errors). The JSON-RPC numeric `code` is structural and coarse; the `mhs_code` is
the stable identity that clients, tests and documentation branch on. This appendix
is the complete registry of OpenMHS 0.9; the codes belong to wire revision 1 and
keep their `MHS.` prefix. The tables are generated by
`python3 MHS/sdk/tools/gen_appendices.py` from [`errors.json`](errors.json), which
also generates the SDK table in `mhs/errors.py`; edit the JSON, not the tables.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Structure

```text
MHS . SAFETY . INTERLOCK_OPEN
 │      │            └─ CODE: uppercase, underscores, stable forever
 │      └─ AREA: one of the areas in §2
 └─ fixed prefix
```

**ERR-001.** A code MUST match `^MHS\\.[A-Z]+\\.[A-Z0-9_]+$` and MUST be listed in
this appendix. An endpoint MUST NOT emit an unregistered code; unknown codes are a
conformance failure (the client MAY still display them generically, §5).

**ERR-002.** A code, once published, MUST NOT change meaning and MUST NOT be reused
for a different condition. Retired codes stay in this appendix marked `retired`
([MHS-010](10-governance.md) GOV-040).

**ERR-003.** Every error object MUST carry `mhs_code`, `message` and
`data.retryable`; a non-retryable error SHOULD carry `data.remediation`. A
validation error SHOULD carry `data.details`. The `error` object schema is
[`defs.schema.json`](../schema/defs.schema.json) `$defs.error` (closed: no extra
fields).

**ERR-004.** Clients MUST NOT branch on `error.message` or on the JSON-RPC numeric
code for semantics; they MUST branch on `mhs_code`
([MHS-002](02-wire-protocol.md) PROTO-040). The numeric code exists for JSON-RPC
interoperability and transport tooling.

**ERR-005.** A receipt's `error` uses the same object and codes as a JSON-RPC
error. A physical rejection is a receipt with `status: "rejected"` and the same
`mhs_code` a JSON-RPC error would carry
([MHS-002](02-wire-protocol.md) PROTO-028); implementations MUST NOT invent a
second vocabulary for receipts.

**ERR-006.** `data.retryable` MUST be `true` only when retrying the identical
request cannot duplicate a physical effect and cannot bypass a safety check.
`MHS.OUTCOME.UNKNOWN`, any `MHS.SAFETY.*` rejection and any gated-permit error MUST
be `retryable: false`.

---

## 2. Areas and JSON-RPC structural codes
"""

B_AREAS_TAIL = """
**ERR-007.** An endpoint MUST use the structural code from this table for the
area. Multiple `mhs_code` values in one area share its structural code; a client
that sees an unexpected structural code MUST still read `mhs_code` and treat the
error by area.

---

## 3. Registry

Every code has exactly one record in [`errors.json`](errors.json) with the same
members: `code`, `area`, `jsonrpc_code`, `retryable`, `status`, `since`,
`meaning`, `remediation`, `driver_subset` and, for a deprecated code,
`replaced_by`. Status uses the lifecycle words of capability classes: `stable`,
`deprecated` (still registered and accepted; emit the replacement), `retired` or
`feature` (a `hello.features` disclosure, never an error, §4); `active` is the
pre-0.9 spelling of `stable`. `since` is the OpenMHS specification release
(`spec_version`, as MAJOR.MINOR.PATCH) that registered the code with its current
meaning; `mhs_error_registry` versions the registry format and wire revision, not
the codes. Remediation is written for the client or agent that receives the error.
The **Driver** column marks the driver subset (§3.{subset}): the only codes a driver
or bridge raises itself; every other code is produced by the runtime.
"""

B_TAIL = """
---

## 4. Cross-reference: codes that are also feature strings

Three identifiers are **not errors** and MUST NOT be emitted in an error object;
they are advertised in `hello.features` and endpoint descriptor `features[]`:

| Feature | Meaning | Where |
|---|---|---|
| `MHS.SAFETY.NOT_CERTIFIED` | Mandatory disclosure that OpenMHS is not a safety certification. | [MHS-004](04-safety.md) SAFE-050. |
| `MHS.CAPABILITY.EXPERIMENTAL_PRESENT` | An `experimental` capability class is bound by this endpoint. | [MHS-003](03-capability-registry.md) CAP-005. |
| `replay.seek` | Replay endpoint supports revision seeking. | [MHS-005](05-fidelity.md) FID-024. |

**ERR-008.** An endpoint MUST NOT use an error code as a feature marker or a
feature string as an error `mhs_code`; the two vocabularies are disjoint except
for the three documented disclosures above, which are only features.

---

## 5. Client handling of unknown codes

**ERR-009.** A client that receives an unregistered `MHS.<AREA>.<CODE>` MUST treat
it as a non-retryable error of that area, display the code and `message`, and MUST
NOT map it to success or to a generic "unknown" that loses the area. Area-level
behaviour is stable; code-level additions are MINOR changes.

**ERR-010.** A client MUST NOT retry when `data.retryable` is absent. Absence is
treated as `false`; the endpoint is non-conformant for omitting it.

---

## 6. Adding a code

**ERR-011.** A new code requires an accepted RFC ([MHS-010](10-governance.md) §2),
a record in [`errors.json`](errors.json) (this appendix is regenerated from it), a
conformance test for the condition, and a MINOR version bump of the document set
and suite. Deletion/retirement follows the deprecation windows of
[MHS-010](10-governance.md) §5.

**ERR-012.** The code string and its meaning are part of the stable API surface:
renaming a code is prohibited; introduce a new code and retire the old one.

---

## 7. Requirements list (this appendix)

**ERR-001** Codes match the grammar and are registered here.
**ERR-002** Stable meaning; no reuse.
**ERR-003** `mhs_code`, `message`, `data.retryable` mandatory; remediation advised.
**ERR-004** Branch on `mhs_code`, not message or numeric code.
**ERR-005** Receipt errors use the same objects/codes.
**ERR-006** Retryable only when safe; unknown/safety never retryable.
**ERR-007** Structural code per area.
**ERR-008** Feature strings and error codes are disjoint vocabularies.
**ERR-009** Unknown codes handled by area, non-retryable.
**ERR-010** Missing `retryable` means not retryable.
**ERR-011** New codes via RFC + test + MINOR bump.
**ERR-012** No renaming; new code + retirement instead.
"""


def _retry(record: dict) -> str:
    if record["retryable"] is None:
        return "—"
    return "yes" if record["retryable"] else "no"


def _rpc(record: dict) -> str:
    return "—" if record["jsonrpc_code"] is None else str(record["jsonrpc_code"])


def render_appendix_b(registry: dict) -> str:
    """Return appendix MHS-B for ``registry`` (errors.json)."""
    records = registry["errors"]
    out: list[str] = [B_HEAD.rstrip("\n"), ""]
    add = out.append
    add("| Area | JSON-RPC `code` | Codes | Used for |")
    add("|---|---|---|---|")
    counts = Counter(record["area"] for record in records)
    for area in registry["areas"]:
        codes = ", ".join(f"`{code}`" for code in area["jsonrpc_codes"])
        add(f"| `{area['area']}` | {codes} | {counts.get(area['area'], 0)} | {_cell(area['summary'])} |")
    populated = [area for area in registry["areas"] if counts.get(area["area"])]
    out.append(B_AREAS_TAIL.rstrip("\n").replace("{subset}", str(len(populated) + 1)))
    number = 0
    for area in registry["areas"]:
        members = [record for record in records if record["area"] == area["area"]]
        if not members:
            continue
        number += 1
        add("")
        add(f"### 3.{number} `MHS.{area['area']}.*`")
        add("")
        add("| Code | JSON-RPC | Retryable | Status | Driver | Meaning | Remediation |")
        add("|---|---|---|---|---|---|---|")
        for record in members:
            status = record["status"]
            if record.get("replaced_by"):
                status += f" → `{record['replaced_by']}`"
            add("| " + " | ".join([
                f"`{record['code']}`", _rpc(record), _retry(record), status,
                "yes" if record["driver_subset"] else "", _cell(record["meaning"]), _cell(record["remediation"]),
            ]) + " |")
    subset = [record for record in records if record["driver_subset"]]
    number += 1
    add("")
    add(f"### 3.{number} Driver subset")
    add("")
    add(f"These {len(subset)} codes are the complete vocabulary a driver or bridge raises")
    add("(`mhs.signals.DriverFailed(code, message)`); the runtime produces every other code.")
    add("A driver that cannot classify a native failure raises any other exception, which the")
    add("runtime reports as `MHS.ADAPTER.SHIM_FAILED` with a redacted message.")
    add("")
    add("| Code | Raised when |")
    add("|---|---|")
    for record in subset:
        add(f"| `{record['code']}` | {_cell(record['meaning'])} |")
    deprecated = [record for record in records if record["status"] == "deprecated"]
    number += 1
    add("")
    add(f"### 3.{number} Deprecated codes")
    add("")
    add("A deprecated code stays registered for its deprecation window; endpoints emit the")
    add("replacement and clients treat both alike.")
    add("")
    add("| Code | Replaced by |")
    add("|---|---|")
    for record in deprecated:
        add(f"| `{record['code']}` | `{record['replaced_by']}` |")
    out.append(B_TAIL.rstrip("\n"))
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
def outputs() -> dict[Path, str]:
    """Return ``{appendix path: rendered text}`` for both appendices."""
    catalogue = json.loads(CAPABILITIES.read_text(encoding="utf-8"))
    registry = json.loads(ERRORS.read_text(encoding="utf-8"))
    return {APPENDIX_A: render_appendix_a(catalogue), APPENDIX_B: render_appendix_b(registry)}


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if an appendix differs from its source")
    args = parser.parse_args(argv)
    try:
        rendered = outputs()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc!r}", file=sys.stderr)
        return 2
    stale = 0
    for path, text in rendered.items():
        current = path.read_text(encoding="utf-8") if path.is_file() else ""
        if current == text:
            print(f"ok: {path.name}" if args.check else f"unchanged: {path.name}")
            continue
        if args.check:
            stale += 1
            diff = difflib.unified_diff(current.splitlines(), text.splitlines(), str(path), "generated",
                                        lineterm="", n=1)
            print("\n".join(list(diff)[:40]))
            print(f"stale: {path} differs from its JSON source; run gen_appendices.py", file=sys.stderr)
        else:
            path.write_text(text, encoding="utf-8")
            print(f"wrote {path.name}")
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
