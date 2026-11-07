"""Governed MCP invocation: durable command ids, UNKNOWN, replay (HOST-003).

The bare OpenAI4S transport (``CallMCPTool`` -> ``MCPService`` -> ``MCPManager``)
has no command id before dispatch, no durable journal and no reconciliation
gate.  This module is the governed wrapper; the stock host route invokes it
through ``hostroute.py``/``host/mcp.py`` for an MHS capability tool, so the
governance sits on the real route.  It still works directly through the *real*
MCP connector (``mhs.mcp`` over stdio, the OpenAI4S ``MCPConnection`` class):

* allocate a ``command_id`` and append it to a JSONL journal **before** the
  mutating ``tools/call`` (and fsync by default);
* a connection/handshake failure before dispatch is a *pre-send* failure: no
  command was sent, so a retry is safe;
* a timeout/transport failure after the dispatch marker is an ambiguous
  physical outcome, and so is an ``isError`` result whose ``mhs_error`` says
  ``may_have_effect: true`` (or whose code is ``MHS.OUTCOME.TIMEOUT``/
  ``MHS.OUTCOME.UNKNOWN``: the projection sent the command and lost the
  answer).  It raises :class:`MCPOutcomeUnknown` with ``MHS.OUTCOME.UNKNOWN``,
  the command id, ``reconcile_required=true`` and is recorded in the host
  ledger.  It is never reported as a generic retryable infrastructure error;
* a ``running``/``accepted`` receipt (long-running work, plan 3.7) is journaled
  ``in_flight`` with its ``operation_id`` and returned; the device's gate stays
  shut until the operation is settled (``invoke_via`` reads it with
  ``mhs__operations`` on the same connection; :func:`reconcile` uses the
  endpoint evidence);
* the endpoint ``deadline_ms`` is shorter than the transport timeout
  (:func:`_endpoint_deadline_ms`), so a ``running``/``unknown`` receipt arrives
  before the MCP client gives up;
* a retry with the same ``command_id`` is sent unchanged to the endpoint.  MHS
  idempotency ``(device_id, command_id)`` returns the retained receipt with
  ``replayed: true`` and performs no second effect;
* :func:`reconcile` reads state, operations and the endpoint evidence (the
  MCP resource ``mhs://<endpoint>/evidence``) through the same MCP path.

The wrapper also accepts a :class:`~openai4s_mhs.host_evidence.HostLedger` and
appends an intent record before dispatch and an outcome record after (including
``unknown``/``pre_send_error``).  A ledger write failure is **visible**: a
pre-dispatch failure aborts the call, a post-dispatch failure raises with the
receipt attached.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

try:  # POSIX advisory locking for the shared journal file
    import fcntl as _fcntl
except ImportError:  # pragma: no cover - Windows
    _fcntl = None  # type: ignore[assignment]
try:  # pragma: no cover - Windows
    import msvcrt as _msvcrt
except ImportError:
    _msvcrt = None  # type: ignore[assignment]

from mhs import canonical

from .config import MHSConfig
from .host_evidence import HostLedger, HostLedgerError
from .mcpconfig import connector_entry, connector_env, connector_id

__all__ = [
    "CommandJournal",
    "MCPConnector",
    "MCPInvokeError",
    "MCPOutcomeUnknown",
    "export_evidence",
    "invoke",
    "invoke_via",
    "read_evidence",
    "reconcile",
]

#: Environment variables a spawned mhs.mcp child needs; secrets are not copied.
_CONNECTOR_ENV = (
    "PATH",
    "HOME",
    "USERPROFILE",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TMPDIR",
    "TMP",
    "TEMP",
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
    "PYTHONPATH",
    "PYTHONHOME",
    "PYTHONDONTWRITEBYTECODE",
    "VIRTUAL_ENV",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)

_RESERVED_ARGUMENTS = frozenset(
    {"session_id", "permit_id", "command_id", "expected_revision", "deadline_ms"}
)
#: ``isError`` codes after which the command may have been applied.
_AMBIGUOUS_CODES = frozenset({"MHS.OUTCOME.UNKNOWN", "MHS.OUTCOME.TIMEOUT"})
#: Receipt statuses of a command the endpoint is still executing (plan 3.7).
_IN_FLIGHT_STATUSES = frozenset({"accepted", "running"})


class MCPInvokeError(RuntimeError):
    """A governed-invocation failure with a stable code and retry semantics."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
        command_id: str | None = None,
        retry_safe: bool = False,
        reconcile_required: bool = False,
        receipt: Mapping[str, Any] | None = None,
        journal: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = str(message)
        self.details = dict(details or {})
        self.command_id = command_id
        self.retry_safe = bool(retry_safe)
        self.reconcile_required = bool(reconcile_required)
        self.receipt = dict(receipt) if isinstance(receipt, Mapping) else None
        self.journal = dict(journal) if isinstance(journal, Mapping) else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.message,
            "mhs_code": self.code,
            "command_id": self.command_id,
            "retry_safe": self.retry_safe,
            "reconcile_required": self.reconcile_required,
            "details": self.details,
        }


