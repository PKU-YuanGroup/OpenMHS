"""Acceptance run of the OpenCyberGlove package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py); nothing here ran on a
real glove.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import DriverFailed, build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
NOT_READY = "MHS.DEVICE.NOT_READY"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CyberGloveCases(unittest.TestCase):
    def serve(self, **options):
        driver = load_driver(HERE, backend="fake", options=options or None)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.gloves = driver.native
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def capture(self, payload=None):
        return self.client.invoke("cap.sensing.read.v1", payload or {}, **self.ids)

    # -- reads ---------------------------------------------------------------------------------------------------
    def test_the_state_exposes_the_packet_of_the_configured_hand(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["hand"], "left")
        self.assertEqual(state["acquisition"], "running")
        self.assertEqual(len(state["tensile"]), 19)
        self.assertTrue(all(isinstance(value, int) for value in state["tensile"]))
        for name in ("accelerometer", "gyroscope", "magnetometer"):
            self.assertEqual(len(state[name]), 3)
            self.assertTrue(all(isinstance(value, float) for value in state[name]))
        self.assertIsInstance(state["temperature"], float)
        self.assertIsInstance(state["packet_timestamp_us"], int)

    def test_the_hand_option_selects_the_served_glove(self) -> None:
        self.serve(hand="right")
        self.assertEqual(self.state()["hand"], "right")

    def test_a_malformed_hand_option_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            load_driver(HERE, backend="fake", options={"hand": "middle"})

    # -- measurement capability ----------------------------------------------------------------------------------
    def test_a_measurement_returns_every_channel_or_only_the_requested_one(self) -> None:
        self.serve()
        state = self.state()
        everything = self.capture()
        self.assertEqual(everything["status"], "completed")
        values = everything["output"]["values"]
        self.assertEqual(set(values), {"tensile", "accelerometer", "gyroscope", "magnetometer",
                                       "temperature", "packet_timestamp_us",
                                       "hand", "acquisition"})
        self.assertIn("temperature", values)
        self.assertIn("tensile", values)
        self.assertIn("sampled_at", everything["output"])
        one = self.capture({"fields": ["temperature"]})
        self.assertEqual(one["output"]["values"], {"temperature": state["temperature"]})
        unknown = self.capture({"fields": ["temperature-alt"]})   # the conformance alternate of the class example
        self.assertEqual(unknown["status"], "completed")
        self.assertEqual(unknown["output"]["values"], {})

    def test_each_capture_returns_a_new_packet(self) -> None:
        self.serve()
        first = self.capture({"fields": ["packet_timestamp_us"]})["output"]["values"]["packet_timestamp_us"]
        second = self.capture({"fields": ["packet_timestamp_us"]})["output"]["values"]["packet_timestamp_us"]
        self.assertGreater(second, first)

    def test_a_native_failure_is_reported_not_hidden(self) -> None:
        self.serve()
        self.gloves._fail_next_read(RuntimeError("Serial port not connected."))
        with self.assertRaises(DriverFailed) as caught:
            self.driver.read_sensors(fields=["temperature"])
        self.assertEqual(caught.exception.code, NOT_READY)

    def test_a_failing_native_stop_is_not_hidden(self) -> None:
        self.serve()
        original = self.gloves.stop                  # the fake's native stop (OpenCyberGlove.stop, sdk.py:39-45)

        def boom():
            raise RuntimeError("serial line dropped during stop")

        self.gloves.stop = boom
        self.addCleanup(setattr, self.gloves, "stop", original)
        with self.assertRaises(RuntimeError):
            self.driver.stop()

    # -- e-stop, reset and recovery --------------------------------------------------------------------------------
    def test_the_estop_reaches_the_sdk_stop_and_freezes_acquisition(self) -> None:
        self.serve()
        before = self.state()
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.gloves._stops, 1)
        stopped = self.state()
        self.assertEqual(stopped["acquisition"], "stopped")
        self.assertEqual(stopped["tensile"], before["tensile"])      # the last held packet, not a new one
        self.assertEqual(stopped["packet_timestamp_us"], before["packet_timestamp_us"])
        held = self.capture({"fields": ["packet_timestamp_us", "acquisition"]})
        self.assertEqual(held["status"], "completed")
        self.assertEqual(held["output"]["values"],
                         {"packet_timestamp_us": before["packet_timestamp_us"], "acquisition": "stopped"})
        self.assertEqual(self.gloves._stops, 1)

    def test_a_reset_does_not_restart_acquisition(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        before = self.state()
        starts = self.gloves._starts
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.gloves._starts, starts)                # no auto-resume on reset
        after = self.state()
        self.assertEqual(after["acquisition"], "stopped")
        self.assertEqual(after["packet_timestamp_us"], before["packet_timestamp_us"])

    # -- reference and hardware boundary ---------------------------------------------------------------------------
    def test_the_reference_declares_the_provenance_and_the_native_stop(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(safety["estop"]["native"], "stop")
        self.assertEqual(safety["safe_state"]["achieved_by"], [])
        self.assertEqual(reference["device"]["risk"], "R1")
        facts = reference["facts"]
        self.assertTrue(any("input-only" in fact["text"] for fact in facts))
        self.assertTrue(any(fact["ref"] == "open_cyber_glove/glove.py:169" for fact in facts))

    def test_the_hardware_factory_needs_the_port_of_the_selected_hand(self) -> None:
        from importlib import util

        spec = util.spec_from_file_location("ocg_native_for_test", HERE / "native.py")
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaises(RuntimeError):
            module.connect(hand="left")
        with self.assertRaises(RuntimeError):
            module.connect(hand="right")
        with self.assertRaises(ValueError):
            module.connect(hand="middle", left_port="/dev/null")
        with self.assertRaises(TypeError):
            module.connect(hand="left", left_port="/dev/null", unexpected=True)


if __name__ == "__main__":
    unittest.main()
