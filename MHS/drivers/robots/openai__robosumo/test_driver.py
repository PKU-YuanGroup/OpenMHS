"""Acceptance run of the RoboSumo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym, mujoco_py and MuJoCo and is not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
AGENTS = 2
CONTROLS = 8


def controls(first=0.0, second=0.0):
    return {"ant0": [first] * CONTROLS, "ant1": [second] * CONTROLS}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboSumoCases(unittest.TestCase):
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

    def step(self, client, ticks=1, action=None):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": controls() if action is None else action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_advances_the_two_agent_world(self) -> None:
        client = self.serve()
        receipt = self.step(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        items = output["observation"]["items"]
        self.assertEqual(len(items), AGENTS)
        self.assertTrue(all(len(item["values"]) == 3 for item in items), items)
        self.assertTrue(math.isfinite(output["reward"]))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_reset_seed_repeats_the_start(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(len(second["observation"]["items"]), AGENTS)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_an_episode_is_truncated_after_500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=501)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertEqual(output["tick"], 501)                    # sumo.py:165 tests steps > timestep_limit
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_agent_pushed_out_terminates_the_episode(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ticks=40, action=controls(first=1.0))
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["terminated"])
        rewards = self.state(client)["info"]["rewards"]
        self.assertEqual(len(rewards), AGENTS)
        self.assertTrue(any(value <= -2000.0 for value in rewards), rewards)   # sumo.py:38
        self.assertTrue(any(value >= 2000.0 for value in rewards), rewards)

    def test_the_action_input_requires_both_named_agents(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.world.step.v1",
                                {"ticks": 1, "action": {"ant0": [0.0] * CONTROLS}}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)

    def test_a_control_outside_the_actuator_range_is_refused(self) -> None:
        # ant.xml:58-65 bounds every ant motor to -1.0 .. 1.0; the bridge publishes the two Box spaces as runtime
        # limits, so the refusal comes before the fake and its revision does not move.
        client = self.serve()
        before = self.state(client)["tick"]
        receipt = self.step(client, action=controls(first=2.0))
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], before)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("robosumo:RoboSumo-Ant-vs-Ant-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)
        self.assertTrue(any("120" in gap for gap in fidelity["gaps"]), fidelity["gaps"])


if __name__ == "__main__":
    unittest.main()
