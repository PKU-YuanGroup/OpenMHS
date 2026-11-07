"""Acceptance run of the Nikon package: the gate, plus cases for what is specific to this driver.

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


class NikonCases(unittest.TestCase):
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

    def test_the_initial_state_is_the_fake_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["firmware_version"], "1.2.3")
        self.assertEqual((state["x"], state["y"], state["z"]), (1234.5, 678.9, 3456.78))
        self.assertEqual((state["condenser"], state["dia"], state["filter"]), (2, 0.5, 1))
        self.assertEqual((state["light"], state["shutter"]), (False, False))
        self.assertEqual((state["objective"], state["optical_path"], state["zoom"]), (3, 0, 1))

    def test_the_stage_waits_for_the_site(self) -> None:
        client = self.serve()
        for field in ("x", "y", "z"):
            refused = self.configure(client, **{field: 0.0})
            self.assertEqual(refused["status"], "rejected", field)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, field)
        self.assertEqual(self.state(client)["x"], 1234.5)

    def test_the_example_overlay_supplies_the_stage_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, x=0.0, y=100.0, z=-100.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["x"], state["y"], state["z"]), (0.0, 100.0, -100.0))
        for patch in ({"x": 10001.0}, {"y": -10001.0}, {"z": 10001.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        self.assertEqual((self.state(client)["x"], self.state(client)["y"]), (0.0, 100.0))

    def test_the_optics_writes_reach_the_state(self) -> None:
        client = self.serve()
        applied = {"condenser": 3, "dia": 0.25, "filter": 2, "light": True,
                   "objective": 4, "optical_path": 2, "shutter": True}
        self.assertEqual(self.configure(client, **applied)["status"], "completed")
        state = self.state(client)
        for name, value in applied.items():
            self.assertEqual(state[name], value, name)
        for patch in ({"condenser": 7}, {"filter": 6}, {"objective": 6}, {"optical_path": 4}, {"dia": 1.5}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)
        after = self.state(client)
        for name, value in applied.items():
            self.assertEqual(after[name], value, name)

    def test_the_estop_disables_the_light_and_shutter(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, light=True, shutter=True)["status"], "completed")
        self.assertEqual((self.state(client)["light"], self.state(client)["shutter"]), (True, True))
        client.estop("test", **self.ids)
        self.assertEqual((self.state(client)["light"], self.state(client)["shutter"]), (False, False))
        refused = self.configure(client, light=True)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
