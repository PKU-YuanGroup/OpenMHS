"""stdio transport: priority lane, exactly-once events, wire hygiene (WP-04 4a2).

Ports of the review repros ``sdk-core/e4.py`` (one command produced two
``mhs.event`` notifications with the same seq), ``verify-integration-surfaces/
slow_test.py`` (MISSED integration-surfaces: an e-stop queued behind a 4 s
blocking command) and the stdio half of ``sdk-core/e6.py`` (NaN input, an
effectful command sent as a JSON-RPC notification).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any

import mhs
from mhs import canonical

SRC = str(Path(mhs.__file__).resolve().parents[1])
ENDPOINT = str(Path(__file__).with_name("_stdio_endpoint.py"))


class StdioChild:
    """A raw NDJSON driver for one stdio endpoint child process."""

    def __init__(self, *args: str) -> None:
        env = dict(os.environ, PYTHONPATH=SRC, PYTHONDONTWRITEBYTECODE="1")
        self.proc = subprocess.Popen(
            [sys.executable, "-B", ENDPOINT, *args],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
        self.t0 = time.monotonic()
        self.messages: list[tuple[float, dict[str, Any]]] = []
        self._lock = threading.Lock()
        self._next_id = 0
        threading.Thread(target=self._read, daemon=True).start()
        self.stderr = b""
        hello = self.call("mhs.hello", protocol_versions=["1.0"])
        self.device_id = hello["result"]["devices"][0]["device_id"]

    def _read(self) -> None:
        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            with self._lock:
                self.messages.append((time.monotonic() - self.t0, json.loads(line)))

    def send(self, method: str, *, notification: bool = False, raw: bytes | None = None,
             **params: Any) -> int | None:
        assert self.proc.stdin is not None
        if raw is not None:
            self.proc.stdin.write(raw)
            self.proc.stdin.flush()
            return None
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method, "params": params}
        request_id = None
        if not notification:
            with self._lock:
                self._next_id += 1
                request_id = self._next_id
            message["id"] = request_id
        self.proc.stdin.write((json.dumps(message) + "\n").encode())
        self.proc.stdin.flush()
        return request_id

    def wait(self, request_id: Any, timeout: float = 15.0) -> tuple[float, dict[str, Any]]:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            with self._lock:
                for stamp, message in self.messages:
                    if "method" not in message and message.get("id") == request_id:
                        return stamp, message
            time.sleep(0.002)
        raise AssertionError(f"no response to request {request_id!r} within {timeout} s")

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        return self.wait(self.send(method, **params))[1]

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return [message for _stamp, message in self.messages if message.get("method") == "mhs.event"]

    def close(self) -> None:
        if self.proc.returncode is not None:
            return
        try:
            if self.proc.stdin is not None and not self.proc.stdin.closed:
                self.proc.stdin.close()
            self.proc.wait(timeout=20)
        except subprocess.TimeoutExpired:  # pragma: no cover - cleanup only
            self.proc.kill()
            self.proc.wait(timeout=5)
        if self.proc.stderr is not None:
            self.stderr = self.proc.stderr.read()
            self.proc.stderr.close()


def _code(response: dict[str, Any]) -> str | None:
    if "error" in response:
        return (response["error"].get("data") or {}).get("mhs_code")
    error = (response.get("result") or {}).get("error") or {}
    return error.get("mhs_code")


class StdioPriorityLaneTests(unittest.TestCase):
    def test_estop_is_answered_while_a_blocking_command_runs(self) -> None:
        """slow_test.py: e-stop 0.2 s into a 4 s non-cancellable step."""
        child = StdioChild("--slow-step-s", "4")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        step = child.send("mhs.command", session_id=session, capability_id="cap.world.step.v1",
                          input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=10000)
        time.sleep(0.2)
        sent = time.monotonic() - child.t0
        estop = child.send("mhs.safety.estop", session_id=session, reason="panic", deadline_ms=1000)
        answered, response = child.wait(estop, timeout=5.0)
        self.assertIn("result", response, response)
        self.assertTrue(response["result"]["output"]["latched"], response)
        self.assertLess(answered - sent, 0.1,
                        f"e-stop answered after {answered - sent:.3f} s behind a blocking command")
        _stamp, motion = child.wait(child.send(
            "mhs.command", session_id=session, capability_id="cap.world.step.v1",
            input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=10000))
        self.assertEqual(motion["result"]["status"], "rejected", motion)
        self.assertEqual(_code(motion), "MHS.SAFETY.ESTOP_ENGAGED")
        child.wait(step, timeout=10.0)

    def test_cancel_is_not_queued_behind_the_running_command(self) -> None:
        child = StdioChild("--test-profile")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        delay = child.send("mhs.command", session_id=session, capability_id="x-cap.mhs-test.delay.v1",
                           input={"ms": 2000}, deadline_ms=10000)
        operation_id = None
        end = time.monotonic() + 1.5
        while operation_id is None and time.monotonic() < end:
            listed = child.call("mhs.operations.list", session_id=session)["result"]["operations"]
            operation_id = listed[0]["operation_id"] if listed else None
        self.assertIsNotNone(operation_id, "the delay operation was not registered")
        sent = time.monotonic() - child.t0
        cancel = child.send("mhs.operations.cancel", session_id=session, operation_id=operation_id,
                            deadline_ms=2000)
        answered, response = child.wait(cancel, timeout=5.0)
        self.assertLess(answered - sent, 1.0, response)
        self.assertEqual(response["result"]["status"], "cancelled", response)
        _stamp, delayed = child.wait(delay, timeout=5.0)
        self.assertEqual(delayed["result"]["status"], "cancelled", delayed)


class StdioEventTests(unittest.TestCase):
    def test_e4_one_command_emits_exactly_one_event(self) -> None:
        child = StdioChild("--test-profile")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        subscription = child.call("mhs.subscribe", session_id=session, streams=["state"],
                                  deadline_ms=1000)["result"]["subscription_id"]
        receipt = child.call("mhs.command", session_id=session, capability_id="cap.world.step.v1",
                             input={"ticks": 1}, deadline_ms=2000)
        self.assertEqual(receipt["result"]["status"], "completed", receipt)
        time.sleep(0.4)
        events = [event for event in child.events()
                  if event["params"]["subscription_id"] == subscription]
        self.assertEqual([event["params"]["seq"] for event in events], [1],
                         f"expected exactly one event: {events}")


class StdioWireHygieneTests(unittest.TestCase):
    def test_nan_input_is_a_parse_error_and_never_executes(self) -> None:
        child = StdioChild("--test-profile")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        before = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant):
                child.send("", raw=(
                    '{"jsonrpc":"2.0","id":"nan-%s","method":"mhs.command","params":{"session_id":"%s",'
                    '"capability_id":"x-cap.mhs-reference.start.v1","input":{"speed_mm_s":%s},'
                    '"deadline_ms":2000}}\n' % (constant, session, constant)).encode())
                deadline = time.monotonic() + 5
                response = None
                while response is None and time.monotonic() < deadline:
                    with child._lock:  # noqa: SLF001 - test driver
                        response = next((m for _s, m in child.messages
                                         if "error" in m and m.get("id") is None), None)
                    time.sleep(0.01)
                self.assertIsNotNone(response, "no parse error was returned")
                self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.PROTOCOL.PARSE_ERROR")
                with child._lock:  # noqa: SLF001
                    child.messages = [(s, m) for s, m in child.messages if m is not response]
        after = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        self.assertEqual(before, after, "a NaN command reached the device")

    def test_effectful_notification_is_dropped_and_logged(self) -> None:
        child = StdioChild("--test-profile")
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        before = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        child.send("mhs.command", notification=True, session_id=session,
                   capability_id="cap.world.step.v1", input={"ticks": 5}, deadline_ms=2000)
        time.sleep(0.2)
        after = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        child.close()
        self.assertEqual(before, after, "a command sent as a notification was executed")
        self.assertIn(b"notification", child.stderr)
        self.assertIn(b"mhs.command", child.stderr)

    def test_wire_estop_with_a_non_finite_deadline_latches(self) -> None:
        """Verifier probe estop_inf.py on the wire: ``1e999`` (valid JSON that
        overflows to inf) and a ``NaN`` literal never refuse an e-stop."""
        for literal in ("1e999", "NaN"):
            with self.subTest(literal):
                child = StdioChild("--test-profile")
                self.addCleanup(child.close)
                session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
                child.send("", raw=(
                    '{"jsonrpc":"2.0","id":"estop","method":"mhs.safety.estop","params":'
                    '{"device_id":"%s","reason":"x","deadline_ms":%s}}\n'
                    % (child.device_id, literal)).encode())
                _stamp, response = child.wait("estop", timeout=5.0)
                self.assertIn("result", response, response)
                self.assertTrue(response["result"]["output"]["latched"], response)
                _stamp, motion = child.wait(child.send(
                    "mhs.command", session_id=session, capability_id="cap.world.step.v1",
                    input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=2000))
                self.assertEqual(_code(motion), "MHS.SAFETY.ESTOP_ENGAGED", motion)

    def test_wire_command_with_an_overflowing_number_is_refused(self) -> None:
        child = StdioChild("--test-profile")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        before = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        child.send("", raw=(
            '{"jsonrpc":"2.0","id":"big","method":"mhs.command","params":{"session_id":"%s",'
            '"capability_id":"cap.world.step.v1","input":{"ticks":1e999},"deadline_ms":2000}}\n'
            % session).encode())
        _stamp, response = child.wait("big", timeout=5.0)
        self.assertEqual(_code(response), "MHS.PROTOCOL.PARSE_ERROR", response)
        after = child.call("mhs.resource.read", session_id=session, deadline_ms=2000)["result"]["revision"]
        self.assertEqual(before, after)

    def test_a_deeply_nested_line_is_a_parse_error_and_the_endpoint_survives(self) -> None:
        """WP-04 4a2 verifier probe ``r2/repros/deep_probe.py``: one line of
        200,000 ``[`` (within the 1 MiB limit) raised RecursionError out of the
        reader loop and killed the endpoint, and with it the e-stop channel."""
        child = StdioChild("--test-profile")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        child.send("", raw=b"[" * 200_000 + b"\n")
        deadline = time.monotonic() + 10
        response = None
        while response is None and time.monotonic() < deadline:
            with child._lock:  # noqa: SLF001 - test driver
                response = next((m for _s, m in child.messages if "error" in m and m.get("id") is None), None)
            time.sleep(0.01)
        self.assertIsNotNone(response, f"no parse error; endpoint exit code {child.proc.poll()}")
        self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.PROTOCOL.PARSE_ERROR")
        self.assertIsNone(child.proc.poll(), "the stdio endpoint died")
        _stamp, estop = child.wait(child.send("mhs.safety.estop", device_id=child.device_id, reason="x",
                                              deadline_ms=2000), timeout=5.0)
        self.assertTrue(estop["result"]["output"]["latched"], estop)
        _stamp, motion = child.wait(child.send(
            "mhs.command", session_id=session, capability_id="cap.world.step.v1",
            input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=2000))
        self.assertEqual(_code(motion), "MHS.SAFETY.ESTOP_ENGAGED", motion)


if __name__ == "__main__":
    unittest.main()
