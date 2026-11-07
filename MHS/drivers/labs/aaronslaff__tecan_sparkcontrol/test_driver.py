"""Acceptance run of the SparkControl package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
CALIBRATE = "x-cap.aaronslaff.calibrate_instrument.v1"
START = "x-cap.aaronslaff.start_method.v1"
STOP = "x-cap.aaronslaff.stop_method.v1"
STOP_ACTIVE = "x-cap.aaronslaff.stop_active_method.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SparkControlCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_initial_reads_return_the_fake_documents(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["instrument_status"], {"state": "idle"})
        self.assertEqual(state["available_apps"], {"apps": []})
        self.assertEqual(state["instrument_settings"], {"settings": {}})
        self.assertEqual(state["plate_geometry"],
                         {"plate_type": "96-well microplate", "rows": 8, "columns": 12})
        self.assertEqual(state["method_status"], {})
        self.assertEqual(state["measurement_results"], {})

    def test_the_method_lifecycle_is_visible_in_the_reads(self) -> None:
        client = self.serve()
        started = client.invoke(START, {"method_id": "method-1"}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        self.assertEqual(started["output"]["response"]["status"], "running")
        state = self.state(client)
        self.assertEqual(state["method_status"], {"method_id": "method-1", "status": "running"})
        self.assertEqual(state["measurement_results"], {"method_id": "method-1", "results": []})

        stopped = client.invoke(STOP, {"method_id": "method-1"}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["response"]["status"], "stopped")
        self.assertEqual(self.state(client)["method_status"]["status"], "stopped")

    def test_the_calibration_reaches_the_native(self) -> None:
        client = self.serve()
        calibrated = client.invoke(CALIBRATE, {"calibration_type": "wavelength"}, **self.ids)
        self.assertEqual(calibrated["status"], "completed", calibrated)
        self.assertEqual(calibrated["output"]["response"],
                         {"calibration_type": "wavelength", "status": "completed"})

    def test_the_estop_stops_the_tracked_method_and_latches(self) -> None:
        client = self.serve()
        self.assertEqual(client.invoke(START, {"method_id": "method-1"}, **self.ids)["status"], "completed")
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["method_status"]["status"], "stopped")
        refused = client.invoke(START, {"method_id": "method-2"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_safe_state_action_reports_when_no_method_is_tracked(self) -> None:
        client = self.serve()
        stopped = client.invoke(STOP_ACTIVE, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"], {"stopped": False, "method_id": ""})


if __name__ == "__main__":
    unittest.main()
