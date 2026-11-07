"""Acceptance run of the UR reach Gymnasium package: the gate plus package cases.

Add cases, never remove the check_driver call.  The cases exercise the fake
backend only; no MuJoCo, ROS graph or hardware is started.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class URReachCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, values, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"values": values}},
            **self.ids,
        )

    def test_a_step_advances_the_world_and_returns_the_upstream_observation_size(self) -> None:
        client = self.serve()
        before = client.read("world", **self.ids)
        receipt = self.step(client, [0.0] * 6, ticks=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["tick"], 3, receipt)
        after = client.read("world", **self.ids)
        self.assertEqual(after["state"]["tick"], 3, after)
        self.assertEqual(len(after["state"]["observation"]["values"]), 15, after)
        self.assertEqual(set(after["state"]["info"]), {"dist"})
        self.assertNotEqual(before["state"]["tick"], after["state"]["tick"])

    def test_reset_with_a_seed_reproduces_the_observation(self) -> None:
        client = self.serve()
        first = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        second = client.invoke("cap.world.reset.v1", {"seed": 7}, **self.ids)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(second["status"], "completed", second)
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])
        self.assertEqual(first["output"]["seed"], 7)

    def test_an_out_of_envelope_action_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, [2.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)

    def test_a_wrong_action_length_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * 5)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", receipt)

    def test_the_software_estop_latch_refuses_the_next_step(self) -> None:
        client = self.serve()
        self.step(client, [0.2] * 6)
        before = client.read("world", **self.ids)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        after = client.read("world", **self.ids)
        self.assertEqual(after["state"]["tick"], before["state"]["tick"])
        self.assertEqual(after["state"]["observation"], before["state"]["observation"])
        refused = self.step(client, [0.0] * 6)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)


if __name__ == "__main__":
    unittest.main()
