"""Acceptance run of the PF400 driver: the gate, plus the status-port halt cases.

Add cases, never remove the check_driver call. The fake controller is in-process. Hosts, durations and any
trajectory value other than the GPL labels are test data. Nothing here opens a socket.
"""

import importlib.util
import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
MOVE = "x-cap.ad-sdl.move_joints.v1"
HALT = "x-cap.ad-sdl.halt.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
MOVE_INPUT = {"profile": 1, "joints": [0.0], "speed": 1}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PF400Cases(unittest.TestCase):
    def serve(self, site_limits=SITE_LIMITS):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.driver = driver
        return client, driver.native

    def move(self, client, payload=None):
        return client.invoke(MOVE, dict(MOVE_INPUT if payload is None else payload), **self.ids)

    def test_move_sends_mspeed_then_movej_and_does_not_report_reached(self) -> None:
        client, fake = self.serve()
        receipt = self.move(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {
            "reply": "0", "accepted": True, "profile": 1, "joints": [0.0], "speed": 1.0})
        self.assertNotIn("reached", receipt["output"])
        # The server reads traj_state around the command. The move itself is mspeed, then MoveJ.
        robot = [item["command"] for item in fake.exchanges
                 if item["port"] == 10100 and item["command"] != "state"]
        self.assertEqual(robot, ["mspeed 1", "MoveJ 1 0"])

    def test_unapproved_values_and_a_missing_overlay_send_nothing(self) -> None:
        client, fake = self.serve()
        for payload in (
            {"profile": 2, "joints": [0.0], "speed": 1},
            {"profile": 0, "joints": [0.0], "speed": 1},
            {"profile": 1, "joints": [5.0], "speed": 1},
            {"profile": 1, "joints": [0.0], "speed": 2},
        ):
            refused = self.move(client, payload)
            self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", refused)
        self.assertFalse(any(item["command"] != "state" for item in fake.exchanges), fake.exchanges)
        client, fake = self.serve(site_limits=None)
        refused = self.move(client)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", refused)
        self.assertFalse(any(item["command"] != "state" for item in fake.exchanges), fake.exchanges)

    def test_idle_state_is_one_and_estop_still_halts_on_the_status_port(self) -> None:
        client, fake = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["traj_state"], 1)
        stopped = client.estop("idle arm", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertEqual(len(halts), 2, fake.exchanges)
        self.assertTrue(all(item["port"] == 10000 and item["robot"] == 1 for item in halts), fake.exchanges)
        self.assertEqual(fake.traj[1], 0)
        selects = [item for item in fake.exchanges if item["command"] == "selectRobot 1"]
        self.assertEqual(len(selects), 2)
        self.assertTrue(all(item["robot"] == 0 and item["port"] == 10000 for item in selects))
        refused = self.move(client)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)
        self.assertFalse(any(item["command"].startswith("MoveJ") for item in fake.exchanges))

    def test_status_commands_are_separate_receives(self) -> None:
        client, fake = self.serve()
        halted = client.invoke(HALT, {}, **self.ids)
        self.assertEqual(halted["status"], "completed", halted)
        self.assertEqual(halted["output"]["traj_state"], 0)
        status = [(item["command"], item["robot"]) for item in fake.exchanges if item["port"] == 10000]
        self.assertEqual(status, [("selectRobot 1", 0), ("halt", 1), ("state", 1)])

    def test_a_negative_select_does_not_halt_and_the_stop_fails(self) -> None:
        client, fake = self.serve()
        fake._select_reply = "-1001"
        stopped = client.estop("undefined robot", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(any(item["command"] == "halt" for item in fake.exchanges))

    def test_trajstate_2_or_15_is_not_halted(self) -> None:
        for stuck in (2, 15):
            client, fake = self.serve()
            # A fresh session per value: a failed stop latches, and a later stop on that session is a new attempt.
            # The budget is the driver's own option, shortened so the test does not wait the default four seconds.
            self.driver._stop_confirm_s = 0.25
            fake.traj[1] = stuck
            fake._stuck = True
            stopped = client.estop(f"stuck {stuck}", deadline_ms=30000, **self.ids)
            self.assertEqual(stopped["status"], "failed", stopped)
            self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
            self.assertEqual(fake.traj[1], stuck)

    def test_an_unreachable_status_port_does_not_complete_the_stop(self) -> None:
        client, fake = self.serve()
        fake._status_down = True
        stopped = client.estop("status down", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(any(item["port"] == 10000 for item in fake.exchanges), fake.exchanges)

    def test_a_negative_mspeed_does_not_send_movej(self) -> None:
        client, fake = self.serve()
        fake._mspeed_reply = "-2803"
        receipt = self.move(client)
        self.assertEqual(receipt["status"], "failed", receipt)
        sent = [item["command"] for item in fake.exchanges if item["command"] != "state"]
        self.assertEqual(sent, ["mspeed 1"])

    def test_move_waits_for_the_stop_lock_before_movej(self) -> None:
        client, fake = self.serve()
        reached = threading.Event()

        def before():
            reached.set()

        self.driver._before_send = before
        receipts = []
        worker = threading.Thread(target=lambda: receipts.append(self.move(client)), daemon=True)
        move = ("MoveJ 1 0",)
        with self.driver._stop_lock():
            worker.start()
            self.assertTrue(reached.wait(10))
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                if any(item["command"] == "MoveJ 1 0" for item in fake.exchanges):
                    break
                time.sleep(0.01)
            sent_while_held = any(item["command"] == "MoveJ 1 0" for item in fake.exchanges)
        worker.join(15)
        self.assertFalse(sent_while_held, fake.exchanges)
        self.assertEqual(receipts[0]["status"], "completed", receipts)
        self.assertTrue(any(item["command"] == "MoveJ 1 0" for item in fake.exchanges))
        del move

    def test_cancel_under_the_lock_sends_no_movej(self) -> None:
        client, fake = self.serve()
        box = []

        def before():
            worker = threading.Thread(
                target=lambda: box.append(client.estop("during the pre-send hook", deadline_ms=30000, **self.ids)),
                daemon=True)
            worker.start()
            worker.join(15)
            box.append(worker.is_alive())

        self.driver._before_send = before
        receipt = self.move(client)
        self.assertFalse(box[1], "the e-stop did not finish while the move was outside the stop lock")
        self.assertEqual(box[0]["status"], "completed", box)
        self.assertEqual(receipt["status"], "cancelled", receipt)
        self.assertFalse(any(item["command"].startswith("MoveJ") for item in fake.exchanges), fake.exchanges)

    def test_estop_during_a_deferred_move_does_not_report_the_safe_state(self) -> None:
        # MoveJ bytes are written, then left unhandled until after estop returns. halt is RapidDecel and
        # does not retire that line, so TrajState can still be 0 when the command later starts.
        client, fake = self.serve()
        fake._defer_move = True
        receipts = []
        worker = threading.Thread(target=lambda: receipts.append(self.move(client, MOVE_INPUT)), daemon=True)
        worker.start()
        self.assertTrue(fake._move_waiting.wait(10), fake.exchanges)
        stopped = client.estop("MoveJ not yet handled", deadline_ms=30000, **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertEqual(fake.traj[1], 0, fake.exchanges)
        halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertTrue(halts, fake.exchanges)
        self.assertTrue(all(item["port"] == 10000 and item["robot"] == 1 for item in halts), fake.exchanges)
        fake._release_move.set()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(receipts[0]["status"], "unknown", receipts)
        self.assertEqual(fake.traj[1], 2)
        # The reply is the retirement (sent after the mailbox wait). A later halt and a fresh state read confirm.
        move_at = next(i for i, item in enumerate(fake.exchanges) if str(item["command"]).startswith("MoveJ"))
        confirmed = client.estop("MoveJ reply has arrived", deadline_ms=30000, **self.ids)
        self.assertEqual(confirmed["status"], "completed", confirmed)
        self.assertEqual(fake.traj[1], 0)
        later = [item for item in fake.exchanges[move_at + 1:] if item["command"] == "halt"]
        self.assertTrue(later, fake.exchanges)
        self.assertTrue(all(item["port"] == 10000 and item["robot"] == 1 for item in later), fake.exchanges)

    def test_cancel_during_mspeed_sends_no_movej(self) -> None:
        client, fake = self.serve()
        fake._block_mspeed = True
        receipts = []
        worker = threading.Thread(target=lambda: receipts.append(self.move(client)), daemon=True)
        worker.start()
        self.assertTrue(fake._mspeed_waiting.wait(10), fake.exchanges)
        stopped = client.estop("during mspeed", deadline_ms=30000, **self.ids)
        fake._mspeed_event.set()
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertNotEqual(receipts[0]["status"], "completed", receipts)
        self.assertFalse(any(item["command"].startswith("MoveJ") for item in fake.exchanges), fake.exchanges)

    def test_a_trickled_reply_stays_inside_the_stop_budget(self) -> None:
        client, fake = self.serve()
        self.driver._stop_confirm_s = 0.35
        fake._fragment = True
        fake._recv_pause_s = 0.2
        started = time.monotonic()
        stopped = client.estop("trickled reply", deadline_ms=30000, **self.ids)
        elapsed = time.monotonic() - started
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertLess(elapsed, 0.9, elapsed)

    def test_a_slow_connect_fails_inside_the_stop_budget(self) -> None:
        client, fake = self.serve()
        self.driver._stop_confirm_s = 0.2
        fake._connect_pause_s = 1.0
        started = time.monotonic()
        stopped = client.estop("slow connect", deadline_ms=30000, **self.ids)
        elapsed = time.monotonic() - started
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertLess(elapsed, 0.7, elapsed)
        self.assertFalse(any(item["port"] == 10000 for item in fake.exchanges), fake.exchanges)

    def test_halt_dispatches_while_a_robot_connect_is_blocked(self) -> None:
        client, fake = self.serve()
        fake._connect_pause_s = 1.0
        fake._connect_pause_ports = {10100}
        self.driver._stop_confirm_s = 0.35
        reads = []

        def read_state():
            try:
                reads.append(client.read("main", **self.ids))
            except Exception as exc:  # the assertion is the halt, not this read
                reads.append(exc)

        worker = threading.Thread(target=read_state, daemon=True)
        worker.start()
        self.assertTrue(fake._connect_entered.wait(10))
        started = time.monotonic()
        stopped = client.estop("robot connect blocked", deadline_ms=30000, **self.ids)
        elapsed = time.monotonic() - started
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertLess(elapsed, 0.8, elapsed)
        halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertTrue(halts, fake.exchanges)
        self.assertTrue(all(item["port"] == 10000 and item["robot"] == 1 for item in halts), fake.exchanges)
        worker.join(5)
        self.assertFalse(worker.is_alive())

    def test_a_timeout_between_cancel_check_and_publish_closes_the_socket(self) -> None:
        # The worker has passed the first cancel check and has a socket. The caller times out before publication.
        client, fake = self.serve()
        release = threading.Event()
        entered = threading.Event()
        self.addCleanup(release.set)

        def hold():
            entered.set()
            if not release.wait(5):
                raise TimeoutError("the handoff seam was not released")

        self.driver._before_socket_handoff = hold
        try:
            self.driver._connect(10000, time.monotonic() + 0.15)
        except TimeoutError:
            timed_out = True
        else:
            timed_out = False
        self.assertTrue(timed_out)
        self.assertTrue(entered.is_set())
        self.assertIn(10000, fake._clients)
        self.assertFalse(any(item["command"] == "halt" for item in fake.exchanges), fake.exchanges)
        release.set()
        deadline = time.monotonic() + 2
        while fake._clients and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(fake._clients, dict(fake._clients))
        del self.driver._before_socket_handoff
        stopped = client.estop("after the unpublished socket was closed", deadline_ms=30000, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertTrue(halts and all(item["port"] == 10000 and item["robot"] == 1 for item in halts),
                        fake.exchanges)

    def test_a_timed_out_connect_closes_before_the_next_halt(self) -> None:
        client, fake = self.serve()
        fake._connect_pause_s = 0.4
        fake._connect_pause_ports = {10000}
        self.driver._stop_confirm_s = 0.15
        failed = client.estop("status connect will expire", deadline_ms=30000, **self.ids)
        self.assertEqual(failed["status"], "failed", failed)
        self.assertEqual(failed["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", failed)
        self.assertFalse(any(item["port"] == 10000 for item in fake.exchanges), fake.exchanges)
        deadline = time.monotonic() + 2
        while fake._connects_finished < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertGreaterEqual(fake._connects_finished, 2, fake._connects_finished)
        self.assertFalse(fake._clients, dict(fake._clients))
        fake._connect_pause_s = 0
        stopped = client.estop("after the expired connect closed", deadline_ms=30000, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertTrue(halts and all(item["port"] == 10000 and item["robot"] == 1 for item in halts),
                        fake.exchanges)

    def test_hardware_factory_accepts_stop_confirm_s_without_opening_a_socket(self) -> None:
        spec = importlib.util.spec_from_file_location("pf400_native_under_test", HERE / "native.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        robot = module.connect(host="operator-supplied.invalid", stop_confirm_s=0.25)
        self.assertEqual(robot.host, "operator-supplied.invalid")
        self.assertEqual(robot.port, 10100)
        self.assertEqual(robot._connect_timeout_s, 1.0)
        for bad in ({"stop_confirm_s": 60}, {"stop_confirm_s": True}, {"connect_timeout_s": 60},
                    {"read_timeout_s": 60}):
            with self.assertRaises(ValueError):
                module.connect(host="operator-supplied.invalid", **bad)

    def test_one_buffer_runs_halt_on_the_previously_selected_robot(self) -> None:
        spec = importlib.util.spec_from_file_location("pf400_fake_under_test", HERE / "fake.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        fake = module.FakePF400()
        fake.port = 10000
        same = fake.connect_robot()
        same.sendall(b"selectRobot 1\nhalt\n")
        same.recv(4096)
        same.recv(4096)
        same_halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertEqual(same_halts[0]["robot"], 0)
        fake.disconnect_robot(same)
        fake.exchanges.clear()
        split = fake.connect_robot()
        split.sendall(b"selectRobot 1\n")
        split.recv(4096)
        split.sendall(b"halt\n")
        split.recv(4096)
        split_halts = [item for item in fake.exchanges if item["command"] == "halt"]
        self.assertEqual(split_halts[0]["robot"], 1)
        self.assertEqual(fake.traj[1], 0)


if __name__ == "__main__":
    unittest.main()
