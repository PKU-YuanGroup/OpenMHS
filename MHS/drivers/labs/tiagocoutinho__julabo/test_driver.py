"""Acceptance run of the Julabo package: the gate, plus cases for what is specific to this driver.

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


class JulaboCases(unittest.TestCase):
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

    def test_the_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=37)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["setpoint"], 30.0)                  # the simulator's default, untouched

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=36.666)["status"], "completed")
        self.assertEqual(self.state(client)["setpoint"], 36.67)                 # two decimals, as the upstream encoder
        for value in (14.99, 60.01):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["setpoint"], 36.67)

    def test_the_reads_and_the_circulation(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["bath_temperature"], state["external_temperature"]), (29.45, 28.22))
        self.assertEqual((state["running"], state["active_set_point_channel"]), (False, 1))
        started = client.invoke("x-cap.tiagocoutinho.start_circulation.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"running": True})
        self.assertTrue(self.state(client)["running"])
        stopped = client.invoke("x-cap.tiagocoutinho.stop_circulation.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"running": False})

    def test_the_estop_stops_the_circulation_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.tiagocoutinho.start_circulation.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = client.invoke("x-cap.tiagocoutinho.start_circulation.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