class MCPOutcomeUnknown(MCPInvokeError):
    """The command may have physically applied; observe before anything else."""

    def __init__(
        self,
        message: str,
        *,
        command_id: str,
        details: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
        journal: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(
            "MHS.OUTCOME.UNKNOWN",
            message,
            details=details,
            command_id=command_id,
            retry_safe=False,
            reconcile_required=True,
            receipt=receipt,
            journal=journal,
        )


#: A ``dispatching`` marker with no terminal record is only *live* while this
#: process is actually inside that call.  The registry is deliberately keyed by
#: (normalised journal path, command id): a new journal object, a new process or
#: an injected BaseException all lose the entry, so the durable ``dispatching``
#: record is then reconstructed as UNKNOWN instead of being trusted as in-flight.
_LIVE_DISPATCH: dict[tuple[str, str], int] = {}
_LIVE_DISPATCH_LOCK = threading.Lock()

_JOURNAL_LOCKS: dict[str, threading.RLock] = {}
_JOURNAL_LOCKS_GUARD = threading.Lock()


def _normalise_journal_path(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.realpath(os.path.expanduser(os.fspath(path))))


def _journal_thread_lock(path: Path) -> threading.RLock:
    key = str(path)
    with _JOURNAL_LOCKS_GUARD:
        lock = _JOURNAL_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _JOURNAL_LOCKS[key] = lock
        return lock


class _JournalFileLock:
    """Serialize append/read of one journal across threads and processes.

    The journal is the recovery source of truth; a torn line must never be
    produced by two concurrent governed calls that happen to share the path
    (one journal per host, many endpoints).  The lock is a sidecar, so the
    journal remains a plain append-only JSONL file.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_path = path.with_name(path.name + ".lock")
        self._thread_lock = _journal_thread_lock(path)
        self._handle: Any = None

    def __enter__(self) -> "_JournalFileLock":
        self._thread_lock.acquire()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._handle = open(self.lock_path, "a+b")
            if _fcntl is not None:
                _fcntl.flock(self._handle.fileno(), _fcntl.LOCK_EX)
            elif _msvcrt is not None:  # pragma: no cover - Windows
                if os.fstat(self._handle.fileno()).st_size == 0:
                    self._handle.write(b"\0")
                    self._handle.flush()
                self._handle.seek(0)
                _msvcrt.locking(self._handle.fileno(), _msvcrt.LK_LOCK, 1)
        except BaseException:
            if self._handle is not None:
                self._handle.close()
            self._thread_lock.release()
            raise
        return self

    def __exit__(self, *exc: Any) -> None:
        try:
            if self._handle is not None:
                if _fcntl is not None:
                    _fcntl.flock(self._handle.fileno(), _fcntl.LOCK_UN)
                elif _msvcrt is not None:  # pragma: no cover - Windows
                    self._handle.seek(0)
                    _msvcrt.locking(self._handle.fileno(), _msvcrt.LK_UNLCK, 1)
                self._handle.close()
        finally:
            self._handle = None
            self._thread_lock.release()


class CommandJournal:
    """Append-only JSONL journal of command ids written before dispatch.

    The journal *is* the recoverable state machine for one governed command::

        allocated -> prepared -> dispatching -> <terminal>
                                              \\-> unknown

    ``terminal`` is ``completed``/``receipt``/``tool_error``/``pre_send_error``.
    A ``dispatching`` record with no terminal record means the process may have
    died between the endpoint effect and the host's receipt append; on reload it
    is reconstructed as UNKNOWN (``reconcile_required=true``).  ``allocated``
    and ``prepared`` alone are pre-send: nothing left the host, so they do not
    block a retry.

    A torn or unparsable tail fails closed: the journal raises
    ``MHS.HOST.JOURNAL_CORRUPT`` rather than skipping the dangerous record.
    """

    TERMINAL_PHASES = frozenset(
        {"completed", "receipt", "tool_error", "pre_send_error"}
    )

    def __init__(self, path: str | os.PathLike[str], *, fsync: bool = True) -> None:
        self.path = _normalise_journal_path(path)
        self.fsync = bool(fsync)

    # -- durable primitives -------------------------------------------------
    def append(self, record: Mapping[str, Any]) -> dict[str, Any]:
        entry = {str(key): value for key, value in record.items()}
        entry.setdefault("ts", canonical.now_rfc3339())
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n"
        try:
            with _JournalFileLock(self.path):
                if self.path.exists() and self.path.stat().st_size:
                    with open(self.path, "rb") as existing:
                        existing.seek(-1, os.SEEK_END)
                        if existing.read(1) != b"\n":
                            raise MCPInvokeError(
                                "MHS.HOST.JOURNAL_CORRUPT",
                                "command journal ends with a torn record; "
                                "refusing to append past it",
                                details={"path": str(self.path)},
                            )
                with open(self.path, "a", encoding="utf-8") as handle:
                    handle.write(line)
                    handle.flush()
                    if self.fsync:
                        os.fsync(handle.fileno())
        except OSError as exc:
            raise MCPInvokeError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED",
                f"command journal append failed: {exc}",
                details={"path": str(self.path)},
            ) from exc
        return entry

    def records(self) -> list[dict[str, Any]]:
        """Read every record; a torn/corrupt journal fails closed.

        The predecessor skipped undecodable lines, which is exactly how a
        half-written ``dispatching`` record disappeared from the recovery gate.
        """
        if not self.path.exists():
            return []
        try:
            with _JournalFileLock(self.path):
                raw = self.path.read_bytes()
        except OSError as exc:
            raise MCPInvokeError(
                "MHS.HOST.JOURNAL_CORRUPT",
                f"command journal could not be read: {exc}",
                details={"path": str(self.path)},
            ) from exc
        if raw and not raw.endswith(b"\n"):
            raise MCPInvokeError(
                "MHS.HOST.JOURNAL_CORRUPT",
                "command journal ends with a torn record (no trailing newline); "
                "refusing to infer that no command was dispatched",
                details={
                    "path": str(self.path),
                    "recovery": "inspect the journal, reconcile the affected "
                    "device, then quarantine the journal",
                },
            )
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MCPInvokeError(
                "MHS.HOST.JOURNAL_CORRUPT",
                f"command journal is not UTF-8: {exc}",
                details={"path": str(self.path)},
            ) from exc
        entries: list[dict[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise MCPInvokeError(
                    "MHS.HOST.JOURNAL_CORRUPT",
                    f"command journal line {line_number} is not valid JSON: {exc.msg}",
                    details={
                        "path": str(self.path),
                        "line": line_number,
                        "recovery": "inspect the journal, reconcile the affected "
                        "device, then quarantine the journal",
                    },
                ) from exc
            if not isinstance(item, dict):
                raise MCPInvokeError(
                    "MHS.HOST.JOURNAL_CORRUPT",
                    f"command journal line {line_number} is not a JSON object",
                    details={"path": str(self.path), "line": line_number},
                )
            entries.append(item)
        return entries

    # -- live-dispatch registry --------------------------------------------
    def _live_key(self, command_id: str) -> tuple[str, str]:
        return (str(self.path), str(command_id))

    def mark_live(self, command_id: str) -> None:
        key = self._live_key(command_id)
        with _LIVE_DISPATCH_LOCK:
            _LIVE_DISPATCH[key] = _LIVE_DISPATCH.get(key, 0) + 1

    def clear_live(self, command_id: str) -> None:
        key = self._live_key(command_id)
        with _LIVE_DISPATCH_LOCK:
            remaining = _LIVE_DISPATCH.get(key, 0) - 1
            if remaining > 0:
                _LIVE_DISPATCH[key] = remaining
            else:
                _LIVE_DISPATCH.pop(key, None)

    def is_live(self, command_id: str) -> bool:
        with _LIVE_DISPATCH_LOCK:
            return _LIVE_DISPATCH.get(self._live_key(command_id), 0) > 0

    # -- state machine ------------------------------------------------------
    @staticmethod
    def _command_states(
        records: Sequence[Mapping[str, Any]], endpoint_id: str, device_id: str
    ) -> list[tuple[str, str, dict[str, Any], list[dict[str, Any]]]]:
        ordered: list[str] = []
        grouped: dict[str, list[dict[str, Any]]] = {}
        for item in records:
            if item.get("kind") != "command_dispatch":
                continue
            if str(item.get("endpoint_id")) != str(endpoint_id):
                continue
            if str(item.get("device_id")) != str(device_id):
                continue
            command_id = str(item.get("command_id") or "")
            if not command_id:
                continue
            if command_id not in grouped:
                grouped[command_id] = []
                ordered.append(command_id)
            grouped[command_id].append(dict(item))
        states: list[tuple[str, str, dict[str, Any], list[dict[str, Any]]]] = []
        for command_id in ordered:
            items = grouped[command_id]
            terminal = [
                item for item in items if item.get("phase") in CommandJournal.TERMINAL_PHASES
            ]
            unknown = [item for item in items if item.get("phase") == "unknown"]
            in_flight = [item for item in items if item.get("phase") == "in_flight"]
            dispatching = [item for item in items if item.get("phase") == "dispatching"]
            if terminal:
                state, record = "terminal", terminal[-1]
            elif unknown:
                state, record = "unknown", unknown[-1]
            elif in_flight:
                # The endpoint answered ``running``/``accepted``: sent, not final.
                state, record = "in_flight", in_flight[-1]
            elif dispatching:
                state, record = "dispatching", dispatching[-1]
            elif any(item.get("phase") in ("allocated", "prepared") for item in items):
                # Pre-send: no endpoint call was made, so this is a safe retry.
                state, record = "presend", items[-1]
            else:
                # An unrecognised phase cannot be proven pre-send.
                state, record = "unknown", items[-1]
            states.append((command_id, state, record, items))
        return states

    def _reconciled_ids(
        self,
        records: Sequence[Mapping[str, Any]],
        endpoint_id: str,
        device_id: str,
    ) -> set[str]:
        resolved: set[str] = set()
        for item in records:
            if item.get("kind") != "command_reconcile":
                continue
            if str(item.get("endpoint_id")) != str(endpoint_id):
                continue
            if str(item.get("device_id")) != str(device_id):
                continue
            ids = item.get("resolved_command_ids")
            if ids is None:
                # Only an explicit reconciled outcome may close a command; an
                # inconclusive observation is evidence, not permission.
                if item.get("outcome") == "reconciled":
                    ids = item.get("command_ids") or []
                else:
                    ids = []
            for command_id in ids or []:
                resolved.add(str(command_id))
        return resolved

    def unreconciled(self, endpoint_id: str, device_id: str) -> list[dict[str, Any]]:
        """Unresolved post-send states on this endpoint/device.

        A durable ``dispatching`` record with no terminal record is returned as
        a synthetic ``unknown`` unless this process is still inside that exact
        dispatch.  An ``in_flight`` record (a ``running``/``accepted`` receipt)
        is pending with its ``operation_id`` until the operation is settled.
        ``allocated``/``prepared`` records are pre-send and are not pending.  A
        reconciled command stays closed until a *new* ambiguous record appears
        for a new command id.
        """
        records = self.records()
        reconciled = self._reconciled_ids(records, endpoint_id, device_id)
        pending: list[dict[str, Any]] = []
        for command_id, state, record, items in self._command_states(
            records, endpoint_id, device_id
        ):
            if state not in ("unknown", "dispatching", "in_flight"):
                continue
            if command_id in reconciled:
                continue
            if state == "dispatching" and self.is_live(command_id):
                continue
            item = dict(record)
            item["phase"] = "in_flight" if state == "in_flight" else "unknown"
            item["state"] = state
            item["command_id"] = command_id
            item["reconcile_required"] = True
            item["retry_safe"] = False
            if state == "dispatching":
                item["recovered_from"] = "dispatching"
                item.setdefault(
                    "error",
                    "dispatching record has no definitive terminal outcome; "
                    "reconstructed as UNKNOWN on reload",
                )
            if item.get("arguments_digest") is None:
                for candidate in reversed(items):
                    if candidate.get("arguments_digest") is not None:
                        item["arguments_digest"] = candidate["arguments_digest"]
                        break
            pending.append(item)
        return pending

    def for_command(self, command_id: str) -> list[dict[str, Any]]:
        return [
            item
            for item in self.records()
            if str(item.get("command_id")) == str(command_id)
        ]


def _policy_ready(config: MHSConfig) -> None:
    if not config.enabled:
        raise MCPInvokeError(
            "MHS.AUTH.FORBIDDEN",
            "the MHS integration is disabled (enabled=false); no endpoint call was made",
        )


def _endpoint(config: MHSConfig, endpoint_id: str):
    try:
        return config.endpoint(endpoint_id)
    except LookupError as exc:
        raise MCPInvokeError(
            "MHS.HOST.ENDPOINT_NOT_ALLOWED",
            f"endpoint {endpoint_id!r} is not in the configured allow-list: {exc}",
        ) from exc


def _config_path(config: MHSConfig) -> str:
    if not config.config_path:
        raise MCPInvokeError(
            "MHS.HOST.CONFIG_REQUIRED",
            "the governed MCP path needs the settings file path so mhs.mcp can "
            "enforce the same enabled/allow_hardware policy; load the config with "
            "MHSConfig.load(path) or set config.config_path",
        )
    return str(config.config_path)


def _child_env(spec) -> dict[str, str]:
    env = {name: os.environ[name] for name in _CONNECTOR_ENV if name in os.environ}
    env.setdefault("PATH", os.defpath)
    env["PYTHONUNBUFFERED"] = "1"
    # A source-tree SDK must be importable by the mhs.mcp child even when this
    # process found it through sys.path rather than PYTHONPATH.
    source_root = connector_env().get("PYTHONPATH")
    if source_root:
        parts = [part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part]
        if source_root not in parts:
            env["PYTHONPATH"] = os.pathsep.join([source_root, *parts])
    for name, value in (getattr(spec, "env", None) or {}).items():
        env[str(name)] = str(value)
    return env


def _endpoint_deadline_ms(timeout_s: float) -> int:
    """The ``deadline_ms`` sent to the endpoint for a transport timeout of ``timeout_s``.

    The endpoint answers at its deadline (``running`` with an operation id for
    long-running work, else ``unknown`` + ``MHS.OUTCOME.TIMEOUT``).  Sending the
    transport timeout itself would race that answer against the MCP client
    giving up, and the receipt would be lost; a margin of 20 % (at least
    250 ms) lets it arrive.
    """
    total = int(float(timeout_s) * 1000)
    return max(250, total - max(250, total // 5))


def _bounded_timeout(config: MHSConfig, timeout_s: float | None) -> float:
    if timeout_s is None:
        timeout_s = float(config.command_timeout_ms) / 1000.0
    try:
        value = float(timeout_s)
    except (TypeError, ValueError) as exc:
        raise MCPInvokeError("MHS.PROTOCOL.INVALID_PARAMS", "timeout_s must be a number") from exc
    return min(max(value, 1.0), 600.0)


def _mcp_client_module():
    try:
        from openai4s import mcp_client  # type: ignore
    except Exception as exc:  # noqa: BLE001 - OpenAI4S absent is a supported mode
        raise MCPInvokeError(
            "MHS.HOST.ADAPTER_MISSING",
            "the OpenAI4S MCP client (openai4s.mcp_client) is not importable: install "
            "OpenAI4S in this environment or put its source tree on PYTHONPATH "
            "(work/openai4s-src in this workspace)",
            details={"cause": str(exc), "host": "openai4s"},
        ) from exc
    return mcp_client


def open_connection(
    spec,
    config: MHSConfig,
    *,
    connector_command: Sequence[str] | None = None,
    timeout_s: float | None = None,
):
    """Open a real OpenAI4S ``MCPConnection`` to the generated mhs.mcp server.

    ``connector_command`` exists only for fault-injection tests (a proxy that
    drops one reply); production always uses the generated connector row.
    """
    module = _mcp_client_module()
    if connector_command is None:
        entry = connector_entry(
            spec,
            python=sys.executable,
            enabled=True,
            config_path=_config_path(config),
        )
        command = list(entry["command"])
    else:
        command = [str(part) for part in connector_command]
    return module.MCPConnection(
        command,
        env=_child_env(spec),
        timeout=_bounded_timeout(config, timeout_s),
    )


class MCPConnector:
    """A real MCP connection to one MHS endpoint, as a context manager."""

    def __init__(
        self,
        endpoint_id: str,
        config: MHSConfig | None = None,
        *,
        connector_command: Sequence[str] | None = None,
        timeout_s: float | None = None,
    ) -> None:
        self.config = config or MHSConfig.load()
        _policy_ready(self.config)
        self.spec = _endpoint(self.config, endpoint_id)
        self.endpoint_id = endpoint_id
        self._command = connector_command
        self._timeout_s = timeout_s
        self.connection: Any = None
        self.tools: list[dict[str, Any]] = []

    def __enter__(self) -> "MCPConnector":
        try:
            self.connection = open_connection(
                self.spec,
                self.config,
                connector_command=self._command,
                timeout_s=self._timeout_s,
            )
            self.tools = self.connection.list_tools()
        except BaseException:
            self.close()
            raise
        return self

    def tool_names(self) -> set[str]:
        return {str(item.get("name")) for item in self.tools if isinstance(item, Mapping)}

    def call(self, name: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if self.connection is None:
            raise MCPInvokeError("MHS.TRANSPORT.UNAVAILABLE", "MCP connection is not open")
        return self.connection.call_tool(name, dict(arguments or {}))

    def read_resource(self, uri: str) -> dict[str, Any]:
        if self.connection is None:
            raise MCPInvokeError("MHS.TRANSPORT.UNAVAILABLE", "MCP connection is not open")
        return self.connection.read_resource(str(uri))

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _mcp_error_payload(result: Mapping[str, Any]) -> dict[str, Any]:
    raw = result.get("raw")
    structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
    payload = structured.get("mhs_error") if isinstance(structured, Mapping) else None
    if isinstance(payload, Mapping):
        return {str(key): value for key, value in payload.items()}
    text = str(result.get("text") or "")
    return {"mhs_code": "MHS.HOST.TOOL_ERROR", "message": text or "MCP tool error"}


def read_evidence(connector: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """``(bundle, verification, error)`` of the endpoint evidence over MCP.

    A connection that can read resources (:class:`MCPConnector`) reads the
    standard resource ``mhs://<endpoint>/evidence`` that ``mhs__evidence``
    names and verifies the bundle here, offline.  A transport that can only
    call tools (the host route's ``MCPManager`` pair) asks ``mhs__evidence``
    for ``include_bundle``.
    """
    reader = getattr(connector, "read_resource", None)
    if callable(reader):
        summary = connector.call("mhs__evidence", {"last_n": 0})
        if bool(summary.get("is_error")):
            return None, None, _mcp_error_payload(summary)
        raw = summary.get("raw")
        structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
        evidence = structured.get("evidence") if isinstance(structured, Mapping) else None
        uri = evidence.get("uri") if isinstance(evidence, Mapping) else None
        if isinstance(uri, str) and uri:
            try:
                document = reader(uri)
                contents = document.get("contents") if isinstance(document, Mapping) else None
                text = contents[0].get("text") if isinstance(contents, list) and contents else None
                bundle = json.loads(text) if isinstance(text, str) else None
                if not isinstance(bundle, dict):
                    raise ValueError(f"{uri} did not return an evidence bundle")
                from mhs.evidence import verify_bundle

                report = verify_bundle(bundle)
                verify = report.to_dict() if hasattr(report, "to_dict") else dict(report)
                return bundle, dict(verify), None
            except Exception as exc:  # noqa: BLE001 - reported, never raised past evidence
                return None, None, {
                    "mhs_code": "MHS.HOST.EVIDENCE_EXPORT_FAILED",
                    "message": f"resources/read {uri}: {exc}",
                }
    response = connector.call("mhs__evidence", {"include_bundle": True})
    if bool(response.get("is_error")):
        return None, None, _mcp_error_payload(response)
    raw = response.get("raw")
    structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
    evidence = structured.get("evidence") if isinstance(structured, Mapping) else None
    if not isinstance(evidence, Mapping) or not isinstance(evidence.get("bundle"), Mapping):
        return None, None, {
            "mhs_code": "MHS.HOST.PROTOCOL_ERROR",
            "message": "mhs__evidence returned no evidence bundle",
        }
    verify = evidence.get("verify")
    return dict(evidence["bundle"]), dict(verify) if isinstance(verify, Mapping) else None, None


def _structured_receipt(result: Mapping[str, Any]) -> dict[str, Any] | None:
    raw = result.get("raw")
    structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
    if isinstance(structured, Mapping):
        receipt = structured.get("receipt")
        if isinstance(receipt, Mapping):
            return dict(receipt)
    return None


def _operation_id(result: Mapping[str, Any], receipt: Mapping[str, Any]) -> str | None:
    """The operation handle of a ``running``/``accepted`` receipt."""
    if isinstance(receipt.get("operation_id"), str) and receipt.get("operation_id"):
        return str(receipt["operation_id"])
    raw = result.get("raw")
    structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
    operation = structured.get("operation") if isinstance(structured, Mapping) else None
    if isinstance(operation, Mapping) and operation.get("operation_id"):
        return str(operation["operation_id"])
    return None


def _journal(
    journal: CommandJournal | None,
    config: MHSConfig,
    record: Mapping[str, Any],
) -> CommandJournal:
    effective = journal or CommandJournal(config.command_journal_path)
    effective.append(record)
    return effective


def _ledger_record(
    ledger: HostLedger,
    *,
    kind: str,
    spec,
    config: MHSConfig,
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    command_id: str,
    input_digest: str,
    arguments_digest: str,
    approvals: Sequence[Any] | None,
    denials: Sequence[Any] | None,
    mode: str | None,
    outcome: str,
    receipt: Mapping[str, Any] | None = None,
    error: Mapping[str, Any] | None = None,
    reconcile_required: bool = False,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "kind": kind,
        "connector_id": connector_id(spec),
        "endpoint_id": endpoint_id,
        "device_id": device_id,
        "capability_id": capability_id,
        "command_id": command_id,
        "input_digest": input_digest,
        "arguments_digest": arguments_digest,
        "approvals": [dict(item) if isinstance(item, Mapping) else item for item in (approvals or [])],
        "denials": [dict(item) if isinstance(item, Mapping) else item for item in (denials or [])],
        "mode": mode,
        "outcome": outcome,
        "reconcile_required": bool(reconcile_required),
        "policy": {"enabled": bool(config.enabled), "allow_hardware": bool(config.allow_hardware)},
    }
    if receipt is not None:
        record["receipt"] = dict(receipt)
        record["receipt_digest"] = canonical.digest(receipt)
        evidence = receipt.get("evidence")
        if isinstance(evidence, Mapping):
            record["endpoint_evidence"] = dict(evidence)
    if error is not None:
        record["error"] = dict(error)
    if extra:
        record.update({str(key): value for key, value in extra.items()})
    try:
        return ledger.append(record, kind=kind)
    except HostLedgerError as exc:
        raise MCPInvokeError(
            "MHS.HOST.EVIDENCE_WRITE_FAILED",
            f"host evidence ledger append failed: {exc.message}",
            details={"cause": exc.to_dict()},
            command_id=command_id,
            retry_safe=False,
            receipt=receipt,
            reconcile_required=reconcile_required,
        ) from exc


class _ConnectorTransport:
    """Adapt :class:`MCPConnector` to the transport contract of ``invoke_via``."""

    def __init__(self, connector: MCPConnector) -> None:
        self.connector = connector

    def tool_names(self) -> set[str]:
        return self.connector.tool_names()

    def call(
        self, name: str, arguments: Mapping[str, Any] | None = None
    ) -> dict[str, Any]:
        return self.connector.call(name, arguments)


def _prepare_invoke(
    effective: MHSConfig,
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    arguments: Mapping[str, Any] | None,
    *,
    command_id: str | None,
    journal: CommandJournal | None,
    ledger: HostLedger | None,
    timeout_s: float | None,
    approvals: Sequence[Any] | None,
    denials: Sequence[Any] | None,
    permit_id: str | None = None,
    expected_revision: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Validate policy, identity and the recovery gate before any effect.

    The reconciliation gate runs **before** the ``allocated`` record is written,
    so a refused command leaves no state of its own, and it runs whether the
    command id was generated here or supplied by the caller.  The only exemption
    is a verified replay: a pending record for the *same* command id, endpoint,
    device, capability and physical-argument digest.
    """
    _policy_ready(effective)
    spec = _endpoint(effective, endpoint_id)
    args = {str(key): value for key, value in dict(arguments or {}).items()}
    for reserved in _RESERVED_ARGUMENTS & set(args):
        if reserved not in ("session_id", "permit_id", "expected_revision"):
            raise MCPInvokeError(
                "MHS.PROTOCOL.INVALID_PARAMS",
                f"governed invoke owns the reserved argument {reserved!r}",
                retry_safe=True,
            )
    # Control arguments belong to the MHS envelope, not to the capability
    # input.  Pulling them out here keeps the journaled input digest (and the
    # host ledger's copy of it) identical to the endpoint receipt's digest.
    if permit_id is None and isinstance(args.get("permit_id"), str):
        permit_id = args.pop("permit_id")
    else:
        args.pop("permit_id", None)
    if expected_revision is None and isinstance(args.get("expected_revision"), int):
        expected_revision = args.pop("expected_revision")
    else:
        args.pop("expected_revision", None)
    if session_id is None and isinstance(args.get("session_id"), str):
        session_id = args.pop("session_id")
    else:
        args.pop("session_id", None)
    cmd_id = str(command_id or canonical.ulid())
    if not canonical.is_ulid(cmd_id):
        raise MCPInvokeError(
            "MHS.PROTOCOL.INVALID_PARAMS",
            "command_id must be a 26-character ULID",
            retry_safe=True,
        )
    args_digest = canonical.digest(args)
    journal_obj = journal or CommandJournal(effective.command_journal_path)
    previous = journal_obj.for_command(cmd_id)
    for item in previous:
        recorded_digest = item.get("arguments_digest")
        if recorded_digest is not None and str(recorded_digest) != args_digest:
            raise MCPInvokeError(
                "MHS.CONFLICT.COMMAND_ID_REUSE",
                "command_id was already journaled with a different input; use a new ULID",
                command_id=cmd_id,
                retry_safe=False,
                details={"previous_digests": [item.get("arguments_digest") for item in previous]},
            )
    pending = journal_obj.unreconciled(endpoint_id, device_id)
    if pending:
        same_id = [
            item for item in pending if str(item.get("command_id")) == cmd_id
        ]
        verified_replay = bool(same_id) and all(
            str(item.get("endpoint_id")) == str(endpoint_id)
            and str(item.get("device_id")) == str(device_id)
            and str(item.get("capability_id")) == str(capability_id)
            and item.get("arguments_digest") == args_digest
            for item in same_id
        )
        if not verified_replay:
            first = pending[0]
            running = [item for item in pending if item.get("state") == "in_flight"]
            raise MCPInvokeError(
                "MHS.HOST.RECONCILE_REQUIRED",
                (
                    "an earlier command on this device is still running (operation "
                    + ", ".join(str(item.get("operation_id")) for item in running)
                    + "); wait for it with mhs__operations, then reconcile() before "
                    "issuing a new command (only a verified same-id retry is allowed)"
                )
                if len(running) == len(pending)
                else (
                    "an earlier command on this device has an unresolved UNKNOWN outcome; "
                    "call reconcile() before issuing a new command (only a verified "
                    "same-id retry is allowed)"
                ),
                command_id=str(first.get("command_id")),
                retry_safe=False,
                reconcile_required=True,
                details={
                    "pending_command_ids": [item.get("command_id") for item in pending],
                    "pending_states": [
                        {
                            "command_id": item.get("command_id"),
                            "phase": item.get("phase"),
                            "recovered_from": item.get("recovered_from"),
                            **(
                                {"operation_id": item.get("operation_id")}
                                if item.get("state") == "in_flight"
                                else {}
                            ),
                        }
                        for item in pending
                    ],
                    "supplied_command_id": cmd_id,
                },
            )
    active_ledger = ledger
    if active_ledger is None:
        try:
            active_ledger = HostLedger(effective.host_ledger_path)
        except HostLedgerError as exc:
            raise MCPInvokeError(
                "MHS.HOST.EVIDENCE_WRITE_FAILED",
                f"host evidence ledger is unavailable: {exc.message}",
                command_id=cmd_id,
                retry_safe=False,
                details={"cause": exc.to_dict()},
            ) from exc
    retry_of = previous[-1].get("phase") if previous else None
    timeout = _bounded_timeout(effective, timeout_s)
    return {
        "config": effective,
        "spec": spec,
        "args": args,
        "args_digest": args_digest,
        "cmd_id": cmd_id,
        "journal": journal_obj,
        "ledger": active_ledger,
        "retry_of": retry_of,
        "timeout": timeout,
        "deadline_ms": _endpoint_deadline_ms(timeout),
        "approvals": list(approvals or []),
        "denials": list(denials or []),
        "permit_id": permit_id,
        "expected_revision": expected_revision,
        "session_id": session_id,
    }


def _record_presend_error(
    prepared: Mapping[str, Any],
    *,
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    stage: str,
    error: Mapping[str, Any],
) -> None:
    """A failure before ``tools/call`` is a safe retry, and says so durably."""
    prepared["journal"].append(
        {
            "kind": "command_dispatch",
            "phase": "pre_send_error",
            "command_id": prepared["cmd_id"],
            "endpoint_id": endpoint_id,
            "device_id": device_id,
            "capability_id": capability_id,
            "error": str(error.get("message") or error),
            "retry_safe": True,
        }
    )
    _ledger_record(
        prepared["ledger"],
        kind="invoke_outcome",
        spec=prepared["spec"],
        config=prepared["config"],
        endpoint_id=endpoint_id,
        device_id=device_id,
        capability_id=capability_id,
        command_id=prepared["cmd_id"],
        input_digest=prepared["args_digest"],
        arguments_digest=prepared["args_digest"],
        approvals=prepared["approvals"],
        denials=prepared["denials"],
        mode=None,
        outcome="pre_send_error",
        error=dict(error),
        extra={"retry_safe": True, "phase": "pre_send_error", "stage": stage},
    )


def _governed_invoke(
    transport: Any,
    prepared: Mapping[str, Any],
    *,
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    permit_id: str | None,
    expected_revision: int | None,
    session_id: str | None,
    return_result: bool,
) -> Any:
    """The shared governed body: journal intent, dispatch, record outcome."""
    effective: MHSConfig = prepared["config"]
    spec = prepared["spec"]
    args: dict[str, Any] = prepared["args"]
    args_digest: str = prepared["args_digest"]
    cmd_id: str = prepared["cmd_id"]
    journal_obj: CommandJournal = prepared["journal"]
    active_ledger: HostLedger = prepared["ledger"]
    retry_of = prepared["retry_of"]
    deadline_ms = prepared["deadline_ms"]

    active_journal = _journal(
        journal_obj,
        effective,
        {
            "kind": "command_dispatch",
            "phase": "allocated",
            "command_id": cmd_id,
            "endpoint_id": endpoint_id,
            "device_id": device_id,
            "capability_id": capability_id,
            "arguments_digest": args_digest,
        },
    )
    try:
        tools = {str(name) for name in transport.tool_names()}
        from mhs.mcp import projection_tool_name

        tool_name = projection_tool_name(device_id, capability_id)
        if tool_name not in tools:
            raise MCPInvokeError(
                "MHS.CAPABILITY.UNKNOWN",
                f"projected MCP tool {tool_name!r} is not advertised by the connector",
                command_id=cmd_id,
                retry_safe=True,
                details={"tools": sorted(tools)},
            )
        inspect = transport.call("mhs__inspect", {"device_id": device_id})
        if bool(inspect.get("is_error")):
            payload = _mcp_error_payload(inspect)
            raise MCPInvokeError(
                str(payload.get("mhs_code") or "MHS.DEVICE.UNKNOWN"),
                str(payload.get("message") or "cannot inspect the device"),
                command_id=cmd_id,
                retry_safe=True,
                details={"stage": "inspect"},
            )
        raw = inspect.get("raw")
        structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
        manifest = structured.get("inspect") if isinstance(structured, Mapping) else None
        if not isinstance(manifest, Mapping):
            raise MCPInvokeError(
                "MHS.HOST.PROTOCOL_ERROR",
                "mhs__inspect returned no manifest",
                command_id=cmd_id,
                retry_safe=True,
            )
        mode = str(manifest.get("mode")) if manifest.get("mode") is not None else None
        resource = None
        for capability in manifest.get("capabilities") or []:
            if (
                isinstance(capability, Mapping)
                and str(capability.get("capability_id")) == capability_id
            ):
                resource = capability.get("resource")
                break
        if resource is None:
            raise MCPInvokeError(
                "MHS.CAPABILITY.UNKNOWN",
                f"capability {capability_id!r} is not in the device manifest",
                command_id=cmd_id,
                retry_safe=True,
            )
        input_digest = canonical.digest(
            {"capability_id": capability_id, "resource": resource, "input": args}
        )
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "prepared",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "resource": resource,
                "input_digest": input_digest,
                "arguments_digest": args_digest,
                "retry_of": retry_of,
            }
        )
        _ledger_record(
            active_ledger,
            kind="invoke_intent",
            spec=spec,
            config=effective,
            endpoint_id=endpoint_id,
            device_id=device_id,
            capability_id=capability_id,
            command_id=cmd_id,
            input_digest=input_digest,
            arguments_digest=args_digest,
            approvals=prepared["approvals"],
            denials=prepared["denials"],
            mode=mode,
            outcome="intent",
            extra={"retry_of": retry_of, "resource": resource},
        )
    except MCPInvokeError as exc:
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "pre_send_error",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "error": exc.message,
                "retry_safe": True,
            }
        )
        raise
    except HostLedgerError:
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "pre_send_error",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "error": "host evidence ledger append failed before dispatch",
                "retry_safe": True,
            }
        )
        raise
    except Exception as exc:  # noqa: BLE001
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "pre_send_error",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "error": f"{type(exc).__name__}: {exc}",
                "retry_safe": True,
            }
        )
        raise MCPInvokeError(
            "MHS.TRANSPORT.UNAVAILABLE",
            f"MCP discovery failed before dispatch (safe to retry): {exc}",
            command_id=cmd_id,
            retry_safe=True,
        ) from exc

    call_arguments: dict[str, Any] = dict(args)
    call_arguments["command_id"] = cmd_id
    call_arguments["deadline_ms"] = deadline_ms
    if permit_id is not None:
        call_arguments["permit_id"] = permit_id
    if expected_revision is not None:
        call_arguments["expected_revision"] = int(expected_revision)
    if session_id is not None:
        call_arguments["session_id"] = session_id

    # The durable dispatch marker is written (and fsynced) *before* the
    # effect.  ``mark_live`` is process-local only: if this process dies, the
    # record reloads as UNKNOWN instead of looking like an in-flight call.
    journal_obj.mark_live(cmd_id)
    try:
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "dispatching",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "tool": tool_name,
                "input_digest": input_digest,
                "arguments_digest": args_digest,
                "retry_of": retry_of,
            }
        )
        try:
            result = transport.call(tool_name, call_arguments)
        except Exception as exc:  # noqa: BLE001 - ambiguous after the dispatch marker
            return _raise_unknown_after_dispatch(
                active_journal=active_journal,
                active_ledger=active_ledger,
                prepared=prepared,
                endpoint_id=endpoint_id,
                device_id=device_id,
                capability_id=capability_id,
                input_digest=input_digest,
                mode=mode,
                cause=f"{type(exc).__name__}: {exc}",
            )

        if bool(result.get("is_error")):
            payload = _mcp_error_payload(result)
            code = str(payload.get("mhs_code") or "MHS.HOST.TOOL_ERROR")
            if _may_have_effect(payload):
                # The projection sent the command and lost the answer
                # (MHS.OUTCOME.TIMEOUT/UNKNOWN, may_have_effect: true): the
                # same ambiguity as a lost MCP reply, never a safe retry.
                return _raise_unknown_after_dispatch(
                    active_journal=active_journal,
                    active_ledger=active_ledger,
                    prepared=prepared,
                    endpoint_id=endpoint_id,
                    device_id=device_id,
                    capability_id=capability_id,
                    input_digest=input_digest,
                    mode=mode,
                    cause=f"{code}: {payload.get('message') or 'no receipt'}",
                    mhs_error=payload,
                )
            active_journal.append(
                {
                    "kind": "command_dispatch",
                    "phase": "tool_error",
                    "command_id": cmd_id,
                    "endpoint_id": endpoint_id,
                    "device_id": device_id,
                    "capability_id": capability_id,
                    "mhs_error": payload,
                    "retry_safe": True,
                }
            )
            _ledger_record(
                active_ledger,
                kind="invoke_outcome",
                spec=spec,
                config=effective,
                endpoint_id=endpoint_id,
                device_id=device_id,
                capability_id=capability_id,
                command_id=cmd_id,
                input_digest=input_digest,
                arguments_digest=args_digest,
                approvals=prepared["approvals"],
                denials=prepared["denials"],
                mode=mode,
                outcome="tool_error",
                error=payload,
                extra={"retry_safe": True, "phase": "tool_error"},
            )
            raise MCPInvokeError(
                code,
                str(payload.get("message") or "MCP tool call failed before an MHS receipt"),
                command_id=cmd_id,
                retry_safe=True,
                details={"stage": "tools/call", "mhs_error": payload},
            )

        receipt = _structured_receipt(result)
        if receipt is None:
            active_journal.append(
                {
                    "kind": "command_dispatch",
                    "phase": "tool_error",
                    "command_id": cmd_id,
                    "endpoint_id": endpoint_id,
                    "device_id": device_id,
                    "capability_id": capability_id,
                    "error": "MCP result carried no MHS receipt",
                    "retry_safe": True,
                }
            )
            _ledger_record(
                active_ledger,
                kind="invoke_outcome",
                spec=spec,
                config=effective,
                endpoint_id=endpoint_id,
                device_id=device_id,
                capability_id=capability_id,
                command_id=cmd_id,
                input_digest=input_digest,
                arguments_digest=args_digest,
                approvals=prepared["approvals"],
                denials=prepared["denials"],
                mode=mode,
                outcome="tool_error",
                error={"mhs_code": "MHS.HOST.PROTOCOL_ERROR", "message": "no MHS receipt"},
                extra={"retry_safe": True},
            )
            raise MCPInvokeError(
                "MHS.HOST.PROTOCOL_ERROR",
                "MCP result carried no MHS receipt",
                command_id=cmd_id,
                retry_safe=True,
            )
        status = str(receipt.get("status") or "")
        if status == "unknown":
            active_journal.append(
                {
                    "kind": "command_dispatch",
                    "phase": "unknown",
                    "command_id": cmd_id,
                    "endpoint_id": endpoint_id,
                    "device_id": device_id,
                    "capability_id": capability_id,
                    "receipt_id": receipt.get("receipt_id"),
                    "reconcile_required": True,
                    "retry_safe": False,
                }
            )
            _ledger_record(
                active_ledger,
                kind="invoke_outcome",
                spec=spec,
                config=effective,
                endpoint_id=endpoint_id,
                device_id=device_id,
                capability_id=capability_id,
                command_id=cmd_id,
                input_digest=input_digest,
                arguments_digest=args_digest,
                approvals=prepared["approvals"],
                denials=prepared["denials"],
                mode=mode,
                outcome="unknown",
                receipt=receipt,
                error=(
                    receipt.get("error")
                    if isinstance(receipt.get("error"), Mapping)
                    else None
                ),
                reconcile_required=True,
                extra={"phase": "unknown"},
            )
            raise MCPOutcomeUnknown(
                "the endpoint returned an UNKNOWN receipt; the effect may have occurred. "
                f"Reconcile command_id {cmd_id} before any retry.",
                command_id=cmd_id,
                details={"receipt_id": receipt.get("receipt_id")},
                receipt=receipt,
            )
        if status in _IN_FLIGHT_STATUSES:
            # Plan 3.7: a long-running command answers ``running`` (or
            # ``accepted``) with an operation id and keeps executing.  It is
            # not final: journal it as in flight so no new command on this
            # device starts until the operation ended (``invoke_via`` settles
            # it through ``mhs__operations`` on the same connection;
            # :func:`reconcile` through the endpoint evidence).
            operation_id = _operation_id(result, receipt)
            active_journal.append(
                {
                    "kind": "command_dispatch",
                    "phase": "in_flight",
                    "command_id": cmd_id,
                    "endpoint_id": endpoint_id,
                    "device_id": device_id,
                    "capability_id": capability_id,
                    "receipt_id": receipt.get("receipt_id"),
                    "operation_id": operation_id,
                    "status": status,
                    "arguments_digest": args_digest,
                    "replayed": bool(receipt.get("replayed")),
                    "retry_of": retry_of,
                    "reconcile_required": True,
                    "retry_safe": False,
                }
            )
            _ledger_record(
                active_ledger,
                kind="invoke_outcome",
                spec=spec,
                config=effective,
                endpoint_id=endpoint_id,
                device_id=device_id,
                capability_id=capability_id,
                command_id=cmd_id,
                input_digest=input_digest,
                arguments_digest=args_digest,
                approvals=prepared["approvals"],
                denials=prepared["denials"],
                mode=mode,
                outcome="in_flight",
                receipt=receipt,
                reconcile_required=True,
                extra={"status": status, "operation_id": operation_id, "phase": "in_flight"},
            )
            if return_result:
                return {"receipt": receipt, "result": result, "command_id": cmd_id}
            return receipt
        active_journal.append(
            {
                "kind": "command_dispatch",
                "phase": "completed" if status == "completed" else "receipt",
                "command_id": cmd_id,
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "capability_id": capability_id,
                "receipt_id": receipt.get("receipt_id"),
                "status": status,
                "replayed": bool(receipt.get("replayed")),
                "retry_of": retry_of,
                "reconcile_required": False,
            }
        )
        _ledger_record(
            active_ledger,
            kind="invoke_outcome",
            spec=spec,
            config=effective,
            endpoint_id=endpoint_id,
            device_id=device_id,
            capability_id=capability_id,
            command_id=cmd_id,
            input_digest=input_digest,
            arguments_digest=args_digest,
            approvals=prepared["approvals"],
            denials=prepared["denials"],
            mode=mode,
            outcome="receipt",
            receipt=receipt,
            error=(
                receipt.get("error")
                if isinstance(receipt.get("error"), Mapping)
                else None
            ),
            extra={
                "status": status,
                "replayed": bool(receipt.get("replayed")),
                "retry_of": retry_of,
            },
        )
        if return_result:
            return {"receipt": receipt, "result": result, "command_id": cmd_id}
        return receipt
    finally:
        journal_obj.clear_live(cmd_id)


