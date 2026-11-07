"""Acceptance run of the BMG package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The fake follows the upstream method bodies over an in-memory COM
stand-in (fake.py); every value it answers is a placeholder, not a device fact.
"""

import tempfile
import unittest
from pathlib import Path

from mhs.adapter import LoadError, close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
HEATER_OFF = "x-cap.ad-sdl.bmg_heater_off.v1"
CONFIGURE = "cap.device.configure.v1"
# A test overlay for an extended-temperature-range unit (not a statement about any installed device).
EXTENDED_OVERLAY = {
    "$schema": "https://openmhs.invalid/schema/0.9/site-limits.schema.json",
    "openmhs": "0.9",
    "site": "Test bench (extended-range BMG reader)",
    "issued_by": {"id": "operator:test"},
    "devices": {
        "mhs://localhost/bmg-reader": {
            "setpoint": {"min": 10.0, "max": 60.0, "unit": "Cel", "source": "operator",
                         "reason": "test only: an extended-temperature-range unit"},
        },
    },
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BmgCases(unittest.TestCase):
    def serve(self, site_limits=None, **options):
        server = load(HERE, backend="fake", site_limits=site_limits, options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.com = server.devices[device_id].bridge.native.com   # the fake's in-memory COM object
        return client

    def configure(self, client, **patch):
        return client.invoke(CONFIGURE, patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_reads_are_the_three_sensors_and_the_com_strings(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["version"], "fake BMG remote control")
        self.assertEqual(state["status"], "Idle")            # stripped, as the upstream does
        self.assertEqual(state["error"], "")
        self.assertEqual((state["temperature_1"], state["temperature_2"], state["temperature_3"]),
                         (25.0, 25.0, 25.0))                 # raw GetInfo 250 divided by 10
        self.assertNotIn("setpoint", state)                  # nothing written yet

    def test_a_sensor_without_a_number_is_left_out_of_the_state(self) -> None:
        client = self.serve()
        self.com.info["Temp2"] = None                        # GetInfo gives no value
        self.com.info["Temp3"] = "n/a"                       # a value float() cannot parse
        state = self.state(client)
        self.assertEqual(state["temperature_1"], 25.0)
        self.assertNotIn("temperature_2", state)
        self.assertNotIn("temperature_3", state)

    def test_a_status_or_error_that_is_not_text_reads_unknown(self) -> None:
        client = self.serve()
        self.com.info["Status"] = None
        self.com.info["Error"] = 7
        state = self.state(client)
        self.assertEqual((state["status"], state["error"]), ("unknown", "unknown"))

    def test_the_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=37)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.com.executed, [])
        self.assertNotIn("setpoint", self.state(client))

    def test_the_example_overlay_supplies_a_standard_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=36.5)["status"], "completed")
        self.assertEqual(self.com.executed, [("Temp", "36.5")])
        self.assertEqual(self.state(client)["setpoint"], 36.5)
        for value in (24.9, 45.1):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.com.executed, [("Temp", "36.5")])
        self.assertEqual(self.state(client)["setpoint"], 36.5)

    def test_the_native_validator_follows_the_model_flag(self) -> None:
        client = self.serve(EXTENDED_OVERLAY)                # a standard-range model behind a wider overlay
        refused = self.configure(client, setpoint=50.0)
        self.assertEqual(refused["status"], "failed")        # the upstream ValueError
        self.assertEqual(self.com.executed, [])
        self.assertNotIn("setpoint", self.state(client))
        client = self.serve(EXTENDED_OVERLAY, extended_temperature_range_model=True)
        self.assertEqual(self.configure(client, setpoint=50.0)["status"], "completed")
        self.assertEqual(self.com.executed, [("Temp", "50.0")])

    def test_a_refused_temp_command_fails_the_write(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.com.responses["Temp"] = 3                       # placeholder non-zero ExecuteAndWait answer
        failed = self.configure(client, setpoint=36.5)
        self.assertEqual(failed["status"], "failed")
        self.assertNotIn("setpoint", self.state(client))

    def test_the_estop_switches_the_heater_off_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=36.5)["status"], "completed")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertTrue(stopped["output"]["safe_state_achieved"])
        # the @estop method and the safe-state action each send Temp 0.0 (a direct driver sends both)
        self.assertEqual(self.com.executed, [("Temp", "36.5"), ("Temp", "0.0"), ("Temp", "0.0")])
        self.assertEqual(self.state(client)["setpoint"], 36.5)   # the last value written, as the description says
        refused = self.configure(client, setpoint=36.5)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        off = client.invoke(HEATER_OFF, {}, **self.ids)      # the safe-state action stays callable
        self.assertEqual(off["output"], {"heating_off": True})

    def test_an_unacknowledged_heater_off_leaves_the_estop_unreached(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=36.5)["status"], "completed")
        self.com.responses["Temp"] = 5                       # placeholder non-zero ExecuteAndWait answer
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        self.assertEqual(stopped["error"]["details"]["reason"], "native_failed")
        self.assertTrue(stopped["error"]["details"]["latched"])
        refused = self.configure(client, setpoint=30.0)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_tray_and_the_assay_are_not_served(self) -> None:
        client = self.serve()
        served = {cap["capability_id"] for cap in client.inspect(self.ids["device_id"])["capabilities"]}
        self.assertEqual(served, {CONFIGURE, HEATER_OFF})
        refused = client.invoke("x-cap.ad-sdl.bmg_run_assay.v1", {"assay_name": "A"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(self.com.executed, [])

    def test_the_hardware_backend_waits_for_a_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as state:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, "hardware", allow_hardware=True, state_dir=state)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
