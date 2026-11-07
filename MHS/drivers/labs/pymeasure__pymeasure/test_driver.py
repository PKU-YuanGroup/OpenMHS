"""Acceptance run of the DMM6500 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Dmm6500Cases(unittest.TestCase):
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

    def test_the_state_and_the_nplc_write(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["mode"], state["digits"]), ("voltage", 6))
        self.assertEqual(state["nplc"], 1.0)
        done = self.configure(client, nplc=2.5)
        self.assertEqual(done["status"], "completed")
        self.assertAlmostEqual(self.state(client)["nplc"], 2.5)             # the fake stored it
        for value in (0.0004, 15.1):
            refused = self.configure(client, nplc=value)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertAlmostEqual(self.state(client)["nplc"], 2.5)             # untouched by the refusals

    def test_the_measure_actions(self) -> None:
        client = self.serve()
        dc = client.invoke("cap.measure.voltage.v1", {"dc": True}, **self.ids)
        self.assertEqual(dc["status"], "completed")
        self.assertAlmostEqual(dc["output"]["voltage"], 5.0)
        self.assertIn("sampled_at", dc["output"])
        self.assertEqual(self.state(client)["mode"], "voltage")
        ac = client.invoke("cap.measure.voltage.v1", {"dc": False}, **self.ids)
        self.assertEqual(ac["status"], "completed")
        self.assertEqual(self.state(client)["mode"], "voltage ac")
        current = client.invoke("cap.measure.current.v1", {}, **self.ids)
        self.assertEqual(current["status"], "completed")
        self.assertAlmostEqual(current["output"]["current"], 0.01)
        self.assertEqual(self.state(client)["mode"], "current")
        resistance = client.invoke("cap.measure.resistance.v1", {"four_wire": True}, **self.ids)
        self.assertEqual(resistance["status"], "completed")
        self.assertTrue(resistance["output"]["four_wire"])
        self.assertEqual(self.state(client)["mode"], "resistance 4W")

    def test_the_estop_aborts_the_scan_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        refused = self.configure(client, nplc=2.0)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
