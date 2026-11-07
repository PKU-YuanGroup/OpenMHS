"""Acceptance run of the pumpy package: the gate, plus cases for what is specific to this driver.

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


class PumpyCases(unittest.TestCase):
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

    def pump(self, client, payload):
        return client.invoke("cap.actuation.pump.v1", payload, **self.ids)

    def test_the_sourced_diameter_and_the_operator_required_writes(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, diameter=24)["status"], "completed")
        self.assertEqual(self.state(client)["diameter"], 24.0)
        refused = self.configure(client, diameter=40)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["diameter"], 24.0)
        for patch in ({"flowrate": 2000}, {"targetvolume": 100}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)

    def test_the_example_overlay_supplies_the_ranges_and_the_pump_action(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, flowrate=600)["status"], "completed")
        self.assertEqual(self.state(client)["flowrate"], 600.0)
        self.assertEqual(self.configure(client, targetvolume=250)["status"], "completed")
        self.assertEqual(self.state(client)["targetvolume"], 250.0)
        receipt = self.pump(client, {"flow_rate": 50, "direction": "forward", "volume": 500})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"dispensed_volume": 500.0})
        state = self.state(client)
        self.assertEqual(state["flowrate"], 3000.0)
        self.assertEqual(state["targetvolume"], 500.0)

    def test_the_safe_state_action_stops_the_pump(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.tomwphillips.stop_pump.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True})

    def test_the_estop_latches_the_pump_action(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        client.estop("test", **self.ids)
        refused = self.pump(client, {"flow_rate": 50, "direction": "forward", "volume": 500})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = self.configure(client, diameter=24)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
