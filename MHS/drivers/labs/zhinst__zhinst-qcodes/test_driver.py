"""Acceptance run of the zhinst-qcodes PQSC driver: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
TRIGGER = "x-cap.zhinst.pqsc_trigger.v1"
WAIT_DONE = "x-cap.zhinst.pqsc_wait_done.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZhinstPQSCCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_carry_the_upstream_types(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertIsInstance(state["device_type"], str)
        self.assertIsInstance(state["serial"], str)
        self.assertIsInstance(state["firmware"], str)
        self.assertIsInstance(state["streaming_nodes"], list)
        self.assertIsInstance(state["ref_clock_locked"], bool)

    def test_the_trigger_operations_reach_the_fake(self) -> None:
        client, fake = self.serve()
        for operation in ("arm", "run", "stop", "factory_reset"):
            receipt = client.invoke(TRIGGER, {"operation": operation}, **self.ids)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"], {"operation": operation, "issued": True})
        self.assertEqual([call[0] for call in fake._calls],
                         ["arm", "run", "stop", "factory_reset"])

    def test_arm_and_run_is_forwarded_without_the_deep_flag(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(TRIGGER, {"operation": "arm_and_run"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(fake._calls, [("arm_and_run", None, None)])

    def test_an_unknown_operation_is_refused(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(TRIGGER, {"operation": "launch"}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(fake._calls, [])

    def test_the_wait_done_timeout_waits_for_the_site_envelope(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke(WAIT_DONE, {"timeout": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_wait_done_timeout_inside_and_outside_the_site_envelope(self) -> None:
        client, fake = self.serve(site_limits=SITE_LIMITS)
        applied = client.invoke(WAIT_DONE, {"timeout": 2.0}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertTrue(applied["output"]["done"])
        outside = client.invoke(WAIT_DONE, {"timeout": 60.0}, **self.ids)
        self.assertEqual(outside["status"], "rejected", outside)
        self.assertEqual(outside["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual([call[0] for call in fake._calls], ["wait_done"])

    def test_the_estop_stops_the_native_device_and_latches(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(fake._stops, 1)
        self.assertEqual(fake._calls[-1], ("stop", True))     # the deep, synchronized stop (model review)
        refused = client.invoke(TRIGGER, {"operation": "arm"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_a_stop_that_raises_leaves_the_estop_unreached(self) -> None:
        client, fake = self.serve()

        def failed_stop(*, deep=True):
            raise RuntimeError("placeholder: the deep stop did not synchronize")

        fake.stop = failed_stop
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke(TRIGGER, {"operation": "run"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_identity_and_node_reads_are_text_whatever_the_native_type(self) -> None:
        client, fake = self.serve()
        fake._idn["firmware"] = 12345                            # placeholder integer node value

        class _Node:
            def __str__(self):
                return "/dev0000/demods/0/sample"                # placeholder node path

        fake._streaming_nodes = [_Node()]
        state = self.state(client)
        self.assertEqual(state["firmware"], "12345")
        self.assertEqual(state["streaming_nodes"], ["/dev0000/demods/0/sample"])

    def test_a_failed_native_call_is_a_failed_receipt(self) -> None:
        client, fake = self.serve()

        def rejected(**kwargs):
            raise RuntimeError("placeholder: native arm failed")

        fake.arm = rejected
        receipt = client.invoke(TRIGGER, {"operation": "arm"}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)


if __name__ == "__main__":
    unittest.main()
