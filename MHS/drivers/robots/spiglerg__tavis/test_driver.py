"""Acceptance run of the TAVIS package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream stack
(Isaac Sim, Isaac Lab, IsaacLab-Arena, an NVIDIA RTX GPU and downloaded USD assets) was not available where the gate
runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO = [0.0] * 19


def action(first=0.0, rest=0.0):
    return [first] + [rest] * 18


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class TavisCases(unittest.TestCase):
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

    @staticmethod
    def observation(receipt):
        return receipt["output"]["observation"]["policy"]["values"]

    def test_the_fake_is_a_world_simulator(self) -> None:
        client = self.serve()
        hello = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        self.assertEqual((hello["mode"], hello["risk_class"]), ("simulated", "R0"))
        self.assertEqual([item["kind"] for item in device["resources"]], ["world.sim"])

    def test_the_fake_has_the_19d_gr1t2_action_layout(self) -> None:
        client = self.serve()
        observation = self.observation(self.reset(client, seed=3))
        self.assertEqual(len(observation), 19)
        self.assertEqual(self.step(client, ZERO)["status"], "completed")

    def test_a_step_moves_the_fake_joints(self) -> None:
        client = self.serve()
        start = self.observation(self.reset(client, seed=3))[0]
        receipt = self.step(client, action(first=0.5))
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertAlmostEqual(self.observation(receipt)[0], start + 0.05, places=7)
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_several_ticks_apply_the_action_each_tick(self) -> None:
        client = self.serve()
        start = self.observation(self.reset(client, seed=5))[0]
        output = self.step(client, action(first=0.25), ticks=4)["output"]
        self.assertAlmostEqual(self.observation({"output": output})[0], start + 0.1, places=7)
        self.assertEqual(output["tick"], 4)

    def test_the_action_box_is_unbounded(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        self.assertEqual(self.step(client, [1e6] * 19)["status"], "completed")
        for values in ([], [1.0, 2.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)              # the refused steps changed nothing

    def test_ticks_are_bounded_by_the_world_class(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        for ticks in (0, 10001):
            refused = self.step(client, ZERO, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)              # the refused steps changed nothing

    def test_a_seed_repeats_the_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        other = self.reset(client, seed=12)["output"]
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"], other["observation"])
        self.assertEqual((first["seed"], other["seed"]), (11, 12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_passed_through(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"unused": True})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        fidelity = client.inspect(self.ids["device_id"])["fidelity"]
        self.assertEqual(fidelity["engine"], "tavis:make_tavis_env")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"]), ("F0", 50.0))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
