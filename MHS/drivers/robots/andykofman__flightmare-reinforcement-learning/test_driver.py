"""Acceptance run of the Flightmare FlightEnvVec package: the gate plus repository-specific cases.

The cases run on the package fake backend (fake.py).  The clone was not
imported, the flightgym extension was not built and no simulator or hardware
was contacted.
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
OBSERVATION_SIZE = 12
ACTION_SIZE = 4


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlightEnvVecCases(unittest.TestCase):
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

    def test_the_action_space_is_normalized_to_the_upstream_bounds(self) -> None:
        client = self.serve()
        for values in ([-1.0] * ACTION_SIZE, [1.0] * ACTION_SIZE, [0.0] * ACTION_SIZE):
            receipt = self.step(client, values)
            self.assertEqual(receipt["status"], "completed", receipt)
        for values in ([1.5] + [0.0] * (ACTION_SIZE - 1), [-1.5] + [0.0] * (ACTION_SIZE - 1)):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 3)                     # refused steps changed nothing

    def test_a_malformed_action_is_rejected_before_the_environment(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0] * (ACTION_SIZE - 1))
        self.assertEqual(receipt["status"], "rejected")
        self.assertIn(receipt["error"]["mhs_code"], (ENVELOPE, "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_returns_the_first_environment_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=4)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = receipt["output"]["observation"]["values"]
        self.assertEqual(len(observation), OBSERVATION_SIZE)
        # The random reset draws z as a uniform [-1, 1] value plus 5
        # (quadrotor_env.cpp:92), so the altitude starts between 4 and 6.
        self.assertGreaterEqual(observation[2], 4.0)
        self.assertLessEqual(observation[2], 6.0)
        self.assertEqual(receipt["output"]["seed"], 4)

    def test_the_fake_repeats_a_seeded_start_state(self) -> None:
        # Fake and bridge contract only (model review of 2026-11-04): upstream EnvBase::setSeed calls std::srand,
        # while the reset draws from an mt19937 seeded from std::random_device (env_base.hpp:39, 60-62), so a
        # live flightgym backend would not repeat this start state.
        client = self.serve()
        first = self.reset(client, seed=11)["output"]["observation"]
        second = self.reset(client, seed=11)["output"]["observation"]
        third = self.reset(client, seed=12)["output"]["observation"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        # The bridge passes the stored seed to the next reset; the repeated observation is fake behaviour
        # (see test_the_fake_repeats_a_seeded_start_state).
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(first["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_a_hovering_action_is_truncated_at_the_wrapper_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        receipt = self.step(client, [0.0] * ACTION_SIZE, ticks=300)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 300))
        ended = self.step(client, [0.0] * ACTION_SIZE)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=2)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_descending_action_reaches_the_terminal_altitude(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        output = self.step(client, [-1.0] * ACTION_SIZE, ticks=300)["output"]
        self.assertTrue(output["terminated"], output)
        self.assertFalse(output["truncated"], output)
        self.assertGreaterEqual(output["tick"], 1)
        self.assertLess(output["tick"], 300)
        self.assertTrue(math.isfinite(output["reward"]))
        # A terminal environment is reset inside the vectorized per-agent step
        # (vec_env.cpp:159-162), so the observation is a fresh one.
        self.assertGreaterEqual(output["observation"]["values"][2], 4.0)
        ended = self.step(client, [0.0] * ACTION_SIZE)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_reset_options_are_accepted_and_unused(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5, options={"unused_upstream": True})
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * ACTION_SIZE)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * ACTION_SIZE), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)                     # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
