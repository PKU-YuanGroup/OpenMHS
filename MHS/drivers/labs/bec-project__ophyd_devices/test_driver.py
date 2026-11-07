"""Acceptance run of the PSI simple positioner: the gate, plus the cases specific to this package.

Add cases, never remove the check_driver call.  Since the model review of 2026-11-05 the e-stop sends the upstream
hold request (user_setpoint := user_readback.get(), a new target rather than a stop) and reports
SAFE_STATE_UNREACHED with the latch held, so the gate fails G6.ESTOP_FAILED and the package is blocked; the cases
below keep the contract and the honest stop outcome exercised.
"""

import json
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.bec-project.axis_move.v1"
STOP = "x-cap.bec-project.axis_stop.v1"
FIELDS = ("done_moving", "position", "setpoint", "velocity")
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PSISimplePositionerCases(unittest.TestCase):
    def serve(self, overlay=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver

    def example_overlay(self):
        return json.loads((HERE / "site-limits.example.json").read_text())

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_field_is_a_fresh_signal_read(self) -> None:
        client, fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(FIELDS))
        self.assertEqual(state["position"], 0.0)       # placeholder
        self.assertEqual(state["setpoint"], 0.0)       # placeholder
        self.assertEqual(state["velocity"], 1.0)       # placeholder
        self.assertTrue(state["done_moving"])
        for name in ("user_readback", "user_setpoint", "velocity", "motor_done_move"):
            calls = getattr(fake.native, name)._calls
            self.assertTrue(calls, name)
            self.assertEqual(set(calls), {False}, f"{name} must be read with use_monitor=False")

    def test_move_without_the_operator_overlay_is_refused(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(MOVE, {"target": 1.0}, **self.ids)  # placeholder target
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(fake.native.move_count, 0)

    def test_move_with_the_example_overlay_reaches_the_target(self) -> None:
        client, fake = self.serve(self.example_overlay())
        receipt = client.invoke(MOVE, {"target": 1.0}, **self.ids)  # placeholder target
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["reached"], receipt)
        self.assertAlmostEqual(receipt["output"]["position"], 1.0)  # placeholder target
        self.assertAlmostEqual(fake.native.user_readback.get(use_monitor=False), 1.0)  # placeholder target
        self.assertAlmostEqual(self.state(client)["position"], 1.0)  # placeholder target
        self.assertGreaterEqual(fake.native.move_count, 1)

    def test_the_stop_action_is_a_hold_request(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"], receipt)  # the fake axis was idle
        self.assertGreaterEqual(fake.native.stop_count, 1)
        self.assertTrue(fake.native.stopped)

    def test_the_hold_request_retargets_a_moving_axis(self) -> None:
        # Upstream fallback (psi_positioner_base.py:319-321): the setpoint becomes the read-back value; the done
        # flag is the axis's own and the running move status fails.
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        fake = driver.native
        status = fake.move(1.0)                  # placeholder target
        time.sleep(0.05)                         # placeholder: let the fake axis start moving
        fake.stop()
        self.assertTrue(status.done)
        self.assertFalse(status.success)
        held = fake.user_setpoint.get(use_monitor=False)
        self.assertGreater(held, 0.0)
        self.assertLess(held, 1.0)

    def test_the_stopped_flag_survives_a_later_move(self) -> None:
        # Upstream resets stopped only in stage() (psi_device_base.py:109-118); reached must not depend on it.
        client, fake = self.serve(self.example_overlay())
        client.invoke(STOP, {}, **self.ids)
        receipt = client.invoke(MOVE, {"target": 1.0}, **self.ids)  # placeholder target
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(fake.native.stopped)
        self.assertTrue(receipt["output"]["reached"], receipt)

    def test_the_estop_sends_the_hold_but_reports_unreached(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        self.assertGreaterEqual(fake.native.stop_count, 1)
        refused = client.invoke(MOVE, {"target": 1.0}, **self.ids)  # placeholder target
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(self.state(client)["position"], 0.0)  # placeholder start position

    def test_the_stop_action_is_not_a_safe_state_action(self) -> None:
        client, _fake = self.serve()
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")


if __name__ == "__main__":
    unittest.main()
