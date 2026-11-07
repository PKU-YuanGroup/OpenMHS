"""Acceptance run of the OpenUC2 ESP32 stage package: the gate plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
FAULTED = "MHS.DEVICE.FAULTED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StageCases(unittest.TestCase):
    def serve(self, site_limits=None, options=None):
        server = load(HERE, backend="fake", site_limits=site_limits, options=options)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def move(self, client, x=100.0, y=200.0, z=50.0):
        return client.invoke("x-cap.openuc2.move_xyz.v1",
                             {"x_um": x, "y_um": y, "z_um": z}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_move_waits_for_the_site_envelope(self) -> None:
        client = self.serve()
        before = self.state(client)
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client), before)

    def test_the_example_overlay_moves_three_axes(self) -> None:
        client = self.serve(OVERLAY)
        receipt = self.move(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"x_um": 100.0, "y_um": 200.0, "z_um": 50.0})
        state = self.state(client)
        self.assertEqual((state["x_um"], state["y_um"], state["z_um"]), (100.0, 200.0, 50.0))
        refused = self.move(client, x=1001.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["x_um"], 100.0)

    def test_the_stop_and_the_estop(self) -> None:
        client = self.serve(OVERLAY)
        self.assertEqual(self.move(client)["status"], "completed")
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertTrue(stopped["output"]["stopped"])
        self.assertEqual(stopped["output"]["stopped_position"],
                         {"x_um": 100.0, "y_um": 200.0, "z_um": 50.0})
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_stage_that_keeps_moving_leaves_the_stop_unreached_and_latched(self) -> None:
        # Model review: stopAll() returns nothing (ESP32StageManager.py:647-648); only two device position queries
        # that agree after it confirm the standstill, so a stage that keeps moving is never a completed stop.
        client = self.serve(OVERLAY, options={"keeps_moving": True})
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_position_query_is_refused_never_reported_as_a_position(self) -> None:
        # Model review: when the device query raises, getPosition() returns its cached _position
        # (ESP32StageManager.py:605-617), which holds the commanded target after a move (542-544).
        client = self.serve(OVERLAY, options={"query_fails": True})
        with self.assertRaises(MHSError) as raised:
            self.state(client)
        self.assertEqual(raised.exception.code, FAULTED)
        moved = self.move(client)
        self.assertEqual(moved["status"], "unknown", moved)
        self.assertEqual(moved["error"]["mhs_code"], UNKNOWN, moved)
        stopped = client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED, stopped)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)

    def test_the_estop_and_the_teardown_send_the_native_stop(self) -> None:
        # Model review: teardown stops all axes before the hardware factory closes the ESP32 client, because a
        # stage moving when its command stream breaks does not stop cleanly (agents.md:893-896).
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.estop("test")
        self.assertGreaterEqual(driver.native._stop_calls, 1)
        before = driver.native._stop_calls
        driver.close()
        self.assertEqual(driver.native._stop_calls, before + 1)


if __name__ == "__main__":
    unittest.main()
