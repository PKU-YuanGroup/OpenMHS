"""Acceptance run of this driver package: the gate, plus cases against the stock server and the fake backend.

Add cases, never remove the ``check_driver`` call.
"""

import asyncio
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
OVERLAY = str(HERE / "site-limits.example.json")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BambuCases(unittest.TestCase):
    def serve(self, site_limits=None, artifact_store=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits, artifact_store=artifact_store)
        self.addCleanup(close_server, server)
        self.driver = driver
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        hello = client.hello()
        device_id = hello["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_reads_are_the_fake_status(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["state"], "idle")
        self.assertTrue(state["online"])
        self.assertEqual(state["nozzle_target_temperature"], 0.0)
        self.assertEqual(state["bed_target_temperature"], 0.0)
        self.assertEqual(state["print_speed_level"], 2)
        self.assertTrue(state["chamber_light"])
        self.assertEqual(state["alerts"], [])

    def test_writes_reach_the_fake_and_are_read_back(self) -> None:
        client = self.serve(site_limits=OVERLAY)
        for patch in ({"nozzle_target_temperature": 200.0}, {"bed_target_temperature": 60.0},
                      {"print_speed_level": 3}, {"chamber_light": False}):
            receipt = self.configure(client, **patch)
            self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual(state["nozzle_target_temperature"], 200.0)
        self.assertEqual(state["bed_target_temperature"], 60.0)
        self.assertEqual(state["print_speed_level"], 3)
        self.assertFalse(state["chamber_light"])

    def test_nozzle_and_speed_bounds_are_refused_without_a_native_call(self) -> None:
        client = self.serve()
        for patch in ({"nozzle_target_temperature": 301.0}, {"nozzle_target_temperature": -1.0},
                      {"print_speed_level": 0}, {"print_speed_level": 5}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)
        state = self.state(client)
        self.assertEqual(state["nozzle_target_temperature"], 0.0)
        self.assertEqual(state["print_speed_level"], 2)

    def test_bed_target_needs_the_operator_overlay_and_respects_the_model(self) -> None:
        client = self.serve()
        refused = self.configure(client, bed_target_temperature=60.0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], UNSET, refused)
        client = self.serve(site_limits=OVERLAY)
        accepted = self.configure(client, bed_target_temperature=80.0)
        self.assertEqual(accepted["status"], "completed", accepted)
        refused = self.configure(client, bed_target_temperature=81.0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, refused)

    def test_start_pause_resume_stop(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.zhenwei2972.start_print.v1",
                                {"remote_path": "cache/benchy.3mf"}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        self.assertEqual(started["output"]["file"], "cache/benchy.3mf")
        self.assertEqual(self.state(client)["state"], "running")
        paused = client.invoke("x-cap.zhenwei2972.pause_print.v1", {}, **self.ids)
        self.assertEqual(paused["status"], "completed", paused)
        self.assertEqual(self.state(client)["state"], "paused")
        resumed = client.invoke("x-cap.zhenwei2972.resume_print.v1", {}, **self.ids)
        self.assertEqual(resumed["status"], "completed", resumed)
        self.assertEqual(self.state(client)["state"], "running")
        stopped = client.invoke("x-cap.zhenwei2972.stop_print.v1", {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(self.state(client)["state"], "idle")

    def test_calibration_needs_a_selected_routine(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.zhenwei2972.calibrate_printer.v1",
                                {"bed_level": False, "vibration": False, "motor_noise": False, "lidar": False},
                                **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", refused)
        accepted = client.invoke("x-cap.zhenwei2972.calibrate_printer.v1", {"bed_level": True}, **self.ids)
        self.assertEqual(accepted["status"], "completed", accepted)
        self.assertTrue(accepted["output"]["options"]["bed_level"])

    def test_ordinary_stop_requests_zero_targets_and_reads_the_cache(self) -> None:
        client = self.serve(site_limits=OVERLAY)
        warmed = self.configure(client, nozzle_target_temperature=200.0, bed_target_temperature=60.0)
        self.assertEqual(warmed["status"], "completed", warmed)
        receipt = client.invoke("x-cap.zhenwei2972.safe_stop.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertTrue(output["stop_acknowledged"])
        self.assertTrue(output["heater_targets_zero"])
        state = self.state(client)
        self.assertEqual(state["state"], "idle")
        self.assertEqual(state["nozzle_target_temperature"], 0.0)
        self.assertEqual(state["bed_target_temperature"], 0.0)

    def test_capture_publishes_the_jpeg_as_an_artifact(self) -> None:
        client = self.serve(artifact_store=LocalArtifactStore())
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (1, 1))
        self.assertEqual(output["media_type"], "image/jpeg")
        artifact = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertTrue(artifact["data"].startswith(b"\xff\xd8"), artifact["descriptor"])

    def test_estop_reaches_the_native_stop_and_latches(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        with self.assertRaises(DriverFailed):
            driver.estop("test")
        self.assertTrue(any(name == "stop_print" for name, _args in driver.native._commands))
        client = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        refused_stop = client.invoke("x-cap.zhenwei2972.safe_stop.v1", {}, **self.ids)
        self.assertEqual(refused_stop["error"]["mhs_code"], ESTOP, refused_stop)
        refused = self.configure(client, nozzle_target_temperature=200.0)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)
        refused_action = client.invoke("x-cap.zhenwei2972.start_print.v1",
                                       {"remote_path": "cache/benchy.3mf"}, **self.ids)
        self.assertEqual(refused_action["status"], "rejected", refused_action)
        self.assertEqual(refused_action["error"]["mhs_code"], ESTOP, refused_action)

    def test_estop_reports_a_missing_acknowledgement(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native._force_stop_reply({"acknowledged": False, "hint": "test: no report echoed the sequence id"})
        with self.assertRaises(OutcomeUnknown):
            driver.estop("test")
        self.assertTrue(any(name == "stop_print" for name, _args in driver.native._commands))

    def test_estop_reports_a_malformed_reply(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native._force_stop_reply("not a report dict")
        with self.assertRaises(DriverFailed):
            driver.estop("test")
        self.assertTrue(any(name == "stop_print" for name, _args in driver.native._commands))

    def test_busy_start_and_calibration_are_refused(self) -> None:
        client = self.serve()
        started = client.invoke("x-cap.zhenwei2972.start_print.v1", {"remote_path": "cache/a.3mf"}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        for capability, payload in (("x-cap.zhenwei2972.start_print.v1", {"remote_path": "cache/b.3mf"}),
                                    ("x-cap.zhenwei2972.calibrate_printer.v1", {"bed_level": True})):
            refused = client.invoke(capability, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", refused)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.BUSY", refused)

    def test_missing_or_nonzero_heater_targets_cannot_complete_the_ordinary_stop(self) -> None:
        self.serve()

        async def ignore_heater_request(nozzle=None, bed=None):
            return {"acknowledged": True, "success": True}

        self.driver.native.set_temperature = ignore_heater_request
        for value in (None, 200.0, float("nan")):
            self.driver.native._nozzle.target = value
            with self.assertRaises(DriverFailed):
                asyncio.run(self.driver.safe_stop())

    def test_an_unknown_job_state_cannot_complete_the_ordinary_stop(self) -> None:
        self.serve()

        async def ignore_stop_request():
            return {"acknowledged": True, "success": True}

        self.driver.native.stop_print = ignore_stop_request
        self.driver.native._state = "unknown"
        with self.assertRaises(DriverFailed):
            asyncio.run(self.driver.safe_stop())

    def test_unreported_progress_remains_missing(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertNotIn("progress_percent", state)
        self.assertNotIn("remaining_minutes", state)

    def test_fractional_targets_report_the_integer_native_setpoints(self) -> None:
        client = self.serve(site_limits=OVERLAY)
        receipt = self.configure(client, nozzle_target_temperature=200.9, bed_target_temperature=60.9)
        self.assertEqual(receipt["status"], "completed", receipt)
        state = self.state(client)
        self.assertEqual(state["nozzle_target_temperature"], 200.0)
        self.assertEqual(state["bed_target_temperature"], 60.0)


if __name__ == "__main__":
    unittest.main()
