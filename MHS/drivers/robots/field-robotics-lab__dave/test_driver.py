"""Acceptance run of the DAVE ocean-current package: the gate plus local cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CURRENT = "x-cap.field-robotics-lab.current.v1"
SET_CURRENT = "x-cap.field-robotics-lab.set_current.v1"
ZERO_CURRENT = "x-cap.field-robotics-lab.zero_current.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"

VALID = {"velocity": 1.25, "horizontal_angle": 0.5, "vertical_angle": 0.25}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DaveCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_current_observation_returns_the_world_frame_vector(self) -> None:
        client = self.serve()
        receipt = client.invoke(CURRENT, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["frame_id"], "/world")
        self.assertEqual(set(output["velocity"]), {"x", "y", "z"})

    def test_the_resource_state_reads_the_two_model_services(self) -> None:
        client = self.serve()
        state = client.read("current", **self.ids)["state"]
        self.assertEqual(set(state["current_velocity_model"]), {"mean", "min", "max", "noise", "mu"})
        self.assertEqual(set(state["horizontal_angle_model"]), {"mean", "min", "max", "noise", "mu"})

    def test_set_current_reaches_the_service_with_the_mapped_request(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        output = driver.call(SET_CURRENT, VALID)
        self.assertEqual(output, {"success": True})
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual(calls[-1]["service"], "/hydrodynamics/set_current_velocity")
        self.assertEqual(calls[-1]["args"], VALID)

    def test_set_current_changes_the_observable_model_state(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        before = driver.read("current")
        self.assertEqual(before["current_velocity_model"]["mean"], 0.75)
        driver.call(SET_CURRENT, VALID)
        after = driver.read("current")
        self.assertEqual(after["current_velocity_model"]["mean"], 1.25)
        self.assertEqual(after["horizontal_angle_model"]["mean"], 0.5)

    def test_set_current_needs_the_operator_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke(SET_CURRENT, VALID, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_lets_set_current_reach_the_service(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(SET_CURRENT, VALID, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"success": True})
        state = client.read("current", **self.ids)["state"]
        self.assertEqual(state["current_velocity_model"]["mean"], 1.25)
        self.assertEqual(state["horizontal_angle_model"]["mean"], 0.5)

    def test_zero_current_changes_state_and_does_not_engage_the_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(ZERO_CURRENT, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = client.read("current", **self.ids)["state"]
        self.assertEqual(state["current_velocity_model"]["mean"], 0.0)
        self.assertEqual(state["horizontal_angle_model"]["mean"], 0.0)
        after = client.invoke(SET_CURRENT, VALID, **self.ids)
        self.assertEqual(after["status"], "completed", after)

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_set_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(SET_CURRENT, VALID)
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_service_does_not_report_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_set_service = True
        with self.assertRaises(DriverFailed):
            driver.call(SET_CURRENT, VALID)
        self.assertEqual(driver.native.velocity, 0.75)

    def test_the_native_short_circuit_can_partially_apply_a_request(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.angle_max = 0.0  # placeholder test range
        with self.assertRaises(DriverFailed):
            driver.call(SET_CURRENT, {"velocity": 2.0, "horizontal_angle": 1.0, "vertical_angle": 0.0})
        self.assertEqual(driver.native.velocity, 2.0)
        self.assertEqual(driver.native.horizontal_angle, 0.1)

    def serve_with_fake_flag(self, name):
        driver = load_driver(HERE, "fake")
        setattr(driver.native, name, True)
        server = build_server(driver, site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        return client, {"device_id": device_id, "session_id": session}

    def assert_failed_estop(self, receipt):
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(receipt["output"]["latched"])

    def test_the_estop_fails_when_the_native_service_fails(self) -> None:
        client, ids = self.serve_with_fake_flag("fail_set_service")
        self.assert_failed_estop(client.estop("test", **ids))

    def test_the_estop_fails_on_a_malformed_native_reply(self) -> None:
        client, ids = self.serve_with_fake_flag("malformed_set_response")
        self.assert_failed_estop(client.estop("test", **ids))

    def test_the_estop_fails_when_a_configured_range_excludes_zero(self) -> None:
        # Model review of 2026-11-04: SetMean refuses a mean outside [min, max] and the callback's && chain
        # stops there, so the velocity mean is already zero while the e-stop must not claim a safe state.
        driver = load_driver(HERE, "fake")
        driver.native.angle_max = -0.1  # placeholder range that excludes zero
        server = build_server(driver, site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        ids = {"device_id": device_id,
               "session_id": client.open_session(device_ids=[device_id])["session_id"]}
        self.assert_failed_estop(client.estop("test", **ids))
        self.assertEqual(driver.native.velocity, 0.0)
        self.assertEqual(driver.native.horizontal_angle, 0.1)
        refused = client.invoke(SET_CURRENT, VALID, **ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_current_stop_latches_and_refuses_observations_and_commands(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        refused_current = client.invoke(CURRENT, {}, **self.ids)
        self.assertEqual(refused_current["status"], "rejected", refused_current)
        self.assertEqual(refused_current["error"]["mhs_code"], ESTOP)
        refused_set = client.invoke(SET_CURRENT, VALID, **self.ids)
        self.assertEqual(refused_set["status"], "rejected", refused_set)
        self.assertEqual(refused_set["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
