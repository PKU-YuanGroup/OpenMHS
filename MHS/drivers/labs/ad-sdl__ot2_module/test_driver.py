"""Acceptance run of the Opentrons OT-2 package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.  The cases run on the fake backend (fake.py), mostly with the example
overlay (site-limits.example.json), which allows one placeholder protocol path.  ``self.robot`` is the fake
OT2_Driver; its ``_refused_actions``, ``_ignored_actions`` and ``_offline`` switches stand for a robot that refuses a
run action, accepts one without applying it, or does not answer GET /runs.  Nothing here ran on an OT-2.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import load_driver
from mhs.driver import build_server, close_server
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
OVERLAY = str(HERE / "site-limits.example.json")
START = "x-cap.ad-sdl.start_protocol.v1"
STOP_RUNS = "x-cap.ad-sdl.stop_active_run.v1"
ALLOWED = json.loads((HERE / "site-limits.example.json").read_text())[
    "devices"]["mhs://localhost/ot2"][START]["protocol_path"]["allowed"][0]
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
FAULTED = "MHS.DEVICE.FAULTED"
UNKNOWN = "MHS.OUTCOME.UNKNOWN"
STOPPED = ("stop-requested", "stopped")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Ot2Cases(unittest.TestCase):
    def serve(self, site_limits=OVERLAY):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        self.driver = driver
        self.robot = driver.native  # the fake OT2_Driver
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def start(self, client, path=ALLOWED):
        return client.invoke(START, {"protocol_path": str(path)}, **self.ids)

    def status_of(self, run_id):
        return self.robot._runs[run_id]["status"]

    def add_foreign_run(self, status):
        """A run another client (the Opentrons App, say) created on the same robot."""
        run_id = "foreign-%d" % (len(self.robot._runs) + 1)  # placeholder: test identifier
        self.robot._runs[run_id] = {"id": run_id, "protocolId": "protocol-foreign", "status": status,
                                    "current": True, "commands": []}
        return run_id

    def test_a_started_protocol_is_visible_in_the_reads(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client)["robot_status"], "idle")
        receipt = self.start(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["status"], "running")
        state = self.state(client)
        self.assertEqual(state["active_run_id"], output["run_id"])
        self.assertEqual(state["active_run_status"], "running")
        self.assertEqual(state["robot_status"], "running")
        self.assertIn(output["run_id"], [run["runID"] for run in state["runs"]])
        self.assertEqual(self.robot._protocols[output["protocol_id"]], ALLOWED)

    def test_only_a_protocol_the_operator_allows_reaches_the_robot(self) -> None:
        client = self.serve(site_limits=None)
        refused = self.start(client)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.robot._runs, {})
        client = self.serve()
        refused = self.start(client, "/home/someone/other_protocol.py")
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        self.assertEqual(self.robot._runs, {})

    def test_the_estop_stops_the_run_confirms_it_and_latches(self) -> None:
        client = self.serve()
        receipt = self.start(client)
        self.assertEqual(receipt["status"], "completed", receipt)
        run_id = receipt["output"]["run_id"]
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIn(self.status_of(run_id), STOPPED)
        state = self.state(client)
        self.assertEqual(state["active_run_id"], run_id)
        self.assertIn(state["active_run_status"], STOPPED)
        refused = self.start(client)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(len(self.robot._runs), 1)

    def test_the_stop_reaches_a_run_started_elsewhere_besides_an_old_own_run(self) -> None:
        client = self.serve()
        own = self.start(client)["output"]["run_id"]
        self.robot._runs[own]["status"] = "succeeded"  # the own run ended on its own
        foreign = self.add_foreign_run("running")
        receipt = client.invoke(STOP_RUNS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["stopped_runs"], [{"run_id": foreign, "status": "stop-requested"}])
        self.assertEqual(self.status_of(own), "succeeded")
        self.assertIn(self.status_of(foreign), STOPPED)

    def test_paused_finishing_and_unnamed_statuses_are_stopped_idle_and_ended_runs_are_not(self) -> None:
        client = self.serve()
        moving = [self.add_foreign_run(status) for status in ("paused", "finishing", "awaiting-something")]
        resting = [self.add_foreign_run(status) for status in ("idle", "succeeded", "failed", "stopped")]
        receipt = client.invoke(STOP_RUNS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual([item["run_id"] for item in receipt["output"]["stopped_runs"]], moving)
        self.assertEqual([self.status_of(run_id) for run_id in resting], ["idle", "succeeded", "failed", "stopped"])

    def test_a_refused_stop_is_unreached_and_keeps_the_latch(self) -> None:
        client = self.serve()
        run_id = self.start(client)["output"]["run_id"]
        self.robot._refused_actions.add("stop")  # the robot answers 409 and the run keeps running
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        self.assertEqual(self.status_of(run_id), "running")
        refused = self.start(client)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        # Once the robot takes the stop, the runtime's background retry confirms it; the latch stays engaged.
        self.robot._refused_actions.clear()
        deadline = time.monotonic() + 10
        while self.status_of(run_id) not in STOPPED and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertIn(self.status_of(run_id), STOPPED)
        self.assertEqual(self.start(client)["error"]["mhs_code"], ESTOP)

    def test_a_stop_answered_201_without_a_state_change_is_unreached(self) -> None:
        client = self.serve()
        run_id = self.start(client)["output"]["run_id"]
        self.robot._ignored_actions.add("stop")  # 201, but the run reads running afterwards
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        self.assertEqual(self.status_of(run_id), "running")

    def test_an_unanswered_run_list_fails_the_stop_and_the_runs_read(self) -> None:
        client = self.serve()
        foreign = self.add_foreign_run("running")
        self.robot._offline = True  # GET /runs does not answer 200
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], UNREACHED)
        self.assertEqual(self.status_of(foreign), "running")
        with self.assertRaises(MHSError) as caught:  # an empty run list would claim that no run is stored
            client.read("main", **self.ids)
        self.assertEqual(caught.exception.code, FAULTED)

    def test_a_refused_play_fails_the_start_with_its_code(self) -> None:
        client = self.serve()
        self.robot._refused_actions.add("play")
        receipt = self.start(client)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], FAULTED)
        self.assertIn("HTTP 409", receipt["error"]["message"])
        (run_id,) = list(self.robot._runs)
        self.assertEqual(self.status_of(run_id), "idle")

    def test_a_play_request_that_raises_is_unknown_not_failed(self) -> None:
        client = self.serve()

        def broken_play(run_id):  # the connection drops: the robot may or may not have taken the play
            raise ConnectionError("connection reset")

        self.robot.resume = broken_play
        receipt = self.start(client)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNKNOWN)

    def test_an_estop_during_the_play_request_stops_the_new_run(self) -> None:
        client = self.serve()
        entered, release = threading.Event(), threading.Event()
        play = self.robot.resume

        def held_play(run_id):  # the play request is in flight until the test releases it
            entered.set()
            release.wait(10)
            return play(run_id)

        self.robot.resume = held_play
        receipts = []
        worker = threading.Thread(target=lambda: receipts.append(self.start(client)))
        worker.start()
        self.assertTrue(entered.wait(10))
        (run_id,) = list(self.robot._runs)
        self.assertEqual(self.status_of(run_id), "idle")
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertIn(self.status_of(run_id), STOPPED)
        release.set()
        worker.join(10)
        self.assertEqual(receipts[0]["status"], "cancelled", receipts[0])
        self.assertIn(self.status_of(run_id), STOPPED)

    def test_an_idle_own_run_without_a_play_in_flight_is_left_alone(self) -> None:
        client = self.serve()
        self.robot._refused_actions.add("play")
        self.assertEqual(self.start(client)["status"], "failed")
        (run_id,) = list(self.robot._runs)
        receipt = client.invoke(STOP_RUNS, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["stopped_runs"], [])
        self.assertEqual(self.status_of(run_id), "idle")


if __name__ == "__main__":
    unittest.main()
