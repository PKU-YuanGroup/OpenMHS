"""Acceptance run of the HXN beamline status monitor: the gate, plus cases specific to this package.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FIELDS = ("shutter_status", "beam_current", "beamline_enabled", "cryo_filling")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HxnBeamlineStatusCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_field_is_a_fresh_read_of_its_signal(self) -> None:
        client, fake = self.serve()
        state = self.state(client)
        self.assertEqual(sorted(state), sorted(FIELDS))
        self.assertEqual(state["shutter_status"], 1)                 # placeholder
        self.assertEqual(state["beam_current"], 500.0)               # placeholder
        self.assertEqual(state["beamline_enabled"], 1)               # placeholder
        self.assertEqual(state["cryo_filling"], 0)                   # placeholder
        for name in FIELDS:
            calls = getattr(fake, name)._use_monitor
            self.assertTrue(calls, name)
            self.assertEqual(set(calls), {False}, f"{name} must be read with use_monitor=False")

    def test_read_channels_without_fields_returns_every_channel(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke("cap.sensing.read.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"],
                         {"shutter_status": 1, "beam_current": 500.0, "beamline_enabled": 1,
                          "cryo_filling": 0})                            # placeholder
        self.assertIn("sampled_at", receipt["output"])

    def test_read_channels_selects_a_subset(self) -> None:
        client, fake = self.serve()
        before = len(fake.beam_current._use_monitor)
        receipt = client.invoke("cap.sensing.read.v1", {"fields": ["beam_current"]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {"beam_current": 500.0})  # placeholder
        self.assertGreater(len(fake.beam_current._use_monitor), before)
        self.assertNotIn("shutter_status", receipt["output"]["values"])

    def test_an_unknown_channel_is_refused(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke("cap.sensing.read.v1", {"fields": ["not_a_channel"]}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)

    def test_the_monitor_offers_no_write(self) -> None:
        client, _fake = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"beam_current": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.UNKNOWN")

    def test_an_estop_keeps_the_read_only_endpoint_available(self) -> None:
        # The device has no actuator and no @estop: the runtime latches effectful work, while an observational
        # read capability stays available.  No physical stop is claimed.
        client, _fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        receipt = client.invoke("cap.sensing.read.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"]["beam_current"], 500.0)  # placeholder
        self.assertEqual(self.state(client)["beam_current"], 500.0)  # placeholder


if __name__ == "__main__":
    unittest.main()
