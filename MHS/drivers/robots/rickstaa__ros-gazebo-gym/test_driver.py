"""Acceptance run of the Panda reach package: the gate, plus cases for what is specific to this driver.

The cases run on the fake backend (fake.py) in the isolated simulator host process, as the gate does: ROS, Gazebo
and MoveIt are not installed where the gate runs, so nothing here compares the fake with the upstream environment.
The gate call is kept; add cases, never remove it.
"""

import json
import math
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
INPUT = "MHS.CAPABILITY.INPUT_INVALID"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ZERO = [0.0] * 7


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PandaReachCases(unittest.TestCase):
    def serve(self, **options):
        server = load(HERE, backend="fake", options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def reset(self, client, seed=None, **fields):
        if seed is not None:
            fields["seed"] = seed
        return client.invoke("cap.world.reset.v1", fields, **self.ids)

    def step(self, client, values, ticks=1):
        return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": {"values": values}}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def fields(self, receipt):
        observation = receipt["output"]["observation"]
        return (observation["observation"]["values"], observation["achieved_goal"]["values"],
                observation["desired_goal"]["values"])

    def test_the_pause_and_its_read_back_cite_the_companion_gazebo_ros(self) -> None:
        # integrator v4 (2026-11-05): the reviewed companion source (task.json companions, from the registry card)
        task = json.loads((HERE / "task.json").read_text(encoding="utf-8"))
        [companion] = task["companions"]
        self.assertEqual((companion["alias"], companion["package_id"], companion["commit"], companion["profile"]),
                         ("gazebo_ros_pkgs", "gh.ros-simulation/gazebo_ros_pkgs",
                          "cd9cc952402375be5f274f39b29399c4087aa839", "ros1-noetic-gazebo11"))
        api = "companion:gazebo_ros_pkgs/gazebo_ros/src/gazebo_ros_api_plugin.cpp"
        driver = load_driver(HERE, backend="fake")
        try:
            refs = {fact.ref: fact.text for fact in type(driver).facts}
        finally:
            driver.close()
        self.assertIn("SetPaused(true)", refs[api + ":1725-1729"])
        self.assertIn("IsPaused()", refs[api + ":1489"])
        self.assertIn("pause_physics", refs[api + ":492-498"])
        self.assertIn("get_physics_properties", refs[api + ":383-389"])

    def test_the_sim_backend_is_built_only_in_the_host_process(self) -> None:
        # host.py imports gymnasium and ros_gazebo_gym in the host process, where they are not installed here: the
        # construction fails there and the endpoint reports it; nothing upstream is imported by the endpoint.
        with self.assertRaisesRegex(ValueError, "could not be built in the simulator host"):
            load(HERE, backend="sim")

    def test_fake_fidelity_cannot_be_projected_as_native(self) -> None:
        driver = load_driver(HERE, backend="fake")
        self.addCleanup(driver.close)
        with self.assertRaisesRegex(ValueError, "isolated-process backends require a manifest"):
            driver.fidelity_for("sim")

    def test_the_estop_pauses_the_world_and_reads_the_pause_back(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        stop = client.estop("test", **self.ids)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertEqual((stop["output"]["estop"], stop["output"]["safe_state_achieved"]), ("engaged", True))
        for refused in (self.step(client, ZERO), self.reset(client, seed=1)):
            self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.state(client)["tick"], 1)                    # readable, and not advanced
        self.assertEqual(client.reset(**self.ids)["status"], "completed")  # lifts the host's fence
        self.assertEqual(self.step(client, ZERO)["status"], "completed")

    def test_a_pause_that_does_not_take_effect_is_never_confirmed(self) -> None:
        client = self.serve(stop_ignored=True)
        self.assertEqual(self.step(client, ZERO)["status"], "completed")
        stop = client.estop("the fake simulator acknowledges the pause but keeps running", **self.ids)
        self.assertEqual((stop["status"], stop["error"]["mhs_code"]), ("failed", UNREACHED), stop)
        self.assertEqual((stop["output"]["latched"], stop["output"]["safe_state_achieved"]), (True, False))
        refused = client.reset(**self.ids)
        self.assertNotEqual(refused.get("status"), "completed", refused)
        self.assertEqual(self.step(client, ZERO)["error"]["mhs_code"], ESTOP)

    def test_an_estop_during_a_step_waits_for_it_and_pauses_again(self) -> None:
        client = self.serve(step_delay_s=0.4)
        self.assertEqual(self.reset(client, seed=3)["status"], "completed")
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.update(receipt=self.step(client, ZERO)), daemon=True)
        worker.start()
        time.sleep(0.1)                                                    # the step is inside the host now
        stop = client.estop("during a step", **self.ids)
        worker.join(5.0)
        self.assertEqual(stop["status"], "completed", stop)
        self.assertTrue(stop["output"]["safe_state_achieved"])
        self.assertIn(outcome["receipt"]["status"], ("completed", "cancelled"), outcome)
        self.assertEqual(self.step(client, ZERO)["error"]["mhs_code"], ESTOP)

    def test_the_action_space_is_the_shipped_effort_bounds(self) -> None:
        client = self.serve()
        self.assertEqual(self.step(client, [0.0] * 7)["status"], "completed")
        for values in ([88.0, 0, 0, 0, 0, 0, 0], [0, 0, 0, 0, -13.0, 0, 0]):
            refused = self.step(client, values)
            self.assertEqual(refused["status"], "rejected", values)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, values)
        self.assertEqual(self.state(client)["tick"], 1)                    # the refused steps changed nothing

    def test_a_wrong_length_is_an_input_error(self) -> None:
        client = self.serve()
        refused = self.step(client, [0.0] * 6)
        self.assertNotEqual(refused["status"], "completed")
        self.assertEqual(refused["error"]["mhs_code"], INPUT)

    def test_reset_publishes_the_goal_and_the_observation(self) -> None:
        client = self.serve()
        receipt = self.reset(client, seed=5)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 5)
        ee, achieved, goal = self.fields(receipt)
        self.assertEqual((len(ee), len(achieved), len(goal)), (3, 3, 3))
        self.assertEqual(achieved, ee)
        self.assertTrue(0.1 <= goal[0] <= 0.8 and -0.4 <= goal[1] <= 0.4 and 0.1 <= goal[2] <= 1.0, goal)

    def test_a_seed_repeats_the_reset_and_a_different_seed_differs(self) -> None:
        client = self.serve()
        first = self.reset(client, seed=7)["output"]["observation"]
        self.assertEqual(self.reset(client, seed=7)["output"]["observation"], first)
        self.assertNotEqual(self.reset(client, seed=8)["output"]["observation"], first)

    def test_the_reward_is_minus_the_goal_distance(self) -> None:
        client = self.serve()
        ee, _, goal = self.fields(self.reset(client, seed=5))
        distance = math.dist(ee, goal)
        output = self.step(client, ZERO)["output"]
        self.assertAlmostEqual(output["reward"], -distance, places=7)
        self.assertEqual(self.fields({"output": output})[0], ee)          # the zero effort does not move the fake EE

    def test_reaching_the_goal_needs_two_hold_samples(self) -> None:
        client = self.serve()
        ee, _, goal = self.fields(self.reset(client, seed=5))
        # The fake's documented placeholder mapping moves the EE by 0.02 m per effort unit (fake.py).
        action = [(goal[i] - ee[i]) / 0.02 for i in range(3)] + [0.0] * 4
        self.assertTrue(all(-87.0 <= value <= 87.0 for value in action), action)
        first = self.step(client, action)["output"]
        self.assertFalse(first["terminated"], first)
        self.assertAlmostEqual(first["reward"], 0.0, places=7)
        second = self.step(client, ZERO)["output"]
        self.assertTrue(second["terminated"], second)
        self.assertAlmostEqual(second["reward"], 0.0, places=7)

    def test_reset_retains_the_source_hold_counter(self) -> None:
        client = self.serve()
        outcomes = []
        observations = []
        for _ in range(3):
            receipt = self.reset(client, seed=5)
            ee, _, goal = self.fields(receipt)
            observations.append(receipt["output"]["observation"])
            action = [(goal[i] - ee[i]) / 0.02 for i in range(3)] + [0.0] * 4
            outcomes.append(self.step(client, action)["output"]["terminated"])
        self.assertEqual(outcomes, [False, True, False])
        self.assertTrue(all(obs == observations[0] for obs in observations))

    def test_the_episode_truncates_at_500_steps(self) -> None:
        client = self.serve()
        seed = 0
        while True:
            ee, _, goal = self.fields(self.reset(client, seed=seed))
            if math.dist(ee, goal) >= 0.05:
                break
            seed += 1
        receipt = self.step(client, ZERO, ticks=500)
        output = receipt["output"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual((output["terminated"], output["truncated"], output["tick"]), (False, True, 500))
        ended = self.step(client, ZERO)
        self.assertEqual((ended["status"], ended["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(self.reset(client, seed=seed)["status"], "completed")
        self.assertEqual(self.state(client)["tick"], 0)

    def test_the_seed_class_sets_the_next_reset(self) -> None:
        client = self.serve()
        accepted = client.invoke("cap.world.seed.v1", {"seed": 21}, **self.ids)
        self.assertEqual(accepted["output"]["accepted"], True)
        first = self.reset(client)["output"]
        self.assertEqual(first["seed"], 21)
        self.assertEqual(self.reset(client, seed=21)["output"]["observation"], first["observation"])

    def test_the_fidelity_contract_is_published(self) -> None:
        client = self.serve()
        device = client.inspect(self.ids["device_id"])
        fidelity = device["fidelity"]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["safety"]["risk_class"], "R2")
        self.assertEqual(device["safety"]["estop"]["native"], "gazebo.pause_proxy")
        self.assertEqual(fidelity["fidelity_level"], "F0")
        self.assertIn("package fake", fidelity["engine"])
        self.assertEqual(fidelity["determinism"]["kind"], "none")
        self.assertEqual((fidelity["timestep_ms"], fidelity["realtime_factor"], fidelity["clock"]), (0, 0, "lockstep"))
        self.assertEqual((fidelity["reset"], fidelity["snapshot_restore"]), ("partial", False))
        self.assertGreaterEqual(len(fidelity["gaps"]), 4)
        notes = " ".join(device["profile"]["operating_notes"])
        self.assertIn("isolated_process_v1", notes)
        self.assertIn("gazebo.get_physics_properties().pause", notes)

    def test_the_info_dictionary_has_the_upstream_keys(self) -> None:
        client = self.serve()
        self.reset(client, seed=5)
        self.step(client, ZERO)
        info = self.state(client)["info"]
        self.assertEqual(set(info), {"reference", "state_of_interest", "reference_error"})
        self.assertEqual(len(info["reference_error"]), 3)


if __name__ == "__main__":
    unittest.main()
