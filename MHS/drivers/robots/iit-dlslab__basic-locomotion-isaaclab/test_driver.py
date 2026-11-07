"""Acceptance run of the Go2-Flat package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the upstream task are not installed where the gate runs, so nothing here compares the stand-in with the upstream
environment and no simulator or hardware run is claimed.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7, -0.8, 0.9, -1.0, 1.1, -1.2]
# go2_env_cfg.py:173-183: 3 + 3 + 3 + 3 + 12 + 12 values precede the last-actions term of one 52-value frame.
ACTION_OFFSET = 36
FRAME = 52
OBSERVATION = 260


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Go2FlatCases(unittest.TestCase):
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

    def test_the_action_is_twelve_values(self) -> None:
        client = self.serve()
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), OBSERVATION)
        # the last-action tail of the newest (last) frame is the applied action (go2_env_cfg.py:173-183)
        self.assertEqual(observation[-FRAME + ACTION_OFFSET:-FRAME + ACTION_OFFSET + 12], ACTION)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        refused = self.step(client, ACTION[:-1])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused step changed nothing

    def test_the_action_space_is_unbounded_in_the_fake(self) -> None:
        client = self.serve()
        # The clone's _pre_physics_step accepts any finite action tensor and clamps it to +/-3.0
        # (locomotion_env.py:322-323); the action-space object is built by the external DirectRLEnv and its bounds
        # were not inspected, so this package publishes no finite envelope and the bridge accepts large values.
        self.assertEqual(self.step(client, [1.0e6] * 12)["status"], "completed")

    def test_ticks_advance_the_world_and_the_history(self) -> None:
        client = self.serve()
        first = self.step(client, ACTION, ticks=1)
        self.assertEqual(first["output"]["tick"], 1)
        second = self.step(client, [0.0] * 12, ticks=2)
        output = second["output"]
        self.assertEqual(output["tick"], 3)
        observation = output["observation"]["values"]
        # two more steps shift the first action one frame older (go2_env_cfg.py:185-191 and locomotion_env.py:417-420)
        self.assertEqual(observation[-2 * FRAME + ACTION_OFFSET:-2 * FRAME + ACTION_OFFSET + 12], [0.0] * 12)
        self.assertEqual(observation[-3 * FRAME + ACTION_OFFSET:-3 * FRAME + ACTION_OFFSET + 12], ACTION)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_fake_never_terminates(self) -> None:
        client = self.serve()
        output = self.step(client, ACTION, ticks=4)["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(output["tick"], 4)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "the fake accepts and ignores reset options"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 2)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mhs-fake:Locomotion-Go2-Flat")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
