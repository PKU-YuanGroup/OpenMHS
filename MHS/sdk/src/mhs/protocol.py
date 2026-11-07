"""MHS wire protocol: JSON-RPC 2.0 messages, method names and helpers.

MHS/1.0 is JSON-RPC 2.0 over a transport binding (stdio NDJSON, HTTP POST +
SSE, WebSocket).  This module is the single import point for:

* protocol constants (``MHS_PROTOCOL_VERSION``, ``MCP_PROJECTION_VERSION``),
* the :class:`Method` namespace with every method name and notification name,
* :class:`Request`, :class:`Response` and :class:`Notification` dataclasses,
* :func:`encode_message` / :func:`decode_message` for one-message NDJSON,
* :func:`make_request`, :func:`make_result`, :func:`make_error`,
  :func:`make_event`, :func:`make_progress`, :func:`make_safety_alert`,
* deadline parsing and validation helpers,
* re-exports of the error registry (:data:`MHS_ERROR_CODES`,
  :class:`ErrorCode`, :class:`MHSError`) so binding authors need one import.

Encoding uses compact, key-sorted UTF-8 JSON with one message per line and a
trailing newline; key sorting makes request digests reproducible across
implementations.  ``params`` ordering is not semantic.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

from . import canonical
from .errors import (
    ERROR_CODES,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    MHS_ERROR_CODES,
    PARSE_ERROR,
    ErrorCode,
    MHSError,
    error_from_json,
    error_to_json,
    is_known_code,
)

__all__ = [
    "JSONRPC_VERSION",
    "MHS_VERSION",
    "MHS_PROTOCOL_VERSION",
    "MCP_PROJECTION_VERSION",
    "Method",
    "METHODS",
    "METHOD_NAMES",
    "NOTIFICATION_METHODS",
    "Request",
    "Response",
    "Notification",
    "ProtocolError",
    "decode_message",
    "encode_batch",
    "encode_json",
    "encode_message",
    "is_notification",
    "is_request",
    "is_response",
    "loads_strict",
    "make_error",
    "make_event",
    "make_notification",
    "make_progress",
    "make_request",
    "make_result",
    "make_safety_alert",
    "new_id",
    "parse_deadline",
    "validate_deadline",
    "MHS_ERROR_CODES",
    "ERROR_CODES",
    "ErrorCode",
    "MHSError",
    "error_from_json",
    "error_to_json",
    "PARSE_ERROR",
    "INVALID_REQUEST",
    "METHOD_NOT_FOUND",
    "INVALID_PARAMS",
    "INTERNAL_ERROR",
]

JSONRPC_VERSION = "2.0"
MHS_VERSION = "1.0"
MHS_PROTOCOL_VERSION = "1.0"
#: Version of the MCP projection defined by MHS-000 section 5.4 (T4).
MCP_PROJECTION_VERSION = "1.0"

#: Maximum deadline accepted by the reference endpoint, in milliseconds.
DEFAULT_MAX_DEADLINE_MS = 600_000
DEFAULT_DEADLINE_MS = 30_000


class ProtocolError(MHSError):
    """Raised for malformed wire messages (a subclass of :class:`MHSError`)."""


class Method:
    """Names of every MHS/1.0 method and notification.

    Usage::

        from mhs.protocol import Method
        client.request(Method.HELLO, {})
    """

    # Requests (architecture section 5.2).
    HELLO = "mhs.hello"
    DEVICES_LIST = "mhs.devices.list"
    DEVICES_GET = "mhs.devices.get"
    SCHEMA_GET = "mhs.schema.get"
    SESSION_OPEN = "mhs.session.open"
    SESSION_HEARTBEAT = "mhs.session.heartbeat"
    SESSION_CLOSE = "mhs.session.close"
    RESOURCE_READ = "mhs.resource.read"
    RESOURCE_WRITE = "mhs.resource.write"
    COMMAND = "mhs.command"
    OPERATIONS_GET = "mhs.operations.get"
    OPERATIONS_LIST = "mhs.operations.list"
    OPERATIONS_CANCEL = "mhs.operations.cancel"
    SUBSCRIBE = "mhs.subscribe"
    UNSUBSCRIBE = "mhs.unsubscribe"
    SNAPSHOT = "mhs.snapshot"
    RESTORE = "mhs.restore"
    SAFETY_STATUS = "mhs.safety.status"
    SAFETY_ESTOP = "mhs.safety.estop"
    SAFETY_RESET = "mhs.safety.reset"
    SAFETY_PERMIT = "mhs.safety.permit"
    EVIDENCE_EXPORT = "mhs.evidence.export"
    EVIDENCE_VERIFY = "mhs.evidence.verify"
    CONFORMANCE_REPORT = "mhs.conformance.report"
    COMPOSITION_RUN = "mhs.composition.run"
    REGISTRY_SEARCH = "mhs.registry.search"

    # Notifications.
    EVENT = "mhs.event"
    PROGRESS = "mhs.progress"
    SAFETY_ALERT = "mhs.safety.alert"


#: Method name -> metadata (blocking: MUST carry deadline_ms, level: M/S/O).
METHODS: dict[str, dict[str, Any]] = {
    Method.HELLO: {"blocking": False, "level": "M"},
    Method.DEVICES_LIST: {"blocking": False, "level": "M"},
    Method.DEVICES_GET: {"blocking": False, "level": "M"},
    Method.SCHEMA_GET: {"blocking": False, "level": "M"},
    Method.SESSION_OPEN: {"blocking": False, "level": "M"},
    Method.SESSION_HEARTBEAT: {"blocking": False, "level": "S"},
    Method.SESSION_CLOSE: {"blocking": False, "level": "M"},
    Method.RESOURCE_READ: {"blocking": True, "level": "M"},
    Method.RESOURCE_WRITE: {"blocking": True, "level": "S"},
    Method.COMMAND: {"blocking": True, "level": "M"},
    Method.OPERATIONS_GET: {"blocking": True, "level": "M"},
    Method.OPERATIONS_LIST: {"blocking": False, "level": "S"},
    Method.OPERATIONS_CANCEL: {"blocking": True, "level": "M"},
    Method.SUBSCRIBE: {"blocking": True, "level": "M"},
    Method.UNSUBSCRIBE: {"blocking": False, "level": "M"},
    Method.SNAPSHOT: {"blocking": True, "level": "S"},
    Method.RESTORE: {"blocking": True, "level": "S"},
    Method.SAFETY_STATUS: {"blocking": True, "level": "M"},
    Method.SAFETY_ESTOP: {"blocking": True, "level": "S"},
    Method.SAFETY_RESET: {"blocking": True, "level": "S"},
    Method.SAFETY_PERMIT: {"blocking": False, "level": "S"},
    Method.EVIDENCE_EXPORT: {"blocking": False, "level": "M"},
    Method.EVIDENCE_VERIFY: {"blocking": False, "level": "S"},
    Method.CONFORMANCE_REPORT: {"blocking": False, "level": "S"},
    Method.COMPOSITION_RUN: {"blocking": True, "level": "O"},
    # Method.REGISTRY_SEARCH is not an endpoint method (02 row 26 / PROTO-039:
    # the registry is a separate service, mhs.registry); an endpoint answers
    # it with MHS.PROTOCOL.METHOD_NOT_FOUND.  The constant stays for clients.
}
METHOD_NAMES: frozenset[str] = frozenset(METHODS)
NOTIFICATION_METHODS: frozenset[str] = frozenset(
    {Method.EVENT, Method.PROGRESS, Method.SAFETY_ALERT}
)

_UNSET = object()


# ---------------------------------------------------------------------------
# Message dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Request:
    """A JSON-RPC request or notification (``id=None`` means notification)."""

    method: str
    params: Any = field(default_factory=dict)
    id: str | int | None = None
    jsonrpc: str = JSONRPC_VERSION

    @property
    def is_notification(self) -> bool:
        """True when this message has no ``id`` and expects no response."""
        return self.id is None

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready request object."""
        message: dict[str, Any] = {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
        }
        if self.params is not None:
            message["params"] = self.params
        if self.id is not None:
            message["id"] = self.id
        return message

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> "Request":
        """Build a request from a decoded JSON object (lenient)."""
        return cls(
            method=str(obj.get("method", "")),
            params=obj.get("params", {}),
            id=obj.get("id"),
            jsonrpc=str(obj.get("jsonrpc", JSONRPC_VERSION)),
        )

    def to_bytes(self) -> bytes:
        """Encode this request as one NDJSON line."""
        return encode_message(self)

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        """Return a short debugging representation."""
        kind = "Notification" if self.is_notification else "Request"
        return f"{kind}({self.method!r}, id={self.id!r})"


