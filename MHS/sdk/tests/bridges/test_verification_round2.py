"""Regressions found by the second independent WP-05 verification (each failed first).

Ported verifier probes (scratch/verify-WP-05/round2/probes/):

* q1_interlock_bool.py, q5_pyobj_interlock.py, q6_server_reset.py (blocker):
  parse kind ``bool`` read every token except ``1``/``ON``/``TRUE`` as
  ``False``, so an inverted-sense interlock (``closed_when: false``, e.g.
  ``DOOR:OPEN?``) read an error, empty or garbage reply as *closed*; through
  ``MHSServer`` the reset and the next actuation completed;
* q2_serial_race.py (major): a serial transaction (or SCPI exchange) that had
  passed the e-stop epoch check still put its command on the wire after the
  e-stop command;
* q3_gym_box2d.py: a multi-dimensional ``Box`` (and ``MultiDiscrete``) action
  got no element limits, so out-of-range actions reached ``env.step``;
* q4_serial_unread.py: serial transcript replay dropped a recorded response
  the bridge never read;
* non-finite numbers reached command templates and natives when the argument
  declared no type (``VOLT nan``).
"""

from __future__ import annotations

import math
import threading
import time
import unittest

from tests.bridges import support

from mhs.bridge.base import FieldMapping, MappingError, format_command, parse_text
from mhs.bridge.bindings import parse_spec_errors, validate_binding
from mhs.bridge.gymnasium import GymnasiumBridge
from mhs.bridge.python import PythonObjectBridge
from mhs.bridge.scpi import ScpiBridge
from mhs.bridge.serial import FakeSerial, SerialBridge
from mhs.bridge.transcript import Transcript, TranscriptDivergence
from mhs.errors import MHSError
from mhs.server import Resource

DOOR = "tests.bridges.test_verification_round2:DoorDev"
MALFORMED = ("ERR", "", '-113,"Undefined header"', "2", "maybe")


def code_of(exc: BaseException | None) -> str | None:
    return getattr(exc, "code", None)


class DoorDev:
    """A native client whose ``ask(line)`` answers ``reply`` (probe q5)."""

    reply = "ERR"

    def __init__(self) -> None:
        self.calls: list = []

    def ask(self, line: str) -> str:
        self.calls.append(line)
        return self.reply

    def door_open(self):
        self.calls.append("door_open")
        return self.reply

    def clear(self) -> None:
        self.calls.append("clear")


def inverted_serial(responses: dict, **safety) -> tuple[SerialBridge, FakeSerial]:
    serial = FakeSerial(responses, default="OK\n")
    bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.2, "safety_bindings": {
        **safety,
        "interlocks": [{"id": "door", "command": "DOOR:OPEN?", "parse": {"kind": "bool"}, "closed_when": False}]}},
        serial_factory=lambda **kw: serial)
    return bridge, serial


# ---------------------------------------------------------------------------
# blocker: a malformed reply must never read as a closed interlock
# ---------------------------------------------------------------------------


