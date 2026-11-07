"""Acceptance run of the Runze syringe-pump package: the gate, plus cases specific to this driver.

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
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PUMP = "cap.actuation.pump.v1"
STOP = "x-cap.deepmodeling.stop_pump.v1"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RunzePumpCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def serve_native(self):
        """A served driver with the example overlay, returning the client and the fake native object."""
        driver = load_driver(HERE, backend="fake")
        overlay = json.loads((HERE / "site-limits.example.json").read_text())
        server = build_server(driver, site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    @staticmethod
    def wait_busy(fake):
        deadline = time.monotonic() + 5.0
        while not fake._busy and time.monotonic() < deadline:
            time.sleep(0.01)
        return fake._busy

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reads_start_from_the_fake_placeholders(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["position"], 12500.0)          # placeholder: half of the fake syringe
        self.assertEqual(state["plunger_position"], 12500.0)
        self.assertEqual(state["status"], "Idle")
        self.assertEqual(state["valve_position"], "I")        # placeholder
        self.assertEqual(state["velocity_grade"], "0")        # placeholder

    def test_numeric_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"position": 500.0}, {"max_velocity": 50.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["position"], 12500.0)   # placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, position=500.0)["status"], "completed")
        self.assertEqual(self.state(client)["position"], 500.0)
        self.assertEqual(self.configure(client, max_velocity=50.0)["status"], "completed")
        for patch in ({"position": 25001.0}, {"max_velocity": 101.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_pump_action_moves_the_plunger(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500,
                                       "duration_s": 10}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["dispensed_volume"], 500.0)
        self.assertGreaterEqual(receipt["output"]["duration_s"], 0.0)
        state = self.state(client)
        self.assertEqual(state["position"], 12000.0)
        self.assertEqual(state["max_velocity"], 50.0)
        reverse = client.invoke(PUMP, {"flow_rate": 40, "direction": "reverse", "volume": 400}, **self.ids)
        self.assertEqual(reverse["status"], "completed")
        self.assertEqual(reverse["output"]["dispensed_volume"], 400.0)
        self.assertEqual(self.state(client)["position"], 12400.0)

    def test_duration_alone_is_converted_to_a_volume(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "duration_s": 2}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"]["dispensed_volume"], 100.0)
        self.assertEqual(self.state(client)["position"], 12400.0)

    def test_the_safe_state_action_and_the_estop_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})
        client.estop("test", **self.ids)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    # -- cases added by the model review (r23) ------------------------------------------------------------------
    def test_an_estop_during_a_move_ends_it_part_way(self) -> None:
        client, fake = self.serve_native()
        fake.move_time_s = 2.0                                    # placeholder: a long modelled move
        start = fake._steps
        box = {}
        worker = threading.Thread(target=lambda: box.update(receipt=client.invoke(
            PUMP, {"flow_rate": 50, "direction": "forward", "volume": 5000}, **self.ids)))
        worker.start()
        self.assertTrue(self.wait_busy(fake))
        stopped = client.estop("test", **self.ids)
        worker.join(10)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(box["receipt"]["status"], "cancelled", box["receipt"])
        moved = start - fake._steps
        self.assertGreater(moved, 0)
        self.assertLess(moved, int(5.0 / fake.max_volume * fake.total_steps))

    def test_no_move_command_follows_an_estop_that_lands_before_the_move(self) -> None:
        # Nothing in the clone shows T holding a later command, so the driver must not send the move once the
        # e-stop started.
        client, fake = self.serve_native()
        action_thread, in_gap, resume, moves = [], threading.Event(), threading.Event(), []
        set_max_velocity, get_position = fake.set_max_velocity, fake.get_position

        def armed_set_max_velocity(velocity):
            action_thread.append(threading.current_thread())
            return set_max_velocity(velocity)

        def gated_get_position():
            if action_thread and threading.current_thread() is action_thread[0] and not in_gap.is_set():
                in_gap.set()
                resume.wait(5)
            return get_position()

        fake.set_max_velocity = armed_set_max_velocity
        fake.get_position = gated_get_position
        fake.push_plunger = lambda volume: moves.append(volume)
        box = {}
        worker = threading.Thread(target=lambda: box.update(receipt=client.invoke(
            PUMP, {"flow_rate": 50, "direction": "forward", "volume": 1000}, **self.ids)))
        worker.start()
        self.assertTrue(in_gap.wait(5))
        stopped = client.estop("test", **self.ids)
        resume.set()
        worker.join(10)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(box["receipt"]["status"], "cancelled", box["receipt"])
        self.assertEqual(moves, [])

    def test_a_position_write_ended_by_the_estop_is_cancelled_not_applied(self) -> None:
        client, fake = self.serve_native()
        fake.move_time_s = 2.0                                    # placeholder: a long modelled move
        box = {}
        worker = threading.Thread(target=lambda: box.update(receipt=self.configure(client, position=24000.0)))
        worker.start()
        self.assertTrue(self.wait_busy(fake))
        stopped = client.estop("test", **self.ids)
        worker.join(10)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(box["receipt"]["status"], "cancelled", box["receipt"])
        self.assertNotEqual(fake._position_ml() * 1000.0, 24000.0)

    def test_a_stop_sent_while_idle_does_not_hold_the_next_move(self) -> None:
        # Fake modelling (conservative): T ends only the move in progress; a move command sent after it runs.
        _client, fake = self.serve_native()
        start = fake._steps
        fake._query("T")
        fake.push_plunger(1.0)
        self.assertEqual(start - fake._steps, int(1.0 / fake.max_volume * fake.total_steps))

    def test_the_estop_is_unreached_while_the_pump_stays_busy(self) -> None:
        client, fake = self.serve_native()
        fake.get_status = lambda: "Busy"                          # a status reply other than the idle byte
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_velocity_reads_back_as_a_whole_pulse_frequency(self) -> None:
        client, fake = self.serve_native()
        self.assertEqual(self.configure(client, max_velocity=40.0)["status"], "completed")
        # int(0.04 / 25 * 6000) = 9 pulses/s, read back as 9 / 6000 * 25 mL/s (placeholder 25 mL syringe)
        self.assertEqual(self.state(client)["max_velocity"], 37.5)


if __name__ == "__main__":
    unittest.main()
