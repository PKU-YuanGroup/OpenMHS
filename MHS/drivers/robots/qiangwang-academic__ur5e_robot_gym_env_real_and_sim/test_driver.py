"""Acceptance run of the UR5 reaching package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py).  The upstream simulator is not installed or imported: it needs
CoppeliaSim and the legacy remote API, so the fake is the only executable stand-in here.  Add cases, never remove
the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
ZERO = [0.0, 0.0, 0.0, 0.0]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UR5Cases(unittest.TestCase):
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

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [-5.0, -5.0, -5.0, -5.0])["status"], "completed")
        self.assertEqual(self.step(client, [5.0, 5.0, 5.0, 5.0])["status"], "completed")
        before = self.state(client)["tick"]
        for values in ([-5.1, 0.0, 0.0, 0.0], [0.0, 5.1, 0.0, 0.0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], before)       # the refused steps changed nothing

    def test_a_zero_action_advances_the_tick_without_terminating(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["tick"], output["terminated"], output["truncated"]), (5, False, False))
        self.assertIsInstance(output["reward"], float)

    def test_a_seed_repeats_the_reset_and_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                   # a fresh world: the hash counts episodes
            first = self.reset(client, seed=seed)["output"]
            hashes = [first["observation"]]
            hashes.append(self.step(client, ZERO)["output"]["state_hash"])
            return first["seed"], hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_stay_detector_reports_status_3(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5)["status"], "completed")
        self.assertEqual(self.step(client, ZERO, ticks=31)["status"], "completed")
        # v3:299-329: after 30 equal tip positions the clone reports step_end_status 3 and resets the target
        self.assertEqual(self.state(client)["info"]["step_end_status"], 3)

    def test_the_observation_is_the_small_fake_image(self) -> None:
        client = self.serve()
        values = self.reset(client, seed=7)["output"]["observation"]["values"]
        self.assertEqual((len(values), len(values[0]), len(values[0][0])), (4, 4, 3))
        gaps = " ".join(client.inspect(self.ids["device_id"])["fidelity"]["gaps"])
        self.assertIn("128x128x3", gaps)                            # the real camera size is disclosed

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["fidelity_level"], fidelity["timestep_ms"]), ("F0", 0))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)              # readable, and not advanced

    def test_a_long_run_does_not_terminate_because_num_step_is_not_advanced(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        receipt = self.step(client, ZERO, ticks=200)
        self.assertEqual(receipt["status"], "completed")
        # the fake mirrors the clone: num_step is never incremented, so the MAX_STEP branch is unreachable
        self.assertEqual(receipt["output"]["terminated"], False)
        self.assertEqual(self.state(client)["tick"], 200)
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)


if __name__ == "__main__":
    unittest.main()
