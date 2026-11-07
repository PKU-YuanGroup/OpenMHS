"""Acceptance run of the LocoMuJoCo package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (``fake.py``): the upstream
package, jax and the separate ``loco_mujoco_models`` model files are not installed where the gate runs, so nothing
here compares the fake with the upstream simulator.  The observation and action widths and values are the fake's
placeholder test data, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
# placeholder: the fake's action width and observation width
ACTION = [0.0] * 27
OBSERVATION_WIDTH = 68


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LocoMujocoCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or ACTION}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5] * 27)["status"], "completed")
        for values in ([1.5] * 27, [-1.5] * 27):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values[0])
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values[0])
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_the_action_vector_has_the_environment_shape(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0] * 26)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_a_step_changes_the_observation_and_the_tick(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(before), OBSERVATION_WIDTH)
        receipt = self.step(client, [0.5] * 27)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["reward"], 0.0)
        self.assertNotEqual(output["observation"]["values"], before)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_ticks_advance_that_many_transitions(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        output = self.step(client, [0.25] * 27, ticks=3)["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(self.state(client)["tick"], 3)
        self.assertEqual(output["reward"], 0.0)

    def test_a_seed_repeats_the_fake_trajectory(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["values"]
        second = self.reset(client, seed=7)["output"]["observation"]["values"]
        other = self.reset(client, seed=8)["output"]["observation"]["values"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_out_of_range_ticks_are_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 0, "action": {"values": ACTION}}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mujoco:loco-mujoco:LocoMujoco")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (10.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
