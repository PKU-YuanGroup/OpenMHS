"""Fail-safe e-stop requests (WP-09 follow-ups F2 and F6).

An emergency stop is recognised by what it asks for, not by how well its envelope is written, and a stop that names no device is
a stop of every device of the endpoint:

* a request whose ``method`` is ``mhs.safety.estop`` latches although its ``jsonrpc`` is not ``"2.0"``, its ``id`` is not a
  string or an integer, or its ``params`` are not an object (the answer is still an error, which says that the stop was served);
* an e-stop without ``device_id`` on an endpoint that serves several devices latches all of them, concurrently, so a stop path
  that hangs on one device never delays the latch of another;
* an e-stop that is refused at the door stays refused: over HTTP with ``auth_tokens`` a request without the bearer token is a 401
  before anything is decoded, malformed or not.
"""

from __future__ import annotations

import json
import logging
import threading
import time
import unittest
from typing import Any

from mhs import canonical
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from . import test_transport_http as http_tests
from .test_transport_stdio import StdioChild
from .test_transport_stdio import _code as stdio_code
from ._support import (
    FIDELITY,
    MOVE,
    STOP,
    NativeStopBridge,
    Rpc,
    error_code,
    stub_capabilities,
    stub_server,
    ulid,
    wait_until,
)

ESTOP_CLASS = "cap.motion.estop.v1"


def as_dict(response: Any) -> Any:
    if response is None:
        return None
    if isinstance(response, list):
        return [as_dict(item) for item in response]
    return response.to_dict() if hasattr(response, "to_dict") else dict(response)


def estop_message(**over: Any) -> dict[str, Any]:
    message: dict[str, Any] = {"jsonrpc": "2.0", "id": 7, "method": "mhs.safety.estop",
                               "params": {"reason": "operator pressed stop", "deadline_ms": 1000}}
    message.update(over)
    return {key: value for key, value in message.items() if value is not ...}


def two_devices(latency_ms: int = 200, *, extra_caps: tuple[Capability, ...] = (), **server_kwargs: Any):
    """An endpoint with two simulated devices (a and b), each with a native e-stop."""
    bridges = [NativeStopBridge("mhs://localhost/safety/a"), NativeStopBridge("mhs://localhost/safety/b")]
    devices = []
    for bridge in bridges:
        devices.append(Device(
            bridge.device_id, mode="simulated",
            resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
            capabilities=stub_capabilities(extra=extra_caps),
            safety=SafetyEnvelope(risk_class="R1", estop={"kind": "software", "latching": True, "latency_ms": latency_ms},
                                  safe_state={"description": "stopped", "achieved_by": [STOP]}),
            fidelity=dict(FIDELITY), bridge=bridge,
        ))
    server = MHSServer("mhs://localhost/safety", devices, log_ready=False, **server_kwargs)
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    return server, rpc, devices, bridges


def quiet_server_log(test: unittest.TestCase) -> None:
    """The warnings that say a defective e-stop was served are expected in these tests."""
    logger = logging.getLogger("mhs.server")
    level = logger.level
    logger.setLevel(logging.ERROR)
    test.addCleanup(logger.setLevel, level)


