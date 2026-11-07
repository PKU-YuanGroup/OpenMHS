"""Acceptance run of the Genesis humanoid package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream environment
needs Python 3.10 and genesis-world/torch/stable-baselines3, which are not installed where the gate runs, so nothing
here compares the fake with the upstream simulator.  The fake's joint count is test data; the cases derive it from
the length of the reset observation instead of hard-coding it.
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


class GenesisHumanoidCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, **fields):
        receipt = client.invoke("cap.world.reset.v1", fields, **self.ids)
        if receipt.get("status") == "completed":
            self.values = receipt["output"]["observation"]["values"]
            self.joints = (len(self.values) - 8) // 3
        return receipt

    def step(self, client, value=0.0, ticks=1):
        values = [value] * self.joints
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        for value in (1.0, -1.0):                                      # the bounds themselves are accepted
            self.assertEqual(self.step(client, value)["status"], "completed")
        tick = self.state(client)["tick"]
        for values in ([1.5] + [0.0] * (self.joints - 1), [0.0] * (self.joints - 1) + [-1.5]):
            refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": values}}, **self.ids)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], tick)              # refused steps changed nothing

    def test_the_observation_and_reward_follow_the_upstream_layout(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)
        values = self.values
        self.assertEqual(len(values), 3 * self.joints + 8)
        self.assertEqual(values[0:3], [0.0, 0.0, 1.0])                  # spawn (humanoid_env.py:104)
        self.assertEqual(values[3:7], [0.0, 0.0, 0.0, 1.0])             # identity quaternion
        self.assertTrue(all(value == 0.0 for value in values[7:7 + 3 * self.joints]))
        self.assertEqual(values[7 + 3 * self.joints], 1.0)              # target_velocity default (line 38)
        stepped = self.step(client, 1.0)
        self.assertEqual(stepped["status"], "completed")
        output = stepped["output"]
        observed = output["observation"]["values"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (1, False, False))
        for value in observed[7:7 + self.joints]:                       # action * 0.1 (lines 163-165)
            self.assertAlmostEqual(value, 0.1, places=7)
        for value in observed[7 + self.joints:7 + 2 * self.joints]:     # 0.1 over dt 1/20 = 2.0
            self.assertAlmostEqual(value, 2.0, places=7)
        self.assertEqual(observed[7 + 2 * self.joints:7 + 3 * self.joints],
                         [0.0] * self.joints)                           # still the previous action
        # 0.5 stability + 0.3 * (1 - |1.0 - 0.8|) height - 0.1 * 4 energy - 0.1 * 1 smoothness = 0.24
        self.assertAlmostEqual(output["reward"], 0.24, places=7)
        second = self.step(client, 0.0)["output"]
        previous = second["observation"]["values"][7 + 2 * self.joints:7 + 3 * self.joints]
        self.assertEqual(previous, [1.0] * self.joints)                 # the first action is now the previous one
        self.assertAlmostEqual(second["reward"], 0.64, places=7)        # smoothness penalty 0.1 now

    def test_a_seed_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        again = self.reset(client, seed=21)["output"]
        self.assertEqual(first["observation"], again["observation"])

    def test_an_episode_is_truncated_at_episode_length(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, 0.0, ticks=1000)                    # episode_length default (line 37)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 1000))
        ended = self.step(client, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("genesis", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                 # readable, and not advanced

    def test_reset_options_are_accepted_and_ignored(self) -> None:
        client = self.serve()
        plain = self.reset(client, seed=3)["output"]["observation"]
        with_options = self.reset(client, seed=3, options={"note": "the upstream reset ignores options"})["output"]
        self.assertEqual(with_options["observation"], plain)


if __name__ == "__main__":
    unittest.main()
