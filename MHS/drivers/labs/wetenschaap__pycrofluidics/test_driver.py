"""Acceptance run of the Elveflow OB1 package: the gate, plus cases for what is specific to this driver.

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


class ElveflowOB1Cases(unittest.TestCase):
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

    def test_the_pressure_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["pressure_1"], state["flow_1"], state["remote"]), (0.0, 0.0, False))
        refused = self.configure(client, pressure_1=50)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["pressure_1"], 0.0)

    def test_the_example_overlay_supplies_the_pressure_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, pressure_1=50)["status"], "completed")
        self.assertEqual(self.state(client)["pressure_1"], 50.0)
        for value in (-1, 201):
            refused = self.configure(client, pressure_1=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["pressure_1"], 50.0)

    def test_the_read_actions_and_their_channel_bound(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, pressure_1=25)["status"], "completed")
        pressure = client.invoke("x-cap.wetenschaap.read_pressure.v1", {"channel": 1}, **self.ids)
        self.assertEqual(pressure["output"], {"channel": 1, "pressure": 25.0})
        flow = client.invoke("x-cap.wetenschaap.read_flow.v1", {"channel": 1}, **self.ids)
        self.assertEqual(flow["output"], {"channel": 1, "flow_rate": 0.0})
        for channel in (0, 5):
            refused = client.invoke("x-cap.wetenschaap.read_pressure.v1", {"channel": channel}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, channel)

    def test_the_remote_loop_and_the_safe_state(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, pressure_1=50)["status"], "completed")
        started = client.invoke("x-cap.wetenschaap.start_remote.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"running": True})
        self.assertTrue(self.state(client)["remote"])
        stopped = client.invoke("x-cap.wetenschaap.stop_remote.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"stopped": True})
        state = self.state(client)
        self.assertFalse(state["remote"])
        self.assertEqual(state["pressure_1"], 0.0)

    def test_the_estop_zeroes_the_pressures_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, pressure_1=50)["status"], "completed")
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        self.assertEqual(self.state(client)["pressure_1"], 0.0)
        refused = self.configure(client, pressure_1=50)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = client.invoke("x-cap.wetenschaap.start_remote.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
