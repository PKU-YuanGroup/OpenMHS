"""SURF-07 / MISSED integration-surfaces: the MCP stdio loop never queues an e-stop behind a call.

``test_slow_endpoint_estop_is_not_queued_behind_a_blocking_call`` is the port
of ``verify-integration-surfaces/slow_test.py`` through ``python3 -m mhs.mcp``:
a 3 s non-cancellable step is in flight on the same MCP connection when the
model calls ``mhs__estop``.  The in-process tests drive :func:`serve_stdio`
with a blocking fake client, so they need no subprocess.
"""

from __future__ import annotations

import io
import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any

from mhs.mcp import MCPProjection, serve_stdio

from tests.endpoints import support as endpoint_support
from tests.surfaces import _support as s

STEP = "mhs__lab_conveyor_workcell__world_step"


class _Responses:
    """Collect JSON-RPC responses by id with their arrival time."""

    def __init__(self, stream: Any) -> None:
        self.by_id: dict[Any, tuple[float, dict]] = {}
        self.order: list[Any] = []
        self._ready = threading.Condition()
        self._thread = threading.Thread(target=self._read, args=(stream,), daemon=True)
        self._thread.start()

    def _read(self, stream: Any) -> None:
        for line in iter(stream.readline, b""):
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if "id" in message:
                with self._ready:
                    self.by_id[message["id"]] = (time.monotonic(), message)
                    self.order.append(message["id"])
                    self._ready.notify_all()

    def wait(self, mid: Any, timeout: float = 20.0) -> tuple[float, dict]:
        with self._ready:
            if not self._ready.wait_for(lambda: mid in self.by_id, timeout):
                raise AssertionError(f"no response to {mid!r} within {timeout} s")
            return self.by_id[mid]


def _send(stream: Any, mid: Any, method: str, params: dict | None = None) -> float:
    message: dict = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if mid is not None:
        message["id"] = mid
    stream.write((json.dumps(message) + "\n").encode())
    stream.flush()
    return time.monotonic()


class _BlockingClient(endpoint_support.FakeClient):
    """invoke() blocks until released; estop() answers at once."""

    def __init__(self, manifests):
        super().__init__(manifests)
        self.entered = threading.Event()
        self.release = threading.Event()
        self.stops: list[str] = []

    def invoke(self, capability_id, payload=None, **kwargs):
        self.entered.set()
        self.release.wait(10)
        return super().invoke(capability_id, payload, **kwargs)

    def estop(self, reason, device_id=None, *, session_id=None):
        self.stops.append(str(device_id))
        return {"status": "completed", "capability_id": "cap.internal.safety_estop.v1",
                "output": {"latched": True}, "device_id": device_id}


