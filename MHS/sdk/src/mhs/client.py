"""MHS client and transports (T1 stdio, T2 HTTP/SSE).

The client is dependency-free and deliberately boring: it correlates request
ids, enforces deadlines, drains notifications, and returns the *result* of a
JSON-RPC method.  A rejected physical action is a receipt (a result), not an
exception; only transport/protocol/session-level failures raise
:class:`~mhs.errors.MHSError`.

Receipts are :class:`Receipt` objects (a ``dict``) with ``ok`` and
``raise_for_status()``; ``invoke(..., check=True)`` raises
:class:`MHSRejected` for any outcome other than ``completed`` (or work still
running).  Transport failures say whether the request can have had an effect:

* ``MHS.TRANSPORT.UNAVAILABLE`` (retryable): the endpoint could not be reached
  (connection refused, DNS failure, connect timeout, a stdio command that does
  not start).  The request was never delivered, so nothing happened.
* ``MHS.OUTCOME.TIMEOUT`` / ``MHS.OUTCOME.UNKNOWN`` (not retryable): the
  request was sent and no response arrived.  ``error.data`` carries
  ``command_id`` (when the request had one) and ``may_have_effect``; retry
  only with the same ``command_id`` after observing the device.

``client.device(device_id)`` returns a :class:`DeviceHandle` that owns its own
session, so a code file can drive several devices of one endpoint without one
session overwriting another.

``connect(server)`` talks to an :class:`mhs.server.MHSServer` in this process
(:class:`InProcessTransport`).  :func:`add_observer` lets a ledger see every
``hello``, every receipt and every lost response of every client in the
process (``mhs run`` uses it to write ``.mhs-run/<id>.json``).
"""

from __future__ import annotations

import http.client
import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode

from . import _ids, canonical, protocol
from .errors import MHSError, error_from_json
from .protocol import Method

DEFAULT_TIMEOUT_S = 60.0
#: Hard bound on one framed JSON message read from an endpoint (bytes).
MAX_MESSAGE_BYTES = 16 * 1024 * 1024
#: Client identity sent in ``mhs.hello`` and ``mhs.session.open``.
CLIENT_INFO = {"name": "mhs-python", "version": _ids.SDK_VERSION}
#: Receipt statuses that end a command (``unknown`` is not final: a later
#: receipt reconciles it, plan 3.7).
FINAL_STATUSES = frozenset({"completed", "failed", "rejected", "cancelled"})
#: Receipt statuses of work that is still in progress.
PENDING_STATUSES = frozenset({"accepted", "running"})
#: Methods whose request can change a device: a lost response may hide an effect.
EFFECTFUL_METHODS = frozenset({
    Method.COMMAND, Method.RESOURCE_WRITE, Method.RESTORE, Method.SAFETY_ESTOP, Method.SAFETY_RESET,
    Method.SAFETY_PERMIT, Method.OPERATIONS_CANCEL, Method.COMPOSITION_RUN,
})
#: ``principal.x-meta`` members only the endpoint writes (never sent as identity).
_RESERVED_X_META = ("authenticated", "role", "claimed_principal")
#: Session errors after which a session id is gone for good.
_SESSION_LAPSED = frozenset({"MHS.SESSION.EXPIRED", "MHS.SESSION.UNKNOWN", "MHS.SESSION.CLOSED"})
#: Methods whose result is a receipt (seen by :func:`add_observer` callbacks).
RECEIPT_METHODS = frozenset({
    Method.COMMAND, Method.RESOURCE_WRITE, Method.RESTORE, Method.SAFETY_ESTOP, Method.SAFETY_RESET,
    Method.OPERATIONS_CANCEL, Method.OPERATIONS_GET,
})

_OBSERVERS: list[Callable[[str, Any, Mapping[str, Any]], None]] = []
_OBSERVERS_LOCK = threading.Lock()


def add_observer(callback: Callable[[str, Any, Mapping[str, Any]], None]) -> Callable[[], None]:
    """Call ``callback(event, client, payload)`` for every client of this process; return its remover.

    ``event`` is ``"hello"`` (payload: the ``mhs.hello`` result), ``"receipt"``
    (a receipt returned by a receipt method: ``mhs.command``, ``resource.write``,
    ``restore``, ``safety.estop``/``reset``, ``operations.cancel``/``get``) or
    ``"lost"`` (a request that was sent and got no response:
    ``{method, code, command_id?, may_have_effect}``).  A callback that raises
    is ignored: observing never changes what the client returns.
    """
    with _OBSERVERS_LOCK:
        _OBSERVERS.append(callback)

    def remove() -> None:
        with _OBSERVERS_LOCK:
            if callback in _OBSERVERS:
                _OBSERVERS.remove(callback)

    return remove


def _notify(event: str, client: Any, payload: Mapping[str, Any]) -> None:
    with _OBSERVERS_LOCK:
        observers = list(_OBSERVERS)
    for callback in observers:
        try:
            callback(event, client, payload)
        except Exception:  # noqa: BLE001 - an observer never breaks the client
            pass


class TransportError(MHSError):
    """Transport-level failure (the endpoint may be alive; the channel failed)."""


class MHSRejected(MHSError):
    """A receipt whose outcome is not a success (raised by ``check=True``).

    ``receipt`` is the full receipt; ``code`` is the receipt's ``error.mhs_code``
    (``MHS.OUTCOME.UNKNOWN`` for an ``unknown`` outcome without one).
    """

    def __init__(self, receipt: Mapping[str, Any]):
        self.receipt = receipt if isinstance(receipt, Receipt) else Receipt(receipt or {})
        status = str(self.receipt.get("status") or "unknown")
        error = self.receipt.get("error") if isinstance(self.receipt.get("error"), Mapping) else {}
        code = str(error.get("mhs_code") or _STATUS_CODES.get(status, "MHS.OUTCOME.UNKNOWN"))
        message = str(error.get("message") or f"{self.receipt.get('capability_id') or 'command'} {status}")
        data: dict[str, Any] = {
            key: value for key, value in error.items() if key not in ("mhs_code", "message")
        }
        for key in ("status", "receipt_id", "command_id", "operation_id", "capability_id", "device_id"):
            if self.receipt.get(key) is not None:
                data.setdefault(key, self.receipt.get(key))
        retryable = error.get("retryable") if isinstance(error.get("retryable"), bool) else False
        super().__init__(code, f"{status}: {message}", data, retryable=retryable)

    @property
    def status(self) -> str:
        return str(self.receipt.get("status") or "unknown")


_STATUS_CODES = {
    "unknown": "MHS.OUTCOME.UNKNOWN",
    "cancelled": "MHS.OUTCOME.ABORTED",
    "failed": "MHS.DEVICE.FAULTED",
    "rejected": "MHS.PROTOCOL.INVALID_PARAMS",
}


class Receipt(dict):
    """An MHS receipt (a plain ``dict`` with outcome helpers).

    ``ok`` is true only for ``completed``.  ``raise_for_status()`` returns the
    receipt for ``completed`` and for work still in progress (``accepted``,
    ``running``) and raises :class:`MHSRejected` for ``rejected``, ``failed``,
    ``cancelled`` and ``unknown``.
    """

    @property
    def status(self) -> str | None:
        value = self.get("status")
        return str(value) if value is not None else None

    @property
    def ok(self) -> bool:
        return self.get("status") == "completed"

    @property
    def pending(self) -> bool:
        return self.get("status") in PENDING_STATUSES

    @property
    def error(self) -> dict[str, Any] | None:
        value = self.get("error")
        return dict(value) if isinstance(value, Mapping) else None

    @property
    def code(self) -> str | None:
        error = self.error
        return str(error.get("mhs_code")) if error and error.get("mhs_code") else None

    def raise_for_status(self) -> "Receipt":
        if self.ok or self.pending:
            return self
        raise MHSRejected(self)


def _receipt(value: Any) -> Receipt:
    return value if isinstance(value, Receipt) else Receipt(value or {})


