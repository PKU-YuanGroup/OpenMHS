"""Acceptance run of the SustainCluster package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream environment
needs pandas, numpy, torch and the workload dataset and is not installed where the gate runs, so nothing here compares
the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TaskSchedulingEnvCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 5):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused steps changed nothing

    def test_a_step_advances_one_tick_and_returns_the_aggregated_observation(self) -> None:
        client = self.serve()
        receipt = self.step(client, 2)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # The fake's fixed test configuration has five datacenters, so the aggregated vector is
        # 4 time + 5 task + 5 * 5 datacenter features (envs/task_scheduling_env.py:81-86).
        self.assertEqual(len(output["observation"]["values"]), 34)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_observation_changes_with_the_clock_and_the_assignment(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        first = self.step(client, 0)["output"]["observation"]["values"]
        second = self.step(client, 4)["output"]["observation"]["values"]
        self.assertNotEqual(before, first)
        self.assertNotEqual(first, second)

    def test_a_seed_repeats_the_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(second["seed"], 11)
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=12)["output"]
        self.assertNotEqual(other["observation"], first["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_reset_options_are_accepted_and_ignored(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=4, options={"note": "upstream ignores reset options"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 4)

    def test_the_episode_truncates_at_the_end_time(self) -> None:
        client = self.serve()
        output = self.step(client, 0, ticks=10000)["output"]
        # The fake's fixed scenario lasts seven days at 15 minutes per step: 7 * 24 * 4 = 672 steps.
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, True, 672))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("sustain-cluster:TaskSchedulingEnv", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (900000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
