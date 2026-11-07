"""Acceptance run of the ScopeMCP package: the gate, plus cases for this driver.

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


class ScopemcpCases(unittest.TestCase):
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

    def test_the_metadata_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["instrument_model"], "DS1102")                  # fake placeholder
        self.assertEqual(state["run_status"], "TRIG")                          # fake placeholder
        self.assertEqual(state["channel1_frequency_hz"], 1000.0)               # fake placeholder
        self.assertEqual(state["channel1_scale"], "1.00V")                     # fake placeholder
        self.assertEqual(state["channel1_coupling"], "DC")                     # fake placeholder
        self.assertEqual(state["channel1_offset_raw"], 0)                      # fake placeholder
        self.assertEqual(state["channel2_frequency_hz"], 500.0)                # fake placeholder
        self.assertEqual(state["channel2_scale"], "500mV")                     # fake placeholder

    def test_the_scale_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, channel1_scale="2V")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["channel1_scale"], "1.00V")        # untouched

    def test_the_example_overlay_supplies_the_scale_and_the_offset(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, channel1_scale="500mV")["status"], "completed")
        self.assertEqual(self.state(client)["channel1_scale"], "500mV")
        self.assertEqual(self.configure(client, channel1_offset_v=1.5)["status"], "completed")
        self.assertEqual(self.state(client)["channel1_offset_v"], 1.5)
        refused = self.configure(client, channel1_scale="5V")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.configure(client, channel1_offset_v=6.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_coupling_is_the_upstream_set(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel1_coupling="AC")["status"], "completed")
        self.assertEqual(self.state(client)["channel1_coupling"], "AC")
        refused = self.configure(client, channel1_coupling="XYZ")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_actions(self) -> None:
        client = self.serve()
        autoset = client.invoke("x-cap.kletternaut.autoset.v1", {}, **self.ids)
        self.assertEqual(autoset["status"], "completed")
        self.assertEqual(autoset["output"], {"channel1_scale": "2.00V", "channel1_coupling": "DC"})
        started = client.invoke("x-cap.kletternaut.run.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"run_status": "TRIG"})
        stopped = client.invoke("x-cap.kletternaut.stop_acquisition.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.kletternaut.run.v1", {}, **self.ids)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke("x-cap.kletternaut.run.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
