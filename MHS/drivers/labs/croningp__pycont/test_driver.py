"""Acceptance run of the pycont package: the gate, plus cases for what is specific to this driver.

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
PUMP = "cap.actuation.pump.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PycontCases(unittest.TestCase):
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

    def test_the_initial_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["volume"], 2500.0)                 # fake test data: 2.5 mL
        self.assertEqual(state["plunger_position"], 12000)        # 2.5 mL at the fake's 4800 steps/mL
        self.assertEqual(state["valve_position"], "I")
        self.assertEqual(state["top_velocity"], 6000)
        self.assertEqual(state["default_top_velocity"], 6000)
        self.assertEqual((state["busy"], state["initialized"]), (False, False))

    def test_the_pump_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = client.invoke(PUMP, {"direction": "forward", "flow_rate": 50, "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["volume"], 2500.0)

    def test_the_example_overlay_runs_the_pump_both_ways(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        forward = client.invoke(PUMP, {"direction": "forward", "flow_rate": 50, "volume": 500}, **self.ids)
        self.assertEqual(forward["status"], "completed", forward)
        self.assertAlmostEqual(forward["output"]["dispensed_volume"], 500.0, places=6)
        self.assertAlmostEqual(self.state(client)["volume"], 2000.0, places=6)
        reverse = client.invoke(PUMP, {"direction": "reverse", "flow_rate": 50, "volume": 500}, **self.ids)
        self.assertEqual(reverse["status"], "completed", reverse)
        self.assertAlmostEqual(reverse["output"]["dispensed_volume"], 500.0, places=6)
        self.assertAlmostEqual(self.state(client)["volume"], 2500.0, places=6)

    def test_the_valve_write_and_its_allowed_set(self) -> None:
        client = self.serve()
        written = client.write("main", {"valve_position": "O"}, **self.ids)
        self.assertEqual(written["status"], "completed", written)
        self.assertEqual(self.state(client)["valve_position"], "O")
        refused = client.write("main", {"valve_position": "Z"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["valve_position"], "O")

    def test_the_estop_latches_and_refuses_the_pump(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        terminated = client.invoke("x-cap.croningp.terminate.v1", {}, **self.ids)
        self.assertEqual(terminated["status"], "completed", terminated)
        client.estop("test", **self.ids)
        refused = client.invoke(PUMP, {"direction": "forward", "flow_rate": 50, "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
