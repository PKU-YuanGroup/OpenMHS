"""Acceptance run of the LeIsaac PickOrange driver: the gate, plus cases specific to this package.

The cases run on the fake backend (fake.py).  The upstream Isaac Lab environment needs Isaac Sim, the
``isaaclab[isaacsim,all]==2.3.0`` extra and a GPU, so nothing here compares the fake with an upstream run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
EXAMPLE_OVERLAY = HERE / "fixtures" / "operator-limits.example.json"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ACTION = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6]
# ceil(25.0 / (1/60 * 1)) - 1, the direct task's time_out (single_arm_env.py:64-65 and :162-165).
TIMEOUT_TICKS = 1499


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PickOrangeCases(unittest.TestCase):
    def serve(self, *, overlay=False):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY if overlay else None)
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

    def test_the_first_step_writes_the_joint_targets(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        values = observation["policy"]["joint_pos"]["values"][0]
        for got, want in zip(values, ACTION):
            self.assertAlmostEqual(got, want, places=12)
        self.assertEqual(observation["policy"]["joint_pos_target"]["values"][0], values)
        self.assertEqual((output["tick"], output["reward"], output["terminated"], output["truncated"]),
                         (1, 0.0, False, False))

    def test_the_action_preserves_the_upstream_unbounded_space(self) -> None:
        # Isolated R0 Gymnasium stepping has the source-backed unbounded Box, not a hardware target envelope.
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        huge = 1e300  # placeholder probe; not a physical joint target
        receipt = self.step(client, [huge] * 6)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["policy"]["joint_pos"]["values"][0], [huge] * 6)

    def test_the_example_envelope_refuses_both_sides_of_every_joint(self) -> None:
        client = self.serve(overlay=True)
        before = self.state(client)
        for index in range(6):
            for value in (-1.0001, 1.0001):
                action = list(ACTION)
                action[index] = value
                refused = self.step(client, action)
                self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.state(client), before)
        self.assertEqual(self.step(client, ACTION)["status"], "completed")

    def test_ticks_are_bounded_by_the_class(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, ACTION, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_initial_state(self) -> None:
        def observation(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_episode_truncates_at_the_time_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        before = self.step(client, ACTION, ticks=TIMEOUT_TICKS - 1)["output"]
        self.assertFalse(before["truncated"])
        self.assertEqual(before["observation"]["policy"]["joint_pos"]["values"][0], ACTION)
        output = self.step(client, ACTION)["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]),
                         (TIMEOUT_TICKS, False, True))
        # The native step resets timed-out environments before returning observations (direct_rl_env.py:82-107).
        reset_positions = output["observation"]["policy"]["joint_pos"]["values"][0]
        self.assertTrue(all(abs(value) <= 0.01 for value in reset_positions))  # placeholder reset jitter
        self.assertEqual(output["observation"]["policy"]["actions"]["values"][0], ACTION)
        ended = self.step(client, [0.0] * 6)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertTrue(fidelity["engine"].startswith("analytic:"), fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 60.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("640 x 480" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
