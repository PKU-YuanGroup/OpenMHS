"""Acceptance run of the RP2DAQ package: the gate, plus cases for what is specific to this driver.

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


class Rp2daqCases(unittest.TestCase):
    def serve(self, site_limits=str(HERE / "site-limits.example.json")):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_initial_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["gpio_pin"], 25)
        self.assertEqual(state["gpio_level"], 0)
        self.assertGreaterEqual(state["adc_mean"], 0)
        self.assertLessEqual(state["adc_mean"], 4095)
        self.assertEqual(state["stepper_position"], 0)
        self.assertFalse(state["stepper_moving"])

    def test_gpio_adc_pwm_and_stepper(self) -> None:
        client = self.serve()
        written = client.invoke("cap.device.configure.v1", {"gpio_pin": 13, "gpio_level": 1}, **self.ids)
        self.assertEqual(written["status"], "completed")
        state = self.state(client)
        self.assertEqual((state["gpio_pin"], state["gpio_level"]), (13, 1))

        sampled = client.invoke("x-cap.filipdominec.adc_sample.v1",
                                {"channel_mask": 1, "blocksize": 4, "clkdiv": 95}, **self.ids)
        self.assertEqual(sampled["status"], "completed")
        self.assertEqual(sampled["output"]["sample_count"], 4)
        self.assertEqual(sampled["output"]["channel_mask"], 1)

        pwm = client.invoke("x-cap.filipdominec.pwm_set.v1",
                            {"pin": 0, "value": 100, "wrap_value": 999, "clkdiv": 1,
                             "clkdiv_int_frac": 0, "phase_correct": 0}, **self.ids)
        self.assertEqual(pwm["status"], "completed")
        self.assertEqual(pwm["output"], {"pin": 0, "value": 100, "configured": True})

        started = client.invoke("x-cap.filipdominec.stepper_init.v1",
                                {"stepper_number": 0, "dir_gpio": 2, "step_gpio": 3,
                                 "endswitch_gpio": 4, "disable_gpio": 5, "inertia": 30}, **self.ids)
        self.assertEqual(started["status"], "completed")
        moved = client.invoke("x-cap.filipdominec.stepper_move.v1",
                              {"stepper_number": 0, "to": 1000, "speed": 100, "relative": 0}, **self.ids)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["nanopos"], 1000)
        self.assertEqual(self.state(client)["stepper_position"], 1000)

    def test_the_estop_holds_the_stepper_and_latches(self) -> None:
        client = self.serve()
        client.invoke("cap.device.configure.v1", {"gpio_pin": 13, "gpio_level": 1}, **self.ids)
        client.invoke("x-cap.filipdominec.stepper_init.v1",
                      {"stepper_number": 0, "dir_gpio": 2, "step_gpio": 3,
                       "endswitch_gpio": 4, "disable_gpio": 5, "inertia": 30}, **self.ids)
        client.invoke("x-cap.filipdominec.stepper_move.v1",
                      {"stepper_number": 0, "to": 1000, "speed": 100, "relative": 0}, **self.ids)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["gpio_level"], 0)              # the safe state drives configured outputs low
        self.assertEqual(state["stepper_position"], 1000)     # held at the position it had reached
        refused = client.invoke("cap.device.configure.v1", {"gpio_level": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_a_move_needs_the_sites_travel(self) -> None:
        client = self.serve(site_limits=None)
        client.invoke("x-cap.filipdominec.stepper_init.v1",
                      {"stepper_number": 0, "dir_gpio": 2, "step_gpio": 3,
                       "endswitch_gpio": 4, "disable_gpio": 5, "inertia": 30}, **self.ids)
        refused = client.invoke("x-cap.filipdominec.stepper_move.v1",
                                {"stepper_number": 0, "to": 1000, "speed": 100, "relative": 0}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_envelope_is_enforced(self) -> None:
        client = self.serve()
        refused = client.invoke("cap.device.configure.v1", {"gpio_pin": 26}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = client.invoke("x-cap.filipdominec.adc_sample.v1",
                                {"channel_mask": 0, "blocksize": 4, "clkdiv": 95}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)


if __name__ == "__main__":
    unittest.main()
