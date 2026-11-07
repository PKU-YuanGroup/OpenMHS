"""Acceptance run of the RoboCasa package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend (fake.py); robosuite, MuJoCo,
gymnasium and the kitchen assets are not installed where the gate runs, so nothing here compares the fake with the
upstream simulator.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
# The five fields of the wrapper action space, bounded by -1 and 1 (gym_wrapper.py:83-102).
ACTION = {
    "gripper_close": [0.0],
    "end_effector_position": [0.0, 0.0, 0.0],
    "end_effector_rotation": [0.0, 0.0, 0.0],
    "base_motion": [0.0, 0.0, 0.0, 0.0],
    "control_mode": [0.0],
}


def action_with(**changes):
    result = {key: list(value) for key, value in ACTION.items()}
    result.update(changes)
    return result


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboCasaCases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": action or ACTION}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        self.assertEqual(self.step(client)["status"], "completed")
        for action in (action_with(gripper_close=[2.0]),
                       action_with(end_effector_position=[0.0, -1.5, 0.0]),
                       action_with(base_motion=[0.0, 0.0, 0.0, 1.01])):
            refused = self.step(client, action=action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_a_step_advances_the_tick_and_moves_the_placeholder_state(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=4)["status"], "completed")
        before = self.state(client)["observation"]["state.end_effector_position_relative"]
        receipt = self.step(client, action=action_with(end_effector_position=[1.0, 0.0, 0.0]), ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        after = output["observation"]["state.end_effector_position_relative"]
        self.assertGreater(after[0], before[0])
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_seed_repeats_the_reset_state(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        third = self.reset(client, seed=12)["output"]
        self.assertEqual(first["seed"], 11)
        self.assertEqual(first["observation"], second["observation"])
        self.assertNotEqual(first["observation"], third["observation"])

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed")
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.state(client)["seed"], 21)
        without_seed = self.reset(client)["output"]
        self.assertEqual(without_seed["seed"], 21)
        with_seed = self.reset(client, seed=21)["output"]
        self.assertEqual(without_seed["observation"], with_seed["observation"])

    def test_reset_options_are_accepted_and_ignored(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5, options={"split": "pretrain"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R1")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertTrue(fidelity["engine"].startswith("custom:robocasa/"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
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
