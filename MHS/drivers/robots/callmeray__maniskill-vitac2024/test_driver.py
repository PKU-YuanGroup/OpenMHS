"""Acceptance run of the ViTac peg-insertion package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); SAPIEN, SapienIPC and
the upstream clone are not imported or run, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = [0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ViTacPegInsertionCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None):
        fields = {} if seed is None else {"seed": seed}
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        for values in ([-1.1, 0.0, 0.0], [0.0, 1.1, 0.0], [0.0, 0.0, -1.1]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_a_step_updates_the_offset_and_the_marker_shape(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=3)
        self.assertEqual(reset["status"], "completed")
        before = reset["output"]["observation"]["gt_offset"]["values"]
        flow = reset["output"]["observation"]["marker_flow"]["values"]
        self.assertEqual((len(flow), len(flow[0]), len(flow[0][0]), len(flow[0][0][0])), (2, 2, 128, 2))
        receipt = self.step(client, [0.5, -0.25, 1.0])
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["gt_offset"]["values"]
        self.assertNotEqual(after, before)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                    # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, values)["output"]["state_hash"]
                    for values in ([1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 1.0, 1.0])]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_an_offset_past_the_threshold_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, [1.0, 1.0, 1.0], ticks=10)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # theta grows by 4 per tick and starts in [-10, 10] on the fake, so the 15 limit is crossed by tick 7
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLessEqual(output["tick"], 7)
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_a_still_action_is_truncated_at_the_episode_budget(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        receipt = self.step(client, ZERO_ACTION, ticks=15)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, True))
        self.assertEqual(receipt["output"]["tick"], 15)
        self.assertEqual(self.step(client, ZERO_ACTION)["error"]["mhs_code"], PRECONDITION)
        self.reset(client, seed=2)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:vitac-peg-insertion-fake", "F0"))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "parameter"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