def _may_have_effect(payload: Mapping[str, Any]) -> bool:
    """Whether an ``isError`` result leaves the command's effect undecided."""
    if payload.get("may_have_effect") is True:
        return True
    return str(payload.get("mhs_code") or "") in _AMBIGUOUS_CODES


def _raise_unknown_after_dispatch(
    *,
    active_journal: CommandJournal,
    active_ledger: HostLedger,
    prepared: Mapping[str, Any],
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    input_digest: str,
    mode: str | None,
    cause: str,
    mhs_error: Mapping[str, Any] | None = None,
) -> Any:
    """Journal UNKNOWN, then raise it; the journal is the source of truth."""
    cmd_id = prepared["cmd_id"]
    record: dict[str, Any] = {
        "kind": "command_dispatch",
        "phase": "unknown",
        "command_id": cmd_id,
        "endpoint_id": endpoint_id,
        "device_id": device_id,
        "capability_id": capability_id,
        "error": cause,
        "reconcile_required": True,
        "retry_safe": False,
    }
    if mhs_error is not None:
        record["mhs_error"] = dict(mhs_error)
    active_journal.append(record)
    ledger_error: dict[str, Any] | None = None
    try:
        _ledger_record(
            active_ledger,
            kind="invoke_outcome",
            spec=prepared["spec"],
            config=prepared["config"],
            endpoint_id=endpoint_id,
            device_id=device_id,
            capability_id=capability_id,
            command_id=cmd_id,
            input_digest=input_digest,
            arguments_digest=prepared["args_digest"],
            approvals=prepared["approvals"],
            denials=prepared["denials"],
            mode=mode,
            outcome="unknown",
            error=dict(mhs_error) if mhs_error is not None
            else {"mhs_code": "MHS.OUTCOME.UNKNOWN", "message": cause},
            reconcile_required=True,
            extra={"phase": "unknown", "transport_error": cause},
        )
    except MCPInvokeError as exc:
        # The journal already holds the ambiguous outcome; an audit failure
        # must not downgrade it to a retryable transport error.
        ledger_error = exc.to_dict()
    raise MCPOutcomeUnknown(
        (
            "the MCP projection sent the command but lost its answer"
            if mhs_error is not None
            else "MCP transport failed after dispatch"
        )
        + f": the effect may have occurred. Reconcile with command_id {cmd_id} before any retry.",
        command_id=cmd_id,
        details={
            "stage": "tools/call",
            "cause": cause,
            **({"mhs_error": dict(mhs_error)} if mhs_error is not None else {}),
            **({"ledger_error": ledger_error} if ledger_error else {}),
        },
    )


