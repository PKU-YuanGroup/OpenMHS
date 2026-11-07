"""Acceptance run of this driver package: the gate, plus cases for what is specific to this environment.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): gymnasium, pandas and
numpy are not needed, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"

PROFILES = {
    "electricity_load_profile": [2.0] * 12,
    "solar_generation_profile": [0.5] * 12,
    "electricity_price": [10.0] * 12,
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WorldCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", options=options or None)
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

    def test_the_action_box_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [1.0])["status"], "completed")
        for values in ([1.0001], [-1.0001]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                       # the refused steps changed nothing

    def test_a_step_matches_the_energy_arithmetic(self) -> None:
        client = self.serve(**PROFILES, max_timesteps=6, num_forecasting_steps=2)
        initial = self.reset(client, seed=0)["output"]["observation"]["values"]
        self.assertEqual(initial, [0.0, 2.0, 2.0, 0.5, 0.5, 10.0, 10.0])      # 3*2+1 numbers, soc 0
        receipt = self.step(client, [0.5])
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual(output["observation"]["values"][0], 10.0)            # 0.5 * 20 kWh charged
        # battery 10 + load 2 - solar 0.5 = 11.5 kWh, priced at 10: reward -115
        self.assertAlmostEqual(output["reward"], -115.0, places=9)
        self.assertEqual(output["tick"], 1)
        self.assertEqual(self.state(client)["info"], {"electricity_consumption": 11.5, "electricity_price": 10.0})

    def test_surplus_solar_is_not_fed_into_the_grid(self) -> None:
        client = self.serve(electricity_load_profile=[1.0] * 12, solar_generation_profile=[100.0] * 12,
                            electricity_price=[3.0] * 12, max_timesteps=3, num_forecasting_steps=1)
        self.reset(client)
        output = self.step(client, [0.0])["output"]
        self.assertEqual(self.state(client)["info"]["electricity_consumption"], 0.0)
        self.assertEqual(output["reward"], 0.0)

    def test_the_episode_terminates_at_max_timesteps(self) -> None:
        client = self.serve(**PROFILES, max_timesteps=3, num_forecasting_steps=2)
        self.reset(client)
        for expected_tick in (1, 2, 3):
            output = self.step(client, [0.0])["output"]
            self.assertEqual(output["tick"], expected_tick)
            self.assertEqual(output["terminated"], expected_tick == 3)
            self.assertEqual(output["truncated"], False)
        ended = self.step(client, [0.0])
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_randomised_start(self) -> None:
        client = self.serve(electricity_load_profile=[float(index) for index in range(40)],
                            solar_generation_profile=[0.0] * 40, electricity_price=[1.0] * 40,
                            max_timesteps=5, num_forecasting_steps=2, randomize_start_time_step=True)
        first = self.reset(client, seed=7)["output"]
        second = self.reset(client, seed=7)["output"]
        self.assertEqual(first["seed"], 7)
        self.assertEqual(first["observation"], second["observation"])
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 9}, **self.ids)["output"],
                         {"seed": 9, "accepted": True})
        pending = self.reset(client)["output"]
        self.assertEqual(pending["seed"], 9)
        self.assertEqual(pending["observation"], self.reset(client, seed=9)["output"]["observation"])

    def test_the_default_observation_has_3n_plus_1_values(self) -> None:
        client = self.serve()
        observation = self.reset(client, seed=1)["output"]["observation"]["values"]
        self.assertEqual(len(observation), 13)                                 # 3 * default forecast 4 + 1
        self.assertEqual(observation[0], 0.0)                                  # state of charge after a reset

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("analytic:building-energy-storage-simulation", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0.0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0])["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, [0.0]), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                        # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
