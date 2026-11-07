"""MCP tool calls: retry tokens, input refusals, protocol, evidence, operations (``mcp_drive.py`` port).

Findings: SURF-05 (input-schema refusals), SURF-06 (retry token, bounded
evidence, compact device list), SURF-07 (latest protocol version,
``resources/read`` before ``resources/list``, cancellation of a call in
flight), MISSED integration-surfaces (``retryToken`` broken end to end).
"""

from __future__ import annotations

import json
import threading
import time
import unittest

from mhs import canonical
from mhs.mcp import EVIDENCE_LAST_N, LATEST_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS, retry_command_id

from tests.surfaces import _support as s


class RetryTokenTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.server = s.reference("conveyor")
        self.addCleanup(self.spec.close)
        self.mcp = s.Mcp(self.server)
        self.step = self.mcp.tool("__world_step")

    def test_the_same_retry_token_replays_the_same_receipt(self) -> None:
        tick = s.tick(self.spec)
        first = s.receipt(self.mcp.call(self.step, {"ticks": 3}, meta={"retryToken": "retry-1"}))
        again = s.receipt(self.mcp.call(self.step, {"ticks": 3}, meta={"retryToken": "retry-1"}))
        self.assertEqual(first["status"], "completed")
        self.assertEqual(again["receipt_id"], first["receipt_id"])
        self.assertTrue(again.get("replayed"))
        self.assertEqual(first["command_id"], retry_command_id("retry-1", self.step))
        self.assertEqual(s.tick(self.spec), tick + 3)  # acted once
        other = s.receipt(self.mcp.call(self.step, {"ticks": 3}, meta={"retryToken": "retry-2"}))
        self.assertNotEqual(other["receipt_id"], first["receipt_id"])
        self.assertEqual(s.tick(self.spec), tick + 6)

    def test_a_non_ulid_command_id_maps_to_a_deterministic_ulid(self) -> None:
        mapped = retry_command_id("step-001", self.step)
        self.assertTrue(canonical.is_ulid(mapped))
        self.assertEqual(mapped, retry_command_id("step-001", self.step))
        self.assertNotEqual(mapped, retry_command_id("step-001", self.mcp.tool("__world_state")))
        first = s.receipt(self.mcp.call(self.step, {"ticks": 1, "command_id": "step-001"}))
        self.assertEqual(first["command_id"], mapped)
        again = s.receipt(self.mcp.call(self.step, {"ticks": 1, "command_id": "step-001"}))
        self.assertEqual(again["receipt_id"], first["receipt_id"])
        ulid = canonical.ulid()
        verbatim = s.receipt(self.mcp.call(self.step, {"ticks": 1, "command_id": ulid}))
        self.assertEqual(verbatim["command_id"], ulid)

    def test_a_reused_token_with_another_input_is_refused_not_executed(self) -> None:
        self.mcp.call(self.step, {"ticks": 1}, meta={"retryToken": "same"})
        tick = s.tick(self.spec)
        reused = self.mcp.call(self.step, {"ticks": 2}, meta={"retryToken": "same"})
        self.assertEqual(s.receipt(reused)["status"], "rejected")
        self.assertEqual(s.tick(self.spec), tick)

    def test_an_endpoint_failure_reports_the_command_id_to_retry_with(self) -> None:
        def broken(*_args, **_kwargs):
            from mhs.errors import MHSError

            raise MHSError("MHS.OUTCOME.TIMEOUT", "no response", {"may_have_effect": True})

        self.mcp.client.invoke = broken
        result = self.mcp.call(self.step, {"ticks": 1}, meta={"retryToken": "lost-1"})
        self.assertTrue(result["isError"])
        error = s.mhs_error(result)
        self.assertEqual(error["command_id"], retry_command_id("lost-1", self.step))
        self.assertTrue(error["may_have_effect"])


class InputRefusalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.server = s.reference("conveyor")
        self.addCleanup(self.spec.close)
        self.mcp = s.Mcp(self.server)
        self.step = self.mcp.tool("__world_step")

    def test_schema_refusal_is_a_tool_error_with_field_reasons(self) -> None:
        mark = self.mcp.mark()
        result = self.mcp.call(self.step, {"ticks": "five"})
        self.assertTrue(result["isError"], result)
        text = result["content"][0]["text"]
        self.assertTrue(text.startswith("MHS.CAPABILITY.INPUT_INVALID: $.ticks"), text)
        self.assertEqual(s.mhs_error(result)["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertTrue(s.mhs_error(result)["details"]["errors"])
        missing = self.mcp.call(self.step, {})
        self.assertIn("missing required property 'ticks'", missing["content"][0]["text"])
        self.assertNotIn("mhs.command", self.mcp.sent_since(mark))

    def test_an_enforced_limit_is_left_to_the_endpoint_which_receipts_it(self) -> None:
        # Plan 3.5: an out-of-range value is a safety refusal with a receipt, not INPUT_INVALID.
        result = self.mcp.call(self.step, {"ticks": 999999})
        self.assertFalse(result["isError"], result)
        receipt = s.receipt(result)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        evidence = self.mcp.call("mhs__evidence", {"command_id": receipt["command_id"]})
        self.assertEqual([item["receipt_id"] for item in evidence["structuredContent"]["evidence"]["receipts"]],
                         [receipt["receipt_id"]])

    def test_unknown_tool_stays_a_protocol_error(self) -> None:
        response = self.mcp.request("tools/call", {"name": "mhs__nope__nope", "arguments": {}})
        self.assertEqual(response["error"]["code"], -32602)


class ProtocolTests(unittest.TestCase):
    def test_initialize_negotiates_the_latest_supported_version(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        for requested, expected in [(version, version) for version in SUPPORTED_PROTOCOL_VERSIONS] + [
                ("2099-01-01", LATEST_PROTOCOL_VERSION)]:
            with self.subTest(requested=requested):
                mcp = s.Mcp(server, protocol_version=requested)
                self.assertEqual(mcp.initialized["result"]["protocolVersion"], expected)
        self.assertEqual(LATEST_PROTOCOL_VERSION, SUPPORTED_PROTOCOL_VERSIONS[-1])

    def test_resources_read_works_before_resources_list(self) -> None:
        spec, server = s.reference("conveyor")
        self.addCleanup(spec.close)
        mcp = s.Mcp(server)
        uri = "mhs://localhost:7400/devices/lab/conveyor-workcell/resources/workcell"
        read = mcp.request("resources/read", {"uri": uri})
        self.assertIn("result", read, read)
        self.assertEqual(json.loads(read["result"]["contents"][0]["text"])["resource_id"], "workcell")
        listed = {item["uri"] for item in mcp.request("resources/list")["result"]["resources"]}
        self.assertIn(uri, listed)
        self.assertIn("mhs://localhost:7400/evidence", listed)
        self.assertIn("mhs://localhost:7400/devices/lab/conveyor-workcell/reference", listed)
        reference = json.loads(mcp.request("resources/read", {
            "uri": "mhs://localhost:7400/devices/lab/conveyor-workcell/reference"})["result"]["contents"][0]["text"])
        self.assertEqual(reference["device"]["id"], s.CONVEYOR)


class DiscoveryToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.server = s.reference("conveyor")
        self.addCleanup(self.spec.close)
        self.mcp = s.Mcp(self.server)
        self.step = self.mcp.tool("__world_step")

    def test_evidence_is_bounded_and_the_bundle_is_a_resource(self) -> None:
        receipts = [s.receipt(self.mcp.call(self.step, {"ticks": 1})) for _ in range(EVIDENCE_LAST_N + 2)]
        evidence = self.mcp.call("mhs__evidence", {})
        self.assertFalse(evidence["isError"], evidence)
        summary = evidence["structuredContent"]["evidence"]
        bundle = self.mcp.client.export_evidence()
        self.assertEqual(summary["count"], len(bundle["receipts"]))
        self.assertEqual(summary["head_digest"], bundle["head_digest"])
        self.assertTrue(summary["valid"])
        self.assertEqual(len(summary["receipts"]), EVIDENCE_LAST_N)
        self.assertEqual(summary["receipts"][-1]["receipt_id"], receipts[-1]["receipt_id"])
        self.assertNotIn("bundle", summary)
        self.assertEqual(len(self.mcp.call("mhs__evidence", {"last_n": 2})["structuredContent"]["evidence"]
                             ["receipts"]), 2)
        one = self.mcp.call("mhs__evidence", {"command_id": receipts[0]["command_id"], "last_n": 0})
        self.assertEqual([item["receipt_id"] for item in one["structuredContent"]["evidence"]["receipts"]],
                         [receipts[0]["receipt_id"]])
        full = self.mcp.request("resources/read", {"uri": summary["uri"]})["result"]["contents"][0]["text"]
        self.assertEqual(json.loads(full)["head_digest"], bundle["head_digest"])
        with_bundle = self.mcp.call("mhs__evidence", {"include_bundle": True})["structuredContent"]["evidence"]
        self.assertEqual(with_bundle["bundle"]["head_digest"], bundle["head_digest"])
        # include_bundle is a host-only argument: the model-visible schema offers the bounded summary only
        listed = next(tool for tool in self.mcp.tools() if tool["name"] == "mhs__evidence")
        self.assertNotIn("include_bundle", listed["inputSchema"]["properties"])
        refused = self.mcp.call("mhs__evidence", {"last_n": -1})
        self.assertTrue(refused["isError"])

    def test_devices_is_a_compact_summary(self) -> None:
        result = self.mcp.call("mhs__devices", {})
        devices = result["structuredContent"]["devices"]
        self.assertEqual([item["device_id"] for item in devices], [s.CONVEYOR])
        self.assertEqual(set(devices[0]), {"device_id", "name", "mode", "risk_class", "resources", "tools"})
        self.assertIn(self.step, devices[0]["tools"])
        self.assertLess(len(result["content"][0]["text"]), 1500)

    def test_read_resolves_a_unique_resource_without_device_id(self) -> None:
        read = self.mcp.call("mhs__read", {"resource_id": "workcell"})
        self.assertFalse(read["isError"], read)
        unknown = self.mcp.call("mhs__read", {"resource_id": "nope"})
        self.assertTrue(unknown["isError"])

    def test_operations_lists_gets_and_waits_for_the_connectors_operations(self) -> None:
        receipt = s.receipt(self.mcp.call(self.step, {"ticks": 1}))
        listed = self.mcp.call("mhs__operations", {"device_id": s.CONVEYOR})["structuredContent"]["operations"]
        self.assertIn(receipt["operation_id"], [item["operation_id"] for item in listed["operations"]])
        got = self.mcp.call("mhs__operations", {"operation_id": receipt["operation_id"], "wait_ms": 1000})
        self.assertEqual(got["structuredContent"]["operations"]["receipt_id"], receipt["receipt_id"])


class InFlightCancelTests(unittest.TestCase):
    def test_notifications_cancelled_cancels_the_call_in_flight(self) -> None:
        spec, server = s.reference("conveyor", test_profile=True)
        self.addCleanup(spec.close)
        mcp = s.Mcp(server)
        delay = mcp.tool("__mhs_test_delay")
        outcome: dict = {}

        def run() -> None:
            started = time.monotonic()
            outcome["result"] = mcp.call(delay, {"ms": 2000}, mid="call-7")
            outcome["elapsed"] = time.monotonic() - started

        thread = threading.Thread(target=run)
        thread.start()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not any(
                op.final_receipt is None for op in list(server._operations.values())):
            time.sleep(0.005)
        mcp.notify("notifications/cancelled", {"requestId": "call-7", "reason": "user aborted"})
        thread.join(5.0)
        self.assertFalse(thread.is_alive())
        self.assertEqual(s.receipt(outcome["result"])["status"], "cancelled")
        self.assertLess(outcome["elapsed"], 1.5)


if __name__ == "__main__":
    unittest.main()
