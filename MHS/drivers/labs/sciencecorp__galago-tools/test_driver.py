"""Acceptance run of the galago-tools OT-2 driver: the gate, plus repository-specific cases.

Add cases, never remove the check_driver call.  The fake robot server is a dictionary of runs; ids, the protocol path
and every status word other than succeeded, stopped, failed and blocked-by-open-door (driver.py:227-231) are test data.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
RUN = "x-cap.sciencecorp.ot2_run_protocol.v1"
STOP = "x-cap.sciencecorp.ot2_stop_run.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
PROTOCOL = "/srv/ot2/approved/tip-check.py"        # the example overlay's approved file


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class GalagoOt2Cases(unittest.TestCase):
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

    def run_protocol(self, client):
        return client.invoke(RUN, {"protocol": PROTOCOL}, **self.ids)

    def test_run_uploads_creates_and_plays(self) -> None:
        client, fake = self.serve()
        fake._run_reads = 10 ** 6                # the protocol runs for the whole test
        receipt = self.run_protocol(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"run_id": "run-1", "protocol": PROTOCOL, "status": "running"})
        self.assertEqual([r for r in fake._requests if r[0] == "POST"],
                         [("POST", "/protocols"), ("POST", "/runs"), ("POST", "/runs/run-1/actions play")])
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["run_id"], "run-1")
        self.assertEqual(state["run_status"], "running")

    def test_unapproved_protocol_is_refused_and_no_overlay_refuses_all(self) -> None:
        client, fake = self.serve()
        refused = client.invoke(RUN, {"protocol": "/tmp/other.py"}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        client, fake = self.serve(site_limits=None)
        refused = self.run_protocol(client)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertEqual(fake._requests, [])

    def test_estop_stops_the_run_and_confirms_the_status_without_deleting_it(self) -> None:
        client, fake = self.serve()
        fake._run_reads = 10 ** 6
        self.run_protocol(client)
        fake._stop_settles_after = 3            # three reads report stop-requested before stopped
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertEqual(fake._runs["run-1"], "stopped")
        self.assertIn(("POST", "/runs/run-1/actions stop"), fake._requests)
        self.assertNotIn(("DELETE", "/runs/run-1"), fake._requests)
        self.assertEqual(fake._requests.count(("POST", "/runs/run-1/actions stop")), 1)   # the safe-state action
        refused = self.run_protocol(client)                                               # re-reads, sends nothing
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_estop_fails_when_the_run_never_reports_stopped(self) -> None:
        client, fake = self.serve()
        fake._run_reads = 10 ** 6
        self.run_protocol(client)
        fake._stop_settles_after = 10 ** 6      # stop-requested for longer than STOP_CONFIRM_S
        stopped = client.estop("never stops", deadline_ms=30000, **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_a_finished_run_needs_no_stop(self) -> None:
        client, fake = self.serve()
        self.run_protocol(client)            # the fake's run succeeds after one "running" read
        self.assertEqual(client.read("main", **self.ids)["state"]["run_status"], "succeeded")
        stopped = client.estop("after the run ended", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertNotIn(("POST", "/runs/run-1/actions stop"), fake._requests)

    def test_without_a_run_the_stop_reads_the_robot_server(self) -> None:
        client, fake = self.serve()
        stopped = client.estop("no run", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIn(("GET", "/health"), fake._requests)

    def test_a_second_run_waits_for_the_first(self) -> None:
        client, fake = self.serve()
        fake._run_reads = 10 ** 6
        self.run_protocol(client)
        busy = self.run_protocol(client)
        self.assertEqual(busy["status"], "rejected", busy)
        self.assertEqual(busy["error"]["mhs_code"], "MHS.DEVICE.BUSY")
        self.assertEqual(client.invoke(STOP, {}, **self.ids)["output"], {"run_id": "run-1", "status": "stopped"})
        self.assertEqual(self.run_protocol(client)["output"]["run_id"], "run-2")

    def test_a_failed_play_is_an_unknown_outcome(self) -> None:
        client, fake = self.serve()

        def refused(run_id):
            fake._requests.append(("POST", f"/runs/{run_id}/actions play"))
            raise ConnectionError("placeholder: connection reset")

        fake.start_run = refused
        receipt = self.run_protocol(client)
        self.assertEqual(receipt["status"], "unknown", receipt)

    def test_an_estop_during_upload_leaves_the_run_unplayed_and_stopped(self) -> None:
        client, fake = self.serve()
        original = fake.upload_and_schedule_protocol
        stops = []

        def upload(protocol_file):
            run_id = original(protocol_file)
            worker = threading.Thread(target=lambda: stops.append(client.estop("during upload", **self.ids)))
            worker.start()
            worker.join(15)
            return run_id

        fake.upload_and_schedule_protocol = upload
        receipt = self.run_protocol(client)
        self.assertEqual(receipt["status"], "cancelled", receipt)
        self.assertEqual(stops[0]["status"], "completed", stops)
        self.assertNotIn(("POST", "/runs/run-1/actions play"), fake._requests)
        self.assertEqual(fake._runs["run-1"], "stopped")

    def test_closing_the_driver_cancels_and_deletes_the_run_as_upstream(self) -> None:
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=SITE_LIMITS)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        fake = driver.native
        fake._run_reads = 10 ** 6
        client.invoke(RUN, {"protocol": PROTOCOL}, device_id=device_id, session_id=session)
        close_server(server)
        self.assertIn(("POST", "/runs/run-1/actions stop"), fake._requests)
        self.assertIn(("DELETE", "/runs/run-1"), fake._requests)
        self.assertIsNone(fake.run_id)

    # -- review round 1 (Sonnet safety finding F3) -------------------------------------------------------------------
    def test_play_waits_while_a_stop_holds_the_stop_lock(self) -> None:
        # play is sent only under the stop lock: while a stop holds it (here the test does), the run is uploaded and
        # created but not played; it is played once the lock is released.
        client, fake = self.serve()
        fake._run_reads = 10 ** 6
        original = fake.upload_and_schedule_protocol
        uploaded = threading.Event()
        receipts = []

        def upload(protocol_file):
            run_id = original(protocol_file)
            uploaded.set()
            return run_id

        fake.upload_and_schedule_protocol = upload
        play = ("POST", "/runs/run-1/actions play")
        with self.driver._stop_lock():
            worker = threading.Thread(target=lambda: receipts.append(self.run_protocol(client)))
            worker.start()
            self.assertTrue(uploaded.wait(10))
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline and play not in fake._requests:
                time.sleep(0.01)
            played_while_held = play in fake._requests
        worker.join(15)
        self.assertFalse(played_while_held, fake._requests)
        self.assertEqual(receipts[0]["status"], "completed", receipts)
        self.assertIn(play, fake._requests)

if __name__ == "__main__":
    unittest.main()
