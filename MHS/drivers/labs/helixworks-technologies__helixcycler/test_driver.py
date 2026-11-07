"""Acceptance run of the HelixCycler package: the gate, plus cases for what is specific to this driver.

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


class HelixCyclerCases(unittest.TestCase):
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

    def test_the_reads_are_the_fake_start_values(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["lid_temperature"], 25.0)
        self.assertEqual(state["plate_temperature"], 24.5)
        self.assertEqual(state["plate_hold_remaining"], "0")

    def test_the_lid_range_is_enforced_and_the_write_reaches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, lid_setpoint=90)["status"], "completed")
        self.assertEqual(self.state(client)["lid_setpoint"], 90)
        for value in (36.9, 105.1):
            refused = self.configure(client, lid_setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["lid_setpoint"], 90)

    def test_the_catalogue_action_sets_the_plate_target(self) -> None:
        client = self.serve()
        done = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 60}, **self.ids)
        self.assertEqual(done["status"], "completed")
        self.assertEqual(done["output"], {"setpoint": 60})
        refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 100}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_shake_speed_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, shake_speed=500)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_supplies_the_shake_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, shake_speed=500)["status"], "completed")
        self.assertEqual(self.state(client)["shake_speed"], 500)
        for value in (199, 3001):
            refused = self.configure(client, shake_speed=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["shake_speed"], 500)

    def test_the_lid_actions_report_their_native_command(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.helixworks-technologies.open_lid.v1", {}, **self.ids)["output"],
                         {"opened": True})
        self.assertEqual(client.invoke("x-cap.helixworks-technologies.close_lid.v1", {}, **self.ids)["output"],
                         {"closed": True})

    def test_the_estop_deactivates_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, lid_setpoint=95)["status"], "completed")
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "completed")
        self.assertEqual(estop["output"]["estop"], "engaged")
        refused = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": 60}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
