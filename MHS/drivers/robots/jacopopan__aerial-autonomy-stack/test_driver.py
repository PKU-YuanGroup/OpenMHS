"""Acceptance run of the AASEnv-v0 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream
Docker/Gazebo/PX4 stack was not run, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
# The fake's nominal control period: gym_freq_hz defaults to 50 (aas_env.py:20), and the bridge targets
# step_size * physics_dt (simulation.yml.erb:38-42 and zeromq_bridge.cpp:197).
CONTROL_PERIOD_S = 0.02
# max_steps = int(MAX_EPISODE_LENGTH_SEC * GYM_FREQ_HZ) = int(300.0 * 50) (aas_env.py:33-51).
MAX_EPISODE_STEPS = 15000


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AASEnvCases(unittest.TestCase):
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

    def step(self, client, value, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": [value]}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        for value in (1.5, -1.5):
            refused = self.step(client, value)
            self.assertEqual(refused["status"], "rejected", value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        for values in ([], [0.0, 0.0]):
            refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"values": values}}, **self.ids)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 1)                   # the refused steps changed nothing

    def test_the_clock_advances_by_the_control_period(self) -> None:
        client = self.serve()
        start = self.reset(client)["output"]["observation"]["values"]
        receipt = self.step(client, 0.5, ticks=3)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]["values"]
        elapsed = (observation[0] + observation[1] * 1e-9) - (start[0] + start[1] * 1e-9)
        self.assertAlmostEqual(elapsed, 3 * CONTROL_PERIOD_S, places=6)
        self.assertEqual(observation[1], 60_000_000)                     # 60 ms does not carry into a second
        self.assertEqual((receipt["output"]["tick"], receipt["output"]["terminated"]), (3, False))

    def test_each_step_pays_minus_one(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        output = self.step(client, -0.25, ticks=4)["output"]
        # aas_env.py:385-391: reward -1.0 per step, terminated False, truncated only at max_steps
        self.assertEqual((output["reward"], output["terminated"], output["truncated"]), (-4.0, False, False))
        self.assertEqual(output["tick"], 4)

    def test_the_episode_is_truncated_at_max_steps(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client)["status"], "completed")
        first = self.step(client, 0.0, ticks=MAX_EPISODE_STEPS - 5000)["output"]
        self.assertEqual((first["truncated"], first["tick"]), (False, MAX_EPISODE_STEPS - 5000))
        second = self.step(client, 0.0, ticks=5000)["output"]
        self.assertEqual((second["truncated"], second["tick"]), (True, MAX_EPISODE_STEPS))
        self.assertEqual(second["reward"], -5000.0)
        ended = self.step(client, 0.0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.state(client)["tick"], MAX_EPISODE_STEPS)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(second["seed"], 7)

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3, options={"note": "accepted and ignored by AASEnv.reset"})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("analytic", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (20.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 6)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 0.0)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 0.0), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                   # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