@dataclass
class Response:
    """A JSON-RPC response: exactly one of ``result`` or ``error``."""

    id: str | int | None = None
    result: Any = _UNSET
    error: Mapping[str, Any] | None = None
    jsonrpc: str = JSONRPC_VERSION

    @property
    def ok(self) -> bool:
        """True when the response carries a result rather than an error."""
        return self.error is None

    def raise_for_error(self) -> "Response":
        """Raise :class:`MHSError` if this response is an error, else return self."""
        if self.error is not None:
            raise error_from_json(self.error)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready response object."""
        message: dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.error is not None:
            message["error"] = dict(self.error)
        else:
            message["result"] = None if self.result is _UNSET else self.result
        message["id"] = self.id
        return message

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> "Response":
        """Build a response from a decoded JSON object."""
        return cls(
            id=obj.get("id"),
            result=obj.get("result", _UNSET),
            error=obj.get("error"),
            jsonrpc=str(obj.get("jsonrpc", JSONRPC_VERSION)),
        )

    def to_bytes(self) -> bytes:
        """Encode this response as one NDJSON line."""
        return encode_message(self)


@dataclass
class Notification:
    """A JSON-RPC notification (no ``id``, no response)."""

    method: str
    params: Any = field(default_factory=dict)
    jsonrpc: str = JSONRPC_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready notification object."""
        return {
            "jsonrpc": self.jsonrpc,
            "method": self.method,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, obj: Mapping[str, Any]) -> "Notification":
        """Build a notification from a decoded JSON object."""
        return cls(
            method=str(obj.get("method", "")),
            params=obj.get("params", {}),
            jsonrpc=str(obj.get("jsonrpc", JSONRPC_VERSION)),
        )

    def to_bytes(self) -> bytes:
        """Encode this notification as one NDJSON line."""
        return encode_message(self)


