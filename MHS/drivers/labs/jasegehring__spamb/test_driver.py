"""Acceptance run of the SPAMB syringe-pump package: the gate, plus cases for what is specific to this driver.

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


class SpambPumpCases(unittest.TestCase):
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

    def test_a_numeric_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, flow_rate=2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["flow_rate"], 1.0)          # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, flow_rate=3.0)["status"], "completed")
        self.assertEqual(self.state(client)["flow_rate"], 3.0)
        refused = self.configure(client, flow_rate=0.05)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = self.configure(client, direction="sideways")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["flow_rate"], 3.0)
        self.assertEqual(self.state(client)["direction"], "withdraw")

    def test_the_catalogue_action_converts_units_and_direction(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("cap.actuation.pump.v1",
                                {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"dispensed_volume": 0.0})
        state = self.state(client)
        self.assertTrue(state["running"])
        self.assertEqual(state["direction"], "infuse")                  # forward maps to the upstream word
        self.assertAlmostEqual(state["flow_rate"], 3.0)                 # 50 uL/s = 3.0 mL/min
        self.assertAlmostEqual(state["target_volume"], 0.5)             # 500 uL = 0.5 mL
        stopped = client.invoke("x-cap.jasegehring.stop_pump.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"running": False})
        self.assertFalse(self.state(client)["running"])

    def test_the_estop_stops_the_pump_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.invoke("cap.actuation.pump.v1", {"flow_rate": 50, "direction": "reverse", "volume": 500},
                      **self.ids)
        self.assertTrue(self.state(client)["running"])
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = client.invoke("cap.actuation.pump.v1",
                                {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
