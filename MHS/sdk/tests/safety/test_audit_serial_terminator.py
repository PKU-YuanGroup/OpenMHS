"""An unterminated serial reply must not close an interlock (SAFE-012).

The serial bridge is line-oriented: a response is complete only when the
configured terminator has arrived. The read loop used to return any nonempty
buffer, so ``DOOR?`` answering ``ON`` with no newline was parsed as the boolean
closed value. A deadline or a read limit that stops on that partial buffer is
not a reading. The interlock stays ``unknown`` and reset stays refused.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from mhs.bridge.serial import FakeSerial, SerialBridge


def code_of(exc: BaseException) -> str | None:
    return getattr(exc, "code", None)


def door_bridge(serial: object, *, timeout_s: float = 0.2, timeout_ms: int = 200,
                terminator: str = "\n") -> SerialBridge:
    return SerialBridge(
        {
            "port": "/dev/fake",
            "timeout_s": timeout_s,
            "terminator": terminator,
            "safety_bindings": {
                "reset": {"command": "RST"},
                "interlocks": [{
                    "id": "door",
                    "command": "DOOR?",
                    "parse": {"kind": "bool"},
                    "closed_when": True,
                    "timeout_ms": timeout_ms,
                    "description": "door closed",
                }],
            },
        },
        serial_factory=lambda **_kwargs: serial,
    )


class _Chunks:
    """pyserial stand-in that yields scripted ``readline`` chunks, then nothing."""

    def __init__(self, chunks: list[bytes]):
        self._chunks = list(chunks)
        self.written: list[bytes] = []
        self.is_open = True

    def write(self, data: bytes) -> int:
        self.written.append(bytes(data))
        return len(data)

    def readline(self) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    def reset_input_buffer(self) -> None:
        return None

    def close(self) -> None:
        self.is_open = False


class UnterminatedSerialInterlockTests(unittest.TestCase):
    def test_on_without_a_newline_stays_unknown_and_blocks_reset(self) -> None:
        # Audit reproduction: FakeSerial, DOOR? -> ON, no newline.
        serial = FakeSerial({"DOOR?": "ON", "RST": "OK\n"})
        bridge = door_bridge(serial, timeout_s=0.1, timeout_ms=100)
        try:
            self.assertEqual(
                bridge.interlocks(),
                [{"id": "door", "state": "unknown", "description": "door closed"}],
            )
            with self.assertRaises(Exception) as caught:
                bridge.reset()
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.INTERLOCK_OPEN")
            self.assertNotIn(b"RST\n", serial.written)
        finally:
            bridge.close()

    def test_read_limit_stops_on_partial_on_and_stays_unknown(self) -> None:
        serial = _Chunks([b"O", b"N", b"\n"])
        bridge = door_bridge(serial, timeout_s=1.0, timeout_ms=1000)
        try:
            with patch("mhs.bridge.serial._MAX_READS_PER_TRANSACTION", 2):
                reported = bridge.interlocks()
            self.assertEqual(reported, [{"id": "door", "state": "unknown", "description": "door closed"}])
            self.assertEqual(serial._chunks, [b"\n"], "the terminator was still unread")
        finally:
            bridge.close()

    def test_empty_terminator_cannot_close_an_interlock_or_allow_reset(self) -> None:
        serial = FakeSerial({"DOOR?": "ON", "RST": "OK\n"})
        bridge = door_bridge(serial, terminator="")
        try:
            self.assertEqual(bridge.interlocks()[0]["state"], "unknown")
            with self.assertRaises(Exception) as caught:
                bridge.reset()
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.INTERLOCK_OPEN")
            self.assertNotIn(b"RST", serial.written)
        finally:
            bridge.close()

    def test_crlf_terminator_missing_from_a_newline_fragment_stays_unknown(self) -> None:
        serial = _Chunks([b"ON\n"])
        bridge = door_bridge(serial, terminator="\r\n", timeout_s=1.0, timeout_ms=1000)
        try:
            with patch("mhs.bridge.serial._MAX_READS_PER_TRANSACTION", 1):
                self.assertEqual(bridge.interlocks()[0]["state"], "unknown")
        finally:
            bridge.close()

    def test_a_terminated_on_still_reads_closed(self) -> None:
        serial = FakeSerial({"DOOR?": "ON\n", "RST": "OK\n"})
        bridge = door_bridge(serial)
        try:
            self.assertEqual(bridge.interlocks()[0]["state"], "closed")
            self.assertEqual(bridge.reset()["reset"], True)
            self.assertIn(b"RST\n", serial.written)
        finally:
            bridge.close()

    def test_a_reply_split_across_reads_is_closed_once_terminated(self) -> None:
        serial = _Chunks([b"O", b"N\n"])
        bridge = door_bridge(serial)
        try:
            self.assertEqual(bridge.interlocks()[0]["state"], "closed")
        finally:
            bridge.close()


if __name__ == "__main__":
    unittest.main()
