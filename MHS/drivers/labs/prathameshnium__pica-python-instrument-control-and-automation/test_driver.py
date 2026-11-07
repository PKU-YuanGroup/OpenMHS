"""Acceptance run of the Cryo-con 34 package: the gate, plus cases for what is specific to this driver.

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


class CryoconCases(unittest.TestCase):
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
        before = self.state(client)["setpoint"]
        refused = self.configure(client, setpoint=10.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["setpoint"], before)

    def test_the_example_overlay_supplies_the_setpoint_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = self.configure(client, setpoint=10.0)
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(self.state(client)["setpoint"], 10.0)
        for value in (3.9, 400.1):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["setpoint"], 10.0)

    def test_the_controller_state_and_the_control_actions(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["input_units"], state["source_units"], state["loop_source"]), ("K", "K", "A"))
        self.assertFalse(state["control_engaged"])
        engaged = client.invoke("x-cap.prathameshnium.control_engage.v1", {}, **self.ids)
        self.assertEqual(engaged["status"], "completed")
        self.assertEqual(engaged["output"], {"engaged": True})
        self.assertTrue(self.state(client)["control_engaged"])
        stopped = client.invoke("x-cap.prathameshnium.control_stop.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"engaged": False})
        self.assertFalse(self.state(client)["control_engaged"])

    def test_the_estop_stops_the_loops_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.prathameshnium.control_engage.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["control_engaged"])
        refused = client.invoke("x-cap.prathameshnium.control_engage.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_enumeration_writes_are_bounded(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, loop_type="PID")["status"], "completed")
        self.assertEqual(self.configure(client, display_time_constant=2)["status"], "completed")
        self.assertEqual(self.state(client)["display_time_constant"], 2.0)
        self.assertEqual(self.configure(client, load=25)["status"], "completed")
        self.assertEqual(self.state(client)["load"], 25)
        for patch in ({"loop_type": "Bogus"}, {"load": 30}, {"display_time_constant": 3}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_example_overlay_narrows_the_power(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, max_power=40)["status"], "completed")
        self.assertEqual(self.state(client)["max_power"], 40.0)
        refused = self.configure(client, max_power=60)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["max_power"], 40.0)


if __name__ == "__main__":
    unittest.main()
