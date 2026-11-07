"""Acceptance run of the Sartorius balance package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SartoriusCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
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

    def test_the_initial_state(self) -> None:
        state = self.state(self.serve())
        self.assertEqual(state["net_weight"], 12345.0)          # 12.345 g, placeholder fake data
        self.assertEqual(state["gross_weight"], 12845.0)        # net + 0.5 g tare, placeholder fake data
        self.assertEqual(state["tare_value"], 500.0)
        self.assertTrue(state["stable"])
        self.assertEqual(state["status_state"], "stable")
        self.assertEqual(state["display_unit"], "g")
        self.assertEqual(state["filter_mode"], "stable")
        self.assertEqual(state["auto_zero"], "on")
        self.assertEqual(state["isocal_mode"], "off")
        self.assertEqual(state["tare_behavior"], "with_stability")
        self.assertEqual(state["menu_access"], "can_edit")
        self.assertEqual(state["model"], "MSE1203S-100-DR")      # placeholder fake data
        self.assertEqual(state["serial"], "0000000000")
        self.assertEqual(state["software"], "1.0.0")

    def test_a_setting_write_reaches_the_fake_and_is_reflected(self) -> None:
        client = self.serve()
        applied = self.configure(client, filter_mode="very_stable", menu_access="read_only")
        self.assertEqual(applied["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["filter_mode"], "very_stable")
        self.assertEqual(state["menu_access"], "read_only")

    def test_the_display_unit_write_keeps_the_mass_in_milligrams(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, display_unit="kg")["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["display_unit"], "kg")
        self.assertEqual(state["net_weight"], 12345.0)          # 0.012345 kg converted to mg

    def test_an_unknown_setting_value_is_refused_without_a_write(self) -> None:
        client = self.serve()
        refused = self.configure(client, display_unit="lb")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.state(client)["display_unit"], "g")

    def test_measure_mass_returns_milligrams_and_stability(self) -> None:
        client = self.serve()
        measured = client.invoke("cap.measure.mass.v1", {}, **self.ids)
        self.assertEqual(measured["status"], "completed")
        self.assertEqual(measured["output"]["mass"], 12345.0)
        self.assertTrue(measured["output"]["stable"])
        self.assertIn("sampled_at", measured["output"])

    def test_measure_mass_selects_the_channel_and_refuses_an_unknown_one(self) -> None:
        client = self.serve()
        gross = client.invoke("cap.measure.mass.v1", {"channel": "gross", "settle": True}, **self.ids)
        self.assertEqual(gross["status"], "completed")
        self.assertEqual(gross["output"]["mass"], 12845.0)
        refused = client.invoke("cap.measure.mass.v1", {"channel": "lb"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_closes_the_transport_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["net_weight"], 12345.0)
        refused = self.configure(client, filter_mode="very_stable")
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
