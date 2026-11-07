"""Acceptance run of the Franka Hand package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py): its ``_calls`` list is what
reached the "hand".  Nothing here ran on a real Franka Hand or on the upstream physics engine.
"""

import json
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FrankaHandCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.hand = driver.native                              # the fake FrankaHandPhysics
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.hand._calls[:]                                # forget any set-up
        return self.client

    def state(self):
        return self.client.read("main", **self.ids)["state"]

    def sent(self, name=None):
        return [(command, args) for command, args in self.hand._calls if name is None or command == name]

    def invoke(self, capability_id, payload=None):
        return self.client.invoke(capability_id, payload or {}, **self.ids)

    # -- reads -----------------------------------------------------------------------------------------------
    def test_the_fake_state_is_fully_open_with_the_stub_temperature(self) -> None:
        self.serve()
        state = self.state()
        self.assertEqual((state["width_mm"], state["max_width_mm"]), (80.0, 80.0))
        self.assertEqual((state["is_grasped"], state["is_stuck"]), (False, False))
        self.assertEqual(state["temperature_c"], 30)

    # -- the catalogue capabilities ---------------------------------------------------------------------------
    def test_a_grasp_inside_the_epsilon_band_succeeds_and_reports_the_width(self) -> None:
        self.serve()
        self.hand.object_width = 0.04                          # placeholder: a 4 cm test object
        receipt = self.invoke("cap.manipulation.grasp.v1", {"width": 40})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"grasped": True, "width_mm": 40.0})
        self.assertEqual(self.state()["width_mm"], 40.0)
        self.assertTrue(self.state()["is_grasped"])
        [(name, args)] = self.sent("grasp")
        self.assertEqual((args["width"], args["epsilon_inner"], args["epsilon_outer"], args["speed"], args["force"]),
                         (0.04, 0.005, 0.005, 0.0, 0.0))

    def test_a_grasp_outside_the_band_completes_with_grasped_false(self) -> None:
        self.serve()
        self.hand.object_width = 0.04                          # placeholder: the same 4 cm object
        receipt = self.invoke("cap.manipulation.grasp.v1", {"width": 30})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"grasped": False, "width_mm": 40.0})
        self.assertFalse(self.state()["is_grasped"])

    def test_a_release_opens_the_fingers_to_the_requested_width(self) -> None:
        self.serve()
        self.invoke("cap.manipulation.grasp.v1", {"width": 40})  # placeholder: no object, closes to 0
        receipt = self.invoke("cap.manipulation.release.v1", {"open_width": 20})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"released": True, "width_mm": 20.0})
        self.assertEqual(self.state()["width_mm"], 20.0)
        self.assertEqual(self.sent("move")[0][1]["width"], 0.02)

    def test_the_stroke_is_enforced_before_the_native_call(self) -> None:
        self.serve()
        for capability_id, payload in (
            ("cap.manipulation.grasp.v1", {"width": 81}),
            ("cap.manipulation.release.v1", {"open_width": -1}),
            ("x-cap.barisyazici.hand_move.v1", {"width": 81}),
        ):
            refused = self.invoke(capability_id, payload)
            self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ENVELOPE), capability_id)
        self.assertEqual(self.sent(), [])                      # the hand saw none of them

    # -- the extension capabilities ----------------------------------------------------------------------------
    def test_move_and_home_reach_the_hand_and_report_the_achieved_width(self) -> None:
        self.serve()
        moved = self.invoke("x-cap.barisyazici.hand_move.v1", {"width": 60})
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"], {"moved": True, "width_mm": 60.0})
        self.assertEqual(self.state()["width_mm"], 60.0)
        homed = self.invoke("x-cap.barisyazici.hand_home.v1")
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True, "width_mm": 80.0})
        self.assertEqual(self.state()["width_mm"], 80.0)

    def test_the_stop_action_is_the_declared_safe_state(self) -> None:
        self.serve()
        self.invoke("x-cap.barisyazici.hand_move.v1", {"width": 20})
        receipt = self.invoke("x-cap.barisyazici.hand_stop.v1")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"stopped": True, "width_mm": 80.0})
        self.assertEqual(self.state()["width_mm"], 80.0)

    # -- e-stop ------------------------------------------------------------------------------------------------
    def test_the_estop_reaches_the_native_stop_and_latches(self) -> None:
        self.serve()
        self.client.estop("test", **self.ids)
        self.assertGreaterEqual(len(self.sent("stop")), 1)     # @estop and the safe-state action both call stop()
        self.assertEqual(self.state()["width_mm"], 80.0)
        before = len(self.sent())
        refused = self.invoke("cap.manipulation.grasp.v1", {"width": 40})
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("rejected", ESTOP))
        self.assertEqual(len(self.sent()), before)             # the latched refusal reached the hand with nothing

    # -- the reference -----------------------------------------------------------------------------------------
    def test_the_reference_declares_the_stroke_and_the_safe_state_action(self) -> None:
        reference = json.loads((HERE / "reference.json").read_text(encoding="utf-8"))
        self.assertEqual(reference["safety"]["safe_state"]["achieved_by"], ["x-cap.barisyazici.hand_stop.v1"])
        self.assertEqual(reference["safety"]["estop"]["native"], "stop")
        limits = [(action["cap_id"], item["limit"]["max"], item["limit"]["ref"])
                  for action in reference["actions"] for item in action["inputs"] if "limit" in item]
        self.assertEqual(limits, [
            ("cap.manipulation.grasp.v1", 80, "docs/robot-state.md:202"),
            ("cap.manipulation.release.v1", 80, "docs/robot-state.md:202"),
            ("x-cap.barisyazici.hand_move.v1", 80, "docs/robot-state.md:202"),
        ])


if __name__ == "__main__":
    unittest.main()
