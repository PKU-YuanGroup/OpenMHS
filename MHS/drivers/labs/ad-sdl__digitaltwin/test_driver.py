"""Acceptance run of the digitaltwin package: the gate, plus cases for this fake.

The cases run on the fake backend only.  The upstream environment needs Isaac Lab, Isaac Sim, torch and a Linux GPU
host, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverDefinitionError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
# A 16-element action inside the fake's placeholder bounds: left pose, left quaternion, left gripper,
# right pose, right quaternion, right gripper (mimic_env.py:13-21).
ACTION = [0.1, 0.2, 0.3, 0.0, 0.0, 0.0, 1.0, 0.5,
          -0.1, -0.2, -0.3, 0.0, 0.0, 0.0, 1.0, 0.5]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DigitalTwinFakeCases(unittest.TestCase):
    def test_the_unsupplied_sim_backend_is_refused_before_construction(self):
        with self.assertRaisesRegex(DriverDefinitionError, "only the fake backend"):
            load_driver(HERE, "sim")

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

    def test_the_sixteen_element_action_order_is_preserved(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed", receipt)
        values = receipt["output"]["observation"]["values"]
        self.assertEqual(len(values), 16)
        for sent, seen in zip(ACTION, values):
            self.assertAlmostEqual(sent, seen, places=6)
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertEqual((receipt["output"]["terminated"], receipt["output"]["truncated"]), (False, False))

    def test_an_out_of_range_action_is_refused_before_the_step(self) -> None:
        client = self.serve()
        refused = self.step(client, [2.0] + ACTION[1:])              # above the fake arm bound (placeholder)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)
        wrong_length = self.step(client, ACTION[:-1])
        self.assertEqual(wrong_length["status"], "rejected")

    def test_a_seed_repeats_the_placeholder_start(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]
        second = self.reset(client, seed=7)["output"]["observation"]
        other = self.reset(client, seed=8)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        reset = self.reset(client)["output"]
        self.assertEqual(reset["seed"], 21)
        direct = self.reset(client, seed=21)["output"]
        self.assertEqual(reset["observation"], direct["observation"])

    def test_the_episode_truncates_at_the_derived_length(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ACTION, ticks=600)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        # env_cfg.py:400 and :399-401: 30.0 s / (0.01 s * 5) = 600 control steps; time_out is a termination term,
        # but the fake models no termination terms and reports only truncation.
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (600, False, True))
        ended = self.step(client, ACTION)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)

    def test_the_fake_fidelity_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["engine"], "analytic:centrifuge-mimic-placeholder")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["timestep_ms"], 50.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_fake(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)


if __name__ == "__main__":
    unittest.main()
