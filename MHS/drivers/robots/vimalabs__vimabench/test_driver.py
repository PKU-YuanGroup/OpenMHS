"""Acceptance run of the VIMA-Bench package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the ``check_driver`` call.  The cases run on the fake backend (``fake.py``): pybullet,
gym 0.21.0 and the upstream package are not installed where the gate runs, so nothing here compares the fake with the
upstream simulator.  The target and the start range used by the termination case are fake test data (``# placeholder``
in fake.py), not facts about VIMA-Bench.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"

POSITION = [0.50, 0.00]
ROTATION = [0.0, 0.0, 0.0, 1.0]
TARGET = [0.60, 0.20]  # placeholder: the fake's TARGET_XY


def action(pose0_position=None, pose1_position=None, pose0_rotation=None, pose1_rotation=None):
    return {
        "pose0_position": list(pose0_position if pose0_position is not None else POSITION),
        "pose0_rotation": list(pose0_rotation if pose0_rotation is not None else ROTATION),
        "pose1_position": list(pose1_position if pose1_position is not None else POSITION),
        "pose1_rotation": list(pose1_rotation if pose1_rotation is not None else ROTATION),
    }


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VIMAEnvCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=3):
        return client.invoke("cap.world.reset.v1", {"seed": seed}, **self.ids)

    def step(self, client, ticks=1, **poses):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action(**poses)}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_reset_returns_the_upstream_observation_shape(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), {"rgb", "segm", "ee"})
        self.assertEqual(set(observation["rgb"]), {"front", "top"})
        self.assertEqual(set(observation["segm"]), {"front", "top"})
        # placeholder fake shape (3 x 2 x 2 rgb, 2 x 2 segm); the real task default is 3 x 128 x 256 / 128 x 256
        self.assertEqual(len(observation["rgb"]["front"]), 3)
        self.assertEqual(len(observation["rgb"]["front"][0]), 2)
        self.assertEqual(len(observation["segm"]["front"]), 2)
        self.assertEqual(observation["ee"], 0)
        self.assertEqual(receipt["output"]["seed"], 3)
        state = self.state(client)
        self.assertEqual((state["tick"], state["episode"]), (0, 1))
        self.assertEqual(state["info"]["prompt"], "put the object into the object")
        self.assertIsNone(state["observation"].get("missing"))

    def test_one_tick_applies_one_primitive(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=3, pose1_position=[0.55, -0.10])
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["tick"], 3)
        self.assertEqual(output["reward"], 0.0)
        self.assertFalse(output["terminated"])
        self.assertFalse(output["truncated"])
        self.assertTrue(output["state_hash"].startswith("sha256:"))
        self.assertEqual(self.state(client)["tick"], 3)

    def test_a_place_on_the_target_terminates_and_stops_the_ticks(self) -> None:
        client = self.serve()
        self.reset(client)
        receipt = self.step(client, ticks=10, pose1_position=TARGET)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertTrue(output["terminated"])
        self.assertEqual(output["tick"], 1)                      # the driver stops at a terminal step
        self.assertTrue(self.state(client)["info"]["success"])
        self.assertFalse(self.state(client)["info"]["failure"])

    def test_the_action_space_bounds_are_refused_before_the_fake(self) -> None:
        client = self.serve()
        self.reset(client)
        bad = [
            {"pose0_position": [0.24, 0.0]},
            {"pose0_position": [0.76, 0.0]},
            {"pose0_position": [0.50, -0.51]},
            {"pose1_position": [0.50, 0.51]},
            {"pose0_rotation": [1.1, 0.0, 0.0, 0.0]},
            {"pose1_rotation": [0.0, 0.0, 0.0, -1.1]},
        ]
        for poses in bad:
            refused = self.step(client, **poses)
            self.assertEqual(refused["status"], "rejected", poses)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, poses)
        self.assertEqual(self.state(client)["tick"], 0)          # a refused step changed nothing

    def test_the_class_schema_bounds_are_refused(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            refused = client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action()}, **self.ids)
            self.assertEqual(refused["status"], "rejected", ticks)
            self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID, ticks)
        refused = self.reset(client, seed=-1)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"pose0_position": POSITION}},
                                **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], INPUT_INVALID)

    def test_a_seed_repeats_the_first_observation(self) -> None:
        def first(seed):
            client = self.serve()
            return self.reset(client, seed=seed)["output"]["observation"]

        self.assertEqual(first(11), first(11))
        self.assertNotEqual(first(11), first(12))

    def test_the_seed_capability_sets_the_seed_without_resetting(self) -> None:
        client = self.serve()
        self.reset(client, seed=3)
        self.assertEqual(self.step(client)["output"]["tick"], 1)
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertEqual(accepted["output"], {"seed": 21, "accepted": True})
        self.assertEqual(self.state(client)["tick"], 1)

    def test_the_estop_latches_step_reset_and_seed(self) -> None:
        client = self.serve()
        self.reset(client)
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), self.reset(client),
                        client.invoke("cap.world.seed.v1", {"seed": 2}, **self.ids)):
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)          # readable, and not advanced

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("pybullet:vima_bench/VIMAEnvBase", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertAlmostEqual(fidelity["timestep_ms"], 1000.0 / 240.0, places=9)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"]), (0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
