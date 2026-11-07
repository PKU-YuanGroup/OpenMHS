"""Acceptance run of the Isaac Drone Racer package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream
environment needs Isaac Sim 4.5.0, Isaac Lab v2.1.0 and a GPU, so nothing here compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
HOVER = {"values": [0.0, 0.0, 0.0, 0.0]}
FULL = {"values": [1.0, 1.0, 1.0, 1.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DroneRacerCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOVER)["status"], "completed")
        for values in ({"values": [1.5, 0.0, 0.0, 0.0]}, {"values": [0.0, -1.5, 0.0, 0.0]},
                       {"values": [0.0, 0.0, 0.0, -1.5]}):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        wrong_length = self.step(client, {"values": [0.0, 0.0, 0.0, 0.0, 0.0]})
        self.assertEqual(wrong_length["status"], "rejected", wrong_length)
        self.assertEqual(wrong_length["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_zero_ticks_is_refused(self) -> None:
        client = self.serve()
        refused = self.step(client, HOVER, ticks=0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=8)["output"]
        self.assertNotEqual(first["observation"], other["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(self.reset(client, seed=11)["output"]["observation"], first["observation"])

    def test_a_step_advances_the_world(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, HOVER)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        policy = output["observation"]["policy"]["values"]
        self.assertEqual(len(policy), 20)                                       # six concatenated policy terms
        self.assertEqual(policy[16:], [0.0, 0.0, 0.0, 0.0])                     # the last applied action
        self.assertEqual(self.state(client)["tick"], 1)
        before = output["state_hash"]
        self.assertNotEqual(self.step(client, FULL)["output"]["state_hash"], before)

    def test_full_thrust_flies_away(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, FULL, ticks=300)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # the 20 m flyaway termination of drone_racer_env_cfg.py:188 is reached well inside 300 ticks
        self.assertTrue(output["terminated"], output)
        self.assertFalse(output["truncated"], output)
        self.assertLess(output["tick"], 300)
        ended = self.step(client, HOVER)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_the_time_limit_truncates(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        output = self.step(client, HOVER, ticks=2000)["output"]                 # 20 s of 10 ms steps
        self.assertEqual((output["truncated"], output["terminated"], output["tick"]), (True, False, 2000))
        self.assertEqual(self.step(client, HOVER)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("isaaclab:Isaac-Drone-Racer-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, HOVER)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, HOVER), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 1}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
