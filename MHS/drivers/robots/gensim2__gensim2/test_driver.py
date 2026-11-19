"""Acceptance run of the GenSim2 package: the gate, plus cases for this driver's fake environment.

Add cases, never remove the check_driver call.  Everything here runs on the package's fake backend: the SAPIEN
environment needs gym, sapien==2.2.2, a CUDA renderer and the asset tree, and is not installed or run here.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# Test data of the fake (fake.py placeholders), not upstream facts.
HOLD = {"values": [0.3, 0.0, 0.7, 1.0, 0.0, 0.0, 0.0, 1.0]}
REACH = {"values": [0.5, 0.0, 0.9, 1.0, 0.0, 0.0, 0.0, 1.0]}
OUTSIDE = {"values": [1.5, 0.0, 0.9, 1.0, 0.0, 0.0, 0.0, 1.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FakeEnvironmentCases(unittest.TestCase):
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

    def test_the_action_box_is_the_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.step(client, REACH)["status"], "completed")
        refused = self.step(client, OUTSIDE)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        short = self.step(client, {"values": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]})
        self.assertEqual((short["status"], short["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 1)          # neither refusal reached the fake

    def test_the_observation_is_the_fifteen_value_state(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 15)
        self.assertEqual(values[:4], [0.3, 0.0, 0.7, 1.0])       # fake placeholder start pose
        self.assertEqual(self.state(client)["episode"], 1)

    def test_reaching_the_target_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)
        tick = None
        for expected in (1, 2, 3):
            receipt = self.step(client, REACH)
            self.assertEqual(receipt["status"], "completed")
            tick = receipt["output"]["tick"]
            self.assertEqual(tick, expected)
            if receipt["output"]["terminated"]:
                break
        self.assertEqual(tick, 3)                                # the placeholder target is reached
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(self.state(client)["info"]["success"])
        after = self.step(client, REACH)
        self.assertEqual((after["status"], after["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_horizon_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, HOLD, ticks=50)              # the fake cannot reach the target from here
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (50, True, False))
        self.assertFalse(self.state(client)["info"]["success"])

    def test_legacy_reset_options_do_not_select_random(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11, options={"random": True})["output"]["observation"]["values"]
        second = self.reset(client, seed=11, options={"random": True})["output"]["observation"]["values"]
        other = self.reset(client, seed=12, options={"random": True})["output"]["observation"]["values"]
        # wrappers.py:112 accepts only random=False. The legacy bridge fallback calls seed(seed), reset()
        # after the unsupported seed/options keywords are refused; those options never reach the native task.
        self.assertEqual(first[:3], [0.3, 0.0, 0.7])  # fake-only placeholder default pose
        self.assertEqual(first, second)
        self.assertEqual(first, other)

    def test_the_gripper_uses_integer_openness(self) -> None:
        client = self.serve()
        for openness in (-1.0, 0.0, 0.5, 1.0):
            self.reset(client)
            values = list(HOLD["values"])
            values[-1] = openness
            receipt = self.step(client, {"values": values})
            self.assertEqual(receipt["status"], "completed", receipt)
            # sapien/env.py:435 writes int(openness) * 0.04 to each finger's target.
            self.assertEqual(receipt["output"]["observation"]["values"][-1], int(openness) * 0.04)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertEqual((accepted["output"]["seed"], accepted["output"]["accepted"]), (21, True))
        first = self.reset(client, options={"random": True})["output"]["observation"]["values"]
        second = self.reset(client, seed=21, options={"random": True})["output"]["observation"]["values"]
        self.assertEqual(first, second)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gensim2:analytic-fake", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (800.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        self.assertEqual(self.step(client, REACH)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, REACH), self.reset(client, seed=2)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
