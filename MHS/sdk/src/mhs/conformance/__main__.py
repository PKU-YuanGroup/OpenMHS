"""``python3 -m mhs.conformance`` -- run the suite, or verify a report by re-running it.

Run (``run`` may be omitted)::

    python3 -m mhs.conformance [run] --endpoint http://127.0.0.1:7400 --profile MHS-Sim --level CL4 --out r.json
    python3 -m mhs.conformance --command "python -m mhs.reference conveyor --stdio --test-profile" --level CL4
    python3 -m mhs.conformance --factory my_driver.tests:build_server --level CL3      # in-process
    python3 -m mhs.conformance --reference lab --level CL4                               # in-process
    python3 -m mhs.conformance --reference arm --noise --level CL4                       # seeded-noise arm
    python3 -m mhs.conformance --reference replay --bundle recording.json --level CL4    # replay endpoint

Verify::

    python3 -m mhs.conformance verify r.json --endpoint http://127.0.0.1:7400

``verify`` validates the report (schema, digest, the level recomputed from the
per-test ``required`` flags, missing required tests, disclaimers), re-runs the
suite with the report's profile and claimed level against the given target,
and compares the two (levels, the set of tests, every required verdict, the
manifest digest).

Targets: ``--endpoint`` (HTTP), ``--command`` (stdio child), ``--factory
module:callable`` (a zero-argument callable returning an ``MHSServer``; run
in-process with a fresh endpoint per test group) or ``--reference NAME`` (the
reference protocol fixtures, in-process: ``conveyor`` [``--test-profile``],
``lab``, ``arm`` [``--noise`` ``--seed N``], ``replay`` ``--bundle FILE``).
The published reference reports are reproduced this way (see
``MHS/conformance/README.md``).

Exit codes: 0 ok (report produced and the required level achieved; or report
verified), 1 the report could not be produced or does not verify, 2 usage
error (including an unknown profile or level), 3 transport error, 5 the
required level (``--require-level``, default ``--level``) was not achieved --
including a ``CL0`` requirement whose required CL0 tests failed (the report
then says ``NO LEVEL ACHIEVED``; ``level_achieved: CL0`` is only its floor).
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any, Callable

from mhs.conformance.report import compare_reports, level_awarded, load_report, save_report, validate_report
from mhs.conformance.suite import capping_tests, conformance_summary, run_suite

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_TRANSPORT = 3
EXIT_BELOW_TARGET = 5
_ORDER = ("CL0", "CL1", "CL2", "CL3", "CL4", "CL5")


def _add_target(parser: argparse.ArgumentParser) -> None:
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--endpoint", help="HTTP endpoint URL, e.g. http://127.0.0.1:7400")
    target.add_argument("--command", help="stdio endpoint launch command, e.g. 'python -m mhs.reference conveyor --stdio'")
    target.add_argument("--factory", help="in-process: module:callable returning a fresh MHSServer")
    target.add_argument("--reference", choices=("conveyor", "lab", "arm", "replay"),
                        help="in-process: a reference protocol fixture")
    parser.add_argument("--test-profile", action="store_true", help="with --reference conveyor: add the test hooks")
    parser.add_argument("--noise", action="store_true", help="with --reference arm: the seeded-noise arm")
    parser.add_argument("--seed", type=int, default=None,
                        help="with --reference arm --noise: the initial seed (default 0)")
    parser.add_argument("--bundle", default=None,
                        help="with --reference replay: the recorded evidence bundle the replay endpoint serves")


def _add_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--allow-actuation", action="store_true",
                        help="operator opt-in: run actuating tests against hardware/hybrid devices (CON-031); "
                             "without it, negative tests run on hardware only in-process (--factory/--reference), "
                             "where the harness blocks every write/invoke at the bridge")
    parser.add_argument("--read-only", action="store_true", help="send no command at all (CON-022)")
    parser.add_argument("--fixtures", default=None, help="fixture file with test inputs (JSON)")
    parser.add_argument("--approvals", default=None, help="operator approval records for permits (JSON array)")
    parser.add_argument("--source-commit", default=None, help="pinned upstream commit of the driver under test")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mhs.conformance",
        description="Run the executable OpenMHS conformance suite and emit conformance-report.json.",
    )
    _add_target(parser)
    _add_options(parser)
    parser.add_argument("--profile", default="MHS-Sim", help="MHS-Sim | MHS-Device | MHS-Bridge")
    parser.add_argument("--level", default="CL3", help="claimed level CL0..CL4")
    parser.add_argument("--out", default=None, help="write the report JSON to this path")
    parser.add_argument("--json", action="store_true", help="print the whole report as JSON on stdout")
    parser.add_argument("--require-level", default=None,
                        help="exit 5 unless this level was achieved (default: the claimed --level)")
    return parser


def build_verify_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m mhs.conformance verify",
        description="Validate a conformance report and compare it with a fresh run of the suite.",
    )
    parser.add_argument("report", help="report JSON to verify")
    _add_target(parser)
    _add_options(parser)
    return parser


def _load_json(path: str | None) -> Any:
    if not path:
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _resolve_factory(spec: str) -> Callable[[], Any]:
    module_name, _, attribute = spec.partition(":")
    if not module_name or not attribute:
        raise ValueError(f"--factory {spec!r} must be module:callable")
    target: Any = importlib.import_module(module_name)
    for part in attribute.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise ValueError(f"--factory {spec!r} is not callable")
    return target


def _reference_options(args: argparse.Namespace) -> dict[str, Any]:
    """``mhs.reference.build_endpoint`` options of ``--reference``; ``ValueError`` for a misuse (exit 2)."""

    name = args.reference
    if args.test_profile and name != "conveyor":
        raise ValueError("--test-profile applies to --reference conveyor only")
    if (args.noise or args.seed is not None) and name != "arm":
        raise ValueError("--noise/--seed apply to --reference arm only")
    if args.seed is not None and not args.noise:
        raise ValueError("--seed needs --noise (the exact arm takes no seed)")
    if name == "replay" and not args.bundle:
        raise ValueError("--reference replay needs --bundle <recorded evidence bundle>")
    if args.bundle and name != "replay":
        raise ValueError("--bundle applies to --reference replay only")
    options: dict[str, Any] = {}
    if args.test_profile:
        options["test_profile"] = True
    if args.noise:
        options["noise"] = True
        options["seed"] = int(args.seed) if args.seed is not None else 0
    if args.bundle:
        options["bundle"] = str(args.bundle)
    return options


def _run(args: argparse.Namespace, profile: str, level: str) -> dict[str, Any]:
    options = dict(
        allow_actuation=args.allow_actuation,
        read_only=args.read_only,
        fixtures=args.fixtures,
        approvals=_load_json(args.approvals),
        source_commit=args.source_commit,
    )
    if args.factory or args.reference:
        from mhs.conformance.inprocess import reference_factory, run_suite_inprocess

        factory = _resolve_factory(args.factory) if args.factory else reference_factory(
            args.reference, **_reference_options(args))
        return run_suite_inprocess(factory, profile=profile, level=level, **options)
    from mhs import connect

    if args.command:
        import shlex

        client = connect(argv=shlex.split(args.command))
    else:
        client = connect(args.endpoint)
    try:
        return run_suite(client, profile=profile, level=level, **options)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:  # noqa: BLE001
                pass


def _is_transport_error(exc: BaseException) -> bool:
    code = str(getattr(exc, "code", "") or "")
    return code.startswith("MHS.TRANSPORT.") or isinstance(exc, (ConnectionError, OSError))


def main_run(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = _run(args, args.profile, args.level)
    except ValueError as exc:
        sys.stderr.write(f"usage error: {exc}\n")
        return EXIT_USAGE
    except BaseException as exc:  # noqa: BLE001 - the CLI reports, it never tracebacks
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        sys.stderr.write(f"conformance suite produced no report: {type(exc).__name__}: {exc}\n")
        return EXIT_TRANSPORT if _is_transport_error(exc) else EXIT_FAILED
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(conformance_summary(report))
    if args.out:
        result = save_report(report, args.out, validate=False)
        print(f"report saved: {result['path']} (digest {report['report_digest']})")
    required = args.require_level or args.level
    if required not in _ORDER:
        sys.stderr.write(f"usage error: unknown --require-level {required!r}\n")
        return EXIT_USAGE
    blocked, capping = capping_tests(report)
    if level_awarded(report) is None:
        print(f"below target: no level achieved (CL0 is blocked by "
              f"{', '.join(test_id for test_id, _status in capping)}), required {required}")
        return EXIT_BELOW_TARGET
    if _ORDER.index(str(report.get("level_achieved"))) < _ORDER.index(required) or (
            blocked is not None and _ORDER.index(blocked) <= _ORDER.index(required)):
        print(f"below target: achieved {report.get('level_achieved')}, required {required}")
        return EXIT_BELOW_TARGET
    return EXIT_OK


def main_verify(argv: list[str]) -> int:
    args = build_verify_parser().parse_args(argv)
    try:
        report = load_report(args.report)
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"cannot read {args.report}: {exc}\n")
        return EXIT_USAGE
    errors = validate_report(report)
    for error in errors:
        print(f"INVALID {error}")
    try:
        rerun = _run(args, str(report.get("profile")), str(report.get("level_claimed")))
    except ValueError as exc:
        print(f"INVALID the report's profile/level cannot be re-run: {exc}")
        return EXIT_FAILED
    except BaseException as exc:  # noqa: BLE001
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        sys.stderr.write(f"re-run failed: {type(exc).__name__}: {exc}\n")
        return EXIT_TRANSPORT if _is_transport_error(exc) else EXIT_FAILED
    mismatches, notes = compare_reports(report, rerun)
    for line in mismatches:
        print(f"MISMATCH {line}")
    for line in notes:
        print(f"note: {line}")
    if errors or mismatches:
        print(f"report does NOT verify ({len(errors)} invalid, {len(mismatches)} mismatch(es)); "
              f"re-run achieved {rerun.get('level_achieved')}")
        return EXIT_FAILED
    awarded = level_awarded(report)
    print(f"report verifies: {report.get('profile')} "
          f"{awarded if awarded is not None else 'no level achieved (CL0 failed)'} "
          f"(re-run digest {rerun.get('report_digest')})")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "verify":
        return main_verify(arguments[1:])
    if arguments and arguments[0] == "run":
        arguments = arguments[1:]
    return main_run(arguments)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
