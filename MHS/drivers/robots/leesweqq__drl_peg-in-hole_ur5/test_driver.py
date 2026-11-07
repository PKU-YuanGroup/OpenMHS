"""Acceptance run of the peg-in-hole package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); pybullet and the
upstream environment are not installed where the gate runs, so nothing here compares the fake with the PyBullet
environment.
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


class PegInHoleCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, [0.005, -0.005, 0.0])["status"], "completed")
        for values in ([0.0051, 0.0, 0.0], [0.0, 0.0, -0.0051]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_ticks_are_bounded_below(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0, 0.0, 0.0], ticks=0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_reset(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed")
            self.assertEqual(receipt["output"]["seed"], seed)
            return receipt["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_step_returns_a_tick_a_reward_and_a_state_hash(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, [0.001, -0.002, -0.003])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertLess(output["reward"], 0.0)                  # the start is still away from the hole
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["reward"]), (1, 1, output["reward"]))

    def test_a_zero_action_is_truncated_at_500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        # The zero action keeps the fake end effector at its start pose, 0.15 above the hole: never inserted,
        # so only the 500-step limit (rlenv.py:25, 175) ends the episode.
        receipt = self.step(client, [0.0, 0.0, 0.0], ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 500))
        ended = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_peg_reaches_the_hole_in_this_kinematic_model(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=5)["output"]["observation"]["cam_image"]["values"]
        # rlenv.py:110-114 puts the hole in x 0.5..0.6 and y 0..0.1; fake.py projects both the hole (255) and the
        # end effector (128) into the 100x100 image, so the test can steer by the same pixels the agent sees.
        target = observation.index(255) if 255 in observation else observation.index(128)
        target_x, target_y = target % 100, target // 100
        reached = None
        for tick in range(1, 61):
            image = self.state(client)["observation"]["cam_image"]["values"]
            eef = image.index(128)
            eef_x, eef_y = eef % 100, eef // 100
            if 255 in image:
                target = image.index(255)
                target_x, target_y = target % 100, target // 100
            dx = (target_x - eef_x) / 99 * 0.1
            dy = (target_y - eef_y) / 99 * 0.1
            values = [min(max(dx, -0.005), 0.005), min(max(dy, -0.005), 0.005),
                      -0.005 if tick <= 11 else 0.0]
            receipt = self.step(client, values)
            self.assertEqual(receipt["status"], "completed", tick)
            reached = receipt["output"]
            if reached["terminated"]:
                break
        self.assertIsNotNone(reached)
        self.assertTrue(reached["terminated"], reached)
        self.assertGreaterEqual(reached["reward"], 99.0, reached)      # rlenv.py:248-249 adds 100 on insertion
        self.assertLessEqual(reached["tick"], 60)
        self.assertEqual(self.state(client)["info"].get("insertion_success"), True)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0, 0.0, 0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0, 0.0, 0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
