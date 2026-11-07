"""Acceptance run of the SustainDC package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every case runs on the fake backend (fake.py): the upstream package
was not installed and no upstream run is compared with the fake.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
OBS_SIZES = {"agent_ls": 26, "agent_dc": 14, "agent_bat": 13}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SustainDCCases(unittest.TestCase):
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

    def step(self, client, action, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_three_agent_action_spaces_are_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"agent_ls": 1, "agent_dc": 1, "agent_bat": 1})["status"], "completed")
        for bad in ({"agent_ls": -1, "agent_dc": 1, "agent_bat": 1},
                    {"agent_ls": 1, "agent_dc": 3, "agent_bat": 1},
                    {"agent_ls": 1, "agent_dc": 1, "agent_bat": 4}):
            refused = self.step(client, bad)
            self.assertEqual(refused["status"], "rejected", bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        self.assertEqual(self.state(client)["tick"], 1)                          # the refused steps changed nothing

    def test_a_missing_agent_is_an_input_error(self) -> None:
        client = self.serve()
        refused = self.step(client, {"agent_ls": 1, "agent_dc": 1})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_reset_returns_one_state_per_agent(self) -> None:
        client = self.serve()
        output = self.reset(client, seed=7)["output"]
        observation = output["observation"]
        self.assertEqual(sorted(observation), sorted(OBS_SIZES))
        for name, size in OBS_SIZES.items():
            self.assertEqual(len(observation[name]["values"]), size, name)
        self.assertEqual(output["seed"], 7)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        actions = ({"agent_ls": 0, "agent_dc": 1, "agent_bat": 2},
                   {"agent_ls": 1, "agent_dc": 0, "agent_bat": 1},
                   {"agent_ls": 2, "agent_dc": 2, "agent_bat": 0})

        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            return [self.step(client, action)["output"]["state_hash"] for action in actions]

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_step_advances_the_tick_and_the_state(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]
        receipt = self.step(client, {"agent_ls": 0, "agent_dc": 1, "agent_bat": 2})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["terminated"], False)
        self.assertEqual(output["truncated"], False)
        self.assertAlmostEqual(output["reward"], -0.08, places=7)          # placeholder reward of the fake
        self.assertNotEqual(output["observation"], before)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_options_object_is_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5, options={"note": "the fake ignores options"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 5)

    def test_the_episode_truncates_at_the_fake_length(self) -> None:
        client = self.serve()
        action = {"agent_ls": 1, "agent_dc": 1, "agent_bat": 1}
        receipt = self.step(client, action, ticks=672)                    # placeholder: the fake's episode length
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((receipt["output"]["truncated"], receipt["output"]["terminated"]), (True, False))
        ended = self.step(client, action)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("sustaindc:SustainDC", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (900000.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, {"agent_ls": 1, "agent_dc": 1, "agent_bat": 1})["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, {"agent_ls": 1, "agent_dc": 1, "agent_bat": 1}),
                        self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
