"""Acceptance run of the CausalWorld package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): pybullet, gym and the
clone are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CausalWorldCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 9)["status"], "completed")
        for values in ([2.0] + [0.0] * 8, [-2.0] + [0.0] * 8):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_the_observation_is_the_reaching_vector(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["terminated"]), (0, 1, False))
        values = state["observation"]["values"]
        self.assertEqual(len(values), 37)                                         # 1 + 9 + 9 + 9 + 9
        self.assertTrue(all(-1.0 <= value <= 1.0 for value in values), values)

        receipt = self.step(client, [0.5] * 9)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["values"][1:10], [0.5] * 9)       # the fake applies the action
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertIsInstance(output["reward"], (int, float))
        self.assertEqual(len(output["observation"]["values"]), 37)

    def test_a_seed_repeats_the_start_state(self) -> None:
        def start(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            return self.state(client)["observation"]["values"]

        first = start(11)
        self.assertEqual(start(11), first)
        self.assertNotEqual(start(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_ends_after_the_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        for expected_tick in range(1, 126):
            output = self.step(client, [0.0] * 9)["output"]
            self.assertEqual(output["tick"], expected_tick)
            self.assertFalse(output["terminated"], expected_tick)
        output = self.step(client, [0.0] * 9)["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (126, True, False))
        ended = self.step(client, [0.0] * 9)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_ticks_input_is_bounded(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, [0.0] * 9, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 9)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 9), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