class StrictBoolParseTests(unittest.TestCase):
    def test_only_recognised_tokens_parse(self) -> None:
        for text in ("1", "on", "TRUE", " 1 \r\n"):
            with self.subTest(text=text):
                self.assertIs(parse_text(text, {"kind": "bool"}), True)
        for text in ("0", "off", "False", "0\n"):
            with self.subTest(text=text):
                self.assertIs(parse_text(text, {"kind": "bool"}), False)
        for text in MALFORMED:
            with self.subTest(text=text):
                with self.assertRaises(MappingError):
                    parse_text(text, {"kind": "bool"})

    def test_declared_true_and_false_tokens(self) -> None:
        spec = {"kind": "bool", "true": "CLOSED", "false": "OPEN"}
        self.assertIs(parse_text("closed", spec), True)
        self.assertIs(parse_text("OPEN", spec), False)
        for text in ("AJAR", "1", "0", ""):
            with self.subTest(text=text):
                with self.assertRaises(MappingError):
                    parse_text(text, spec)

    def test_validator_needs_a_false_token_for_a_custom_true_token(self) -> None:
        self.assertEqual(parse_spec_errors({"kind": "bool"}), [])
        self.assertEqual(parse_spec_errors({"kind": "bool", "true": "1"}), [])
        self.assertEqual(parse_spec_errors({"kind": "bool", "true": "CLOSED", "false": "OPEN"}), [])
        self.assertTrue(parse_spec_errors({"kind": "bool", "true": "CLOSED"}))
        self.assertTrue(parse_spec_errors({"kind": "bool", "true": "X", "false": "x"}))
        self.assertTrue(parse_spec_errors({"kind": "bool", "true": "0"}))   # collides with the default false

    def test_a_malformed_boolean_readback_is_an_error_not_false(self) -> None:
        serial = FakeSerial({"OUTP?": "ERR\n"})
        bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.2, "capabilities": {
            "x-cap.test.output.v1": {"command": "OUTP?", "parse": {"kind": "bool", "field": "on"}}}},
            serial_factory=lambda **kw: serial)
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.test.output.v1", {})
            self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.OUTPUT_INVALID")
            serial.responses["OUTP?"] = "0\n"
            self.assertEqual(bridge.call("x-cap.test.output.v1", {}), {"on": False})
        finally:
            bridge.close()


