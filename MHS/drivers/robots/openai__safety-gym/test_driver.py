"""Acceptance run of the Safety Gym package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): MuJoCo itself is not
installed where the gate runs, so nothing here compares the fake with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SafetyGymCarCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": list(ctrl)}}, **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_step_is_bounded_by_the_model_actuator_ctrlrange(self) -> None:
        client = self.serve()
        refused = self.step(client, [2.0, 0.0])
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 0)                       # nothing was actuated
        completed = self.step(client, [0.5, -0.5])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["output"]["tick"], 1)
        state = self.state(client)
        self.assertEqual(state["tick"], 1)
        self.assertGreater(state["qpos"][7], 0.0)                            # the left wheel turned forward
        self.assertLess(state["qpos"][8], 0.0)                               # the right wheel turned backward

    def test_the_model_shape_comes_from_car_xml(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        state = self.state(client)
        # 7 qpos / 6 qvel of the free joint, 2 hinges, a ball joint of 4 qpos / 3 qvel, and 2 motors (car.xml:15-30)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (13, 11, 2))
        self.assertEqual(state["qpos"][2], 0.1)                              # car.xml:12 body start z
        self.assertEqual(state["timestep_ms"], 4.0)                          # car.xml:3
        self.assertEqual(state["time_ms"], 0)
        self.assertEqual(state["seed"], 0)

    def test_ticks_advance_the_model_timestep(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.0, 0.0], ticks=10)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["tick"], 10)
        self.assertAlmostEqual(receipt["output"]["observation"]["time"], 0.04, places=9)
        self.assertAlmostEqual(self.state(client)["time_ms"], 40, places=9)
        self.assertEqual(self.state(client)["qpos"][7], 0.0)                 # a zero ctrl leaves the wheels alone

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.5])["status"], "completed")
        self.assertGreater(self.state(client)["qpos"][7], 0.0)
        reset = self.reset(client, seed=0)
        self.assertEqual(reset["status"], "completed")
        self.assertEqual(reset["output"]["seed"], 0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"], state["qpos"][7], state["ctrl"]),
                         (0, 0, 0.0, [0.0, 0.0]))

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.2, 0.2])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.2, 0.2]), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                      # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")    # a simulator needs no operator
        self.assertEqual(self.step(client, [0.2, 0.2])["status"], "completed")

    def test_the_fidelity_contract_is_the_model(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(fidelity["engine"], "mujoco:safety_gym/xmls/car.xml")
        self.assertEqual(fidelity["fidelity_level"], "F1")
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (4.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)


if __name__ == "__main__":
    unittest.main()
