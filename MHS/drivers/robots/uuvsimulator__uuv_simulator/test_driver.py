"""Acceptance and environment-specific cases for the UUV current driver.

Add cases, never remove the ``check_driver`` harness call.
"""

import json
import math
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNSET = "MHS.SAFETY.LIMITS_UNSET"

_STREAM = {
    "velocity": 1.5,          # placeholder test value
    "horizontal_angle": 0.0,  # placeholder test value
    "vertical_angle": 0.0,    # placeholder test value
}
_ANGLE = {"angle": math.pi / 2.0}  # placeholder test value


def _example_overlay():
    return json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CurrentCases(unittest.TestCase):
    def serve(self, overlay=True):
        server = load(HERE, backend="fake",
                      site_limits=_example_overlay() if overlay else None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def fake_driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_read_state_has_the_published_flow_vector(self) -> None:
        client = self.serve(overlay=False)
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(set(state["flow_velocity"]), {"x", "y", "z"})

    def test_current_velocity_observation_returns_three_components(self) -> None:
        client = self.serve(overlay=True)
        receipt = client.invoke("x-cap.uuvsimulator.current_velocity.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]), {"linear_x", "linear_y", "linear_z"})
        self.assertIsInstance(receipt["output"]["linear_x"], (int, float))

    def test_set_current_velocity_needs_operator_bounds(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNSET)

    def test_set_current_velocity_changes_the_flow_state(self) -> None:
        client = self.serve(overlay=True)
        before = client.read("main", **self.ids)["state"]["flow_velocity"]
        receipt = client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["accepted"])
        after = client.read("main", **self.ids)["state"]["flow_velocity"]
        self.assertNotEqual(before, after)
        self.assertAlmostEqual(after["x"], 1.5)

    def test_horizontal_angle_changes_the_flow_direction(self) -> None:
        client = self.serve(overlay=True)
        self.assertEqual(client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM,
                                       **self.ids)["status"], "completed")
        receipt = client.invoke("x-cap.uuvsimulator.set_horizontal_angle.v1", _ANGLE, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        after = client.read("main", **self.ids)["state"]["flow_velocity"]
        self.assertAlmostEqual(after["y"], 1.5, places=5)

    def test_vertical_angle_changes_the_flow_direction(self) -> None:
        client = self.serve(overlay=True)
        self.assertEqual(client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM,
                                       **self.ids)["status"], "completed")
        receipt = client.invoke("x-cap.uuvsimulator.set_vertical_angle.v1", _ANGLE, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        after = client.read("main", **self.ids)["state"]["flow_velocity"]
        self.assertAlmostEqual(after["z"], 1.5, places=5)

    def test_a_rejected_velocity_returns_a_failure(self) -> None:
        driver = self.fake_driver()
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.uuvsimulator.set_current_velocity.v1",
                        {"velocity": 6.0, "horizontal_angle": 0.0, "vertical_angle": 0.0})

    def test_a_failed_service_is_a_failure(self) -> None:
        driver = self.fake_driver()
        driver.native.fail_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM)

    def test_a_rejected_application_result_is_a_failure(self) -> None:
        driver = self.fake_driver()
        driver.native.fail_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.uuvsimulator.set_horizontal_angle.v1", _ANGLE)

    def test_zero_current_is_an_input_free_safe_state_action(self) -> None:
        client = self.serve(overlay=False)
        receipt = client.invoke("x-cap.uuvsimulator.zero_current.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["zeroed"])

    def test_estop_zeroes_the_current_and_latches_set_commands(self) -> None:
        client = self.serve(overlay=True)
        self.assertEqual(client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM,
                                       **self.ids)["status"], "completed")
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        after = client.read("main", **self.ids)["state"]["flow_velocity"]
        self.assertAlmostEqual(after["x"], 0.0)
        refused = client.invoke("x-cap.uuvsimulator.set_current_velocity.v1", _STREAM, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_failed_estop_service_does_not_claim_the_safe_state(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_service = True
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.estop("test", device_id=device_id, session_id=session)
        self.assertNotEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
