"""Acceptance run of the APT piezo package: the gate, plus cases for what is specific to this driver.

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
MOVE = "x-cap.solgaardlab.move_piezo.v1"
ZERO = "x-cap.solgaardlab.zero_piezo.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AptPiezoCases(unittest.TestCase):
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

    def move(self, client, position_um):
        return client.invoke(MOVE, {"position_um": position_um}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_commanded_state_starts_at_zero_in_closed_loop(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 0.0)
        self.assertIs(state["closed_loop"], True)
        self.assertEqual(state["max_travel"], 30.0)      # the fake's placeholder, not a stage fact

    def test_the_position_write_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, position=1.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)

    def test_the_move_input_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client, 2.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 0.0)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, position=1.25)["status"], "completed")
        self.assertEqual(self.state(client)["position"], 1.25)
        for value in (-0.5, 30.5):
            refused = self.configure(client, position=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["position"], 1.25)

    def test_the_move_and_zero_actions_are_observable(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client, 2.5)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"position_um": 2.5})
        self.assertEqual(self.state(client)["position"], 2.5)
        zeroed = client.invoke(ZERO, {}, **self.ids)
        self.assertEqual(zeroed["status"], "completed")
        self.assertEqual(zeroed["output"], {"position_um": 0.0})
        self.assertEqual(self.state(client)["position"], 0.0)

    def test_the_closed_loop_write_is_observable(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, closed_loop=False)["status"], "completed")
        self.assertIs(self.state(client)["closed_loop"], False)
        self.assertEqual(self.configure(client, closed_loop=True)["status"], "completed")
        self.assertIs(self.state(client)["closed_loop"], True)

    def test_the_estop_zeroes_the_piezo_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.move(client, 3.0)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["position"], 0.0)
        refused = self.move(client, 3.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = self.configure(client, closed_loop=False)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
