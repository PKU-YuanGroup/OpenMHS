"""Acceptance run of this driver package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): rware is not installed
where the gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
FAULTED = "MHS.DEVICE.FAULTED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RwareCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None):
        fields = {} if seed is None else {"seed": seed}
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, index, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"items": [index]}}, **self.ids)

    def observation(self, receipt):
        return receipt["output"]["observation"]["items"][0]["values"]

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reset_is_the_registered_one_agent_layout(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=3)
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"]["seed"], 3)
        self.assertEqual(len(first["output"]["observation"]["items"]), 1)
        values = self.observation(first)
        # (4 + 4) self bits + 9 sensor cells * (1 + 4 + 0) agent bits + 9 sensor cells * 2 shelf bits
        self.assertEqual(len(values), 71)
        self.assertIn(values[0], range(10))                                    # x is inside the 10-column grid
        self.assertIn(values[1], range(11))                                    # y is inside the 11-row grid
        self.assertEqual(sum(values[3:7]), 1.0)                                # one direction is set

    def test_a_seed_repeats_the_initial_state(self) -> None:
        client = self.serve()
        first = self.observation(self.reset(client, seed=7))
        second = self.observation(self.reset(client, seed=7))
        self.assertEqual(first, second)
        other = self.observation(self.reset(client, seed=8))
        self.assertNotEqual(first, other)

    def test_forward_moves_and_turning_changes_the_direction(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)                                             # agent at (0, 3), facing down
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed")
        forward = self.observation(receipt)
        self.assertEqual(forward[:2], [0.0, 4.0])
        self.assertEqual(forward[3:7], [0.0, 1.0, 0.0, 0.0])
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["reward"]), (1, 0.0))
        turned = self.step(client, 2)                                          # LEFT from DOWN is RIGHT
        self.assertEqual(turned["status"], "completed")
        self.assertEqual(self.observation(turned)[3:7], [0.0, 0.0, 0.0, 1.0])

    def test_toggle_load_picks_up_and_drops_a_shelf(self) -> None:
        client = self.serve()
        self.reset(client, seed=7)                                             # agent at (1, 4), a shelf cell
        loaded = self.step(client, 4)
        self.assertEqual(loaded["status"], "completed")
        self.assertEqual(self.observation(loaded)[2], 1.0)
        dropped = self.step(client, 4)
        self.assertEqual(dropped["status"], "completed")
        self.assertEqual(self.observation(dropped)[2], 0.0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)
        self.assertEqual(first["output"]["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["output"]["observation"])

    def test_the_registered_max_steps_ends_the_episode(self) -> None:
        client = self.serve()
        self.reset(client, seed=1)
        output = None
        for expected_tick in range(1, 501):
            receipt = self.step(client, 0)                                     # NOOP advances the step counter
            self.assertEqual(receipt["status"], "completed", expected_tick)
            output = receipt["output"]
            self.assertEqual(output["tick"], expected_tick)
        # rware/__init__.py:36 registers max_steps=500 and warehouse.py:936-942 reports done, never truncated
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))

    def test_an_action_outside_the_discrete_space_fails(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        for index in (-1, 5):
            receipt = self.step(client, index)
            self.assertEqual(receipt["status"], "failed", index)
            self.assertEqual(receipt["error"]["mhs_code"], FAULTED, index)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:rware-tiny-1ag-v2", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                         # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
