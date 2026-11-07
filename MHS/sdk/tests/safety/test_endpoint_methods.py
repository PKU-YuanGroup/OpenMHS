"""Endpoint methods and runtime hygiene (WP-04 4a2; SDK-08, SDK-12, SDK-14, SDK-15).

Ports of ``sdk-core/e1.py`` / ``sdk-core-verify/v12.py`` (``mhs.registry.search``
crashed with a TypeError; ``mhs.conformance.report`` returned six hard-coded
passes), the in-process half of ``sdk-core/e6.py`` (an effectful command sent as
a notification was executed) and the stdio double-emit of ``sdk-core/e4.py``
seen from inside the server (``_notify`` emitted while holding ``self._lock``
and the flusher emitted the same event again).
"""

from __future__ import annotations

import copy
import inspect
import threading
import time
import unittest
from typing import Any

from mhs import _ids, canonical, protocol
from mhs.bridge.base import BridgeContext
from mhs.evidence import EvidenceLog
from mhs.schema import SchemaStore
from mhs.server import Capability, MHSServer, _BLOCKING_METHODS, _SELF_BOUNDED_METHODS

from ._support import (
    MOVE,
    READ,
    StubBridge,
    conveyor,
    error_code,
    open_session,
    stub_capabilities,
    stub_server,
)


class RegistrySearchTests(unittest.TestCase):
    def test_v12_registry_search_is_not_an_endpoint_method(self) -> None:
        server, rpc, _device, _session = conveyor()
        response = rpc.raw("mhs.registry.search", query={"capability": "step"})
        self.assertEqual(error_code(response), "MHS.PROTOCOL.METHOD_NOT_FOUND", response)

    def test_the_protocol_method_table_matches_the_endpoint(self) -> None:
        """protocol.METHODS lists exactly what an endpoint may serve (verifier 4a2 minor)."""
        self.assertNotIn("mhs.registry.search", protocol.METHODS)
        self.assertNotIn("mhs.registry.search", protocol.METHOD_NAMES)
        self.assertEqual(protocol.Method.REGISTRY_SEARCH, "mhs.registry.search")
        served = set(MHSServer._METHODS)
        # mhs.composition.run is an optional (O) endpoint method this SDK does not serve.
        self.assertEqual(set(protocol.METHOD_NAMES) - served, {"mhs.composition.run"})
        self.assertEqual(served - set(protocol.METHOD_NAMES), set())


class ConformanceReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server, self.rpc, _device, _session = conveyor()
        self.store = SchemaStore()

    def test_v12_without_a_stored_run_nothing_is_claimed(self) -> None:
        report = self.rpc("mhs.conformance.report", level="CL5")
        self.assertEqual(self.store.validate(report, "conformance-report.schema.json"), [])
        self.assertEqual(report["level_achieved"], "CL0")
        self.assertTrue(report["tests"])
        self.assertEqual({test["status"] for test in report["tests"]}, {"skip"})
        self.assertTrue(all(test["detail"].startswith("not_run") for test in report["tests"]))
        self.assertEqual(report["coverage"]["passed"], 0)
        body = {key: value for key, value in report.items() if key != "report_digest"}
        self.assertEqual(report["report_digest"], canonical.digest(body))
        self.assertIn("not_certified", {item["id"] for item in report["disclaimers"]})
        self.assertEqual(report["environment"]["suite"], f"{_ids.DIST_NAME} {_ids.SDK_VERSION}")

    def test_the_last_stored_run_suite_report_is_returned(self) -> None:
        stored = self.rpc("mhs.conformance.report")
        stored = copy.deepcopy(stored)
        stored["level_achieved"] = "CL2"
        stored["tests"][0]["status"] = "pass"
        stored.pop("report_digest")
        stored["report_digest"] = canonical.digest(stored)
        self.server.record_conformance_report(stored)
        self.assertEqual(self.rpc("mhs.conformance.report"), stored)
        tampered = copy.deepcopy(stored)
        tampered["level_achieved"] = "CL4"
        with self.assertRaises(ValueError):
            self.server.record_conformance_report(tampered)
        foreign = copy.deepcopy(stored)
        foreign["subject"]["id"] = "mhs://elsewhere"
        foreign.pop("report_digest")
        foreign["report_digest"] = canonical.digest(foreign)
        with self.assertRaises(ValueError):
            self.server.record_conformance_report(foreign)
        self.assertEqual(self.rpc("mhs.conformance.report")["report_digest"], stored["report_digest"])


