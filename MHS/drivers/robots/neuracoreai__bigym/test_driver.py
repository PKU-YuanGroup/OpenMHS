"""Acceptance run of the BiGym DrawerTopOpen package: the gate plus cases specific to this driver.

The cases run on the package's analytic fake backend (fake.py).  The upstream MuJoCo environment is not installed
and is never imported, so nothing here compares the fake with a real BiGym run.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


def values(floating=(0.0, 0.0, 0.0), arm=0.0, grippers=(0.5, 0.5)):
    """A 15-value action for the fake's default H1 stand-in configuration."""
    return {"values": list(floating) + [arm] * 10 + list(grippers)}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DrawerTopOpenCases(unittest.TestCase):
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

    def test_the_action_space_is_the_fake_box(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, values())["status"], "completed")
        for action in (values(floating=(0.02, 0.0, 0.0)), values(grippers=(1.5, 0.5))):
            refused = self.step(client, action)
            self.assertEqual(refused["status"], "rejected", action)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, action)
        self.assertEqual(self.state(client)["tick"], 1)                           # the refused steps changed nothing

    def test_the_observation_shape_is_the_fake_stand_in(self) -> None:
        client = self.serve()
        observation = self.step(client, values(arm=0.05))["output"]["observation"]
        self.assertEqual(sorted(observation), [
            "proprioception",
            "proprioception_floating_base",
            "proprioception_floating_base_actions",
            "proprioception_grippers",
        ])
        self.assertEqual(len(observation["proprioception"]["values"]), 4)
        self.assertEqual(len(observation["proprioception_grippers"]["values"]), 2)
        self.assertEqual(len(observation["proprioception_floating_base"]["values"]), 3)
        self.assertEqual(len(observation["proprioception_floating_base_actions"]["values"]), 3)

    def test_a_seed_repeats_the_reset_and_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)
        self.assertEqual((first["status"], first["output"]["seed"]), ("completed", 7))
        second = self.reset(client, seed=7)
        self.assertEqual(second["output"]["observation"], first["output"]["observation"])
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        from_class = self.reset(client)["output"]
        self.assertEqual(from_class["seed"], 21)
        self.assertEqual(from_class["observation"], self.reset(client, seed=21)["output"]["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3, options={"comment": "ignored by the upstream task"})
        self.assertEqual((receipt["status"], receipt["output"]["seed"]), ("completed", 3))

    def test_opening_the_last_drawer_terminates_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, values(arm=0.1), ticks=10)                    # 10 x 0.1 progress on the last drawer
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (True, False, 10))
        self.assertEqual(output["reward"], 1.0)
        ended = self.step(client, values())
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_leaving_the_workspace_fails_the_episode(self) -> None:
        client = self.serve()
        receipt = self.step(client, values(floating=(0.01, 0.0, 0.0)), ticks=1100)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(output["reward"], 0.0)
        self.assertGreaterEqual(output["tick"], 1021)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:bigym-DrawerTopOpen", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, values())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, values()), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
