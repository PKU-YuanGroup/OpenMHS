"""Acceptance run of the AVIS Engine package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py), whose ``_commands``
list records what reached the stand-in car.  Nothing here ran the external simulator or a vehicle.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class AvisEngineCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.car = driver.native                              # the fake Car
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.car._commands[:]                             # forget the set-up
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self, name=None):
        return [args for command, args in self.car._commands if name is None or command == name]

    # -- reads and writes ---------------------------------------------------------------------------------------
    def test_the_initial_state_is_the_fake_stand_in(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual(state["speed"], 0)                   # placeholder
        self.assertEqual(state["sensors"], [1500, 1500, 1500])  # placeholder
        self.assertEqual((state["throttle"], state["steering"], state["sensor_angle"]), (0, 0, 30))  # placeholders

    def test_a_write_reaches_car_and_the_state_reads_it_back(self) -> None:
        self.serve()
        receipt = self.client.write("main", {"throttle": 20, "steering": -10}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.sent("setSpeed"), [20])
        self.assertEqual(self.sent("setSteering"), [-10])
        state = self.state()
        self.assertEqual((state["throttle"], state["steering"]), (20, -10))
        self.assertEqual(state["speed"], 20)                  # the fake reports the throttle as speed (placeholder)

    def test_the_documented_ranges_are_refused_before_car(self) -> None:
        self.serve()
        for name, value, bound in (("throttle", 101, 100), ("throttle", -101, -100),
                                   ("steering", 101, 100), ("steering", -101, -100)):
            refused = self.client.write("main", {name: value}, **self.ids)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), (name, value))
            self.assertEqual((refused["error"]["details"]["path"], refused["error"]["details"]["bound"]),
                             (name, bound))
        self.assertEqual(self.sent("setSpeed"), [])
        self.assertEqual(self.sent("setSteering"), [])
        for name, value in (("throttle", 100), ("throttle", -100), ("steering", 100), ("steering", -100)):
            self.assertEqual(self.client.write("main", {name: value}, **self.ids)["status"], "completed")

    def test_the_sensor_angle_waits_for_the_site_and_the_overlay_narrows(self) -> None:
        client = self.serve()
        refused = client.write("main", {"sensor_angle": 45}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.sent("setSensorAngle"), [])
        client = self.serve(OVERLAY)
        self.assertEqual(client.write("main", {"sensor_angle": 45}, **self.ids)["status"], "completed")
        self.assertEqual(self.sent("setSensorAngle"), [45])
        for value in (-1, 91):                                # the example overlay allows 0..90 deg
            refused = client.write("main", {"sensor_angle": value}, **self.ids)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), value)
        self.assertEqual(self.sent("setSensorAngle"), [45])

    # -- stop and e-stop ----------------------------------------------------------------------------------------
    def test_stop_zeroes_the_commands_and_reaches_car(self) -> None:
        self.serve()
        self.client.write("main", {"throttle": 20, "steering": 10}, **self.ids)
        del self.car._commands[:]
        receipt = self.client.invoke("cap.motion.stop.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True})
        self.assertEqual(len(self.sent("stop")), 1)
        self.assertEqual((self.car.speed_value, self.car.steering_value), (0, 0))

    def test_the_estop_reaches_the_single_native_stop_and_latches(self) -> None:
        self.serve()
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(self.sent("stop")), 1)
        self.assertEqual(self.car._stop_calls, 1)
        speed_calls = len(self.sent("setSpeed"))          # the e-stop's own Car.stop set speed 0
        refused = self.client.write("main", {"throttle": 10}, **self.ids)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(len(self.sent("setSpeed")), speed_calls)   # the latched write reached nothing
        self.assertEqual(self.client.reset(**self.ids)["status"], "completed")
        self.assertEqual(self.client.write("main", {"throttle": 10}, **self.ids)["status"], "completed")

    # -- the declared package -----------------------------------------------------------------------------------
    def test_the_reference_declares_the_site_bound_and_the_fake_only_backend(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual((reference["device"]["kind"], reference["device"]["mode"]), ("robot.mobile_base", "simulated"))
        self.assertEqual(reference["safety"]["estop"]["native"], "stop")
        self.assertEqual([item["name"] for item in reference["safety"]["operator_required"]], ["sensor_angle"])
        self.assertEqual({item["name"] for item in reference["adjusts"]}, {"throttle", "steering", "sensor_angle"})
        lock = json.loads((HERE / "driver.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["backends"], {"fake": ".fake:FakeCar"})
        self.assertIsNone(lock["reviewed_by"])


if __name__ == "__main__":
    unittest.main()
