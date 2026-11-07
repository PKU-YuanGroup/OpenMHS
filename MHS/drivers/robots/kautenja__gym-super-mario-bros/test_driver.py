"""Acceptance run of this driver package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): nes-py and the upstream
environment are not installed where the gate runs, so nothing here compares the fake with the real NES emulator.
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


class SuperMarioBrosCases(unittest.TestCase):
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
        self.assertEqual(self.step(client, 255)["status"], "completed")
        for index in (-1, 256):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 2)                    # the refused steps changed nothing
        for ticks in (0, 10001):
            refused = client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": 0}}, **self.ids)
            # ticks is a shape bound of the step input, not a limit derived from the action space
            self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", ticks)

    def test_reset_and_step_return_the_gymnasium_shapes(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=0, options={})
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 0)
        values = reset["output"]["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (2, 2, 3))
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        info = self.state(client)["info"]
        # the documented 1-1 opening values (tests/test_smv_env.py:81-90), advanced by one frame
        self.assertEqual((info["coins"], info["life"], info["world"]), (0, 2, 1))
        self.assertEqual((info["stage"], info["level"], info["area"]), (1, 0, 1))
        self.assertEqual((info["time"], info["x_pos"], info["y_pos"]), (400, 41, 79))
        self.assertIn("reward_components", info)
        self.assertIn("reward_total_clipped", info)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (1, 0, 1, 1, 1)]

        first = trajectory(7)
        self.assertEqual(trajectory(7), first)
        self.assertNotEqual(trajectory(8), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 5}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 5)
        self.assertEqual(self.reset(client, seed=5)["output"]["observation"], first["observation"])

    def test_the_third_lost_life_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=0)
        receipt = self.step(client, 1, ticks=4800)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # the fake's clock reaches zero after 1600 frames and the life counter goes 2, 1, 0, then 0xff
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 4800))
        self.assertEqual(self.state(client)["info"]["life"], 255)
        ended = self.step(client, 1)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:SuperMarioBros-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=0)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