def _request_context(message: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``command_id`` and ``may_have_effect`` of a request (or batch) for error data."""
    messages = [message] if isinstance(message, Mapping) else list(message)
    effect = False
    command_ids: list[str] = []
    for item in messages:
        if not isinstance(item, Mapping):
            continue
        effect = effect or str(item.get("method") or "") in EFFECTFUL_METHODS
        params = item.get("params") if isinstance(item.get("params"), Mapping) else {}
        if isinstance(params.get("command_id"), str):
            command_ids.append(params["command_id"])
    data: dict[str, Any] = {"may_have_effect": effect}
    if len(command_ids) == 1:
        data["command_id"] = command_ids[0]
    elif command_ids:
        data["command_ids"] = command_ids
    return data


def _unavailable(target: str, reason: Any) -> TransportError:
    return TransportError(
        "MHS.TRANSPORT.UNAVAILABLE",
        f"cannot reach the MHS endpoint {target}: {reason}",
        {"may_have_effect": False, "details": {"endpoint": target, "reason": str(reason)[:300]}},
        retryable=True,
    )


def _lost_response(code: str, text: str, message: Any) -> MHSError:
    """The request was sent and no response came back (an outcome code is never retryable)."""
    data = _request_context(message)
    return MHSError(code, text, data, retryable=False if code.startswith("MHS.OUTCOME.") else None)


# ---------------------------------------------------------------------------
# stdio transport (T1)
# ---------------------------------------------------------------------------


class StdioTransport:
    """Newline-delimited JSON-RPC over a child process's stdin/stdout."""

    kind = "stdio"

    def __init__(self, argv: Sequence[str], *, env: Mapping[str, str] | None = None,
                 cwd: str | None = None, timeout: float = DEFAULT_TIMEOUT_S,
                 inherit_env: bool = True) -> None:
        self.argv = [str(part) for part in argv]
        self.timeout = float(timeout)
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._responses: dict[Any, dict[str, Any]] = {}
        self._notifications: list[dict[str, Any]] = []
        self._reader: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._stderr: list[str] = []
        self._closed = False
        self._failure: str | None = None
        child_env = dict(os.environ) if inherit_env else {}
        child_env.update(dict(env or {}))
        try:
            self._process = subprocess.Popen(
                self.argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=child_env,
                cwd=cwd,
            )
        except OSError as exc:
            raise _unavailable(" ".join(self.argv)[:200], exc) from exc
        self._reader = threading.Thread(target=self._read_loop, name="mhs-stdio-reader", daemon=True)
        self._reader.start()
        self._stderr_thread = threading.Thread(target=self._drain_stderr, name="mhs-stdio-stderr", daemon=True)
        self._stderr_thread.start()

    # -- reading -----------------------------------------------------
    def _read_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        stdout = self._process.stdout
        while True:
            try:
                # Bounded read: a malicious or broken endpoint cannot make the
                # client allocate an unbounded line.
                line = stdout.readline(MAX_MESSAGE_BYTES + 1)
            except (ValueError, OSError):
                break
            if not line:
                break
            if len(line) > MAX_MESSAGE_BYTES and not line.endswith(b"\n"):
                with self._condition:
                    self._failure = "endpoint message exceeded the size limit"
                    self._condition.notify_all()
                break
            text = line.strip()
            if not text:
                continue
            try:
                message = json.loads(text.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            self._dispatch(message)
        with self._condition:
            self._failure = self._failure or "endpoint closed the stdio channel"
            self._condition.notify_all()

    def _dispatch(self, message: Any) -> None:
        if isinstance(message, list):
            for item in message:
                self._dispatch(item)
            return
        if not isinstance(message, Mapping):
            return
        if "id" in message and ("result" in message or "error" in message):
            with self._condition:
                self._responses[message.get("id")] = dict(message)
                self._condition.notify_all()
            return
        if message.get("method"):
            with self._condition:
                self._notifications.append(dict(message))
                self._condition.notify_all()

    def _drain_stderr(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for line in self._process.stderr:
            if len(self._stderr) < 500:
                self._stderr.append(line.decode("utf-8", "replace").rstrip())
            else:
                self._stderr.pop(0)
                self._stderr.append(line.decode("utf-8", "replace").rstrip())

    # -- sending -----------------------------------------------------
    def _write(self, payload: bytes) -> None:
        assert self._process is not None and self._process.stdin is not None
        with self._lock:
            if self._failure:
                raise TransportError("MHS.TRANSPORT.CLOSED", f"cannot write to endpoint: {self._failure}",
                                     {"may_have_effect": False})
            try:
                self._process.stdin.write(payload)
                self._process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as exc:
                raise TransportError("MHS.TRANSPORT.CLOSED", f"cannot write to endpoint: {exc}",
                                     {"may_have_effect": False}) from exc

    def request(self, message: Mapping[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        request_id = message.get("id")
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        self._write(payload)
        deadline = time.time() + float(timeout or self.timeout)
        with self._condition:
            while request_id not in self._responses:
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise _lost_response("MHS.OUTCOME.TIMEOUT", "request deadline exceeded", message)
                if self._failure and request_id not in self._responses:
                    raise _lost_response(
                        "MHS.OUTCOME.UNKNOWN" if _request_context(message)["may_have_effect"]
                        else "MHS.TRANSPORT.CLOSED",
                        f"{self._failure} before the response arrived", message,
                    )
                self._condition.wait(min(remaining, 0.25))
            return self._responses.pop(request_id)

    def request_batch(
        self, messages: Sequence[Mapping[str, Any]], *, timeout: float | None = None
    ) -> list[dict[str, Any]]:
        """Send one JSON-RPC batch and return responses in request order."""
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        if not messages:
            raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "empty JSON-RPC batch")
        payload = json.dumps(list(messages), separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        self._write(payload)
        ids = [message.get("id") for message in messages]
        deadline = time.time() + float(timeout or self.timeout)
        with self._condition:
            while any(request_id not in self._responses for request_id in ids):
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise _lost_response("MHS.OUTCOME.TIMEOUT", "batch deadline exceeded", messages)
                if self._failure:
                    raise _lost_response(
                        "MHS.OUTCOME.UNKNOWN" if _request_context(messages)["may_have_effect"]
                        else "MHS.TRANSPORT.CLOSED",
                        f"{self._failure} before the batch response arrived", messages,
                    )
                self._condition.wait(min(remaining, 0.25))
            return [self._responses.pop(request_id) for request_id in ids]

    def notify(self, message: Mapping[str, Any]) -> None:
        payload = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        self._write(payload)

    def drain_notifications(self) -> list[dict[str, Any]]:
        with self._condition:
            pending = list(self._notifications)
            self._notifications.clear()
        return pending

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return list(self._stderr[-limit:])

    # -- lifecycle ---------------------------------------------------
    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        process = self._process
        if process is not None:
            try:
                if process.stdin:
                    process.stdin.close()
            except OSError:
                pass
            try:
                process.terminate()
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                try:
                    process.kill()
                    process.wait(timeout=5)
                except OSError:
                    pass
            for stream in (process.stdout, process.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except OSError:
                    pass
        if self._reader is not None:
            self._reader.join(timeout=2.0)
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=0.5)

    def __enter__(self) -> "StdioTransport":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# HTTP transport (T2)
# ---------------------------------------------------------------------------


class _EventStream:
    """One ``GET /mhs/v1/events`` stream (SSE is scoped to one session)."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.stop = threading.Event()
        self.response: Any = None
        self.sock: socket.socket | None = None
        self.thread: threading.Thread | None = None

    def interrupt(self) -> None:
        """Unblock a pending ``readline`` at once (``close()`` alone waits for the next frame)."""
        sock = self.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        response = self.response
        if response is not None:
            try:
                response.close()
            except Exception:  # noqa: BLE001 - close must be best effort
                pass


def _response_socket(response: Any) -> socket.socket | None:
    raw = getattr(getattr(response, "fp", None), "raw", None)
    sock = getattr(raw, "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


class HttpTransport:
    """JSON-RPC over ``POST /mhs/v1/rpc`` plus session-scoped SSE reader threads."""

    kind = "http"

    def __init__(self, base_url: str, *, token: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self.base_url = base_url.rstrip("/")
        self.rpc_url = self.base_url + "/mhs/v1/rpc"
        self.events_url = self.base_url + "/mhs/v1/events"
        self.token = token or os.environ.get("MHS_TOKEN")
        self.timeout = float(timeout)
        self._notifications: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._streams: dict[str, _EventStream] = {}
        self._closed = False

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _post(self, data: bytes, message: Any, timeout: float | None) -> bytes:
        request = urllib.request.Request(self.rpc_url, data=data, headers=self._headers(), method="POST")
        deadline = float(timeout or self.timeout)
        try:
            with urllib.request.urlopen(request, timeout=deadline) as response:
                return response.read(MAX_MESSAGE_BYTES + 1)
        except urllib.error.HTTPError:
            raise
        except urllib.error.URLError as exc:
            # urllib wraps every failure before the request was fully sent
            # (refused, DNS, unreachable, connect timeout): no effect possible.
            raise _unavailable(self.rpc_url, getattr(exc, "reason", exc)) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise _lost_response("MHS.OUTCOME.TIMEOUT", f"no response within {deadline:g} s: {exc}",
                                 message) from exc
        except (http.client.HTTPException, OSError) as exc:
            raise _lost_response("MHS.OUTCOME.UNKNOWN", f"connection lost before the response: {exc}",
                                 message) from exc

    def request(self, message: Mapping[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        data = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            body = self._post(data, message, timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read(MAX_MESSAGE_BYTES + 1) or b""
            try:
                payload = json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                payload = {}
            if isinstance(payload, Mapping) and ("result" in payload or "error" in payload):
                return dict(payload)
            raise TransportError(
                "MHS.TRANSPORT.PROTOCOL_ERROR", f"HTTP {exc.code} from endpoint: {body[:200]!r}"
            ) from exc
        if len(body) > MAX_MESSAGE_BYTES:
            raise TransportError(
                "MHS.LIMIT.PAYLOAD_TOO_LARGE", "endpoint response exceeded the size limit"
            )
        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("MHS.PROTOCOL.PARSE_ERROR", "endpoint returned non-JSON") from exc

    def request_batch(
        self, messages: Sequence[Mapping[str, Any]], *, timeout: float | None = None
    ) -> list[dict[str, Any]]:
        """Send one JSON-RPC HTTP batch and return responses in request order."""
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        if not messages:
            raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "empty JSON-RPC batch")
        data = json.dumps(list(messages), separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        try:
            body = self._post(data, messages, timeout)
        except urllib.error.HTTPError as exc:
            body = exc.read(MAX_MESSAGE_BYTES + 1) or b""
            raise TransportError(
                "MHS.TRANSPORT.PROTOCOL_ERROR", f"HTTP {exc.code} from endpoint: {body[:200]!r}"
            ) from exc
        if len(body) > MAX_MESSAGE_BYTES:
            raise TransportError("MHS.LIMIT.PAYLOAD_TOO_LARGE", "endpoint response exceeded the size limit")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportError("MHS.PROTOCOL.PARSE_ERROR", "endpoint returned non-JSON") from exc
        if not isinstance(payload, list):
            raise TransportError("MHS.PROTOCOL.INVALID_REQUEST", "batch response is not an array")
        by_id = {
            item.get("id"): dict(item)
            for item in payload
            if isinstance(item, Mapping) and "id" in item
        }
        return [by_id.get(message.get("id"), {"id": message.get("id"), "error": {
            "code": -32603,
            "message": "missing batch response",
            "data": {"mhs_code": "MHS.PROTOCOL.INVALID_REQUEST"},
        }}) for message in messages]

    def notify(self, message: Mapping[str, Any]) -> None:
        self.request(message)

    # -- SSE ---------------------------------------------------------
    def start_events(self, subscription_id: str | None = None,
                     session_id: str | None = None) -> None:
        """Start the event stream of ``session_id`` (one stream per session; idempotent).

        The endpoint serves ``GET /mhs/v1/events`` only for a live session
        (``?session_id=``) and delivers only that session's subscriptions.
        """
        key = str(session_id or "")
        with self._lock:
            if self._closed or key in self._streams:
                return
            query: dict[str, str] = {}
            if session_id:
                query["session_id"] = str(session_id)
            if subscription_id:
                query["subscription_id"] = str(subscription_id)
            stream = _EventStream(self.events_url + (("?" + urlencode(query)) if query else ""))
            stream.thread = threading.Thread(target=self._sse_loop, args=(stream,), name="mhs-sse", daemon=True)
            self._streams[key] = stream
        stream.thread.start()

    def _sse_loop(self, stream: _EventStream) -> None:
        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        while not stream.stop.is_set():
            try:
                request = urllib.request.Request(stream.url, headers=headers, method="GET")
                with urllib.request.urlopen(request, timeout=3600) as response:
                    stream.response = response
                    stream.sock = _response_socket(response)
                    while not stream.stop.is_set():
                        raw = response.readline(MAX_MESSAGE_BYTES + 1)
                        if not raw:
                            break
                        if len(raw) > MAX_MESSAGE_BYTES and not raw.endswith(b"\n"):
                            break
                        line = raw.decode("utf-8", "replace").strip()
                        if not line.startswith("data:"):
                            continue
                        try:
                            message = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        with self._lock:
                            self._notifications.append(message)
            except urllib.error.HTTPError as exc:
                # 400/401/403/404: no live session or not ours; retrying cannot help.
                if exc.code in (400, 401, 403, 404) or stream.stop.is_set():
                    break
                stream.stop.wait(0.5)
            except (urllib.error.URLError, TimeoutError, OSError, ValueError, AttributeError,
                    http.client.HTTPException):
                # ValueError/AttributeError: close() shut the response down mid-read.
                if stream.stop.is_set():
                    break
                stream.stop.wait(0.5)
            finally:
                stream.response = None
                stream.sock = None

    def drain_notifications(self) -> list[dict[str, Any]]:
        with self._lock:
            pending = list(self._notifications)
            self._notifications.clear()
        return pending

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return []

    def close(self) -> None:
        with self._lock:
            self._closed = True
            streams = list(self._streams.values())
        for stream in streams:
            stream.stop.set()
            stream.interrupt()
        for stream in streams:
            if stream.thread is not None and stream.thread is not threading.current_thread():
                stream.thread.join(timeout=1.0)

    def __enter__(self) -> "HttpTransport":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


class SSETransport(HttpTransport):
    """HTTP transport with a subscription-scoped SSE reader.

    The JSON-RPC calls are identical to :class:`HttpTransport`; the subclass
    starts the event-stream reader for one session immediately, so a caller
    that only needs notifications can use it directly::

        sse = SSETransport("http://127.0.0.1:7400",
                            subscription_id="sub_…", session_id="mhs_s_…")
        events = sse.drain_notifications()
    """

    kind = "sse"

    def __init__(
        self,
        base_url: str,
        *,
        subscription_id: str | None = None,
        session_id: str | None = None,
        token: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        super().__init__(base_url, token=token, timeout=timeout)
        self.subscription_id = subscription_id
        self.session_id = session_id
        self.start_events(subscription_id, session_id)

    def events(self, timeout: float = 0.0) -> list[dict[str, Any]]:
        """Drain buffered SSE notifications (optionally waiting up to ``timeout``)."""
        pending = self.drain_notifications()
        if timeout > 0 and not pending:
            deadline = time.time() + timeout
            while time.time() < deadline and not pending:
                time.sleep(0.02)
                pending = self.drain_notifications()
        return pending


# ---------------------------------------------------------------------------
# in-process transport
# ---------------------------------------------------------------------------


class InProcessTransport:
    """JSON-RPC to an :class:`mhs.server.MHSServer` in this process (``server.handle``).

    No socket and no child process: ``mhs serve <dir> --mcp`` and code files
    that build their own endpoint use it.  ``auth_token`` authenticates every
    request as that ``auth_tokens`` principal, like an HTTP bearer token.
    """

    kind = "inprocess"

    def __init__(self, server: Any, *, auth_token: str | None = None,
                 timeout: float = DEFAULT_TIMEOUT_S) -> None:
        if not callable(getattr(server, "handle", None)):
            raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "an in-process endpoint needs a server with handle()")
        self.server = server
        self.auth_token = auth_token
        self.timeout = float(timeout)
        self._closed = False

    def read_artifact(self, uri: str, *, session_id: str) -> dict[str, Any]:
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        return self.server.read_artifact(uri, session_id=session_id, auth_token=self.auth_token)

    def _handle(self, message: Mapping[str, Any]) -> Any:
        if self.auth_token is not None:
            response = self.server.handle(dict(message), auth_token=self.auth_token)
        else:
            response = self.server.handle(dict(message))
        return response.to_dict() if hasattr(response, "to_dict") else response

    def request(self, message: Mapping[str, Any], *, timeout: float | None = None) -> dict[str, Any]:
        if self._closed:
            raise TransportError("MHS.TRANSPORT.CLOSED", "transport is closed", {"may_have_effect": False})
        return self._handle(message)

    def request_batch(self, messages: Sequence[Mapping[str, Any]], *,
                      timeout: float | None = None) -> list[dict[str, Any]]:
        return [self.request(message, timeout=timeout) for message in messages]

    def notify(self, message: Mapping[str, Any]) -> None:
        self._handle(message)

    def drain_notifications(self) -> list[dict[str, Any]]:
        take = getattr(self.server, "take_notifications", None)
        if not callable(take):
            return []
        try:
            return list(take() or [])
        except Exception:  # noqa: BLE001 - notifications are best effort
            return []

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return []

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> "InProcessTransport":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


def transport_target(transport: Any) -> str:
    """A short description of where ``transport`` goes (URL, launch command or ``inprocess``)."""
    kind = getattr(transport, "kind", "")
    if kind in ("http", "sse"):
        return str(getattr(transport, "base_url", ""))
    if kind == "stdio":
        return " ".join(str(part) for part in getattr(transport, "argv", []))
    return str(kind or type(transport).__name__)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


def _caller_principal(principal: Mapping[str, Any] | None) -> dict[str, Any]:
    """The principal to claim; endpoint-owned ``x-meta`` members are never sent."""
    if principal is None:
        return {"id": "mhs-python-client", "kind": "service"}
    out = dict(principal)
    meta = out.get("x-meta")
    if isinstance(meta, Mapping):
        kept = {str(key): value for key, value in meta.items() if key not in _RESERVED_X_META}
        if kept:
            out["x-meta"] = kept
        else:
            out.pop("x-meta", None)
    elif "x-meta" in out:
        out.pop("x-meta", None)
    return out


class MHSClient:
    """High-level MHS client.  One instance per endpoint.

    Both spellings from the frozen interface are accepted::

        MHSClient(client_transport)
        MHSClient("http://127.0.0.1:7400", transport=None)
        MHSClient(endpoint="http://127.0.0.1:7400")
    """

    def __init__(
        self,
        endpoint: Any = None,
        transport: Any = None,
        *,
        endpoint_id: str | None = None,
    ) -> None:
        if transport is None:
            if endpoint is not None and hasattr(endpoint, "request") and hasattr(endpoint, "close"):
                transport, endpoint = endpoint, None
            elif endpoint is not None and callable(getattr(endpoint, "handle", None)) \
                    and not isinstance(endpoint, (str, list, tuple)):
                transport, endpoint = InProcessTransport(endpoint), None
            elif isinstance(endpoint, (list, tuple)):
                transport = StdioTransport([str(part) for part in endpoint])
                endpoint = None
            elif isinstance(endpoint, str):
                text = endpoint
                if text.startswith(("http://", "https://")):
                    transport = HttpTransport(text)
                elif text.startswith("mhs://"):
                    rest = text[len("mhs://"):]
                    host, _, _path = rest.partition("/")
                    if ":" not in host:
                        host = host + ":7400"
                    transport = HttpTransport("http://" + host)
                elif " " in text.strip():
                    import shlex

                    transport = StdioTransport(shlex.split(text))
                else:
                    raise MHSError(
                        "MHS.PROTOCOL.INVALID_REQUEST",
                        f"unsupported endpoint target: {endpoint!r}",
                    )
            else:
                raise MHSError(
                    "MHS.PROTOCOL.INVALID_REQUEST",
                    "MHSClient needs an endpoint URL, an argv list or a transport",
                )
        self.transport = transport
        self.endpoint_id = endpoint_id or (endpoint if isinstance(endpoint, str) else None)
        self.session_id: str | None = None
        self._request_seq = 0
        self._seq_lock = threading.Lock()
        # Notifications for other subscriptions are retained here so a client
        # with several subscriptions can drain them independently.
        self._event_backlog: list[dict[str, Any]] = []

    # -- JSON-RPC plumbing -------------------------------------------
    @property
    def supports_local_artifacts(self) -> bool:
        return isinstance(self.transport, InProcessTransport)

    @property
    def local_artifact_max_bytes(self) -> int:
        """Configured local store ceiling; never negotiated from remote output."""
        if not isinstance(self.transport, InProcessTransport) or self.transport._closed:
            return 0
        from .artifacts import LocalArtifactStore, MAX_ARTIFACT_BYTES
        store = getattr(self.transport.server, "_artifact_store", None)
        value = store.max_artifact_bytes if isinstance(store, LocalArtifactStore) else 0
        return value if type(value) is int and 0 < value <= MAX_ARTIFACT_BYTES else 0

    def read_artifact(self, uri: str, *, session_id: str) -> dict[str, Any]:
        """Retrieve a bounded artifact through this authenticated in-process client.

        Remote artifact transport is not defined by this SDK. Never interpret an
        artifact reference as a local file path or issue an ad-hoc HTTP request.
        """
        if not isinstance(self.transport, InProcessTransport):
            raise MHSError("MHS.PROTOCOL.UNSUPPORTED_FEATURE", "artifact retrieval requires InProcessTransport")
        return self.transport.read_artifact(uri, session_id=session_id)

    def _next_id(self) -> str:
        with self._seq_lock:
            self._request_seq += 1
            seq = self._request_seq
        return f"c{seq}-{int(time.time() * 1000) % 100000}"

    def request(self, method: str, params: Mapping[str, Any] | None = None, *,
                deadline_ms: int | None = None, timeout_s: float | None = None) -> Any:
        payload: dict[str, Any] = dict(params or {})
        if deadline_ms is not None and method not in (Method.HELLO,):
            payload.setdefault("deadline_ms", int(deadline_ms))
        if timeout_s is None:
            # The transport must never outlive the caller's declared budget by
            # more than the response round-trip grace.  Blocking methods all put
            # deadline_ms in params; non-blocking methods keep the transport
            # default.
            budget = payload.get("deadline_ms")
            if isinstance(budget, (int, float)) and not isinstance(budget, bool) and budget > 0:
                timeout_s = min(600.0, max(1.0, float(budget) / 1000.0 + 1.0))
        message = protocol.make_request(method, payload, id=self._next_id()).to_dict()
        try:
            response = self.transport.request(message, timeout=timeout_s)
        except MHSError as exc:
            if exc.code in ("MHS.OUTCOME.TIMEOUT", "MHS.OUTCOME.UNKNOWN"):
                # Every transport: the caller can reconcile by command_id.
                for key, value in _request_context(message).items():
                    exc.data.setdefault(key, value)
                lost = {"method": method, "code": exc.code, **_request_context(message)}
                _notify("lost", self, lost)
            raise
        if not isinstance(response, Mapping):
            raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "response is not a JSON object")
        # PROTO-006: correlate the response with this request; reject a foreign
        # protocol generation, a different id or a shape with neither outcome.
        if response.get("jsonrpc") != "2.0":
            raise MHSError(
                "MHS.TRANSPORT.PROTOCOL_ERROR",
                "response jsonrpc must be exactly '2.0'",
                {"details": {"received": response.get("jsonrpc")}},
            )
        expected_id = message.get("id")
        if response.get("error") and response.get("id") is None:
            # JSON-RPC 2.0: an error the endpoint could not tie to a request (an
            # HTTP 401 before the body was read, a parse error) has id null.
            raise error_from_json(response["error"])
        if expected_id is not None and response.get("id") != expected_id:
            raise MHSError(
                "MHS.TRANSPORT.PROTOCOL_ERROR",
                "response id does not match the request id",
                {"details": {"expected": expected_id, "received": response.get("id")}},
            )
        if "result" not in response and "error" not in response:
            raise MHSError(
                "MHS.TRANSPORT.PROTOCOL_ERROR",
                "response carries neither result nor error",
            )
        if response.get("error"):
            raise error_from_json(response["error"])
        result = response.get("result")
        if method in RECEIPT_METHODS and isinstance(result, Mapping) and result.get("receipt_id"):
            _notify("receipt", self, result)
        return result

    # -- discovery ---------------------------------------------------
    def hello(self) -> dict[str, Any]:
        result = self.request(Method.HELLO, {"client": dict(CLIENT_INFO),
                                             "protocol_versions": [protocol.MHS_VERSION]})
        if isinstance(result, Mapping) and result.get("endpoint_id"):
            self.endpoint_id = str(result["endpoint_id"])
        _notify("hello", self, dict(result or {}))
        return dict(result or {})

    def devices(self) -> list[dict[str, Any]]:
        # ``detail: full`` guarantees manifests (capability input schemas,
        # safety and fidelity), which is what hosts need to reason safely.
        result = self.request(Method.DEVICES_LIST, {"detail": "full"})
        return list((result or {}).get("devices") or [])

    def batch(self, calls: Sequence[Mapping[str, Any]], *, timeout: float | None = None) -> list[dict[str, Any]]:
        """Send a JSON-RPC batch.

        Each call is ``{"method": ..., "params": {...}}``.  The result is a
        list aligned with ``calls``: ``{"ok": true, "result": ...}`` or
        ``{"ok": false, "error": {...}}``.  Transport failures raise.
        """
        if not calls:
            return []
        prepared: list[dict[str, Any]] = []
        for call in calls:
            if not isinstance(call, Mapping) or not isinstance(call.get("method"), str):
                raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "batch calls need a method")
            params = call.get("params") or {}
            request_id = call.get("id") or self._next_id()
            prepared.append(
                protocol.make_request(str(call["method"]), dict(params), id=request_id).to_dict()
            )
        if not hasattr(self.transport, "request_batch"):
            # Transports without native batches still preserve call semantics.
            responses = [self.transport.request(message) for message in prepared]
        else:
            responses = self.transport.request_batch(
                prepared, timeout=timeout or max(30.0, float(self.transport.timeout))
            )
        output: list[dict[str, Any]] = []
        for message, response in zip(prepared, responses):
            if response.get("error"):
                output.append({"ok": False, "error": dict(response["error"])})
            else:
                result = response.get("result")
                if message.get("method") in RECEIPT_METHODS and isinstance(result, Mapping) \
                        and result.get("receipt_id"):
                    _notify("receipt", self, result)
                output.append({"ok": True, "result": result})
        return output

    def inspect(self, device_id: str | None = None) -> dict[str, Any]:
        result = self.request(Method.DEVICES_GET, {"device_id": device_id} if device_id else {})
        return dict((result or {}).get("device") or result or {})

    def get_schema(self, ref: str) -> dict[str, Any]:
        return dict(self.request(Method.SCHEMA_GET, {"ref": ref}) or {})

    def fetch_descriptor(self) -> dict[str, Any] | None:
        """Read the well-known descriptor over HTTP, when the transport is HTTP."""
        if getattr(self.transport, "kind", "") != "http":
            return None
        url = self.transport.base_url + "/.well-known/mhs.json"  # type: ignore[attr-defined]
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception:  # noqa: BLE001 - discovery is best-effort
            return None

    # -- sessions ----------------------------------------------------
    def open_session(
        self,
        device_ids: Sequence[str] | None = None,
        capabilities: Sequence[str] | None = None,
        mode: str | None = None,
        ttl_s: int = 600,
        principal: Mapping[str, Any] | None = None,
        approvals: Sequence[Mapping[str, Any]] | None = None,
        *,
        make_default: bool = True,
    ) -> dict[str, Any]:
        """Open a session; it becomes ``client.session_id`` unless ``make_default=False``.

        ``principal`` is a claim: with a bearer token the endpoint records the
        token's principal instead.  Endpoint-owned ``x-meta`` members
        (``authenticated``, ``role``, ``claimed_principal``) are never sent.
        """
        result = self.request(
            Method.SESSION_OPEN,
            {
                "principal": _caller_principal(principal),
                "device_ids": list(device_ids or []),
                "capabilities": list(capabilities or []),
                "mode": mode,
                "ttl_s": int(ttl_s),
                "approvals": list(approvals or []),
                "client_info": dict(CLIENT_INFO),
            },
        )
        session_id = (result or {}).get("session_id")
        if session_id and make_default:
            self.session_id = str(session_id)
        return dict(result or {})

    def heartbeat(self, session_id: str | None = None) -> dict[str, Any]:
        return dict(self.request(Method.SESSION_HEARTBEAT, {"session_id": session_id or self._require_session()}) or {})

    def close_session(self, session_id: str | None = None, *, timeout_s: float = 5.0) -> dict[str, Any]:
        target = session_id or self.session_id
        if not target:
            return {"closed_at": None}
        result = dict(
            self.request(Method.SESSION_CLOSE, {"session_id": target}, timeout_s=timeout_s) or {}
        )
        if target == self.session_id:
            self.session_id = None
        return result

    def device(
        self,
        device_id: str,
        *,
        capabilities: Sequence[str] | None = None,
        mode: str | None = None,
        ttl_s: int = 600,
        principal: Mapping[str, Any] | None = None,
        check: bool = False,
    ) -> "DeviceHandle":
        """A handle on one device that owns its own session (opened on first use)."""
        return DeviceHandle(self, device_id, capabilities=capabilities, mode=mode, ttl_s=ttl_s,
                            principal=principal, check=check)

    # -- reads -------------------------------------------------------
    def read(self, resource_id: str, device_id: str | None = None,
             fields: Sequence[str] | None = None, *,
             session_id: str | None = None,
             deadline_ms: int = 30_000) -> dict[str, Any]:
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "resource_id": resource_id,
            "deadline_ms": deadline_ms,
        }
        if device_id:
            params["device_id"] = device_id
        if fields:
            params["fields"] = list(fields)
        return dict(self.request(Method.RESOURCE_READ, params) or {})

    def write(self, resource_id: str, patch: Mapping[str, Any], *, device_id: str | None = None,
              session_id: str | None = None, expected_revision: int | None = None,
              command_id: str | None = None, deadline_ms: int = 30_000,
              check: bool = False) -> Receipt:
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "resource_id": resource_id,
            "patch": dict(patch),
            "deadline_ms": deadline_ms,
            "command_id": command_id or _ulid(),
        }
        if device_id:
            params["device_id"] = device_id
        if expected_revision is not None:
            params["expected_revision"] = int(expected_revision)
        receipt = _receipt(self.request(Method.RESOURCE_WRITE, params))
        return receipt.raise_for_status() if check else receipt

    # -- actuation ---------------------------------------------------
    def invoke(
        self,
        capability_id: str,
        input: Mapping[str, Any] | None = None,  # noqa: A002 - protocol name
        *,
        device_id: str | None = None,
        resource: str | None = None,
        expected_revision: int | None = None,
        deadline_ms: int = 30_000,
        permit_id: str | None = None,
        command_id: str | None = None,
        session_id: str | None = None,
        lease: str | None = None,
        check: bool = False,
        wait: bool = False,
        wait_timeout_s: float | None = None,
    ) -> Receipt:
        """Send one ``mhs.command`` and return its receipt.

        A rejected, failed or unknown outcome is a receipt, not an exception,
        unless ``check=True`` (then :class:`MHSRejected`).  ``wait=True``
        follows a ``running``/``accepted`` (or ``unknown``) receipt with an
        ``operation_id`` to its final receipt (:meth:`wait`).  The
        ``command_id`` (generated when omitted) is in the receipt and in the
        data of a transport timeout, so a retry can reuse it.
        """
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "capability_id": capability_id,
            "input": dict(input or {}),
            "command_id": command_id or _ulid(),
            "deadline_ms": int(deadline_ms),
        }
        if device_id:
            params["device_id"] = device_id
        if resource:
            params["resource"] = resource
        if expected_revision is not None:
            params["expected_revision"] = int(expected_revision)
        if permit_id:
            params["permit_id"] = permit_id
        if lease:
            params["lease"] = lease
        receipt = _receipt(self.request(Method.COMMAND, params,
                                        timeout_s=max(deadline_ms / 1000.0 + 0.75, 1.0)))
        operation_id = receipt.get("operation_id")
        if wait and isinstance(operation_id, str) and receipt.get("status") not in FINAL_STATUSES:
            receipt = self.wait(operation_id, timeout=wait_timeout_s, session_id=params["session_id"])
        return receipt.raise_for_status() if check else receipt

    def get_operation(self, operation_id: str, *, session_id: str | None = None,
                      deadline_ms: int = 10_000) -> Receipt:
        return _receipt(self.request(Method.OPERATIONS_GET, {
            "session_id": session_id or self._require_session(),
            "operation_id": operation_id,
            "deadline_ms": deadline_ms,
        }))

    def wait(self, operation_id: str, timeout: float | None = None, *, session_id: str | None = None,
             poll_s: float = 0.1) -> Receipt:
        """Poll ``mhs.operations.get`` until the operation's receipt is final.

        Final is ``completed``, ``failed``, ``rejected`` or ``cancelled``;
        ``unknown`` is not final (a later receipt reconciles it).  Raises
        ``MHS.OUTCOME.TIMEOUT`` (``data.operation_id``, ``may_have_effect``)
        when no final receipt arrived within ``timeout`` seconds (default 600).
        """
        limit = 600.0 if timeout is None else max(0.0, float(timeout))
        deadline = time.monotonic() + limit
        delay = max(0.01, float(poll_s))
        while True:
            receipt = self.get_operation(operation_id, session_id=session_id)
            if receipt.get("status") in FINAL_STATUSES:
                return receipt
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MHSError(
                    "MHS.OUTCOME.TIMEOUT",
                    f"operation {operation_id} is still {receipt.get('status')} after {limit:g} s",
                    {"operation_id": operation_id, "command_id": receipt.get("command_id"),
                     "may_have_effect": True, "status": receipt.get("status")},
                    retryable=False,
                )
            time.sleep(min(delay, remaining))
            delay = min(delay * 1.5, 1.0)

    def operations(self, device_id: str | None = None, *, session_id: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"session_id": session_id or self._require_session()}
        if device_id:
            params["device_id"] = device_id
        return dict(self.request(Method.OPERATIONS_LIST, params) or {})

    def cancel(self, operation_id: str, deadline_ms: int = 5_000, *,
               session_id: str | None = None, reason: str | None = None) -> Receipt:
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "operation_id": operation_id,
            "deadline_ms": deadline_ms,
        }
        if reason:
            params["reason"] = reason
        return _receipt(self.request(Method.OPERATIONS_CANCEL, params))

    # -- subscriptions ----------------------------------------------
    def subscribe(self, streams: Sequence[str] | str = ("state",), *,
                  device_id: str | None = None, session_id: str | None = None,
                  rate_hz: float | None = None,
                  filter: Mapping[str, Any] | None = None) -> str:
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "streams": [streams] if isinstance(streams, str) else list(streams),
            "deadline_ms": 30_000,
        }
        if device_id:
            params["device_id"] = device_id
        if rate_hz:
            params["rate_hz"] = float(rate_hz)
        if filter:
            params["filter"] = dict(filter)
        result = dict(self.request(Method.SUBSCRIBE, params) or {})
        subscription_id = str(result.get("subscription_id"))
        if getattr(self.transport, "kind", "") in ("http", "sse") and hasattr(self.transport, "start_events"):
            # SSE is session-scoped: one stream per session carries every
            # subscription of that session; the client filters by subscription_id.
            self.transport.start_events(session_id=params["session_id"])
        return subscription_id

    def unsubscribe(self, subscription_id: str, *, session_id: str | None = None) -> dict[str, Any]:
        return dict(self.request(Method.UNSUBSCRIBE, {
            "session_id": session_id or self._require_session(),
            "subscription_id": subscription_id,
        }) or {})

    def events(self, subscription_id: str | None = None, timeout: float = 1.0) -> list[dict[str, Any]]:
        """Drain notifications, optionally waiting up to ``timeout`` seconds.

        ``subscription_id`` filters ``mhs.event`` notifications for one
        subscription.  Notifications belonging to other subscriptions are kept
        in a bounded client-side backlog instead of being discarded, so
        draining one subscription does not starve another.
        """

        def collect() -> list[dict[str, Any]]:
            fresh = self.transport.drain_notifications()
            if isinstance(fresh, list):
                self._event_backlog.extend(fresh)
            if len(self._event_backlog) > 4096:
                # Keep the newest events; surface the loss explicitly.
                dropped = self._event_backlog[:-4096]
                self._event_backlog = self._event_backlog[-4096:]
                if subscription_id:
                    first = next(
                        (item for item in dropped
                         if (item.get("params") or {}).get("subscription_id") == subscription_id),
                        None,
                    )
                    if first is not None:
                        self._event_backlog.insert(
                            0,
                            {
                                "jsonrpc": "2.0",
                                "method": Method.EVENT,
                                "params": {
                                    "subscription_id": subscription_id,
                                    "stream": "control",
                                    "type": "gap",
                                    "payload": {"type": "gap", "dropped": len(dropped)},
                                },
                            },
                        )
            selected: list[dict[str, Any]] = []
            retained: list[dict[str, Any]] = []
            for item in self._event_backlog:
                if (
                    not subscription_id
                    or item.get("method") != Method.EVENT
                    or (item.get("params") or {}).get("subscription_id") == subscription_id
                ):
                    selected.append(item)
                else:
                    retained.append(item)
            self._event_backlog = retained
            return selected

        pending = collect()
        if timeout > 0 and not pending:
            deadline = time.time() + timeout
            while time.time() < deadline and not pending:
                time.sleep(0.02)
                pending = collect()
        return pending

    # -- snapshots ---------------------------------------------------
    def snapshot(self, device_id: str | None = None, *,
                 session_id: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"session_id": session_id or self._require_session(), "deadline_ms": 30_000}
        if device_id:
            params["device_id"] = device_id
        return dict(self.request(Method.SNAPSHOT, params) or {})

    def restore(self, snapshot: Any, device_id: str | None = None, *,
                session_id: str | None = None,
                command_id: str | None = None) -> Receipt:
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "snapshot": snapshot,
            "deadline_ms": 30_000,
        }
        if device_id:
            params["device_id"] = device_id
        if command_id:
            params["command_id"] = command_id
        return _receipt(self.request(Method.RESTORE, params))

    # -- safety ------------------------------------------------------
    def safety_status(self, device_id: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"deadline_ms": 10_000}
        if device_id:
            params["device_id"] = device_id
        return dict(self.request(Method.SAFETY_STATUS, params) or {})

    def estop(self, reason: str, device_id: str | None = None, *,
              session_id: str | None = None, deadline_ms: int = 10_000) -> Receipt:
        """Engage the e-stop of ``device_id``; no open session is needed.

        A session (``session_id`` or the client's) only attributes the stop to
        its principal; without one the endpoint attributes it to the caller.
        """
        params: dict[str, Any] = {"reason": reason, "deadline_ms": int(deadline_ms)}
        session = session_id or self.session_id
        if session:
            params["session_id"] = session
        if device_id:
            params["device_id"] = device_id
        return _receipt(self.request(Method.SAFETY_ESTOP, params))

    def reset(self, device_id: str | None = None, *, session_id: str | None = None) -> Receipt:
        params: dict[str, Any] = {"session_id": session_id or self._require_session(), "deadline_ms": 10_000}
        if device_id:
            params["device_id"] = device_id
        return _receipt(self.request(Method.SAFETY_RESET, params))

    def permit(
        self,
        capability_id: str,
        input: Mapping[str, Any] | None = None,
        ttl_s: int = 60,
        approvals: Sequence[Mapping[str, Any]] | None = None,
        *,
        input_digest: str | None = None,
        device_id: str | None = None,
        resource: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Request a permit bound to the exact action digest.

        Prefer passing the action ``input`` (and optionally ``device_id`` /
        ``resource``): the client computes PROTO-036's
        ``digest({capability_id, resource, input})``.  ``input_digest`` remains
        for callers that already computed it, but the server cannot verify it
        against the action unless ``input`` is also supplied.
        """
        params: dict[str, Any] = {
            "session_id": session_id or self._require_session(),
            "capability_id": capability_id,
            "ttl_s": int(ttl_s),
            "approvals": list(approvals or []),
        }
        if input is not None:
            if not isinstance(input, Mapping):
                raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "input must be an object")
            resolved_resource = resource or self.capability_resource(
                capability_id, device_id=device_id
            )
            if resolved_resource is None:
                raise MHSError(
                    "MHS.PROTOCOL.INVALID_PARAMS",
                    "capability is not bound to a resource; pass resource explicitly",
                    {"capability_id": capability_id},
                )
            params["input"] = dict(input)
            params["input_digest"] = canonical.digest(
                {"capability_id": capability_id, "resource": resolved_resource, "input": dict(input)}
            )
            params["resource"] = resolved_resource
        elif input_digest is not None:
            params["input_digest"] = input_digest
        else:
            raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", "permit() needs input or input_digest")
        if device_id:
            params["device_id"] = device_id
        return dict(self.request(Method.SAFETY_PERMIT, params) or {})

    def capability_resource(self, capability_id: str, *, device_id: str | None = None) -> str | None:
        """Resolve a capability's bound resource from cached device manifests."""
        cache = getattr(self, "_device_manifest_cache", None)
        if cache is None:
            try:
                discovered = self.devices()
            except Exception:  # noqa: BLE001 - caller may pass resource explicitly
                discovered = []
            cache = {}
            for manifest in discovered or []:
                if isinstance(manifest, Mapping):
                    cache[str(manifest.get("device_id"))] = manifest
            self._device_manifest_cache = cache
        candidates = [cache[device_id]] if device_id in cache else list(cache.values())
        for manifest in candidates:
            for capability in manifest.get("capabilities") or []:
                if isinstance(capability, Mapping) and capability.get("capability_id") == capability_id:
                    resource = capability.get("resource")
                    return str(resource) if isinstance(resource, str) else None
        return None

    # -- evidence ----------------------------------------------------
    def export_evidence(self, *, session_id: str | None = None) -> dict[str, Any]:
        """Export the endpoint's evidence bundle (no session needed; a given one is validated)."""
        params: dict[str, Any] = {}
        if session_id:
            params["session_id"] = session_id
        return dict(self.request(Method.EVIDENCE_EXPORT, params) or {})

    def verify_evidence(self, bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if bundle is not None:
            params["bundle"] = dict(bundle)
        return dict(self.request(Method.EVIDENCE_VERIFY, params) or {})

    # Canonical-interface aliases.
    evidence_export = export_evidence
    evidence_verify = verify_evidence
    schema = get_schema

    # -- misc --------------------------------------------------------
    def session(
        self,
        device_ids: Sequence[str] | None = None,
        capabilities: Sequence[str] | None = None,
        mode: str | None = None,
        ttl_s: int = 600,
        principal: Mapping[str, Any] | None = None,
    ):
        """Context manager that opens a least-privilege session and closes it."""
        return _SessionScope(self, device_ids, capabilities, mode, ttl_s, principal)

    def stderr_tail(self, limit: int = 20) -> list[str]:
        return list(getattr(self.transport, "stderr_tail", lambda **_: [])(limit=limit))

    def _require_session(self) -> str:
        if not self.session_id:
            raise MHSError("MHS.SESSION.UNKNOWN", "no session is open; call open_session() first")
        return self.session_id

    def close(self) -> None:
        try:
            if self.session_id:
                self.close_session(timeout_s=1.5)
        except Exception:  # noqa: BLE001 - closing must never raise
            pass
        self.transport.close()

    def __enter__(self) -> "MHSClient":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# per-device handle
# ---------------------------------------------------------------------------


class DeviceHandle:
    """One device of an endpoint with its own session (``client.device(device_id)``).

    The session is opened on first use with ``device_ids=[device_id]`` and never
    becomes ``client.session_id``, so handles on several devices of one client
    do not overwrite each other.  It is renewed with a heartbeat when less
    than a third of its TTL is left.  When the endpoint reports it expired,
    the call raises ``MHS.SESSION.EXPIRED`` (the device may have gone to its
    safe state: re-read state) and the next call opens a new session.
    ``check=True`` makes every receipt-returning call raise
    :class:`MHSRejected` for an outcome other than ``completed``.
    """

    def __init__(self, client: MHSClient, device_id: str, *, capabilities: Sequence[str] | None = None,
                 mode: str | None = None, ttl_s: int = 600, principal: Mapping[str, Any] | None = None,
                 check: bool = False) -> None:
        self.client = client
        self.device_id = str(device_id)
        self.capabilities = list(capabilities or [])
        self.mode = mode
        self.ttl_s = int(ttl_s)
        self.principal = dict(principal) if principal is not None else None
        self.check = bool(check)
        self.session_id: str | None = None
        self._renew_at = 0.0
        self._lock = threading.Lock()
        self.receipts: list[Receipt] = []

    # -- session -----------------------------------------------------
    def session(self) -> str:
        """The handle's session id (opened, or renewed by a heartbeat, as needed)."""
        with self._lock:
            if self.session_id is None:
                opened = self.client.open_session(
                    [self.device_id], self.capabilities, mode=self.mode, ttl_s=self.ttl_s,
                    principal=self.principal, make_default=False,
                )
                session_id = opened.get("session_id")
                if not session_id:
                    raise MHSError("MHS.SESSION.UNKNOWN", "mhs.session.open returned no session_id")
                self.session_id = str(session_id)
                self._renew_at = time.monotonic() + self.ttl_s * 2.0 / 3.0
            elif time.monotonic() >= self._renew_at:
                try:
                    self.client.heartbeat(self.session_id)
                except MHSError as exc:
                    if exc.code in _SESSION_LAPSED:
                        self.session_id = None
                        raise MHSError(
                            "MHS.SESSION.EXPIRED",
                            f"the session of {self.device_id} lapsed ({exc.code}); the device may have gone to its "
                            "safe state: re-read its state before continuing (the next call opens a new session)",
                            {"device_id": self.device_id, "session_renewed": False},
                            retryable=True,
                        ) from exc
                    raise
                self._renew_at = time.monotonic() + self.ttl_s * 2.0 / 3.0
            return self.session_id

    def _lapsed(self, exc: MHSError) -> None:
        if exc.code in _SESSION_LAPSED:
            with self._lock:
                self.session_id = None

    def _record(self, receipt: Receipt, check: bool | None) -> Receipt:
        self.receipts.append(receipt)
        return receipt.raise_for_status() if (self.check if check is None else check) else receipt

    # -- calls -------------------------------------------------------
    def invoke(self, capability_id: str, input: Mapping[str, Any] | None = None, *,  # noqa: A002
               check: bool | None = None, **kwargs: Any) -> Receipt:
        try:
            receipt = self.client.invoke(capability_id, input, device_id=self.device_id,
                                         session_id=self.session(), **kwargs)
        except MHSError as exc:
            self._lapsed(exc)
            raise
        return self._record(receipt, check)

    call = invoke

    def write(self, resource_id: str, patch: Mapping[str, Any], *, check: bool | None = None,
              **kwargs: Any) -> Receipt:
        try:
            receipt = self.client.write(resource_id, patch, device_id=self.device_id,
                                        session_id=self.session(), **kwargs)
        except MHSError as exc:
            self._lapsed(exc)
            raise
        return self._record(receipt, check)

    def read(self, resource_id: str | None = None, fields: Sequence[str] | None = None,
             **kwargs: Any) -> dict[str, Any]:
        target = resource_id or self._primary_resource()
        try:
            return self.client.read(target, device_id=self.device_id, fields=fields,
                                    session_id=self.session(), **kwargs)
        except MHSError as exc:
            self._lapsed(exc)
            raise

    def estop(self, reason: str = "code file requested an emergency stop") -> Receipt:
        # No session is opened for a stop: an e-stop never waits for one.
        return self._record(self.client.estop(reason, device_id=self.device_id, session_id=self.session_id),
                            False)

    def safety(self) -> dict[str, Any]:
        return self.client.safety_status(self.device_id)

    def manifest(self) -> dict[str, Any]:
        return self.client.inspect(self.device_id)

    def operations(self) -> dict[str, Any]:
        return self.client.operations(self.device_id, session_id=self.session())

    def cancel(self, operation_id: str, *, reason: str | None = None) -> Receipt:
        return self.client.cancel(operation_id, session_id=self.session(), reason=reason)

    def wait(self, operation_id: str, timeout: float | None = None, *, check: bool | None = None) -> Receipt:
        return self._record(self.client.wait(operation_id, timeout, session_id=self.session()), check)

    def snapshot(self) -> dict[str, Any]:
        return self.client.snapshot(self.device_id, session_id=self.session())

    def restore(self, snapshot: Any, *, check: bool | None = None, **kwargs: Any) -> Receipt:
        return self._record(self.client.restore(snapshot, self.device_id, session_id=self.session(), **kwargs),
                            check)

    def _primary_resource(self) -> str:
        manifest = self.client.inspect(self.device_id)
        for resource in manifest.get("resources") or []:
            if isinstance(resource, Mapping) and resource.get("resource_id"):
                return str(resource["resource_id"])
        raise MHSError("MHS.PROTOCOL.INVALID_PARAMS", f"{self.device_id} declares no resource; pass resource_id")

    # -- lifecycle ---------------------------------------------------
    def close(self) -> None:
        with self._lock:
            session_id, self.session_id = self.session_id, None
        if session_id:
            try:
                self.client.close_session(session_id, timeout_s=1.5)
            except Exception:  # noqa: BLE001 - closing must never raise
                pass

    def __enter__(self) -> "DeviceHandle":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"DeviceHandle({self.device_id!r}, session={self.session_id!r})"


# ---------------------------------------------------------------------------


def connect(
    target: str | Sequence[str] | None = None,
    *,
    argv: Sequence[str] | None = None,
    endpoint: str | None = None,
    **kwargs: Any,
) -> MHSClient:
    """Connect to an MHS endpoint.

    ``target`` is either an HTTP(S)/mhs:// URL or an argv sequence launching a
    stdio endpoint (the T1 binding).  ``argv=`` and ``endpoint=`` are accepted
    as explicit spellings of the same two forms::

        client = connect("http://127.0.0.1:7400")
        client = connect(["python3", "-m", "mhs.reference", "conveyor", "--stdio"])
        client = connect(argv=["python3", "-m", "mhs.reference", "conveyor", "--stdio"])
        client = connect(endpoint="http://127.0.0.1:7400")
        client = connect(server)          # an MHSServer in this process (mhs.adapter.load(...))

    ``token=`` is the bearer token (HTTP; in process: the ``auth_tokens``
    token).  An unreachable endpoint raises ``MHS.TRANSPORT.UNAVAILABLE``
    (retryable).
    """
    if argv is not None:
        target = list(argv)
    elif endpoint is not None:
        target = endpoint
    if target is None:
        raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "connect() needs an endpoint URL or an argv list")
    if not isinstance(target, (str, list, tuple)) and callable(getattr(target, "handle", None)):
        client = MHSClient(InProcessTransport(target, auth_token=kwargs.get("token"),
                                              timeout=kwargs.get("timeout", DEFAULT_TIMEOUT_S)))
        client.hello()
        return client
    if isinstance(target, (list, tuple)):
        transport = StdioTransport([str(part) for part in target],
                                   env=kwargs.get("env"), cwd=kwargs.get("cwd"),
                                   inherit_env=kwargs.get("inherit_env", True),
                                   timeout=kwargs.get("timeout", DEFAULT_TIMEOUT_S))
        client = MHSClient(transport)
        try:
            client.hello()
        except Exception:
            transport.close()
            raise
        return client
    text = str(target)
    if text.startswith("mhs+stdio://"):
        argv = text[len("mhs+stdio://"):].split(",")
        return connect(argv, **kwargs)
    if text.startswith(("http://", "https://")):
        transport = HttpTransport(text, token=kwargs.get("token"), timeout=kwargs.get("timeout", DEFAULT_TIMEOUT_S))
        client = MHSClient(transport)
        # PROTO-013: hello is the first call on every new connection, including
        # HTTP.  Without it the endpoint must refuse connection-scoped calls.
        client.hello()
        return client
    if text.startswith("mhs://"):
        # mhs:// authority defaults to http on port 7400 when no scheme is given
        rest = text[len("mhs://"):]
        host, _, path = rest.partition("/")
        port = "7400"
        if ":" in host:
            host, port = host.rsplit(":", 1)
        return connect(f"http://{host}:{port}", **kwargs)
    if text.startswith("stdio:"):
        return connect([part for part in text[len("stdio:"):].split(",") if part], **kwargs)
    if " " in text.strip():
        # A shell-style launch command is shorthand for the stdio argv binding.
        import shlex

        return connect(shlex.split(text), **kwargs)
    if os.path.exists(text) and text.endswith(".json"):
        raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", "pass an HTTP URL or an argv list, not a JSON path")
    raise MHSError("MHS.PROTOCOL.INVALID_REQUEST", f"unsupported endpoint target: {target!r}")


class _SessionScope:
    """``with client.session([...]) as session_id:`` helper."""

    def __init__(self, client: MHSClient, device_ids, capabilities, mode, ttl_s, principal) -> None:
        self.client = client
        self.device_ids = list(device_ids or [])
        self.capabilities = list(capabilities or [])
        self.mode = mode
        self.ttl_s = ttl_s
        self.principal = principal
        self.session_id: str | None = None

    def __enter__(self) -> str:
        opened = self.client.open_session(
            self.device_ids, self.capabilities, mode=self.mode,
            ttl_s=self.ttl_s, principal=self.principal,
        )
        self.session_id = str(opened.get("session_id") or "")
        return self.session_id

    def __exit__(self, *exc_info: Any) -> None:
        if self.session_id:
            try:
                self.client.close_session(self.session_id)
            except Exception:  # noqa: BLE001 - teardown must not mask the reason
                pass


def _ulid() -> str:
    from .canonical import ulid

    return ulid()


__all__ = [
    "CLIENT_INFO",
    "DeviceHandle",
    "EFFECTFUL_METHODS",
    "FINAL_STATUSES",
    "InProcessTransport",
    "MHSClient",
    "MHSRejected",
    "PENDING_STATUSES",
    "RECEIPT_METHODS",
    "Receipt",
    "SSETransport",
    "StdioTransport",
    "HttpTransport",
    "TransportError",
    "MAX_MESSAGE_BYTES",
    "add_observer",
    "connect",
    "transport_target",
]
