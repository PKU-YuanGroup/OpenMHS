"""Acceptance run of the Gym-Gazebo-Sim CartpoleEnv driver: the gate, plus driver-specific cases.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py):
Gazebo, ROS 2 and the upstream package are not installed where the gate runs, so nothing
here compares the fake with a live simulator.  The expected numbers are the fake's own
kinematics, not device facts.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
STEP_S = 0.01          # fake.py: placeholder bookkeeping interval
VELOCITY_STEP = 0.2    # src/gym_gazebo/envs/cartpole_env.py:137


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartpoleCases(unittest.TestCase):
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

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        for index in (-1, 2):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 1)   # the refused steps changed nothing

    def test_reset_returns_the_four_value_state(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=4)["output"]
        self.assertEqual(output["seed"], 4)
        values = output["observation"]["values"]
        self.assertEqual(values, [0.0, 0.0, 0.0, 0.0])    # fake start state, placeholder

    def test_the_action_rule_and_state_order(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, 1)["output"]["observation"]["values"]
        self.assertEqual(first[0], round(VELOCITY_STEP * STEP_S, 2))
        self.assertEqual(first[1], VELOCITY_STEP)
        self.assertEqual(first[2:], [0.0, 0.0])          # the fake models no pole dynamics
        second = self.step(client, 1)["output"]["observation"]["values"]
        self.assertEqual(second[1], 2 * VELOCITY_STEP)
        third = self.step(client, 0)["output"]["observation"]["values"]
        self.assertEqual(third[1], VELOCITY_STEP)         # action != 1 decrements the velocity

    def test_the_cart_terminates_past_the_x_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 1, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertEqual(output["reward"], 121.0)   # 121 in-bounds ticks plus the 0.0 terminal tick
        # x = 0.01 * sum(0.2 * i) = 0.001 * n * (n + 1); 15 is first exceeded at n = 122
        self.assertEqual(output["tick"], 122)
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_is_recorded_for_the_next_reset_fake_only(self) -> None:
        """Fake-only: upstream CartpoleEnv.reset ignores seed and options and returns the next /joint_states
        sample from Gazebo (src/gym_gazebo/envs/cartpole_env.py:82-124), so equal observations after equally
        seeded resets come from the fake's constant placeholder start state, not from an upstream property."""
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], second["observation"])   # fake-only, see the docstring

    def test_reset_accepts_options(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3, options={"unused": True})["status"], "completed")
        self.assertEqual(self.reset(client, options={"another": 1})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:cartpole-env-v0-fake (no physics)", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
