"""Acceptance run of the PyRoboSim package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
RESET = "cap.world.reset.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PyrobosimCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_the_world_state_reports_the_entities(self) -> None:
        client = self.serve()
        world = self.state(client)["world_state"]
        self.assertEqual(sorted(world["rooms"]), ["kitchen", "living_room"])
        self.assertEqual(world["hallways"], {"hallway_0": True})
        self.assertEqual(world["locations"],
                         {"table": False, "shelf": False, "fridge": True, "cabinet": False})
        self.assertEqual(world["objects"], ["apple", "cracker"])
        self.assertEqual(world["robots"], ["robot"])

    def test_reset_returns_its_seed_and_observation(self) -> None:
        client = self.serve()
        receipt = client.invoke(RESET, {"seed": 7}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["seed"], 7)
        self.assertEqual(receipt["output"]["observation"]["robots"], ["robot"])

    def test_reset_refuses_a_negative_seed_before_the_native_call(self) -> None:
        client = self.serve()
        receipt = client.invoke(RESET, {"seed": -1}, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_open_and_close_change_the_location_state(self) -> None:
        client = self.serve()
        opened = client.invoke("x-cap.sea-bass.open_location.v1", {"location": "table"}, **self.ids)
        self.assertEqual(opened["status"], "completed", opened)
        self.assertEqual(opened["output"], {"status": "SUCCESS", "message": "", "success": True})
        self.assertTrue(self.state(client)["world_state"]["locations"]["table"])
        closed = client.invoke("x-cap.sea-bass.close_location.v1", {"location": "table"}, **self.ids)
        self.assertEqual(closed["status"], "completed", closed)
        self.assertFalse(self.state(client)["world_state"]["locations"]["table"])

    def test_a_native_precondition_failure_is_a_failed_receipt(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.sea-bass.open_location.v1", {"location": "cabinet"}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        invalid = client.invoke("x-cap.sea-bass.open_location.v1", {"location": "missing"}, **self.ids)
        self.assertEqual(invalid["status"], "failed", invalid)

    def test_the_inflation_radius_waits_for_the_operator(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"inflation_radius": 0.1}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["inflation_radius"], 0.0)

    def test_the_example_overlay_supplies_the_inflation_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = client.invoke("cap.device.configure.v1", {"inflation_radius": 0.25}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(self.state(client)["inflation_radius"], 0.25)
        refused = client.invoke("cap.device.configure.v1", {"inflation_radius": 1.5}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["inflation_radius"], 0.25)

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke("x-cap.sea-bass.open_location.v1", {"location": "table"},
                                       **self.ids)["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused = client.invoke("x-cap.sea-bass.close_location.v1", {"location": "table"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_estop_zeroes_velocities_before_the_blocking_shutdown(self) -> None:
        # Upstream World.shutdown can wait for an in-flight action; the velocity reset must not wait behind it.
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        robot = driver.native.get_robot_by_name("robot")
        robot.dynamics.velocity = [0.4, 0.0, 0.2]       # placeholder commanded velocity
        seen = []
        shutdown = driver.native.shutdown

        def recording_shutdown():
            seen.append(list(robot.dynamics.velocity))
            shutdown()

        driver.native.shutdown = recording_shutdown
        driver.stop()
        self.assertEqual(seen, [[0.0, 0.0, 0.0]])
        self.assertEqual(robot.dynamics.velocity, [0.0, 0.0, 0.0])

    def test_a_failed_native_shutdown_is_not_reported_as_success(self) -> None:
        server = load(HERE, backend="fake", options={"fail_shutdown": True})
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.estop("test", device_id=device_id, session_id=session)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")


if __name__ == "__main__":
    unittest.main()
