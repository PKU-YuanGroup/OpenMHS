"""Generate MHS/sdk/src/mhs/conformance/applicability.json (SPEC-001).

Auditable rule-based inventory of all numbered normative requirements:

* parse every ``**AREA-NNN.**`` statement from ``MHS/spec/*.md``;
* attach the profile/level scope from MHS-001 §2, §3.2 and §5.1;
* attach the executable checks recorded in ``traceability.json``;
* for everything else record an explicit disposition with a spec basis, or
  ``not_verified`` when no justification exists.

Bold statements whose id does not follow the ``AREA-NNN`` grammar (for example
``MHS-A-001``) are listed under ``nonconforming_ids`` and not counted, so the
inventory never silently drops them.

Usage (from anywhere; the SDK source is put on ``sys.path`` and no bytecode is
written)::

    python3 MHS/sdk/tools/build_applicability.py           # regenerate
    python3 MHS/sdk/tools/build_applicability.py --check   # exit 1 when the file is stale

Re-run it after any change to ``MHS/spec/*.md`` or ``traceability.json``.
Ported from the round-2 remediation script (the original stays untouched in
the private audit directory).
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from collections import Counter  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
SDK_SRC = ROOT / "MHS" / "sdk" / "src"
if str(SDK_SRC) not in sys.path:
    sys.path.insert(0, str(SDK_SRC))

from mhs.conformance.report import SUITE_VERSION  # noqa: E402
from mhs.conformance.requirements import validate_applicability  # noqa: E402

SPEC_DIR = ROOT / "MHS" / "spec"
TRACEABILITY = SDK_SRC / "mhs" / "conformance" / "traceability.json"
OUT = SDK_SRC / "mhs" / "conformance" / "applicability.json"
GENERATED_BY = "MHS/sdk/tools/build_applicability.py"

ENDPOINT = ["MHS-Sim", "MHS-Device", "MHS-Bridge"]
ALL_PROFILES = ["MHS-Sim", "MHS-Device", "MHS-Bridge", "MHS-Host", "MHS-Registry"]
AREA_PROFILES = {
    "CON": ALL_PROFILES,
    "PROTO": ENDPOINT,
    "CAP": ENDPOINT,
    "SESS": ENDPOINT,
    "OP": ENDPOINT,
    "MODE": ENDPOINT,
    "SAFE": ENDPOINT,
    "FID": ENDPOINT,
    "EVID": ENDPOINT,
    "EVT": ENDPOINT,
    "TPT": ENDPOINT,
    "COMP": ["MHS-Bridge"],
    "ADPT": ["MHS-Bridge"],
    "HOST": ["MHS-Host"],
    "REG": ["MHS-Registry"],
    "PRIV": ["MHS-Registry"],
    "GOV": ALL_PROFILES,
    "ERR": ALL_PROFILES,
}
AREA_LEVELS = {
    "CON": ["CL0", "CL1", "CL2", "CL3", "CL4", "CL5"],
    "PROTO": ["CL1", "CL2", "CL3", "CL4"],
    "CAP": ["CL0", "CL1", "CL2", "CL3", "CL4"],
    "SESS": ["CL1", "CL2", "CL3", "CL4"],
    "OP": ["CL2", "CL3", "CL4"],
    "MODE": ["CL1", "CL2", "CL3", "CL4"],
    "SAFE": ["CL2", "CL3", "CL4"],
    "FID": ["CL1", "CL2", "CL3", "CL4"],
    "EVID": ["CL2", "CL3", "CL4"],
    "EVT": ["CL1", "CL2", "CL3"],
    "COMP": ["CL5"],
    "ADPT": ["CL0"],
    "TPT": ["CL1", "CL2", "CL3", "CL4"],
    "HOST": ["CL1", "CL2", "CL3", "CL4", "CL5"],
    "REG": ["CL0", "CL1", "CL2", "CL3", "CL4", "CL5"],
    "PRIV": ["CL5"],
    "GOV": [],
    "ERR": [],
}

_WELL_FORMED = re.compile(r"^\*\*([A-Z][A-Z0-9]*-[0-9]{3})\.\*\*")
_NONCONFORMING = re.compile(r"^\*\*([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+-[0-9]{3})\.\*\*")


def parse_requirements() -> tuple[dict[str, dict], list[dict], list[dict]]:
    entries: dict[str, dict] = {}
    duplicates: list[dict] = []
    nonconforming: list[dict] = []
    for path in sorted(SPEC_DIR.glob("*.md")):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            record_of = lambda requirement_id: {  # noqa: E731
                "id": requirement_id,
                "doc": path.relative_to(ROOT).as_posix(),
                "line": lineno,
                "text": line.strip()[:240],
            }
            match = _WELL_FORMED.match(line)
            if not match:
                odd = _NONCONFORMING.match(line)
                if odd:
                    nonconforming.append(record_of(odd.group(1)))
                continue
            requirement_id = match.group(1)
            record = record_of(requirement_id)
            if requirement_id in entries:
                duplicates.append(record)
                continue
            entries[requirement_id] = record
    return entries, duplicates, nonconforming


def disposition_for(requirement_id: str, area: str, executable: dict[str, list[str]]) -> tuple[str, list[str], str]:
    if requirement_id in executable:
        checks = executable[requirement_id]
        return (
            "executable",
            checks,
            "executed by " + ", ".join(checks) + " (MHS-001 §4.1 stable test id / grouped T-id)",
        )
    if area == "GOV":
        return (
            "editorial",
            [],
            "MHS-001 §4.2: GOV requirements are verified editorially, not in the suite",
        )
    if area == "ERR":
        return (
            "editorial",
            [],
            "MHS-B error registry: error vocabulary integrity is checked by errors.json/schema tests, not by an endpoint behaviour test",
        )
    if area == "CON":
        return (
            "report_process",
            [],
            "MHS-001 §4.2 CON: report/claim process requirement; reviewed through report validation, digest recomputation and claim audit, not an endpoint behaviour test",
        )
    if area == "COMP":
        return (
            "level_not_claimed",
            [],
            "CON-006/§3.3: CL5 composition is assessed only for MHS-Bridge, MHS-Host and MHS-Registry; MHS-Sim tops out at CL4",
        )
    if area in {"HOST", "REG", "PRIV", "ADPT"}:
        return (
            "out_of_profile",
            [],
            "MHS-001 §2: "
            + {
                "HOST": "MHS-Host",
                "REG": "MHS-Registry",
                "PRIV": "MHS-Registry",
                "ADPT": "MHS-Bridge",
            }[area]
            + " profile obligation, not an MHS-Sim endpoint obligation; this report makes no such profile claim",
        )
    return (
        "not_verified",
        [],
        f"no executable check in suite {SUITE_VERSION} and no profile/level exclusion applies; explicit residual gap, never counted as checked",
    )


def build() -> dict:
    entries, duplicates, nonconforming = parse_requirements()
    trace = json.loads(TRACEABILITY.read_text(encoding="utf-8"))["tests"]
    executable: dict[str, list[str]] = {}
    for test_id, requirement_ids in trace.items():
        for requirement_id in requirement_ids:
            executable.setdefault(requirement_id, []).append(test_id)
    for checks in executable.values():
        checks.sort()

    inventory: dict[str, dict] = {}
    for requirement_id, record in sorted(entries.items()):
        area = requirement_id.split("-")[0]
        disposition, checks, basis = disposition_for(requirement_id, area, executable)
        inventory[requirement_id] = {
            **record,
            "area": area,
            "profiles": AREA_PROFILES.get(area, []),
            "levels": AREA_LEVELS.get(area, []),
            "disposition": disposition,
            "checks": checks,
            "basis": basis,
        }
    counts = Counter(entry["disposition"] for entry in inventory.values())
    counts["normative_ids"] = len(inventory)
    document = {
        "artifact": "mhs-conformance-applicability",
        "version": "1.0.0",
        "generated_by": GENERATED_BY,
        "generated_from": [
            "MHS/spec/*.md numbered requirements",
            "MHS/sdk/src/mhs/conformance/traceability.json",
            "MHS-001 §2, §3.2, §4.1, §4.2, §5.1",
        ],
        "counting_rules": {
            "checked": "requirement has at least one executable suite check",
            "tested": "at least one of those checks appears in a given report",
            "dispositioned": "explicit non-executable disposition with a spec basis (out_of_profile, editorial, report_process, level_not_claimed)",
            "not_verified": "no executable check and no disposition; must never be presented as checked",
            "sum": "checked + dispositioned + not_verified = normative_ids",
        },
        "duplicate_locations": duplicates,
        "nonconforming_ids": nonconforming,
        "counts": dict(sorted(counts.items())),
        "requirements": inventory,
    }
    errors = validate_applicability(document)
    if errors:
        raise SystemExit("generated inventory is invalid: " + "; ".join(errors[:10]))
    return document


def render(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true", help="exit 1 when applicability.json is not up to date")
    args = parser.parse_args(argv)
    document = build()
    text = render(document)
    current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
    summary = {"path": OUT.relative_to(ROOT).as_posix(), "counts": document["counts"],
               "duplicates": len(document["duplicate_locations"]),
               "nonconforming_ids": [item["id"] for item in document["nonconforming_ids"]]}
    if args.check:
        if current != text:
            stale = []
            try:
                previous = json.loads(current).get("requirements", {}) if current else {}
            except ValueError:
                previous = {}
            for requirement_id, entry in document["requirements"].items():
                if previous.get(requirement_id) != entry:
                    stale.append(requirement_id)
            print(json.dumps({**summary, "stale": True, "changed_ids": stale[:20],
                              "changed_count": len(stale)}))
            return 1
        print(json.dumps({**summary, "stale": False}))
        return 0
    OUT.write_text(text, encoding="utf-8")
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
