"""Acceptance run of the Zolix stage package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The values asserted here are the fake's placeholders (marked in
fake.py), not facts about a device.
"""

import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.lewbert.stage_move_abs.v1"
STOP = "cap.motion.stop.v1"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
INTERLOCK = "MHS.SAFETY.INTERLOCK_OPEN"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ZolixCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.server = server
        return client

    def fake(self):
        return self.server.devices[self.ids["device_id"]].bridge.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def move(self, client, **patch):
        return client.invoke(MOVE, patch, **self.ids)

    def test_the_fake_starts_at_rest(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["x_um"], state["y_um"], state["r_deg"]), (0.0, 0.0, 0.0))
        self.assertEqual((state["moving"], state["estop_active"], state["alarm"]), (False, False, False))

    def test_the_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        refused = self.move(client, x_um=100.0, y_um=-50.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        state = self.state(client)
        self.assertEqual((state["x_um"], state["y_um"]), (0.0, 0.0))

    def test_the_example_overlay_moves_the_stage_and_reports_the_rest_position(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.move(client, x_um=100.0, y_um=-50.0, r_deg=1.0)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertAlmostEqual(receipt["output"]["x_um"], 100.0)
        self.assertAlmostEqual(receipt["output"]["y_um"], -50.0)
        self.assertAlmostEqual(receipt["output"]["r_deg"], 1.0)
        state = self.state(client)
        self.assertAlmostEqual(state["x_um"], 100.0)
        self.assertAlmostEqual(state["y_um"], -50.0)
        self.assertAlmostEqual(state["r_deg"], 1.0)
        self.assertFalse(state["moving"])

    def test_an_input_outside_the_example_overlay_is_refused_without_moving(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = self.move(client, x_um=1001.0, y_um=0.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual((state["x_um"], state["y_um"]), (0.0, 0.0))

    def test_the_stop_action_is_the_safe_state(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["stopped"])
        self.assertFalse(self.state(client)["moving"])
        # The class field is accepted for schema compatibility; the native stop has no deceleration parameter.
        with_value = client.invoke(STOP, {"deceleration": 2.0}, **self.ids)
        self.assertEqual(with_value["status"], "completed", with_value)

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["moving"])
        refused = self.move(client, x_um=10.0, y_um=10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_stop_that_leaves_an_axis_moving_is_not_a_safe_state(self) -> None:
        # Model review: the upstream stop never raises (talos/hal/devices/zolix.py:347-365), so a stop opcode the
        # controller does not act on returns normally.  Only the fresh status read may confirm the safe state; the
        # runtime counts a safe-state action that returns as reached, so this case must fail, never complete with
        # stopped false.  The fake is changed in memory only: an axis keeps moving and its stop does nothing.
        client = self.serve(str(HERE / "site-limits.example.json"))
        fake = self.fake()
        fake._target = (5.0, 5.0, 0.0)                # placeholder: an axis is moving ...
        fake._move_end = time.monotonic() + 3600.0    # placeholder: ... for longer than the test runs
        fake.stop = lambda: None                      # the controller does not act on the stop opcode
        direct = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(direct["status"], "failed", direct)
        self.assertEqual(direct["error"]["mhs_code"], UNREACHED)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED)
        self.assertTrue(receipt["error"]["details"]["latched"])
        refused = self.move(client, x_um=10.0, y_um=10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_controller_estop_bit_blocks_the_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.fake()._estop = True                     # placeholder: the controller reports its e-stop bit
        self.assertTrue(self.state(client)["estop_active"])
        refused = self.move(client, x_um=10.0, y_um=10.0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INTERLOCK)
        state = self.state(client)
        self.assertEqual((state["x_um"], state["y_um"]), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
