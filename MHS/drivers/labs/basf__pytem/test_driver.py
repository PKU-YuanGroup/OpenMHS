"""Acceptance run of the pyTEM package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PytemCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_stage_write_is_bounded_and_lands(self) -> None:
        client = self.serve()
        refused = self.configure(client, stage_x=1000.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["stage_x"], 12.5)          # test data, untouched
        applied = self.configure(client, stage_x=-250.25, stage_z=100.0, stage_alpha=-30.0)
        self.assertEqual(applied["status"], "completed", applied)
        state = self.state(client)
        self.assertEqual((state["stage_x"], state["stage_z"], state["stage_alpha"]),
                         (-250.25, 100.0, -30.0))

    def test_reset_homes_every_axis(self) -> None:
        client = self.serve()
        self.configure(client, stage_x=-250.25, stage_y=33.0, stage_z=100.0,
                       stage_alpha=-30.0, stage_beta=4.0)
        reset = client.invoke("x-cap.basf.reset_stage_position.v1", {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"], {"home": True})
        state = self.state(client)
        self.assertEqual([state["stage_x"], state["stage_y"], state["stage_z"],
                          state["stage_alpha"], state["stage_beta"]], [0.0, 0.0, 0.0, 0.0, 0.0])

    def test_safe_state_action_reaches_the_native(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["beam_blanked"], state["screen_position"], state["column_valve_position"]),
                         (False, "retracted", "open"))
        safe = client.invoke("x-cap.basf.enter_safe_state.v1", {}, **self.ids)
        self.assertEqual(safe["status"], "completed", safe)
        self.assertEqual(safe["output"], {"applied": True})
        state = self.state(client)
        self.assertEqual((state["beam_blanked"], state["screen_position"], state["column_valve_position"]),
                         (True, "inserted", "closed"))

    def test_estop_reaches_the_safe_state_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertTrue(self.state(client)["beam_blanked"])
        refused = self.configure(client, stage_x=1.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
