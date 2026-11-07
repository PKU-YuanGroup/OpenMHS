"""Record and replay line-oriented exchanges (serial, SCPI and HTTP-like transports).

A :class:`Transcript` is an ordered list of exchanges::

    {
      "transcript": "1.0",
      "name": "sr860-lockin",
      "terminator": "\\n",
      "exchanges": [
        {"send": "*IDN?", "recv": "Stanford_Research_Systems,SR860,003456,v1.47"},
        {"send": "FREQ 2000"},                       # a write: no response recorded
        {"send": "*RST", "recv": "OK", "recv_optional": true},   # response may be ignored
        {"send": {"method": "GET", "path": "/health"}, "recv": {"status": 200}}
      ]
    }

Replay is strict: every request must equal the next recorded ``send`` (exact
order, exact text or JSON value), a read needs a recorded ``recv``, a recorded
``recv`` must be read before the next request (unless the exchange is marked
``"recv_optional": true``), and :meth:`Transcript.assert_complete` fails while
exchanges -- or an unread response -- remain.  Any mismatch raises
:class:`TranscriptDivergence` (an ``AssertionError``), which the bridges
propagate unchanged, so a fake can never silently drift from the recording.

Three replay transports share one cursor:

* :meth:`Transcript.line_transport` -- ``write/read/query(line, timeout_s=)``,
  the interface :class:`mhs.bridge.scpi.ScpiBridge` uses;
* :meth:`Transcript.serial` -- a pyserial-like port for
  :class:`mhs.bridge.serial.SerialBridge` (``serial_factory=lambda **kw: t.serial()``);
* :meth:`Transcript.http` -- ``request(method, path, body=None)`` for HTTP-like clients.

:meth:`Transcript.recorder` wraps a live line transport and appends what it
sends and receives, so a session on real hardware becomes the fake for CI.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from typing import Any, Mapping, Sequence

from mhs.bridge.base import main as _bridge_main

__all__ = [
    "TRANSCRIPT_VERSION",
    "RecordingLineTransport",
    "ReplayHttp",
    "ReplayLineTransport",
    "ReplaySerial",
    "Transcript",
    "TranscriptDivergence",
    "main",
]

TRANSCRIPT_VERSION = "1.0"
_DOCUMENT_KEYS = {"transcript", "name", "terminator", "exchanges", "description"}
_EXCHANGE_KEYS = {"send", "recv", "recv_optional", "note"}


class TranscriptDivergence(AssertionError):
    """A replayed request differs from the recording (or the recording ran out)."""

    def __init__(self, message: str, *, index: int | None = None, expected: Any = None, got: Any = None):
        self.index = index
        self.expected = expected
        self.got = got
        super().__init__(message)


def _brief(value: Any) -> str:
    text = json.dumps(value, sort_keys=True) if not isinstance(value, str) else repr(value)
    return text if len(text) <= 120 else text[:117] + "..."


class Transcript:
    """An ordered, strictly replayed list of request/response exchanges."""

    def __init__(self, exchanges: Sequence[Mapping[str, Any]] = (), *, name: str | None = None,
                 terminator: str = "\n"):
        self.name = name or "transcript"
        self.terminator = str(terminator)
        self._exchanges: list[dict[str, Any]] = []
        for index, exchange in enumerate(exchanges):
            self._exchanges.append(self._check_exchange(exchange, index))
        self._cursor = 0
        self._pending: Any = None
        self._has_pending = False
        self._pending_optional = False
        self._lock = threading.RLock()

    # -- construction / persistence ----------------------------------------
    @staticmethod
    def _check_exchange(exchange: Any, index: int) -> dict[str, Any]:
        if not isinstance(exchange, Mapping):
            raise ValueError(f"exchanges[{index}] must be an object")
        unknown = set(exchange) - _EXCHANGE_KEYS
        if unknown:
            raise ValueError(f"exchanges[{index}] has unknown keys {sorted(unknown)}")
        if "send" not in exchange:
            raise ValueError(f"exchanges[{index}] needs a 'send'")
        if "recv_optional" in exchange and not isinstance(exchange["recv_optional"], bool):
            raise ValueError(f"exchanges[{index}].recv_optional must be a boolean")
        return copy.deepcopy(dict(exchange))

    @classmethod
    def from_json(cls, document: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> "Transcript":
        if isinstance(document, Mapping):
            unknown = set(document) - _DOCUMENT_KEYS
            if unknown:
                raise ValueError(f"transcript has unknown keys {sorted(unknown)}")
            version = document.get("transcript", TRANSCRIPT_VERSION)
            if str(version).split(".")[0] != TRANSCRIPT_VERSION.split(".")[0]:
                raise ValueError(f"unsupported transcript version {version!r}")
            return cls(document.get("exchanges") or [], name=document.get("name"),
                       terminator=document.get("terminator", "\n"))
        return cls(document)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "Transcript":
        with open(path, encoding="utf-8") as handle:
            return cls.from_json(json.load(handle))

    def to_json(self) -> dict[str, Any]:
        with self._lock:
            return {
                "transcript": TRANSCRIPT_VERSION,
                "name": self.name,
                "terminator": self.terminator,
                "exchanges": copy.deepcopy(self._exchanges),
            }

    def dump(self, path: str | os.PathLike[str]) -> None:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_json(), handle, indent=2, sort_keys=True)
            handle.write("\n")

    # -- recording ---------------------------------------------------------
    def record(self, send: Any, recv: Any = None) -> None:
        with self._lock:
            exchange: dict[str, Any] = {"send": copy.deepcopy(send)}
            if recv is not None:
                exchange["recv"] = copy.deepcopy(recv)
            self._exchanges.append(exchange)

    def _record_response(self, recv: Any) -> None:
        with self._lock:
            if not self._exchanges or "recv" in self._exchanges[-1]:
                raise ValueError("a response can only be recorded after its request")
            self._exchanges[-1]["recv"] = copy.deepcopy(recv)

    # -- replay ------------------------------------------------------------
    @property
    def position(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> list[dict[str, Any]]:
        with self._lock:
            return copy.deepcopy(self._exchanges[self._cursor:])

    def rewind(self) -> None:
        with self._lock:
            self._cursor = 0
            self._pending = None
            self._has_pending = False
            self._pending_optional = False

    def _unread_divergence(self, got: Any) -> TranscriptDivergence | None:
        """The divergence for a recorded response nobody read (``None`` when there is none)."""

        if not self._has_pending or self._pending_optional:
            return None
        index = self._cursor - 1
        return TranscriptDivergence(
            f"transcript {self.name!r}: the response {_brief(self._pending)} recorded for "
            f"{_brief(self._exchanges[index]['send'])} (exchange {index}) was never read; "
            "mark the exchange \"recv_optional\": true if the device's answer is ignored",
            index=index, expected=self._pending, got=got,
        )

    def send(self, message: Any) -> None:
        """Consume the next exchange; its ``send`` must equal ``message`` exactly."""

        with self._lock:
            unread = self._unread_divergence(message)
            if unread is not None:
                raise unread
            if self._cursor >= len(self._exchanges):
                raise TranscriptDivergence(
                    f"transcript {self.name!r} is exhausted after {len(self._exchanges)} exchanges; "
                    f"unexpected request {_brief(message)}",
                    index=self._cursor, expected=None, got=message,
                )
            expected = self._exchanges[self._cursor]
            if expected["send"] != message:
                raise TranscriptDivergence(
                    f"transcript {self.name!r} diverged at exchange {self._cursor}: expected "
                    f"{_brief(expected['send'])}, got {_brief(message)}",
                    index=self._cursor, expected=expected["send"], got=message,
                )
            self._cursor += 1
            self._has_pending = "recv" in expected
            self._pending_optional = bool(expected.get("recv_optional", False))
            self._pending = copy.deepcopy(expected.get("recv"))

    def receive(self) -> Any:
        """The response recorded for the last request (a read needs one)."""

        with self._lock:
            if not self._has_pending:
                previous = self._exchanges[self._cursor - 1]["send"] if self._cursor else None
                raise TranscriptDivergence(
                    f"transcript {self.name!r} has no response recorded after {_brief(previous)}",
                    index=self._cursor, expected=None, got="<read>",
                )
            value = self._pending
            self._pending = None
            self._has_pending = False
            self._pending_optional = False
            return value

    def exchange(self, message: Any) -> Any:
        """``send`` then return the recorded response, or ``None`` for a write-only exchange."""

        with self._lock:
            self.send(message)
            if not self._has_pending:
                return None
            return self.receive()

    def assert_complete(self) -> None:
        with self._lock:
            unread = self._unread_divergence(None)
            if unread is not None:
                raise unread
            if self._cursor < len(self._exchanges):
                left = self._exchanges[self._cursor:]
                raise TranscriptDivergence(
                    f"transcript {self.name!r} has {len(left)} unconsumed exchange(s), next "
                    f"{_brief(left[0]['send'])}",
                    index=self._cursor, expected=left[0]["send"], got=None,
                )

    # -- transports --------------------------------------------------------
    def line_transport(self) -> "ReplayLineTransport":
        return ReplayLineTransport(self)

    def serial(self, *, encoding: str = "ascii", **_options: Any) -> "ReplaySerial":
        return ReplaySerial(self, encoding=encoding)

    def http(self) -> "ReplayHttp":
        return ReplayHttp(self)

    def recorder(self, transport: Any) -> "RecordingLineTransport":
        return RecordingLineTransport(transport, self)


class ReplayLineTransport:
    """``write/read/query`` over a transcript (the ScpiBridge transport interface)."""

    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        self.closed = False

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        self.transcript.send(line)

    def read(self, *, timeout_s: float | None = None) -> str:
        return str(self.transcript.receive())

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        with self.transcript._lock:
            self.transcript.send(line)
            return str(self.transcript.receive())

    def interrupt(self) -> None:
        """Replay has nothing to interrupt."""

    def close(self) -> None:
        self.closed = True

    def describe(self) -> dict[str, Any]:
        return {"kind": "transcript", "name": self.transcript.name, "position": self.transcript.position}


class ReplaySerial:
    """A pyserial-like port that replays a transcript (``write``/``readline``).

    A recorded response stays pending in the transcript until the bridge reads
    it (``readline``/``read``), so a response the bridge never reads is a
    :class:`TranscriptDivergence` at the next request and in
    :meth:`Transcript.assert_complete` -- the same strict rule as
    :meth:`Transcript.line_transport` (``recv_optional`` exempts an exchange).
    Flushing the input buffer never discards an unread recorded line: bytes
    already fetched but not consumed are a divergence too.  A write-only
    exchange reads nothing (the device stays silent: a timeout).
    """

    def __init__(self, transcript: Transcript, *, encoding: str = "ascii"):
        self.transcript = transcript
        self.encoding = encoding
        self.terminator = transcript.terminator
        self.is_open = True
        self.timeout = 0.1
        self._partial = ""
        self._buffer = bytearray()
        self._buffer_optional = False
        self._lock = threading.Lock()

    def write(self, data: bytes) -> int:
        text = self._partial + bytes(data).decode(self.encoding, "replace")
        lines = text.split(self.terminator)
        self._partial = lines.pop()
        for line in lines:
            self.transcript.send(line.rstrip("\r"))   # the response stays pending until read
        return len(data)

    def _fetch(self) -> None:
        """Move the pending recorded response (if any) into the read buffer (lock held)."""

        transcript = self.transcript
        with transcript._lock:
            if not transcript._has_pending:
                return
            optional = transcript._pending_optional
            response = transcript.receive()
        if response is not None:
            self._buffer.extend((str(response) + self.terminator).encode(self.encoding))
            self._buffer_optional = optional

    def readline(self) -> bytes:
        with self._lock:
            marker = self.terminator.encode(self.encoding)
            if marker not in self._buffer:
                self._fetch()
            index = self._buffer.find(marker)
            if index < 0:
                chunk = bytes(self._buffer)
                self._buffer.clear()
                return chunk
            chunk = bytes(self._buffer[: index + len(marker)])
            del self._buffer[: index + len(marker)]
            return chunk

    def read(self, size: int = 1) -> bytes:
        with self._lock:
            if len(self._buffer) < size:
                self._fetch()
            chunk = bytes(self._buffer[:size])
            del self._buffer[:size]
            return chunk

    def reset_input_buffer(self) -> None:
        with self._lock:
            if self._buffer and not self._buffer_optional:
                unread = bytes(self._buffer).decode(self.encoding, "replace")
                self._buffer.clear()
                raise TranscriptDivergence(
                    f"transcript {self.transcript.name!r}: the recorded response data {_brief(unread)} "
                    "was never read before the input buffer was flushed",
                    index=self.transcript.position - 1, expected=unread, got="<flush>",
                )
            self._buffer.clear()

    def close(self) -> None:
        self.is_open = False


class ReplayHttp:
    """``request(method, path, body=None)`` over a transcript of JSON exchanges."""

    def __init__(self, transcript: Transcript):
        self.transcript = transcript

    def request(self, method: str, path: str, *, body: Any = None, headers: Mapping[str, str] | None = None) -> Any:
        message: dict[str, Any] = {"method": str(method).upper(), "path": str(path)}
        if body is not None:
            message["body"] = body
        return self.transcript.exchange(message)


class RecordingLineTransport:
    """Wrap a live line transport and append every exchange to a transcript."""

    def __init__(self, inner: Any, transcript: Transcript):
        self.inner = inner
        self.transcript = transcript

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        self.inner.write(line, timeout_s=timeout_s)
        self.transcript.record(line)

    def read(self, *, timeout_s: float | None = None) -> str:
        value = self.inner.read(timeout_s=timeout_s)
        self.transcript._record_response(value)
        return value

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        value = self.inner.query(line, timeout_s=timeout_s)
        self.transcript.record(line, value)
        return value

    def interrupt(self) -> None:
        interrupt = getattr(self.inner, "interrupt", None)
        if callable(interrupt):
            interrupt()

    def close(self) -> None:
        self.inner.close()


def main(argv: Sequence[str] | None = None) -> int:
    """Not a launcher: print the usage line and return 2."""

    return _bridge_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
