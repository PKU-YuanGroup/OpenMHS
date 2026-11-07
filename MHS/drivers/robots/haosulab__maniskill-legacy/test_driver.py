"""Acceptance run of the ManiSkill legacy package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the analytics fake backend (fake.py); the upstream
SAPIEN environment is not installed where the gate runs and package code never imports the clone, so nothing here
compares the fake with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION_DIM = 13


def action(value=0.0, **overrides):
    values = [value] * ACTION_DIM
    for index, item in overrides.items():
        values[int(index[1:])] = item
    return values


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpenCabinetDoorCases(unittest.TestCase):
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
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values or action()}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action(1.0))["status"], "completed")
        for values in (action(0.0, v0=1.5), action(0.0, v12=-1.5)):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                  # the refused steps changed nothing

    def test_the_action_opens_the_target_joint(self) -> None:
        client = self.serve()
        before = self.reset(client, seed=3)["output"]["observation"]["values"]
        self.assertEqual(len(before), 75)
        self.assertEqual(before[29], 1.0)                                # one target indicator
        receipt = self.step(client, action(1.0))
        self.assertEqual(receipt["status"], "completed")
        # fake.py: a first-order drawer moves by 0.05 per step at a full command; this is test data
        self.assertAlmostEqual(receipt["output"]["observation"]["values"][13], before[13] + 0.05, places=9)
        self.assertAlmostEqual(receipt["output"]["reward"], before[13] + 0.05 - 0.9, places=9)
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["terminated"]), (1, False))

    def test_a_seed_repeats_the_reset(self) -> None:
        def first(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]["values"]

        self.assertEqual(first(11), first(11))
        self.assertNotEqual(first(11), first(12))

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        seeded = self.reset(client)["output"]
        self.assertEqual(seeded["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], seeded["observation"])

    def test_success_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=0)
        for expected_tick in range(1, 19):
            receipt = self.step(client, action(1.0))
            self.assertEqual(receipt["status"], "completed", expected_tick)
            if not receipt["output"]["terminated"]:
                self.assertLess(receipt["output"]["observation"]["values"][13], 0.9)
        self.assertTrue(receipt["output"]["terminated"])
        self.assertEqual(receipt["output"]["observation"]["values"][13], 0.9)  # open_extent 0.9 (config:49)
        ended = self.step(client, action(1.0))
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_stalled_drawer_is_capped_at_200_steps(self) -> None:
        client = self.serve()
        self.reset(client, seed=0)
        output = None
        for expected_tick in range(1, 201):
            receipt = self.step(client, action(-1.0))
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        self.assertTrue(output["terminated"])
        self.assertEqual(output["observation"]["values"][13], 0.0)
        self.assertEqual(self.step(client, action(0.0))["error"]["mhs_code"], PRECONDITION)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        announced = client.hello()["devices"][0]
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(announced["mode"], "simulated")
        self.assertEqual(announced["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:mani_skill_open_cabinet_door_v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action(1.0))["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action(1.0)), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                  # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