# ---------------------------------------------------------------------------
# Encode / decode
# ---------------------------------------------------------------------------


def _json_bytes(obj: Any) -> bytes:
    """Compact, key-sorted UTF-8 JSON without a trailing newline."""
    return json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def encode_json(message: Any) -> bytes:
    """Encode a message (dataclass or dict) as UTF-8 JSON without a newline."""
    if isinstance(message, (Request, Response, Notification)):
        message = message.to_dict()
    return _json_bytes(message)


def encode_message(message: Any) -> bytes:
    """Encode one message as a single NDJSON line (UTF-8, trailing ``\\n``)."""
    return encode_json(message) + b"\n"


def encode_batch(messages: Iterable[Any]) -> bytes:
    """Encode a JSON-RPC batch as one NDJSON line."""
    return _json_bytes([_plain(m) for m in messages]) + b"\n"


def _plain(message: Any) -> Any:
    """Convert a message dataclass to its plain dict form."""
    if isinstance(message, (Request, Response, Notification)):
        return message.to_dict()
    return message


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not a valid JSON number")


def loads_strict(data: bytes | bytearray | str) -> Any:
    """Decode one JSON text strictly as RFC 8259 JSON.

    ``NaN``, ``Infinity`` and ``-Infinity`` (which :func:`json.loads` accepts
    by default) are refused, like invalid UTF-8 and malformed JSON, with
    :class:`ProtocolError` ``MHS.PROTOCOL.PARSE_ERROR``.  Every transport
    decodes requests with this function.
    """
    try:
        text = bytes(data).decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)
    except UnicodeDecodeError as exc:
        raise ProtocolError(
            ErrorCode.PROTOCOL_PARSE_ERROR, "message is not valid UTF-8", cause=exc
        ) from exc
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        raise ProtocolError(
            ErrorCode.PROTOCOL_PARSE_ERROR, f"invalid JSON: {getattr(exc, 'msg', exc)}", cause=exc
        ) from exc
    except RecursionError as exc:  # a line of 200,000 '[' fits the 1 MiB limit
        raise ProtocolError(
            ErrorCode.PROTOCOL_PARSE_ERROR, "invalid JSON: nesting is too deep", cause=exc
        ) from exc


