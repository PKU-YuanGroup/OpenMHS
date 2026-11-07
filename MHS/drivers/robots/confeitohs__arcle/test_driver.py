"""Acceptance run of the ARCLE package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): the upstream package
needs gymnasium, numpy and pygame, so nothing here compares the fake with the upstream environment.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RawARCCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.device_id = device_id
        step = next(item for item in client.inspect(device_id)["capabilities"]
                    if item["capability_id"] == "cap.world.step.v1")
        selection = step["input_schema"]["properties"]["action"]["properties"]["selection"]
        self.cells = int(selection["minItems"])
        self.side = int(round(self.cells ** 0.5))
        return client

    def reset(self, client, **fields):
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, operation, selection=None, ticks=1):
        if selection is None:
            selection = [0] * self.cells
        return client.invoke("cap.world.step.v1",
                             {"ticks": ticks, "action": {"selection": selection, "operation": operation}},
                             **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def selection(self, side, predicate):
        return [1 if predicate(row, column) else 0 for row in range(side) for column in range(side)]

    def test_the_action_space_is_the_limit(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        first = [0] * self.cells
        first[0] = 2
        middle = [0] * self.cells
        middle[self.cells // 2] = 2
        last = [0] * self.cells
        last[-1] = 2
        refused = [
            self.step(client, 1, selection=first),
            self.step(client, 1, selection=middle),
            self.step(client, 1, selection=last),
            self.step(client, 12),
            self.step(client, -1),
        ]
        for receipt in refused:
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE, receipt)
        self.assertEqual(self.state(client)["tick"], 1)          # the refused steps changed nothing

    def test_reset_publishes_the_problem(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["seed"], 3)
        observation = receipt["output"]["observation"]
        self.assertEqual(set(observation), {"trials_remain", "terminated", "input", "input_dim", "grid",
                                            "grid_dim"})
        self.assertEqual(len(observation["grid"]["values"]), self.side)
        self.assertEqual(len(observation["grid"]["values"][0]), self.side)
        self.assertGreaterEqual(observation["input_dim"]["values"][0], 1)
        state = self.state(client)
        self.assertEqual(state["tick"], 0)
        self.assertEqual(state["info"]["answer_dim"], [3, 3])
        self.assertEqual(len(state["info"]["answer"]), self.side)

    def test_a_color_operation_paints_the_selection(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=1)["status"], "completed")
        before = self.state(client)["observation"]["grid"]["values"]
        old = before[0][0]
        color = (old + 1) % 10
        selection = [0] * self.cells
        selection[0] = 1
        receipt = self.step(client, color, selection=selection)
        self.assertEqual(receipt["status"], "completed")
        after = receipt["output"]["observation"]["grid"]["values"]
        self.assertEqual(after[0][0], color)
        self.assertEqual(receipt["output"]["reward"], 0.0)

    def test_submit_terminates_when_grid_matches_answer(self) -> None:
        client = self.serve()
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        state = self.state(client)
        answer = state["info"]["answer"]
        height, width = state["info"]["answer_dim"]
        for color in range(10):
            selection = self.selection(self.side, lambda row, column: answer[row][column] == color)
            self.assertEqual(self.step(client, color, selection=selection)["status"], "completed", color)
        self.assertEqual(self.step(client, 10)["status"], "completed")       # resize_to_answer
        receipt = self.step(client, 11)                                     # submit
        self.assertEqual(receipt["status"], "completed")
        output = receipt["output"]
        self.assertEqual((output["terminated"], output["truncated"]), (True, False))
        self.assertEqual(output["reward"], 1.0)
        self.assertEqual(output["tick"], 12)
        self.assertEqual(output["observation"]["grid_dim"]["values"], [height, width])
        ended = self.step(client, 0)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=0)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_a_seed_repeats_the_trajectory(self) -> None:
        def trajectory(seed):
            client = self.serve()                                  # a fresh world: the state hash counts episodes
            self.assertEqual(self.reset(client, seed=seed)["output"]["seed"], seed)
            hashes = []
            for operation in (1, 5, 10, 11):
                hashes.append(self.step(client, operation)["output"]["state_hash"])
            return hashes

        first = trajectory(11)
        self.assertEqual(trajectory(11), first)
        self.assertNotEqual(trajectory(21), first)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_reset_options_choose_the_problem_set(self) -> None:
        client = self.serve()
        example = self.reset(client, seed=0, options={"adaptation": True, "subprob_index": 0})["output"]
        test = self.reset(client, seed=0, options={"adaptation": False, "subprob_index": 0})["output"]
        self.assertNotEqual(example["observation"], test["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.device_id)
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R0")
        self.assertEqual((fidelity["engine"], fidelity["fidelity_level"]),
                         ("gymnasium:ARCLE/RawARCEnv-v0", "F0"))
        self.assertEqual(fidelity["determinism"]["kind"], "seeded")
        self.assertEqual(fidelity["determinism"]["seed_control"], "parameter")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]),
                         (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("full", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 5)

    def test_the_estop_latches_the_simulation(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, 1)["status"], "completed")
        client.estop("test", **self.ids)
        for refused in (self.step(client, 1), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                          # readable, and not advanced


if __name__ == "__main__":
    unittest.main()
