"""``python -m mhs.driver``: the driver package tools (check, reference, new, export, catalog).

::

    python3 -m mhs.driver check <dir> --backend fake      # the acceptance gate (G1-G9); exit 0 = done
    python3 -m mhs.driver reference <dir>                 # write reference.json and REFERENCE.md
    python3 -m mhs.driver new <dir> --card <dir>/task.json [--like <exemplar dir>]
    python3 -m mhs.driver export <dir> [--out mhs-adapter.json]
    python3 -m mhs.driver catalog search <words> | catalog show <cap id> | catalog kinds
    python3 -m mhs.driver --print-interface               # the text of MHS/sdk/INTERFACE.md

Exit status: 0 success, 1 failure (a failing gate, a stale reference file, a
refused scaffold), 2 usage error.  ``check`` never imports the package: it
runs the gates in a child process and exits 0 only on a schema-valid passing
report from it (:func:`mhs.driver.check.run_check_isolated`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    from .scaffold import KINDS

    parser = argparse.ArgumentParser(
        prog="python3 -m mhs.driver",
        description="OpenMHS driver package tools: the acceptance gate, reference files, scaffolding, export and "
                    "the capability catalogue.")
    parser.add_argument("--print-interface", action="store_true",
                        help="print the generated interface contract (MHS/sdk/INTERFACE.md) and exit")
    commands = parser.add_subparsers(dest="command", metavar="{check,reference,new,export,catalog}")

    check = commands.add_parser("check", help="run the acceptance gate G1-G9 and write check-report.json",
                                description="Run the acceptance gate on a driver directory. Exit 0 on a pass "
                                            "(evidence contract_checked), 1 on a failure (failing gate ids are "
                                            "printed), 2 on a usage error.")
    check.add_argument("directory", help="the driver package directory")
    check.add_argument("--backend", default="fake", choices=("fake", "sim", "hardware"),
                       help="backend to check (fake or sim; hardware is refused: operator procedure)")
    check.add_argument("--root", help="project root that task.json paths are relative to (default: found above "
                                      "the directory)")
    check.add_argument("--clone", help="the upstream clone to read (default: task.json local_path under the root)")
    check.add_argument("--companions-root",
                       help="the directory of fetched companion clones and their LOCK.json (default: the directory "
                            "of each lock companion's local_path under the root, work/companions)")
    check.add_argument("--json", action="store_true", help="print the check report as JSON")
    check.add_argument("--no-report", action="store_true", help="do not write check-report.json")
    check.add_argument("--verbose", action="store_true",
                       help="print warnings of passing gates and the gate process's own output too")

    reference = commands.add_parser("reference", help="write reference.json and REFERENCE.md",
                                    description="Generate the reference file of a driver directory from driver.py "
                                                "and driver.lock.json.")
    reference.add_argument("directory")
    reference.add_argument("--check", action="store_true",
                           help="write nothing; exit 1 when a generated file is missing or stale")

    new = commands.add_parser("new", help="scaffold a driver package from the templates or an exemplar",
                              description="Create a driver package. The task card is --card or <dir>/task.json; "
                                          "--like copies an exemplar's code files (card-specific files come from "
                                          "the templates). Existing files are never overwritten without --force.")
    new.add_argument("directory")
    new.add_argument("--card", help="the task card (copied to <dir>/task.json)")
    new.add_argument("--like", help="an exemplar driver directory to copy structurally")
    new.add_argument("--kind", choices=KINDS, help="template kind (default: from the card's helper)")
    new.add_argument("--model-id", help="authored_by.model_id written into driver.lock.json")
    new.add_argument("--run-id", help="authored_by.run_id written into driver.lock.json")
    new.add_argument("--force", action="store_true", help="overwrite existing files")

    export = commands.add_parser("export", help="print an mhs-adapter.json for the driver (interop)",
                                 description="Export the driver as an mhs-adapter.json whose single 'driver' bridge "
                                             "points back at the directory.")
    export.add_argument("directory")
    export.add_argument("--out", help="write the document here instead of printing it")

    catalog = commands.add_parser("catalog", help="look up capability classes",
                                  description="Search and show the capability catalogue (MHS/spec/capabilities.json).")
    lookups = catalog.add_subparsers(dest="lookup", metavar="{show,search,kinds}")
    show = lookups.add_parser("show", help="print one capability class")
    show.add_argument("capability_id")
    search = lookups.add_parser("search", help="find capability classes by words")
    search.add_argument("words", nargs="+")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--all", action="store_true", help="include deprecated classes")
    search.add_argument("--json", action="store_true")
    lookups.add_parser("kinds", help="list the catalogue resource kinds")
    return parser


def _check(args: argparse.Namespace) -> int:
    from .check import CheckUsageError, format_report, run_check_isolated

    try:
        report, output = run_check_isolated(Path(args.directory), backend=args.backend, root=args.root,
                                            clone=args.clone, write_report=not args.no_report,
                                            companions_root=args.companions_root)
    except CheckUsageError as exc:
        print(f"usage error: {exc}", file=sys.stderr)
        return 2
    if args.verbose and output.strip():
        sys.stderr.write(output if output.endswith("\n") else output + "\n")
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(format_report(report, verbose=args.verbose))
    return 0 if report.get("passed") else 1


def _reference(args: argparse.Namespace) -> int:
    from .package import stale_references, write_reference
    from .spec import DriverDefinitionError

    directory = Path(args.directory)
    if not (directory / "driver.py").is_file():
        print(f"usage error: {directory} is not a driver directory (no driver.py)", file=sys.stderr)
        return 2
    try:
        if args.check:
            stale = stale_references(directory)
            for name in stale:
                print(f"{directory / name}: missing or stale (run python3 -m mhs.driver reference {directory})")
            return 1 if stale else 0
        for path in write_reference(directory):
            print(f"wrote {path}")
    except DriverDefinitionError as exc:
        print(f"the driver does not resolve: {exc}", file=sys.stderr)
        return 1
    return 0


def _new(args: argparse.Namespace) -> int:
    from .package import ScaffoldError, scaffold

    values = {"model_id": args.model_id, "run_id": args.run_id}
    try:
        written = scaffold(Path(args.directory), card=args.card, like=args.like, kind=args.kind, force=args.force,
                           values=values)
    except ScaffoldError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    for path in written:
        print(f"wrote {path}")
    directory = args.directory
    print(f"next: edit driver.py and the fake, then python3 -m mhs.driver reference {directory} and "
          f"python3 -m mhs.driver check {directory} --backend fake")
    return 0


def _export(args: argparse.Namespace) -> int:
    from .package import export_adapter
    from .spec import DriverDefinitionError

    directory = Path(args.directory)
    if not (directory / "driver.py").is_file():
        print(f"usage error: {directory} is not a driver directory (no driver.py)", file=sys.stderr)
        return 2
    try:
        document = export_adapter(directory, out=args.out)
    except DriverDefinitionError as exc:
        print(f"the driver does not resolve: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(document, indent=2, sort_keys=True) + "\n"
    if args.out:
        try:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"usage error: cannot write {args.out}: {exc}", file=sys.stderr)
            return 2
        print(f"wrote {args.out}")
    else:
        sys.stdout.write(text)
    return 0


def _catalog(args: argparse.Namespace) -> int:
    from .. import catalog

    if args.lookup == "show":
        entry = catalog.get(args.capability_id)
        if entry is None:
            print(f"{args.capability_id} is not in the catalogue; try: python3 -m mhs.driver catalog search <words>",
                  file=sys.stderr)
            return 1
        print(json.dumps(entry, indent=2, sort_keys=True))
        return 0
    if args.lookup == "search":
        found = catalog.search(" ".join(args.words), limit=args.limit, include_deprecated=args.all)
        if args.json:
            print(json.dumps(found, indent=2, sort_keys=True))
        else:
            for item in found:
                print(f"{item['capability_id']:<36} {item.get('verb', ''):<6} {item.get('status', ''):<12} "
                      f"{item.get('title', '')}")
        return 0 if found else 1
    for kind in catalog.default_catalog().resource_kinds:
        print(kind)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))
    except SystemExit as exc:
        return int(exc.code or 0)
    if args.print_interface:
        from .interface import interface_text

        sys.stdout.write(interface_text())
        return 0
    handlers: dict[str, Any] = {"check": _check, "reference": _reference, "new": _new, "export": _export}
    if args.command in handlers:
        return handlers[args.command](args)
    if args.command == "catalog":
        if args.lookup is None:
            print("usage: python3 -m mhs.driver catalog {show,search,kinds} ...", file=sys.stderr)
            return 2
        return _catalog(args)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