class InterlockMalformedReplyTests(unittest.TestCase):
    def test_serial_inverted_interlock(self) -> None:
        for reply, expected in (("1", "open"), ("0", "closed"), *((bad, "unknown") for bad in MALFORMED)):
            with self.subTest(reply=reply):
                bridge, _serial = inverted_serial({"DOOR:OPEN?": reply + "\n"})
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                finally:
                    bridge.close()

    def test_scpi_inverted_interlock(self) -> None:
        for reply, expected in (("1", "open"), ("0", "closed"), *((bad, "unknown") for bad in MALFORMED)):
            with self.subTest(reply=reply):
                transcript = Transcript.from_json({"exchanges": [{"send": "DOOR:OPEN?", "recv": reply}]})
                bridge = ScpiBridge({"idn": False, "safety_bindings": {"interlocks": [
                    {"id": "door", "query": "DOOR:OPEN?", "parse": {"kind": "bool"}, "closed_when": False}]}},
                    transport=transcript.line_transport())
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                finally:
                    bridge.close()

    def test_python_object_inverted_interlock_and_reset(self) -> None:
        for reply, expected in (("1", "open"), ("0", "closed"), *((bad, "unknown") for bad in MALFORMED)):
            with self.subTest(reply=reply):
                bridge = PythonObjectBridge({"target": DOOR, "safety_bindings": {
                    "reset": {"native": "clear"},
                    "interlocks": [{"id": "door", "native": "ask", "invoke": "query", "command": "DOOR:OPEN?",
                                    "parse": {"kind": "bool"}, "closed_when": False}]}})
                native = bridge._ensure_loaded()
                native.reply = reply
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

    def test_python_object_boolean_closed_when_only_matches_a_boolean(self) -> None:
        for value, expected in ((False, "closed"), (True, "open"), (0, "unknown"), ("ERR", "unknown"),
                                (None, "unknown")):
            with self.subTest(value=value):
                bridge = PythonObjectBridge({"target": DOOR, "safety_bindings": {"interlocks": [
                    {"id": "door", "native": "door_open", "invoke": "call", "closed_when": False}]}})
                bridge._ensure_loaded().reply = value
                try:
                    self.assertEqual(bridge.interlocks()[0]["state"], expected)
                finally:
                    bridge.close()

    def test_serial_reset_is_refused_on_a_malformed_reply(self) -> None:
        bridge, serial = inverted_serial({"DOOR:OPEN?": "ERR\n", "RST": "OK\n"}, reset={"command": "RST"})
        try:
            with self.assertRaises(Exception) as caught:
                bridge.reset()
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.INTERLOCK_OPEN")
            self.assertNotIn(b"RST\n", serial.written)
        finally:
            bridge.close()

    def _server(self, door_reply: str):
        serial = FakeSerial({"DOOR:OPEN?": door_reply, "STOP": "", "RST": "OK\n"}, default="OK\n")
        bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.2,
                               "capabilities": {"x-cap.heat.on.v1": {"command": "HEAT 1"}},
                               "safety_bindings": {"estop": {"command": "STOP"}, "reset": {"command": "RST"},
                                                   "interlocks": [{"id": "door", "command": "DOOR:OPEN?",
                                                                   "parse": {"kind": "bool"},
                                                                   "closed_when": False}]}},
                              serial_factory=lambda **kw: serial)
        device = support.simulated_device(
            "mhs://localhost:7799/lab/oven", resources=[Resource("instrument", "thermal.zone")],
            capabilities=[support.open_capability("x-cap.heat.on.v1", "instrument")], bridge=bridge)
        return support.Harness(device), serial, bridge

    def test_server_rejects_reset_and_actuation_on_a_malformed_reply(self) -> None:
        for reply in ('-113,"Undefined header"\n', "ERR\n", "\n"):
            with self.subTest(reply=reply):
                harness, serial, bridge = self._server(reply)
                try:
                    self.assertEqual(harness.estop()["status"], "completed")
                    receipt = harness.reset()
                    self.assertEqual(receipt.get("status"), "rejected", receipt)
                    # The server (WP-04 4a1) answers a refused reset with
                    # RESET_REFUSED and keeps the bridge's INTERLOCK_OPEN refusal.
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

    def test_server_control_closed_door_resets(self) -> None:
        harness, serial, bridge = self._server("0\n")
        try:
            self.assertEqual(harness.estop()["status"], "completed")
            self.assertEqual(harness.reset().get("status"), "completed")
            self.assertEqual(harness.command("x-cap.heat.on.v1", {})["status"], "completed")
            self.assertIn(b"HEAT 1\n", serial.written)
        finally:
            bridge.close()

    def test_boolean_closed_when_and_bool_parse_go_together(self) -> None:
        serial = FakeSerial({})
        bad = (
            {"id": "door", "command": "DOOR?", "parse": {"kind": "int"}, "closed_when": False},
            {"id": "door", "command": "DOOR?", "parse": {"kind": "bool"}, "closed_when": 1},
            {"id": "door", "command": "DOOR?", "parse": {"kind": "bool", "true": "CLOSED"}},
        )
        for spec in bad:
            with self.subTest(bridge="serial", spec=spec):
                with self.assertRaises(Exception) as caught:
                    SerialBridge({"port": "/dev/fake", "safety_bindings": {"interlocks": [spec]}},
                                 serial_factory=lambda **kw: serial)
                self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
            scpi_spec = {("query" if key == "command" else key): value for key, value in spec.items()}
            with self.subTest(bridge="scpi", spec=scpi_spec):
                with self.assertRaises(Exception) as caught:
                    ScpiBridge({"idn": False, "safety_bindings": {"interlocks": [scpi_spec]}},
                               transport=Transcript([]).line_transport())
                self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")
        with self.assertRaises(Exception) as caught:
            PythonObjectBridge({"target": DOOR, "safety_bindings": {"interlocks": [
                {"id": "door", "native": "ask", "invoke": "query", "command": "DOOR?",
                 "parse": {"kind": "bool"}, "closed_when": "CLOSED"}]}}, load=False)
        self.assertEqual(code_of(caught.exception), "MHS.ADAPTER.MANIFEST_INVALID")


# ---------------------------------------------------------------------------
# major: nothing actuating reaches the wire after the e-stop command
# ---------------------------------------------------------------------------