class HelloTests(unittest.TestCase):
    def test_unclaimed_devices_claim_no_conformance(self) -> None:
        server, rpc, _device, _bridge = stub_server()
        hello = rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertEqual(hello["conformance"], [])

    def test_a_claimed_device_is_listed_as_claimed(self) -> None:
        server, rpc, device, _bridge = stub_server()
        digest = "sha256:" + "ab" * 32
        device.conformance = {"profile": "MHS-Sim", "level": "CL2", "report_digest": digest}
        hello = rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertEqual(hello["conformance"], [{"profile": "MHS-Sim", "level": "CL2",
                                                 "report_digest": digest}])

    def test_implementation_spec_version_and_retention(self) -> None:
        server, rpc, _device, _bridge = stub_server()
        hello = rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertEqual(hello["implementation"], {"name": _ids.DIST_NAME, "version": _ids.SDK_VERSION})
        self.assertEqual(hello["spec_version"], _ids.SPEC_VERSION)
        self.assertEqual(hello["server"]["version"], _ids.SDK_VERSION)
        self.assertEqual(hello["mhs_version"], _ids.WIRE_VERSION)
        limits = hello["limits"]
        self.assertEqual(limits["receipt_retention_days"] * 86_400, limits["max_receipt_retention_s"])
        self.assertEqual(limits["max_receipt_retention_s"], server.receipt_retention_s)

    def test_evidence_server_identity_comes_from_ids(self) -> None:
        self.assertEqual(EvidenceLog("mhs://localhost/x").server,
                         {"name": _ids.DIST_NAME, "version": _ids.SDK_VERSION})
        server, rpc, _device, _bridge = stub_server()
        bundle = rpc("mhs.evidence.export")
        self.assertEqual(bundle["endpoint_info"]["server"]["version"], _ids.SDK_VERSION)


class NotificationTests(unittest.TestCase):
    def test_e6_effectful_notifications_are_dropped(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        before = server._revisions[device.device_id]
        cases = {
            "mhs.command": {"session_id": session, "capability_id": MOVE, "input": {"pos": 3},
                            "deadline_ms": 1000},
            "mhs.resource.write": {"session_id": session, "patch": {"pos": 3}, "deadline_ms": 1000},
            "mhs.safety.reset": {"session_id": session, "deadline_ms": 1000},
            "mhs.restore": {"session_id": session, "snapshot": {}, "deadline_ms": 1000},
            "mhs.safety.permit": {"session_id": session, "capability_id": MOVE, "input": {"pos": 3}},
        }
        for method, params in cases.items():
            with self.subTest(method):
                with self.assertLogs("mhs.server", level="WARNING") as logs:
                    result = server.handle({"jsonrpc": "2.0", "method": method, "params": params})
                self.assertIsNone(result)
                self.assertTrue(any(method in line for line in logs.output), logs.output)
        self.assertEqual(bridge.calls.count(MOVE), 0)
        self.assertNotIn("reset", bridge.calls)
        self.assertEqual(server._revisions[device.device_id], before)
        self.assertEqual(server._permits, {})

    def test_an_estop_notification_still_latches(self) -> None:
        server, rpc, device, bridge = stub_server()
        result = server.handle({"jsonrpc": "2.0", "method": "mhs.safety.estop",
                                "params": {"reason": "fire-and-forget", "deadline_ms": 1000}})
        self.assertIsNone(result)
        self.assertTrue(server._latched[device.device_id])

    def test_non_finite_numbers_are_a_parse_error(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value):
                response = rpc.raw("mhs.command", session_id=session, capability_id=MOVE,
                                   input={"pos": value}, deadline_ms=1000)
                self.assertEqual(error_code(response), "MHS.PROTOCOL.PARSE_ERROR", response)
        self.assertEqual(bridge.calls.count(MOVE), 0)


class EventDeliveryTests(unittest.TestCase):
    def test_push_events_are_emitted_once_and_outside_the_server_lock(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        subscription = rpc("mhs.subscribe", session_id=session, streams=["state"],
                           deadline_ms=1000)["subscription_id"]
        emitted: list[Any] = []
        held: list[bool] = []

        def emit(message: Any) -> None:
            held.append(server._lock._is_owned())  # noqa: SLF001
            emitted.append(message.to_dict() if hasattr(message, "to_dict") else message)

        server._emit = emit
        self.addCleanup(setattr, server, "_emit", None)
        receipt = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 2},
                      deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed")
        events = [m for m in emitted if m.get("method") == "mhs.event"
                  and m["params"]["subscription_id"] == subscription]
        self.assertEqual([event["params"]["seq"] for event in events], [1])
        self.assertEqual(held, [False] * len(held), "emit() ran while holding self._lock")
        self.assertEqual(server.take_notifications_for(subscription), [], "the event was buffered twice")

    def test_safety_changes_reach_control_subscriptions(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        subscription = rpc("mhs.subscribe", session_id=session, streams=["control"],
                           deadline_ms=1000)["subscription_id"]
        rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
        events = [event.to_dict()["params"] for event in server.take_notifications_for(subscription)]
        safety = [event for event in events if event.get("type") == "safety"]
        self.assertTrue(safety, events)
        self.assertEqual(safety[0]["stream"], "control")
        self.assertTrue(safety[0]["payload"]["latched"])


class BridgeContextTests(unittest.TestCase):
    def test_bridges_see_a_truthful_remaining_budget(self) -> None:
        seen: dict[str, Any] = {}

        class Recording(StubBridge):
            def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
                if capability_id == MOVE:
                    time.sleep(0.05)
                    seen["deadline_at"] = ctx.extra.get("deadline_at")
                    seen["server_ms"] = ctx.remaining_ms()
                    seen["bridge_ms"] = BridgeContext.coerce(ctx).remaining_ms()
                    seen["now"] = time.monotonic()
                return super().call(capability_id, args, ctx)

        server, rpc, device, bridge = stub_server(Recording())
        session = open_session(rpc, device)
        rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1}, deadline_ms=1000)
        self.assertIsInstance(seen["deadline_at"], float)
        self.assertLessEqual(seen["deadline_at"] - seen["now"], 1.0)
        for key in ("server_ms", "bridge_ms"):
            self.assertLess(seen[key], 1000, key)
            self.assertGreater(seen[key], 500, key)


