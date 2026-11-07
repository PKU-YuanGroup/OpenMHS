"""Acceptance run of the Webots-drone package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream package, Webots and its controller binding are not
installed where the gate runs, so nothing here compares the fake with a Webots run.
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
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WebotsDroneCases(unittest.TestCase):
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
        for values in ([math.pi / 12.0 + 0.01, 0.0, 0.0, 0.0],
                       [0.0, math.pi / 12.0 + 0.01, 0.0, 0.0],
                       [0.0, 0.0, math.pi + 0.01, 0.0],
                       [0.0, 0.0, 0.0, 5.01]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        for ticks in (0, 10001):  # the bridge's schema bounds, not an action-space bound
            refused = client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": ZERO_ACTION}},
                                    **self.ids)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused calls changed nothing

    def test_the_first_step_moves_the_drone(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=3)
        self.assertEqual(reset["status"], "completed")
        initial = reset["output"]["observation"]["values"]
        self.assertEqual(len(initial), 22)  # is_pixels=False: the vector observation
        self.assertEqual(initial[8], 25.0)  # position z is the initial altitude
        receipt = self.step(client, [0.0, 0.1, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        observed = output["observation"]["values"]
        self.assertGreater(observed[6], initial[6])  # pitch 0.1 moves the fake along +x
        self.assertLess(observed[6], initial[6] + 0.6)
        self.assertEqual(observed[8], 25.0)
        self.assertAlmostEqual(observed[1], 0.1)
        self.assertTrue(math.isfinite(output["reward"]))

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, [0.1, 0.0, 0.0, 0.0])["output"]["state_hash"] for _ in range(5)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_time_limit_truncates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, [0.0, 0.1, 0.0, 0.0], ticks=70)  # along the open side: no risk zone
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["truncated"])
        self.assertFalse(output["terminated"])
        # 60 s of 8 ms base steps over a 120-130 step macro-step: 58 to 63 environment steps
        self.assertGreaterEqual(output["tick"], 55)
        self.assertLessEqual(output["tick"], 65)
        self.assertEqual(self.step(client, ZERO_ACTION)["error"]["mhs_code"], PRECONDITION)

    def test_the_no_action_limit_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        output = self.step(client, ZERO_ACTION, ticks=10)["output"]
        self.assertTrue(output["terminated"])
        self.assertIn(output["tick"], (5, 6))  # 625 base frames at 120-130 frames per step
        self.assertEqual(self.step(client, ZERO_ACTION)["error"]["mhs_code"], PRECONDITION)

    def test_the_out_area_limit_terminates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        output = self.step(client, [0.0, -math.pi / 12.0, 0.0, 0.0], ticks=60)["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertLess(output["tick"], 60)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("webots", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (1000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
