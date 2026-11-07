"""Acceptance run of the FlyBody package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py, a stand-in ``mujoco``
module): the MuJoCo engine is not installed where the gate runs, so nothing here compares the stand-in with it.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FlyBodyCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def step(self, client, ticks=1, ctrl=None):
        if ctrl is None:
            ctrl = [0.0] * len(self.state(client)["ctrl"])
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def test_the_model_dimensions_come_from_the_model_file(self) -> None:
        client = self.serve()
        state = self.state(client)
        # 102 hinge joints plus the 7 qpos values of the free joint, and 102 dofs plus its 6
        self.assertEqual((len(state["qpos"]), len(state["qvel"])), (109, 108))
        self.assertEqual(len(state["ctrl"]), 78)                    # the actuators of the model's actuator section
        self.assertEqual(state["timestep_ms"], 0.1)                 # 0.0001 s of the <option> element
        self.assertEqual(state["tick"], 0)

    def test_a_step_advances_the_model_and_the_receipt_reports_it(self) -> None:
        client = self.serve()
        receipt = self.step(client, ticks=10)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 10)
        self.assertAlmostEqual(output["observation"]["time"], 0.001, places=12)
        self.assertEqual(len(output["observation"]["qpos"]), 109)
        state = self.state(client)
        self.assertEqual(state["tick"], 10)
        self.assertEqual(state["time_ms"], 1)                       # 0.001 s after ten steps, rounded to ms

    def test_a_reset_returns_the_world_to_its_initial_state(self) -> None:
        client = self.serve()
        self.step(client, ticks=3)
        receipt = client.invoke("cap.world.reset.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["observation"]["time"], 0.0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))

    def test_the_fidelity_contract_states_the_stand_in(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco", "F1"))
        self.assertEqual(fidelity["timestep_ms"], 0.1)
        self.assertEqual((fidelity["realtime_factor"], fidelity["clock"], fidelity["reset"]), (0, "lockstep", "full"))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)           # the stand-in, the meshes, the ctrlrange, dm_control

    def test_the_step_is_bounded_by_the_model_control_ranges(self) -> None:
        # fruitfly.xml:11 makes every actuator ctrl-limited and the default classes give the ranges; the stand-in
        # reads them, so the bridge publishes the model's own per-actuator envelope.
        client = self.serve()
        step = next(item for item in client.inspect(self.ids["device_id"])["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        limit = step["limits"]["action.ctrl"]
        self.assertEqual((len(limit["min"]), limit["source"]), (78, "upstream_code"))
        self.assertEqual(sorted({(low, high) for low, high in zip(limit["min"], limit["max"])
                                 if (low, high) in ((0.0, 1.0), (-1.0, 1.0))}), [(-1.0, 1.0), (0.0, 1.0)])
        ctrl = [0.0] * 78
        ctrl[limit["max"].index(1.0)] = 1.5          # placeholder: just above a range that ends at 1
        refused = self.step(client, ctrl=ctrl)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", refused)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client), client.invoke("cap.world.reset.v1", {}, **self.ids)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)             # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
