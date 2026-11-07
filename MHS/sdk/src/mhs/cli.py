"""``mhs`` command line interface (``MHS/sdk/docs/cli.md``).

The CLI is one of the three control surfaces (with the MCP projection and
code files).  It is a thin layer over :mod:`mhs.client`, :mod:`mhs.adapter`,
:mod:`mhs.run`, :mod:`mhs.discovery` and :mod:`mhs.conformance`; the endpoint
enforces every safety rule, so the CLI has no more authority than any other
client.  Every endpoint command takes ``--json`` (the machine-readable
contract; human output is for people and may change).

Exit codes (one table for every command)::

    0   success
    1   the command ran but was refused or failed: a receipt that is not
        completed (rejected, failed, cancelled, unknown), an endpoint error,
        a driver strict mode refuses, an invalid document
    2   usage error (bad flags, bad JSON input, missing file)
    3   transport error: the endpoint cannot be reached or the response was
        lost (MHS.TRANSPORT.*, MHS.OUTCOME.TIMEOUT, MHS.OUTCOME.UNKNOWN)
    4   authentication or authorisation error (MHS.AUTH.*, a reset without an
        interactive operator, a hardware backend that is not allowed)
    5   conformance below the required level (mhs conform)
    130 interrupted

Precedence: a receipt gives 0 or 1 by its status (whatever its error code),
except a refusal whose ``error.mhs_code`` is ``MHS.AUTH.*``, which gives 4.
Codes 3 and 4 otherwise come from errors raised without a receipt.  A command
that addresses several devices (``mhs estop``) exits 0 only when every device
succeeded; otherwise with the code its failures share (3 when only transport
failed, 4 when only authorisation did), else 1.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import _ids
from .client import MHSRejected, connect
from .errors import MHSError
from .protocol import MHS_VERSION

__all__ = [
    "EXIT_AUTH",
    "EXIT_BELOW_TARGET",
    "EXIT_INTERRUPTED",
    "EXIT_OK",
    "EXIT_REJECTED",
    "EXIT_TRANSPORT",
    "EXIT_USAGE",
    "UsageError",
    "build_parser",
    "exit_code_for",
    "main",
]

EXIT_OK = 0
EXIT_REJECTED = 1
EXIT_USAGE = 2
EXIT_TRANSPORT = 3
EXIT_AUTH = 4
EXIT_BELOW_TARGET = 5
EXIT_INTERRUPTED = 130

_REFERENCE_NAMES = ("conveyor", "lab", "arm", "replay")
_LEVELS = ("CL0", "CL1", "CL2", "CL3", "CL4", "CL5")


class UsageError(Exception):
    """A local usage error (exit 2): nothing was sent to an endpoint."""


def exit_code_for(exc: BaseException) -> int:
    """The exit code of an exception raised by a command (see the module docstring)."""
    if isinstance(exc, MHSRejected):
        return _receipt_exit(exc.receipt) or EXIT_REJECTED
    if isinstance(exc, UsageError):
        return EXIT_USAGE
    if isinstance(exc, KeyboardInterrupt):
        return EXIT_INTERRUPTED
    code = str(getattr(exc, "code", "") or "") if isinstance(exc, MHSError) else ""
    if code.startswith("MHS.TRANSPORT.") or code in ("MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"):
        return EXIT_TRANSPORT
    if code.startswith("MHS.AUTH."):
        return EXIT_AUTH
    return EXIT_REJECTED


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str))


def _emit(payload: Any, *, as_json: bool) -> None:
    if as_json:
        _print_json(payload)
        return
    print(_render_human(payload))


def _render_human(payload: Any, *, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(payload, dict):
        lines = []
        for key, value in payload.items():
            if isinstance(value, (dict, list)) and value:
                lines.append(f"{pad}{key}:")
                lines.append(_render_human(value, indent=indent + 1))
            else:
                lines.append(f"{pad}{key}: {value}")
        return "\n".join(lines)
    if isinstance(payload, list):
        if not payload:
            return f"{pad}(empty)"
        return "\n".join(_render_human(item, indent=indent) for item in payload)
    return f"{pad}{payload}"


def _error_object(exc: MHSError) -> dict[str, Any]:
    return {"mhs_code": exc.code, "message": exc.message, "retryable": exc.retryable,
            "data": {key: value for key, value in exc.data.items() if key not in ("remediation", "retryable")},
            "remediation": exc.data.get("remediation")}


def _report_error(exc: MHSError, *, as_json: bool) -> None:
    """``--json``: ``{"error": {...}}`` on stdout (the result); otherwise one line on stderr."""
    if as_json:
        _print_json({"error": _error_object(exc)})
        return
    hint = exc.data.get("remediation")
    print(f"mhs: {exc.code}: {exc.message}" + (f" ({hint})" if hint else ""), file=sys.stderr)


def _receipt_line(receipt: Mapping[str, Any]) -> str:
    error = receipt.get("error") if isinstance(receipt.get("error"), Mapping) else {}
    parts = [str(receipt.get("status")), f"receipt {receipt.get('receipt_id')}"]
    if receipt.get("device_id"):
        parts.append(str(receipt.get("device_id")))
    if receipt.get("capability_id"):
        parts.append(str(receipt.get("capability_id")))
    if receipt.get("operation_id") and receipt.get("status") in ("accepted", "running", "unknown"):
        parts.append(f"operation {receipt.get('operation_id')}")
    if error:
        parts.append(f"{error.get('mhs_code')}: {error.get('message')}")
    return "  ".join(parts)


def _receipt_exit(receipt: Mapping[str, Any]) -> int:
    """0 for ``completed``/``accepted``/``running``; 4 for a refusal with ``MHS.AUTH.*``; 1 otherwise."""
    if receipt.get("status") in ("completed", "accepted", "running"):
        return EXIT_OK
    error = receipt.get("error") if isinstance(receipt.get("error"), Mapping) else {}
    return EXIT_AUTH if str(error.get("mhs_code") or "").startswith("MHS.AUTH.") else EXIT_REJECTED


# ---------------------------------------------------------------------------
# endpoint helpers
# ---------------------------------------------------------------------------


def _target(value: str) -> Any:
    """``http(s)://...``, ``mhs://host[:port]`` or ``stdio:<command>`` -> what :func:`mhs.connect` takes."""
    from .discovery import parse_target

    try:
        transport, url, command = parse_target(value)
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    return url if transport == "http" else command


def _read_token(path: str | None, *, flag: str) -> str | None:
    if not path:
        return None
    try:
        token = Path(path).expanduser().read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise UsageError(f"cannot read {flag} {path!r}: {exc}") from exc
    if not token:
        raise UsageError(f"{flag} {path!r} is empty")
    return token


def _connect(args: argparse.Namespace) -> Any:
    target = _target(args.endpoint)
    token = _read_token(getattr(args, "token_file", None), flag="--token-file")
    if token is not None:
        if not isinstance(target, str):
            raise UsageError("a bearer token needs an HTTP endpoint (a stdio pipe is authenticated when it is "
                             "launched)")
        return connect(target, token=token)
    return connect(target)


def _device_ids(client: Any) -> list[str]:
    return [str(item.get("device_id")) for item in client.devices()]


def _segments(device_id: str) -> list[str]:
    return [part for part in device_id.split("://", 1)[-1].split("/") if part]


