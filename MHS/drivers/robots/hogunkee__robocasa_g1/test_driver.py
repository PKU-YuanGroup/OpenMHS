"""Acceptance run of the RoboCasa-G1 package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): robosuite_g1, MuJoCo,
gymnasium and the tabletop assets are not installed where the gate runs, so nothing here compares the fake with the
upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

#: The five part actions of the repository example (test_env.py:25-29); placeholder values, not device facts.
PARTS = {"left_hand": 7, "right_hand": 7, "left_arm": 7, "right_arm": 7, "waist": 3}
VIDEO_KEYS = (
    "video.ego_view_pad_res256_freq20",
    "video.ego_view_bg_crop_pad_res256_freq20",
    "video.rs_view_pad_res256_freq20",
    "video.world_view",
)


def action(**parts):
    """A zero action with the five part keys; parts override one array."""
    value = {name: [0.0] * length for name, length in PARTS.items()}
    value.update(parts)
    return value


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RoboCasaG1Cases(unittest.TestCase):
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

    def step(self, client, payload, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": payload}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_action_envelope_is_the_upstream_box(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        for part in ("left_arm", "waist"):
            out = action()
            out[part][0] = 1.5
            refused = self.step(client, out)
            self.assertEqual(refused["status"], "rejected", part)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, part)
        self.assertEqual(self.state(client)["tick"], 1)                       # the refused steps changed nothing

    def test_a_step_advances_the_parts_and_returns_the_groot_keys(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        receipt = self.step(client, action(left_arm=[0.5] * 7))
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual((output["reward"], output["terminated"], output["truncated"], output["tick"]),
                         (0.0, False, False, 1))
        self.assertNotEqual(observation["state.left_arm"], [0.0] * 7)
        for key in VIDEO_KEYS:
            self.assertEqual(len(observation[key]), 2)                        # placeholder 2x2x3 frame
            self.assertEqual(len(observation[key][0][0]), 3)
        self.assertTrue(observation["annotation.human.coarse_action"].startswith("unlocked_waist: "))

    def test_a_seed_repeats_the_initial_observation(self) -> None:
        def observation(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]

        first = observation(11)
        self.assertEqual(observation(11), first)
        self.assertNotEqual(observation(12), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertTrue(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"])
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_reset_options_are_accepted(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=5, options={"unused": True})["status"], "completed")

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertTrue(fidelity["engine"].startswith(
            "gymnasium:g1_unified/EvalPnPAppleToPlate_G1ArmsAndWaistDex31Hands_Env"))
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (50.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 8)
        self.assertTrue(any("256x256x3" in gap for gap in fidelity["gaps"]))

    def test_the_estop_latches_and_reopens_at_the_recorded_seed(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, action())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, action()), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                       # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.step(client, action())["status"], "completed")


if __name__ == "__main__":
    unittest.main()
