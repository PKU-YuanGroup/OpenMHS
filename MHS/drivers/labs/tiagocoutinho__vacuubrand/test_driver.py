"""Acceptance run of the Vacuubrand DCP 3000 package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The numbers asserted here are the fake's placeholders, not device
facts or limits.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class VacuubrandCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_the_reads_are_published_in_pascals(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["pressure"], 100410.0)                      # fake placeholder in mbar
        self.assertEqual(state["transducer_pressures"], [36200.0, 23400.0, 27800.0, 21300.0])
        self.assertEqual(state["configuration"]["unit"], "mbar")
        self.assertEqual(state["configuration"]["nb_active_pressure_transducers"], 4)
        self.assertEqual(state["errors"], [])
        self.assertEqual(state["on_setpoint_1"], 11100.0)                  # fake placeholder in mbar
        self.assertEqual(state["recording_time_interval"], 5940)

    def test_the_set_points_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = client.write("main", {"on_setpoint_1": 5000}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["on_setpoint_1"], 11100.0)

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = client.write("main", {"on_setpoint_1": 5000, "event_time_interval": 30}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"]["applied"], {"on_setpoint_1": 5000.0, "event_time_interval": 30})
        state = self.state(client)
        self.assertEqual((state["on_setpoint_1"], state["event_time_interval"]), (5000.0, 30))
        for value in (99, 100001):
            refused = client.write("main", {"on_setpoint_1": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["on_setpoint_1"], 5000.0)

    def test_the_pressure_measurement_and_the_venting_commands(self) -> None:
        client = self.serve()
        measured = self.invoke(client, "cap.measure.pressure.v1", {"reference": "absolute"})
        self.assertEqual(measured["status"], "completed", measured)
        self.assertEqual(measured["output"]["pressure"], 100410.0)
        self.assertEqual(measured["output"]["reference"], "absolute")
        self.assertIn("sampled_at", measured["output"])
        for capability_id, output in (
            ("x-cap.tiagocoutinho.switch_on.v1", {"remote": True}),
            ("x-cap.tiagocoutinho.open_venting_valve.v1", {"venting_valve": "open"}),
            ("x-cap.tiagocoutinho.vent.v1", {"venting_valve": "venting"}),
            ("x-cap.tiagocoutinho.switch_off.v1", {"remote": False}),
            ("x-cap.tiagocoutinho.close_venting_valve.v1", {"venting_valve": "closed"}),
        ):
            receipt = self.invoke(client, capability_id)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["output"], output)

    def test_the_estop_releases_remote_control_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.tiagocoutinho.switch_on.v1")
        self.invoke(client, "x-cap.tiagocoutinho.open_venting_valve.v1")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertTrue(stopped["output"]["latched"])
        self.assertEqual(self.state(client)["pressure"], 0.0)              # REMOTE - stops the pressure reply
        refused = self.invoke(client, "x-cap.tiagocoutinho.switch_on.v1")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
