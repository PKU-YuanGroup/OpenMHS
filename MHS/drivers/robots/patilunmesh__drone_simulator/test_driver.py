"""Acceptance run of the CBF drone simulator package: the gate, plus local cases.

Add cases, never remove the check_driver call.  The package is expected to
report the missing native stop in G6/G8; the local cases still exercise the
declared reset and pose surface.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DroneCbfSimCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_reset_needs_the_operator_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.patilunmesh.reset.v1",
                                {"reset": True, "cbf_param": 15.0}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_allows_reset_and_reports_done(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.patilunmesh.reset.v1",
                                {"reset": True, "cbf_param": 15.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["done"], True)

    def test_the_pose_and_twist_reads_expose_the_published_odometry(self) -> None:
        client = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(set(state["pose"]), {"position", "orientation"})
        self.assertEqual(set(state["pose"]["position"]), {"x", "y", "z"})
        self.assertEqual(set(state["twist"]), {"linear", "angular"})
        self.assertEqual(set(state["twist"]["linear"]), {"x", "y", "z"})

    def test_reset_reaches_the_service_and_changes_the_fake_pose(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertNotEqual(driver.native.position, [0.0, 0.0, 0.0])
        self.assertEqual(driver.call("x-cap.patilunmesh.reset.v1",
                                     {"reset": True, "cbf_param": 15.0}), {"done": True})
        self.assertEqual(driver.native.position, [15.0, 0.0, 0.0])
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual([message.get("service") for message in calls], ["/ResetSim"])
        self.assertEqual(calls[0]["args"], {"reset": True, "cbf_param": 15.0})

    def test_a_failed_service_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_reset_service = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.patilunmesh.reset.v1", {"reset": True, "cbf_param": 15.0})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_reset_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call("x-cap.patilunmesh.reset.v1", {"reset": True, "cbf_param": 15.0})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_malformed_service_reply_is_unknown(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_reset_reply = True
        with self.assertRaises(Exception) as caught:  # noqa: BLE001 - the exact bridge error is the assertion
            driver.call("x-cap.patilunmesh.reset.v1", {"reset": True, "cbf_param": 15.0})
        self.assertEqual(getattr(caught.exception, "code", None), "MHS.OUTCOME.UNKNOWN")

    def test_no_safe_state_is_claimed(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        status = driver.safety_status()
        self.assertIsNone(status.get("estop", {}).get("native"))
        self.assertIs(status.get("safe_state", {}).get("achieved"), False)

    def test_the_estop_latches_and_refuses_the_reset(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        refused = client.invoke("x-cap.patilunmesh.reset.v1",
                                {"reset": True, "cbf_param": 15.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
