"""Acceptance run of the ISARA automounter package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class IsaraCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_initial_state_is_the_controller_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["status"], 0)
        self.assertEqual(state["position"], "SOAK")
        self.assertEqual((state["emergency_ok"], state["collision_ok"]), (True, True))
        self.assertEqual(state["next_port"], "")

    def test_selecting_a_port_prepares_the_native_mount_parameters(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.michel4j.select_mount_port.v1", {"port": "2A16"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"port": "2A16", "tool": 4, "puck": 2, "sample": 16})
        state = self.state(client)
        self.assertEqual((state["next_port"], state["tool"]), ("2A16", 4))

    def test_home_moves_the_controller_state_and_reports_it(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.michel4j.home.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"homed": True})
        self.assertEqual(self.state(client)["position"], "HOME")

    def test_the_estop_queues_panic_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.estop("test", **self.ids)["status"], "completed")
        refused = client.invoke("x-cap.michel4j.home.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
