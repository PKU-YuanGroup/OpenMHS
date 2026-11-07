"""Acceptance run of the BARK-ML highway package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (fake.py): bark-ml itself needs
the compiled bark-simulator package, gym and a display, so nothing here compares the fake with the upstream scene.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
OBSERVATION_LEN = 22


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class HighwayCases(unittest.TestCase):
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

    def step(self, client, acceleration, steering_rate, ticks=1):
        return client.invoke(
            "cap.world.step.v1",
            {"ticks": ticks, "action": {"values": [acceleration, steering_rate]}},
            **self.ids,
        )

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_integrates_the_continuous_action(self) -> None:
        client = self.serve()
        receipt = self.step(client, 1.0, 0.0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        values = output["observation"]["values"]
        self.assertEqual(len(values), OBSERVATION_LEN)
        # the fake starts at rest, so after one 0.2 s step the longitudinal velocity is 0.2 m/s, normalized by 30
        self.assertAlmostEqual(values[3], 0.2 / 30.0, places=9)
        self.assertEqual((output["tick"], self.state(client)["tick"]), (1, 1))

    def test_the_action_envelope_is_the_upstream_action_space(self) -> None:
        client = self.serve()
        for acceleration, steering_rate in ((4.01, 0.0), (-5.01, 0.0), (0.0, 0.21), (0.0, -0.21)):
            refused = self.step(client, acceleration, steering_rate)
            self.assertEqual(refused["status"], "rejected", (acceleration, steering_rate))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (acceleration, steering_rate))
        self.assertEqual(self.state(client)["tick"], 0)                    # no refused action advanced the world
        self.assertEqual(self.step(client, -5.0, -0.2)["status"], "completed")
        self.assertEqual(self.step(client, 4.0, 0.2)["status"], "completed")

    def test_a_reset_restores_the_initial_observation(self) -> None:
        client = self.serve()
        first = self.reset(client)["output"]["observation"]["values"]
        self.step(client, 2.0, 0.1, ticks=3)
        second = self.reset(client)["output"]["observation"]["values"]
        self.assertEqual(first, second)
        state = self.state(client)
        self.assertEqual((state["tick"], state["terminated"], state["truncated"]), (0, False, False))

    def test_the_seed_class_is_accepted_and_echoed(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 42}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual((seeded["output"]["seed"], seeded["output"]["accepted"]), (42, True))
        reset = self.reset(client, seed=42)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 42)

    def test_the_default_step_count_ends_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, 0.0, 0.0, ticks=221)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"]), (221, True))
        ended = self.step(client, 0.0, 0.0)
        self.assertEqual(ended["status"], "failed")
        self.assertEqual(ended["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(self.reset(client)["status"], "completed")        # a reset starts the next episode

    def test_a_lane_departure_ends_the_episode_early(self) -> None:
        client = self.serve()
        receipt = self.step(client, 4.0, 0.2, ticks=50)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertLess(output["tick"], 50)                               # the placeholder lane bound stops the run
        self.assertFalse(output["truncated"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("bark-ml:highway-v0", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (200.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1.0, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1.0, 0.0), self.reset(client)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
