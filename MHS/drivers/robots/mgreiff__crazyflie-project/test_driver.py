"""Acceptance run of the Crazyflie trajectory ROS package: the gate, plus repository cases.

Add cases, never remove the check_driver call.  The tests use the ROS-free fake
transport only; no ROS graph, rosbridge peer, crazyflie_ros driver, simulator or
hardware is contacted.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = HERE / "site-limits.example.json"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"

VELOCITY = {
    "linear": {"x": 0.1, "y": -0.1, "z": 0.0},
    "angular": {"x": 0.0, "y": 0.0, "z": 0.1},
}
PACKET = {
    "data": [0.1, -0.1, 0.2, -0.2, 0.3, -0.3],
    "time": 1.0,
    "index": 0,
    "dimension": 0,
    "number": 1,
    "type": 0,
}
SYNC = {
    "synchronize": 1,
    "circular": [0, 0, 0, 0],
    "number": [1, 1, 1, 1],
    "time": [0.5, 0.5, 0.5, 0.5],
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CrazyflieCases(unittest.TestCase):
    def serve(self, *, overlay: bool = True):
        server = load(HERE, backend="fake", site_limits=str(OVERLAY) if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_the_master_publications_reach_the_fake(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.mgreiff.cmd_vel.v1", VELOCITY),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.call("x-cap.mgreiff.trajectory_packet.v1", PACKET),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.call("x-cap.mgreiff.synchronization_packet.v1", SYNC),
                         {"published": True, "confirmed": False})
        self.assertEqual(driver.native.twist_packets[-1], {
            "linear": {"x": 0.1, "y": -0.1, "z": 0.0},
            "angular": {"x": 0.0, "y": 0.0, "z": 0.1},
        })
        self.assertEqual(driver.native.trajectory_packets[-1], PACKET)
        self.assertEqual(driver.native.synchronization_packets[-1], SYNC)
        self.assertEqual(driver.native.log_ref_values, PACKET["data"])
        self.assertIn("/crazyflie/trajectory_packet", driver.native.advertised_topics)

    def test_update_params_reaches_the_acknowledged_service(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.mgreiff.update_params.v1",
                                     {"parameters": ["reference.x", "reference.y"]}),
                         {"accepted": True})
        self.assertEqual(driver.native.last_params, ["reference.x", "reference.y"])

    def test_the_emergency_request_is_acknowledged(self) -> None:
        driver = self.driver()
        self.assertEqual(driver.call("x-cap.mgreiff.emergency.v1", {}), {"accepted": True})
        self.assertTrue(driver.native.emergency_requested)
        self.assertEqual(driver.native.emergency_requests, 1)

    def test_a_failed_emergency_service_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.fail_emergency_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.mgreiff.emergency.v1", {})
        self.assertFalse(driver.native.emergency_requested)

    def test_a_malformed_emergency_response_is_a_failure(self) -> None:
        driver = self.driver()
        driver.native.malformed_emergency_response = True
        with self.assertRaises(OutcomeUnknown):
            driver.call("x-cap.mgreiff.emergency.v1", {})
        self.assertFalse(driver.native.emergency_requested)

    def test_operator_required_inputs_refuse_without_an_overlay(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke("x-cap.mgreiff.trajectory_packet.v1", PACKET, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_the_example_overlay_admits_valid_values_and_refuses_out_of_envelope(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.mgreiff.trajectory_packet.v1", PACKET, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"published": True, "confirmed": False})
        too_big = dict(PACKET, data=[11.0, -0.1, 0.2, -0.2, 0.3, -0.3])
        refused = client.invoke("x-cap.mgreiff.trajectory_packet.v1", too_big, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_e_stop_latches_but_does_not_claim_a_safe_state(self) -> None:
        # Reviewer (r20): /crazyflie/emergency is answered by the external crazyflie_ros driver (the clone
        # defines only the proxy, master.py:36), so no stop is bound: the e-stop calls nothing upstream,
        # fails SAFE_STATE_UNREACHED and keeps the latch.
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        server = build_server(driver, site_limits=str(OVERLAY))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        receipt = client.estop("test", **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertFalse(driver.native.emergency_requested)
        self.assertEqual(driver.native.emergency_requests, 0)
        refused = client.invoke("x-cap.mgreiff.cmd_vel.v1", VELOCITY, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_no_stop_or_safe_state_action_is_declared(self) -> None:
        cls = type(self.driver())
        self.assertFalse(any(action.safe_state for action in cls.actions.values()))
        self.assertNotIn("estop", dict(cls.safety_bindings))


if __name__ == "__main__":
    unittest.main()
