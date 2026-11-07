"""Acceptance run of the Opentrons OT-2 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
REENABLE = "x-cap.accelerationconsortium.reenable.v1"
HALT = "x-cap.accelerationconsortium.halt_motion.v1"
HOME = "x-cap.accelerationconsortium.home_all.v1"
MOVE_AXES = "x-cap.accelerationconsortium.move_axes.v1"
SMOOTHIE_READS = ("position", "firmware_version", "pipette_left_model", "pipette_left_id", "pipette_right_model",
                  "pipette_right_id")
HOMED = {"x": 418.0, "y": 353.0, "z": 218.0, "a": 218.0, "b": 19.0, "c": 19.0}   # the fake's placeholder


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class OpentronsOT2Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_fake(self):
        """Serve with the example overlay and return the client and the fake, so a case can set its knobs."""
        overlay = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def engaged(self, client):
        return client.safety_status(self.ids["device_id"])["estop"]["engaged"]

    def move(self, client, x=100.0, y=100.0, z=100.0):
        return client.invoke("cap.motion.cartesian_pose.v1",
                              {"position": {"x": x, "y": y, "z": z}}, **self.ids)

    def move_axes(self, client, x=100.0, y=100.0, z=100.0, a=100.0, b=0.0, c=0.0):
        return client.invoke(MOVE_AXES, {"x": x, "y": y, "z": z, "a": a, "b": b, "c": c}, **self.ids)

    def aspirate(self, client, axis="B", volume=100.0, per_mm=10.0, flow=100.0):
        return client.invoke("x-cap.accelerationconsortium.aspirate.v1",
                              {"axis": axis, "volume_ul": volume, "ul_per_mm": per_mm,
                               "flow_rate_ul_s": flow}, **self.ids)

    def dispense(self, client, axis="B", volume=100.0, per_mm=10.0, flow=100.0):
        return client.invoke("x-cap.accelerationconsortium.dispense.v1",
                              {"axis": axis, "volume_ul": volume, "ul_per_mm": per_mm,
                               "flow_rate_ul_s": flow}, **self.ids)

    def start_move(self, client, fake):
        """Start a six-axis move in a thread and wait until the fake holds its lock for it."""
        receipts = {}

        def run():
            receipts["move"] = self.move_axes(client)

        worker = threading.Thread(target=run, daemon=True)
        worker.start()
        deadline = time.monotonic() + 5.0
        while "move" not in fake._smoothie_log and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIn("move", fake._smoothie_log)
        return worker, receipts

    def test_reads_and_lights(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertTrue(state["simulating"])
        self.assertEqual(state["position"], {"x": 0.0, "y": 0.0, "z": 0.0, "a": 0.0, "b": 0.0, "c": 0.0})
        self.assertEqual((state["button_light"], state["rail_lights"]), (
            {"red": True, "green": True, "blue": True}, True))
        self.assertEqual((state["button_pressed"], state["door_closed"]), (False, True))
        self.assertEqual(state["firmware_version"], "fake-smoothie")
        self.assertEqual(state["serial_number"], "fake-ot2")
        self.assertEqual(state["pipette_left_model"], "p300_single_gen2")
        self.assertEqual(state["pipette_left_id"], "fake-left")
        self.assertEqual((state["pipette_right_model"], state["pipette_right_id"]), ("", ""))
        self.assertEqual(self.configure(client, button_light={"red": False, "green": True, "blue": False})["status"],
                         "completed")
        self.assertEqual(self.configure(client, rail_lights=False)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["button_light"], {"red": False, "green": True, "blue": False})
        self.assertFalse(state["rail_lights"])

    def test_the_move_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.move(client)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)

    def test_the_example_overlay_allows_and_bounds_the_cartesian_move(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move(client)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 100.0, "z": 100.0})
        for x, y, z in ((-0.5, 100.0, 100.0), (100.0, 300.5, 100.0), (100.0, 100.0, -50.5)):
            refused = self.move(client, x, y, z)
            self.assertEqual(refused["status"], "rejected", (x, y, z))
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, (x, y, z))

    def test_the_six_axis_move_uses_the_operator_envelope(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        moved = self.move_axes(client)
        self.assertEqual(moved["status"], "completed")
        self.assertEqual(moved["output"]["position"], {"x": 100.0, "y": 100.0, "z": 100.0, "a": 100.0, "b": 0.0,
                                                        "c": 0.0})
        refused = self.move_axes(client, b=50.5)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)

    def test_aspirate_and_dispense_book_the_plunger(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        drawn = self.aspirate(client, "B", 100.0, 10.0, 100.0)
        self.assertEqual(drawn["status"], "completed")
        self.assertEqual(drawn["output"]["aspirated_volume"], 100.0)
        self.assertEqual(self.state(client)["position"]["b"], 10.0)
        pushed = self.dispense(client, "B", 40.0, 10.0, 100.0)
        self.assertEqual(pushed["status"], "completed")
        self.assertEqual(pushed["output"]["dispensed_volume"], 40.0)
        self.assertEqual(self.state(client)["position"]["b"], 6.0)

    def test_home_and_halt_complete(self) -> None:
        client = self.serve()
        homed = client.invoke(HOME, {}, **self.ids)
        self.assertEqual(homed["status"], "completed")
        self.assertEqual(homed["output"], {"homed": True})
        self.assertEqual(self.state(client)["position"], HOMED)
        stopped = client.invoke(HALT, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})

    def test_the_estop_latches_and_only_the_reenable_reaches_the_smoothie_after_it(self) -> None:
        client, fake = self.serve_fake()
        self.assertEqual(self.move(client)["status"], "completed")
        halted_at = len(fake._smoothie_log)
        client.estop("test", **self.ids)
        self.assertEqual(fake._smoothie_log[-1], "stop")
        refused = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        reset = client.reset(**self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        state = self.state(client)
        for name in SMOOTHIE_READS:
            self.assertNotIn(name, state)
        self.assertEqual((state["serial_number"], state["door_closed"]), ("fake-ot2", True))
        for receipt in (self.move(client), self.move_axes(client), client.invoke(HOME, {}, **self.ids),
                        self.aspirate(client), self.dispense(client)):
            self.assertEqual(receipt["status"], "failed", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)
        self.assertEqual(set(fake._smoothie_log[halted_at:]), {"stop"})
        recovered = client.invoke(REENABLE, {}, **self.ids)
        self.assertEqual(recovered["status"], "completed", recovered)
        self.assertEqual(recovered["output"], {"reenabled": True, "homed": True})
        after = [entry for entry in fake._smoothie_log[halted_at:] if entry != "stop"]
        self.assertEqual(after[:2], ["reset_from_error", "home"])
        self.assertEqual(self.state(client)["position"], HOMED)
        moved = self.move(client)
        self.assertEqual(moved["status"], "completed", moved)

    def test_the_halt_action_also_requires_the_reenable(self) -> None:
        client, _fake = self.serve_fake()
        self.assertEqual(client.invoke(HALT, {}, **self.ids)["status"], "completed")
        refused = self.move(client)
        self.assertEqual((refused["status"], refused["error"]["mhs_code"]), ("failed", PRECONDITION))
        self.assertEqual(client.invoke(REENABLE, {}, **self.ids)["status"], "completed")
        self.assertEqual(self.move(client)["status"], "completed")

    def test_the_estop_halts_a_running_move_once_its_cancellation_frees_the_lock(self) -> None:
        client, fake = self.serve_fake()
        fake._move_s = 30.0
        worker, receipts = self.start_move(client, fake)
        started = time.monotonic()
        estop = client.estop("test", **self.ids)
        self.assertLess(time.monotonic() - started, 5.0)
        worker.join(10.0)
        self.assertEqual(estop["status"], "completed", estop)
        self.assertTrue(estop["output"]["safe_state_achieved"])
        self.assertTrue(self.engaged(client))
        self.assertEqual(receipts["move"]["status"], "cancelled")
        log = fake._smoothie_log
        self.assertLess(log.index("move:cancelled"), log.index("stop"))
        self.assertGreaterEqual(fake._stops, 1)

    def test_a_dependency_that_keeps_the_lock_leaves_the_estop_unreached_and_latched(self) -> None:
        client, fake = self.serve_fake()
        fake._move_s = 1.5
        fake._hold_lock_on_cancel = True
        worker, _receipts = self.start_move(client, fake)
        estop = client.estop("test", **self.ids)
        self.assertEqual(estop["status"], "failed", estop)
        self.assertEqual(estop["error"]["mhs_code"], UNREACHED)
        self.assertNotIn("stop", fake._smoothie_log)
        self.assertTrue(self.engaged(client))
        worker.join(10.0)
        deadline = time.monotonic() + 10.0
        while "stop" not in fake._smoothie_log and time.monotonic() < deadline:
            time.sleep(0.05)
        log = fake._smoothie_log
        self.assertLess(log.index("move:cancelled-late"), log.index("stop"))
        self.assertTrue(self.engaged(client))


if __name__ == "__main__":
    unittest.main()
