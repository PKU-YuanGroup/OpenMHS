"""Acceptance run of the Jiminy CartPole package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``): the Jiminy engine,
NumPy and Gymnasium are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.
"""

import importlib.util
import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def load_fake():
    """Import the package fake by path (the gate loads test_driver.py without its directory on sys.path)."""
    spec = importlib.util.spec_from_file_location("jiminy_cartpole_fake_for_tests", HERE / "fake.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CartPoleCases(unittest.TestCase):
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

    def test_the_action_space_is_discrete_three(self) -> None:
        client = self.serve()
        for index in (0, 1, 2):
            self.assertEqual(self.step(client, index)["status"], "completed", index)
        for index in (-1, 3):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 3)                 # the refused steps changed nothing

    def test_the_observation_is_the_encoder_layout(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(before), 4)
        self.assertTrue(all(abs(value) <= 0.05 for value in before), before)   # cartpole.py:28-35, 189-193
        after = self.step(client, 2)["output"]["observation"]["values"]
        # a +10 N push accelerates the cart: in the upstream encoder layout the cart velocity is element 2
        # (row Q is [cart position, pole angle], row V is [cart velocity, pole velocity]).
        self.assertGreater(after[2], before[2])

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                      # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in (0, 1, 2, 2, 0)]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        other = self.serve()
        self.assertEqual(self.reset(other, seed=21)["output"]["observation"], first["observation"])

    def test_a_constant_push_truncates_and_pays_reward(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 2, ticks=500)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        # BaseJiminyEnv.has_terminated returns terminated=False and truncates out-of-bounds positions
        # (generic.py:1434-1464); the reward is 1.0 on every step because it is computed from terminated only
        # (cartpole.py:210-216), including the truncating step.
        self.assertEqual((output["terminated"], output["truncated"]), (False, True))
        self.assertGreaterEqual(output["tick"], 1)
        self.assertLess(output["tick"], 500)                            # the bounds truncate before the time limit
        self.assertEqual(output["reward"], float(output["tick"]))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fake_truncates_at_the_registered_time_limit(self) -> None:
        fake = load_fake()
        env = fake.FakeCartPoleJiminyEnv()
        env.reset(seed=0)
        env._state = [0.0, 0.0, 0.0, 0.0]                               # the equilibrium: no force, no motion
        output = None
        for expected in range(1, 501):
            output = env.step(1)
            self.assertEqual(output[0], [0.0, 0.0, 0.0, 0.0], expected)
            self.assertEqual((output[2], output[3]), (False, expected == 500), expected)
        self.assertEqual(output[1], 1.0)
        with self.assertRaises(RuntimeError):
            env.step(1)
        env.close()

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("gymnasium:cartpole", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
