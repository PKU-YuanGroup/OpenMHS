"""Acceptance run of the ManipArena-Sim package: the gate, plus cases for what is specific to this driver.

The cases run on the package fake (fake.py).  Isaac Sim, Isaac Lab and IsaacLab-Arena are not installed where the gate
runs, so nothing here compares the fake with the upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
#: placeholder: the fake action width, the same test data the fake publishes
VALUES = [0.0] * 12
#: placeholder: a non-zero fake command
PUSH = [0.1, -0.1, 0.2, -0.2, 0.3, -0.3, 0.4, -0.4, 0.5, -0.5, 0.6, -0.6]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ManipArenaCases(unittest.TestCase):
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

    def step(self, client, values=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or VALUES}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_the_environment(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, PUSH, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(len(output["observation"]["policy"]), 4)          # placeholder fake observation width
        self.assertRegex(output["state_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertNotEqual(self.state(client)["observation"], {"policy": [0.0, 0.0, 0.0, 0.0]})

    def test_the_seed_is_echoed_and_used_by_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"],
                         {"seed": 21, "accepted": True})
        pending = self.reset(client)["output"]
        self.assertEqual(pending["seed"], 21)
        explicit = self.reset(client, seed=21)["output"]
        self.assertEqual(explicit["seed"], 21)
        self.assertEqual(pending["observation"], explicit["observation"])

    def test_a_reset_clears_the_tick_and_counts_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        self.step(client, ticks=2)
        self.assertEqual(self.state(client)["tick"], 2)
        reset = self.reset(client, seed=3)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(self.state(client)["episode"], 2)

    def test_the_action_width_is_checked_against_the_environment(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        refused = self.step(client, values=[0.0])
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)                    # the refused step changed nothing

    def test_only_the_default_scenario_is_served(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, scenario="default")["status"], "completed")
        refused = self.reset(client, scenario="other")
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "maniparena_sim:AssembledEnvironment/gymnasium")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1),
                        client.invoke("cap.world.seed.v1", {"seed": 4}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