def decode_message(data: bytes | bytearray | str | Any) -> Any:
    """Decode one JSON-RPC message (or a batch list) from ``data``.

    Returns a :class:`Request` (which may be a notification), a
    :class:`Response`, or a list of either for a batch.  Raises
    :class:`ProtocolError` for malformed framing.
    """
    if isinstance(data, (bytes, bytearray)):
        try:
            text = bytes(data).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError(
                ErrorCode.PROTOCOL_PARSE_ERROR, "message is not valid UTF-8", cause=exc
            ) from exc
    elif isinstance(data, str):
        text = data
    elif isinstance(data, Mapping):
        return _decode_object(data)
    else:
        raise ProtocolError(
            ErrorCode.PROTOCOL_INVALID_MESSAGE,
            f"cannot decode message of type {type(data).__name__}",
        )
    text = text.strip()
    if not text:
        raise ProtocolError(
            ErrorCode.PROTOCOL_PARSE_ERROR, "empty message (expected JSON per line)"
        )
    value = loads_strict(text)
    if isinstance(value, list):
        if not value:
            raise ProtocolError(
                ErrorCode.PROTOCOL_INVALID_REQUEST, "empty JSON-RPC batch"
            )
        return [_decode_object(item) for item in value]
    if not isinstance(value, Mapping):
        raise ProtocolError(
            ErrorCode.PROTOCOL_INVALID_REQUEST,
            "a JSON-RPC message must be an object or a batch array",
        )
    return _decode_object(value)


def _decode_object(obj: Mapping[str, Any]) -> Request | Response | Notification:
    """Decode one JSON object into a message dataclass."""
    version = obj.get("jsonrpc", JSONRPC_VERSION)
    if version != JSONRPC_VERSION:
        raise ProtocolError(
            ErrorCode.PROTOCOL_INVALID_REQUEST,
            f"unsupported jsonrpc version {version!r}",
        )
    if "method" in obj:
        method = obj["method"]
        if not isinstance(method, str) or not method:
            raise ProtocolError(
                ErrorCode.PROTOCOL_INVALID_REQUEST, "method must be a non-empty string"
            )
        if "id" in obj:
            if isinstance(obj["id"], bool) or not isinstance(
                obj["id"], (str, int, type(None))
            ):
                raise ProtocolError(
                    ErrorCode.PROTOCOL_INVALID_REQUEST,
                    "id must be a string, integer or null",
                )
        message = Request.from_dict(obj)
        if message.is_notification:
            return Notification(method=message.method, params=message.params)
        return message
    if "result" in obj or "error" in obj:
        if "result" in obj and "error" in obj:
            raise ProtocolError(
                ErrorCode.PROTOCOL_INVALID_MESSAGE,
                "response contains both result and error",
            )
        if "error" in obj:
            error = obj["error"]
            if not isinstance(error, Mapping):
                raise ProtocolError(
                    ErrorCode.PROTOCOL_INVALID_MESSAGE,
                    "error member must be an object",
                )
        return Response.from_dict(obj)
    raise ProtocolError(
        ErrorCode.PROTOCOL_INVALID_REQUEST,
        "message has neither method nor result/error",
    )


def is_request(value: Any) -> bool:
    """True for a :class:`Request` with an id (expects a response)."""
    return isinstance(value, Request) and not value.is_notification


def is_notification(value: Any) -> bool:
    """True for a :class:`Notification` or an id-less :class:`Request`."""
    return isinstance(value, Notification) or (
        isinstance(value, Request) and value.is_notification
    )


def is_response(value: Any) -> bool:
    """True for a :class:`Response`."""
    return isinstance(value, Response)


# ---------------------------------------------------------------------------
# Message factories
# ---------------------------------------------------------------------------


def new_id() -> str:
    """Return a fresh ULID suitable as a JSON-RPC request id."""
    return canonical.ulid()


def make_request(
    method: str, params: Mapping[str, Any] | None = None, id: Any = None
) -> Request:
    """Build a request; pass ``id=None`` (default) for a notification."""
    return Request(method=method, params=dict(params or {}), id=id)


def make_notification(method: str, params: Mapping[str, Any] | None = None) -> Notification:
    """Build a JSON-RPC notification."""
    return Notification(method=method, params=dict(params or {}))


def make_result(id: Any, result: Any) -> Response:
    """Build a success response."""
    return Response(id=id, result=result)


def make_error(
    id: Any,
    error: MHSError | str | None = None,
    message: str | None = None,
    data: Mapping[str, Any] | None = None,
) -> Response:
    """Build an error response from an :class:`MHSError` or an ``MHS.*`` code."""
    if isinstance(error, MHSError):
        mhs_error = error
    else:
        code = error or ErrorCode.INTERNAL_ERROR
        mhs_error = MHSError(code, message, data)
    return Response(id=id, error=mhs_error.to_error_object())


