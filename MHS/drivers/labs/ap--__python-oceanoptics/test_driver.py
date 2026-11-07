"""Acceptance run of the Ocean Optics TEC package: the gate, plus cases for what is specific to this driver.

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


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OceanOpticsTECCases(unittest.TestCase):
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

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def test_the_setpoint_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=-20.0)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        action = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": -20.0}, **self.ids)
        self.assertEqual(action["status"], "rejected")
        self.assertEqual(action["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["setpoint"], -15.0)     # the fake start value, untouched

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = self.configure(client, setpoint=-20.0)
        self.assertEqual(completed["status"], "completed", completed)
        self.assertEqual(self.state(client)["setpoint"], -20.0)
        action = client.invoke("cap.thermal.setpoint.v1", {"target_temperature": -30.0}, **self.ids)
        self.assertEqual(action["status"], "completed", action)
        self.assertEqual(action["output"]["setpoint"], -30.0)
        self.assertEqual(self.state(client)["setpoint"], -30.0)
        for value in (-40.5, 0.5):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["setpoint"], -30.0)

    def test_the_reads_and_the_safe_state_action(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["tec_temperature"], state["pcb_temperature"], state["heatsink_temperature"]),
                         (-10.0, 25.0, 24.0))
        self.assertEqual((state["setpoint"], state["tec_enabled"], state["fan_enabled"]), (-15.0, True, True))
        off = client.invoke("x-cap.ap.tec_safe_off.v1", {}, **self.ids)
        self.assertEqual(off["status"], "completed", off)
        self.assertEqual(off["output"], {"tec_enabled": False, "fan_enabled": True})
        state = self.state(client)
        self.assertFalse(state["tec_enabled"])
        self.assertTrue(state["fan_enabled"])

    def test_the_estop_switches_the_tec_off_and_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=-20.0)["status"], "completed")
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["tec_enabled"])
        self.assertTrue(state["fan_enabled"])
        refused = self.configure(client, setpoint=-20.0)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
