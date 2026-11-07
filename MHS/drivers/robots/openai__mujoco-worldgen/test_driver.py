"""Acceptance run of the MuJoCo Worldgen particle driver: the gate, plus cases specific to this model.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); MuJoCo
itself is not installed where the gate runs, so nothing here compares the fake with the real engine.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
#: Operator example data the gate serves too: the model gives no actuator a control range.
EXAMPLE_OVERLAY = HERE / "site-limits.example.json"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WorldgenParticleCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake", site_limits=EXAMPLE_OVERLAY)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_is_read_from_the_mjcf(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(len(state["qpos"]), 3)                       # slide0, slide1 and slide2 (main.xml:6-8)
        self.assertEqual(len(state["qvel"]), 3)
        self.assertEqual(len(state["ctrl"]), 2)                       # two motors (main.xml:17-18)
        self.assertEqual(state["timestep_ms"], 5.0)                   # <option timestep="0.005"/> (main.xml:3)
        self.assertEqual(state["tick"], 0)

    def test_a_step_advances_time_and_the_actuated_joints(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.5, 0.1], ticks=2)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        observation = output["observation"]
        self.assertEqual(output["tick"], 2)
        self.assertAlmostEqual(observation["time"], 0.01, places=9)
        # the fake's placeholder response is control * gear 100 * 0.01 per second (fake.py, not physics)
        self.assertAlmostEqual(observation["qpos"][0], 0.005, places=9)
        self.assertAlmostEqual(observation["qpos"][1], 0.001, places=9)
        self.assertEqual(observation["qpos"][2], 0.0)                 # no motor drives slide2
        state = self.state(client)
        self.assertEqual(state["tick"], 2)
        self.assertEqual(state["ctrl"], [0.5, 0.1])
        self.assertEqual(state["qpos"][0], observation["qpos"][0])

    def test_the_model_declares_no_control_range(self) -> None:
        client = self.serve()
        # main.xml:16-19 states no ctrlrange, so the bound is the operator's: here the example overlay's
        # illustrative -10..10, which refuses a large value before the engine runs.
        receipt = self.step(client, [1e6, -1e6])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_control_vector_of_the_wrong_length_is_refused(self) -> None:
        client = self.serve()
        receipt = self.step(client, [0.5])
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.state(client)["tick"], 0)

    def test_reset_restores_the_model_defaults(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.1], ticks=3)["status"], "completed")
        receipt = self.reset(client, seed=9)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["seed"], 0)                           # the bridge's configured seed, not 9
        self.assertEqual(output["observation"]["qpos"], [0.0, 0.0, 0.0])
        self.assertEqual(output["observation"]["time"], 0.0)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"], state["ctrl"]), (0, 0, [0.0, 0.0]))

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]), ("mujoco:worldgen-particle", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (5.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.5, 0.1])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.5, 0.1]), self.reset(client, seed=1)):
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)               # readable, and not advanced


    def test_a_control_step_needs_an_operator_bound(self) -> None:
        # The model gives no actuator a ctrlrange: without an operator overlay the endpoint refuses every step that
        # sets action.ctrl (LIMITS_UNSET) before the engine runs, and a step without an action still advances.
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id, "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        width = len(client.read("world", **ids)["state"]["ctrl"])
        refused = client.invoke("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.0] * width}}, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 0)
        ticked = client.invoke("cap.world.step.v1", {"ticks": 1}, **ids)
        self.assertEqual(ticked["status"], "completed", ticked)
        self.assertEqual(client.read("world", **ids)["state"]["tick"], 1)

if __name__ == "__main__":
    unittest.main()