class SlowFlush(FakeSerial):
    """Blocks the first transaction inside ``reset_input_buffer`` (after the epoch check)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.in_flush = threading.Event()
        self.release = threading.Event()

    def reset_input_buffer(self) -> None:
        if not self.release.is_set():
            self.in_flush.set()
            self.release.wait(2.0)
        super().reset_input_buffer()


class EstopWireOrderTests(unittest.TestCase):
    def _assert_nothing_after(self, wire: list[str], stop: str, actuation: str) -> None:
        self.assertIn(stop, wire)
        after = wire[wire.index(stop) + 1:]
        self.assertNotIn(actuation, after, f"{actuation!r} reached the wire after the e-stop: {wire}")

    def test_serial_transaction_past_the_epoch_check(self) -> None:
        serial = SlowFlush({"HEAT 1": "OK\n"})
        bridge = SerialBridge({"port": "/dev/fake", "timeout_s": 0.3, "capabilities": {
            "x-cap.heat.on.v1": {"command": "HEAT {on}", "args": {"on": {"from": "input.on"}}}},
            "safety_bindings": {"estop": {"command": "STOP"}}}, serial_factory=lambda **kw: serial)
        holder: dict = {}

        def run() -> None:
            try:
                holder["result"] = bridge.call("x-cap.heat.on.v1", {"on": 1})
            except BaseException as exc:  # noqa: BLE001
                holder["error"] = exc

        worker = threading.Thread(target=run)
        try:
            worker.start()
            self.assertTrue(serial.in_flush.wait(2.0))
            self.assertEqual(bridge.estop("probe q2")["performed"], ["STOP"])
            serial.release.set()
            worker.join(3.0)
            wire = [line.decode().strip() for line in serial.written]
            self.assertEqual(wire, ["STOP"])
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
        finally:
            serial.release.set()
            bridge.close()

    def test_scpi_exchange_past_the_epoch_check(self) -> None:
        recorded = Transcript()
        transport = recorded.recorder(_SilentLine())
        bridge = ScpiBridge({"idn": False, "commands": {"x-cap.test.volt.v1": {
            "resource": "psu", "write": "VOLT {value:g}", "args": {"value": {"from": "input.volts"}}}},
            "safety_bindings": {"estop": {"write": "OUTP OFF"}}}, transport=transport)
        passed = threading.Event()
        release = threading.Event()
        original = bridge._refuse_if_estopped

        def gated(epoch, label):
            original(epoch, label)
            wire_lock = getattr(bridge, "_wire_lock", None)
            if ("VOLT" in label and not passed.is_set() and bridge._txn_lock._is_owned()
                    and not (wire_lock is not None and wire_lock.locked())):
                passed.set()   # past the check, not yet on the wire
                release.wait(2.0)

        bridge._refuse_if_estopped = gated
        holder: dict = {}

        def run() -> None:
            try:
                holder["result"] = bridge.call("x-cap.test.volt.v1", {"volts": 5})
            except BaseException as exc:  # noqa: BLE001
                holder["error"] = exc

        worker = threading.Thread(target=run)
        try:
            worker.start()
            self.assertTrue(passed.wait(2.0))
            estop = threading.Thread(target=lambda: bridge.estop("probe q2 scpi"))
            estop.start()
            estop.join(0.5)
            release.set()
            worker.join(3.0)
            estop.join(3.0)
            wire = [exchange["send"] for exchange in recorded.to_json()["exchanges"]]
            self._assert_nothing_after(wire, "OUTP OFF", "VOLT 5")
            self.assertEqual(wire, ["OUTP OFF"])
            self.assertEqual(code_of(holder.get("error")), "MHS.SAFETY.ESTOP_ENGAGED", holder)
        finally:
            release.set()
            bridge.close()

    def test_scpi_queries_still_replay_as_one_exchange(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "*IDN?", "recv": support.IDN},
                                                         {"send": "FREQ?", "recv": "1000.0"}]})
        bridge = ScpiBridge({"commands": {"x-cap.test.frequency.v1": {
            "resource": "lockin", "query": "FREQ?", "parse": {"kind": "float"},
            "result": {"map": {"frequency": "output.$"}}}}}, transport=transcript.line_transport())
        try:
            self.assertEqual(bridge.call("x-cap.test.frequency.v1", {}), {"frequency": 1000.0})
            transcript.assert_complete()
        finally:
            bridge.close()


class _SilentLine:
    """A live line transport stand-in that accepts writes (and answers nothing)."""

    def write(self, line: str, *, timeout_s: float | None = None) -> None:
        return None

    def read(self, *, timeout_s: float | None = None) -> str:
        raise TimeoutError("nothing to read")

    def query(self, line: str, *, timeout_s: float | None = None) -> str:
        raise TimeoutError("nothing to read")

    def interrupt(self) -> None:
        return None

    def close(self) -> None:
        return None


# ---------------------------------------------------------------------------
# minors
# ---------------------------------------------------------------------------


class Box2D:
    """A (2, 2) box with per-element bounds, duck-typed under another class name (probe q3)."""

    def __init__(self) -> None:
        self.low = [[-1.0, -2.0], [-3.0, -4.0]]
        self.high = [[1.0, 2.0], [3.0, 4.0]]
        self.shape = (2, 2)
        self.dtype = "float32"


class MultiDiscrete:
    def __init__(self, nvec: list[int], start: list[int] | None = None) -> None:
        self.nvec = list(nvec)
        if start is not None:
            self.start = list(start)
        self.shape = (len(self.nvec),)
        self.dtype = "int64"


class MultiBinary:
    def __init__(self, n: int) -> None:
        self.n = int(n)
        self.shape = (self.n,)
        self.dtype = "int8"


class SpaceEnv:
    def __init__(self, action_space) -> None:
        self.action_space = action_space
        self.observation_space = support.Box([-10.0], [10.0])
        self.actions: list = []

    def reset(self, seed=None, options=None):
        return [0.0], {}

    def step(self, action):
        self.actions.append(action)
        return [0.0], 0.0, False, False, {}


class GymElementLimitTests(unittest.TestCase):
    def _step(self, bridge: GymnasiumBridge, action: dict):
        return bridge.call("cap.world.step.v1", {"action": action, "ticks": 1})

    def test_multi_dimensional_box_gets_per_element_limits(self) -> None:
        env = SpaceEnv(Box2D())
        bridge = GymnasiumBridge(env=env)
        try:
            rule = bridge.action_limits()["action.values"]
            self.assertEqual(list(rule["min"]), [-1.0, -2.0, -3.0, -4.0])
            self.assertEqual(list(rule["max"]), [1.0, 2.0, 3.0, 4.0])
            for values in ([100, 100, 100, 100], [0.0, 0.0, 0.0, -4.5], [1.5, 0.0, 0.0, 0.0]):
                with self.subTest(values=values):
                    with self.assertRaises(Exception) as caught:
                        self._step(bridge, {"values": values})
                    self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(env.actions, [])
            self.assertEqual(self._step(bridge, {"values": [0.5, -1.5, 2.5, -3.5]})["tick"], 1)
            self.assertEqual(list(env.actions[-1]), [0.5, -1.5, 2.5, -3.5])
        finally:
            bridge.close()

    def test_a_box_subclass_of_any_shape_is_bounded(self) -> None:
        class Box(Box2D):   # the gymnasium class name ...
            pass

        class BoundedBox(Box):   # ... and a user subclass of it
            pass

        for space in (Box(), BoundedBox()):
            with self.subTest(space=type(space).__name__):
                env = SpaceEnv(space)
                bridge = GymnasiumBridge(env=env)
                try:
                    self.assertEqual(list(bridge.action_limits()["action.values"]["max"]), [1.0, 2.0, 3.0, 4.0])
                    with self.assertRaises(Exception) as caught:
                        self._step(bridge, {"values": [0, 0, 3.5, 0]})
                    self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
                    self.assertEqual(env.actions, [])
                finally:
                    bridge.close()

    def test_multi_discrete_upper_bounds_come_from_nvec(self) -> None:
        env = SpaceEnv(MultiDiscrete([3, 2]))
        bridge = GymnasiumBridge(env=env)
        try:
            rule = bridge.action_limits()["action.values"]
            self.assertEqual(list(rule["min"]), [0, 0])
            self.assertEqual(list(rule["max"]), [2, 1])
            with self.assertRaises(Exception) as caught:
                self._step(bridge, {"values": [3, 0]})
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(env.actions, [])
            self._step(bridge, {"values": [2, 1]})
            self.assertEqual(list(env.actions[-1]), [2, 1])
        finally:
            bridge.close()

    def test_multi_discrete_start_offsets(self) -> None:
        env = SpaceEnv(MultiDiscrete([3, 2], start=[-1, 5]))
        bridge = GymnasiumBridge(env=env)
        try:
            rule = bridge.action_limits()["action.values"]
            self.assertEqual((list(rule["min"]), list(rule["max"])), ([-1, 5], [1, 6]))
            self._step(bridge, {"values": [-1, 6]})
            with self.assertRaises(Exception) as caught:
                self._step(bridge, {"values": [0, 4]})
            self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
        finally:
            bridge.close()

    def test_multi_binary_and_dict_members(self) -> None:
        env = SpaceEnv(support.Dict({"grid": Box2D(), "switches": MultiBinary(3)}))
        bridge = GymnasiumBridge(env=env)
        try:
            limits = bridge.action_limits()
            self.assertEqual(list(limits["action.grid"]["max"]), [1.0, 2.0, 3.0, 4.0])
            self.assertEqual((limits["action.switches"]["min"], limits["action.switches"]["max"]), (0, 1))
            for action in ({"grid": [0, 0, 0, 9], "switches": [0, 1, 0]},
                           {"grid": [0, 0, 0, 0], "switches": [0, 2, 0]}):
                with self.subTest(action=action):
                    with self.assertRaises(Exception) as caught:
                        self._step(bridge, action)
                    self.assertEqual(code_of(caught.exception), "MHS.SAFETY.ENVELOPE_VIOLATION")
            self.assertEqual(env.actions, [])
            self._step(bridge, {"grid": [0, 0, 0, 0], "switches": [1, 0, 1]})
            self.assertEqual(len(env.actions), 1)
        finally:
            bridge.close()


class SerialReplayStrictnessTests(unittest.TestCase):
    def _bridge(self, transcript: Transcript) -> SerialBridge:
        return SerialBridge({"port": "/dev/fake", "timeout_s": 0.2, "capabilities": {
            "x-cap.heat.v1": {"command": "HEAT {v}", "args": {"v": {"from": "input.v"}}, "response": False},
            "x-cap.temp.v1": {"command": "TEMP?", "parse": {"kind": "float"}}}},
            serial_factory=lambda **kw: transcript.serial())

    def test_an_unread_recorded_response_diverges(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "HEAT 80", "recv": "ERR overtemp"},
                                                         {"send": "TEMP?", "recv": "21.5"}]})
        bridge = self._bridge(transcript)
        try:
            bridge.call("x-cap.heat.v1", {"v": 80})
            with self.assertRaises(TranscriptDivergence):
                transcript.assert_complete()
            with self.assertRaises(TranscriptDivergence):
                bridge.call("x-cap.temp.v1", {})
        finally:
            bridge.close()

    def test_recv_optional_allows_the_ignored_answer(self) -> None:
        transcript = Transcript.from_json({"exchanges": [
            {"send": "HEAT 80", "recv": "OK", "recv_optional": True}, {"send": "TEMP?", "recv": "21.5"}]})
        bridge = self._bridge(transcript)
        try:
            bridge.call("x-cap.heat.v1", {"v": 80})
            self.assertEqual(bridge.call("x-cap.temp.v1", {}), {"value": 21.5})
            transcript.assert_complete()
        finally:
            bridge.close()

    def test_a_write_only_exchange_reads_nothing(self) -> None:
        transcript = Transcript.from_json({"exchanges": [{"send": "TEMP?"}]})
        bridge = self._bridge(transcript)
        try:
            with self.assertRaises(Exception) as caught:
                bridge.call("x-cap.temp.v1", {})
            self.assertEqual(code_of(caught.exception), "MHS.OUTCOME.UNKNOWN")
            transcript.assert_complete()
        finally:
            bridge.close()


class NonFiniteInputTests(unittest.TestCase):
    def test_format_command_refuses_non_finite_numbers(self) -> None:
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value):
                with self.assertRaises(MHSError) as caught:
                    format_command("VOLT {v}", {"v": value})
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(format_command("VOLT {v}", {"v": 1.5}), "VOLT 1.5")

    def test_untyped_input_rules_refuse_non_finite_numbers(self) -> None:
        mapping = FieldMapping({"v": {"from": "input.v"}}, direction="input")
        for value in (float("nan"), float("inf"), [1.0, float("nan")], {"a": float("-inf")}):
            with self.subTest(value=value):
                with self.assertRaises(MappingError):
                    mapping.map({"v": value})
        self.assertEqual(mapping.map({"v": 2.5}), {"v": 2.5})
        output = FieldMapping({"v": {"from": "output.$"}}, direction="output")
        self.assertTrue(math.isnan(output.map(float("nan"))["v"]))   # outputs are the server's concern

    def test_scpi_never_writes_nan(self) -> None:
        transcript = Transcript()   # nothing may reach the wire
        bridge = ScpiBridge({"idn": False, "commands": {"x-cap.test.volt.v1": {
            "resource": "psu", "write": "VOLT {value}", "args": {"value": {"from": "input.volts"}}}}},
            transport=transcript.line_transport())
        try:
            for value in (float("nan"), float("inf")):
                with self.subTest(value=value):
                    with self.assertRaises(Exception) as caught:
                        bridge.call("x-cap.test.volt.v1", {"volts": value})
                    self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
            transcript.assert_complete()
        finally:
            bridge.close()

    def test_python_object_native_never_sees_nan(self) -> None:
        # (through the current MHSServer a NaN input fails earlier, as MHS.INTERNAL.ERROR
        # CanonicalJSONError -- a WP-04 follow-up; the bridge refuses it on its own)
        bridge = PythonObjectBridge({"target": "tests.bridges.support:Heater", "capabilities": {
            "x-cap.test.setpoint.v1": {"bridge": "python-object", "native": "set_point",
                                       "args": {"celsius": {"from": "input.t"}},
                                       "result": {"map": {"setpoint": "output.setpoint"}},
                                       "concurrency": "exclusive", "timeout_ms": 1000}}})
        native = bridge._ensure_loaded()
        try:
            for value in (float("nan"), float("inf")):
                with self.subTest(value=value):
                    with self.assertRaises(Exception) as caught:
                        bridge.call("x-cap.test.setpoint.v1", {"t": value})
                    self.assertEqual(code_of(caught.exception), "MHS.CAPABILITY.INPUT_INVALID")
            self.assertNotIn("set_point", [name for name, _ in native.calls])
            self.assertEqual(bridge.call("x-cap.test.setpoint.v1", {"t": 40.0}), {"setpoint": 40.0})
        finally:
            bridge.close()


class ValidatorFalseTokenTests(unittest.TestCase):
    def test_validate_binding_accepts_the_false_token(self) -> None:
        binding = {"bridge": "python-object", "native": "ask", "invoke": "query", "command": "OUTP?",
                   "parse": {"kind": "bool", "true": "ON", "false": "OFF"},
                   "result": {"map": {"on": "output.$"}}, "concurrency": "shared", "timeout_ms": 500}
        self.assertEqual(validate_binding(binding), [])
        binding["parse"] = {"kind": "bool", "true": "ENABLED"}
        self.assertTrue(validate_binding(binding))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
