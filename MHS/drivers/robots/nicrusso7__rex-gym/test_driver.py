"""Acceptance run of the rex-gym package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  pybullet, gym and rex-gym are not installed where the gate runs, so
nothing here compares the fake with the upstream environment.  The numbers asserted are the clone's action and
observation bounds and the registered episode limit; the fake's dynamics are placeholders and only their structure is
checked.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION_MAX = 0.4
MAX_EPISODE_STEPS = 2500


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RexWalkCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [ACTION_MAX, -ACTION_MAX])["status"], "completed")
        for values in ([0.5, 0.0], [-0.5, 0.0], [0.0, 0.41], [0.0, -0.41]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        second = self.reset(client, seed=11)
        self.assertEqual((first["status"], second["status"]), ("completed", "completed"))
        self.assertEqual(first["output"]["seed"], 11)
        self.assertEqual(first["output"]["observation"], second["output"]["observation"])
        self.assertNotEqual(self.reset(client, seed=12)["output"]["observation"],
                            first["output"]["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((receipt["status"], receipt["output"]), ("completed", {"seed": 21, "accepted": True}))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_advances_the_observation_and_the_tick(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        receipt = self.step(client, [0.1, -0.2], ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (3, False, False))
        self.assertEqual(len(output["observation"]["values"]), 4)          # walk_env.py:356-362
        self.assertEqual(output["reward"], 0.0)                            # placeholder of the fake
        state = self.state(client)
        self.assertEqual(state["tick"], 3)
        self.assertEqual(state["observation"], output["observation"])

    def test_the_registered_limit_truncates_at_2500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, [0.0, 0.0], ticks=MAX_EPISODE_STEPS)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (MAX_EPISODE_STEPS, False, True))
        ended = self.step(client, [0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")  # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:RexWalk-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual(fidelity["timestep_ms"], 1.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_observation_stays_inside_its_space(self) -> None:
        client = self.serve()
        self.reset(client, seed=6)
        for _ in range(20):
            receipt = self.step(client, [ACTION_MAX, -ACTION_MAX])
            self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        rate_bound = 2 * math.pi / 0.001
        self.assertTrue(all(abs(value) <= rate_bound for value in values), values)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
