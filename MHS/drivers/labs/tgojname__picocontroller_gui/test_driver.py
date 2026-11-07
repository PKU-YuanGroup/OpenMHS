"""Acceptance run of the 8742 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
JOG = "x-cap.tgojname.jog_axis.v1"
STOP = "cap.motion.stop.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PicoControllerCases(unittest.TestCase):
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

    def jog(self, client, axis, direction, velocity):
        return client.invoke(JOG, {"axis": axis, "direction": direction, "velocity": velocity}, **self.ids)

    def test_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertIsInstance(state["version"], str)
        self.assertEqual(len(state["motor_types"]), 4)
        self.assertEqual(state["motion_done"], [True, True, True, True])

    def test_jog_starts_motion_and_stop_clears_it(self) -> None:
        client = self.serve()
        receipt = self.jog(client, 2, "+", 500)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"axis": 2, "direction": "+", "velocity": 500, "move_started": True})
        self.assertEqual(self.state(client)["motion_done"], [True, False, True, True])
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": True})
        self.assertEqual(self.state(client)["motion_done"], [True, True, True, True])

    def test_limits_refuse_before_the_native(self) -> None:
        client = self.serve()
        for payload in (
            {"axis": 0, "direction": "+", "velocity": 500},
            {"axis": 5, "direction": "+", "velocity": 500},
            {"axis": 1, "direction": "0", "velocity": 500},
            {"axis": 1, "direction": "+", "velocity": 2001},
        ):
            refused = client.invoke(JOG, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.state(client)["motion_done"], [True, True, True, True])

    def test_estop_stops_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(self.jog(client, 3, "-", 250)["status"], "completed")
        self.assertEqual(self.state(client)["motion_done"], [True, True, False, True])
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["motion_done"], [True, True, True, True])
        refused = self.jog(client, 3, "-", 250)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
