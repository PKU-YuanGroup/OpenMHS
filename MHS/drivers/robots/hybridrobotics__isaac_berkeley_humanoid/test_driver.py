"""Acceptance run of the Berkeley Humanoid rough-task package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): Isaac Sim, Isaac Lab and
the upstream task are not installed where the gate runs, so nothing here compares the stand-in with the upstream
environment and no simulator or hardware run is claimed.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
ACTION = [0.1, -0.2, 0.3, -0.4, 0.5, -0.6, 0.7, -0.8, 0.9, -1.0, 1.1, -1.2]
# fake.py: three placeholder base values followed by the 12-value last-action term.
BASE_VALUES = 3
OBSERVATION = BASE_VALUES + len(ACTION)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BerkeleyHumanoidCases(unittest.TestCase):
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

    def seed_next(self, client, seed):
        return client.invoke("cap.world.seed.v1", {"seed": seed}, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_is_twelve_values(self) -> None:
        client = self.serve()
        receipt = self.step(client, ACTION)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        observation = output["observation"]["values"]
        self.assertEqual(len(observation), OBSERVATION)
        # the last-action term of the policy observation is the applied action (velocity_env_cfg.py:143).
        self.assertEqual(observation[BASE_VALUES:], ACTION)
        self.assertEqual((output["reward"], output["tick"]), (0.0, 1))
        refused = self.step(client, ACTION[:-1])
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 1)  # the refused step changed nothing

    def test_the_action_space_is_unbounded_in_the_fake(self) -> None:
        client = self.serve()
        # The action-space object is built by the external ManagerBasedRLEnv and its bounds were not inspected, so
        # this package publishes no finite envelope and the bridge accepts large values.
        self.assertEqual(self.step(client, [1.0e6] * len(ACTION))["status"], "completed")

    def test_ticks_advance_the_world_and_the_last_action(self) -> None:
        client = self.serve()
        first = self.step(client, ACTION, ticks=1)
        self.assertEqual(first["output"]["tick"], 1)
        second = self.step(client, [0.0] * len(ACTION), ticks=2)
        output = second["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(output["observation"]["values"][BASE_VALUES:], [0.0] * len(ACTION))
        self.assertEqual(self.state(client)["tick"], 3)

    def test_the_fake_never_terminates(self) -> None:
        client = self.serve()
        output = self.step(client, ACTION, ticks=4)["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(output["tick"], 4)

    def test_a_seed_repeats_the_reset(self) -> None:
        def observation(seed):
            client = self.serve()
            receipt = self.reset(client, seed=seed)
            self.assertEqual(receipt["status"], "completed", receipt)
            return receipt["output"]["observation"]["values"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["output"]["seed"], 5)
        self.assertEqual(self.seed_next(client, 21)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"note": "the fake accepts and ignores reset options"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 2)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mhs-fake:Velocity-Rough-Berkeley-Humanoid-v0")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ACTION), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
