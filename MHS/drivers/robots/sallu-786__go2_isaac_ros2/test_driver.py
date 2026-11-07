"""Acceptance run of the Go2 Isaac Lab package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py); the upstream Isaac Sim/Isaac Lab environment is not installed here and
was never run.  Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ZERO = [0.0, 0.0, 0.0]  # placeholder action of the fake's three-number action space


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2Cases(unittest.TestCase):
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

    def test_reset_and_step_advance_the_clock(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)
        receipt = self.step(client, ZERO)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        # the configuration declares no reward terms (go2_env.py:120-123), so a step pays 0
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual(len(output["observation"]["values"]), 4)  # placeholder observation width of the fake
        self.assertEqual(self.step(client, ZERO, ticks=3)["output"]["tick"], 4)

    def test_an_action_outside_the_space_is_refused(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        refused = self.step(client, [2.0, 0.0, 0.0])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)   # the refused action changed nothing

    def test_a_seed_repeats_the_reset(self) -> None:
        def observation(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]

        self.assertEqual(observation(11), observation(11))
        self.assertNotEqual(observation(11), observation(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("isaaclab:Isaac-Velocity-Flat-Unitree-Go2-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
