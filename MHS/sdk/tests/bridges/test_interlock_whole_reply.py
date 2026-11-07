"""An interlock reading must parse the whole reply (MERGE-B fix round; each failed first).

Ported verifier probes:

* ``scratch/verify-WP-05/round3/probes/r4_int_interlock.py`` (serial and SCPI),
  ``r5_server_int.py`` (end to end through ``MHSServer``) and
  ``r6_pyobj_int.py`` (python-object bridge);
* ``scratch/verify-MERGE-B/probes/v_interlock_numeric.py`` (end to end).

The blocker: for parse kinds ``int`` and ``float`` the bridges took the first
number found *anywhere* in the reply, so an error reply whose first number
equals ``closed_when`` (``'ERR 0'`` with ``closed_when: 0``, ``'E1 bad'`` with
``closed_when: 1``) read *closed*; the reset completed and the next actuation
reached the wire.  An interlock reading now has to match the whole stripped
reply (the default number pattern, or the declared pattern anchored at both
ends); anything else reads ``unknown`` and blocks the reset.  Capability and
state reads keep the lenient first-number parse.
"""

from __future__ import annotations

import unittest

from tests.bridges import support

from mhs.bridge.base import MappingError, parse_text
from mhs.bridge.python import PythonObjectBridge
from mhs.bridge.scpi import ScpiBridge
from mhs.bridge.serial import FakeSerial, SerialBridge
from mhs.bridge.transcript import Transcript
from mhs.server import Resource

DOOR = "tests.bridges.test_interlock_whole_reply:DoorDev"

# (reply, closed_when, expected state) for an int parse.
INT_CASES = (
    ("E0 unknown command", 0, "unknown"),
    ("E0: unknown command", 0, "unknown"),
    ("ERR 0", 0, "unknown"),
    ('0,"No error"', 0, "unknown"),
    ("-0.0", 0, "unknown"),
    ("E1 bad", 1, "unknown"),
    ("ERR 1: x", 1, "unknown"),
    ("ERR 1: bad command", 1, "unknown"),
    ("E1 syntax", 1, "unknown"),
    # controls: a plain number still reads closed or open
    ("0", 0, "closed"),
    (" 0 ", 0, "closed"),
    ("+0", 0, "closed"),
    ("1", 1, "closed"),
    ("1", 0, "open"),
    ("0", 1, "open"),
    ("10", 0, "open"),
)


def code_of(exc: BaseException | None) -> str | None:
    return getattr(exc, "code", None)


class DoorDev:
    """A native client whose ``ask(line)`` answers ``reply``."""

    reply = "ERR"

    def __init__(self) -> None:
        self.calls: list = []

    def ask(self, line: str) -> str:
        self.calls.append(line)
        return self.reply

    def clear(self) -> None:
        self.calls.append("clear")


def serial_bridge(reply: str, closed_when, parse=None) -> tuple[SerialBridge, FakeSerial]:
    serial = FakeSerial({"DOOR?": reply + "\n", "RST": "OK\n"}, default="OK\n")
    bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.2, "safety_bindings": {
        "reset": {"command": "RST"},
        "interlocks": [{"id": "door", "command": "DOOR?", "parse": parse or {"kind": "int"},
                        "closed_when": closed_when}]}},
        serial_factory=lambda **kw: serial)
    return bridge, serial


def scpi_bridge(reply: str, closed_when, parse=None) -> ScpiBridge:
    transcript = Transcript.from_json({"exchanges": [{"send": "DOOR?", "recv": reply}]})
    return ScpiBridge({"idn": False, "safety_bindings": {"interlocks": [
        {"id": "door", "query": "DOOR?", "parse": parse or {"kind": "int"}, "closed_when": closed_when}]}},
        transport=transcript.line_transport())