class DefectiveEnvelopeTests(unittest.TestCase):
    """A request that is recognisably an e-stop latches whatever is wrong with its envelope."""

    DEFECTS = {
        "jsonrpc 1.0": {"jsonrpc": "1.0"},
        "jsonrpc missing": {"jsonrpc": ...},
        "jsonrpc a number": {"jsonrpc": 2.0},
        "id a float": {"id": 1.5},
        "id a boolean": {"id": True},
        "id a list": {"id": ["a"]},
        "id an object": {"id": {"a": 1}},
        "id null": {"id": None},
        "params a list": {"params": ["stop"]},
        "params a string": {"params": "now"},
        "params a number": {"params": 5},
    }

    def setUp(self) -> None:
        quiet_server_log(self)

    def test_each_defect_of_the_envelope_still_latches(self) -> None:
        for name, defect in self.DEFECTS.items():
            with self.subTest(name):
                server, rpc, device, bridge = stub_server(NativeStopBridge())
                response = as_dict(server.handle(estop_message(**defect)))
                self.assertTrue(server._latched[device.device_id], f"{name}: the device was not latched")
                self.assertEqual(bridge.count("estop"), 1, f"{name}: the native stop did not run")
                self.assertIn("error", response, response)
                self.assertIn(error_code(response), ("MHS.PROTOCOL.INVALID_REQUEST", "MHS.PROTOCOL.INVALID_PARAMS"), response)

    def test_the_error_says_that_the_stop_was_served_and_carries_its_receipt(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        response = as_dict(server.handle(estop_message(jsonrpc="1.0")))
        self.assertEqual(response["id"], 7, "a valid id is echoed")
        details = response["error"]["data"]["details"]
        self.assertIs(details["estop_served"], True)
        self.assertIn("jsonrpc", details["defect"])
        self.assertEqual(details["receipt"]["status"], "completed")
        self.assertEqual(details["receipt"]["device_id"], device.device_id)
        self.assertTrue(details["receipt"]["output"]["latched"])

    def test_an_invalid_id_is_answered_with_a_null_id(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        response = as_dict(server.handle(estop_message(id=1.5)))
        self.assertIsNone(response["id"])
        self.assertTrue(server._latched[device.device_id])

    def test_a_notification_with_a_defective_envelope_latches_and_gets_no_answer(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        self.assertIsNone(server.handle(estop_message(jsonrpc="1.0", id=...)))
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(bridge.count("estop"), 1)

    def test_the_stop_that_failed_is_reported_in_the_error(self) -> None:
        bridge = NativeStopBridge()

        def broken(reason="", ctx=None):  # noqa: ANN001
            raise RuntimeError("the drive does not answer")

        bridge.estop = broken
        server, rpc, device, _ = stub_server(bridge, safety=SafetyEnvelope(
            risk_class="R1", estop={"kind": "software", "latching": True, "latency_ms": 50}, safe_state={"description": "x"}))
        response = as_dict(server.handle(estop_message(jsonrpc="1.0")))
        self.assertTrue(server._latched[device.device_id], "the latch stays engaged whatever the stop path does")
        receipt = response["error"]["data"]["details"]["receipt"]
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_non_finite_values_in_a_defective_estop_do_not_stop_it(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        message = estop_message(jsonrpc="1.0")
        message["params"]["deadline_ms"] = float("inf")
        with self.assertLogs("mhs.server", level="WARNING"):
            server.handle(message)
        self.assertTrue(server._latched[device.device_id])

    def test_a_defective_estop_inside_a_batch_latches_and_is_answered_in_place(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        batch = [{"jsonrpc": "2.0", "id": 1, "method": "mhs.devices.list", "params": {}}, estop_message(jsonrpc="1.0", id=2)]
        responses = as_dict(server.handle(batch))
        self.assertEqual([item["id"] for item in responses], [1, 2])
        self.assertIn("result", responses[0])
        self.assertIn("error", responses[1])
        self.assertTrue(server._latched[device.device_id])

    def test_only_the_estop_methods_are_recognised_by_a_defective_envelope(self) -> None:
        """The same defects on any other request are refused, and nothing latches."""
        for method in ("mhs.safety.estop ", "MHS.SAFETY.ESTOP", "mhs.safety.estop2", "mhs.safety.status", "mhs.command", 5, None):
            with self.subTest(method=method):
                server, rpc, device, bridge = stub_server(NativeStopBridge())
                response = as_dict(server.handle(estop_message(jsonrpc="1.0", method=method)))
                self.assertIn("error", response, response)
                self.assertFalse(server._latched[device.device_id])
                self.assertEqual(bridge.count("estop"), 0)

    def test_a_well_formed_request_is_answered_as_before(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        response = as_dict(server.handle(estop_message()))
        self.assertEqual(response["result"]["status"], "completed")
        self.assertNotIn("estop", response["result"].get("x-vendor", {}), "a single-device stop carries no stop-all marker")

    def test_the_command_form_with_a_defective_envelope_latches_too(self) -> None:
        estop_cap = Capability(ESTOP_CLASS, "axis", input_schema={"type": "object", "properties": {"reason": {"type": "string"}}})
        server, rpc, device, bridge = stub_server(NativeStopBridge(), capabilities=stub_capabilities(extra=[estop_cap]))
        response = as_dict(server.handle({"jsonrpc": "1.0", "id": 3, "method": "mhs.command",
                                          "params": {"capability_id": ESTOP_CLASS, "input": {"reason": "x"}}}))
        self.assertTrue(server._latched[device.device_id])
        self.assertIn("error", response)

    def test_a_defective_estop_that_names_an_unusable_device_stops_every_device(self) -> None:
        for selector in (5, ["a"], "mhs://localhost/safety/nowhere", ""):
            with self.subTest(device_id=repr(selector)):
                server, rpc, devices, bridges = two_devices()
                message = estop_message(jsonrpc="1.0")
                message["params"]["device_id"] = selector
                server.handle(message)
                self.assertTrue(all(server._latched[d.device_id] for d in devices), selector)

    def test_the_command_form_with_an_unusable_device_stops_every_device_that_binds_the_class(self) -> None:
        estop_cap = Capability(ESTOP_CLASS, "axis", input_schema={"type": "object", "properties": {"reason": {"type": "string"}}})
        server, rpc, devices, bridges = two_devices(extra_caps=(estop_cap,))
        server.handle({"jsonrpc": "1.0", "id": 3, "method": "mhs.command",
                       "params": {"capability_id": ESTOP_CLASS, "device_id": 12, "input": {"reason": "x"}}})
        self.assertTrue(all(server._latched[d.device_id] for d in devices))

    def test_a_defective_estop_that_names_a_device_stops_that_device(self) -> None:
        server, rpc, devices, bridges = two_devices()
        message = estop_message(jsonrpc="1.0")
        message["params"]["device_id"] = devices[1].device_id
        server.handle(message)
        self.assertTrue(server._latched[devices[1].device_id])
        self.assertFalse(server._latched[devices[0].device_id])


class StopAllTests(unittest.TestCase):
    """An e-stop that names no device stops every device of the endpoint."""

    def setUp(self) -> None:
        self.release = threading.Event()
        self.addCleanup(self.release.set)

    def test_without_a_device_id_every_device_is_latched_and_stopped(self) -> None:
        server, rpc, devices, bridges = two_devices()
        command_id = ulid()
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000, command_id=command_id)
        self.assertEqual(receipt["status"], "completed", receipt)
        for device, bridge in zip(devices, bridges):
            self.assertTrue(server._latched[device.device_id], device.device_id)
            self.assertEqual(bridge.count("estop"), 1, device.device_id)
            self.assertTrue(rpc("mhs.safety.status", device_id=device.device_id, deadline_ms=1000)["estop_engaged"])
        marker = receipt["x-vendor"]["estop"]
        self.assertEqual(marker["scope"], "all_devices")
        self.assertEqual([item["device_id"] for item in marker["devices"]], [d.device_id for d in devices])
        self.assertTrue(all(item["status"] == "completed" and item["receipt_id"] for item in marker["devices"]), marker)

    def test_a_named_device_is_stopped_alone(self) -> None:
        server, rpc, devices, bridges = two_devices()
        receipt = rpc("mhs.safety.estop", device_id=devices[0].device_id, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["device_id"], devices[0].device_id)
        self.assertNotIn("estop", receipt.get("x-vendor", {}))
        self.assertTrue(server._latched[devices[0].device_id])
        self.assertFalse(server._latched[devices[1].device_id])

    def test_a_session_on_one_device_keeps_the_stop_to_that_device(self) -> None:
        server, rpc, devices, bridges = two_devices()
        session = rpc("mhs.session.open", device_ids=[devices[1].device_id], mode="simulated")["session_id"]
        receipt = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["device_id"], devices[1].device_id)
        self.assertTrue(server._latched[devices[1].device_id])
        self.assertFalse(server._latched[devices[0].device_id])

    def test_a_session_on_several_devices_does_not_narrow_the_stop(self) -> None:
        server, rpc, devices, bridges = two_devices()
        session = rpc("mhs.session.open", device_ids=[d.device_id for d in devices], mode="simulated")["session_id"]
        receipt = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["x-vendor"]["estop"]["scope"], "all_devices")
        self.assertTrue(all(server._latched[d.device_id] for d in devices))

    def test_an_unknown_device_is_still_an_error_and_stops_nothing(self) -> None:
        server, rpc, devices, bridges = two_devices()
        response = rpc.raw("mhs.safety.estop", device_id="mhs://localhost/safety/nowhere", reason="x", deadline_ms=1000)
        self.assertIn("error", response)
        self.assertFalse(any(server._latched[d.device_id] for d in devices))

    def test_a_failing_stop_on_one_device_is_reported_and_the_others_still_stop(self) -> None:
        server, rpc, devices, bridges = two_devices(latency_ms=100)

        def broken(reason="", ctx=None):  # noqa: ANN001
            raise RuntimeError("the drive does not answer")

        bridges[0].estop = broken
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=2000)
        self.assertEqual(receipt["status"], "failed", "completed only when every stop path succeeded (SAFE-002)")
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        statuses = {item["device_id"]: item["status"] for item in receipt["x-vendor"]["estop"]["devices"]}
        self.assertEqual(statuses, {devices[0].device_id: "failed", devices[1].device_id: "completed"})
        self.assertTrue(all(server._latched[d.device_id] for d in devices))
        self.assertEqual(bridges[1].count("estop"), 1)

    def test_a_device_whose_engagement_raises_is_reported_failed_and_the_others_still_stop(self) -> None:
        server, rpc, devices, bridges = two_devices()
        original = server._engage_estop

        def flaky(*, device, **kwargs):  # noqa: ANN001
            if device.device_id == devices[0].device_id:
                raise RuntimeError("engagement blew up")
            return original(device=device, **kwargs)

        server._engage_estop = flaky  # type: ignore[method-assign]
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(receipt["error"]["details"]["devices"], [devices[0].device_id])
        statuses = {item["device_id"]: item["status"] for item in receipt["x-vendor"]["estop"]["devices"]}
        self.assertEqual(statuses, {devices[0].device_id: "failed", devices[1].device_id: "completed"})
        self.assertTrue(server._latched[devices[1].device_id])

    def test_a_hung_stop_path_does_not_delay_the_latch_of_another_device(self) -> None:
        server, rpc, devices, bridges = two_devices(latency_ms=400)

        def hung(reason="", ctx=None):  # noqa: ANN001
            self.release.wait(3.0)
            return {}

        bridges[0].estop = hung
        holder: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: holder.update(result=rpc.raw("mhs.safety.estop", reason="x", deadline_ms=3000)))
        thread.start()
        try:
            started = time.monotonic()
            self.assertTrue(wait_until(lambda: server._latched[devices[1].device_id], timeout=2.0))
            self.assertLess(time.monotonic() - started, 0.3, "the second device waited for the first one's stop path")
            self.assertTrue(thread.is_alive() and not self.release.is_set(), "the first stop path was still pending")
            self.assertTrue(server._latched[devices[0].device_id], "a latch is set before any bridge I/O")
            thread.join(2.5)  # the answer comes with the e-stop budget of the hung device, not when its stop path returns
            self.assertFalse(thread.is_alive(), "the stop-all did not answer within the budget of the hung stop path")
        finally:
            self.release.set()
            thread.join(5.0)
        self.assertEqual(holder["result"]["result"]["status"], "failed", "completed only when every stop path succeeded")
        self.assertEqual(error_code(holder["result"]["result"]), "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_retry_with_the_same_command_id_replays_the_retained_receipts(self) -> None:
        server, rpc, devices, bridges = two_devices()
        command_id = ulid()
        first = rpc("mhs.safety.estop", reason="x", deadline_ms=1000, command_id=command_id)
        again = rpc("mhs.safety.estop", reason="x", deadline_ms=1000, command_id=command_id)
        self.assertTrue(again["replayed"])
        self.assertEqual([item["receipt_id"] for item in again["x-vendor"]["estop"]["devices"]],
                         [item["receipt_id"] for item in first["x-vendor"]["estop"]["devices"]])
        self.assertEqual([bridge.count("estop") for bridge in bridges], [1, 1], "a replay does not stop twice")

    def test_a_single_device_endpoint_is_unchanged(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["device_id"], device.device_id)
        self.assertNotIn("estop", receipt.get("x-vendor", {}))

    def test_the_catalogue_estop_command_without_a_device_stops_every_device_that_binds_it(self) -> None:
        estop_cap = Capability(ESTOP_CLASS, "axis", input_schema={"type": "object", "properties": {"reason": {"type": "string"}}})
        server, rpc, devices, bridges = two_devices(extra_caps=(estop_cap,))
        receipt = rpc("mhs.command", capability_id=ESTOP_CLASS, input={"reason": "x"}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["x-vendor"]["estop"]["scope"], "all_devices")
        self.assertTrue(all(server._latched[d.device_id] for d in devices))

    def test_a_stop_all_is_attributed_in_the_evidence_of_every_device(self) -> None:
        server, rpc, devices, bridges = two_devices()
        rpc("mhs.safety.estop", reason="line 3 smoke", deadline_ms=1000)
        bundle = json.dumps(server.export_evidence(), default=str)
        for device in devices:
            self.assertIn(device.device_id, bundle)
        self.assertGreaterEqual(bundle.count("cap.internal.safety_estop.v1"), 2)


class StdioDefectiveEstopTests(unittest.TestCase):
    def test_a_defective_estop_is_served_on_the_priority_lane_behind_a_blocking_command(self) -> None:
        child = StdioChild("--slow-step-s", "4")
        self.addCleanup(child.close)
        session = child.call("mhs.session.open", mode="simulated")["result"]["session_id"]
        step = child.send("mhs.command", session_id=session, capability_id="cap.world.step.v1",
                          input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=10000)
        time.sleep(0.2)
        sent = time.monotonic() - child.t0
        child.send("", raw=('{"jsonrpc":"1.0","id":"panic","method":"mhs.safety.estop","params":'
                            '{"device_id":"%s","reason":"x"}}\n' % child.device_id).encode())
        answered, response = child.wait("panic", timeout=5.0)
        self.assertIn("error", response, response)
        self.assertTrue(response["error"]["data"]["details"]["estop_served"], response)
        self.assertLess(answered - sent, 0.5, f"answered after {answered - sent:.3f} s behind a blocking command")
        _stamp, motion = child.wait(child.send(
            "mhs.command", session_id=session, capability_id="cap.world.step.v1",
            input={"ticks": 1}, command_id=canonical.ulid(), deadline_ms=10000))
        self.assertEqual(stdio_code(motion), "MHS.SAFETY.ESTOP_ENGAGED", motion)
        child.wait(step, timeout=10.0)


class RefusedAtTheDoorTests(http_tests.HttpFixture):
    """With auth_tokens a request without the bearer token never reaches the decoder, so a malformed e-stop is refused too."""

    def make_server(self):
        spec = http_tests.build_endpoint("conveyor", endpoint_id="mhs://localhost/http-test", test_profile=True)
        devices = http_tests.build_server(spec, log_ready=False)
        server = MHSServer(devices.endpoint_id, list(devices.devices.values()), log_ready=False,
                           auth_tokens={"s3cret-token": {"id": "operator:ada", "kind": "operator"}})
        return spec, server

    def setUp(self) -> None:
        quiet_server_log(self)
        self._auth = {"Authorization": "Bearer s3cret-token"}
        super().setUp()

    def post(self, message, *, headers=None, **kwargs):
        merged = dict(self._auth)
        merged.update(headers or {})
        return super().post(message, headers=merged, **kwargs)

    def test_without_the_token_even_a_malformed_estop_is_refused_and_latches_nothing(self) -> None:
        device_id = next(iter(self.server.devices))
        for label, message in (("well formed", estop_message(jsonrpc="2.0")),
                               ("malformed", estop_message(jsonrpc="1.0")),
                               ("unknown token", estop_message(jsonrpc="1.0"))):
            with self.subTest(label):
                headers = {"Content-Type": "application/json"}
                if label == "unknown token":
                    headers["Authorization"] = "Bearer nope"
                status, _response_headers, data = self.request("POST", "/mhs/v1/rpc", body=json.dumps(message).encode(), headers=headers)
                self.assertEqual(status, 401)
                self.assertFalse(self.server._latched[device_id])

    def test_with_the_token_a_malformed_estop_latches(self) -> None:
        device_id = next(iter(self.server.devices))
        status, _headers, payload = self.post(estop_message(jsonrpc="1.0", params={"device_id": device_id, "reason": "x"}))
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["error"]["data"]["details"]["estop_served"])
        self.assertTrue(self.server._latched[device_id])


class OverHttpWithoutTokensTests(http_tests.HttpFixture):
    def setUp(self) -> None:
        quiet_server_log(self)
        super().setUp()

    def test_a_malformed_estop_latches_over_http(self) -> None:
        device_id = next(iter(self.server.devices))
        status, _headers, payload = self.post(estop_message(jsonrpc="1.0", id="a", params={"reason": "x"}))
        self.assertEqual(status, 200, payload)
        self.assertEqual(payload["id"], "a")
        self.assertTrue(payload["error"]["data"]["details"]["estop_served"])
        self.assertTrue(self.server._latched[device_id])


if __name__ == "__main__":
    unittest.main()
