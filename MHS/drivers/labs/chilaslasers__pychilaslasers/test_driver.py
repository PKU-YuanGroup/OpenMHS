"""Acceptance run of the Chilas laser package: the gate, plus cases for what is specific to this driver.

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


class ChilasLaserCases(unittest.TestCase):
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

    def test_the_state_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["model"], "Unknown")
        self.assertFalse(state["calibrated"])
        self.assertFalse(state["system_state"])
        self.assertFalse(state["diode_enabled"])
        self.assertEqual(state["diode_current"], 20.0)          # the fake's placeholder
        self.assertEqual(state["diode_max_current"], 100.0)     # the fake's placeholder
        self.assertEqual(state["tec_temperature"], 24.5)        # the fake's placeholder
        self.assertEqual(state["tec_target"], 25.0)             # the fake's placeholder
        self.assertEqual(state["tec_current"], 10.0)            # the fake's placeholder

    def test_the_system_output_write(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, system_state=True)["status"], "completed")
        self.assertTrue(self.state(client)["system_state"])
        self.assertEqual(self.configure(client, system_state=False)["status"], "completed")
        self.assertFalse(self.state(client)["system_state"])

    def test_the_actions(self) -> None:
        client = self.serve()
        turned_on = client.invoke("x-cap.chilaslasers.turn_on.v1", {}, **self.ids)
        self.assertEqual(turned_on["output"], {"system_state": True})
        self.assertTrue(self.state(client)["system_state"])
        pulse = client.invoke("x-cap.chilaslasers.trigger_pulse.v1", {}, **self.ids)
        self.assertEqual(pulse["output"], {"triggered": True})
        turned_off = client.invoke("x-cap.chilaslasers.turn_off.v1", {}, **self.ids)
        self.assertEqual(turned_off["output"], {"system_state": False, "diode_enabled": False})
        self.assertFalse(self.state(client)["system_state"])

    def test_the_ranges_wait_for_the_site(self) -> None:
        client = self.serve()
        for capability_id, payload in (
            ("x-cap.chilaslasers.set_diode_current.v1", {"current_ma": 50.0}),
            ("x-cap.chilaslasers.set_tec_target.v1", {"target_temp": 20.0}),
        ):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, capability_id)

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        applied = client.invoke("x-cap.chilaslasers.set_diode_current.v1", {"current_ma": 50.0}, **self.ids)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(applied["output"], {"current_ma": 50.0})
        self.assertEqual(self.state(client)["diode_current"], 50.0)
        target = client.invoke("x-cap.chilaslasers.set_tec_target.v1", {"target_temp": 20.0}, **self.ids)
        self.assertEqual(target["status"], "completed")
        self.assertEqual(target["output"], {"target_temp": 20.0})
        self.assertEqual(self.state(client)["tec_target"], 20.0)
        for capability_id, payload in (
            ("x-cap.chilaslasers.set_diode_current.v1", {"current_ma": 150.0}),
            ("x-cap.chilaslasers.set_tec_target.v1", {"target_temp": 50.0}),
        ):
            refused = client.invoke(capability_id, payload, **self.ids)
            self.assertEqual(refused["status"], "rejected", capability_id)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, capability_id)

    def test_the_estop_disables_the_output_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.chilaslasers.turn_on.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["system_state"])
        self.assertFalse(state["diode_enabled"])
        refused = client.invoke("x-cap.chilaslasers.turn_on.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
