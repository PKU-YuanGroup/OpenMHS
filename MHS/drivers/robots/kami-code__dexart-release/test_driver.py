"""Acceptance run of the DexArt package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Everything runs on the fake backend; the upstream environment is
never imported or run (the gate cannot install the Sapien stack and the clone is read-only).
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ACTION_DIM = 22
OBS_DIM = 32
ACTION = {"values": [0.0] * ACTION_DIM}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DexArtLaptopCases(unittest.TestCase):
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

    def step(self, client, ticks=1, action=None):
        fields = {"ticks": ticks}
        if action is not None:
            fields["action"] = action
        return client.invoke("cap.world.step.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_step_advances_one_tick_and_returns_the_legacy_four_tuple(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        receipt = self.step(client, action=ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["reward"]), (1, 0.0))
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        self.assertEqual(len(output["observation"]["values"]), OBS_DIM)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (1, 1))
        self.assertEqual(state["reward"], 0.0)

    def test_a_reset_starts_an_episode_and_echoes_the_seed(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=11)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 11)
        self.assertEqual(len(first["output"]["observation"]["values"]), OBS_DIM)
        self.assertEqual(self.state(client)["tick"], 0)
        second = self.reset(client, seed=12)
        self.assertEqual(second["status"], "completed")
        self.assertEqual(second["output"]["seed"], 12)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 2))

    def test_a_seed_repeats_the_fake_draw(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]["values"]
        second = self.reset(client, seed=7)["output"]["observation"]["values"]
        other = self.reset(client, seed=8)["output"]["observation"]["values"]
        self.assertEqual(first, second)
        self.assertNotEqual(first, other)

    def test_the_seed_capability_sets_the_next_reset(self) -> None:
        client = self.serve()
        seeded = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(seeded["status"], "completed")
        self.assertEqual(seeded["output"], {"seed": 21, "accepted": True})
        reset = self.reset(client)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 21)

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        refused = self.step(client, action={"values": [2.0] * ACTION_DIM})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE))
        too_short = self.step(client, action={"values": [0.0] * (ACTION_DIM - 1)})
        self.assertEqual((too_short["status"], too_short["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_step_without_an_action_is_refused_without_advancing(self) -> None:
        client = self.serve()
        self.reset(client, seed=4)
        refused = self.step(client)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", INPUT_INVALID))
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_laptop_horizon_terminates_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        receipt = self.step(client, ticks=250, action=ACTION)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (250, True, False))
        ended = self.step(client, action=ACTION)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_world(self) -> None:
        client = self.serve()
        self.reset(client, seed=2)
        self.assertEqual(self.step(client, action=ACTION)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action=ACTION), self.reset(client, seed=2)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic:dexart-laptop", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual(fidelity["timestep_ms"], 40.0)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)


if __name__ == "__main__":
    unittest.main()
