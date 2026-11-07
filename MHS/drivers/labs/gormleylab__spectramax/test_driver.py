"""Acceptance run of the SpectraMax package: the gate, plus cases for what is specific to this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SpectramaxCases(unittest.TestCase):
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

    def setpoint(self, client, value):
        return client.invoke("x-cap.gormleylab.set_incubator_temperature.v1",
                             {"target_temperature": value}, **self.ids)

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["instrument_status"], "IDLE")                     # placeholder of the fake
        self.assertEqual(state["plate_data"].split("\t")[0], "0.101")            # placeholder of the fake

    def test_the_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.setpoint(client, 37)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = self.setpoint(client, 37)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"], {"setpoint": 37})
        refused = self.setpoint(client, 38)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.setpoint(client, 0)["status"], "completed")        # 0 turns the incubator off

    def test_the_uvvis_read_reports_the_result_paths(self) -> None:
        client = self.serve()
        receipt = client.invoke(
            "x-cap.gormleylab.uvvis_read.v1",
            {"method": "method.spr", "results": "results/run1"},
            **self.ids,
        )
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {
            "sda_path": "results/run1.sda",
            "csv_path": "results/run1.csv",
            "xml_path": "results/run1.xml",
        })

    def test_the_estop_latches_and_refuses_the_next_read(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(
            "x-cap.gormleylab.uvvis_read.v1",
            {"method": "method.spr", "results": "results/run1"},
            **self.ids,
        )["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke(
            "x-cap.gormleylab.uvvis_read.v1",
            {"method": "method.spr", "results": "results/run2"},
            **self.ids,
        )
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertIn("plate_data", self.state(client))


if __name__ == "__main__":
    unittest.main()
