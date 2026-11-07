"""Acceptance run of the gazebo_gymnasium package: the gate, plus cases for this driver.

The cases run on the analytic fake backend (fake.py).  The real environment needs
the native gz.sim8 bindings and the ROS 2 Jazzy/Gazebo Harmonic stack
(inprocess_vec_env.py:476-480, README.md:61-63), so nothing here compares the fake
with a Gazebo run.
"""

import unittest
from pathlib import Path

from mhs import canonical
from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
# agent_spec.py:221-222 and 776-779: 500 transitions, both termination thresholds.
MAX_EPISODE_STEPS = 500


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GazeboCartPoleCases(unittest.TestCase):
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

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    @staticmethod
    def values(receipt):
        return receipt["output"]["observation"]["values"]

    def test_the_action_space_is_discrete_two(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (2, -1):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        missing = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(missing["status"], "rejected")
        self.assertEqual(missing["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)          # refused steps changed nothing

    def test_a_step_command_id_replays_without_stepping_again(self) -> None:
        client = self.serve()
        command_id = canonical.ulid()
        payload = {"ticks": 1, "action": {"index": 0}}
        first = client.invoke("cap.world.step.v1", payload, command_id=command_id, **self.ids)
        second = client.invoke("cap.world.step.v1", payload, command_id=command_id, **self.ids)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(second["status"], "completed")
        self.assertTrue(second.get("replayed"))
        self.assertEqual(second["receipt_id"], first["receipt_id"])
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_returns_the_five_value_gymnasium_result(self) -> None:
        client = self.serve()
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["reward"], 1.0)                  # agent_spec.py:776
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["tick"], 1)
        self.assertEqual(len(self.values(receipt)), 4)           # agent_spec.py:762-767
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_pole_falls_and_the_episode_must_be_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        output = None
        for _ in range(20):
            receipt = self.step(client, 1)                       # push one way: agent_spec.py:740-748
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"]:
                break
        self.assertIsNotNone(output)
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")

    def test_the_episode_truncates_at_500_transitions(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        output = None
        for _ in range(MAX_EPISODE_STEPS):
            observation = self.state(client)["observation"]["values"]
            _x, x_dot, theta, theta_dot = observation
            # A balancing action from the observed state; the thresholds stay upstream's.
            index = 1 if theta + 0.3 * theta_dot + 0.2 * _x + 0.1 * x_dot > 0 else 0
            receipt = self.step(client, index)
            self.assertEqual(receipt["status"], "completed")
            output = receipt["output"]
            if output["terminated"] or output["truncated"]:
                break
        self.assertIsNotNone(output)
        self.assertFalse(output["terminated"])
        self.assertTrue(output["truncated"])
        self.assertEqual(output["tick"], MAX_EPISODE_STEPS)
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_the_seed_repeats_the_reset_observation(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)["output"]["observation"]["values"]
        second = self.reset(client, seed=3)["output"]["observation"]["values"]
        third = self.reset(client, seed=4)["output"]["observation"]["values"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, third)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])

    def test_an_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)           # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("GazeboCartPole-v0", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