def python_bridge(reply: str, closed_when, parse=None) -> PythonObjectBridge:
    bridge = PythonObjectBridge({"target": DOOR, "safety_bindings": {
        "reset": {"native": "clear"},
        "interlocks": [{"id": "door", "native": "ask", "invoke": "query", "command": "DOOR?",
                        "parse": parse or {"kind": "int"}, "closed_when": closed_when}]}})
    bridge._ensure_loaded().reply = reply
    return bridge


class WholeReplyParseTests(unittest.TestCase):
    def test_whole_reply_numbers(self) -> None:
        for text, kind, expected in (("0", "int", 0), (" -12 ", "int", -12), ("3.5", "float", 3.5),
                                     ("-0.0", "float", -0.0), ("1e3", "float", 1000.0)):
            with self.subTest(text=text, kind=kind):
                self.assertEqual(parse_text(text, {"kind": kind}, whole=True), expected)
        for text, kind in (("ERR 0", "int"), ("E1 bad", "int"), ('0,"No error"', "int"), ("-0.0", "int"),
                           ("0.0 V", "float"), ("ERR 0.0", "float"), ("", "int")):
            with self.subTest(text=text, kind=kind):
                with self.assertRaises(MappingError):
                    parse_text(text, {"kind": kind}, whole=True)

    def test_a_declared_pattern_must_match_the_whole_reply(self) -> None:
        spec = {"kind": "int", "pattern": r"DOOR=(\d)", "group": 1}
        self.assertEqual(parse_text("DOOR=1", spec, whole=True), 1)
        for text in ("ERR DOOR=1", "DOOR=1 ERR", "DOOR=12"):
            with self.subTest(text=text):
                with self.assertRaises(MappingError):
                    parse_text(text, spec, whole=True)
        regex = {"kind": "regex", "pattern": "(CLOSED|OPEN)", "group": 1}
        self.assertEqual(parse_text("CLOSED", regex, whole=True), "CLOSED")
        with self.assertRaises(MappingError):
            parse_text("NOT CLOSED", regex, whole=True)

    def test_capability_reads_keep_the_first_number(self) -> None:
        # Only interlock readings are anchored; a value read stays lenient.
        self.assertEqual(parse_text("V=3.2 V", {"kind": "float"}), 3.2)
        self.assertEqual(parse_text("ERR 0", {"kind": "int"}), 0)


class NumericInterlockTests(unittest.TestCase):
    def test_serial_int_interlock(self) -> None:
        for reply, closed_when, expected in INT_CASES:
            with self.subTest(reply=reply, closed_when=closed_when):
                bridge, serial = serial_bridge(reply, closed_when)
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                    if expected == "closed":
                        self.assertEqual(bridge.reset()["reset"], True)
                    else:
                        with self.assertRaises(Exception) as caught:
                            bridge.reset()
                        self.assertEqual(code_of(caught.exception), "MHS.SAFETY.INTERLOCK_OPEN")
                        self.assertNotIn(b"RST\n", serial.written)
                finally:
                    bridge.close()

    def test_scpi_int_interlock(self) -> None:
        for reply, closed_when, expected in INT_CASES:
            with self.subTest(reply=reply, closed_when=closed_when):
                bridge = scpi_bridge(reply, closed_when)
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                finally:
                    bridge.close()

    def test_python_object_int_interlock_and_reset(self) -> None:
        for reply, closed_when, expected in INT_CASES:
            with self.subTest(reply=reply, closed_when=closed_when):
                bridge = python_bridge(reply, closed_when)
                native = bridge._ensure_loaded()
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                    if expected == "closed":
                        self.assertEqual(bridge.reset(), {"reset": True, "native": "clear"})
                    else:
                        with self.assertRaises(Exception) as caught:
                            bridge.reset()
                        self.assertEqual(code_of(caught.exception), "MHS.SAFETY.INTERLOCK_OPEN")
                        self.assertNotIn("clear", native.calls)
                finally:
                    bridge.close()

    def test_float_and_pattern_interlocks(self) -> None:
        cases = (
            ({"kind": "float"}, "ERR 0.0", 0, "unknown"),
            ({"kind": "float"}, "0.0", 0, "closed"),
            ({"kind": "int", "pattern": r"DOOR=(\d)", "group": 1}, "DOOR=1", 1, "closed"),
            ({"kind": "int", "pattern": r"DOOR=(\d)", "group": 1}, "ERR DOOR=1", 1, "unknown"),
            ({"kind": "regex", "pattern": "(CLOSED|OPEN)", "group": 1}, "CLOSED", "CLOSED", "closed"),
            ({"kind": "regex", "pattern": "(CLOSED|OPEN)", "group": 1}, "NOT CLOSED", "CLOSED", "unknown"),
            ({"kind": "str"}, "NOT CLOSED", "CLOSED", "open"),
        )
        for parse, reply, closed_when, expected in cases:
            for name, make in (("serial", lambda r, c, p: serial_bridge(r, c, p)[0]),
                               ("scpi", scpi_bridge), ("python", python_bridge)):
                with self.subTest(bridge=name, parse=parse, reply=reply):
                    bridge = make(reply, closed_when, parse)
                    try:
                        self.assertEqual(bridge.interlocks()[0]["state"], expected)
                    finally:
                        bridge.close()


