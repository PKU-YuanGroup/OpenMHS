"""Acceptance run of the Elliptec shutter package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ElliptecShutterCases(unittest.TestCase):
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

    def shutter(self, client, state):
        return client.invoke("cap.optics.shutter.v1", {"state": state}, **self.ids)

    def test_the_shutter_opens_and_closes(self) -> None:
        client = self.serve()
        closed = self.state(client)
        self.assertEqual((closed["is_closed"], closed["is_open"], closed["slot"]), (True, False, 1))
        opened = self.shutter(client, "open")
        self.assertEqual(opened["status"], "completed")
        self.assertEqual(opened["output"], {"state": "open"})
        state = self.state(client)
        self.assertEqual((state["is_open"], state["is_closed"], state["slot"]), (True, False, 2))
        closed_again = self.shutter(client, "closed")
        self.assertEqual(closed_again["output"], {"state": "closed"})
        state = self.state(client)
        self.assertEqual((state["is_closed"], state["is_open"], state["slot"]), (True, False, 1))

    def test_an_unknown_state_is_refused_and_changes_nothing(self) -> None:
        client = self.serve()
        refused = self.shutter(client, "half-open")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["slot"], 1)

    def test_the_slot_move_is_bounded(self) -> None:
        client = self.serve()
        moved = client.invoke("x-cap.roesel.move_to_slot.v1", {"slot": 2}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"slot": 2})
        self.assertTrue(self.state(client)["is_open"])
        for slot in (0, 3):
            refused = client.invoke("x-cap.roesel.move_to_slot.v1", {"slot": slot}, **self.ids)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, slot)
        self.assertEqual(self.state(client)["slot"], 2)

    def test_home_reports_the_slot(self) -> None:
        client = self.serve()
        self.assertEqual(self.shutter(client, "open")["status"], "completed")
        homed = client.invoke("x-cap.roesel.home_shutter.v1", {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"slot": 1})
        self.assertTrue(self.state(client)["is_closed"])

    def test_the_estop_closes_the_shutter_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.shutter(client, "open")["status"], "completed")
        self.assertTrue(self.state(client)["is_open"])
        client.estop("test", **self.ids)
        self.assertTrue(self.state(client)["is_closed"])
        refused = self.shutter(client, "open")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
