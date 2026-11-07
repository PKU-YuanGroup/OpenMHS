"""Acceptance run of the WIL Pycro stage package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StageCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_travel_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, x_position=10)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["x_position"], 0)          # placeholder start, untouched

    def test_the_example_overlay_supplies_the_travel(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, x_position=12)["status"], "completed")
        self.assertEqual(self.configure(client, y_position=34)["status"], "completed")
        self.assertEqual(self.configure(client, z_position=56)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["x_position"], state["y_position"], state["z_position"]), (12, 34, 56))
        for patch in ({"x_position": 1001}, {"y_position": -1}, {"z_position": 2001}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual((self.state(client)["x_position"], self.state(client)["y_position"],
                          self.state(client)["z_position"]), (12, 34, 56))

    def test_the_focus_action_moves_the_focus_axis(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("cap.imaging.focus.v1", {"method": "manual", "target_z": 250}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"focused": False, "z_um": 250.0})
        query = client.invoke("cap.imaging.focus.v1", {"method": "none"}, **self.ids)
        self.assertEqual(query["status"], "completed")
        self.assertEqual(query["output"]["z_um"], 250.0)
        refused = client.invoke("cap.imaging.focus.v1", {"method": "manual", "target_z": 2001}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["z_position"], 250)

    def test_a_fractional_focus_target_reads_back_truncated(self) -> None:
        # Upstream passes z_pos unchanged to core.set_position and truncates the read (stage.py:258, 291).
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = client.invoke("cap.imaging.focus.v1", {"method": "manual", "target_z": 250.7}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["z_um"], 250.0)

    def test_manual_without_a_target_is_refused(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = client.invoke("cap.imaging.focus.v1", {"method": "manual"}, **self.ids)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], PRECONDITION)

    def test_the_estop_sends_nothing_and_does_not_claim_a_safe_state(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.set_z_position(125)
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("test")
        self.assertEqual(caught.exception.code, UNREACHED)
        # No RESET reached the backend: the reset_stage stand-in would read the origin back as 0.
        self.assertEqual(driver.native.get_z_position(), 125)

    def test_the_estop_latches_and_reports_the_safe_state_unreached(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, z_position=125)["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertEqual(self.state(client)["z_position"], 125)         # nothing was sent, nothing reset
        refused = client.invoke("cap.imaging.focus.v1", {"method": "none"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = self.configure(client, z_position=75)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["z_position"], 125)


if __name__ == "__main__":
    unittest.main()
