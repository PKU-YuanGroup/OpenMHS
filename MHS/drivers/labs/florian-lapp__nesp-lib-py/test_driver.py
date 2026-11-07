"""Acceptance run of the NESP syringe pump package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class NespPumpCases(unittest.TestCase):
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

    def invoke(self, client, capability_id):
        return client.invoke(capability_id, {}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_pump_reads_its_identity_and_settings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["model_number"], state["firmware_version"]), (1000, "3.928"))
        self.assertEqual((state["status"], state["running"]), ("STOPPED", False))
        self.assertEqual(state["syringe_diameter_mm"], 30.0)
        self.assertEqual(state["pumping_direction"], "INFUSE")
        self.assertEqual((state["pumping_volume_ml"], state["pumping_rate_ml_per_min"]), (1.0, 10.0))
        self.assertEqual((state["volume_infused_ml"], state["volume_withdrawn_ml"]), (0.0, 0.0))
        self.assertEqual(state["safe_mode_timeout_s"], 0)

    def test_the_syringe_diameter_is_bounded_by_the_class(self) -> None:
        client = self.serve()
        for value in (0.09, 80.01):
            refused = self.configure(client, syringe_diameter_mm=value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        for value in (0.1, 30.0, 80.0):
            self.assertEqual(self.configure(client, syringe_diameter_mm=value)["status"], "completed", value)
        self.assertEqual(self.state(client)["syringe_diameter_mm"], 80.0)

    def test_the_safe_mode_timeout_is_bounded_by_the_class(self) -> None:
        client = self.serve()
        for value in (-1, 256):
            refused = self.configure(client, safe_mode_timeout_s=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        for value in (0, 10, 255):
            self.assertEqual(self.configure(client, safe_mode_timeout_s=value)["status"], "completed", value)
        self.assertEqual(self.state(client)["safe_mode_timeout_s"], 255)

    def test_the_pumping_direction_is_one_of_the_two_members(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, pumping_direction="WITHDRAW")["status"], "completed")
        self.assertEqual(self.state(client)["pumping_direction"], "WITHDRAW")
        refused = self.configure(client, pumping_direction="SIDEWAYS")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["pumping_direction"], "WITHDRAW")

    def test_the_volume_and_the_rate_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"pumping_volume_ml": 2.0}, {"pumping_rate_ml_per_min": 5.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        self.assertEqual((self.state(client)["pumping_volume_ml"],
                          self.state(client)["pumping_rate_ml_per_min"]), (1.0, 10.0))

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, pumping_volume_ml=2.5, pumping_rate_ml_per_min=5.0)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["pumping_volume_ml"], 2.5)
        self.assertEqual(self.state(client)["pumping_rate_ml_per_min"], 5.0)
        for patch in ({"pumping_volume_ml": 0.05}, {"pumping_volume_ml": 10.5},
                      {"pumping_rate_ml_per_min": 0.05}, {"pumping_rate_ml_per_min": 30.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_actions_start_purge_and_stop_the_pump(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, pumping_direction="INFUSE", pumping_volume_ml=1.0, pumping_rate_ml_per_min=5.0)
        started = self.invoke(client, "x-cap.florian-lapp.run_pump.v1")
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"status": "INFUSING", "running": True})
        self.assertEqual((self.state(client)["status"], self.state(client)["running"]), ("INFUSING", True))
        stopped = self.invoke(client, "x-cap.florian-lapp.stop_pump.v1")
        self.assertEqual(stopped["output"], {"status": "STOPPED", "running": False})
        purged = self.invoke(client, "x-cap.florian-lapp.purge.v1")
        self.assertEqual(purged["output"], {"status": "PURGING", "running": True})
        self.assertTrue(self.state(client)["running"])

    def test_the_estop_stops_the_pump_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.florian-lapp.run_pump.v1")
        self.assertTrue(self.state(client)["running"])
        client.estop("test", **self.ids)
        self.assertEqual((self.state(client)["status"], self.state(client)["running"]), ("STOPPED", False))
        refused = self.invoke(client, "x-cap.florian-lapp.run_pump.v1")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
