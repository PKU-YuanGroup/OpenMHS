"""Acceptance run of the rl_rvo_nav package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gym 0.20.0, torch and the external ir-sim v2.5, and nothing here imports or runs it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RlRvoNavCases(unittest.TestCase):
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

    def step(self, client, robots, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"robots": robots}}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reset_returns_the_per_robot_observations(self) -> None:
        client = self.serve()
        receipt = self.reset(client, options={"mode": 0})
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["seed"], 0)                       # the clone has no seed; the class requires the field
        self.assertEqual(len(output["observation"]["robots"]), 2)
        for observation in output["observation"]["robots"]:
            self.assertEqual(len(observation), 14)                # 6 proprioceptive + rvo_state_dim 8
        self.assertEqual(self.state(client)["tick"], 0)

    def test_step_applies_the_commands_and_counts_ticks(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        receipt = self.step(client, [[0.5, 0.0], [0.0, -0.25]], ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 2)
        self.assertEqual(output["truncated"], False)
        first, second = output["observation"]["robots"]
        self.assertEqual(first[0:2], [0.5, 0.0])
        self.assertEqual(second[0:2], [0.0, -0.25])
        self.assertEqual(self.state(client)["tick"], 2)

    def test_a_step_needs_one_velocity_pair_per_command(self) -> None:
        client = self.serve()
        for action in ({}, {"robots": []}, {"robots": [[0.1]]}):
            receipt = client.invoke("cap.world.step.v1", {"ticks": 1, "action": action}, **self.ids)
            self.assertEqual(receipt["status"], "rejected", action)
            self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID, action)
        self.assertEqual(self.state(client)["tick"], 0, "a refused step must not advance the world")

    def test_the_reset_mode_is_checked_before_the_native_call(self) -> None:
        client = self.serve()
        refused = self.reset(client, options={"mode": "circle"})
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("ir-sim", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (100.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [[0.1, 0.0]])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [[0.1, 0.0]]), self.reset(client)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)            # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
