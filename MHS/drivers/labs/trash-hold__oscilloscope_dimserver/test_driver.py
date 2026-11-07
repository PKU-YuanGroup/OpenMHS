"""Acceptance run of the TDS3054C package: the gate, plus cases for what is specific to this driver.

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
SINGLE = "x-cap.trash-hold.single_acquisition.v1"
STOP = "x-cap.trash-hold.stop_acquisition.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TDS3054CCases(unittest.TestCase):
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

    def test_the_initial_state_comes_from_the_select_query(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["channel"], 1)
        self.assertTrue(state["channel_enabled"])
        self.assertAlmostEqual(state["horizontal_increment"], 2.5e-07)   # the fake's placeholder reply

    def test_the_channel_settings_reach_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel=3)["status"], "completed")
        self.assertEqual(self.state(client)["channel"], 3)
        self.assertEqual(self.configure(client, channel_enabled=False)["status"], "completed")
        self.assertFalse(self.state(client)["channel_enabled"])
        self.assertEqual(self.configure(client, channel_enabled=True)["status"], "completed")
        self.assertTrue(self.state(client)["channel_enabled"])

    def test_the_sourced_bounds_are_enforced(self) -> None:
        client = self.serve()
        for patch in ({"channel": 0}, {"channel": 5}, {"trigger_channel": 5},
                      {"trigger_slope": "BOTH"}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual(self.configure(client, trigger_channel=4)["status"], "completed")
        self.assertEqual(self.configure(client, trigger_slope="FALL")["status"], "completed")
        self.assertEqual(self.state(client)["trigger_slope"], "FALL")

    def test_an_unbounded_setting_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, vertical_scale=1.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertNotIn("vertical_scale", self.state(client))

    def test_the_example_overlay_supplies_a_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, vertical_scale=1.0)["status"], "completed")
        refused = self.configure(client, vertical_scale=1000.0)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["vertical_scale"], 1.0)

    def test_the_actions_and_the_estop(self) -> None:
        client = self.serve()
        acquired = client.invoke(SINGLE, {}, **self.ids)
        self.assertEqual(acquired["status"], "completed")
        self.assertEqual(acquired["output"], {"acquired": True})
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})
        client.estop("test", **self.ids)
        refused = self.configure(client, channel=2)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
