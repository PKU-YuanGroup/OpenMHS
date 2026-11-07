"""Acceptance run of the VisFly package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (``fake.py``): Habitat-Sim, torch and the clone are not installed where the gate
runs, so nothing here compares the fake with the upstream simulator.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VisFlyCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action or ZERO_ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"values": [1.0, -1.0, 1.0, -1.0]})["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0], [0.0, -1.5, 0.0, 0.0]):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)               # the refused steps changed nothing

    def test_a_step_advances_the_requested_ticks_and_keeps_the_state_shape(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, {"values": [0.5, 0.0, 0.0, 0.0]}, ticks=4)
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (4, False, False))
        state = output["observation"]["state"]["values"]
        target = output["observation"]["target"]["values"]
        self.assertEqual((len(state), len(target)), (13, 3))
        # the fake starts at [0, 0, 1] +-0.1 and maps the first command to +x motion at 0.5 m/s, 0.03 s per tick
        self.assertAlmostEqual(state[0], 0.5 * 0.03 * 4, delta=0.3)
        self.assertEqual((state[3:7], target), ([1.0, 0.0, 0.0, 0.0], [9.0, 0.0, 1.0]))
        distance = ((9.0 - state[0]) ** 2 + state[1] ** 2 + (1.0 - state[2]) ** 2) ** 0.5
        self.assertLess(output["reward"], -distance)             # the bridge sums the reward over the four ticks

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, {"values": action})["output"]["state_hash"]
                    for action in ([0.1, 0.0, 0.0, 0.0], [0.0, 0.2, 0.0, 0.0], [0.0, 0.0, 0.3, 0.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_options_accept_an_upstream_state(self) -> None:
        client = self.serve()
        values = [[1.0, 2.0, 3.0], [1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        observation = self.reset(client, seed=4, options={"state": values})["output"]["observation"]
        self.assertEqual(observation["state"]["values"],
                         [1.0, 2.0, 3.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
        refused = self.reset(client, options={"state": [[1.0], [1.0], [0.0], [0.0]]})
        self.assertEqual(refused["status"], "failed")             # the upstream accepts lengths 3, 4, 3 and 3

    def test_the_episode_truncates_at_max_episode_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        output = self.step(client, ticks=256)["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (256, False, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (30.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
