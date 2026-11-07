"""Acceptance run of the swarm_sync_sim clock package: the gate plus local cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed, OutcomeUnknown
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
PAUSE = "x-cap.shupx.pause.v1"
RESUME = "x-cap.shupx.resume.v1"
CLOCK = "x-cap.shupx.clock.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SwarmSyncSimCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_the_clock_observation_returns_a_latched_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke(CLOCK, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(set(receipt["output"]["sim_time"]), {"secs", "nsecs"})

    def test_the_online_observation_returns_the_latched_flag(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.shupx.online.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["online"], True)

    def test_pause_and_resume_reach_the_clock_control_service(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(driver.call(PAUSE, {}), {"acknowledged": True})
        self.assertTrue(driver.native.paused)
        self.assertEqual(driver.call(RESUME, {"max_sim_speed": 2.5}), {"acknowledged": True})
        self.assertFalse(driver.native.paused)
        self.assertEqual(driver.native.max_sim_speed, 2.5)
        calls = [message for message in driver.native.sent if message.get("op") == "call_service"]
        self.assertEqual([message.get("service") for message in calls],
                         ["/sss_clock_control", "/sss_clock_control"])
        self.assertEqual(calls[0]["args"], {"proceed": False, "max_sim_speed": 0.0})
        self.assertEqual(calls[1]["args"], {"proceed": True, "max_sim_speed": 2.5})

    def test_pause_keeps_the_latched_clock_sample_observable(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(PAUSE, {}, **self.ids)["status"], "completed")
        clock = client.invoke(CLOCK, {}, **self.ids)
        self.assertEqual(clock["status"], "completed", clock)
        self.assertEqual(set(clock["output"]["sim_time"]), {"secs", "nsecs"})

    def test_resume_needs_the_operator_envelope(self) -> None:
        client = self.serve()
        refused = client.invoke(RESUME, {"max_sim_speed": 2.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_lets_resume_set_the_speed(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(RESUME, {"max_sim_speed": 1.0}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertIs(receipt["output"]["acknowledged"], True)

    def test_a_rejected_application_response_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.reject_clock_application = True
        with self.assertRaises(DriverFailed) as caught:
            driver.call(PAUSE, {})
        self.assertEqual(caught.exception.code, "MHS.ADAPTER.SHIM_FAILED")

    def test_a_failed_ros_service_does_not_report_pause_success(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_clock_service = True
        with self.assertRaises(DriverFailed):
            driver.call(PAUSE, {})
        self.assertFalse(driver.native.paused)

    def test_malformed_service_reply_is_an_unknown_outcome(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.malformed_clock_response = True
        with self.assertRaises(OutcomeUnknown) as caught:
            driver.call(PAUSE, {})
        self.assertEqual(caught.exception.code, "MHS.OUTCOME.UNKNOWN")

    def test_native_estop_refuses_failed_refused_and_malformed_replies(self) -> None:
        for failure in ("fail_clock_service", "reject_clock_application", "malformed_clock_response"):
            with self.subTest(failure=failure):
                driver = load_driver(HERE, "fake")
                self.addCleanup(driver.close)
                setattr(driver.native, failure, True)
                with self.assertRaises(DriverFailed) as caught:
                    driver.estop("negative-path test")
                self.assertEqual(caught.exception.code, UNREACHED)

    def test_the_simulator_stop_pauses_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        # Observational extension actions remain latched after an e-stop.
        refused_clock = client.invoke(CLOCK, {}, **self.ids)
        self.assertEqual(refused_clock["status"], "rejected", refused_clock)
        self.assertEqual(refused_clock["error"]["mhs_code"], ESTOP)
        refused = client.invoke(RESUME, {"max_sim_speed": 1.0}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_clock_observation_advances_only_while_running(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        first = driver.call(CLOCK, {})["sim_time"]
        second = driver.call(CLOCK, {})["sim_time"]
        self.assertNotEqual(first, second)
        driver.call(PAUSE, {})
        held = driver.call(CLOCK, {})["sim_time"]
        held_again = driver.call(CLOCK, {})["sim_time"]
        self.assertEqual(held, held_again)

    def test_declaration_keeps_participant_stepping_out_of_scope(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertEqual(type(driver).ros_version, 1)
        self.assertEqual(type(driver).mode, "simulated")
        self.assertEqual(type(driver).risk, "R0")
        self.assertEqual(type(driver).device_kind, "world.sim")
        self.assertEqual(type(driver).backends, {"fake": ".fake:FakeSwarmSyncSim"})
        self.assertEqual(set(type(driver).safety_bindings), {"estop"})
        self.assertNotIn("/sss_timeclient_register", repr(type(driver).commands))
        self.assertNotIn("/sss_time_client/update_clock_request", repr(type(driver).commands))


if __name__ == "__main__":
    unittest.main()
