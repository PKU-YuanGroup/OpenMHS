"""Acceptance run of the Newport ESP 301 package: the gate, plus cases for what is specific to this driver.

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


class Esp301Cases(unittest.TestCase):
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

    def test_the_position_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, target_position=20.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)        # the simulator's placeholder start, untouched

    def test_the_example_overlay_supplies_a_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, target_position=20.0)["status"], "completed")
        self.assertEqual(self.state(client)["position"], 20.0)
        for value in (-0.1, 20.1):
            refused = self.configure(client, target_position=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["position"], 20.0)

    def test_the_position_is_read_and_the_reset_runs(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.configure(client, target_position=2.5)
        self.assertEqual(self.state(client)["position"], 2.5)
        self.assertEqual(self.state(client)["last_error"], 0.0)
        reset = client.invoke("x-cap.hrosiak.reset_axis.v1", {}, **self.ids)
        self.assertEqual(reset["output"], {"reset": True})

    def test_the_estop_latches_the_position_write(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, target_position=2.5)["status"], "completed")
        client.estop("test", **self.ids)
        refused = self.configure(client, target_position=3.5)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
