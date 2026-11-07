"""Acceptance run of the Festo pressure-over-liquid package: the gate, plus cases specific to this driver.

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


class FestoFluidControlCases(unittest.TestCase):
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

    def command(self, client, capability_id, **payload):
        return client.invoke(capability_id, payload, **self.ids)

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["channels"], [1, 2])
        self.assertEqual(state["liquid_classes"], ["water", "ethylene-glycol10%"])
        self.assertEqual(state["fluid_status"], 0)
        self.assertEqual(state["pressure"], 0.0)

    def test_the_pressure_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, pressure=10)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["pressure"], 0.0)

    def test_the_example_overlay_supplies_the_pressure_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = self.configure(client, pressure=10)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["pressure"], 10.0)
        refused = self.configure(client, pressure=301)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["pressure"], 10.0)

    def test_aspirate_dispense_and_mix(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        aspirated = self.command(client, "x-cap.festo-se.aspirate.v1",
                                 channel=1, volume=10.0, liquid_class="water")
        self.assertEqual(aspirated["status"], "completed")
        self.assertEqual(aspirated["output"], {"aspirated_volume": 10.0, "channel": 1})
        dispensed = self.command(client, "x-cap.festo-se.dispense.v1",
                                 channel=2, volume=20.0, liquid_class="water")
        self.assertEqual(dispensed["status"], "completed")
        self.assertEqual(dispensed["output"], {"dispensed_volume": 20.0, "channel": 2})
        mixed = self.command(client, "x-cap.festo-se.mix.v1",
                             channel=1, volume=5.0, liquid_class="water", cycles=2)
        self.assertEqual(mixed["status"], "completed")
        self.assertEqual(mixed["output"], {"cycles": 2, "volume": 5.0})
        self.assertEqual(self.state(client)["fluid_status"], 0)

    def test_the_safe_state_action_releases_the_pressure(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, pressure=10)
        stopped = self.command(client, "x-cap.festo-se.deactivate.v1")
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"pressure": 0.0})
        self.assertEqual(self.state(client)["pressure"], 0.0)

    def test_the_estop_releases_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, pressure=10)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["pressure"], 0.0)
        refused = self.command(client, "x-cap.festo-se.aspirate.v1",
                               channel=1, volume=10.0, liquid_class="water")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
