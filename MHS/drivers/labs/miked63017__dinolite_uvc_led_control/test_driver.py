"""Acceptance run of the Dino-Lite package: the gate, plus cases for what is specific to this driver.

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


class DinoliteCases(unittest.TestCase):
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

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def test_initial_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["main_led_on"], True)
        self.assertEqual(state["flc_on"], False)
        self.assertEqual(state["flc_brightness"], 6)
        self.assertEqual(state["auto_exposure"], True)
        self.assertEqual(state["exposure_time"], "1/8s")
        self.assertEqual(state["product_id"], "0980")
        self.assertEqual(state["video_device"], "/dev/video0")

    def test_main_led_switches_and_follows_the_state(self) -> None:
        client = self.serve()
        receipt = self.invoke(client, "x-cap.miked63017.set_illumination.v1",
                              {"channel": "main", "on": False})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"channel": "main", "on": False})
        self.assertFalse(self.state(client)["main_led_on"])
        receipt = self.invoke(client, "x-cap.miked63017.set_illumination.v1",
                              {"channel": "main", "on": True})
        self.assertEqual(receipt["output"], {"channel": "main", "on": True})
        self.assertTrue(self.state(client)["main_led_on"])

    def test_flc_brightness_enables_flc_and_moves_one_level_at_a_time(self) -> None:
        client = self.serve()
        receipt = self.invoke(client, "x-cap.miked63017.set_flc_brightness.v1", {"level": 2})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"level": 2})
        state = self.state(client)
        self.assertTrue(state["flc_on"])
        self.assertEqual(state["flc_brightness"], 2)
        receipt = self.invoke(client, "x-cap.miked63017.set_flc_brightness.v1", {"level": 5})
        self.assertEqual(receipt["output"], {"level": 5})
        self.assertEqual(self.state(client)["flc_brightness"], 5)

    def test_toggle_one_fcl_led(self) -> None:
        client = self.serve()
        first = self.invoke(client, "x-cap.miked63017.toggle_flc_led.v1", {"led": 1})
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["output"], {"led": 1, "off": True})
        second = self.invoke(client, "x-cap.miked63017.toggle_flc_led.v1", {"led": 1})
        self.assertEqual(second["output"], {"led": 1, "off": False})

    def test_auto_exposure_and_exposure_steps(self) -> None:
        client = self.serve()
        toggled = self.invoke(client, "x-cap.miked63017.toggle_auto_exposure.v1")
        self.assertEqual(toggled["output"], {"enabled": False})
        self.assertFalse(self.state(client)["auto_exposure"])
        longer = self.invoke(client, "x-cap.miked63017.step_exposure.v1", {"direction": "increase"})
        self.assertEqual(longer["status"], "completed")
        self.assertEqual(longer["output"], {"exposure_time": "1/4s", "direction": "increase"})
        self.assertEqual(self.state(client)["exposure_time"], "1/4s")
        shorter = self.invoke(client, "x-cap.miked63017.step_exposure.v1", {"direction": "decrease"})
        self.assertEqual(shorter["output"], {"exposure_time": "1/8s", "direction": "decrease"})
        self.assertEqual(self.state(client)["exposure_time"], "1/8s")

    def test_step_exposure_turns_auto_exposure_off_first(self) -> None:
        client = self.serve()
        receipt = self.invoke(client, "x-cap.miked63017.step_exposure.v1", {"direction": "increase"})
        self.assertEqual(receipt["status"], "completed")
        self.assertFalse(self.state(client)["auto_exposure"])
        self.assertEqual(self.state(client)["exposure_time"], "1/4s")

    def test_out_of_envelope_is_refused_without_a_change(self) -> None:
        client = self.serve()
        refused = self.invoke(client, "x-cap.miked63017.set_flc_brightness.v1", {"level": 7})
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused_led = self.invoke(client, "x-cap.miked63017.toggle_flc_led.v1", {"led": 5})
        self.assertEqual(refused_led["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertFalse(state["flc_on"])
        self.assertEqual(state["flc_brightness"], 6)

    def test_illumination_off_is_the_safe_state(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.miked63017.set_flc_brightness.v1", {"level": 3})
        self.assertTrue(self.state(client)["flc_on"])
        off = self.invoke(client, "x-cap.miked63017.illumination_off.v1")
        self.assertEqual(off["output"], {"on": False})
        state = self.state(client)
        self.assertFalse(state["flc_on"])
        self.assertFalse(state["main_led_on"])

    def test_the_estop_switches_illumination_off_and_latches(self) -> None:
        client = self.serve()
        self.invoke(client, "x-cap.miked63017.set_flc_brightness.v1", {"level": 3})
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertFalse(state["flc_on"])
        self.assertFalse(state["main_led_on"])
        refused = self.invoke(client, "x-cap.miked63017.set_illumination.v1",
                              {"channel": "main", "on": True})
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
