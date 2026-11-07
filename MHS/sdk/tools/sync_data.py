#!/usr/bin/env python3
"""Copy the normative JSON data into the SDK package before a wheel build.

The canonical files stay where they are edited:

* ``MHS/schema/*.json``      -> ``MHS/sdk/src/mhs/_data/schema/``
* ``MHS/spec/capabilities.json`` -> ``MHS/sdk/src/mhs/_data/spec/capabilities.json``
* ``MHS/spec/errors.json``   -> ``MHS/sdk/src/mhs/_data/spec/errors.json``

``mhs/_data/`` is generated (and git-ignored); it is shipped as package data
so an installed SDK finds its schemas, catalogue and error registry without
the repository checkout.

    python3 MHS/sdk/tools/sync_data.py            # mirror the files
    python3 MHS/sdk/tools/sync_data.py --check    # exit 1 on drift, change nothing

Both modes also verify that every schema ``$id`` starts with
``mhs._ids.SCHEMA_BASE``.  While every schema still uses the legacy prefix
(before the re-namespacing lands) that check only warns; as soon as one
schema uses ``SCHEMA_BASE`` -- or with ``--strict-ids`` -- a mismatch is an
error.

Exit codes: 0 in sync, 1 drift or ``$id`` errors, 2 unreadable or invalid
sources.  Standard library only.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SDK = HERE.parent
MHS_ROOT = SDK.parent
DATA_DIR = SDK / "src" / "mhs" / "_data"
IDS_FILE = SDK / "src" / "mhs" / "_ids.py"

#: Sub-directories of ``_data`` this tool owns; files in them are mirrored.
MIRRORED = ("schema", "spec")
SPEC_FILES = ("capabilities.json", "errors.json")


def load_ids(path: Path = IDS_FILE):
    """Load ``mhs/_ids.py`` without importing the ``mhs`` package."""
    spec = importlib.util.spec_from_file_location("_openmhs_ids", path)
    if spec is None or spec.loader is None:  # pragma: no cover - broken checkout
        raise SystemExit(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def plan(mhs_root: Path = MHS_ROOT) -> dict[str, Path]:
    """Return ``{data-relative path: source path}`` for every mirrored file."""
    mapping: dict[str, Path] = {}
    schema_dir = mhs_root / "schema"
    for path in sorted(schema_dir.glob("*.json")):
        mapping[f"schema/{path.name}"] = path
    for name in SPEC_FILES:
        path = mhs_root / "spec" / name
        if path.is_file():
            mapping[f"spec/{name}"] = path
    return mapping


def _check_sources(mapping: dict[str, Path], mhs_root: Path) -> list[str]:
    """Return problems with the source files themselves (missing or invalid)."""
    problems: list[str] = []
    if not any(rel.startswith("schema/") for rel in mapping):
        problems.append(f"no schemas found in {mhs_root / 'schema'}")
    for name in SPEC_FILES:
        if f"spec/{name}" not in mapping:
            problems.append(f"missing source {mhs_root / 'spec' / name}")
    for rel, source in mapping.items():
        try:
            json.loads(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            problems.append(f"{source}: not valid JSON ({exc})")
    return problems


def _existing(data_dir: Path) -> dict[str, Path]:
    """Return the files currently present in the mirrored ``_data`` sub-dirs."""
    found: dict[str, Path] = {}
    for sub in MIRRORED:
        directory = data_dir / sub
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                found[path.relative_to(data_dir).as_posix()] = path
    return found


def drift(mhs_root: Path = MHS_ROOT, data_dir: Path = DATA_DIR) -> list[str]:
    """Return one message per difference between the sources and ``_data``."""
    mapping = plan(mhs_root)
    present = _existing(data_dir)
    messages: list[str] = []
    for rel, source in mapping.items():
        target = present.get(rel)
        if target is None:
            messages.append(f"missing {rel}")
        elif target.read_bytes() != source.read_bytes():
            messages.append(f"differs {rel}")
    for rel in present:
        if rel not in mapping:
            messages.append(f"extra {rel}")
    return messages


MARKER = ".openmhs-data"


def prunable(data_dir: Path) -> bool:
    """Whether ``sync`` may delete files it does not mirror in ``data_dir``: the package's own ``_data`` directory, a
    directory that carries the marker an earlier sync wrote, or one that is missing or empty (nothing to delete).  A mistaken
    ``--data-dir`` (a home or project directory) is refused instead of pruned."""
    if data_dir.name == "_data" or (data_dir / MARKER).is_file():
        return True
    return not data_dir.exists() or (data_dir.is_dir() and not any(data_dir.iterdir()))


def sync(mhs_root: Path = MHS_ROOT, data_dir: Path = DATA_DIR) -> list[str]:
    """Mirror the sources into ``data_dir``; return the paths that changed."""
    if not prunable(data_dir):
        raise ValueError(f"{data_dir} is not a package data directory (it is not named _data and has no {MARKER} marker); "
                         "refusing to write or prune it")
    mapping = plan(mhs_root)
    present = _existing(data_dir)
    changed: list[str] = []
    for rel, source in mapping.items():
        target = data_dir / rel
        data = source.read_bytes()
        if target.is_file() and target.read_bytes() == data:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        changed.append(rel)
    for rel, path in present.items():
        if rel not in mapping:
            path.unlink()
            changed.append(rel)
    marker = data_dir / MARKER
    if not marker.exists():
        marker.write_text("Generated by MHS/sdk/tools/sync_data.py; files under schema/ and spec/ are mirrored from MHS/.\n",
                          encoding="utf-8")
    return changed


def check_ids(
    mhs_root: Path = MHS_ROOT,
    schema_base: str | None = None,
    *,
    strict: bool | None = None,
) -> tuple[list[str], list[str]]:
    """Return ``(errors, warnings)`` for schema ``$id`` values.

    Every ``MHS/schema/*.schema.json`` ``$id`` must start with ``schema_base``
    (default ``mhs._ids.SCHEMA_BASE``) and should end with the file name.
    With ``strict=None`` the check is an error only once at least one schema
    already uses ``schema_base``; before that the findings are warnings.
    """
    if schema_base is None:
        schema_base = load_ids().SCHEMA_BASE
    findings: list[str] = []
    adopted = False
    for path in sorted((mhs_root / "schema").glob("*.schema.json")):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            findings.append(f"{path.name}: unreadable ({exc})")
            continue
        schema_id = document.get("$id") if isinstance(document, dict) else None
        if not isinstance(schema_id, str):
            findings.append(f"{path.name}: missing $id")
            continue
        if not schema_id.startswith(schema_base):
            findings.append(f"{path.name}: $id {schema_id!r} does not start with {schema_base!r}")
            continue
        adopted = True
        if schema_id != schema_base + path.name:
            findings.append(f"{path.name}: $id {schema_id!r} does not end with the file name")
    if strict is None:
        strict = adopted
    return (findings, []) if strict else ([], findings)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync_data.py",
        description="Mirror MHS/schema and the spec JSON registries into mhs/_data/.",
    )
    parser.add_argument("--check", action="store_true",
                        help="report drift and exit 1 instead of copying")
    parser.add_argument("--strict-ids", action="store_true",
                        help="treat schema $id prefix findings as errors even before the rename lands")
    parser.add_argument("--mhs-root", type=Path, default=MHS_ROOT,
                        help="directory holding schema/ and spec/ (default: %(default)s)")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR,
                        help="package data directory to write (default: %(default)s)")
    parser.add_argument("-q", "--quiet", action="store_true", help="print errors only")
    parser.add_argument("-v", "--verbose", action="store_true", help="list every advisory finding")
    args = parser.parse_args(argv)

    mhs_root = args.mhs_root.resolve()
    data_dir = args.data_dir.resolve()
    mapping = plan(mhs_root)
    problems = _check_sources(mapping, mhs_root)
    if problems:
        for problem in problems:
            print(f"error: {problem}", file=sys.stderr)
        return 2

    id_errors, id_warnings = check_ids(mhs_root, strict=True if args.strict_ids else None)
    if id_warnings and not args.quiet:
        print(f"warning: {len(id_warnings)} schema $id finding(s) against SCHEMA_BASE; advisory "
              "until a schema adopts it (--strict-ids enforces now, -v lists them)", file=sys.stderr)
        if args.verbose:
            for warning in id_warnings:
                print(f"warning: {warning}", file=sys.stderr)

    for error in id_errors:
        print(f"error: {error}", file=sys.stderr)

    status = 0
    if args.check:
        differences = drift(mhs_root, data_dir)
        for message in differences:
            print(f"drift: {message}", file=sys.stderr)
        if differences:
            print(f"error: {data_dir} is out of date; run MHS/sdk/tools/sync_data.py",
                  file=sys.stderr)
            status = 1
        elif not args.quiet:
            print(f"OK: {len(mapping)} files in sync in {data_dir}")
    else:
        try:
            changed = sync(mhs_root, data_dir)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if not args.quiet:
            print(f"synced {len(mapping)} files into {data_dir} ({len(changed)} changed)")
    if id_errors:
        status = 1
    return status


if __name__ == "__main__":
    raise SystemExit(main())