class ServerNumericInterlockTests(unittest.TestCase):
    """End to end through ``MHSServer`` (probes r5_server_int.py, v_interlock_numeric.py)."""

    def _server(self, reply: str, closed_when: int):
        serial = FakeSerial({"LID?": reply + "\n", "STOP": "", "RST": "OK\n"}, default="OK\n")
        bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.2,
                               "capabilities": {"x-cap.heat.on.v1": {"command": "HEAT 1"}},
                               "safety_bindings": {"estop": {"command": "STOP"}, "reset": {"command": "RST"},
                                                   "interlocks": [{"id": "lid", "command": "LID?",
                                                                   "parse": {"kind": "int"},
                                                                   "closed_when": closed_when}]}},
                              serial_factory=lambda **kw: serial)
        device = support.simulated_device(
            "mhs://localhost:7797/lab/oven", resources=[Resource("instrument", "thermal.zone")],
            capabilities=[support.open_capability("x-cap.heat.on.v1", "instrument")], bridge=bridge)
        return support.Harness(device), serial, bridge

    def test_an_error_reply_never_allows_the_reset(self) -> None:
        for reply, closed_when in (("E0 unknown command", 0), ("ERR 0", 0), ("ERR 1: bad command", 1),
                                   ("E1 syntax", 1)):
            with self.subTest(reply=reply, closed_when=closed_when):
                harness, serial, bridge = self._server(reply, closed_when)
                try:
                    self.assertEqual(harness.estop()["status"], "completed")
                    receipt = harness.reset()
                    self.assertEqual(receipt.get("status"), "rejected", receipt)
                    error = receipt.get("error") or {}
                    self.assertEqual(error.get("mhs_code"), "MHS.SAFETY.RESET_REFUSED", receipt)
                    self.assertEqual((error.get("details") or {}).get("bridge_code"), "MHS.SAFETY.INTERLOCK_OPEN",
                                     receipt)
                    self.assertEqual([item.get("state") for item in error.get("interlocks") or []], ["unknown"])
                    self.assertNotEqual(harness.command("x-cap.heat.on.v1", {})["status"], "completed")
                    wire = [line.decode().strip() for line in serial.written]
                    self.assertNotIn("RST", wire)
                    self.assertNotIn("HEAT 1", wire)
                finally:
                    bridge.close()

    def test_control_a_plain_closed_value_resets(self) -> None:
        for reply, closed_when in (("0", 0), ("1", 1)):
            with self.subTest(reply=reply):
                harness, serial, bridge = self._server(reply, closed_when)
                try:
                    self.assertEqual(harness.estop()["status"], "completed")
                    self.assertEqual(harness.reset().get("status"), "completed")
                    self.assertEqual(harness.command("x-cap.heat.on.v1", {})["status"], "completed")
                    self.assertIn(b"HEAT 1\n", serial.written)
                finally:
                    bridge.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
