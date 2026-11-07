"""Acceptance run of the PokeGym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream environment
needs PyBoy, the Pokemon Red ROM and the emulator-only packages, so nothing here compares the fake with the ROM.
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


class PokeGymCases(unittest.TestCase):
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

    def test_the_action_space_is_discrete_8(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        # environment.py:149 with the eight buttons of pyboy_binding.py:40: index 0..7 are in range
        for index in range(8):
            self.assertEqual(self.step(client, index)["status"], "completed", index)
        for index in (-1, 8):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 8)                    # the refused steps changed nothing

    def test_reset_and_step_publish_the_gymnasium_tuple(self) -> None:
        client = self.serve()
        reset = self.reset(client, seed=7)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 7)
        self.assertIsInstance(reset["output"]["observation"], dict)
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        self.assertEqual(output["reward"], 0.0)                            # the first step returns 0 (environment.py:887-894)
        values = output["observation"]["values"]
        self.assertEqual(len(values), 8 * 8 * 4)
        self.assertTrue(all(isinstance(value, int) and 0 <= value <= 255 for value in values))

    def test_ticks_advance_the_counter(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, 0, ticks=4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 4)
        self.assertEqual(self.state(client)["tick"], 4)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual((accepted["status"], accepted["output"]["accepted"]), ("completed", True))
        # the bridge echoes the seed, but the upstream reset ignores it (environment.py:618-619)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_a_second_reset_is_partial(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]["values"]
        for _ in range(3):
            self.assertEqual(self.step(client, 1)["status"], "completed")   # Left: the fake moves away
        second = self.reset(client, seed=3)["output"]["observation"]["values"]
        # environment.py:620-621 loads the first saved state only on the first reset, so later resets keep the game
        self.assertNotEqual(second, first)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("pyboy:pokemon-red", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
