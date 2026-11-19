"""Acceptance run of the AV-ALOHA gym_guided_vision InsertPeg package: the gate plus driver-specific cases.

The cases run on the fake backend (fake.py).  gym_guided_vision, MuJoCo and dm_control are not installed where the
gate runs, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
CAMERAS = {
    "zed_cam_left",
    "zed_cam_right",
    "wrist_cam_left",
    "wrist_cam_right",
    "overhead_cam",
    "worms_eye_cam",
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class InsertPegCases(unittest.TestCase):
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

    def test_reset_returns_the_upstream_observation_layout(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed", receipt)
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), {"pixels", "agent_pos"})
        self.assertEqual(set(observation["pixels"]), CAMERAS)
        for camera in CAMERAS:
            image = observation["pixels"][camera]["values"]
            # the upstream renders 480x640x3 (env.py:66-85); the fake returns a 2x2x3 placeholder
            self.assertEqual((len(image), len(image[0]), len(image[0][0])), (2, 2, 3), camera)
        self.assertEqual(len(observation["agent_pos"]["values"]), 21)

    def test_step_applies_the_21_value_action_layout(self) -> None:
        client = self.serve()
        values = [round(0.1 * (index + 1), 6) for index in range(21)]
        receipt = self.step(client, values)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 1)
        self.assertEqual(output["reward"], 0.0)
        self.assertEqual((output["terminated"], output["truncated"]), (False, False))
        # fake.py writes the same slices as GuidedVisionEnv.step (env.py:204-215), so the observation echoes them
        self.assertEqual(output["observation"]["agent_pos"]["values"], values)
        self.assertEqual(self.state(client)["tick"], 1)

    def test_a_step_without_an_action_is_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.world.step.v1", {"ticks": 1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_an_action_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        for values in ([0.0] * 20, [0.0] * 22):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, values)
        self.assertEqual(self.state(client)["tick"], 0)        # the refused steps changed nothing

    def test_the_seed_action_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=7)["output"]["seed"], 7)
        accepted = client.invoke("cap.world.seed.v1", {"seed": 11}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertEqual((accepted["output"]["seed"], accepted["output"]["accepted"]), (11, True))
        self.assertEqual(self.reset(client)["output"]["seed"], 11)

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        receipt = self.reset(client, options={"note": "the upstream reset accepts options"})
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["resources"][0]["kind"], "world.sim")
        self.assertEqual(fidelity["engine"], "analytic:av-aloha-insert-peg-fake")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "exact")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (40.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        gaps = " ".join(fidelity["gaps"])
        self.assertIn("480x640x3", gaps)                       # the real camera size is named
        self.assertIn("analytic stand-in", gaps)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 21)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0] * 21), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        self.assertEqual(self.state(client)["tick"], 1)        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
