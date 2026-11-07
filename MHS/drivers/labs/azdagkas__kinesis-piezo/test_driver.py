"""Acceptance run of the Kinesis piezo package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
CALIBRATE = "x-cap.azdagkas.kinesis_piezo.calibrate_position.v1"
JOG_UP = "x-cap.azdagkas.kinesis_piezo.jog_up.v1"
JOG_DOWN = "x-cap.azdagkas.kinesis_piezo.jog_down.v1"
HOME = "x-cap.azdagkas.kinesis_piezo.move_to_home.v1"
MOVE_TO_POSITION = "x-cap.azdagkas.kinesis_piezo.move_to_position.v1"
ZERO = "x-cap.azdagkas.kinesis_piezo.zero_reader.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class KinesisPiezoCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["value"], 50.0)          # placeholder start, closed loop
        self.assertEqual(state["units"], "%")
        self.assertTrue(state["closed_loop"])
        self.assertEqual(state["reader_reading"], 10.0)  # placeholder start
        self.assertEqual(state["reader_units"], "\u03bcm")
        self.assertFalse(state["zeroing"])

    def test_the_value_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, value=5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["value"], 50.0)

    def test_the_example_overlay_sets_the_value(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        changed = self.configure(client, value=12.5)
        self.assertEqual(changed["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["value"], 12.5)
        self.assertEqual(state["reader_reading"], 2.5)
        for bad in (-0.5, 75.5):
            refused = self.configure(client, value=bad)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, bad)
        self.assertEqual(self.state(client)["value"], 12.5)

    def test_the_loop_mode_switches_the_unit(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        opened = self.configure(client, closed_loop=False)
        self.assertEqual(opened["status"], "completed")
        state = self.state(client)
        self.assertFalse(state["closed_loop"])
        self.assertEqual(state["units"], "V")
        self.assertEqual(state["value"], 0.0)           # placeholder starting output voltage
        self.assertEqual(self.configure(client, value=10)["status"], "completed")
        self.assertEqual(self.state(client)["value"], 10.0)
        self.assertEqual(self.configure(client, closed_loop=True)["status"], "completed")
        state = self.state(client)
        self.assertTrue(state["closed_loop"])
        self.assertEqual(state["units"], "%")
        self.assertEqual(state["value"], 50.0)

    def test_home_and_the_jog_steps(self) -> None:
        client = self.serve()
        homed = self.invoke(client, HOME)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"value": 0.0})
        self.assertEqual(self.state(client)["value"], 0.0)
        up = self.invoke(client, JOG_UP)
        self.assertEqual(up["output"], {"value": 1.0})
        self.assertEqual(self.invoke(client, JOG_DOWN)["output"], {"value": 0.0})
        self.assertEqual(self.state(client)["value"], 0.0)

    def test_the_calibration_and_the_calibrated_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        calibrated = self.invoke(client, CALIBRATE)
        self.assertEqual(calibrated["status"], "completed")
        self.assertEqual(calibrated["output"], {"calibrated": True})
        state = self.state(client)
        self.assertEqual(state["reader_reading"], 1.0)   # calibrate_pos ends at 1 reader unit
        self.assertEqual(state["value"], 5.0)
        moved = self.invoke(client, MOVE_TO_POSITION, {"position": 5.0})
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"position": 5.0})
        state = self.state(client)
        self.assertEqual(state["reader_reading"], 5.0)
        self.assertEqual(state["value"], 25.0)
        refused = self.invoke(client, MOVE_TO_POSITION, {"position": 20.5})
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["reader_reading"], 5.0)

    def test_the_calibration_needs_closed_loop(self) -> None:
        client = self.serve()
        self.configure(client, closed_loop=False)
        refused = self.invoke(client, CALIBRATE)
        self.assertEqual(refused["status"], "failed")
        self.assertEqual(refused["error"]["mhs_code"], PRECONDITION)

    def test_zeroing_the_reader(self) -> None:
        client = self.serve()
        zeroed = self.invoke(client, ZERO)
        self.assertEqual(zeroed["status"], "completed")
        self.assertEqual(zeroed["output"], {"zeroing": True})
        state = self.state(client)
        self.assertEqual(state["reader_reading"], 0.0)
        self.assertTrue(state["zeroing"])

    def test_the_estop_homes_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, JOG_UP)
        self.assertEqual(self.state(client)["value"], 51.0)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["value"], 0.0)
        refused = self.invoke(client, JOG_UP)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
