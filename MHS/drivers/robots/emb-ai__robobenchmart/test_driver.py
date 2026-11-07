"""Acceptance run of the RoboBenchMart package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): ManiSkill, SAPIEN, Vulkan
and the downloaded scene data are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO_ACTION = [0.0] * 10


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboBenchMartCases(unittest.TestCase):
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

    def test_the_reset_returns_ten_joint_positions(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["seed"], 7)
        self.assertEqual(len(output["observation"]["values"]), 10)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"], state["seed"]), (0, 1, 7))
        self.assertEqual((state["terminated"], state["truncated"]), (False, False))

    def test_a_step_advances_one_tick_and_moves_the_joints(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        receipt = self.step(client, [1.0] * 10)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"], output["terminated"], output["truncated"]),
                         (1, 0.0, False, False))
        observed = output["observation"]["values"]
        self.assertEqual(len(observed), 10)
        self.assertTrue(all(after >= before for before, after in zip(start, observed)), (start, observed))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_advance_that_many_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, ZERO_ACTION, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_action_box_is_the_envelope(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        wrong_length = self.step(client, [0.0] * 11)
        self.assertEqual(wrong_length["status"], "rejected")
        self.assertIn(wrong_length["error"]["mhs_code"],
                      ("MHS.CAPABILITY.INPUT_INVALID", ENVELOPE))
        too_high = self.step(client, [1.5] + [0.0] * 9)
        self.assertEqual((too_high["status"], too_high["error"]["mhs_code"]), ("rejected", ENVELOPE))
        too_low = self.step(client, [-1.5] + [0.0] * 9)
        self.assertEqual((too_low["status"], too_low["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(self.state(client)["tick"], 0)              # the refusals changed nothing

    def test_a_seed_repeats_the_start_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        second = self.reset(client, seed=11)["output"]["observation"]
        self.assertEqual(first, second)
        other = self.reset(client, seed=12)["output"]["observation"]
        self.assertNotEqual(other, first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5, options={"reconfigure": True, "robot_init_pose_seed": 9})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.state(client)["seed"], 5)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:dsynth-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 10)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
