"""Acceptance run of the KitchenShift package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py): MuJoCo and gym are not installed where the gate runs, so nothing here
compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO_ACTION = {"values": [0.0] * 9}
FULL_ACTION = {"values": [1.0] * 9}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KitchenShiftV0Cases(unittest.TestCase):
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

    def test_the_observation_arrays_have_the_upstream_dimensions(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=3)["output"]["observation"]
        self.assertEqual(sorted(observation), ["obj_qp", "obj_qv", "robot_qp", "robot_qv"])
        self.assertEqual(len(observation["robot_qp"]["values"]), 9)       # kitchen_v0.py:63
        self.assertEqual(len(observation["robot_qv"]["values"]), 9)
        self.assertEqual(len(observation["obj_qp"]["values"]), 21)        # kitchen_v0.py:64
        self.assertEqual(len(observation["obj_qv"]["values"]), 21)

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, FULL_ACTION)["status"], "completed")
        refused = self.step(client, {"values": [1.5] + [0.0] * 8})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused step changed nothing

    def test_a_step_scales_the_action_and_moves_the_robot_positions(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=5)["output"]["observation"]["robot_qp"]["values"]
        output = self.step(client, FULL_ACTION)["output"]
        after = output["observation"]["robot_qp"]["values"]
        # kitchen_v0.py:130-131 and :222-225: a = act_mid + 1.0 * act_amp = 2.0, and one step is the default
        # frame_skip of 40 at the model's 0.002 s timestep (kitchen_v0.py:44, assets/kitchen.xml:16)
        self.assertEqual(output["observation"]["robot_qv"]["values"], [2.0] * 9)
        for old, new in zip(before, after):
            self.assertAlmostEqual(new - old, 2.0 * 0.08, places=9)
        self.assertEqual((output["reward"], output["terminated"], output["tick"]), (0.0, False, 1))

    def test_a_seed_repeats_the_reset_and_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)["output"]
        second = self.reset(client, seed=11)["output"]
        self.assertEqual(first["observation"], second["observation"])
        other = self.reset(client, seed=12)["output"]
        self.assertNotEqual(first["observation"], other["observation"])
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        pending = self.reset(client)["output"]
        self.assertEqual((pending["seed"], pending["observation"]),
                         (21, self.reset(client, seed=21)["output"]["observation"]))

    def test_the_registered_time_limit_truncates_at_280_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = self.step(client, ZERO_ACTION, ticks=280)["output"]
        # __init__.py:9: kitchen-v0 is registered with max_episode_steps=280; the bare class never ends
        # (kitchen_v0.py:215-220), so the fake applies the wrapper's truncation
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (280, False, True))
        ended = self.step(client, ZERO_ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["output"]["seed"], 1)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:kitchen-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (80.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO_ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO_ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
