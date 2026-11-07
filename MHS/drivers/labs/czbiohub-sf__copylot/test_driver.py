"""Acceptance run of the Vortran laser package: the gate, plus cases for what is specific to this driver.

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


class VortranCases(unittest.TestCase):
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

    def test_the_reads_come_from_the_upstream_members(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["emission"], False)
        self.assertEqual(state["power"], 1.0)
        self.assertEqual(state["maximum_power"], 10.0)
        self.assertEqual(state["emission_delay"], True)
        self.assertEqual(state["pulse_mode"], False)
        self.assertEqual(state["fault_code"], 0)
        self.assertEqual(state["fault_description"], "NO FAULT")

    def test_the_power_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, power=2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["power"], 1.0)                 # untouched by the refused write

    def test_the_example_overlay_supplies_the_power_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, power=2.0)["status"], "completed")
        self.assertEqual(self.state(client)["power"], 2.0)
        self.assertEqual(self.configure(client, power=8.0)["status"], "completed")
        for value in (8.01, 9.0):
            refused = self.configure(client, power=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["power"], 8.0)

    def test_the_flag_writes_reach_the_device(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, emission_delay=False)["status"], "completed")
        self.assertEqual(self.configure(client, pulse_mode=True)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["emission_delay"], state["pulse_mode"]), (False, True))

    def test_the_emission_actions_and_the_estop(self) -> None:
        client = self.serve()
        on = client.invoke("x-cap.czbiohub-sf.laser_emission_on.v1", {}, **self.ids)
        self.assertEqual(on["output"], {"emission": True})
        self.assertTrue(self.state(client)["emission"])
        off = client.invoke("x-cap.czbiohub-sf.laser_emission_off.v1", {}, **self.ids)
        self.assertEqual(off["output"], {"emission": False})
        self.assertFalse(self.state(client)["emission"])
        client.invoke("x-cap.czbiohub-sf.laser_emission_on.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["emission"])                    # the e-stop switched the emission off
        refused = client.invoke("x-cap.czbiohub-sf.laser_emission_on.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)               # the latch holds


if __name__ == "__main__":
    unittest.main()