class MalformedConstraintTests(unittest.TestCase):
    """Port of the verifier probe ``verify-WP-04/4a2/repros/maxdur_probe.py``.

    A non-numeric ``constraints.max_duration_ms`` raised after the device lock
    and the in-flight entry were taken but outside the ``try``: the call
    answered MHS.INTERNAL.ERROR and every later exclusive command on the
    device was MHS.DEVICE.BUSY for good.
    """

    def _server(self, bad: Any):
        caps = [c for c in stub_capabilities() if c.capability_id != MOVE]
        caps.append(Capability(MOVE, "axis",
                               input_schema={"type": "object", "properties": {"pos": {"type": "integer"}}},
                               exclusive=True, constraints={"max_duration_ms": bad}))
        return stub_server(capabilities=caps)

    def test_a_malformed_max_duration_never_leaks_the_device_lock(self) -> None:
        for bad in ("abc", "10s", [1]):
            with self.subTest(bad=bad):
                server, rpc, device, bridge = self._server(bad)
                session = open_session(rpc, device)
                for _attempt in range(2):
                    receipt = rpc("mhs.command", session_id=session, capability_id=MOVE,
                                  input={"pos": 1}, deadline_ms=1000)
                    self.assertEqual(receipt["status"], "failed", receipt)
                self.assertFalse(server._device_locks[device.device_id].locked())
                self.assertEqual(server._inflight, {})
                self.assertEqual(bridge.calls.count(MOVE), 0)
                stopped = rpc("mhs.command", session_id=session, capability_id="cap.motion.stop.v1",
                              input={}, deadline_ms=1000)
                self.assertEqual(stopped["status"], "completed", stopped)

    def test_a_missing_bridge_frees_the_lock_and_the_command_id(self) -> None:
        server, rpc, device, bridge = stub_server()
        session = open_session(rpc, device)
        command_id = canonical.ulid()
        device.bridge = None
        response = rpc.raw("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1},
                           command_id=command_id, deadline_ms=1000)
        self.assertEqual(error_code(response), "MHS.DEVICE.NOT_READY", response)
        self.assertFalse(server._device_locks[device.device_id].locked())
        self.assertEqual(server._inflight, {})
        device.bridge = bridge
        receipt = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1},
                      command_id=command_id, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)


class SessionIdTests(unittest.TestCase):
    def test_session_ids_carry_random_bits(self) -> None:
        """SSE access rests on the session id until 4b binds tokens to sessions:
        an id opened in the same millisecond must not give away the next one."""
        server, rpc, device, _bridge = stub_server()
        ids = [open_session(rpc, device) for _ in range(20)]
        store = SchemaStore()
        for session_id in ids:
            self.assertRegex(session_id, r"^mhs_s_[0-9A-HJKMNP-TV-Z]{26}[0-9a-f]{16}$")
        self.assertEqual(len({session_id[-16:] for session_id in ids}), len(ids))
        receipt = rpc("mhs.command", session_id=ids[0], capability_id=MOVE, input={"pos": 1},
                      deadline_ms=1000)
        self.assertEqual(store.validate(receipt, "receipt.schema.json"), [])


class DeadCodeTests(unittest.TestCase):
    def test_dead_helpers_are_gone(self) -> None:
        import mhs.server as module

        for name in ("_full_state", "_read_capability", "_session_command_count", "_state_hash",
                     "_m_registry_search"):
            self.assertFalse(hasattr(MHSServer, name), name)
        for name in ("_exclude_pointers", "_hashable"):
            self.assertFalse(hasattr(module, name), name)
        self.assertNotIn("mhs.composition.run", _BLOCKING_METHODS)
        self.assertNotIn("mhs.composition.run", _SELF_BOUNDED_METHODS)
        parameters = inspect.signature(MHSServer).parameters
        self.assertNotIn("max_sync_wait_ms", parameters)
        self.assertNotIn("write_patch", inspect.signature(MHSServer._run_command).parameters)
        self.assertNotIn("lease", inspect.signature(MHSServer._run_command).parameters)


if __name__ == "__main__":
    unittest.main()