class InProcessPriorityTests(unittest.TestCase):
    def test_estop_and_ping_are_answered_while_a_call_is_in_flight(self) -> None:
        client = _BlockingClient([endpoint_support.simple_manifest()])
        projection = MCPProjection(client)
        stdin_r, stdin_w = os.pipe()
        stdout_r, stdout_w = os.pipe()
        writer = os.fdopen(stdin_w, "wb")
        reader = os.fdopen(stdout_r, "rb")
        server_in = os.fdopen(stdin_r, "rb")
        server_out = os.fdopen(stdout_w, "wb")
        thread = threading.Thread(target=lambda: (serve_stdio(projection, stdin=server_in, stdout=server_out),
                                                  server_out.close()), daemon=True)
        stderr = io.StringIO()
        original, sys.stderr = sys.stderr, stderr
        try:
            thread.start()
            responses = _Responses(reader)
            _send(writer, 1, "initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "t"}})
            responses.wait(1)
            _send(writer, 2, "tools/call", {"name": STEP, "arguments": {"ticks": 1}})
            self.assertTrue(client.entered.wait(5))
            sent = _send(writer, 3, "tools/call", {"name": "mhs__estop",
                                                   "arguments": {"device_id": endpoint_support.simple_manifest()
                                                                 ["device_id"]}})
            _send(writer, 4, "ping")
            arrived, estop = responses.wait(3, timeout=3)
            responses.wait(4, timeout=3)
            self.assertLess(arrived - sent, 1.0)
            self.assertFalse(estop["result"]["isError"], estop)
            self.assertNotIn(2, responses.by_id)  # the call is still in flight
            client.release.set()
            _, called = responses.wait(2)
            self.assertFalse(called["result"]["isError"])
            self.assertLess(responses.order.index(3), responses.order.index(2))
        finally:
            sys.stderr = original
            client.release.set()
            writer.close()  # end of input: the loop finishes and closes its output
            thread.join(10)
            if not thread.is_alive():  # never close a stream another thread still reads
                for stream in (reader, server_in):
                    stream.close()
        self.assertFalse(thread.is_alive())

    def test_a_call_cancelled_while_queued_is_never_dispatched(self) -> None:
        # MCP hosts may issue parallel tool calls: call 3 waits behind call 2 when the user aborts it
        client = _BlockingClient([endpoint_support.simple_manifest()])
        invoked: list[Any] = []
        original_invoke = client.invoke

        def counting_invoke(capability_id, payload=None, **kwargs):
            invoked.append(kwargs.get("command_id"))
            return original_invoke(capability_id, payload, **kwargs)

        client.invoke = counting_invoke  # type: ignore[method-assign]
        projection = MCPProjection(client)
        stdin_r, stdin_w = os.pipe()
        stdout_r, stdout_w = os.pipe()
        writer = os.fdopen(stdin_w, "wb")
        reader = os.fdopen(stdout_r, "rb")
        server_in = os.fdopen(stdin_r, "rb")
        server_out = os.fdopen(stdout_w, "wb")
        thread = threading.Thread(target=lambda: (serve_stdio(projection, stdin=server_in, stdout=server_out),
                                                  server_out.close()), daemon=True)
        stderr = io.StringIO()
        original, sys.stderr = sys.stderr, stderr
        try:
            thread.start()
            responses = _Responses(reader)
            _send(writer, 1, "initialize", {"protocolVersion": "2025-06-18", "clientInfo": {"name": "t"}})
            responses.wait(1)
            _send(writer, 2, "tools/call", {"name": STEP, "arguments": {"ticks": 1}})
            self.assertTrue(client.entered.wait(5))
            _send(writer, 3, "tools/call", {"name": STEP, "arguments": {"ticks": 1}})
            _send(writer, None, "notifications/cancelled", {"requestId": 3, "reason": "user aborted"})
            time.sleep(0.3)  # the cancel thread records request 3 before the worker reaches it
            client.release.set()
            _, called = responses.wait(2)
            self.assertFalse(called["result"]["isError"])
            _send(writer, 4, "ping")
            responses.wait(4)
            self.assertEqual(len(invoked), 1, "the cancelled queued call reached the endpoint")
            self.assertNotIn(3, responses.by_id)  # MCP: no response to a cancelled request
        finally:
            sys.stderr = original
            client.release.set()
            writer.close()
            thread.join(10)
            if not thread.is_alive():
                for stream in (reader, server_in):
                    stream.close()
        self.assertFalse(thread.is_alive())

    def test_queued_requests_are_finished_at_end_of_input(self) -> None:
        client = endpoint_support.FakeClient([endpoint_support.simple_manifest()])
        projection = MCPProjection(client)
        lines = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"clientInfo": {"name": "t"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": STEP, "arguments": {"ticks": 1}}},
        ]
        stdin = io.BytesIO(b"".join((json.dumps(line) + "\n").encode() for line in lines) + b"x" * 10 + b"\n")
        stdout = io.BytesIO()
        stderr = io.StringIO()
        original, sys.stderr = sys.stderr, stderr
        try:
            self.assertEqual(serve_stdio(projection, stdin=stdin, stdout=stdout), 0)
        finally:
            sys.stderr = original
        replies = [json.loads(line) for line in stdout.getvalue().splitlines()]
        ids = [reply.get("id") for reply in replies]
        self.assertEqual(sorted(i for i in ids if i is not None), [1, 2, 3])
        self.assertIn(-32700, [reply.get("error", {}).get("code") for reply in replies])
        self.assertTrue(client.closed)


class SlowEndpointTests(unittest.TestCase):
    def test_slow_endpoint_estop_is_not_queued_behind_a_blocking_call(self) -> None:
        endpoint = Path(__file__).with_name("_slow_endpoint.py")
        env = s.child_env()
        env["MHS_SLOW_STEP_S"] = "3"
        process = subprocess.Popen(
            [sys.executable, "-m", "mhs.mcp", "--command", shlex.join([sys.executable, str(endpoint)])],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
        )
        self.addCleanup(self._stop, process)
        responses = _Responses(process.stdout)
        _send(process.stdin, 1, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                               "clientInfo": {"name": "slow-test", "version": "0"}})
        responses.wait(1)
        _send(process.stdin, None, "notifications/initialized")
        _send(process.stdin, 2, "tools/list")
        names = [tool["name"] for tool in responses.wait(2)[1]["result"]["tools"]]
        self.assertIn(STEP, names)
        started = _send(process.stdin, 3, "tools/call", {"name": STEP, "arguments": {"ticks": 1}})
        time.sleep(0.3)
        sent = _send(process.stdin, 4, "tools/call", {"name": "mhs__estop", "arguments": {
            "device_id": s.CONVEYOR, "reason": "panic"}})
        arrived, estop = responses.wait(4, timeout=10)
        self.assertLess(arrived - sent, 1.5, "the e-stop waited behind the blocking call")
        self.assertFalse(estop["result"]["isError"], estop)
        self.assertTrue(estop["result"]["structuredContent"]["estop"]["output"]["latched"])
        finished, step = responses.wait(3, timeout=15)
        self.assertGreater(finished, arrived)
        self.assertGreaterEqual(finished - started, 2.5)
        self.assertIn("result", step)

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        try:
            process.stdin.close()
        except OSError:
            pass
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        if process.stdout is not None:
            process.stdout.close()


if __name__ == "__main__":
    unittest.main()
