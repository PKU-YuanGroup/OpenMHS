"""Acceptance run of the Meta-World package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): metaworld, MuJoCo and
numpy are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = {"values": [0.0, 0.0, 0.0, 0.0]}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AssemblyCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": values or ZERO}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        for values in ({"values": [1.5, 0.0, 0.0, 0.0]}, {"values": [0.0, -1.5, 0.0, 0.0]},
                       {"values": [0.0, 0.0, 1.5, 0.0]}, {"values": [0.0, 0.0, 0.0, -1.5]}):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_step_is_a_translation_of_the_hand(self) -> None:
        client = self.serve()
        start = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(start), 39)                                         # sawyer_xyz_env.py:513-527
        self.assertEqual(start[:3], [0.0, 0.6, 0.2])                             # placeholder start of the fake
        receipt = self.step(client, {"values": [1.0, -1.0, 0.0, 0.0]})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        # action * action_scale (1/100) moves the hand (sawyer_xyz_env.py:320-336, :182)
        self.assertAlmostEqual(values[0], 0.01, places=7)
        self.assertAlmostEqual(values[1], 0.59, places=7)
        self.assertAlmostEqual(values[2], 0.2, places=7)
        self.assertEqual((output["tick"], output["reward"], output["terminated"], output["truncated"]), (1, 0.0, False, False))
        self.assertEqual(len(values), 39)

    def test_reset_ignores_its_seed_like_upstream(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=1)["output"]
        second = self.reset(client, seed=2)["output"]
        # SawyerXYZEnv.reset ignores seed and options (sawyer_xyz_env.py:664-682); the receipt still echoes it
        self.assertEqual((first["seed"], second["seed"]), (1, 2))
        self.assertEqual(first["observation"], second["observation"])

    def test_the_seed_class_is_recorded_but_does_not_reseed(self) -> None:
        client = self.serve()
        before = self.reset(client)["output"]["observation"]
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        after = self.reset(client)["output"]
        self.assertEqual(after["seed"], 21)
        self.assertEqual(after["observation"], before)                            # the fake never reseeds

    def test_the_task_horizon_truncates_at_500_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, ticks=500)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        # max_path_length is 500 (sawyer_xyz_env.py:153-154); the last step sets truncated, never terminated
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (500, False, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        summary = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(summary["risk_class"], "R0")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:metaworld/SawyerNutAssemblyEnvV3", "F1"))
        self.assertEqual((fidelity["determinism"]["kind"], fidelity["determinism"]["seed_control"]),
                         ("seeded", "none"))
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.5, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
