"""Acceptance run of the MetaGym Bandits package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gym is
not installed here and the fake needs only the Python standard library, so nothing here compares the
fake with the upstream environment.  The action bound (0 through 49) comes from the registered
bandits-v0 kwargs (``metagym/bandits/__init__.py:21``) and is derived by the bridge from the fake's
Discrete space.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BanditsCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client):
        return client.invoke("cap.world.reset.v1", {}, **self.ids)

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"index": index}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        self.assertEqual(self.step(client, 49)["status"], "completed")
        for index in (-1, 50):
            refused = self.step(client, index)
            self.assertEqual(refused["status"], "rejected", index)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, index)
        self.assertEqual(self.state(client)["tick"], 2)                    # the refused steps changed nothing

    def test_a_reset_returns_the_empty_observation_of_bandits(self) -> None:
        client = self.serve()
        receipt = self.reset(client)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"], {})              # observation_space is None
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_is_one_bernoulli_pull(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 0)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertIn(output["reward"], (0.0, 1.0))                        # bandits_env.py:73
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["observation"], {})
        self.assertEqual(self.state(client)["tick"], 1)

    def test_an_episode_ends_at_max_steps_and_a_reset_starts_the_next(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, 0, ticks=1000)                         # max_steps=1000 (__init__.py:22)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 1000))
        self.assertGreaterEqual(output["reward"], 0.0)
        self.assertLessEqual(output["reward"], 1000.0)
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client),
                        client.invoke("cap.world.seed.v1", {"seed": 7}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("metagym:bandits-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "statistical")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)


if __name__ == "__main__":
    unittest.main()
