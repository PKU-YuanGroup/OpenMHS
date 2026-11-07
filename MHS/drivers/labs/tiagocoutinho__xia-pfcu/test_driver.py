"""Acceptance run of the XIA PFCU package: the gate, plus cases for what is specific to this driver.

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


class XiaPfcuCases(unittest.TestCase):
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

    def shutter(self, client, state):
        return client.invoke("cap.optics.shutter.v1", {"state": state}, **self.ids)

    def test_the_reported_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["filter_a"], state["filter_b"], state["filter_c"], state["filter_d"]),
                         ("out", "out", "out", "out"))
        self.assertEqual((state["decimation"], state["shutter_enabled"], state["shutter_state"]),
                         (1, True, "closed"))
        self.assertEqual((state["remote_control_enabled"], state["remote_control_only"]), (True, False))
        self.assertTrue(state["identity"].startswith("%PFCU"))

    def test_filters_and_decimation_reach_the_fake(self) -> None:
        client = self.serve()
        applied = self.configure(client, filter_a="in", filter_c="in", decimation=100)
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["filter_a"], state["filter_b"], state["filter_c"], state["filter_d"]),
                         ("in", "out", "in", "out"))
        self.assertEqual(state["decimation"], 100)
        for patch in ({"decimation": 0}, {"decimation": 65536}, {"filter_a": "half-in"}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.state(client)["decimation"], 100)

    def test_the_shutter_opens_and_closes(self) -> None:
        client = self.serve()
        opened = self.shutter(client, "open")
        self.assertEqual(opened["status"], "completed")
        self.assertEqual(opened["output"], {"state": "open"})
        self.assertEqual(self.state(client)["shutter_state"], "open")
        closed = self.shutter(client, "closed")
        self.assertEqual(closed["output"], {"state": "closed"})
        self.assertEqual(self.state(client)["shutter_state"], "closed")

    def test_the_exposure_waits_for_the_site_and_then_runs(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.tiagocoutinho.start_exposure.v1", {"duration_s": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        client = self.serve(str(HERE / "site-limits.example.json"))
        started = client.invoke("x-cap.tiagocoutinho.start_exposure.v1", {"duration_s": 1.0}, **self.ids)
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"duration_s": 1.0})
        self.assertEqual(self.state(client)["shutter_state"], "open")

    def test_the_estop_closes_the_shutter_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.shutter(client, "open")["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["shutter_state"], "closed")
        refused = self.shutter(client, "open")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
