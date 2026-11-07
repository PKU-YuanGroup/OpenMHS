"""``python3 -m openai4s_mhs`` -- the operator's CLI for the OpenAI4S reference host.

Most verbs are deliberately independent of the OpenAI4S package: they import
only the MHS SDK (through :class:`MHSHost`) so they work before the native
tools are installed, in CI, and from a shell.  Every subcommand accepts
``--json`` for a single-line machine-readable result.

Verbs::

    devices      list discovered devices with mode/risk/fidelity
    inspect      full manifest of one device
    read         read one resource/state document
    call         invoke one capability and print the receipt
    safety       status | estop | reset (reset: host operator route, see below)
    evidence     export | verify | ledger
    endpoints    show configured endpoints
    mcp-config   emit OpenAI4S MCP connector entries (agent rows)
    core-patch   check | capture the OpenAI4S core patch (openai4s-core.patch)
    enable | disable | status   the experimental integration switch
    demo         run integration/openai4s/demo/run_demo.py

``safety reset DEVICE --operator NAME`` releases an e-stop latch through the
host operator route (``mhs.mcp --operator-tools``, needs the OpenAI4S MCP
client).  It needs an operator at an interactive terminal who types ``reset``;
otherwise nothing is sent.

Exit codes: the endpoint, settings and evidence verbs exit 0, or 2 on any
error.  ``safety reset``: 0 latch released; 1 the reset receipt is not
``completed`` or the operator did not confirm; 2 usage or settings error; 3
connector or endpoint unreachable; 4 no interactive operator or
``MHS.AUTH.*``.  ``core-patch check``: 0 applies without drift; 1 does not
apply or drifted; 2 git or the checkout is missing.  130 on interrupt.
"""

from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path
from typing import Any

from .config import DEFAULT_CONFIG_PATH, EndpointSpec, MHSConfig
from .host import MHSHost, MHSHostError
from .mcpconfig import connector_config

_PROG = "python3 -m openai4s_mhs"


# ---------------------------------------------------------------------------
# config / endpoint selection
# ---------------------------------------------------------------------------


def _looks_like_target(value: str) -> bool:
    return "://" in value or value.startswith(("http:", "https:", "mhs:"))


def _load_config(path: str | None, endpoint: str | None) -> tuple[MHSConfig, str | None]:
    """Load config and return (config, endpoint id to pass to MHSHost)."""
    config = MHSConfig.load(path)
    if endpoint is None:
        return config, None
    if _looks_like_target(endpoint):
        spec = EndpointSpec(id="cli", url=endpoint, label=endpoint)
        # `replace` preserves every policy/evidence field (including the
        # settings path passed to `mhs.mcp --config`).
        from dataclasses import replace

        return replace(config, endpoints=[spec]), "cli"
    return config, endpoint


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------


def _print_json(payload: Any, *, compact: bool) -> None:
    if compact:
        sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")
    else:
        sys.stdout.write(json.dumps(payload, sort_keys=True, indent=2) + "\n")


def _print_devices(result: Any) -> None:
    devices = result.get("devices") if isinstance(result, dict) else result
    if not devices:
        sys.stdout.write("no devices\n")
        return
    sys.stdout.write(f"{'ENDPOINT':<12} {'DEVICE':<44} {'MODE':<10} {'RISK':<5} CAPS\n")
    for item in devices:
        if "error" in item:
            sys.stdout.write(
                f"{item.get('endpoint_id', '?'):<12} ERROR {item.get('mhs_code', '')}: "
                f"{item['error']}\n"
            )
            continue
        caps = len(item.get("capabilities") or [])
        sys.stdout.write(
            f"{str(item.get('endpoint_id')):<12} "
            f"{str(item.get('device_id')):<44} "
            f"{str(item.get('mode')):<10} "
            f"{str(item.get('risk_class')):<5} {caps}\n"
        )


def _print_endpoints(result: Any) -> None:
    endpoints = result.get("endpoints") if isinstance(result, dict) else result
    if not endpoints:
        sys.stdout.write("no endpoints configured\n")
        return
    sys.stdout.write(f"{'ID':<16} {'TRANSPORT':<9} TARGET\n")
    for item in endpoints:
        sys.stdout.write(
            f"{str(item.get('id')):<16} {str(item.get('transport')):<9} "
            f"{str(item.get('target'))}\n"
        )


