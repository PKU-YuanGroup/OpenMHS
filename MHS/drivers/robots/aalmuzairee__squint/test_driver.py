"""Acceptance run of the squint package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): ManiSkill, SAPIEN and the
GPU stack of the clone are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.  Apart from its action space and joint deltas, which are the upstream's, the fake's numbers are
placeholder test data, not facts or limits of this package.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
NEUTRAL = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SquintCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or NEUTRAL}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def joints(self, client):
        return self.state(client)["observation"]["state"]["values"][:6]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0, 0, 0, 0, 0, -1.0])["status"], "completed")   # normalised: -1 to 1
        for bad in ([1.01, 0, 0, 0, 0, 0], [0, 0, 0, 0, 0, -1.01]):
            refused = self.step(client, bad)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        wrong_length = self.step(client, [0.0] * 5)              # the schema refuses a wrong-shaped action
        self.assertEqual((wrong_length["status"], wrong_length["error"]["mhs_code"]),
                         ("rejected", "MHS.CAPABILITY.INPUT_INVALID"))
        self.assertEqual(self.state(client)["tick"], 1)                      # the refused steps changed nothing

    def test_the_controller_scales_the_action_to_the_joint_deltas(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        before = self.joints(client)
        self.assertEqual(self.step(client, [1.0, -0.5, 0, 0, 0, 1.0])["status"], "completed")
        moved = [after - start for after, start in zip(self.joints(client), before)]
        for got, want in zip(moved, [0.1, -0.05, 0.0, 0.0, 0.0, 0.2]):    # the deltas of envs/robot/so101.py:97-109
            self.assertAlmostEqual(got, want)

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return self.reset(client, seed=seed)["output"]["observation"]

        first = observation(7)
        self.assertEqual(observation(7), first)
        self.assertNotEqual(observation(8), first)

    def test_a_step_changes_the_state_and_the_tick(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        before = self.state(client)["observation"]
        receipt = self.step(client, [0.02, 0, 0, 0, 0, -0.01], ticks=3)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertIsInstance(output["reward"], (int, float))
        after = self.state(client)["observation"]
        self.assertNotEqual(before, after)
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_episode_truncates_at_the_registered_limit(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=50)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["truncated"]), (50, True))
        ended = self.step(client)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")   # a reset starts the next episode
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual(fidelity["engine"], "maniskill3:squint/SO101LiftCube-v1")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