def invoke(
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    config: MHSConfig | None = None,
    command_id: str | None = None,
    timeout_s: float | None = None,
    ledger: HostLedger | None = None,
    journal: CommandJournal | None = None,
    approvals: Sequence[Any] | None = None,
    denials: Sequence[Any] | None = None,
    connector_command: Sequence[str] | None = None,
    permit_id: str | None = None,
    expected_revision: int | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Invoke one capability through the real MCP connector, governed.

    Returns the endpoint receipt (including ``replayed`` on a command-id
    replay).  Raises :class:`MCPOutcomeUnknown` when the outcome is ambiguous
    after dispatch, and :class:`MCPInvokeError` for pre-send/tool failures.
    """
    effective = config or MHSConfig.load()
    prepared = _prepare_invoke(
        effective,
        endpoint_id,
        device_id,
        capability_id,
        arguments,
        command_id=command_id,
        journal=journal,
        ledger=ledger,
        timeout_s=timeout_s,
        approvals=approvals,
        denials=denials,
        permit_id=permit_id,
        expected_revision=expected_revision,
        session_id=session_id,
    )
    cmd_id = prepared["cmd_id"]
    try:
        connector = MCPConnector(
            endpoint_id,
            effective,
            connector_command=connector_command,
            timeout_s=prepared["timeout"],
        )
        connector.__enter__()
    except MCPInvokeError:
        raise
    except Exception as exc:  # noqa: BLE001
        _record_presend_error(
            prepared,
            endpoint_id=endpoint_id,
            device_id=device_id,
            capability_id=capability_id,
            stage="connect",
            error={"mhs_code": "MHS.TRANSPORT.UNAVAILABLE", "message": str(exc)},
        )
        raise MCPInvokeError(
            "MHS.TRANSPORT.UNAVAILABLE",
            f"MCP connector failed before dispatch (safe to retry): {exc}",
            command_id=cmd_id,
            retry_safe=True,
            details={"stage": "connect"},
        ) from exc
    try:
        return _governed_invoke(
            _ConnectorTransport(connector),
            prepared,
            endpoint_id=endpoint_id,
            device_id=device_id,
            capability_id=capability_id,
            permit_id=prepared["permit_id"],
            expected_revision=prepared["expected_revision"],
            session_id=prepared["session_id"],
            return_result=False,
        )
    finally:
        connector.close()


def invoke_via(
    transport: Any,
    endpoint_id: str,
    device_id: str,
    capability_id: str,
    arguments: Mapping[str, Any] | None = None,
    *,
    config: MHSConfig | None = None,
    command_id: str | None = None,
    timeout_s: float | None = None,
    ledger: HostLedger | None = None,
    journal: CommandJournal | None = None,
    approvals: Sequence[Any] | None = None,
    denials: Sequence[Any] | None = None,
    permit_id: str | None = None,
    expected_revision: int | None = None,
    session_id: str | None = None,
    return_result: bool = False,
) -> Any:
    """Govern an invocation whose transport is owned by the caller.

    This is the seam the OpenAI4S host route uses: ``transport`` is the real
    ``MCPManager`` call pair (``tool_names``/``call``) that ``MCPService``
    already resolved, so the governed path does not open a second connector or
    bypass dispatcher policy.  The caller owns the connection; this function
    never closes it.

    An earlier ``running`` command on this device is settled first through
    ``mhs__operations`` on the same connection (the projection session that
    started it owns the operation); a still-running one keeps the gate shut.
    """
    effective = config or MHSConfig.load()
    _policy_ready(effective)
    _endpoint(effective, endpoint_id)
    journal_obj = journal or CommandJournal(effective.command_journal_path)
    _settle_in_flight(transport, journal_obj, endpoint_id, device_id)
    prepared = _prepare_invoke(
        effective,
        endpoint_id,
        device_id,
        capability_id,
        arguments,
        command_id=command_id,
        journal=journal_obj,
        ledger=ledger,
        timeout_s=timeout_s,
        approvals=approvals,
        denials=denials,
        permit_id=permit_id,
        expected_revision=expected_revision,
        session_id=session_id,
    )
    return _governed_invoke(
        transport,
        prepared,
        endpoint_id=endpoint_id,
        device_id=device_id,
        capability_id=capability_id,
        permit_id=prepared["permit_id"],
        expected_revision=prepared["expected_revision"],
        session_id=prepared["session_id"],
        return_result=return_result,
    )


_RECONCILE_TERMINAL_STATUSES = frozenset(
    {"completed", "failed", "cancelled", "rejected"}
)


def _settle_in_flight(
    transport: Any, journal: CommandJournal, endpoint_id: str, device_id: str
) -> list[str]:
    """Close ``in_flight`` records whose operation has a final receipt.

    One ``mhs__operations {operation_id}`` read per pending operation, through
    the caller's connection.  A final receipt for the operation is definitive
    (exactly one final receipt per command, plan 3.7), so it is journaled as a
    ``command_reconcile`` with ``source: operations.get``.  Anything else --
    still running, an error, another connection that does not own the
    operation -- leaves the record pending.
    """
    try:
        pending = journal.unreconciled(endpoint_id, device_id)
    except MCPInvokeError:
        return []  # the gate in _prepare_invoke reports the journal problem
    settled: list[str] = []
    for item in pending:
        command_id = str(item.get("command_id") or "")
        operation_id = item.get("operation_id")
        if item.get("state") != "in_flight" or not command_id or not operation_id:
            continue
        try:
            response = transport.call(
                "mhs__operations", {"device_id": device_id, "operation_id": str(operation_id)}
            )
        except Exception:  # noqa: BLE001 - an unreadable operation stays pending
            continue
        if bool(response.get("is_error")):
            continue
        raw = response.get("raw")
        structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
        operation = structured.get("operations") if isinstance(structured, Mapping) else None
        if not isinstance(operation, Mapping):
            continue
        status = str(operation.get("status") or "")
        if status not in _RECONCILE_TERMINAL_STATUSES:
            continue
        if operation.get("command_id") not in (None, command_id):
            continue
        journal.append(
            {
                "kind": "command_reconcile",
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "command_ids": [command_id],
                "resolved_command_ids": [command_id],
                "outcome": "reconciled",
                "source": "operations.get",
                "evidence": {
                    "operation_id": str(operation_id),
                    "status": status,
                    "receipt_id": operation.get("receipt_id"),
                    "state_revision_after": operation.get("state_revision_after"),
                },
                "observed_at": canonical.now_rfc3339(),
            }
        )
        settled.append(command_id)
    return settled


def _observe_device(connector: Any, device_id: str) -> dict[str, Any]:
    """One read-only observation: manifest, state document and operations."""
    inspect = connector.call("mhs__inspect", {"device_id": device_id})
    if bool(inspect.get("is_error")):
        payload = _mcp_error_payload(inspect)
        raise MCPInvokeError(
            str(payload.get("mhs_code") or "MHS.DEVICE.UNKNOWN"),
            str(payload.get("message") or "cannot inspect the device"),
            details={"stage": "reconcile.inspect"},
        )
    raw = inspect.get("raw")
    structured = raw.get("structuredContent") if isinstance(raw, Mapping) else None
    manifest = structured.get("inspect") if isinstance(structured, Mapping) else None
    if not isinstance(manifest, Mapping):
        raise MCPInvokeError("MHS.HOST.PROTOCOL_ERROR", "mhs__inspect returned no manifest")
    resources = [
        item.get("resource_id")
        for item in manifest.get("resources") or []
        if isinstance(item, Mapping) and item.get("resource_id")
    ]
    state: Any = None
    if resources:
        state_result = connector.call(
            "mhs__read", {"device_id": device_id, "resource_id": resources[0]}
        )
        if bool(state_result.get("is_error")):
            payload = _mcp_error_payload(state_result)
            raise MCPInvokeError(
                str(payload.get("mhs_code") or "MHS.HOST.READ_FAILED"),
                str(payload.get("message") or "cannot read state"),
                details={"stage": "reconcile.read"},
            )
        raw_state = state_result.get("raw")
        structured_state = (
            raw_state.get("structuredContent") if isinstance(raw_state, Mapping) else None
        )
        state = (
            structured_state.get("read")
            if isinstance(structured_state, Mapping)
            else None
        )
    operations_result = connector.call("mhs__operations", {"device_id": device_id})
    operations: Any = None
    operations_error: dict[str, Any] | None = None
    if bool(operations_result.get("is_error")):
        operations_error = _mcp_error_payload(operations_result)
    else:
        raw_ops = operations_result.get("raw")
        structured_ops = (
            raw_ops.get("structuredContent") if isinstance(raw_ops, Mapping) else None
        )
        operations = (
            structured_ops.get("operations")
            if isinstance(structured_ops, Mapping)
            else None
        )
    # Operations are session-scoped on the endpoint; a crash/reload opens a new
    # MCP process and therefore a new session, so operations alone cannot prove
    # what an earlier process did.  The endpoint evidence chain is session
    # independent and carries every receipt with its command id -- that is the
    # definitive, offline-verifiable source for reconciliation.
    bundle, evidence_verify, evidence_error = read_evidence(connector)
    receipts: Any = bundle.get("receipts") if isinstance(bundle, Mapping) else None
    revision = None
    state_hash = None
    if isinstance(state, Mapping):
        if isinstance(state.get("revision"), int):
            revision = int(state["revision"])
        if isinstance(state.get("state_hash"), str):
            state_hash = state["state_hash"]
    return {
        "mode": manifest.get("mode"),
        "resources": resources,
        "state": state,
        "operations": operations,
        "operations_error": operations_error,
        "receipts": receipts,
        "evidence_verify": evidence_verify,
        "evidence_error": evidence_error,
        "state_revision": revision,
        "state_hash": state_hash,
        "observed_at": canonical.now_rfc3339(),
    }


def _matching_terminal_outcome(
    observation: Mapping[str, Any], command_id: str, device_id: str
) -> dict[str, Any] | None:
    """One definitive terminal outcome for ``command_id``, if observed.

    The endpoint evidence chain is checked first: its receipts are session
    independent and hash-chained, so they survive the process/session loss that
    a reconciliation exists to repair.  Operations remain a fallback for an
    endpoint whose evidence export is unavailable.
    """
    verify = observation.get("evidence_verify")
    evidence_trustworthy = bool(
        isinstance(verify, Mapping) and verify.get("valid") is True
    )
    receipts = observation.get("receipts")
    if evidence_trustworthy and isinstance(receipts, list):
        # Latest matching receipt wins: a same-id retry after a rejected attempt
        # appends the successful receipt later in the chain.
        for item in reversed(receipts):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("command_id")) != str(command_id):
                continue
            if str(item.get("device_id")) != str(device_id):
                continue
            status = str(item.get("status") or "")
            if status in _RECONCILE_TERMINAL_STATUSES:
                return {
                    "source": "endpoint_evidence",
                    "receipt_id": item.get("receipt_id"),
                    "status": status,
                    "command_id": item.get("command_id"),
                    "device_id": item.get("device_id"),
                    "capability_id": item.get("capability_id"),
                    "state_revision_after": item.get("state_revision_after"),
                    "evidence": item.get("evidence"),
                }
    operations = observation.get("operations")
    if isinstance(operations, list):
        for item in reversed(operations):
            if not isinstance(item, Mapping):
                continue
            if str(item.get("command_id")) != str(command_id):
                continue
            if str(item.get("device_id")) != str(device_id):
                continue
            status = str(item.get("state") or item.get("status") or "")
            if status in _RECONCILE_TERMINAL_STATUSES:
                return {
                    "source": "operations",
                    "operation_id": item.get("operation_id"),
                    "status": status,
                    "command_id": item.get("command_id"),
                    "device_id": item.get("device_id"),
                    "capability_id": item.get("capability_id"),
                }
    return None


def reconcile(
    endpoint_id: str,
    device_id: str,
    *,
    config: MHSConfig | None = None,
    timeout_s: float | None = None,
    connector_command: Sequence[str] | None = None,
    journal: CommandJournal | None = None,
    settle_s: float = 0.2,
) -> dict[str, Any]:
    """Observe state/operations twice and record reconciliation evidence.

    A single read is not proof: the endpoint may be mid-command, and "no
    operation item" does not mean "no effect".  A pending command is closed
    only when **both** observations contain the *same* operation id in a
    definitive terminal state (``completed``/``failed``/``cancelled``/
    ``rejected``).  Everything else is journaled as inconclusive evidence and
    the gate stays shut.
    """
    effective = config or MHSConfig.load()
    _policy_ready(effective)
    _endpoint(effective, endpoint_id)
    journal_obj = journal or CommandJournal(effective.command_journal_path)
    pending = journal_obj.unreconciled(endpoint_id, device_id)
    with MCPConnector(
        endpoint_id,
        effective,
        connector_command=connector_command,
        timeout_s=timeout_s,
    ) as connector:
        first = _observe_device(connector, device_id)
        second: dict[str, Any] | None = None
        if pending:
            # Two observations are the difference between evidence and a guess;
            # the pause is bounded so reconciliation cannot become an
            # open-ended poll that hides an in-flight command.
            time.sleep(min(max(float(settle_s), 0.0), 5.0))
            second = _observe_device(connector, device_id)

    resolved: list[str] = []
    command_evidence: dict[str, Any] = {}
    if pending and second is not None:
        for item in pending:
            command_id = str(item.get("command_id"))
            first_operation = _matching_terminal_outcome(first, command_id, device_id)
            second_operation = _matching_terminal_outcome(second, command_id, device_id)
            matched = bool(
                first_operation
                and second_operation
                and first_operation.get("source") == second_operation.get("source")
                and (
                    first_operation.get("receipt_id")
                    or first_operation.get("operation_id")
                )
                == (second_operation.get("receipt_id") or second_operation.get("operation_id"))
                and str(first_operation.get("status"))
                == str(second_operation.get("status"))
            )
            if matched:
                resolved.append(command_id)
            command_evidence[command_id] = {
                "resolved": matched,
                "first_operation": first_operation,
                "second_operation": second_operation,
            }

    observation_evidence = [first]
    if second is not None:
        observation_evidence.append(second)
    outcome = "none"
    if pending:
        outcome = "reconciled" if len(resolved) == len(pending) else "inconclusive"
    if pending:
        journal_obj.append(
            {
                "kind": "command_reconcile",
                "endpoint_id": endpoint_id,
                "device_id": device_id,
                "command_ids": [str(item.get("command_id")) for item in pending],
                "resolved_command_ids": resolved,
                "outcome": outcome,
                "evidence": {
                    "observations": [
                        {
                            "observed_at": observation.get("observed_at"),
                            "state_revision": observation.get("state_revision"),
                            "state_hash": observation.get("state_hash"),
                            "operations_digest": canonical.digest(
                                observation.get("operations") or []
                            ),
                            "operations": observation.get("operations"),
                            "operations_error": observation.get("operations_error"),
                            "receipt_ids": [
                                item.get("receipt_id")
                                for item in (observation.get("receipts") or [])
                                if isinstance(item, Mapping)
                            ],
                            "evidence_head_digest": (
                                observation.get("evidence_verify") or {}
                            ).get("head_digest"),
                            "evidence_valid": (
                                observation.get("evidence_verify") or {}
                            ).get("valid"),
                            "evidence_error": observation.get("evidence_error"),
                        }
                        for observation in observation_evidence
                    ],
                    "commands": command_evidence,
                    "state_revision": first.get("state_revision"),
                    "state_hash": first.get("state_hash"),
                },
                "state_revision": first.get("state_revision"),
                "observed_at": canonical.now_rfc3339(),
            }
        )
    remaining = journal_obj.unreconciled(endpoint_id, device_id)
    return {
        "endpoint_id": endpoint_id,
        "device_id": device_id,
        "mode": first.get("mode"),
        "resources": first.get("resources"),
        "state": first.get("state"),
        "operations": first.get("operations"),
        "observed_at": first.get("observed_at"),
        "reconcile": {
            "pending_command_ids": [str(item.get("command_id")) for item in pending],
            "resolved_command_ids": resolved,
            "remaining_command_ids": [
                str(item.get("command_id")) for item in remaining
            ],
            "outcome": outcome,
            "observations": len(observation_evidence),
            "evidence": command_evidence,
        },
    }


def export_evidence(
    endpoint_id: str,
    *,
    config: MHSConfig | None = None,
    timeout_s: float | None = None,
    connector_command: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Export and verify the endpoint evidence bundle through the MCP path."""
    effective = config or MHSConfig.load()
    _policy_ready(effective)
    _endpoint(effective, endpoint_id)
    with MCPConnector(
        endpoint_id,
        effective,
        connector_command=connector_command,
        timeout_s=timeout_s,
    ) as connector:
        bundle, verify, error = read_evidence(connector)
        if error is not None or bundle is None:
            payload = error or {}
            raise MCPInvokeError(
                str(payload.get("mhs_code") or "MHS.HOST.EVIDENCE_EXPORT_FAILED"),
                str(payload.get("message") or "evidence export failed"),
                details={"stage": "evidence"},
            )
        return {"bundle": bundle, "verify": verify}
