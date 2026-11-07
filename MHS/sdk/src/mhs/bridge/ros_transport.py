"""Bounded JSON WebSocket transport and ROS-free recording fake for rosbridge.

The optional ``websocket-client`` package is imported only on first I/O. A
transport is not an authorization boundary: RosDriver checks the hardware
review before constructing it. Nothing here contacts a peer on construction.
"""

from __future__ import annotations

import copy
import importlib
import json
import math
import queue
import select
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlsplit

from .transcript import TranscriptDivergence

__all__ = ["RecordingRosTransport", "WebSocketTransport"]


def _json_copy(value: Any, *, max_bytes: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("a rosbridge message must be an object")
    encoded = json.dumps(dict(value), ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > max_bytes:
        raise ValueError("rosbridge message exceeds max_message_bytes")
    return json.loads(encoded)


def _positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a finite positive number")
    return float(value)


@dataclass
class _Fragments:
    total: int
    deadline: float
    chunks: list[str] = field(default_factory=list)
    size: int = 0


class WebSocketTransport:
    """One rosbridge connection; no reconnect/replay after an uncertain send.

    ``send`` and ``recv`` can run concurrently. Once connected, the socket's
    short timeout remains fixed (it is not changed by concurrent operations).
    Each receive slice is bounded; callers implement the overall deadline.
    The URL must be ws/wss without credentials, fragments or query parameters.
    Configuration of authentication is deliberately outside this first helper.
    Text fragments are assembled in wire order within the same message budget.
    At most eight interleaved messages and 1024 parts per message are retained;
    each assembly must finish within ``timeout_s`` of its first part.
    """

    def __init__(self, url: str, *, timeout_s: float = 2.0, max_message_bytes: int = 1048576,
                 connector: Callable[..., Any] | None = None):
        parsed = urlsplit(url) if isinstance(url, str) else None
        if (parsed is None or parsed.scheme not in ("ws", "wss") or not parsed.hostname
                or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("rosbridge url must be ws:// or wss:// without credentials, query or fragment")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("invalid rosbridge URL port") from exc
        self.url = url
        self.timeout_s = _positive(timeout_s, "timeout_s")
        if isinstance(max_message_bytes, bool) or not isinstance(max_message_bytes, int) or max_message_bytes < 256:
            raise ValueError("max_message_bytes must be an integer of at least 256")
        self.max_message_bytes = max_message_bytes
        self._connector = connector
        self._socket: Any = None
        self._connect_lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._recv_lock = threading.Lock()
        self._fragment_lock = threading.Lock()
        self._fragments: dict[str, _Fragments] = {}
        self._fragment_bytes = 0
        self._closed = threading.Event()

    def _connect(self, timeout_s: float) -> Any:
        if self._closed.is_set():
            raise ConnectionError("rosbridge transport is closed")
        if self._socket is not None:
            return self._socket
        deadline = time.monotonic() + timeout_s
        if not self._connect_lock.acquire(timeout=timeout_s):
            raise TimeoutError("rosbridge connection deadline expired")
        try:
            if self._closed.is_set():
                raise ConnectionError("rosbridge transport is closed")
            if self._socket is None:
                connector = self._connector
                if connector is None:
                    try:
                        connector = importlib.import_module("websocket").create_connection
                    except ImportError as exc:
                        raise RuntimeError("the ROS hardware transport requires the optional websocket-client package") from exc
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("rosbridge connection deadline expired")
                connected = connector(self.url, timeout=remaining, enable_multithread=True,
                                      redirect_limit=0)
                # websocket-client shares one socket between its receive and send
                # locks. Keep its timeout fixed to avoid cross-thread mutation.
                connected.settimeout(0.02)
                if self._closed.is_set() or time.monotonic() >= deadline:
                    connected.close(timeout=0)
                    raise TimeoutError("rosbridge connection closed or exceeded its deadline")
                self._socket = connected
            return self._socket
        finally:
            self._connect_lock.release()

    def prepare(self, *, timeout_s: float | None = None) -> None:
        """Connect before the bridge acquires its short wire lock.

        The bridge rechecks its e-stop epoch and deadline after this returns,
        so a slow first connection can never send an old motion afterwards.
        """
        self._connect(_positive(self.timeout_s if timeout_s is None else timeout_s, "timeout_s"))

    def send(self, message: Mapping[str, Any], *, timeout_s: float | None = None) -> None:
        timeout = _positive(self.timeout_s if timeout_s is None else timeout_s, "timeout_s")
        payload = json.dumps(_json_copy(message, max_bytes=self.max_message_bytes), separators=(",", ":"))
        deadline = time.monotonic() + timeout
        if not self._send_lock.acquire(timeout=timeout):
            raise TimeoutError("rosbridge send deadline expired")
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("rosbridge send deadline expired")
            self._connect(remaining).send(payload)
        finally:
            self._send_lock.release()

    def _check_fragments_locked(self) -> None:
        if self._closed.is_set():
            raise ConnectionError("rosbridge transport is closed")
        if any(time.monotonic() >= item.deadline for item in self._fragments.values()):
            # A receive-slice TimeoutError is retryable; an expired partial
            # message is a protocol failure and must poison this connection.
            raise ValueError("rosbridge fragment assembly expired")

    def _accept_fragment(self, value: dict[str, Any]) -> tuple[str, float] | None:
        if set(value) != {"op", "id", "data", "num", "total"}:
            raise ValueError("malformed rosbridge fragment fields")
        ident, data, num, total = (value[key] for key in ("id", "data", "num", "total"))
        if (not isinstance(ident, str) or not ident or len(ident.encode("utf-8")) > 256
                or not isinstance(data, str) or not data
                or type(num) is not int or type(total) is not int
                or not 1 <= total <= 1024 or not 0 <= num < total):
            raise ValueError("malformed rosbridge fragment metadata")
        size = len(data.encode("utf-8"))
        with self._fragment_lock:
            self._check_fragments_locked()
            item = self._fragments.get(ident)
            if item is None:
                if num != 0 or len(self._fragments) >= 8:
                    raise ValueError("rosbridge fragment order or assembly count exceeds bounds")
                item = _Fragments(total, time.monotonic() + self.timeout_s)
                self._fragments[ident] = item
            if total != item.total or num != len(item.chunks):
                raise ValueError("conflicting, duplicate or out-of-order rosbridge fragment")
            if self._fragment_bytes + size > self.max_message_bytes:
                raise ValueError("rosbridge aggregate fragments exceed max_message_bytes")
            item.chunks.append(data)
            item.size += size
            self._fragment_bytes += size
            if len(item.chunks) != total:
                return None
            # Join under the short ownership lock, never while waiting for I/O.
            # The temporary joined copy has the same bounded aggregate size.
            raw = "".join(item.chunks)
            self._fragment_bytes -= item.size
            del self._fragments[ident]
            if time.monotonic() >= item.deadline:
                raise ValueError("rosbridge fragment assembly expired")
            return raw, item.deadline

    def _recv(self, peer: Any, deadline: float) -> dict[str, Any]:
        while True:
            with self._fragment_lock:
                self._check_fragments_locked()
            if time.monotonic() >= deadline:
                raise TimeoutError("rosbridge receive deadline expired")
            try:
                raw = peer.recv()
            except (TimeoutError, socket.timeout):
                if time.monotonic() >= deadline:
                    raise TimeoutError("rosbridge receive deadline expired") from None
                continue
            except Exception as exc:
                # websocket-client's timeout does not inherit socket.timeout.
                if type(exc).__name__ == "WebSocketTimeoutException":
                    if time.monotonic() >= deadline:
                        raise TimeoutError("rosbridge receive deadline expired") from None
                    continue
                raise ConnectionError("rosbridge receive failed") from exc
            if not isinstance(raw, str) or not raw:
                raise ConnectionError("rosbridge requires text JSON frames; peer closed or sent a binary frame")
            if len(raw.encode("utf-8")) > self.max_message_bytes:
                raise ValueError("rosbridge message exceeds max_message_bytes")
            # Reject non-finite values even though Python's json decoder accepts them.
            value = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
            assembly_deadline = None
            if isinstance(value, dict) and value.get("op") == "fragment":
                assembled = self._accept_fragment(value)
                if assembled is None:
                    continue  # Keep partial state across the bridge's short receive slices.
                raw, assembly_deadline = assembled
                value = json.loads(raw, parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
                if isinstance(value, dict) and value.get("op") in ("fragment", "png"):
                    raise ValueError("nested or compressed rosbridge fragments are unsupported")
            result = _json_copy(value, max_bytes=self.max_message_bytes)
            with self._fragment_lock:
                self._check_fragments_locked()
                if assembly_deadline is not None and time.monotonic() >= assembly_deadline:
                    raise ValueError("rosbridge fragment assembly expired")
                return result

    def buffered(self) -> bool:
        """True when the kernel socket already has bytes for another frame.

        This poll is not a ROS 1 freshness proof (BL-17). It does not see bytes that websocket-client has already
        pulled into its own buffer. Every ROS 1 stamp sample is discarded: a producer stamp is not a freshness
        proof, so a frame sitting only in that buffer does not count. The gate's evidence is the recording
        transport, whose queue is exact.
        """
        peer = self._socket
        sock = getattr(peer, "sock", None) if peer is not None else None
        if sock is None:
            return False
        try:
            readable, _, _ = select.select([sock], [], [], 0)
        except (OSError, ValueError):
            return False
        return bool(readable)

    def recv(self, *, timeout_s: float | None = None) -> dict[str, Any]:
        timeout = _positive(self.timeout_s if timeout_s is None else timeout_s, "timeout_s")
        deadline = time.monotonic() + timeout
        if not self._recv_lock.acquire(timeout=timeout):
            raise TimeoutError("rosbridge receive ownership deadline expired")
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("rosbridge receive deadline expired")
            return self._recv(self._connect(remaining), deadline)
        except TimeoutError:
            # A slice deadline does not erase a valid incomplete message.
            raise
        except BaseException:
            self.close()
            raise
        finally:
            self._recv_lock.release()

    def close(self) -> None:
        with self._fragment_lock:
            self._closed.set()
            self._fragments.clear()
            self._fragment_bytes = 0
        peer, self._socket = self._socket, None
        if peer is not None:
            try:
                peer.close(timeout=0)
            except Exception:
                pass


class RecordingRosTransport:
    """Deterministic, ROS-free recording fake with bounded event delivery.

    ``handler(message)`` may return one inbound JSON object, a sequence, or
    None. ``feed`` injects an interleaved topic event. Alternatively, strict
    ``exchanges=[{"send": {...}, "recv": {...}}]`` replay checks each request.
    A missing script request id is ignored during matching; a missing reply id
    on a service_response is filled from that request. No fake opens a socket.
    """

    def __init__(self, handler: Callable[[dict[str, Any]], Any] | None = None, *,
                 exchanges: Sequence[Mapping[str, Any]] | None = None, max_message_bytes: int = 1048576):
        if handler is not None and exchanges is not None:
            raise ValueError("choose a handler or strict exchanges")
        self.handler = handler
        self.exchanges = copy.deepcopy(list(exchanges)) if exchanges is not None else None
        self.max_message_bytes = max_message_bytes
        self.sent: list[dict[str, Any]] = []
        self._index = 0
        self._inbound: queue.Queue[Any] = queue.Queue()
        self._lock = threading.Lock()
        # The inbound queue only. ``send`` must not hold this across ``handler``: a handler that feeds terminal
        # messages and waits for the receiver calls ``buffered``, and that call must not need the handler's lock.
        self._inbound_lock = threading.Lock()
        self.closed = False

    def feed(self, message: Mapping[str, Any]) -> None:
        item = _json_copy(message, max_bytes=self.max_message_bytes)
        with self._inbound_lock:
            if self.closed:
                raise ConnectionError("recording ROS transport is closed")
            self._inbound.put(item)

    def send(self, message: Mapping[str, Any], *, timeout_s: float | None = None) -> None:
        if self.closed:
            raise ConnectionError("recording ROS transport is closed")
        outbound = _json_copy(message, max_bytes=self.max_message_bytes)
        with self._lock:
            if self.closed:
                raise ConnectionError("recording ROS transport is closed")
            self.sent.append(outbound)
            if self.exchanges is not None:
                if self._index >= len(self.exchanges):
                    raise TranscriptDivergence("ROS recording exhausted", got=outbound)
                exchange = self.exchanges[self._index]
                expected = exchange["send"]
                got = {k: v for k, v in outbound.items() if k != "id" or "id" in expected}
                if got != expected:
                    raise TranscriptDivergence("ROS request differs from recording", index=self._index,
                                              expected=expected, got=got)
                self._index += 1
                responses = copy.deepcopy(exchange.get("recv"))
                invoke = False
            else:
                invoke = True
                responses = None
        # The handler runs with neither lock held. It may feed messages and wait until the receiver has taken them.
        if invoke:
            responses = self.handler(copy.deepcopy(outbound)) if self.handler else None
        if isinstance(responses, Mapping):
            responses = [responses]
        prepared = []
        for response in responses or []:
            response = dict(response)
            if response.get("op") == "service_response" and "id" not in response:
                response["id"] = outbound.get("id")
            prepared.append(_json_copy(response, max_bytes=self.max_message_bytes))
        # The whole batch is queued before ``buffered`` can observe the queue, so a reader that woke on the first
        # frame still sees the rest. This lock is not the one held while the handler runs.
        with self._inbound_lock:
            if self.closed:
                raise ConnectionError("recording ROS transport is closed")
            for item in prepared:
                self._inbound.put(item)

    def buffered(self) -> bool:
        """True when another inbound message is already queued.

        The queue flag is not a ROS 1 freshness proof. Holding only the inbound lock keeps a handler that waits
        on the receiver from blocking this call, and holding it across the whole batch keeps that batch atomic.
        """
        with self._inbound_lock:
            return not self._inbound.empty()

    def recv(self, *, timeout_s: float | None = None) -> dict[str, Any]:
        if self.closed:
            raise ConnectionError("recording ROS transport is closed")
        try:
            message = self._inbound.get(timeout=_positive(0.05 if timeout_s is None else timeout_s, "timeout_s"))
        except queue.Empty:
            raise TimeoutError("no recorded ROS event") from None
        if message is None:
            raise ConnectionError("recording ROS transport is closed")
        return message

    def assert_complete(self) -> None:
        if self.exchanges is not None and self._index != len(self.exchanges):
            raise TranscriptDivergence("unconsumed ROS exchanges", index=self._index)
        if not self._inbound.empty():
            raise TranscriptDivergence("unread ROS events remain")

    def close(self) -> None:
        with self._lock:
            self.closed = True
        with self._inbound_lock:
            self.closed = True
            self._inbound.put(None)
