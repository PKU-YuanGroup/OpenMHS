#!/usr/bin/env python3
"""Regenerate the error table in ``mhs/errors.py`` from ``MHS/spec/errors.json``.

``MHS/spec/errors.json`` is the single source of the error registry.  This
tool rewrites only the region between the ``BEGIN GENERATED`` and
``END GENERATED`` markers of ``MHS/sdk/src/mhs/errors.py`` (the registry
version and the ``_NORMATIVE_ERRORS`` rows); everything else in the module,
including :data:`mhs.errors.LEGACY_ALIASES` and ``normalize_code``, is
hand-written and left untouched.

    python3 MHS/sdk/tools/gen_errors.py            # rewrite the table
    python3 MHS/sdk/tools/gen_errors.py --check    # exit 1 if errors.py is stale

Before writing, the registry is checked for the invariants the generated
module relies on (unique codes, area matches the code, one record shape,
feature strings without a JSON-RPC code, a replacement for every deprecated
code, the lifecycle words capability classes use, and a ``since`` that names a
specification release no later than ``spec_version``).  Exit codes: 0 ok, 1 stale (``--check``) or invalid registry, 2 usage
or unreadable files.  Standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parent
MHS_ROOT = SDK.parent
ERRORS_JSON = MHS_ROOT / "spec" / "errors.json"
ERRORS_PY = SDK / "src" / "mhs" / "errors.py"

BEGIN = "# --- BEGIN GENERATED: MHS/sdk/tools/gen_errors.py from MHS/spec/errors.json (do not edit) ---"
END = "# --- END GENERATED ---"

#: Members every record carries (errors.schema.json ``$defs.record``).
RECORD_KEYS = (
    "code", "area", "jsonrpc_code", "retryable", "status", "since",
    "meaning", "remediation", "driver_subset",
)
OPTIONAL_KEYS = ("replaced_by",)
#: Lifecycle words (shared with capability classes; ``feature`` marks a hello.features string).
STATUSES = ("stable", "deprecated", "retired", "feature")


def _release(text: object) -> tuple[int, ...] | None:
    """``"0.9.0"`` (or ``"0.9.0-dev1"``) -> ``(0, 9, 0)``; ``None`` for anything else."""
    parts = text.split("-", 1)[0].split("+", 1)[0].split(".") if isinstance(text, str) else []
    if not parts or not all(part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def load_registry(path: Path = ERRORS_JSON) -> dict:
    """Return the parsed registry document."""
    return json.loads(path.read_text(encoding="utf-8"))


def registry_problems(document: dict) -> list[str]:
    """Return invariant violations of ``document`` (empty when usable)."""
    problems: list[str] = []
    records = document.get("errors")
    if not isinstance(records, list) or not records:
        return ["errors.json has no 'errors' list"]
    areas = {item.get("area"): item for item in document.get("areas") or [] if isinstance(item, dict)}
    spec_release = _release(document.get("spec_version"))
    seen: set[str] = set()
    for index, record in enumerate(records):
        label = f"errors[{index}]"
        if not isinstance(record, dict):
            problems.append(f"{label}: not an object")
            continue
        code = record.get("code")
        label = f"{label} {code}"
        missing = [key for key in RECORD_KEYS if key not in record]
        extra = [key for key in record if key not in RECORD_KEYS + OPTIONAL_KEYS]
        if missing:
            problems.append(f"{label}: missing {missing}")
        if extra:
            problems.append(f"{label}: unknown members {extra}")
        if not isinstance(code, str) or code.count(".") != 2 or not code.startswith("MHS."):
            problems.append(f"{label}: malformed code")
            continue
        if code in seen:
            problems.append(f"{label}: duplicate code")
        seen.add(code)
        if code.split(".")[1] != record.get("area"):
            problems.append(f"{label}: area {record.get('area')!r} does not match the code")
        area = areas.get(record.get("area"))
        if area is None:
            problems.append(f"{label}: area {record.get('area')!r} is not declared in 'areas'")
        status = record.get("status")
        if status == "active":
            problems.append(f"{label}: status 'active' is the pre-0.9 spelling; use 'stable' (the capability "
                            "lifecycle word)")
        elif status not in STATUSES:
            problems.append(f"{label}: status {status!r} is not one of {list(STATUSES)}")
        since = _release(record.get("since"))
        if "since" in record and since is None:
            problems.append(f"{label}: since {record.get('since')!r} is not a MAJOR.MINOR.PATCH release")
        elif since is not None and spec_release is not None and since[: len(spec_release)] > spec_release:
            problems.append(f"{label}: since {record['since']} is later than spec_version "
                            f"{document.get('spec_version')} (since names the specification release that "
                            "registered the code, not the registry or wire revision)")
        if status == "feature":
            if record.get("jsonrpc_code") is not None or record.get("retryable") is not None:
                problems.append(f"{label}: a feature string has no jsonrpc_code or retryable")
        else:
            if not isinstance(record.get("jsonrpc_code"), int) or isinstance(record.get("jsonrpc_code"), bool):
                problems.append(f"{label}: jsonrpc_code must be an integer")
            elif area is not None and record["jsonrpc_code"] not in (area.get("jsonrpc_codes") or []):
                problems.append(f"{label}: jsonrpc_code {record['jsonrpc_code']} is not a structural code of area "
                                f"{record.get('area')} (ERR-007)")
            if not isinstance(record.get("retryable"), bool):
                problems.append(f"{label}: retryable must be a boolean")
        if status == "deprecated" and not record.get("replaced_by"):
            problems.append(f"{label}: deprecated without replaced_by")
        if not isinstance(record.get("driver_subset"), bool):
            problems.append(f"{label}: driver_subset must be a boolean")
    for index, record in enumerate(records):
        target = record.get("replaced_by") if isinstance(record, dict) else None
        if target and target not in seen:
            problems.append(f"errors[{index}]: replaced_by {target!r} is not a registered code")
    if document.get("error_count") != len(records):
        problems.append(f"error_count {document.get('error_count')} != {len(records)} records")
    return problems


def render_block(document: dict) -> str:
    """Return the generated region (markers included) for ``document``."""
    lines = [
        BEGIN,
        "#: Version of the normative error registry embedded below (wire revision 1).",
        f"NORMATIVE_REGISTRY_VERSION = {str(document.get('mhs_error_registry') or '1.0')!r}",
        "",
        "#: Normative registry rows, in registry order: (code, jsonrpc, retryable, area,",
        "#: meaning, remediation, kind, status, since, driver_subset, replaced_by).",
        "_NORMATIVE_ERRORS = (",
    ]
    for record in document["errors"]:
        kind = "feature" if record["status"] == "feature" else "error"
        row = (
            record["code"], record["jsonrpc_code"], record["retryable"], record["area"],
            record["meaning"], record["remediation"], kind, record["status"], record["since"],
            bool(record["driver_subset"]), record.get("replaced_by"),
        )
        lines.append("    (" + ", ".join(repr(item) for item in row) + "),")
    lines.append(")")
    lines.append(END)
    return "\n".join(lines)


def render_module(document: dict, current: str) -> str:
    """Return ``current`` (errors.py source) with the generated region replaced."""
    start = current.find(BEGIN)
    end = current.find(END)
    if start < 0 or end < 0 or end < start:
        raise ValueError(f"{ERRORS_PY}: generated-region markers not found")
    return current[:start] + render_block(document) + current[end + len(END):]


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 if errors.py differs from the registry")
    parser.add_argument("--registry", type=Path, default=ERRORS_JSON, help="errors.json to read")
    parser.add_argument("--module", type=Path, default=ERRORS_PY, help="errors.py to rewrite")
    args = parser.parse_args(argv)
    try:
        document = load_registry(args.registry)
        current = args.module.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    problems = registry_problems(document)
    if problems:
        for problem in problems:
            print(f"invalid registry: {problem}", file=sys.stderr)
        return 1
    try:
        rendered = render_module(document, current)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.check:
        if rendered != current:
            diff = difflib.unified_diff(current.splitlines(), rendered.splitlines(),
                                        str(args.module), "generated", lineterm="", n=1)
            print("\n".join(list(diff)[:60]))
            print(f"stale: {args.module} differs from {args.registry}; run gen_errors.py", file=sys.stderr)
            return 1
        print(f"ok: {args.module} matches {args.registry} ({len(document['errors'])} codes)")
        return 0
    if rendered != current:
        args.module.write_text(rendered, encoding="utf-8")
        print(f"wrote {args.module} ({len(document['errors'])} codes)")
    else:
        print(f"unchanged: {args.module}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
