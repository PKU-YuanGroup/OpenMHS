"""Acceptance run of the BCS motor package: the gate, plus cases for the native-shaped fake and the stop path.

Add cases, never remove the check_driver call.  Since the model review of 2026-11-05 the e-stop sends StopMotor and
reports SAFE_STATE_UNREACHED with the latch held, because the BCS client shares one REQ socket without a lock or a
receive timeout and swallows a refused StopMotor; the gate fails G6.ESTOP_FAILED and the package is blocked.  The
cases below keep the contract, the stop action's fresh-state check and the transport hazard exercised.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.als-controls.bcs_move.v1"
STOP = "x-cap.als-controls.bcs_stop.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
FAULTED = "MHS.DEVICE.FAULTED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BcsMotorCases(unittest.TestCase):
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

    def test_the_initial_state_is_a_fresh_getmotorfull(self) -> None:
        client, fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), ["moving", "position", "units"])
        self.assertEqual(state["position"], 0.0)        # placeholder
        self.assertFalse(state["moving"])
        self.assertEqual(state["units"], "mm")          # placeholder
        self.assertGreater(fake.bcs_server.queries, 0)  # the state read queried the fake server, not a cache

    def test_a_move_is_refused_until_the_site_supplies_the_range(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke(MOVE, {"target_position": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)  # placeholder, untouched

    def test_the_example_overlay_admits_a_move_and_the_fresh_state_shows_it(self) -> None:
        client, fake = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(MOVE, {"target_position": 2.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["position"], 2.5)
        self.assertTrue(receipt["output"]["move_complete"])
        self.assertEqual(self.state(client)["position"], 2.5)
        self.assertEqual(fake.bcs_server.goal, 2.5)

    def test_the_stop_reports_fresh_quiescence(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertEqual(receipt["output"]["position"], 0.0)  # placeholder
        self.assertFalse(fake.isMoving)

    def test_a_stopmotor_acknowledgement_without_move_complete_is_not_stopped(self) -> None:
        client, fake = self.serve()
        fake.bcs_server.move_complete = False
        fake.bcs_server.stop_confirms = False
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], FAULTED)

    def test_a_failed_getmotorfull_is_not_hidden(self) -> None:
        client, fake = self.serve()
        fake.bcs_server.fail_queries = True
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")

    def test_a_malformed_getmotorfull_is_not_hidden(self) -> None:
        client, fake = self.serve()
        fake.bcs_server.malformed_queries = True
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.ADAPTER.SHIM_FAILED")

    def test_the_estop_path_fails_when_the_stop_is_not_confirmed(self) -> None:
        client, fake = self.serve()
        fake.bcs_server.move_complete = False
        fake.bcs_server.stop_confirms = False
        receipt = client.estop("test", **self.ids)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertFalse((receipt.get("output") or {}).get("safe_state_achieved", False))

    def test_the_estop_sends_stopmotor_but_reports_unreached(self) -> None:
        client, fake = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertGreaterEqual(fake.bcs_server.stop_requests, 1)
        self.assertFalse(fake.isMoving)
        refused = client.invoke(MOVE, {"target_position": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertIn("position", self.state(client))

    def test_a_stopmotor_behind_a_pending_reply_never_arrives(self) -> None:
        # A cancelled GetMotorFull leaves the shared REQ socket waiting for its reply (bcs_server.py:123-148):
        # BCSMotor.stop() swallows the refused send in its worker thread (bcs_motor.py:412-436).
        client, fake = self.serve()
        fake.bcs_server.awaiting_reply = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(fake.bcs_server.stop_requests, 0)
        self.assertIsNone(fake.stop())                # the upstream wrapper returns normally all the same
        self.assertEqual(fake.bcs_server.stop_requests, 0)

    def test_a_refused_movemotor_still_ends_completed(self) -> None:
        # zmq_move_motor swallows a failed MoveMotor (bcs_motor.py:378-409); the server's Move Complete then ends
        # the move although the motor never left its position.
        client, fake = self.serve(str(HERE / "site-limits.example.json"))
        fake.bcs_server.fail_move = True
        receipt = client.invoke(MOVE, {"target_position": 2.5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["move_complete"])
        self.assertEqual(receipt["output"]["position"], 0.0)  # placeholder start position, not the target


if __name__ == "__main__":
    unittest.main()