def _event_params(
    subscription_id: str,
    seq: int,
    stream: str,
    payload: Any,
    *,
    device_id: str | None = None,
    resource_id: str | None = None,
    revision: int | None = None,
    state_hash: str | None = None,
    type: str | None = None,
) -> dict[str, Any]:
    """Build the params object shared by subscription/safety notifications."""
    params: dict[str, Any] = {
        "subscription_id": subscription_id,
        "seq": int(seq),
        "ts": canonical.now_rfc3339(),
        "stream": stream,
        "payload": payload,
    }
    if device_id is not None:
        params["device_id"] = device_id
    if resource_id is not None:
        params["resource_id"] = resource_id
    if revision is not None:
        params["revision"] = revision
    if state_hash is not None:
        params["state_hash"] = state_hash
    if type is not None:
        params["type"] = type
    return params


def make_event(
    subscription_id: str,
    seq: int,
    stream: str,
    payload: Any,
    *,
    device_id: str | None = None,
    resource_id: str | None = None,
    revision: int | None = None,
    state_hash: str | None = None,
    type: str | None = None,
) -> Notification:
    """Build an ``mhs.event`` subscription notification (architecture section 5.2)."""
    return Notification(
        method=Method.EVENT,
        params=_event_params(
            subscription_id,
            seq,
            stream,
            payload,
            device_id=device_id,
            resource_id=resource_id,
            revision=revision,
            state_hash=state_hash,
            type=type,
        ),
    )


def make_progress(
    operation_id: str,
    percent: float | None = None,
    message: str | None = None,
    *,
    ticks: int | None = None,
    subscription_id: str | None = None,
    seq: int | None = None,
    device_id: str | None = None,
) -> Notification:
    """Build an ``mhs.progress`` notification for a long-running operation."""
    params: dict[str, Any] = {"operation_id": operation_id}
    if subscription_id is not None:
        params["subscription_id"] = subscription_id
    if seq is not None:
        params["seq"] = int(seq)
    if device_id is not None:
        params["device_id"] = device_id
    params["ts"] = canonical.now_rfc3339()
    if percent is not None:
        params["percent"] = float(percent)
    if ticks is not None:
        params["ticks"] = int(ticks)
    if message is not None:
        params["message"] = message
    return Notification(method=Method.PROGRESS, params=params)


def make_safety_alert(
    device_id: str,
    code: str,
    message: str = "",
    data: Mapping[str, Any] | None = None,
) -> Notification:
    """Build an ``mhs.safety.alert`` notification (e-stop, interlock change, ...)."""
    params: dict[str, Any] = {
        "device_id": device_id,
        "mhs_code": code,
        "message": message or code,
        "ts": canonical.now_rfc3339(),
    }
    if data:
        params.update(dict(data))
    return Notification(method=Method.SAFETY_ALERT, params=params)


# ---------------------------------------------------------------------------
# Deadlines
# ---------------------------------------------------------------------------


def validate_deadline(
    deadline_ms: Any,
    *,
    default: int | None = None,
    max_deadline_ms: int = DEFAULT_MAX_DEADLINE_MS,
    required: bool = False,
) -> int | None:
    """Validate a ``deadline_ms`` value and return it as an int.

    ``deadline_ms`` is a *duration from receipt*, not a wall-clock instant.
    Raises :class:`MHSError` with ``MHS.PROTOCOL.DEADLINE_INVALID`` when the value
    is not a positive integer within ``max_deadline_ms``.
    """
    if deadline_ms is None:
        if required and default is None:
            raise MHSError(
                ErrorCode.LIMIT_DEADLINE_INVALID,
                "deadline_ms is required for this method",
            )
        return default
    if isinstance(deadline_ms, bool) or not isinstance(deadline_ms, (int, float)):
        raise MHSError(
            ErrorCode.LIMIT_DEADLINE_INVALID,
            f"deadline_ms must be an integer, got {type(deadline_ms).__name__}",
        )
    value = int(deadline_ms)
    if value <= 0 or value > int(max_deadline_ms):
        raise MHSError(
            ErrorCode.LIMIT_DEADLINE_INVALID,
            f"deadline_ms must be in 1..{int(max_deadline_ms)}, got {value}",
            {"max_deadline_ms": int(max_deadline_ms)},
        )
    return value


def parse_deadline(
    params: Mapping[str, Any] | None,
    default: int | None = DEFAULT_DEADLINE_MS,
    *,
    max_deadline_ms: int = DEFAULT_MAX_DEADLINE_MS,
    required: bool = False,
) -> int | None:
    """Read and validate ``params["deadline_ms"]``; return the effective value."""
    if not isinstance(params, Mapping):
        params = {}
    return validate_deadline(
        params.get("deadline_ms"),
        default=default,
        max_deadline_ms=max_deadline_ms,
        required=required,
    )
