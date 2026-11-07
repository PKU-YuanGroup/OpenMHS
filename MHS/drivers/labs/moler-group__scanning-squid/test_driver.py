"""Acceptance run of the scanning SQUID microscope's Attocube driver: the gate, plus repository-specific cases.

Add cases, never remove the check_driver call.  The fake follows instruments/atto.py; positions, step counts and the
example overlay's step limit are test data.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import Cancelled, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STEP = "x-cap.moler-group.atto_step.v1"
GROUND = "x-cap.moler-group.atto_ground.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))



def _achieved(status):
    """True once the runtime confirmed the e-stop's stop path (safety status estop.confirmed)."""
    return ((status or {}).get("estop") or {}).get("confirmed")

class _CancellingLock:
    """A lock that sets the operation's cancel event as it is entered (the e-stop's cancel, landing meanwhile)."""

    def __init__(self, event):
        self._lock = threading.Lock()
        self._event = event

    def __enter__(self):
        self._event.set()
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False

class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ScanningSquidAttocubeCases(unittest.TestCase):
    def serve(self, site_limits=SITE_LIMITS):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def test_state_reads_the_scanner_and_the_attocube_modes(self) -> None:
        client, fake = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["scanner_position"], [0.0, 0.0, -1.0])            # placeholder voltages
        self.assertEqual(state["attocube_modes"], {"x": "gnd", "y": "gnd", "z": "gnd"})

    def test_step_runs_the_upstream_step_and_reads_the_mode_back(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(STEP, {"axis": "z", "steps": -5}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"axis": "z", "steps": -5, "mode": "gnd"})
        # The upstream writes the step command twice (ask -> ask_raw, atto.py:109-124, 169); the fake counts the
        # requested steps once, a placeholder: the steps the ANC300 makes for the second copy are not known.
        self.assertEqual(fake.atto._commands, ["stepd 3 5", "stepd 3 5", "stepw 3"])
        self.assertEqual(fake.atto._steps["z"], -5)

    def test_steps_are_refused_without_the_operator_limit_and_outside_it(self) -> None:
        client, fake = self.serve(site_limits=None)
        refused = client.invoke(STEP, {"axis": "x", "steps": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        client, fake = self.serve()
        refused = client.invoke(STEP, {"axis": "x", "steps": 21}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(fake.atto._commands, [])

    def test_estop_stops_and_grounds_every_axis_z_first(self) -> None:
        client, fake = self.serve()
        fake.atto.parameters["mode_ax3"].set("stp")       # as during a step (atto.py:167)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertEqual(fake.atto._commands[:3], ["stop 3", "stop 1", "stop 2"])
        self.assertEqual({key: p.get() for key, p in fake.atto.parameters.items()},
                         {"mode_ax1": "gnd", "mode_ax2": "gnd", "mode_ax3": "gnd"})
        refused = client.invoke(STEP, {"axis": "z", "steps": 1}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_estop_fails_when_an_axis_does_not_read_back_grounded(self) -> None:
        client, fake = self.serve()

        def stop_without_ground(axis):
            fake.atto._commands.append(f"stop {fake.atto.axes[axis]}")

        fake.atto.stop = stop_without_ground
        fake.atto.parameters["mode_ax1"].set("stp")
        stopped = client.estop("x stays in stp", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_estop_tries_every_axis_when_one_stop_raises(self) -> None:
        client, fake = self.serve()
        original = fake.atto.stop

        def failing_z(axis):
            if axis == "z":
                raise RuntimeError("placeholder: VISA timeout")
            original(axis)

        fake.atto.stop = failing_z
        stopped = client.estop("z stop raises", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertIn("stop 1", fake.atto._commands)
        self.assertIn("stop 2", fake.atto._commands)

    def test_ground_action_reports_every_mode(self) -> None:
        client, fake = self.serve()
        receipt = client.invoke(GROUND, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"modes": {"x": "gnd", "y": "gnd", "z": "gnd"}})

    def test_an_axis_missing_from_the_configuration_is_refused(self) -> None:
        client, fake = self.serve()
        del fake.atto.axes["y"]
        refused = client.invoke(STEP, {"axis": "y", "steps": 1}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")

    def test_a_mode_read_during_a_step_is_refused_as_busy(self) -> None:
        client, fake = self.serve()
        original = fake.atto.step
        seen = []

        def step(axis, steps):
            try:
                seen.append(client.read("main", **self.ids))
            except Exception as exc:  # noqa: BLE001 - the refusal is what the case checks
                seen.append(getattr(exc, "code", None) or getattr(exc, "mhs_code", None) or str(exc))
            original(axis, steps)

        fake.atto.step = step
        receipt = client.invoke(STEP, {"axis": "x", "steps": 2}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(seen), 1)
        self.assertIn("MHS.DEVICE.BUSY", str(seen[0]))

    def test_a_step_cancelled_while_it_waits_for_the_session_never_starts(self) -> None:
        driver = load_driver(HERE, backend="fake")
        fake = driver.native
        event = threading.Event()
        driver._anc300_session = {"lock": _CancellingLock(event), "stepping": 0}
        with self.assertRaises(Cancelled):
            driver.call(STEP, {"axis": "z", "steps": 3}, {"cancel_event": event})
        self.assertEqual(fake.atto._commands, [])

    def test_an_estop_during_a_step_is_confirmed_only_after_the_step(self) -> None:
        client, fake = self.serve()
        original = fake.atto.step
        receipts = []

        def step(axis, steps):
            worker = threading.Thread(target=lambda: receipts.append(client.estop("during a step", **self.ids)))
            worker.start()
            worker.join(15)
            original(axis, steps)

        fake.atto.step = step
        receipt = client.invoke(STEP, {"axis": "z", "steps": 3}, **self.ids)
        self.assertEqual(receipt["status"], "cancelled", receipt)
        self.assertEqual(receipts[0]["status"], "failed", receipts)
        self.assertEqual(receipts[0]["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertIn("stop 3", fake.atto._commands)
        # The runtime re-runs the stop in the background; with no step in flight it is confirmed.
        deadline = time.monotonic() + 20
        status = None
        while time.monotonic() < deadline:
            status = client.safety_status(device_id=self.ids["device_id"])
            achieved = _achieved(status)
            if achieved is True:
                break
            time.sleep(0.1)
        self.assertIs(_achieved(status), True, status)
        # The step this test lets run after the first stop (as an upstream step that had not yet sent stepu would) is
        # followed by a later stop of the same axis: the re-run that confirmed.
        last_step = max(i for i, command in enumerate(fake.atto._commands) if command.startswith("step"))
        self.assertIn("stop 3", fake.atto._commands[last_step:])

    # -- review round 1 (Sonnet safety finding F6) -------------------------------------------------------------------
    def test_a_step_that_raises_grounds_its_axis_and_is_unknown(self) -> None:
        # As when the ANC300 answers the second copy of the step command with ERROR (atto.py:121-122, 140-141): the
        # axis is in mode stp and its first copy may be stepping.
        client, fake = self.serve()

        def failing_step(axis, steps):
            index = fake.atto.axes[axis]
            fake.atto.parameters[f"mode_ax{index}"].set("stp")              # atto.py:167
            fake.atto._commands.append(f"stepu {index} {steps}")            # the first copy (atto.py:120)
            raise RuntimeError("placeholder: ERROR in the reply to the second copy")

        fake.atto.step = failing_step
        receipt = client.invoke(STEP, {"axis": "z", "steps": 2}, **self.ids)
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertEqual(fake.atto._commands, ["stepu 3 2", "stop 3"])
        self.assertEqual(fake.atto.parameters["mode_ax3"].get(), "gnd")
        state = client.read("main", **self.ids)["state"]                   # no step is counted in flight any more
        self.assertEqual(state["attocube_modes"], {"x": "gnd", "y": "gnd", "z": "gnd"})

if __name__ == "__main__":
    unittest.main()
