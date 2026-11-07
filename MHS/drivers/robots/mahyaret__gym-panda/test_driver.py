"""Acceptance run of the gym-panda package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym, pybullet and
numpy are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaCases(unittest.TestCase):
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

    def test_the_action_box_bounds_every_element(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ([1.5, 0.0, 0.0, 0.0], [0.0, -1.5, 0.0, 0.0],
                       [0.0, 0.0, 1.5, 0.0], [0.0, 0.0, 0.0, 1.5]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        wrong = self.step(client, [0.0, 0.0, 0.0])
        self.assertEqual((wrong["status"], wrong["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 1)                 # the refused steps changed nothing

    def test_a_step_applies_the_hand_increment(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=11)["output"]["observation"]["values"]
        receipt = self.step(client, [1.0, 0.0, 0.0, 0.5])
        self.assertEqual(receipt["status"], "completed")
        values = receipt["output"]["observation"]["values"]
        # panda_env.py:28-31: one step moves the hand by action * 0.005
        self.assertAlmostEqual(values[0], start[0] + 0.005, places=6)
        self.assertEqual((values[1], values[2]), (start[1], start[2]))
        self.assertEqual((values[3], values[4]), (0.5, 0.5))
        self.assertEqual((receipt["output"]["reward"], receipt["output"]["terminated"]), (0.0, False))

    def test_a_seed_repeats_the_object_start(self) -> None:
        def start_position(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
            self.assertEqual(self.step(client, [0.0, 0.0, 0.0, 1.0])["status"], "completed")
            return self.state(client)["info"]["object_position"]

        first = start_position(11)
        self.assertEqual(start_position(11), first)
        self.assertNotEqual(start_position(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]
        self.assertEqual((accepted["seed"], accepted["accepted"]), (21, True))
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])
        self.step(client, [0.0, 0.0, 0.0, 1.0])
        drawn = self.state(client)["info"]["object_position"]

        other = self.serve()
        self.reset(other, seed=21)
        self.step(other, [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(self.state(other)["info"]["object_position"], drawn)

    def test_the_episode_ends_after_max_episode_len_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=11)
        receipt = self.step(client, [0.0, 0.0, 0.0, 1.0], ticks=2000)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["terminated"]), (2000, False))
        last = self.step(client, [0.0, 0.0, 0.0, 1.0])
        # panda_env.py:13,58-62: done once step_counter is greater than MAX_EPISODE_LEN (20 * 100)
        self.assertEqual((last["output"]["tick"], last["output"]["terminated"]), (2001, True))
        self.assertEqual(last["output"]["reward"], 0.0)
        ended = self.step(client, [0.0, 0.0, 0.0, 1.0])
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client, seed=11)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_closing_the_gripper_near_the_object_can_lift_it(self) -> None:
        client = self.serve()
        self.reset(client, seed=11)                                     # this seed puts the object near the hand
        self.assertEqual(self.step(client, ZERO)["status"], "completed")  # placeholder grasp rule in fake.py
        receipt = self.step(client, [0.0, 0.0, 1.0, 0.0], ticks=100)
        self.assertEqual(receipt["status"], "completed")
        # panda_env.py:51-56: the object passing z 0.45 ends the episode with reward 1
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["reward"]), (True, 1.0))
        self.assertGreater(self.state(client)["info"]["object_position"][2], 0.45)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pybullet:panda-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
