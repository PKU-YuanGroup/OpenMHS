"""Acceptance run of the MiniGrid package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package is not
installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
#: max_steps = 16 * 6 ** 2 of BlockedUnlockPickupEnv (minigrid/envs/blockedunlockpickup.py:72-74)
MAX_STEPS = 16 * 6 ** 2


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MinigridCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 2)["status"], "completed")
        for index in (-1, 7):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_all_seven_actions_are_accepted(self) -> None:
        client = self.serve()
        for index in range(7):
            receipt = self.step(client, index)
            self.assertEqual(receipt["status"], "completed", index)
        self.assertEqual(self.state(client)["tick"], 7)

    def test_left_and_right_turn_the_agent(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["output"]["observation"]["direction"], {"index": 0})
        left = self.step(client, 0)["output"]["observation"]["direction"]
        self.assertEqual(left, {"index": 3})                            # 0 - 1 mod 4 (minigrid_env.py:539-542)
        right = self.step(client, 1)["output"]["observation"]["direction"]
        self.assertEqual(right, {"index": 0})                           # 3 + 1 mod 4 (minigrid_env.py:544-546)

    def test_a_seed_repeats_the_world(self) -> None:
        def world(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.state(client)["observation"]

        self.assertEqual(world(11), world(11))
        self.assertNotEqual(world(11), world(12))

    def test_the_episode_is_truncated_at_max_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, 2, ticks=MAX_STEPS)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(output["tick"], MAX_STEPS)
        ended = self.step(client, 2)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:MiniGrid-BlockedUnlockPickup-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
