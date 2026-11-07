"""Acceptance run of the OctoMuscleCrawl driver: the gate, plus cases for what is specific to this package.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
(gymnasium, numpy, PyElastica, COOMM) is not installed where the gate runs, so nothing here compares the fake with
the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
VALUES = 8 * 9


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OctoMuscleCases(unittest.TestCase):
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

    @staticmethod
    def action(value=0.0):
        return [value] * VALUES

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.action())["status"], "completed")
        refused = self.step(client, self.action(2.0))
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused step changed nothing

    def test_reset_starts_at_the_origin_and_a_step_moves_the_body(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["values"], [0.0] * 6)
        self.assertEqual(self.state(client)["tick"], 0)
        moved = self.step(client, self.action(0.5))
        self.assertEqual(moved["status"], "completed")
        values = moved["output"]["observation"]["values"]
        self.assertEqual(len(values), 6)
        self.assertNotEqual(values, [0.0] * 6)
        self.assertGreater(moved["output"]["reward"], 0.0)
        self.assertEqual(moved["output"]["tick"], 1)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                       # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, self.action(value))["output"]["observation"]["values"]
                    for value in (0.5, -0.5, 1.0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_horizon_truncates_at_720_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, self.action(0.25), ticks=720)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the default horizon is ceil(episode_duration_s / control_dt) = 720 steps (config.py:93-101,
        # muscle_crawl_env.py:47-49)
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 720))
        ended = self.step(client, self.action(0.25))
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_options_are_ignored(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["values"], [0.0] * 6)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:OctoMuscleCrawl-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, self.action())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, self.action()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
