"""Acceptance run of the CrazyFlie package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_calls`` list is
what reached the "drone".  Nothing here ran on a real drone or on the upstream simulator.
"""

import json
import tempfile
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
POSITION = "x-cap.jjshoots.position_setpoint.v1"
VELOCITY = "x-cap.jjshoots.velocity_setpoint.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CrazyflieCases(unittest.TestCase):
    def serve(self, site_limits=None):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.fake = driver.native                              # the fake DroneController
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.fake._calls[:]                                # forget the connection set-up
        return self.client

    def position(self, x=0.0, y=0.0, z=0.5, yaw=0.0):
        return self.client.invoke(POSITION, {"x": x, "y": y, "z": z, "yaw": yaw}, **self.ids)

    def velocity(self, vx=0.1, vy=0.0, vz=0.0, yaw_rate=0.0):
        return self.client.invoke(VELOCITY, {"vx": vx, "vy": vy, "vz": vz, "yaw_rate": yaw_rate}, **self.ids)

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def called(self, name):
        return self.fake._called(name)

    # -- limits ------------------------------------------------------------------------------------------------
    def test_a_setpoint_waits_for_the_site(self) -> None:
        self.serve()
        for receipt in (self.position(), self.velocity()):
            self.assertEqual((receipt["status"], receipt["error"]["mhs_code"]), ("rejected", LIMITS_UNSET))
        self.assertEqual(self.fake._calls, [])

    def test_the_example_overlay_only_narrows(self) -> None:
        self.serve(OVERLAY)
        outside = self.position(x=0.6)                          # the example allows -0.5 .. 0.5
        self.assertEqual((outside["status"], outside["error"]["mhs_code"]), ("rejected", ENVELOPE))
        self.assertEqual(outside["error"]["details"]["bound"], 0.5)
        self.assertEqual(self.fake._calls, [])
        self.assertEqual(self.position(x=0.5)["status"], "completed")     # the boundary is inside
        self.assertEqual(self.velocity(vx=0.6)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.velocity(vx=-0.6)["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.velocity(vx=0.5)["status"], "completed")

    # -- the native calls --------------------------------------------------------------------------------------
    def test_a_position_setpoint_is_stored_then_the_controller_starts(self) -> None:
        self.serve(OVERLAY)
        receipt = self.position(x=0.1, y=-0.2, z=0.5, yaw=0.3)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["setpoint"], {"x": 0.1, "y": -0.2, "z": 0.5, "yaw": 0.3})
        self.assertEqual(receipt["output"]["running"], True)
        self.assertEqual([name for name, _ in self.fake._calls],
                         ["stop", "set_pos_control", "set_setpoint", "start"])
        self.assertEqual(self.called("set_setpoint"), [([0.1, -0.2, 0.5, 0.3],)])
        self.assertEqual(self.called("set_pos_control"), [(True,)])
        state = self.state()
        self.assertEqual((state["running"], state["pos_control"]), (True, True))
        self.assertEqual(state["setpoint"], [0.1, -0.2, 0.5, 0.3])

    def test_a_velocity_setpoint_selects_velocity_control(self) -> None:
        self.serve(OVERLAY)
        receipt = self.velocity(vx=0.2, vy=-0.1, vz=0.0, yaw_rate=0.4)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["setpoint"],
                         {"vx": 0.2, "vy": -0.1, "vz": 0.0, "yaw_rate": 0.4})
        self.assertEqual([name for name, _ in self.fake._calls],
                         ["stop", "set_pos_control", "set_setpoint", "start"])
        self.assertEqual(self.called("set_pos_control"), [(False,)])
        self.assertEqual(self.state()["setpoint"], [0.2, -0.1, 0.0, 0.4])
        self.assertEqual(self.state()["pos_control"], False)

    def test_the_position_control_flag_is_a_writable_state(self) -> None:
        self.serve()
        receipt = self.client.write("main", {"pos_control": True}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(self.called("set_pos_control"), [(True,)])
        self.assertEqual(self.state()["pos_control"], True)

    # -- reads -------------------------------------------------------------------------------------------------
    def test_the_logged_state_and_the_setpoint_are_read_back(self) -> None:
        self.serve()
        self.fake._move_position_estimate(0.1, -0.2, 0.3, 0.4)
        state = self.state()
        self.assertEqual(state["position_estimate"], {"x": 0.1, "y": -0.2, "z": 0.3, "yaw": 0.4})
        self.assertEqual(state["setpoint"], [0.0, 0.0, 0.0, 0.0])
        self.assertEqual((state["running"], state["pos_control"]), (False, False))

    # -- e-stop and safe state ---------------------------------------------------------------------------------
    def test_the_estop_stops_the_controller_and_latches(self) -> None:
        self.serve(OVERLAY)
        self.client.estop("test", **self.ids)
        self.assertGreaterEqual(len(self.called("stop")), 1)
        self.assertEqual(self.fake.running, False)
        before = len(self.fake._calls)
        refused = self.position()
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(len(self.fake._calls), before)         # the latched refusal reached nothing

    def test_the_reference_declares_the_software_stop_path(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        safety = reference["safety"]
        self.assertEqual(safety["estop"]["native"], "stop")
        self.assertNotIn("physical_ref", safety["estop"])
        self.assertIn("x-cap.jjshoots.halt.v1", safety["safe_state"]["achieved_by"])
        self.assertTrue(any("send_stop_setpoint" in fact["text"] for fact in reference["facts"]))
        unset = sorted((item["name"], item["path"]) for item in safety["operator_required"])
        self.assertIn(("set_position_setpoint", "x"), unset)
        self.assertIn(("set_velocity_setpoint", "yaw_rate"), unset)

    # -- the loader --------------------------------------------------------------------------------------------
    def test_the_hardware_backend_is_refused_until_a_human_signs_the_review(self) -> None:
        with tempfile.TemporaryDirectory() as state_dir:
            with self.assertRaises(LoadError) as caught:
                load_driver(HERE, backend="hardware", allow_hardware=True, state_dir=state_dir)
        self.assertEqual(caught.exception.reason, "review_required")


if __name__ == "__main__":
    unittest.main()
