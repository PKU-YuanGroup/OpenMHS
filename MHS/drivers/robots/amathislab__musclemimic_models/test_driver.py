"""Acceptance run of the MuscleMimic driver: the gate, plus cases for what is specific to this model.

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
#: The model shape of README.md:127 (76 joints, 126 muscles) and of the timestep at
#: musclemimic_models/model/arm/assets/myoarm_bimanual_assets.xml:21 (0.002 s).
JOINTS, MUSCLES, TIMESTEP_MS = 76, 126, 2.0


def controls(value=0.0):
    return [value] * MUSCLES


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class MyoBimanualArmCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def step(self, client, ctrl, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": ctrl}}, **self.ids)

    def reset(self, client, seed=0):
        return client.invoke("cap.world.reset.v1", {"seed": seed}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_model_shape_and_control_range_are_derived_from_the_model(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((len(state["qpos"]), len(state["qvel"]), len(state["ctrl"])), (JOINTS, JOINTS, MUSCLES))
        self.assertEqual(state["timestep_ms"], TIMESTEP_MS)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(self.step(client, controls())["status"], "completed")
        out_of_range = controls()
        out_of_range[0] = 1.5
        refused = self.step(client, out_of_range)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["tick"], 1)                      # the refused step changed nothing

    def test_a_step_applies_the_control_and_advances_the_timestep(self) -> None:
        client = self.serve()
        ctrl = controls()
        ctrl[0] = 1.0
        receipt = self.step(client, ctrl, ticks=5)
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["tick"], 5)
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"], state["timestep_ms"]), (5, 10, TIMESTEP_MS))
        self.assertEqual(state["ctrl"], ctrl)                                # the last applied control is observable
        self.assertGreater(state["qpos"][0], 0.0)                            # the placeholder integration moved

    def test_reset_restores_the_model_defaults_and_reports_the_configured_seed(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, controls(0.5), ticks=3)["status"], "completed")
        receipt = self.reset(client, seed=9)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 0)                       # the class seed, not the unused input
        state = self.state(client)
        self.assertEqual((state["tick"], state["time_ms"]), (0, 0))
        self.assertEqual(state["qpos"], [0.0] * JOINTS)
        self.assertEqual(state["qvel"], [0.0] * JOINTS)
        self.assertEqual(state["ctrl"], [0.0] * MUSCLES)

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("mujoco:MuscleMimic MyoBimanualArm", "F1"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (TIMESTEP_MS, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", True))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, controls())["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, controls()), self.reset(client)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                      # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
