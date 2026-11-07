"""Acceptance run of the manipulator-mujoco package: the gate, plus cases for this driver.

The cases run on the fake backend (fake.py).  The upstream environment needs MuJoCo, dm_control, numpy and
gymnasium, which are not installed where the gate runs, so nothing here compares the fake with the upstream
environment.  Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ZERO_ACTION = {"values": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]}       # placeholder test input, not a fact


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AuboI5Cases(unittest.TestCase):
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

    def step(self, client, action=None, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": dict(action or ZERO_ACTION)},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        for values in ([-0.2] * 6, [0.2] * 6, [-0.1, 0.0, 0.0, 0.0, 0.0, 0.11]):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)       # the refused steps changed nothing

    def test_the_action_shape_is_refused_before_native(self) -> None:
        client = self.serve()
        for values in ([0.0] * 5, [0.0] * 7):
            refused = self.step(client, {"values": values})
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_ticks_are_bounded_by_the_bridge(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = self.step(client, ticks=ticks)
            self.assertEqual(refused["status"], "rejected", ticks)
            # ticks is a schema bound of the bridge input, not a limit rule; the runtime refuses it as an input
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_step_advances_the_tick_and_returns_the_upstream_observation(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        first = self.step(client, {"values": [0.1] * 6})
        self.assertEqual(first["status"], "completed")
        output = first["output"]
        self.assertEqual(output["observation"]["values"], [0.0] * 6)   # _get_obs returns zeros(6)
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        # the upstream step ignores the action, so the opposite action leaves the same observation
        second = self.step(client, {"values": [-0.1] * 6})
        self.assertEqual(second["output"]["observation"], output["observation"])
        self.assertEqual(second["output"]["tick"], 2)
        self.assertNotEqual(second["output"]["state_hash"], output["state_hash"])

    def test_reset_returns_the_start_state_and_echoes_the_seed(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=7)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 7)
        self.assertEqual(receipt["output"]["observation"]["values"], [0.0] * 6)
        self.assertEqual(self.state(client)["tick"], 0)
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        self.assertEqual(self.reset(client)["output"]["seed"], 21)

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=2, options={"anything": 1})   # the environment accepts and ignores options
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 2)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:manipulator_mujoco/AuboI5Env-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (2.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)       # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
