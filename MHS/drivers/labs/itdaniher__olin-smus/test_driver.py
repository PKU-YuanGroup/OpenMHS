"""Acceptance run of the Olin SMU package: the gate, plus cases for what is specific to this driver.

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


class OlinSMUCases(unittest.TestCase):
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

    def test_the_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["source_voltage"], state["source_current"]), (0.0, 0.0))
        self.assertEqual(state["source_mode"], "current")
        for patch in ({"source_voltage": 1.0}, {"source_current": 0.01}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["source_mode"], "current")

    def test_the_example_overlay_supplies_the_envelope(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, source_voltage=1.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["source_voltage"], state["source_mode"]), (1.0, "voltage"))
        self.assertEqual(state["measured_voltage"], 1.0)
        self.assertEqual(self.configure(client, source_current=0.01)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["source_current"], state["source_mode"]), (0.01, "current"))
        self.assertEqual(state["measured_current"], 0.01)
        for patch in ({"source_voltage": 5.01}, {"source_voltage": -5.01},
                      {"source_current": 0.051}, {"source_current": -0.051}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        state = self.state(client)
        self.assertEqual((state["source_voltage"], state["source_current"]), (1.0, 0.01))

    def test_the_measured_values_and_their_third_value(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        state = self.state(client)
        self.assertEqual((state["measured_voltage"], state["measured_current"], state["mod_voltage"]),
                         (0.0, 0.0, 0.0))
        self.configure(client, source_voltage=2.5)
        state = self.state(client)
        self.assertEqual((state["measured_voltage"], state["measured_current"]), (2.5, 0.0))
        self.configure(client, source_current=0.02)
        state = self.state(client)
        self.assertEqual((state["measured_voltage"], state["measured_current"]), (0.0, 0.02))

    def test_the_safe_state_action_zeroes_the_source(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, source_current=0.01)
        self.assertEqual(self.state(client)["source_current"], 0.01)
        receipt = client.invoke("x-cap.itdaniher.source_off.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"source_current": 0.0})
        state = self.state(client)
        self.assertEqual((state["source_current"], state["source_mode"]), (0.0, "current"))

    def test_the_estop_zeroes_the_source_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, source_voltage=1.5)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual((state["source_current"], state["source_mode"]), (0.0, "current"))
        refused = self.configure(client, source_current=0.01)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