def _match_device(ids: Sequence[str], wanted: str) -> str:
    """``--device`` among the listed ``ids``: the full id, or a unique segment of one.

    A full id (``...://...``) that is not listed is passed through for the
    endpoint to answer; an ambiguous or unknown short name raises
    ``MHS.HOST.DEVICE_AMBIGUOUS`` / ``MHS.DEVICE.UNKNOWN`` here, before
    anything is sent.
    """
    if wanted in ids:
        return wanted
    matches = [item for item in ids if wanted in _segments(item)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise MHSError("MHS.HOST.DEVICE_AMBIGUOUS", f"{wanted!r} names several devices: {', '.join(matches)}",
                       {"device": wanted, "candidates": matches})
    if "://" in wanted:
        return wanted
    raise MHSError("MHS.DEVICE.UNKNOWN", f"unknown device {wanted}" + (f" (one of: {', '.join(ids)})" if ids else ""),
                   {"device": wanted, "devices": list(ids)})


def _pick_device(client: Any, wanted: str | None, *, resource: str | None = None,
                 capability: str | None = None) -> str:
    """The device a command addresses: ``--device``, the only device, or the one serving ``resource``/``capability``."""
    manifests = client.devices()
    ids = [str(item.get("device_id")) for item in manifests]
    if wanted:
        return _match_device(ids, wanted)
    if len(ids) == 1:
        return ids[0]
    candidates = []
    for manifest in manifests:
        resources = {str(item.get("resource_id")) for item in manifest.get("resources") or []}
        capabilities = {str(item.get("capability_id")) for item in manifest.get("capabilities") or []}
        if (resource and resource in resources) or (capability and capability in capabilities):
            candidates.append(str(manifest.get("device_id")))
    if len(candidates) == 1:
        return candidates[0]
    raise UsageError(f"the endpoint serves {len(ids)} devices; pass --device (one of: {', '.join(ids)})")


def _parse_object(text: str | None, *, flag: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        if text.startswith("@"):
            with open(text[1:], "r", encoding="utf-8") as handle:
                value = json.load(handle)
        else:
            value = json.loads(text)
    except OSError as exc:
        raise UsageError(f"{flag}: cannot read {text[1:]!r}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"{flag} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise UsageError(f"{flag} must be a JSON object")
    return value


def _session(client: Any, args: argparse.Namespace, device_id: str) -> str:
    if getattr(args, "session_id", None):
        return str(args.session_id)
    opened = client.open_session([device_id], mode=getattr(args, "mode", None), ttl_s=getattr(args, "ttl", 600))
    return str(opened.get("session_id"))


# ---------------------------------------------------------------------------
# endpoint commands
# ---------------------------------------------------------------------------


def _cmd_hello(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        result = client.hello()
        if not args.json:
            result = {
                "endpoint_id": result.get("endpoint_id"),
                "mhs_version": result.get("mhs_version"),
                "server": result.get("server"),
                "devices": [d.get("device_id") for d in result.get("devices") or []],
                "features": result.get("features"),
                "conformance": result.get("conformance"),
            }
        _emit(result, as_json=args.json)
    return EXIT_OK


def _device_line(manifest: Mapping[str, Any]) -> str:
    safety = manifest.get("safety") if isinstance(manifest.get("safety"), Mapping) else {}
    count = len(manifest.get("capabilities") or [])
    mode = str(manifest.get("mode"))
    models = manifest.get("models") or []
    if models:
        mode += f" (models {', '.join(str(item) for item in models)})"
    name = manifest.get("display_name") or ""
    return f"{manifest.get('device_id')}  {mode}  {safety.get('risk_class', '-')}  {count} capabilities  {name}".rstrip()


def _cmd_devices(args: argparse.Namespace) -> int:
    if args.device_id:
        return _cmd_describe(args)
    with _connect(args) as client:
        devices = client.devices()
    if args.json:
        _print_json({"devices": devices})
    elif not devices:
        print("(no devices)")
    else:
        for manifest in devices:
            print(_device_line(manifest))
    return EXIT_OK


def _limit_text(path: str, rule: Any) -> str:
    if rule == "operator_required":
        return f"{path} operator_required"
    if not isinstance(rule, Mapping):
        return f"{path} {rule}"
    unit = f" {rule['unit']}" if rule.get("unit") else ""
    if "allowed" in rule:
        return f"{path} in {json.dumps(rule['allowed'])}{unit}"

    def show(value: Any) -> str:
        return json.dumps(value) if isinstance(value, list) else str(value)

    low, high = rule.get("min"), rule.get("max")
    if low is not None and high is not None:
        return f"{path} {show(low)}..{show(high)}{unit}"
    if low is not None:
        return f"{path} >= {show(low)}{unit}"
    if high is not None:
        return f"{path} <= {show(high)}{unit}"
    return f"{path}{unit}"


def _describe_lines(device: Mapping[str, Any], conformance: Sequence[Any] = ()) -> list[str]:
    safety = device.get("safety") if isinstance(device.get("safety"), Mapping) else {}
    estop = safety.get("estop") if isinstance(safety.get("estop"), Mapping) else {}
    safe_state = safety.get("safe_state") if isinstance(safety.get("safe_state"), Mapping) else {}
    fidelity = device.get("fidelity") if isinstance(device.get("fidelity"), Mapping) else {}
    reference = device.get("reference") if isinstance(device.get("reference"), Mapping) else {}
    lines = [f"{device.get('device_id')}  {device.get('display_name') or ''}".rstrip()]
    head = f"  mode: {device.get('mode')}   risk: {safety.get('risk_class', '-')}"
    if device.get("models"):
        head += f"   models: {', '.join(str(item) for item in device.get('models') or [])}"
    lines.append(head)
    claims = ", ".join(f"{item.get('profile')} {item.get('level')}" for item in conformance
                       if isinstance(item, Mapping)) or "none"
    lines.append(f"  trust: not certified (MHS.SAFETY.NOT_CERTIFIED); conformance claimed: {claims}")
    stop = f"  e-stop: {estop.get('kind', '-')}{', latching' if estop.get('latching') else ''}"
    if estop.get("native"):
        stop += f", native {estop.get('native')}"
    if estop.get("physical_ref"):
        stop += f", physical {estop.get('physical_ref')}"
    lines.append(stop)
    if safe_state:
        achieved = ", ".join(str(item) for item in safe_state.get("achieved_by") or [])
        lines.append(f"  safe state: {safe_state.get('description', '-')}" + (f" (by {achieved})" if achieved else ""))
    for interlock in safety.get("interlocks") or []:
        if isinstance(interlock, Mapping):
            needed = ", ".join(str(item) for item in interlock.get("required_for") or [])
            lines.append(f"  interlock: {interlock.get('id')}" + (f" (needed by {needed})" if needed else ""))
    lines.append("  capabilities:")
    for capability in device.get("capabilities") or []:
        if not isinstance(capability, Mapping):
            continue
        row = (f"    {str(capability.get('verb') or '-'):<7} {capability.get('capability_id')}  "
               f"[{capability.get('resource')}]")
        effective = capability.get("x-mhs-effective-limits")
        limits = effective.get("limits") if isinstance(effective, Mapping) else None
        if isinstance(limits, Mapping) and limits:
            row += "  limits: " + "; ".join(_limit_text(path, rule) for path, rule in sorted(limits.items()))
        if capability.get("requires_permit"):
            row += "  (permit)"
        lines.append(row)
    if fidelity:
        determinism = fidelity.get("determinism") if isinstance(fidelity.get("determinism"), Mapping) else {}
        gaps = "; ".join(str(item) for item in fidelity.get("gaps") or []) or "none declared"
        lines.append(f"  fidelity: {fidelity.get('engine', '-')} {fidelity.get('fidelity_level', '')}, "
                     f"determinism {determinism.get('kind', '-')}; gaps: {gaps}")
    for fact in reference.get("facts") or []:
        if isinstance(fact, Mapping):
            lines.append(f"  fact: {fact.get('text')} [{fact.get('source')} {fact.get('ref')}]")
    return lines


def _cmd_describe(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        hello = client.hello()
        ids = [_pick_device(client, args.device_id)] if args.device_id else _device_ids(client)
        devices = [client.inspect(device_id) for device_id in ids]
    if args.json:
        _print_json(devices[0] if args.device_id else {"devices": devices})
        return EXIT_OK
    conformance = hello.get("conformance") or []
    for index, device in enumerate(devices):
        if index:
            print()
        print("\n".join(_describe_lines(device, conformance)))
    return EXIT_OK


def _cmd_read(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        device_id = _pick_device(client, args.device_id, resource=args.resource)
        session_id = _session(client, args, device_id)
        result = client.read(args.resource, device_id=device_id, fields=args.field or None, session_id=session_id)
    _emit(result, as_json=args.json)
    return EXIT_OK


def _cmd_write(args: argparse.Namespace) -> int:
    patch = _parse_object(args.patch, flag="--patch")
    if not patch:
        raise UsageError("--patch must name at least one field")
    with _connect(args) as client:
        device_id = _pick_device(client, args.device_id, resource=args.resource)
        session_id = _session(client, args, device_id)
        receipt = client.write(args.resource, patch, device_id=device_id, session_id=session_id,
                               expected_revision=args.expected_revision, command_id=args.command_id,
                               deadline_ms=args.deadline_ms)
    if args.json:
        _print_json(receipt)
    else:
        print(_receipt_line(receipt))
    return _receipt_exit(receipt)


def _cmd_call(args: argparse.Namespace) -> int:
    payload = _parse_object(args.input, flag="--input")
    with _connect(args) as client:
        device_id = _pick_device(client, args.device_id, capability=args.capability)
        session_id = _session(client, args, device_id)
        receipt = client.invoke(
            args.capability,
            payload,
            device_id=device_id,
            session_id=session_id,
            expected_revision=args.expected_revision,
            deadline_ms=args.deadline_ms,
            command_id=args.command_id,
            permit_id=args.permit_id,
            wait=args.wait,
        )
    if args.json:
        _print_json(receipt)
    else:
        print(_receipt_line(receipt))
        if receipt.get("output") not in (None, {}):
            print(json.dumps(receipt.get("output"), sort_keys=True, ensure_ascii=False, default=str))
    return _receipt_exit(receipt)


def _cmd_session(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        device_ids = args.device_ids or _device_ids(client)
        result = client.open_session(device_ids, mode=args.mode, ttl_s=args.ttl)
        # The session outlives this process until its TTL: pass it to other commands as --session-id.
        client.session_id = None
    _emit(result, as_json=args.json)
    return EXIT_OK


def _cmd_estop(args: argparse.Namespace) -> int:
    """Stop every requested device; one device's failure never keeps the others from being stopped."""
    reason = args.reason or args.reason_text or "operator requested an emergency stop (mhs estop)"
    receipts: list[Mapping[str, Any]] = []
    errors: list[dict[str, Any]] = []
    failures: list[int] = []
    not_stopped: list[str] = []

    def fail(device: str, exc: MHSError) -> None:
        errors.append({"device": device, "error": _error_object(exc)})
        failures.append(exit_code_for(exc))
        not_stopped.append(device)

    with _connect(args) as client:
        ids = _device_ids(client)
        targets: list[str] = []
        # Every name is resolved before anything is sent; an unknown or ambiguous one is reported, not guessed.
        for name in args.device_ids or ids:
            try:
                device_id = _match_device(ids, name)
            except MHSError as exc:
                fail(name, exc)
                continue
            if device_id not in targets:
                targets.append(device_id)
        # No session and no mode: an e-stop never waits for one (plan 3.6).
        for device_id in targets:
            try:
                receipt = client.estop(reason, device_id=device_id)
            except MHSError as exc:
                fail(device_id, exc)
                continue
            receipts.append(receipt)
            if receipt.get("status") != "completed":
                failures.append(_receipt_exit(receipt) or EXIT_REJECTED)
                not_stopped.append(device_id)
    if args.json:
        _print_json({"receipts": receipts, "errors": errors})
    else:
        for receipt in receipts:
            print(_receipt_line(receipt))
        for item in errors:
            error = item["error"]
            print(f"mhs estop: {item['device']}: {error['mhs_code']}: {error['message']}", file=sys.stderr)
        if not_stopped:
            print(f"mhs estop: NOT stopped: {', '.join(not_stopped)}", file=sys.stderr)
        elif not receipts:
            print("mhs estop: the endpoint serves no device", file=sys.stderr)
    if not failures:
        return EXIT_OK if receipts else EXIT_REJECTED
    distinct = set(failures)
    return distinct.pop() if len(distinct) == 1 else EXIT_REJECTED


def _interactive() -> bool:
    """True when a person can answer on this terminal (stdin is a TTY)."""
    stream = sys.stdin
    try:
        return bool(stream is not None and stream.isatty())
    except (AttributeError, ValueError):
        return False


def _confirm(prompt: str) -> bool:
    sys.stderr.write(prompt)
    sys.stderr.flush()
    answer = sys.stdin.readline()
    return answer.strip().lower() == "reset"


def _cmd_reset(args: argparse.Namespace) -> int:
    target = _target(args.endpoint)
    if not isinstance(target, str):
        raise UsageError("reset needs an HTTP endpoint: the operator token is a bearer token (serve the device with "
                         "mhs serve <dir> --port N --operator-token-file F)")
    token = _read_token(args.operator_token_file, flag="--operator-token-file")
    if not _interactive():
        print("mhs reset: refused: releasing an e-stop latch needs a person at an interactive terminal "
              "(stdin is not a TTY); agents and scripts cannot reset", file=sys.stderr)
        return EXIT_AUTH
    with connect(target, token=token) as client:
        if args.device_id:
            device_id = _pick_device(client, args.device_id)
        else:
            ids = _device_ids(client)
            if len(ids) != 1:
                raise UsageError(f"reset releases one device: pass --device (one of: {', '.join(ids)})")
            device_id = ids[0]
        status = client.safety_status(device_id)
        sys.stderr.write(_status_line(status) + "\n")
        if not _confirm(f"Release the e-stop latch of {device_id}? The device does not resume; a new command is "
                        "needed. Type 'reset' to confirm: "):
            print("mhs reset: not confirmed; nothing was sent", file=sys.stderr)
            return EXIT_REJECTED
        session = client.open_session([device_id], mode=None, ttl_s=60, make_default=False,
                                      principal={"id": "operator:mhs-cli", "kind": "operator"})
        session_id = str(session.get("session_id"))
        try:
            receipt = client.reset(device_id, session_id=session_id)
        finally:
            try:
                client.close_session(session_id)
            except MHSError:
                pass
    if args.json:
        _print_json(receipt)
    else:
        print(_receipt_line(receipt))
    return _receipt_exit(receipt)


def _status_line(status: Mapping[str, Any]) -> str:
    estop = status.get("estop") if isinstance(status.get("estop"), Mapping) else {}
    engaged = bool(status.get("estop_engaged", estop.get("engaged")))
    interlocks = ",".join(f"{item.get('id')}={item.get('state')}" for item in status.get("interlocks") or []
                          if isinstance(item, Mapping)) or "-"
    return (f"{status.get('device_id')}  estop={'ENGAGED' if engaged else 'clear'}  interlocks={interlocks}  "
            f"mode={status.get('mode')}  risk={status.get('risk_class')}")


def _cmd_status(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        ids = [_pick_device(client, args.device_id)] if args.device_id else _device_ids(client)
        statuses = [client.safety_status(device_id) for device_id in ids]
    if args.json:
        _print_json(statuses[0] if args.device_id else {"devices": statuses})
    else:
        for status in statuses:
            print(_status_line(status))
    return EXIT_OK


def _cmd_safety(args: argparse.Namespace) -> int:
    """Deprecated spelling: ``safety`` = ``status``, ``--estop R`` = ``estop``, ``--reset`` = ``reset``."""
    if args.estop:
        args.reason, args.reason_text = args.estop, None
        args.device_ids = [args.device_id] if args.device_id else None
        return _cmd_estop(args)
    if args.reset:
        if not args.operator_token_file:
            raise UsageError("safety --reset needs --operator-token-file (use: mhs reset)")
        return _cmd_reset(args)
    return _cmd_status(args)


def _cmd_evidence(args: argparse.Namespace) -> int:
    with _connect(args) as client:
        bundle = client.export_evidence()
        if not (args.verify or args.ledger):
            _print_json(bundle)
            return EXIT_OK
        result: dict[str, Any] = dict(client.verify_evidence(bundle))
    if args.ledger:
        from .run import verify_ledger

        try:
            document = json.loads(Path(args.ledger).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise UsageError(f"cannot read --ledger {args.ledger!r}: {exc}") from exc
        result["ledger"] = verify_ledger(document, bundle)
        result["valid"] = bool(result.get("valid")) and bool(result["ledger"]["valid"])
    _print_json(result)
    return EXIT_OK if result.get("valid") else EXIT_REJECTED


# ---------------------------------------------------------------------------
# conformance, registry, discovery, code files
# ---------------------------------------------------------------------------


def _split_command(command: str) -> list[str]:
    import shlex

    parts = shlex.split(command)
    if not parts:
        raise UsageError("--command is empty")
    return parts


def _driver_factory(directory: str, backend: str) -> Any:
    from .adapter import close_server, load

    if backend == "hardware":
        raise UsageError("mhs conform runs a driver directory on its fake or sim backend; conformance on hardware "
                         "is an operator procedure (serve it, then mhs conform -e <url> --allow-actuation)")
    if not Path(directory).is_dir():
        raise UsageError(f"{directory} is not a directory")

    def factory() -> tuple[Any, Any]:
        server = load(directory, backend=backend)
        return server, (lambda: close_server(server))

    return factory


def _cmd_conform(args: argparse.Namespace) -> int:
    from .conformance import level_awarded, save_report
    from .conformance.suite import capping_tests, conformance_summary
    from .driver.spec import DriverDefinitionError

    chosen = [name for name in ("directory", "endpoint", "command", "reference") if getattr(args, name, None)]
    if len(chosen) != 1:
        raise UsageError("conform needs exactly one subject: a driver directory, --endpoint, --command or "
                         "--reference")
    required = args.require_level or args.level
    if required not in _LEVELS:
        raise UsageError(f"unknown level {required!r} (one of {', '.join(_LEVELS)})")
    options: dict[str, Any] = {"allow_actuation": args.allow_actuation, "read_only": args.read_only,
                               "fixtures": args.fixtures}
    try:
        if args.directory or args.reference:
            from .conformance.inprocess import reference_factory, run_suite_inprocess

            if args.directory:
                factory = _driver_factory(args.directory, args.backend)
            else:
                factory = reference_factory(args.reference, **({"test_profile": True} if args.test_profile else {}))
            report = run_suite_inprocess(factory, profile=args.profile, level=args.level, **options)
        else:
            from .conformance import run_suite

            if args.endpoint:
                client = _connect(args)  # --token-file: the bearer token of an authenticated HTTP endpoint
            else:
                if args.token_file:
                    raise UsageError("--token-file needs an HTTP --endpoint (a stdio pipe is authenticated when "
                                     "it is launched)")
                client = connect(_split_command(args.command))
            try:
                report = run_suite(client, profile=args.profile, level=args.level, **options)
            finally:
                client.close()
    except (DriverDefinitionError, PermissionError) as exc:
        print(f"mhs conform: the subject cannot be served: {exc}", file=sys.stderr)
        return EXIT_REJECTED
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    # With --json, stdout carries the report and nothing else; the notes go to stderr.
    notes = sys.stderr if args.json else sys.stdout
    if args.json:
        _print_json(report)
    else:
        print(conformance_summary(report))
    if args.output:
        saved = save_report(report, args.output, validate=False)
        print(f"report saved: {saved['path']} (digest {report.get('report_digest')})", file=notes)
    blocked, capping = capping_tests(report)
    listing = ", ".join(f"{test_id} ({status})" for test_id, status in capping)
    if level_awarded(report) is None:
        print(f"below target: no level achieved (CL0 is blocked by {listing}), required {required}", file=notes)
        return EXIT_BELOW_TARGET
    if _LEVELS.index(str(report.get("level_achieved"))) < _LEVELS.index(required) or (
            blocked is not None and _LEVELS.index(blocked) <= _LEVELS.index(required)):
        print(f"below target: achieved {report.get('level_achieved')}, required {required}"
              + (f"; capped by {listing}" if listing else ""), file=notes)
        return EXIT_BELOW_TARGET
    return EXIT_OK


def _cmd_registry(args: argparse.Namespace) -> int:
    from .registry import Registry

    registry = Registry.load(args.path)
    if args.stats:
        _emit({"records": len(registry), "stats": registry.stats, "generated_at": registry.generated_at},
              as_json=args.json)
        return EXIT_OK
    if args.package:
        record = registry.get(args.package)
        if record is None:
            print(f"package not found: {args.package}", file=sys.stderr)
            return EXIT_REJECTED
        _emit(record, as_json=args.json)
        return EXIT_OK
    records = registry.search(
        query=args.query, track=args.track, family=args.family, tier=args.tier,
        mode=args.mode, ring=args.ring, limit=args.limit,
    )
    _emit({"count": len(records), "records": records}, as_json=args.json)
    return EXIT_OK


_TRUST_NOTE = ("discovered does not mean trusted: nothing here authenticates an endpoint; authenticate before "
               "granting anything, and only an operator arms hardware")


def _cmd_discover(args: argparse.Namespace) -> int:
    from .discovery import EndpointsFileError, discover

    try:
        endpoints = discover(targets=args.endpoints or (), path=args.file, use_env=not args.no_env,
                             use_file=not args.no_file, probe_http=not args.no_probe, timeout=args.timeout)
    except EndpointsFileError as exc:
        print(f"mhs discover: invalid endpoints file {exc.path}:", file=sys.stderr)
        for problem in exc.problems[:10]:
            print(f"  {problem}", file=sys.stderr)
        return EXIT_USAGE
    except ValueError as exc:
        raise UsageError(str(exc)) from exc
    if args.json:
        _print_json({"endpoints": [item.to_dict() for item in endpoints], "trusted": False, "note": _TRUST_NOTE})
        return EXIT_OK
    if not endpoints:
        print("no endpoints configured (set MHS_ENDPOINTS, write ~/.mhs/endpoints.json, or pass -e)")
    for item in endpoints:
        devices = f"{len(item.devices)} device(s)" if item.devices else "devices unknown"
        line = f"{item.status:<18} {item.key}  {item.endpoint_id or '-'}  {devices}  [{','.join(item.sources)}]"
        if item.error:
            line += f"  {item.error.get('mhs_code')}"
        print(line)
        for warning in item.warnings:
            print(f"  warning: {warning}")
    print(_TRUST_NOTE)
    return EXIT_OK


def _cmd_run(args: argparse.Namespace) -> int:
    from .run import run_script

    try:
        code, path = run_script(args.script, args.args, ledger_dir=args.ledger_dir)
    except FileNotFoundError as exc:
        raise UsageError(str(exc)) from exc
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        summary = f"{len(document.get('receipt_ids') or [])} receipt(s), outcome {document.get('outcome')}"
    except (OSError, ValueError):
        summary = "unreadable"
    # The ledger path is absolute; show it relative to the caller's directory when it lies inside it.
    try:
        shown = str(path.relative_to(Path.cwd()))
    except (ValueError, OSError):
        shown = str(path)
    print(f"mhs run: ledger {shown} ({summary})", file=sys.stderr)
    return code


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

_FILE_SCHEMAS = {
    "mhs-adapter.json": "adapter.schema.json",
    "endpoints.json": "endpoints.schema.json",
    "reference.json": "reference.schema.json",
    "driver.lock.json": "driver-lock.schema.json",
    "check-report.json": "check-report.schema.json",
    "RESULT.json": "driver-result.schema.json",
    "bindings.json": "bindings.schema.json",
}
_KEY_SCHEMAS = (
    (("adapter_id", "bridges"), "adapter.schema.json"),
    (("report_digest", "tests"), "conformance-report.schema.json"),
    (("receipts", "head_digest"), "evidence-bundle.schema.json"),
    (("transports", "endpoint_id"), "endpoint-descriptor.schema.json"),
    (("endpoints",), "endpoints.schema.json"),
    (("receipt_id", "command_id"), "receipt.schema.json"),
    (("permit_id",), "permit.schema.json"),
    (("device_id", "capabilities"), "device.schema.json"),
    (("openmhs", "device", "safety"), "reference.schema.json"),
)


#: The schema error of a synthetic tutorial's lock (task.json ``upstream: null``), which the gate's G2 accepts.
_SYNTHETIC_LOCK_ERROR = "$.upstream: expected object, got null"


def _synthetic(directory: Path) -> bool:
    """True for a synthetic tutorial package (``task.json`` ``"upstream": null``, e.g. the thermostat)."""
    try:
        card = json.loads((directory / "task.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(card, dict) and "upstream" in card and card["upstream"] is None


def _schema_for(path: Path, document: Any, explicit: str | None) -> str:
    from .schema import default_store

    known = set(default_store().names())
    if explicit:
        name = explicit if explicit.endswith(".schema.json") else f"{explicit}.schema.json"
        if name not in known:
            raise UsageError(f"unknown schema {explicit!r}")
        return name
    declared = document.get("$schema") if isinstance(document, Mapping) else None
    if isinstance(declared, str) and declared.rsplit("/", 1)[-1] in known:
        return declared.rsplit("/", 1)[-1]
    if path.name in _FILE_SCHEMAS:
        return _FILE_SCHEMAS[path.name]
    if path.name.startswith("site-limits") and path.suffix == ".json":
        return "site-limits.schema.json"
    if isinstance(document, Mapping):
        for keys, name in _KEY_SCHEMAS:
            if all(key in document for key in keys):
                return name
    raise UsageError(f"cannot tell which schema {path} follows; pass --schema NAME (e.g. adapter, device, "
                     "reference, site-limits, endpoints)")


def _validate_file(path: Path, schema: str | None) -> tuple[str, list[str], list[str]]:
    from .schema import default_store

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return "json", [f"cannot be read as JSON: {exc}"], []
    name = _schema_for(path, document, schema)
    problems = [str(item) for item in default_store().validate(document, name)]
    notes: list[str] = []
    if name == "driver-lock.schema.json" and _synthetic(path.parent):
        problems = [item for item in problems if not item.endswith(_SYNTHETIC_LOCK_ERROR)]
        notes.append("synthetic tutorial (task.json upstream null): upstream null is accepted")
    if not problems and name == "adapter.schema.json":
        import copy

        from .driver.build import device_from_manifest

        for manifest in document.get("devices") or []:
            served = copy.deepcopy(manifest)
            served.pop("instance_id", None)
            try:
                device_from_manifest(served, None)
            except ValueError as exc:
                problems.append(f"device {manifest.get('device_id')}: strict mode refuses it: {exc}")
    elif not problems and name == "conformance-report.schema.json":
        from .conformance import validate_report

        problems.extend(str(item) for item in validate_report(document))
    elif not problems and name == "evidence-bundle.schema.json":
        from .evidence import verify_bundle

        report = verify_bundle(document)
        problems.extend(f"evidence: {item.get('mhs_code')}: {item.get('detail')}"
                        for item in report.get("errors") or [] if isinstance(item, Mapping))
    return name, problems, notes


def _validate_driver_dir(path: Path) -> tuple[str, list[str], list[str]]:
    from .driver.build import strict_findings
    from .driver.loader import driver_class, read_lock
    from .driver.package import stale_references
    from .driver.spec import DriverDefinitionError
    from .schema import default_store

    problems: list[str] = []
    notes: list[str] = []
    try:
        cls = driver_class(path)
    except DriverDefinitionError as exc:
        return "driver", [f"the driver does not resolve: {exc}"], notes
    lock, lock_problems = read_lock(path)
    if _synthetic(path):
        lock_problems = [item for item in lock_problems if not item.endswith(_SYNTHETIC_LOCK_ERROR)]
        notes.append("synthetic tutorial (task.json upstream null): no repository to pin")
    problems.extend(lock_problems)
    if lock is None and not lock_problems:
        notes.append("no driver.lock.json (a hardware backend at R2 or above needs one)")
    if getattr(cls, "_needs_instance", False):
        notes.append("simulator family: its contract is resolved when the backend opens (mhs serve, or the full "
                     "gate)")
    else:
        backends = getattr(cls, "backends", None) or {}
        for view in [None] + [name for name in ("fake", "sim") if name in backends]:
            label = view or "declared"
            try:
                findings = strict_findings(cls, backend=view)
            except DriverDefinitionError as exc:
                problems.append(f"{label} view: {exc}")
                continue
            for item in findings:
                (problems if getattr(item, "refuse", True) else notes).append(f"{label} view: {item.text()}")
        try:
            for name in stale_references(path):
                problems.append(f"{name} is missing or stale (run python3 -m mhs.driver reference {path})")
        except DriverDefinitionError as exc:
            problems.append(f"the reference file cannot be generated: {exc}")
    for overlay in sorted(path.glob("site-limits*.json")):
        try:
            document = json.loads(overlay.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{overlay.name}: cannot be read as JSON: {exc}")
            continue
        problems.extend(f"{overlay.name}: {item}"
                        for item in default_store().validate(document, "site-limits.schema.json"))
    notes.append(f"the full acceptance gate is: mhs driver check {path} --backend fake")
    return "driver", problems, notes


def _cmd_validate(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if path.is_dir():
        if (path / "driver.py").is_file():
            kind, problems, notes = _validate_driver_dir(path)
        elif (path / "mhs-adapter.json").is_file():
            path = path / "mhs-adapter.json"
            kind, problems, notes = _validate_file(path, args.schema)
        else:
            raise UsageError(f"{path} is neither a driver directory (driver.py) nor holds an mhs-adapter.json")
    elif path.is_file():
        kind, problems, notes = _validate_file(path, args.schema)
    else:
        raise UsageError(f"{path}: no such file or directory")
    if args.json:
        _print_json({"path": str(path), "kind": kind, "valid": not problems, "problems": problems, "notes": notes})
    else:
        print(f"{'OK' if not problems else 'INVALID'} {path} ({kind})")
        for problem in problems:
            print(f"  problem: {problem}")
        for note in notes:
            print(f"  note: {note}")
    return EXIT_OK if not problems else EXIT_REJECTED


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


def _token_map(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    """``auth_tokens`` of ``mhs serve``: the client token is an agent, the operator token an operator."""
    tokens: dict[str, dict[str, Any]] = {}
    client_token = _read_token(args.token_file, flag="--token-file")
    operator_token = _read_token(args.operator_token_file, flag="--operator-token-file")
    if client_token:
        tokens[client_token] = {"id": f"agent:{Path(args.token_file).stem}", "kind": "agent"}
    if operator_token:
        if operator_token == client_token:
            raise UsageError("the operator token must differ from the client token")
        tokens[operator_token] = {"id": f"operator:{Path(args.operator_token_file).stem}", "kind": "operator"}
    return tokens


def _serve_mcp(server: Any, args: argparse.Namespace) -> int:
    from .client import InProcessTransport, MHSClient
    from .mcp import MCPPolicy, MCPProjection, serve_stdio

    try:
        policy = MCPPolicy.load(args.mcp_config) if args.mcp_config else MCPPolicy.direct_launch()
    except (OSError, ValueError) as exc:
        raise UsageError(f"cannot load --mcp-config {args.mcp_config!r}: {exc}") from exc
    policy.operator_tools = policy.operator_tools or bool(args.operator_tools)
    policy.allow_external_sessions = policy.allow_external_sessions or bool(args.allow_external_sessions)
    client = MHSClient(InProcessTransport(server))
    client.hello()
    projection = MCPProjection(client, endpoint=str(args.target), policy=policy, describe_inputs=True)
    try:
        return serve_stdio(projection)
    finally:
        projection.close()


def _serve_reference(args: argparse.Namespace) -> int:
    from .reference import build_endpoint, build_server, serve as serve_reference

    for flag, value in (("--backend", args.backend), ("--site-limits", args.site_limits),
                        ("--state-dir", args.state_dir), ("--token-file", args.token_file),
                        ("--operator-token-file", args.operator_token_file), ("--allow-hardware", args.allow_hardware),
                        ("--arm", args.arm)):
        if value:
            raise UsageError(f"{flag} does not apply to the reference endpoint {args.target!r} (a loopback "
                             "protocol fixture); serve a driver directory instead")
    if args.target == "replay" and not args.bundle:
        raise UsageError("the replay endpoint needs --bundle <recorded evidence bundle .json>")
    if args.bundle and not Path(args.bundle).is_file():
        raise UsageError(f"--bundle {args.bundle!r} is not a file")
    options ={"test_profile": args.test_profile, "bundle": args.bundle, "noise": args.noise, "seed": args.seed}
    if args.mcp:
        spec = build_endpoint(args.target, endpoint_id=args.endpoint_id or f"mhs://localhost/{args.target}",
                              **options)
        try:
            return _serve_mcp(build_server(spec, log_ready=False), args)
        finally:
            spec.close()
    port = None if args.stdio else (args.port if args.port is not None else 7400)
    if port == 0:
        import socket

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((args.host, 0))
            port = int(sock.getsockname()[1])
    endpoint_id = args.endpoint_id or (f"mhs://localhost/{args.target}" if args.stdio else f"mhs://localhost:{port}")
    spec = build_endpoint(args.target, endpoint_id=endpoint_id, **options)
    serve_reference(spec, host=args.host, port=port, stdio=args.stdio)
    return EXIT_OK


def _install_sigterm() -> Any:
    """SIGTERM unwinds like Ctrl-C, so the server closes its state directory and drivers.

    Returns the previous handler (``None`` when nothing was installed).
    """
    if threading.current_thread() is not threading.main_thread():
        return None

    def _stop(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    try:
        return signal.signal(signal.SIGTERM, _stop)
    except (ValueError, OSError):  # pragma: no cover - platform without SIGTERM
        return None


def _restore_sigterm(previous: Any) -> None:
    if previous is None:
        return
    try:
        signal.signal(signal.SIGTERM, previous)
    except (ValueError, OSError, TypeError):  # pragma: no cover
        pass


def _load_error_exit(exc: BaseException) -> int:
    reason = getattr(exc, "reason", None)
    if reason in ("hardware_not_allowed", "review_required"):
        return EXIT_AUTH
    return EXIT_USAGE


def _cmd_serve(args: argparse.Namespace) -> int:
    modes = [flag for flag, value in (("--stdio", args.stdio), ("--port", args.port is not None),
                                      ("--mcp", args.mcp)) if value]
    if len(modes) > 1:
        raise UsageError(f"choose one of --stdio, --port N, --mcp (got {' '.join(modes)})")
    if (args.mcp or args.stdio) and (args.token_file or args.operator_token_file):
        raise UsageError("--token-file and --operator-token-file authenticate HTTP clients: use them with --port")
    mcp_only = [flag for flag, value in (("--mcp-config", args.mcp_config), ("--operator-tools", args.operator_tools),
                                         ("--allow-external-sessions", args.allow_external_sessions)) if value]
    if getattr(args, "artifacts", False) and (not args.mcp or args.target in _REFERENCE_NAMES):
        raise UsageError("--artifacts requires a driver directory or adapter with --mcp")
    if mcp_only and not args.mcp:
        raise UsageError(f"{', '.join(mcp_only)} apply to --mcp only")
    previous = _install_sigterm()
    try:
        if args.target in _REFERENCE_NAMES:
            try:
                return _serve_reference(args)
            except KeyboardInterrupt:
                return EXIT_OK
        return _serve_driver(args)
    finally:
        _restore_sigterm(previous)


def _serve_driver(args: argparse.Namespace) -> int:
    from .adapter import LoadError, close_server, load

    if not Path(args.target).exists():
        raise UsageError(f"{args.target} is neither a driver directory, an mhs-adapter.json nor one of "
                         f"{', '.join(_REFERENCE_NAMES)}")
    if args.arm and not args.allow_hardware:
        raise UsageError("--arm arms hardware actuation: it needs --backend hardware --allow-hardware")
    options: dict[str, Any] = {}
    tokens = _token_map(args)
    if tokens:
        options["auth_tokens"] = tokens
    if args.arm:
        options["armed"] = True
    if args.endpoint_id:
        options["endpoint_id"] = args.endpoint_id
    artifact_store = None
    if getattr(args, "artifacts", False):
        from .artifacts import LocalArtifactStore
        artifact_store = LocalArtifactStore()
        options["artifact_store"] = artifact_store
    loaded = False
    try:
        server = load(args.target, backend=args.backend or "fake", site_limits=args.site_limits,
                      allow_hardware=args.allow_hardware, state_dir=args.state_dir, **options)
        loaded = True
    except LoadError as exc:
        print(f"mhs serve: refused ({exc.reason}): {exc}", file=sys.stderr)
        return _load_error_exit(exc)
    except PermissionError as exc:
        print(f"mhs serve: refused: {exc}", file=sys.stderr)
        return EXIT_AUTH
    except ValueError as exc:
        print(f"mhs serve: the driver cannot be served: {exc}", file=sys.stderr)
        return EXIT_REJECTED
    finally:
        if artifact_store is not None and not loaded:
            artifact_store.close()
    try:
        if args.mcp:
            return _serve_mcp(server, args)
        if args.stdio:
            server.run_stdio()
            return EXIT_OK
        port = args.port if args.port is not None else 7400
        try:
            handle = server.start_http(args.host, port)
        except OSError as exc:
            print(f"mhs serve: cannot listen on {args.host}:{port}: {exc}", file=sys.stderr)
            return EXIT_TRANSPORT
        try:
            threading.Event().wait()
        finally:
            handle.shutdown()
        return EXIT_OK
    except KeyboardInterrupt:
        return EXIT_OK
    finally:
        close_server(server)


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"mhs {_ids.SDK_VERSION} ({_ids.PROJECT_NAME} spec {_ids.SPEC_VERSION}, protocol {MHS_VERSION})")
    return EXIT_OK


def _cmd_driver(_args: argparse.Namespace) -> int:  # pragma: no cover - main() delegates before parsing
    return EXIT_USAGE


# ---------------------------------------------------------------------------
# parser
# ---------------------------------------------------------------------------

_EPILOG = """\
exit codes: 0 ok; 1 refused or failed (receipt not completed, endpoint error, invalid document);
2 usage; 3 transport (unreachable, lost response); 4 authentication/authorisation;
5 conformance below target; 130 interrupted.  A receipt gives 0 or 1 by its status, except
a refusal with an MHS.AUTH.* code (4).
endpoints: http://host:port, mhs://host[:port], or "stdio:<launch command>".
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mhs",
        description=f"{_ids.PROJECT_NAME} command line: serve drivers, talk to endpoints, run code files. "
                    f"Open-source Model Hardware Standard. Documentation: {_ids.SITE_URL}",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"mhs {_ids.SDK_VERSION}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    def endpoint_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument("--endpoint", "-e", required=True,
                       help='http://host:port, mhs://host[:port], or "stdio:<launch command>" '
                            '(e.g. "stdio:python3 -m mhs serve MHS/sdk/examples/thermostat --stdio")')
        p.add_argument("--token-file", default=None, metavar="FILE",
                       help="file holding the bearer token for an HTTP endpoint")
        p.add_argument("--json", action="store_true", help="machine-readable output (the stable contract)")

    p = sub.add_parser("serve", help="serve a driver directory, an mhs-adapter.json or a reference endpoint",
                       description="Serve a driver directory or mhs-adapter.json (strict mode, mhs.adapter.load) "
                                   "or a reference protocol fixture (conveyor, lab, arm, replay). Default: HTTP on "
                                   "127.0.0.1:7400; --stdio for a pipe; --mcp for the MCP projection on stdio.")
    p.add_argument("target", help="driver directory, mhs-adapter.json, or conveyor|lab|arm|replay "
                                  "(write ./lab for a directory named lab)")
    p.add_argument("--backend", choices=("fake", "sim", "hardware"), default=None,
                   help="driver backend (default fake; only hardware drives the device)")
    p.add_argument("--allow-hardware", action="store_true",
                   help="operator decision: allow the hardware backend to start (needs --state-dir)")
    p.add_argument("--arm", action="store_true",
                   help="operator decision: arm hardware actuation (otherwise refused with "
                        "MHS.AUTH.HARDWARE_DISABLED)")
    p.add_argument("--site-limits", default=None, metavar="FILE", help="operator overlay (site-limits.json)")
    p.add_argument("--state-dir", default=None, metavar="DIR",
                   help="persist the e-stop latch, the evidence chain and the command journal here")
    p.add_argument("--stdio", action="store_true", help="serve newline-delimited JSON-RPC on stdin/stdout")
    p.add_argument("--port", type=int, default=None, help="serve HTTP on this port (0: a free port; default 7400)")
    p.add_argument("--mcp", action="store_true", help="serve the MCP projection on stdin/stdout")
    p.add_argument("--artifacts", action="store_true",
                   help="--mcp: enable bounded temporary image artifacts for this endpoint")
    p.add_argument("--host", default="127.0.0.1",
                   help="HTTP bind address (a non-loopback address needs --token-file)")
    p.add_argument("--token-file", default=None, metavar="FILE",
                   help="HTTP: bearer token clients must present (principal kind agent)")
    p.add_argument("--operator-token-file", default=None, metavar="FILE",
                   help="HTTP: the operator's bearer token (principal kind operator; mhs reset uses it)")
    p.add_argument("--endpoint-id", default=None, help="advertised endpoint id")
    p.add_argument("--mcp-config", default=None, metavar="FILE",
                   help="--mcp: host policy JSON (enabled, allow_hardware, operator_tools, allow_external_sessions)")
    p.add_argument("--operator-tools", action="store_true",
                   help="--mcp: list mhs__reset and mhs__permit (only for a connector a human operator drives)")
    p.add_argument("--allow-external-sessions", action="store_true",
                   help="--mcp: accept a session_id the projection did not open")
    p.add_argument("--test-profile", action="store_true", help="conveyor: add the x-cap.mhs-test.* hooks")
    p.add_argument("--noise", action="store_true", help="arm: seeded pose noise")
    p.add_argument("--seed", type=int, default=0, help="arm: noise seed")
    p.add_argument("--bundle", default=None, metavar="FILE", help="replay: the recorded evidence bundle")
    p.set_defaults(func=_cmd_serve)

    p = sub.add_parser("driver", help="driver package tools, same as python3 -m mhs.driver (check, reference, "
                                      "new, export, catalog)", add_help=False)
    p.add_argument("rest", nargs=argparse.REMAINDER)
    p.set_defaults(func=_cmd_driver)

    p = sub.add_parser("validate", help="validate a driver directory or a JSON document",
                       description="Check a driver directory (strict resolution, lock file, fresh reference files, "
                                   "site-limits) or a JSON document against its schema. The full gate is "
                                   "mhs driver check <dir> --backend fake.")
    p.add_argument("path", help="driver directory, mhs-adapter.json, reference.json, site-limits.json, ...")
    p.add_argument("--schema", default=None, help="schema name when it cannot be inferred (e.g. device)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("describe", aliases=["inspect"],
                       help="summarise devices: mode, risk, trust, safety, limits, fidelity gaps, facts")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_id", default=None)
    p.set_defaults(func=_cmd_describe)

    p = sub.add_parser("hello", help="negotiate the protocol and list devices")
    endpoint_arg(p)
    p.set_defaults(func=_cmd_hello)

    p = sub.add_parser("devices", help="list devices, one line each (--json: full manifests)")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_id", default=None, help="describe this device instead")
    p.set_defaults(func=_cmd_devices)

    def device_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--device", dest="device_id", default=None,
                       help="device id or a unique segment of it (default: the only, or the matching, device)")
        p.add_argument("--mode", default=None, help="session mode (default: the device's own)")
        p.add_argument("--session-id", default=None, help="use this open session instead of opening one")
        p.add_argument("--ttl", type=int, default=600, help="session TTL in seconds")

    p = sub.add_parser("read", help="read a resource state")
    endpoint_arg(p)
    p.add_argument("resource", help="resource_id")
    p.add_argument("--field", action="append", default=None, help="read only this field (repeatable)")
    device_args(p)
    p.set_defaults(func=_cmd_read)

    p = sub.add_parser("write", help="write named parameters of a resource (cap.device.configure.v1)")
    endpoint_arg(p)
    p.add_argument("resource", help="resource_id")
    p.add_argument("--patch", "-p", required=True, help="JSON object of fields, or @file")
    p.add_argument("--expected-revision", type=int, default=None)
    p.add_argument("--command-id", default=None)
    p.add_argument("--deadline-ms", type=int, default=30000)
    device_args(p)
    p.set_defaults(func=_cmd_write)

    p = sub.add_parser("call", help="invoke a capability")
    endpoint_arg(p)
    p.add_argument("--capability", "-c", required=True)
    p.add_argument("--input", "-i", default="{}", help="JSON input object, or @file")
    p.add_argument("--expected-revision", dest="expected_revision", type=int, default=None)
    p.add_argument("--command-id", dest="command_id", default=None)
    p.add_argument("--deadline-ms", dest="deadline_ms", type=int, default=60000)
    p.add_argument("--permit-id", default=None, help="a permit issued to --session-id")
    p.add_argument("--wait", action="store_true", help="follow a running operation to its final receipt")
    device_args(p)
    p.set_defaults(func=_cmd_call)

    p = sub.add_parser("session", help="open a session (it lives until its TTL; pass it as --session-id)")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_ids", action="append", default=None)
    p.add_argument("--mode", default=None)
    p.add_argument("--ttl", type=int, default=600)
    p.set_defaults(func=_cmd_session)

    p = sub.add_parser("estop", help="engage the e-stop (no session, no mode; every device unless --device)")
    endpoint_arg(p)
    p.add_argument("reason_text", nargs="?", default=None, metavar="REASON")
    p.add_argument("--reason", default=None)
    p.add_argument("--device", dest="device_ids", action="append", default=None,
                   help="stop only this device (repeatable; every named device that resolves is stopped even "
                        "when another name is unknown)")
    p.set_defaults(func=_cmd_estop)

    p = sub.add_parser("reset", help="release a latched e-stop (operator token, interactive terminal)")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_id", default=None)
    p.add_argument("--operator-token-file", required=True, metavar="FILE",
                   help="file holding the operator's bearer token")
    p.set_defaults(func=_cmd_reset)

    p = sub.add_parser("status", help="safety status: e-stop latch and interlocks, one line per device")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_id", default=None)
    p.set_defaults(func=_cmd_status)

    p = sub.add_parser("safety", help="deprecated: use status, estop and reset")
    endpoint_arg(p)
    p.add_argument("--device", dest="device_id", default=None)
    p.add_argument("--mode", default=None, help=argparse.SUPPRESS)
    p.add_argument("--estop", metavar="REASON", default=None)
    p.add_argument("--reset", action="store_true")
    p.add_argument("--operator-token-file", default=None, metavar="FILE")
    p.set_defaults(func=_cmd_safety)

    p = sub.add_parser("evidence", help="export or verify the evidence bundle (optionally against a run ledger)")
    endpoint_arg(p)
    p.add_argument("--verify", action="store_true")
    p.add_argument("--ledger", default=None, metavar="FILE",
                   help="also check that this .mhs-run ledger's receipts are in the verified bundle")
    p.set_defaults(func=_cmd_evidence)

    p = sub.add_parser("run", help="run a Python code file and write its ledger (.mhs-run/<id>.json)",
                       description="Run SCRIPT as __main__ with ARGS; every receipt of every client is recorded in "
                                   "the ledger. Exit code: the CLI table (1 when a receipt was not completed).")
    p.add_argument("--ledger-dir", default=".mhs-run", help="ledger directory (default .mhs-run)")
    p.add_argument("script")
    p.add_argument("args", nargs=argparse.REMAINDER)
    p.set_defaults(func=_cmd_run)

    p = sub.add_parser("discover", help="list endpoints from MHS_ENDPOINTS and ~/.mhs/endpoints.json, probed",
                       description="Discovered does not mean trusted: nothing here authenticates an endpoint.")
    p.add_argument("--endpoint", "-e", dest="endpoints", action="append", default=None,
                   help="an extra endpoint to probe (repeatable)")
    p.add_argument("--file", default=None,
                   help="endpoints file (default $MHS_ENDPOINTS_FILE or ~/.mhs/endpoints.json)")
    p.add_argument("--no-env", action="store_true", help="ignore MHS_ENDPOINTS")
    p.add_argument("--no-file", action="store_true", help="ignore the endpoints file")
    p.add_argument("--no-probe", action="store_true", help="do not fetch /.well-known/mhs.json")
    p.add_argument("--timeout", type=float, default=2.0, help="probe timeout in seconds")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_discover)

    p = sub.add_parser("conform", help="run the conformance suite; prints failing and capping test ids",
                       description="Subject: a driver directory (in process), --endpoint, --command or "
                                   "--reference. Exit 5 when the required level is not achieved.")
    p.add_argument("directory", nargs="?", default=None, help="driver directory (served in process)")
    p.add_argument("--endpoint", "-e", default=None)
    p.add_argument("--token-file", default=None, help="bearer token file for an authenticated --endpoint")
    p.add_argument("--command", default=None, help="stdio endpoint launch command")
    p.add_argument("--reference", choices=_REFERENCE_NAMES, default=None, help="a reference fixture, in process")
    p.add_argument("--test-profile", action="store_true", help="with --reference conveyor")
    p.add_argument("--backend", choices=("fake", "sim", "hardware"), default="fake",
                   help="driver directory backend (fake or sim)")
    p.add_argument("--profile", default="MHS-Sim", help="MHS-Sim | MHS-Device | MHS-Bridge")
    p.add_argument("--level", default="CL3", help="claimed level CL0..CL4")
    p.add_argument("--require-level", default=None, help="exit 5 unless this level is achieved (default --level)")
    p.add_argument("--output", "--out", "-o", dest="output", default=None, help="write the report JSON here")
    p.add_argument("--allow-actuation", action="store_true",
                   help="operator opt-in: actuating tests on hardware/hybrid devices (CON-031)")
    p.add_argument("--read-only", action="store_true", help="send no command at all (CON-022)")
    p.add_argument("--fixtures", default=None, help="fixture file with test inputs (JSON)")
    p.add_argument("--json", action="store_true", help="print the whole report")
    p.set_defaults(func=_cmd_conform)

    p = sub.add_parser("registry", help="query a local registry index")
    p.add_argument("--path", default="MHS/registry", help="registry index.json or directory")
    p.add_argument("--query", "-q", default=None)
    p.add_argument("--track", default=None)
    p.add_argument("--family", default=None)
    p.add_argument("--tier", default=None)
    p.add_argument("--mode", default=None)
    p.add_argument("--ring", type=int, default=None)
    p.add_argument("--package", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--stats", action="store_true")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_registry)

    p = sub.add_parser("version", help="print the SDK, specification and protocol versions")
    p.set_defaults(func=_cmd_version)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] == "driver":
        from .driver.__main__ import main as driver_main

        return int(driver_main(arguments[1:]))
    parser = build_parser()
    try:
        args = parser.parse_args(arguments)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else EXIT_USAGE
    if not getattr(args, "func", None):
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    try:
        return int(args.func(args))
    except UsageError as exc:
        print(f"mhs: usage error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except MHSError as exc:
        _report_error(exc, as_json=bool(getattr(args, "json", False)))
        return exit_code_for(exc)
    except KeyboardInterrupt:
        return EXIT_INTERRUPTED
    except BrokenPipeError:  # pragma: no cover - output closed early (| head)
        try:
            sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
        except OSError:
            pass
        return EXIT_REJECTED


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