# ---------------------------------------------------------------------------
# subcommands
# ---------------------------------------------------------------------------


def _cmd_devices(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    result = host.devices(endpoint)
    if args.as_json:
        _print_json({"devices": result, "count": len(result)}, compact=True)
    else:
        _print_devices({"devices": result})
    return 0


def _cmd_endpoints(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    del endpoint
    result = host.endpoints()
    if args.as_json:
        _print_json({"endpoints": result, "count": len(result)}, compact=True)
    else:
        _print_endpoints({"endpoints": result})
    return 0


def _cmd_inspect(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    _print_json(host.inspect(args.device, endpoint), compact=args.as_json)
    return 0


def _cmd_read(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    try:
        result = host.read(args.device, args.resource, endpoint)
    except MHSHostError as exc:
        if exc.code not in ("MHS.HOST.NO_READ_CAPABILITY", "MHS.HOST.NO_RESOURCES"):
            raise
        # Domain manifests (a pipette exposes well levels, not cap.world.state)
        # need the compatibility read path in the native tool module.  The
        # import stays lazy so every other CLI verb works without OpenAI4S.
        from .tools import read_state

        result = read_state(host, args.device, args.resource, endpoint)
    _print_json(result, compact=args.as_json)
    return 0


def _cmd_call(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    try:
        payload = json.loads(args.input or "{}")
    except json.JSONDecodeError as exc:
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT", f"--input is not valid JSON: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise MHSHostError(
            "MHS.HOST.INVALID_ARGUMENT", "--input must be a JSON object"
        )
    receipt = host.command(
        args.device,
        args.capability,
        payload,
        resource_id=args.resource,
        endpoint_id=endpoint,
        expected_revision=args.expected_revision,
        deadline_ms=args.deadline_ms,
    )
    _print_json(receipt, compact=args.as_json)
    return 0


def _cmd_safety(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    if args.action == "status":
        result = host.safety_status(args.device, endpoint)
    elif args.action == "estop":
        result = host.estop(args.device, args.reason or "CLI requested e-stop", endpoint)
    else:
        return _operator_reset(host.config, args, endpoint, host=host)
    _print_json(result, compact=args.as_json)
    return 0


def _error_exit(code: str) -> int:
    if code.startswith("MHS.AUTH."):
        return 4
    if code.startswith(("MHS.TRANSPORT.", "MHS.OUTCOME.")):
        return 3
    if code in ("MHS.HOST.CONFIG_REQUIRED", "MHS.HOST.ADAPTER_MISSING", "MHS.PROTOCOL.INVALID_PARAMS",
                "MHS.HOST.ENDPOINT_NOT_ALLOWED"):
        return 2
    return 1


def _report_error(args: argparse.Namespace, code: str, message: str, **extra: Any) -> int:
    if getattr(args, "as_json", False):
        _print_json({"error": message, "mhs_code": code, **extra}, compact=True)
    else:
        sys.stderr.write(f"{code}: {message}\n")
    return _error_exit(code)


def _operator_reset(config: MHSConfig, args: argparse.Namespace, endpoint: str | None,
                    host: MHSHost | None = None) -> int:
    """``safety reset``: the host operator route, for an operator at a terminal.

    Without ``--endpoint`` the device is looked up on every configured endpoint (as ``safety estop`` and
    ``safety status`` do); a device on several endpoints needs ``--endpoint``.
    """
    from .operator_route import OperatorRoute

    operator = str(args.operator or "").strip()
    if not operator:
        return _report_error(args, "MHS.PROTOCOL.INVALID_PARAMS",
                             "a reset needs --operator NAME (the human who decides); nothing was sent")
    try:
        interactive = bool(sys.stdin.isatty())
    except (AttributeError, ValueError):
        interactive = False
    if not interactive:
        return _report_error(
            args, "MHS.AUTH.FORBIDDEN",
            "a reset needs an operator at an interactive terminal; nothing was sent",
            policy="operator_route_only",
        )
    try:
        if endpoint is None and len(config.endpoints) > 1 and host is not None:
            spec = host._resolve_device(args.device, None)[0]  # noqa: SLF001 - the estop/status lookup
        else:
            spec = config.endpoint(endpoint)
    except LookupError as exc:
        return _report_error(args, "MHS.HOST.ENDPOINT_NOT_ALLOWED", str(exc))
    except MHSHostError as exc:
        return _report_error(args, exc.code, exc.message, **({"details": exc.details} if exc.details else {}))
    sys.stderr.write(
        f"Release the e-stop latch of {args.device} on endpoint {spec.id} as {operator}?\n"
        "Check the equipment first. Type 'reset' to confirm: "
    )
    sys.stderr.flush()
    answer = sys.stdin.readline()
    if answer.strip().lower() != "reset":
        sys.stderr.write(f"{_PROG}: reset not confirmed; nothing was sent\n")
        return 1
    reason = args.reason or f"operator reset by {operator} (openai4s_mhs CLI)"
    try:
        with OperatorRoute(spec.id, config, operator=operator) as route:
            result = route.reset(args.device, reason=reason)
    except Exception as exc:  # noqa: BLE001 - every failure is reported with a code
        code = str(getattr(exc, "code", "") or "MHS.TRANSPORT.UNAVAILABLE")
        if not code.startswith("MHS."):
            code = "MHS.TRANSPORT.UNAVAILABLE"
        return _report_error(args, code, str(getattr(exc, "message", "") or exc))
    _print_json(result, compact=args.as_json)
    return 0 if str(result["receipt"].get("status")) == "completed" else 1


def _cmd_core_patch(args: argparse.Namespace) -> int:
    from . import corepatch

    try:
        if args.patch_action == "capture":
            if args.write:
                result: Any = corepatch.write(args.source)
            else:
                sys.stdout.write(corepatch.captured_text(args.source))
                return 0
        else:
            patch = corepatch.OVERLAY_PATCH_FILE if args.overlay else corepatch.PATCH_FILE
            result = corepatch.check(patch, args.source, worktree=args.worktree,
                                     compare=not args.overlay)
    except corepatch.CorePatchError as exc:
        _report_error(args, exc.code, exc.message)
        # No git or no checkout is a setup problem (2); a failing git step is a failed check (1).
        return 1 if exc.code == "MHS.HOST.PROTOCOL_ERROR" else 2
    _print_json(result, compact=args.as_json)
    if args.patch_action == "check":
        return 0 if result.get("ok") else 1
    return 0


def _cmd_evidence(host: MHSHost, args: argparse.Namespace, endpoint: str | None) -> Any:
    if args.action == "ledger":
        entries = host.ledger(args.limit)
        _print_json({"entries": entries, "count": len(entries)}, compact=args.as_json)
        return 0
    if args.action == "export":
        bundle = host.evidence_export(endpoint)
        if args.out:
            target = Path(args.out).expanduser().resolve()
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "w", encoding="utf-8") as handle:
                json.dump(bundle, handle, sort_keys=True, indent=2)
            _print_json(
                {
                    "path": str(target),
                    "endpoint_id": bundle.get("endpoint_id") or bundle.get("endpoint"),
                    "head_digest": bundle.get("head_digest"),
                    "count": bundle.get("count"),
                },
                compact=args.as_json,
            )
            return 0
        _print_json(bundle, compact=args.as_json)
        return 0
    if args.bundle:
        with open(Path(args.bundle).expanduser(), "r", encoding="utf-8") as handle:
            bundle = json.load(handle)
        report = host.evidence_verify(bundle, endpoint)
    else:
        report = host.evidence_verify(None, endpoint)
    _print_json(report, compact=args.as_json)
    return 0


def _cmd_mcp_config(args: argparse.Namespace) -> Any:
    from .mcpconfig import refuse_unsafe_agent_rows

    config, _endpoint = _load_config(args.config, None)
    if config.enabled or getattr(args, "write", False):
        refuse_unsafe_agent_rows(config)  # an enabled or stored agent row would carry the unsafe flags
    config_payload = connector_config(config, python=args.python)
    written = None
    if getattr(args, "write", False):
        from .mcp_register import sync_connectors

        written = sync_connectors(config)
        config_payload["openai4s_connectors"] = written
    if args.bare:
        _print_json(config_payload["connectors"], compact=args.as_json)
    else:
        _print_json(config_payload, compact=args.as_json)
    return 0


def _cmd_enable(args: argparse.Namespace) -> Any:
    from . import enable

    payload = enable(args.config)
    _print_json(payload, compact=getattr(args, "as_json", False))
    return 0


def _cmd_disable(args: argparse.Namespace) -> Any:
    from . import disable

    payload = disable(args.config)
    _print_json(payload, compact=getattr(args, "as_json", False))
    return 0


def _cmd_status(args: argparse.Namespace) -> Any:
    from . import status

    payload = status(args.config)
    _print_json(payload, compact=getattr(args, "as_json", False))
    return 0


def _cmd_demo(args: argparse.Namespace) -> Any:
    demo_path = Path(__file__).resolve().parent.parent / "demo" / "run_demo.py"
    if not demo_path.exists():
        sys.stderr.write(f"demo script not found: {demo_path}\n")
        return 2
    saved = sys.argv
    try:
        sys.argv = [str(demo_path), *args.demo_args]
        runpy.run_path(str(demo_path), run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return int(code) if isinstance(code, int) else (0 if code is None else 1)
    finally:
        sys.argv = saved
    return 0


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------


def _common_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--config",
        default=None,
        help=f"MHS config JSON (default: $MHS_CONFIG or {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--endpoint",
        default=None,
        help="Configured endpoint id, or an http(s)/mhs URL to use directly.",
    )
    parser.add_argument(
        "--json", dest="as_json", action="store_true", help="Single-line JSON output."
    )
    return parser


def build_parser() -> argparse.ArgumentParser:
    common = _common_parser()
    parser = argparse.ArgumentParser(
        prog=_PROG,
        description=(
            "Operate OpenMHS endpoints through the OpenAI4S reference host. OpenMHS is an "
            "independent open-source project, not affiliated with or endorsed by Anthropic."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    devices = sub.add_parser("devices", parents=[common], help="List MHS devices.")
    devices.set_defaults(func=_cmd_devices)

    inspect = sub.add_parser("inspect", parents=[common], help="Show one manifest.")
    inspect.add_argument("device")
    inspect.set_defaults(func=_cmd_inspect)

    read = sub.add_parser("read", parents=[common], help="Read device state.")
    read.add_argument("device")
    read.add_argument("--resource", default=None)
    read.set_defaults(func=_cmd_read)

    call = sub.add_parser("call", parents=[common], help="Invoke one capability.")
    call.add_argument("device")
    call.add_argument("capability")
    call.add_argument("--input", default=None, help="JSON object of capability arguments.")
    call.add_argument("--resource", default=None)
    call.add_argument("--expected-revision", type=int, default=None)
    call.add_argument("--deadline-ms", type=int, default=None)
    call.set_defaults(func=_cmd_call)

    safety = sub.add_parser(
        "safety",
        parents=[common],
        help="Safety status / e-stop / operator reset.",
        description=(
            "status and estop talk to the endpoint directly. reset is the host operator route: "
            "an mhs.mcp --operator-tools connection, an operator at an interactive terminal who "
            "types 'reset', and a host-ledger record."
        ),
    )
    safety.add_argument("action", choices=("status", "estop", "reset"))
    safety.add_argument("device")
    safety.add_argument("--reason", default=None, help="Reason recorded with an e-stop or a reset.")
    safety.add_argument("--operator", default=None,
                        help="reset: the human who decides (recorded in the host ledger).")
    safety.set_defaults(func=_cmd_safety)

    evidence = sub.add_parser(
        "evidence", parents=[common], help="Evidence export/verify/ledger."
    )
    evidence.add_argument("action", choices=("export", "verify", "ledger"))
    evidence.add_argument("--out", default=None, help="Write the exported bundle here.")
    evidence.add_argument("--bundle", default=None, help="Bundle file to verify.")
    evidence.add_argument("--limit", type=int, default=100)
    evidence.set_defaults(func=_cmd_evidence)

    endpoints = sub.add_parser(
        "endpoints", parents=[common], help="List configured endpoints."
    )
    endpoints.set_defaults(func=_cmd_endpoints)

    mcp = sub.add_parser(
        "mcp-config",
        parents=[common],
        help="Print OpenAI4S MCP connector entries for the configured endpoints.",
    )
    mcp.add_argument("--python", default=None, help="Interpreter for the connector.")
    mcp.add_argument("--bare", action="store_true", help="Print only the entries list.")
    mcp.add_argument(
        "--write",
        action="store_true",
        help="Also upsert the connector rows into OpenAI4S's connector store.",
    )
    mcp.set_defaults(func=None, mcp_config=True)

    enable = sub.add_parser(
        "enable",
        parents=[common],
        help="Enable the experimental MHS MCP integration (connectors) in settings.",
    )
    enable.set_defaults(settings_action="enable")

    disable = sub.add_parser(
        "disable",
        parents=[common],
        help="Disable the experimental MHS MCP integration and its connector rows.",
    )
    disable.set_defaults(settings_action="disable")

    settings_status = sub.add_parser(
        "status",
        parents=[common],
        help="Show whether the experimental MHS MCP integration is enabled.",
    )
    settings_status.set_defaults(settings_action="status")

    core_patch = sub.add_parser(
        "core-patch",
        help="Check or capture the OpenAI4S core patch (openai4s-core.patch).",
        description=(
            "check: git apply --check in a temporary clone --shared of the OpenAI4S checkout at the "
            "patch's Base-Commit, and compare the patch with the checkout's diff. capture: print the "
            "patch from the checkout (git diff, read-only); --write replaces openai4s-core.patch."
        ),
    )
    core_patch.add_argument("patch_action", choices=("check", "capture"))
    core_patch.add_argument("--source", default=None,
                            help="OpenAI4S git checkout (default: work/openai4s-src of this workspace).")
    core_patch.add_argument("--worktree", action="store_true",
                            help="check: apply against a full checkout instead of the base commit's index.")
    core_patch.add_argument("--overlay", action="store_true",
                            help="check: the optional overlay hook (openai4s-mhs.patch) instead.")
    core_patch.add_argument("--write", action="store_true", help="capture: rewrite openai4s-core.patch.")
    core_patch.add_argument("--json", dest="as_json", action="store_true", help="Single-line JSON output.")
    core_patch.set_defaults(core_patch=True)

    demo = sub.add_parser(
        "demo",
        add_help=False,
        help="Run the acceptance demo (extra arguments are forwarded).",
    )
    demo.add_argument("demo_args", nargs=argparse.REMAINDER)
    demo.set_defaults(demo=True)

    return parser


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    settings_action = getattr(args, "settings_action", None)
    if settings_action:
        handler = {
            "enable": _cmd_enable,
            "disable": _cmd_disable,
            "status": _cmd_status,
        }[settings_action]
        try:
            return int(handler(args) or 0)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"{_PROG}: {exc}\n")
            return 2

    if getattr(args, "demo", False):
        return _cmd_demo(args)
    if getattr(args, "core_patch", False):
        return _cmd_core_patch(args)
    if getattr(args, "mcp_config", False):
        try:
            return _cmd_mcp_config(args)
        except (LookupError, ValueError, OSError, json.JSONDecodeError) as exc:
            sys.stderr.write(f"{_PROG}: {exc}\n")
            return 2

    try:
        config, endpoint = _load_config(args.config, args.endpoint)
    except (LookupError, ValueError, OSError, json.JSONDecodeError) as exc:
        sys.stderr.write(f"{_PROG}: {exc}\n")
        return 2

    try:
        with MHSHost(config) as host:
            return int(args.func(host, args, endpoint) or 0)
    except MHSHostError as exc:
        payload = exc.to_dict()
        if getattr(args, "as_json", False):
            _print_json(payload, compact=True)
        else:
            sys.stderr.write(f"{exc.code}: {exc.message}\n")
        return 2
    except (LookupError, ValueError, OSError, json.JSONDecodeError) as exc:
        if getattr(args, "as_json", False):
            _print_json(
                {"error": str(exc), "mhs_code": "MHS.HOST.INVALID_ARGUMENT"},
                compact=True,
            )
        else:
            sys.stderr.write(f"{_PROG}: {exc}\n")
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover - module entry point
    raise SystemExit(main())
