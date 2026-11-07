"""Acceptance run of the Dino-Lite package: the gate, plus cases for what is specific to this driver.

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

# The fake's placeholder starting values (fake.py); tests, not Facts.
FAKE_DEVICE_NAME = "Dino-Lite AM7515 (fake)"
FAKE_DEVICE_ID = "FAKE-0000"
FAKE_EXPOSURE = 10
FAKE_AE_TARGET = 18


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DinoLiteCases(unittest.TestCase):
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

    def test_the_reads(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["device_name"], FAKE_DEVICE_NAME)
        self.assertEqual(state["device_id"], FAKE_DEVICE_ID)
        self.assertEqual(state["exposure_value"], FAKE_EXPOSURE)
        self.assertEqual(state["ae_target"], FAKE_AE_TARGET)
        self.assertFalse(state["auto_exposure"])

    def test_the_ae_target_envelope(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, ae_target=17)["status"], "completed")
        self.assertEqual(self.state(client)["ae_target"], 17)
        for value in (15, 21):
            refused = self.configure(client, ae_target=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["ae_target"], 17)

    def test_the_auto_exposure_write(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, auto_exposure=True)["status"], "completed")
        self.assertTrue(self.state(client)["auto_exposure"])
        self.assertEqual(self.configure(client, auto_exposure=False)["status"], "completed")
        self.assertFalse(self.state(client)["auto_exposure"])

    def test_the_exposure_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, exposure_value=42)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["exposure_value"], FAKE_EXPOSURE)

    def test_the_example_overlay_supplies_the_exposure_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, exposure_value=42)["status"], "completed")
        self.assertEqual(self.state(client)["exposure_value"], 42)
        for value in (0, 1001):
            refused = self.configure(client, exposure_value=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["exposure_value"], 42)

    def test_the_led_and_flc_actions(self) -> None:
        client = self.serve()
        led = client.invoke("x-cap.williamtsalter.set_led.v1", {"enabled": False}, **self.ids)
        self.assertEqual(led["status"], "completed")
        self.assertEqual(led["output"], {"enabled": False})
        flc = client.invoke("x-cap.williamtsalter.set_flc_level.v1", {"level": 4}, **self.ids)
        self.assertEqual(flc["status"], "completed")
        self.assertEqual(flc["output"], {"level": 4})
        for value in (0, 7):
            refused = client.invoke("x-cap.williamtsalter.set_flc_level.v1", {"level": value}, **self.ids)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)

    def test_the_safe_state_and_the_estop_latch(self) -> None:
        client = self.serve()
        off = client.invoke("x-cap.williamtsalter.switch_off_illumination.v1", {}, **self.ids)
        self.assertEqual(off["status"], "completed")
        self.assertEqual(off["output"], {"led_on": False})
        client.estop("test", **self.ids)
        refused = client.invoke("x-cap.williamtsalter.set_led.v1", {"enabled": True}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
