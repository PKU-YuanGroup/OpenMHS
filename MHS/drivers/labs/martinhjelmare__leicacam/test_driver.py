"""Acceptance run of the leicacam package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PREFIX = "/cli:python-leicacam /app:matrix"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LeicaCAMCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_stage_read_is_the_getinfo_reply(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["stage_information"], PREFIX + " /cmd:getinfo /dev:stage")

    def test_every_scan_action_reports_the_cam_reply(self) -> None:
        client = self.serve()
        for capability_id, word in (
            ("x-cap.martinhjelmare.start_matrix_scan.v1", "/cmd:startscan"),
            ("x-cap.martinhjelmare.stop_matrix_scan.v1", "/cmd:stopscan"),
            ("x-cap.martinhjelmare.pause_matrix_scan.v1", "/cmd:pausescan"),
            ("x-cap.martinhjelmare.autofocus_scan.v1", "/cmd:autofocusscan"),
            ("x-cap.martinhjelmare.enable_all_scan_fields.v1", "/cmd:enableall /value:true"),
            ("x-cap.martinhjelmare.disable_all_scan_fields.v1", "/cmd:enableall /value:false"),
        ):
            receipt = self.invoke(client, capability_id)
            self.assertEqual(receipt["status"], "completed", (capability_id, receipt))
            self.assertTrue(receipt["output"]["acknowledged"], capability_id)
            self.assertIn(word, receipt["output"]["reply"], capability_id)

    def test_the_field_actions_wait_for_the_site(self) -> None:
        client = self.serve()
        fields = {"slide": 1, "wellx": 2, "welly": 3, "fieldx": 1, "fieldy": 2}
        for capability_id in ("x-cap.martinhjelmare.enable_scan_field.v1",
                              "x-cap.martinhjelmare.disable_scan_field.v1"):
            refused = self.invoke(client, capability_id, fields)
            self.assertEqual(refused["status"], "rejected", (capability_id, refused))
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)

    def test_the_example_overlay_supplies_the_field_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = self.invoke(client, "x-cap.martinhjelmare.enable_scan_field.v1",
                              {"slide": 1, "wellx": 2, "welly": 3, "fieldx": 1, "fieldy": 2})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIn("/cmd:enable", receipt["output"]["reply"])
        self.assertIn("/slide:1", receipt["output"]["reply"])
        self.assertIn("/wellx:2", receipt["output"]["reply"])
        self.assertIn("/value:true", receipt["output"]["reply"])
        refused = self.invoke(client, "x-cap.martinhjelmare.enable_scan_field.v1",
                              {"slide": 9, "wellx": 2, "welly": 3, "fieldx": 1, "fieldy": 2})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_safe_state_action_sends_stopscan_and_waits_only_briefly(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        waits = []
        echo = driver.native.wait_for

        def recording_wait_for(cmd, value=None, timeout=60):
            waits.append(timeout)
            return echo(cmd, value, timeout)

        def stop_scan():
            raise AssertionError("CAM.stop_scan waits up to 60 minutes for the reply")

        driver.native.wait_for, driver.native.stop_scan = recording_wait_for, stop_scan
        output = driver.stop_matrix_scan()
        self.assertTrue(output["acknowledged"], output)
        self.assertIn("/cmd:stopscan", output["reply"])
        self.assertEqual(len(waits), 1)
        self.assertLessEqual(waits[0] * 60, 10, "at most 10 s, in the minutes CAM.wait_for counts")

    def test_the_estop_stops_the_scan_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.invoke(client, "x-cap.martinhjelmare.start_matrix_scan.v1")["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = self.invoke(client, "x-cap.martinhjelmare.start_matrix_scan.v1")
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
