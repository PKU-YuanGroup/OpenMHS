"""Acceptance run of the LW-BenchHub package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the package's fake backend (``fake.py``):
Isaac Sim and Isaac Lab are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.  All numbers in the cases are test data of the fake.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION_DIM = 8
OBSERVATION_SIZE = 104
OBJECT_POSITION_START = 101


def action(**overrides) -> dict:
    values = [0.0] * ACTION_DIM
    for index, value in overrides.items():
        values[int(index)] = float(value)
    return {"values": values}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class LiftObjCases(unittest.TestCase):
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

    def policy(self, receipt):
        return receipt["output"]["observation"]["policy"]["values"]

    def test_the_action_contract_is_eight_numbers(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * ACTION_DIM)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)
        for wrong in ([0.0] * (ACTION_DIM - 1), [0.0] * (ACTION_DIM + 1)):
            refused = self.step(client, wrong)
            self.assertEqual(refused["status"], "rejected", len(wrong))
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, len(wrong))
        self.assertEqual(self.state(client)["tick"], 1)                # the refused calls changed nothing

    def test_the_upstream_action_space_is_unbounded(self) -> None:
        client = self.serve()
        # ManagerBasedRLEnv builds Box(-inf, inf, (action_dim,)); the driver must not invent a bound.
        receipt = self.step(client, [0.0, 101.0, -1e6, 1e9, 0.0, -5.0, 0.0, 0.0])
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 1)

    def test_a_seed_repeats_the_object_placement(self) -> None:
        def placement(seed):
            client = self.serve()
            values = self.policy(self.reset(client, seed=seed))
            self.assertEqual(len(values), OBSERVATION_SIZE)
            return values[OBJECT_POSITION_START:]

        first = placement(11)
        self.assertEqual(placement(11), first)
        self.assertNotEqual(placement(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_a_closed_hand_lifts_the_cube_to_success(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        receipt = self.step(client, action(**{"0": 1.0, "7": 1.0})["values"], ticks=80)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertGreaterEqual(output["tick"], 75)                             # 0.015 m / 0.0002 m per tick
        self.assertLessEqual(output["tick"], 80)
        self.assertEqual(output["reward"], 1.0)
        self.assertGreaterEqual(self.policy(receipt)[OBJECT_POSITION_START + 2], 0.965)
        ended = self.step(client, [0.0] * ACTION_DIM)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_an_open_hand_truncates_at_the_episode_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        receipt = self.step(client, [0.0] * ACTION_DIM, ticks=400)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 400))
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual(self.step(client, [0.0] * ACTION_DIM)["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("isaaclab", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_DIM)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION_DIM), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                        # readable, and not advanced

    def test_reset_options_reach_the_environment(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "the fake accepts options"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)
        self.assertEqual(self.state(client)["tick"], 0)


if __name__ == "__main__":
    unittest.main()
