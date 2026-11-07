#!/usr/bin/env python3
"""OpenAI4S x OpenMHS acceptance demo -- one MCP client, one receipt chain.

OpenMHS is an independent open-source project, not affiliated with or endorsed
by Anthropic.

The integration path demonstrated here is **MCP**: OpenAI4S's own ``MCPManager``
spawns one ``python -m mhs.mcp`` server per endpoint and every discovery, read,
command, safety action and evidence export below is an MCP ``tools/call`` (the
evidence bundle is an MCP ``resources/read``).  The demo plays the operator: it
issues a permit and resets an e-stop, so its connectors are launched on the host
operator route (``--operator-tools``) with the demo's own temporary settings
document.  An agent connector row never carries that flag.

What this proves, with no LLM and no API key:

1. the MHS MCP connector is experimental and disabled by default; the demo
   explicitly enables it, then three MHS reference endpoints (conveyor over
   stdio, lab + arm over HTTP) are discovered by **one** ``MCPManager``;
2. sessions are least-privilege (one capability per session) and state is read;
3. a multi-device lab workflow runs (pipette transfer -> sample mover -> plate
   reader), the conveyor is stepped, a permit-gated diverter actuation runs, and
   the arm moves;
4. an e-stop blocks the next actuation with a coded safety refusal, and a lost
   receipt produces an ``unknown`` receipt that must be reconciled by reading
   state (never retried blindly);
5. the evidence chain is exported and verified offline;
6. the same lab endpoint is also driven through a second ``MCPManager``
   connection, replaying a command by ``command_id``; the retained receipt must
   agree. No native OpenAI4S tool registration is used anywhere in this demo.

Run::

    python3 integration/openai4s/demo/run_demo.py

Exit code 0 only when every checkpoint passes.  The report is written to
``integration/openai4s/demo/demo-report.json``.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_INTEGRATION = _HERE.parents[1]
_REPO_ROOT = _HERE.parents[3]
_SDK_SRC = _REPO_ROOT / "MHS" / "sdk" / "src"
_OPENAI4S_SRC = _REPO_ROOT / "work" / "openai4s-src"

_DEMO_DIR = _HERE.parent
for _path in (_INTEGRATION, _SDK_SRC, _OPENAI4S_SRC, _DEMO_DIR):
    text = str(_path)
    if text not in sys.path:
        sys.path.insert(0, text)

# MHS endpoints and the MCP connector are spawned as child processes: they
# inherit the environment, not this process's sys.path, so publish the source
# trees on PYTHONPATH as well (the README documents the same variable).
_PYTHONPATH_PARTS = [str(_SDK_SRC), str(_OPENAI4S_SRC)]
if os.environ.get("PYTHONPATH"):
    _PYTHONPATH_PARTS.append(os.environ["PYTHONPATH"])
os.environ["PYTHONPATH"] = os.pathsep.join(_PYTHONPATH_PARTS)

from openai4s_mhs.config import EndpointSpec, MHSConfig  # noqa: E402
from mcp_adapter import MCPHostAdapter  # noqa: E402
from openai4s_mhs.host import MHSHost, MHSHostError  # noqa: E402

REPORT_PATH = _HERE.parent / "demo-report.json"
READY_TIMEOUT_S = float(os.environ.get("MHS_DEMO_READY_TIMEOUT", "25"))
COMMAND_TIMEOUT_MS = 20_000


class DemoError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# checkpoints / report
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.checkpoints: list[dict] = []
        self.tool_calls: list[dict] = []
        self.receipts: list[dict] = []
        self.sdk_gaps: list[dict] = []

    def check(self, checkpoint_id: str, passed: bool, detail: str, **extra: Any) -> bool:
        entry = {"id": checkpoint_id, "passed": bool(passed), "detail": detail, **extra}
        self.checkpoints.append(entry)
        print(f"[{'PASS' if passed else 'FAIL'}] {checkpoint_id}: {detail}")
        return bool(passed)

    def gap(self, code: str, detail: str, **extra: Any) -> None:
        self.sdk_gaps.append({"code": code, "detail": detail, **extra})
        print(f"[GAP] {code}: {detail}")

    @property
    def ok(self) -> bool:
        return bool(self.checkpoints) and all(item["passed"] for item in self.checkpoints)


# ---------------------------------------------------------------------------
# subprocess helpers (bounded, never an unbounded wait)
# ---------------------------------------------------------------------------


def _public_argv(argv: list[str]) -> str:
    """An argv for the report: the interpreter by name, never a local path."""
    return " ".join(["python3" if part == sys.executable else str(part) for part in argv])


def _write_demo_settings(directory: Path, endpoints: list[EndpointSpec]) -> MHSConfig:
    """The demo's own settings document (never the operator's ~/.openai4s/mhs.json)."""
    path = directory / "mhs.json"
    document = {
        "enabled": True,
        "allow_hardware": False,
        "endpoints": [
            {"id": spec.id, "label": spec.label,
             **({"command": list(spec.command)} if spec.command else {"url": spec.url})}
            for spec in endpoints
        ],
        "command_timeout_ms": COMMAND_TIMEOUT_MS,
        "command_journal": str(directory / "commands.jsonl"),
        "host_ledger": str(directory / "host-ledger.jsonl"),
        "evidence_log": str(directory / "evidence.jsonl"),
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True), encoding="utf-8")
    return MHSConfig.load(path)


def _child_env() -> dict[str, str]:
    env = os.environ.copy()
    parts = [str(_SDK_SRC)]
    existing = env.get("PYTHONPATH")
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def _read_line(proc: subprocess.Popen, timeout: float) -> str | None:
    """Read one stdout line with a hard deadline; None on timeout/EOF."""
    box: "queue.Queue[str]" = queue.Queue()

    def reader() -> None:
        try:
            box.put(proc.stdout.readline() if proc.stdout is not None else "")
        except Exception:  # noqa: BLE001
            box.put("")

    threading.Thread(target=reader, name="demo-ready", daemon=True).start()
    try:
        line = box.get(timeout=timeout)
    except queue.Empty:
        return None
    if not line:
        return None
    return line


def _stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        pass
    for stream in (proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except Exception:  # noqa: BLE001
            pass


def _stderr_tail(proc: subprocess.Popen, limit: int = 800) -> str:
    try:
        if proc.stderr is not None and proc.poll() is not None:
            return proc.stderr.read()[-limit:]
    except Exception:  # noqa: BLE001
        pass
    return ""


def launch_http_endpoint(name: str, port: int, timeout: float = READY_TIMEOUT_S) -> dict:
    """Launch one HTTP reference endpoint and wait for its ready event."""
    argv = [sys.executable, "-m", "mhs.reference", name, "--port", str(port)]
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=_child_env(),
    )
    line = _read_line(proc, timeout)
    if line is None:
        tail = _stderr_tail(proc)
        _stop_process(proc)
        raise DemoError(
            f"{name} endpoint on port {port} did not become ready within {timeout:.0f}s"
            + (f": {tail}" if tail else "")
        )
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        _stop_process(proc)
        raise DemoError(f"{name} endpoint printed a non-JSON ready line: {line[:300]!r}") from exc
    if not payload.get("mhs_ready") or not payload.get("url"):
        _stop_process(proc)
        raise DemoError(f"{name} endpoint ready event is incomplete: {payload}")
    return {"name": name, "process": proc, "url": payload["url"], "ready": payload}


# ---------------------------------------------------------------------------
# MHSHost helpers
# ---------------------------------------------------------------------------


def find_device(devices: list[dict], endpoint_id: str, short_name: str) -> dict | None:
    for item in devices:
        if item.get("endpoint_id") != endpoint_id:
            continue
        device_id = str(item.get("device_id") or "")
        if device_id == short_name or device_id.endswith("/" + short_name):
            return item
    return None


def command(
    report: Report,
    host: MHSHost,
    device_id: str,
    capability_id: str,
    payload: dict,
    *,
    endpoint_id: str,
    tool: str = "mhs_command",
) -> dict:
    """Run one capability, capturing either a receipt or a coded refusal."""
    started = time.monotonic()
    call: dict[str, Any] = {
        "tool": tool,
        "arguments": {
            "device_id": device_id,
            "capability_id": capability_id,
            "input": payload,
            "endpoint_id": endpoint_id,
        },
    }
    try:
        receipt = host.command(
            device_id, capability_id, payload, endpoint_id=endpoint_id
        )
    except Exception as exc:  # noqa: BLE001 - both MHSHostError and MHSError
        code = str(getattr(exc, "code", "MHS.HOST.UNEXPECTED"))
        call.update(
            {
                "ok": False,
                "kind": "error",
                "mhs_code": code,
                "error": str(exc),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        report.tool_calls.append(call)
        return call
    receipt_error = receipt.get("error") or {}
    receipt_code = receipt_error.get("mhs_code") or receipt_error.get("code")
    call.update(
        {
            "ok": True,
            "kind": "receipt",
            "status": receipt.get("status"),
            "command_id": receipt.get("command_id"),
            "receipt_id": receipt.get("receipt_id"),
            "mhs_code": receipt_code,
            "evidence_digest": (receipt.get("evidence") or {}).get("digest"),
            "durability": receipt.get("durability"),
            "duration_ms": int((time.monotonic() - started) * 1000),
        }
    )
    report.tool_calls.append(call)
    report.receipts.append(
        {
            "endpoint_id": endpoint_id,
            "device_id": receipt.get("device_id") or device_id,
            "capability_id": capability_id,
            "command_id": receipt.get("command_id"),
            "receipt_id": receipt.get("receipt_id"),
            "status": receipt.get("status"),
            "mode": receipt.get("mode"),
            "state_hash_after": receipt.get("state_hash_after"),
            "evidence_digest": (receipt.get("evidence") or {}).get("digest"),
            "mhs_code": (receipt.get("error") or {}).get("mhs_code")
            or (receipt.get("error") or {}).get("code"),
            "replayed": receipt.get("replayed", False),
        }
    )
    return call


def error_code(record: dict) -> str:
    return str(record.get("mhs_code") or "")


# ---------------------------------------------------------------------------
# MCP path (OpenAI4S's real MCPManager against mhs.mcp)
# ---------------------------------------------------------------------------


def _find_mcp_tool(tools: list[dict], capability_id: str) -> dict | None:
    for tool in tools:
        blob = " ".join(
            str(tool.get(key) or "") for key in ("name", "description", "title")
        )
        if capability_id in blob:
            return tool
    for tool in tools:
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        if "capability_id" in (schema.get("properties") or {}):
            return tool
    for tool in tools:
        name = str(tool.get("name") or "")
        if "invoke" in name or "command" in name:
            return tool
    return None


def _mcp_arguments(
    tool: dict, device_id: str, capability_id: str, payload: dict, command_id: str
) -> dict:
    schema = tool.get("inputSchema") or tool.get("input_schema") or {}
    props = dict(schema.get("properties") or {})
    args: dict[str, Any] = {}
    if "device_id" in props:
        args["device_id"] = device_id
    if "capability_id" in props:
        args["capability_id"] = capability_id
        if "input" in props:
            args["input"] = payload
        elif "args" in props:
            args["args"] = payload
    elif "input" in props:
        args["input"] = payload
    elif "args" in props:
        args["args"] = payload
    else:
        for key, value in payload.items():
            if key in props or schema.get("additionalProperties") is not False:
                args[key] = value
    if "command_id" in props:
        args["command_id"] = command_id
    return args


def _walk_find(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for value in obj.values():
            found = _walk_find(value, key)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = _walk_find(value, key)
            if found is not None:
                return found
    return None


def mcp_interop(
    report: Report,
    *,
    lab_url: str,
    lab_device: str,
    capability_id: str,
    payload: dict,
    native: dict,
) -> bool:
    try:
        import mhs.mcp  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        return report.check(
            "mcp_interop",
            False,
            "SKIPPED-WITH-FAILURE: mhs.mcp (MCP projection) is missing from the SDK",
            missing=["MHS/sdk/src/mhs/mcp.py"],
            reason=str(exc),
        )
    try:
        from openai4s.mcp_client import MCPManager
    except Exception as exc:  # noqa: BLE001
        return report.check(
            "mcp_interop",
            False,
            "OpenAI4S MCP client unavailable",
            reason=str(exc),
        )

    config = {
        "id": "mhs-lab",
        "command": [
            sys.executable,
            "-m",
            "mhs.mcp",
            "--endpoint",
            lab_url,
        ],
        "transport": "stdio",
        "timeout": 30,
        "env": {
            "PYTHONPATH": os.pathsep.join([str(_SDK_SRC), str(_OPENAI4S_SRC)]),
            **(
                {"PYTHONDONTWRITEBYTECODE": os.environ["PYTHONDONTWRITEBYTECODE"]}
                if os.environ.get("PYTHONDONTWRITEBYTECODE")
                else {}
            ),
        },
    }
    manager = MCPManager()
    started = time.monotonic()
    try:
        tools = manager.list_tools("mhs-lab", config)
        tool_names = [str(item.get("name")) for item in tools if isinstance(item, dict)]
        report.tool_calls.append(
            {
                "tool": "call_mcp_tool",
                "arguments": {"server": "mhs-lab", "tool": "*", "action": "tools/list"},
                "ok": bool(tools),
                "kind": "mcp_list",
                "tools": tool_names,
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        tool = _find_mcp_tool(tools, capability_id)
        if tool is None:
            return report.check(
                "mcp_interop",
                False,
                "mhs.mcp exposed tools but none maps to the native capability",
                capabilities=capability_id,
                tools=tool_names,
            )
        command_id = str(native.get("command_id") or "")
        arguments = _mcp_arguments(tool, lab_device, capability_id, payload, command_id)
        schema = tool.get("inputSchema") or tool.get("input_schema") or {}
        declares_command_id = "command_id" in (schema.get("properties") or {})
        if declares_command_id:
            response = manager.call_tool("mhs-lab", config, str(tool.get("name")), arguments)
            command_id_channel = "arguments.command_id"
        else:
            # Keep the projection's standard envelope out of the capability input.
            arguments.pop("command_id", None)
            connection = manager.get("mhs-lab", config)
            response = _mcp_meta_call(
                connection, str(tool.get("name")), arguments, command_id
            )
            command_id_channel = "params._meta.command_id"
            report.gap(
                "MCP.COMMAND_ID_CHANNEL",
                "mhs.mcp only reads command_id from params._meta and does not declare it in "
                "the tool inputSchema; OpenAI4S's MCPManager.call_tool cannot send _meta, so "
                "the public two-argument call cannot replay idempotently (R9).",
            )
        text = str(response.get("text") or "")
        parsed = _parse_mcp_payload(response)
        mcp_command_id = _walk_find(parsed, "command_id")
        mcp_status = _walk_find(parsed, "status")
        report.tool_calls.append(
            {
                "tool": "call_mcp_tool",
                "arguments": {
                    "server": "mhs-lab",
                    "tool": tool.get("name"),
                    "args": arguments,
                },
                "ok": not response.get("is_error"),
                "kind": "mcp_call",
                "status": mcp_status,
                "command_id": mcp_command_id,
                "is_error": bool(response.get("is_error")),
                "duration_ms": int((time.monotonic() - started) * 1000),
            }
        )
        if response.get("is_error"):
            return report.check(
                "mcp_interop",
                False,
                "mhs.mcp tools/call returned isError=true",
                tool=tool.get("name"),
                text=text[:500],
            )
        agreed = bool(command_id) and str(mcp_command_id) == command_id
        return report.check(
            "mcp_interop",
            agreed,
            (
                f"same lab endpoint via MCPManager: {tool.get('name')} returned the "
                f"native command_id {command_id}"
                if agreed
                else "MCP receipt did not reconcile by command_id"
            ),
            tool=tool.get("name"),
            native_command_id=command_id,
            mcp_command_id=mcp_command_id,
            mcp_status=mcp_status,
            mcp_is_error=bool(response.get("is_error")),
            text=text[:800],
        )
    except Exception as exc:  # noqa: BLE001 - never hang or crash the demo here
        return report.check(
            "mcp_interop",
            False,
            f"MCP path failed: {exc}",
            error=repr(exc),
        )
    finally:
        try:
            manager.shutdown()
        except Exception:  # noqa: BLE001
            pass




def _mcp_meta_call(connection: Any, tool_name: str, arguments: dict, command_id: str) -> dict:
    """Send tools/call with the MCP-standard ``_meta.command_id`` retry token.

    OpenAI4S's ``MCPManager.call_tool`` exposes only ``(name, arguments)`` and
    cannot carry ``_meta``, and ``mhs.mcp`` currently reads command_id from
    ``_meta`` only.  Using the manager's own live connection keeps the real
    OpenAI4S transport and avoids executing the command a second time.
    """
    result = connection._request(  # noqa: SLF001 - the client has no _meta API
        "tools/call",
        {"name": tool_name, "arguments": dict(arguments), "_meta": {"command_id": command_id}},
    )
    if not isinstance(result, dict):
        raise RuntimeError("MCP tools/call returned a non-object result")
    parts = [
        str(block.get("text") or "")
        for block in result.get("content") or []
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return {"is_error": bool(result.get("isError")), "text": "\n".join(parts), "raw": result}


def _parse_mcp_payload(response: dict) -> Any:
    """Recover the machine-readable receipt from an MCP tool result.

    MHS's projection returns the receipt as a JSON text block (preceded by one
    human-readable summary line) and, when the client retains it, as
    ``structuredContent``.  OpenAI4S normalizes text blocks only, so both are
    accepted here and neither is trusted to be prose.
    """
    raw = response.get("raw") if isinstance(response, dict) else None
    if isinstance(raw, dict):
        structured = raw.get("structuredContent")
        if isinstance(structured, (dict, list)):
            return structured
    text = str((response or {}).get("text") or "")
    stripped = text.strip()
    if not stripped:
        return None
    candidates = [stripped]
    candidates.extend(line.strip() for line in reversed(stripped.splitlines()))
    for candidate in candidates:
        if not candidate.startswith(("{", "[")):
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


# ---------------------------------------------------------------------------
# evidence
# ---------------------------------------------------------------------------


def export_and_verify(report: Report, host: MHSHost, endpoint_ids: list[str]) -> dict:
    results: dict[str, dict] = {}
    all_valid = True
    for endpoint_id in endpoint_ids:
        try:
            bundle = host.evidence_export(endpoint_id)
            verification = host.evidence_verify(bundle, endpoint_id)
            valid = bool(verification.get("valid"))
            all_valid = all_valid and valid
            results[endpoint_id] = {
                "valid": valid,
                "checked": verification.get("checked"),
                "head_digest": verification.get("head_digest"),
                "count": bundle.get("count"),
                "errors": verification.get("errors") or [],
            }
        except Exception as exc:  # noqa: BLE001
            all_valid = False
            results[endpoint_id] = {
                "valid": False,
                "error": str(exc),
                "mhs_code": str(getattr(exc, "code", "MHS.HOST.UNEXPECTED")),
            }
    return {"valid": all_valid, "endpoints": results}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def run() -> int:
    started_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report = Report()
    processes: list[subprocess.Popen] = []
    host: MHSHost | None = None
    report_body: dict[str, Any] = {
        "demo": "openai4s-mhs",
        "project": "OpenMHS (independent draft; not affiliated with or endorsed by Anthropic)",
        "started_at": started_at,
        "python": sys.version.split()[0],
        "repo_root": ".",
        "route": "host operator route (mhs.mcp --operator-tools): the demo issues a permit "
                 "and resets an e-stop",
    }
    settings_dir = Path(tempfile.mkdtemp(prefix="openai4s-mhs-demo-"))
    lab_url = ""
    lab_device = ""
    lab_payload = {"source_well": "A1", "destination_well": "B1", "volume_ul": 25}
    lab_capability = "cap.fluid.transfer.v1"
    native_transfer: dict = {}
    evidence: dict = {"valid": False, "endpoints": {}}

    try:
        try:
            import mhs

            report_body["sdk"] = {
                "available": True,
                "version": str(getattr(mhs, "__version__", "")),
                "import_path": str(_SDK_SRC.relative_to(_REPO_ROOT)),
            }
            sdk_ok = report.check(
                "sdk_available", True, f"mhs SDK {getattr(mhs, '__version__', '')} importable"
            )
        except Exception as exc:  # noqa: BLE001
            report_body["sdk"] = {"available": False, "error": str(exc)}
            sdk_ok = report.check(
                "sdk_available",
                False,
                "MHS SDK is not importable; the demo cannot run",
                missing=["MHS/sdk/src/mhs/__init__.py (client/server)"],
            )
        if not sdk_ok:
            return finish(report, report_body, evidence)

        # -- endpoints ---------------------------------------------------
        lab = launch_http_endpoint("lab", 0)
        processes.append(lab["process"])
        try:
            arm = launch_http_endpoint("arm", 7400)
        except DemoError:
            arm = launch_http_endpoint("arm", 0)
        processes.append(arm["process"])
        lab_url = str(lab["url"])
        arm_url = str(arm["url"])

        endpoints = [
            EndpointSpec(
                id="conveyor",
                command=[
                    sys.executable,
                    "-m",
                    "mhs.reference",
                    "conveyor",
                    "--stdio",
                    "--test-profile",
                    "--quiet",
                ],
                label="conveyor workcell (stdio, host-managed)",
            ),
            EndpointSpec(id="lab", url=lab_url, label="lab bench (HTTP)"),
            EndpointSpec(id="arm", url=arm_url, label="2-DOF arm (HTTP)"),
        ]
        # -- experimental MCP integration gate ---------------------------
        # The integration is a standard MCP connector: experimental, disabled by
        # default, enabled by the operator.  The demo proves both halves.
        try:
            from openai4s_mhs.config import MHSConfig as _MHSConfig
            from openai4s_mhs.mcpconfig import connector_config as _connector_config

            default_doc = _connector_config(
                _MHSConfig(enabled=False, sync_openai4s=False, endpoints=endpoints)
            )
            report_body["mcp_integration"] = {
                "kind": "mcp",
                "experimental": True,
                "default_enabled": False,
                "transport": "mcp",
                "connector_ids": [entry["id"] for entry in default_doc["connectors"]],
            }
            report.check(
                "mcp_default_off",
                default_doc["enabled"] is False
                and len(default_doc["connectors"]) == len(endpoints)
                and all(entry["enabled"] is False for entry in default_doc["connectors"]),
                "MHS is an MCP connector, experimental and disabled by default "
                "(rows listed, connector disabled, no endpoint connection)",
                enabled=False,
            )
            enabled_doc = _connector_config(
                _MHSConfig(enabled=True, sync_openai4s=False, endpoints=endpoints)
            )
            report.check(
                "mcp_enabled_for_demo",
                enabled_doc["enabled"] is True
                and all(entry["enabled"] is True for entry in enabled_doc["connectors"]),
                "operator enabled the experimental MCP integration for this demo",
                enabled=True,
                connectors=[entry["id"] for entry in enabled_doc["connectors"]],
            )
        except Exception as exc:  # noqa: BLE001
            report.check("mcp_default_off", False, f"MCP connector settings unavailable: {exc}")

        report_body["endpoints"] = [
            {
                "id": spec.id,
                "label": spec.label,
                "transport": "stdio" if spec.command else "http",
                "target": spec.url or _public_argv(list(spec.command or [])),
                "ready": (
                    lab["ready"] if spec.id == "lab" else arm["ready"] if spec.id == "arm" else None
                ),
            }
            for spec in endpoints
        ]
        transports = {item["transport"] for item in report_body["endpoints"]}
        report.check(
            "endpoints_ready",
            len(endpoints) >= 3 and {"stdio", "http"} <= transports,
            f"{len(endpoints)} endpoints up ({', '.join(sorted(transports))})",
            endpoints=[item["id"] for item in report_body["endpoints"]],
        )

        # One MCP client for every endpoint.  The stdio conveyor is spawned by its
        # connector via `mhs.mcp --command`; the two HTTP endpoints are the
        # processes launched above.
        demo_config = _write_demo_settings(settings_dir, endpoints)
        host = MCPHostAdapter(demo_config, timeout=COMMAND_TIMEOUT_MS / 1000.0)

        # -- discovery ---------------------------------------------------
        devices = host.devices()
        report_body["devices"] = devices
        errors = [item for item in devices if "error" in item]
        capability_count = sum(len(item.get("capabilities") or []) for item in devices if "error" not in item)
        modes = sorted({str(item.get("mode")) for item in devices if "error" not in item})
        gaps_disclosed = all(
            item.get("fidelity") is not None and (item.get("fidelity") or {}).get("gaps")
            for item in devices
            if "error" not in item
        )
        report.check(
            "discovery",
            not errors and len(devices) >= 5 and capability_count >= 6 and gaps_disclosed,
            f"one host discovered {len(devices) - len(errors)} devices, "
            f"{capability_count} capabilities, modes={modes}, fidelity gaps disclosed",
            device_ids=[item.get("device_id") for item in devices if "error" not in item],
            errors=errors,
        )

        conveyor = find_device(devices, "conveyor", "conveyor-workcell")
        pipette = find_device(devices, "lab", "liquid-handler")
        mover = find_device(devices, "lab", "sample-mover")
        reader = find_device(devices, "lab", "plate-reader")
        arm_device = find_device(devices, "arm", "arm-2dof")
        found_all = all(item is not None for item in (conveyor, pipette, mover, reader, arm_device))
        if not report.check(
            "devices_resolved",
            found_all,
            "conveyor, pipette, sample mover, plate reader and arm are all addressable",
            missing=[
                name
                for name, item in (
                    ("conveyor", conveyor),
                    ("pipette", pipette),
                    ("mover", mover),
                    ("reader", reader),
                    ("arm", arm_device),
                )
                if item is None
            ],
        ):
            return finish(report, report_body, evidence)
        assert conveyor and pipette and mover and reader and arm_device
        lab_device = str(pipette["device_id"])

        # -- state reads (each opens a one-capability session) -----------
        reads: dict[str, Any] = {}
        for label, device in (
            ("conveyor", conveyor),
            ("pipette", pipette),
            ("mover", mover),
            ("reader", reader),
            ("arm", arm_device),
        ):
            try:
                try:
                    reads[label] = host.read(str(device["device_id"]))
                except Exception as exc:  # noqa: BLE001
                    if str(getattr(exc, "code", "")) not in (
                        "MHS.HOST.NO_READ_CAPABILITY",
                        "MHS.HOST.NO_RESOURCES",
                    ):
                        raise
                    from openai4s_mhs.tools import read_state

                    reads[label] = read_state(host, str(device["device_id"]))
                report.tool_calls.append(
                    {
                        "tool": "mhs_read",
                        "arguments": {"device_id": device["device_id"]},
                        "ok": True,
                        "kind": "read",
                        "status": "completed",
                    }
                )
            except Exception as exc:  # noqa: BLE001
                reads[label] = {"error": str(exc)}
                report.tool_calls.append(
                    {
                        "tool": "mhs_read",
                        "arguments": {"device_id": device["device_id"]},
                        "ok": False,
                        "kind": "read",
                        "error": str(exc),
                    }
                )
        report_body["state_reads"] = {key: value.get("state", value) for key, value in reads.items()}
        report.check(
            "state_reads",
            all("error" not in value for value in reads.values()),
            "read pipette, mover, reader, conveyor and arm state",
        )

        # -- lab workflow -------------------------------------------------
        transfer = command(
            report,
            host,
            lab_device,
            lab_capability,
            lab_payload,
            endpoint_id="lab",
        )
        move = command(
            report,
            host,
            str(mover["device_id"]),
            "cap.sample.move.v1",
            {"plate_id": "plate-001", "to": "reader"},
            endpoint_id="lab",
        )
        measure = command(
            report,
            host,
            str(reader["device_id"]),
            "cap.measure.spectrum.v1",
            {"plate_id": "plate-001", "wavelengths_nm": [600], "well_ids": ["B1"]},
            endpoint_id="lab",
        )
        lab_ok = all(
            call.get("status") == "completed" for call in (transfer, move, measure)
        )
        if transfer.get("kind") == "receipt":
            native_transfer = transfer
        report.check(
            "lab_workflow",
            lab_ok,
            "pipette A1->B1 25 uL, plate moved to reader, absorbance measured on B1",
            receipts=[
                {
                    "capability_id": call["arguments"].get("capability_id"),
                    "status": call.get("status"),
                    "receipt_id": call.get("receipt_id"),
                }
                for call in (transfer, move, measure)
            ],
        )

        # -- conveyor + permit-gated actuation ---------------------------
        step = command(
            report,
            host,
            str(conveyor["device_id"]),
            "cap.world.step.v1",
            {"ticks": 10},
            endpoint_id="conveyor",
        )
        valve = command(
            report,
            host,
            str(conveyor["device_id"]),
            "cap.actuation.valve.v1",
            {"gate": "divert"},
            endpoint_id="conveyor",
        )
        report.check(
            "conveyor_step",
            step.get("status") == "completed",
            "conveyor advanced 10 deterministic ticks",
        )
        report.check(
            "permit_gated_actuation",
            valve.get("status") == "completed",
            "permit-gated diverter actuation completed (the operator route issued the MHS permit)",
        )

        # -- arm ----------------------------------------------------------
        arm_move = command(
            report,
            host,
            str(arm_device["device_id"]),
            "cap.motion.joint_position.v1",
            {"joint_positions_deg": [25, 40]},
            endpoint_id="arm",
        )
        report.check(
            "arm_move",
            arm_move.get("status") == "completed",
            "2-DOF arm moved to joint positions [25, 40] deg",
        )

        # -- unknown outcome (lost receipt; read before any retry) --------
        inject = command(
            report,
            host,
            str(conveyor["device_id"]),
            "x-cap.mhs-test.fault_inject.v1",
            {"fault": "lost_receipt", "enabled": True},
            endpoint_id="conveyor",
        )
        lost = command(
            report,
            host,
            str(conveyor["device_id"]),
            "cap.world.step.v1",
            {"ticks": 1},
            endpoint_id="conveyor",
        )
        reconciled = host.read(str(conveyor["device_id"]))
        report_body["unknown_outcome"] = {
            "receipt": {
                "status": lost.get("status"),
                "receipt_id": lost.get("receipt_id"),
                "mhs_code": lost.get("mhs_code"),
            },
            "reconciled_state": reconciled.get("state"),
            "retried": False,
        }
        report.check(
            "unknown_outcome",
            inject.get("status") == "completed"
            and lost.get("status") == "unknown"
            and reconciled.get("revision") is not None,
            "lost receipt produced an unknown receipt; state re-read before any retry",
        )

        # -- safety rejection: e-stop blocks the next actuation ---------
        estop = host.estop(str(conveyor["device_id"]), "acceptance demo e-stop", "conveyor")
        report.receipts.append(
            {
                "endpoint_id": "conveyor",
                "device_id": estop.get("device_id"),
                "capability_id": "cap.device.estop.v1",
                "command_id": estop.get("command_id"),
                "receipt_id": estop.get("receipt_id"),
                "status": estop.get("status"),
                "mode": estop.get("mode"),
                "state_hash_after": estop.get("state_hash_after"),
                "evidence_digest": (estop.get("evidence") or {}).get("digest"),
            }
        )
        report.tool_calls.append(
            {
                "tool": "mhs_safety",
                "arguments": {"action": "estop", "device_id": conveyor["device_id"]},
                "ok": estop.get("status") == "completed",
                "kind": "receipt",
                "status": estop.get("status"),
                "receipt_id": estop.get("receipt_id"),
                "command_id": estop.get("command_id"),
            }
        )
        blocked = command(
            report,
            host,
            str(conveyor["device_id"]),
            "cap.world.step.v1",
            {"ticks": 1},
            endpoint_id="conveyor",
        )
        reset = host.reset(str(conveyor["device_id"]), "conveyor")
        report.receipts.append(
            {
                "endpoint_id": "conveyor",
                "device_id": reset.get("device_id"),
                "capability_id": "cap.device.reset.v1",
                "command_id": reset.get("command_id"),
                "receipt_id": reset.get("receipt_id"),
                "status": reset.get("status"),
                "mode": reset.get("mode"),
                "state_hash_after": reset.get("state_hash_after"),
                "evidence_digest": (reset.get("evidence") or {}).get("digest"),
            }
        )
        recovered = command(
            report,
            host,
            str(conveyor["device_id"]),
            "cap.world.step.v1",
            {"ticks": 1},
            endpoint_id="conveyor",
        )
        blocked_code = error_code(blocked)
        blocked_has_receipt = blocked.get("kind") == "receipt"
        report_body["safety_rejection"] = {
            "estop_receipt": {
                "receipt_id": estop.get("receipt_id"),
                "command_id": estop.get("command_id"),
                "evidence_digest": (estop.get("evidence") or {}).get("digest"),
                "status": estop.get("status"),
            },
            "blocked_actuation": {
                "kind": blocked.get("kind"),
                "status": blocked.get("status"),
                "mhs_code": blocked_code,
                "receipt": blocked_has_receipt,
            },
            "recovered_after_reset": recovered.get("status"),
        }
        if not blocked_has_receipt:
            report.gap(
                "SDK.SAFETY.REJECTED_RECEIPT",
                "server raises MHSError for e-stop/interlock/permit refusals instead of "
                "returning a chained `rejected` receipt (INTERFACE.md and spec SAFE-014/"
                "SAFE-030/SAFE-031 say receipt); the demo records the coded refusal and "
                "the e-stop receipt, which is the chained evidence for the refusal",
                mhs_code=blocked_code,
            )
        report.check(
            "safety_rejection",
            blocked_code in ("MHS.SAFETY.ESTOP_ENGAGED", "MHS.SAFETY.INTERLOCK_OPEN", "MHS.SAFETY.PERMIT_INVALID")
            and recovered.get("status") == "completed",
            f"e-stop receipt {estop.get('receipt_id')} chained; next actuation refused with {blocked_code}; "
            "reset restored operation",
        )

        # -- MCP least authority -----------------------------------------
        # The projection exposes one tool per (device, capability).  There is no
        # generic "control hardware" tool, so the model cannot address an
        # arbitrary capability on an arbitrary device; sessions are opened by the
        # projection per (device, capability) and are not exposed as a tool.
        generic_tools: list[str] = []
        capability_tools: list[str] = []
        device_bound = True
        for endpoint_id in host.connectors:
            for tool in host._tools(endpoint_id):  # noqa: SLF001 - demo inspection
                name = str(tool.get("name") or "")
                meta = tool.get("x-mhs") or {}
                capability_id = meta.get("capability_id")
                if capability_id:
                    capability_tools.append(name)
                    if not meta.get("device_id"):
                        device_bound = False
                elif name in ("mhs__command", "mhs__control_hardware", "mhs__execute"):
                    generic_tools.append(name)
        report.check(
            "mcp_least_authority",
            not generic_tools and bool(capability_tools) and device_bound,
            f"{len(capability_tools)} capability tools, each bound to one device; "
            "no generic hardware-control tool; permits gate the actuation",
            capability_tools=capability_tools,
            generic_tools=generic_tools,
        )

        # -- MCP path (same lab endpoint, same command_id) ---------------
        if native_transfer:
            mcp_ok = mcp_interop(
                report,
                lab_url=lab_url,
                lab_device=lab_device,
                capability_id=lab_capability,
                payload=lab_payload,
                native=native_transfer,
            )
        else:
            mcp_ok = report.check(
                "mcp_interop", False, "native lab transfer did not yield a receipt to reconcile"
            )
        report_body["mcp"] = {
            "ok": mcp_ok,
            "endpoint": lab_url,
            "reconciled_by": "command_id",
            "native_command_id": native_transfer.get("command_id"),
        }

        # -- evidence ----------------------------------------------------
        evidence = export_and_verify(report, host, ["conveyor", "lab", "arm"])
        report_body["evidence"] = evidence
        heads = {
            name: value.get("head_digest")
            for name, value in evidence["endpoints"].items()
            if value.get("head_digest")
        }
        report_body["evidence_head_digest"] = heads.get("lab") or next(iter(heads.values()), None)
        report.check(
            "evidence_verified",
            bool(evidence["valid"])
            and len(heads) == 3
            and all((value.get("checked") or 0) >= 1 for value in evidence["endpoints"].values()),
            "three endpoint evidence chains exported and verified offline",
            heads=heads,
        )

        ledger = host.ledger()
        recorded = sum(1 for call in report.receipts if call.get("receipt_id"))
        report.check(
            "receipt_ledger",
            len(ledger) >= recorded and recorded >= 6,
            f"host ledger holds {len(ledger)} receipts; demo recorded {recorded}",
        )

    except Exception as exc:  # noqa: BLE001 - always emit a report
        report_body["error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc()[-4000:],
        }
        report.check("demo_completed", False, f"demo aborted: {type(exc).__name__}: {exc}")
    finally:
        if host is not None:
            try:
                host.close()
            except Exception:  # noqa: BLE001
                pass
        for proc in processes:
            _stop_process(proc)
        shutil.rmtree(settings_dir, ignore_errors=True)

    return finish(report, report_body, evidence)


def finish(report: Report, report_body: dict, evidence: dict) -> int:
    report_body.update(
        {
            "finished_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ok": report.ok,
            "checkpoints": report.checkpoints,
            "tool_calls": report.tool_calls,
            "receipts": report.receipts,
            "evidence": evidence,
            "sdk_gaps": report.sdk_gaps,
        }
    )
    report_body.setdefault("evidence_head_digest", None)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = REPORT_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(report_body, handle, indent=2, sort_keys=True)
    os.replace(tmp, REPORT_PATH)
    print()
    print(f"report: {REPORT_PATH}")
    print(f"checkpoints: {sum(1 for c in report.checkpoints if c['passed'])}/{len(report.checkpoints)} passed")
    print(f"receipts: {len(report.receipts)} | evidence head: {report_body.get('evidence_head_digest')}")
    if not report.ok:
        failed = [c["id"] for c in report.checkpoints if not c["passed"]]
        print(f"FAILED checkpoints: {', '.join(failed) or 'none'}")
    else:
        print("ACCEPTANCE: PASS")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(run())
