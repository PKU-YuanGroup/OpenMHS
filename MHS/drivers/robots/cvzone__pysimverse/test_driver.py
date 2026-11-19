"""Acceptance run of the pysimverse drone package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its private ``_commands``
list is what the "simulator" received.  Nothing here ran a ZMQ server, the upstream simulator or a device.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import LoadError, load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
TAKEOFF = "x-cap.cvzone.takeoff.v1"
LAND = "x-cap.cvzone.land.v1"
MOVE = "x-cap.cvzone.move.v1"
ROTATE = "x-cap.cvzone.rotate.v1"
CAMERA = "x-cap.cvzone.rotate_camera.v1"
STOP = "x-cap.cvzone.stop.v1"


def rc(left_right=0, forward_backward=0, up_down=0, yaw=0, cameraangle=0):
    return {"left_right": left_right, "forward_backward": forward_backward, "up_down": up_down, "yaw": yaw,
            "cameraangle": cameraangle, "streamon": None,
            "color": {"red": None, "green": None, "blue": None}}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PysimverseCases(unittest.TestCase):
    def serve(self, overlay=True):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=OVERLAY if overlay else None)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.fake = driver.native
        self.client = client_for(server)
        self.device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[self.device_id])["session_id"]
        self.ids = {"device_id": self.device_id, "session_id": session}
        del self.fake._commands[:]                      # forget the setup connect()
        return self.client

    def invoke(self, capability_id, payload):
        return self.client.invoke(capability_id, payload, **self.ids)

    def takeoff(self, height=100, speed=50):
        return self.invoke(TAKEOFF, {"takeoff_height": height, "takeoff_speed": speed})

    def move(self, direction, distance=10):
        return self.invoke(MOVE, {"direction": direction, "distance": distance})

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def commands(self):
        return list(self.fake._commands)

    # -- initial state and reference -------------------------------------------------------------------------
    def test_initial_reads_and_the_declared_fidelity(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual((state["is_flying"], state["speed"], state["rotation_speed"], state["stream_on"]),
                         (False, 300.0, 15.0, False))
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual(reference["device"]["mode"], "simulated")
        self.assertEqual(reference["device"]["risk"], "R2")
        self.assertEqual(reference["fidelity"]["fidelity_level"], "F0")
        self.assertEqual(reference["fidelity"]["engine"], "analytic")
        self.assertEqual(reference["safety"]["estop"]["native"], "send_rc_control")
        self.assertEqual(reference["safety"]["safe_state"].get("achieved_by", []), [])
        self.assertIsNone(self.driver.reset_hook)
        self.assertIsNone(type(self.driver).driver_model().reenable)

    def test_the_only_backend_is_the_package_fake(self) -> None:
        with self.assertRaises(LoadError):
            load_driver(HERE, backend="hardware")

    # -- motion -----------------------------------------------------------------------------------------------
    def test_takeoff_and_land_publish_the_native_command_pairs(self) -> None:
        self.serve()
        taken = self.takeoff(100, 50)
        self.assertEqual(taken["status"], "completed", taken)
        self.assertEqual(taken["output"], {"is_flying": True, "takeoff_height": 100, "takeoff_speed": 50,
                                           "applied": True})
        self.assertEqual(self.commands(), [rc(up_down=50), rc()])
        del self.fake._commands[:]
        landed = self.invoke(LAND, {"landing_speed": 20})
        self.assertEqual(landed["status"], "completed", landed)
        self.assertEqual(landed["output"], {"is_flying": False, "landing_speed": 20, "applied": True})
        self.assertEqual(self.commands(), [rc(up_down=-20), rc()])
        self.assertEqual(self.state()["is_flying"], False)

    def test_a_move_uses_the_current_speed_and_the_right_axis(self) -> None:
        self.serve()
        self.assertEqual(self.takeoff()["status"], "completed")
        self.assertEqual(self.client.write("main", {"speed": 100}, **self.ids)["status"], "completed")
        del self.fake._commands[:]
        receipt = self.move("right", 12)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"direction": "right", "distance": 12, "is_flying": True,
                                             "applied": True})
        self.assertEqual(self.commands(), [rc(left_right=100), rc()])
        self.assertEqual(self.state()["speed"], 100.0)

    def test_a_move_before_takeoff_reports_not_applied_and_sends_nothing(self) -> None:
        self.serve()
        for direction in ("forward", "backward", "right", "left", "up", "down"):
            receipt = self.move(direction)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertFalse(receipt["output"]["applied"])
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.invoke(ROTATE, {"angle": 90})["output"]["applied"], False)
        self.assertEqual(self.invoke(CAMERA, {"angle": 30})["output"]["applied"], False)
        self.assertEqual(self.commands(), [])

    def test_rotate_and_camera_keep_the_native_sign_and_camera_angle(self) -> None:
        self.serve()
        self.assertEqual(self.takeoff()["status"], "completed")
        del self.fake._commands[:]
        self.assertEqual(self.invoke(ROTATE, {"angle": -70})["status"], "completed")
        self.assertEqual(self.commands(), [rc(yaw=-15.0 / 70.0), rc()])
        del self.fake._commands[:]
        self.assertEqual(self.invoke(CAMERA, {"angle": 40})["status"], "completed")
        self.assertEqual(self.commands(), [rc(cameraangle=40), rc()])

    def test_stream_actions_change_the_readable_state(self) -> None:
        self.serve()
        on = self.invoke("x-cap.cvzone.stream_on.v1", {})
        self.assertEqual((on["status"], on["output"]), ("completed", {"stream_on": True}))
        self.assertEqual(self.state()["stream_on"], True)
        off = self.invoke("x-cap.cvzone.stream_off.v1", {})
        self.assertEqual((off["status"], off["output"]), ("completed", {"stream_on": False}))
        self.assertEqual(self.state()["stream_on"], False)

    # -- operator bounds --------------------------------------------------------------------------------------
    def test_numeric_inputs_wait_for_the_operator_overlay(self) -> None:
        self.serve(overlay=False)
        refused = self.takeoff()
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.commands(), [])
        write = self.client.write("main", {"speed": 100}, **self.ids)
        self.assertEqual((write["status"], write["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.serve(overlay=True)
        self.assertEqual(self.takeoff()["status"], "completed")
        inside = self.client.write("main", {"speed": 100}, **self.ids)
        self.assertEqual(inside["status"], "completed")
        outside = self.client.write("main", {"speed": 501}, **self.ids)
        self.assertEqual((outside["status"], outside["error"]["mhs_code"]), ("rejected", ENVELOPE))

    def test_the_example_overlay_is_only_a_site_choice(self) -> None:
        self.serve()
        for payload in ({"takeoff_height": 9, "takeoff_speed": 50},
                        {"takeoff_height": 100, "takeoff_speed": 201}):
            refused = self.invoke(TAKEOFF, payload)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, payload)
        self.assertEqual(self.commands(), [])

    # -- e-stop and reset -------------------------------------------------------------------------------------
    def test_a_suppressed_publish_error_cannot_confirm_the_estop(self) -> None:
        self.serve()
        self.assertEqual(self.takeoff()["status"], "completed")
        # The upstream send_rc_control catches socket errors and returns None (drone.py:93-94).
        # This reproduces that boundary without a ZeroMQ socket or upstream import.
        self.fake.send_rc_control = lambda *args, **kwargs: None
        stopped = self.client.estop("unacknowledged publish", **self.ids)
        self.assertEqual((stopped["status"], stopped.get("error", {}).get("mhs_code")),
                         ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"), stopped)
        refused = self.move("forward", 5)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_estop_attempts_zero_but_stays_unconfirmed_and_latched(self) -> None:
        self.serve()
        self.assertEqual(self.takeoff()["status"], "completed")
        del self.fake._commands[:]
        receipt = self.client.estop("test", **self.ids)
        self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]),
                         ("failed", "MHS.SAFETY.SAFE_STATE_UNREACHED"), receipt)
        self.assertGreaterEqual(len(self.commands()), 1)
        self.assertTrue(all(command == rc() for command in self.commands()))
        self.assertTrue(self.fake.is_flying)            # the stop does not land; land() is a separate normal action
        before = len(self.commands())
        refused = self.invoke(MOVE, {"direction": "forward", "distance": 5})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(len(self.commands()), before)

    def test_reset_releases_only_the_latch_and_does_not_confirm_or_resume_motion(self) -> None:
        self.serve()
        self.assertEqual(self.takeoff()["status"], "completed")
        self.assertEqual(self.client.estop("test", **self.ids)["status"], "failed")
        del self.fake._commands[:]
        receipt = self.client.reset(**self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["resumed"])
        self.assertEqual(self.commands(), [])
        self.assertEqual(self.move("forward", 5)["status"], "completed")
        self.assertEqual(self.commands(), [rc(forward_backward=300), rc()])

    # -- the fake ---------------------------------------------------------------------------------------------
    def test_the_fake_preserves_the_upstream_signatures(self) -> None:
        import inspect

        self.serve()
        fake = self.fake
        self.assertEqual(str(inspect.signature(fake.send_rc_control)),
                         "(left_right, forward_backward, up_down, yaw, camera_angle=0, streamon=None, red=None, "
                         "green=None, blue=None)")
        self.assertEqual(str(inspect.signature(fake.take_off)), "(takeoff_height=200, takeoff_speed=200)")
        self.assertEqual(str(inspect.signature(fake.land)), "(landing_speed=100)")
        self.assertEqual(str(inspect.signature(fake.rotate)), "(angle)")
        self.assertEqual(str(inspect.signature(fake.rotate_camera)), "(angle)")
        self.assertEqual(str(inspect.signature(fake.set_speed)), "(speed)")
        self.assertEqual(str(inspect.signature(fake.set_rotation_speed)), "(rotation_speed)")


if __name__ == "__main__":
    unittest.main()
