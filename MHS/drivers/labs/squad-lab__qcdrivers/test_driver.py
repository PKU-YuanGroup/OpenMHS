"""Acceptance run of the SQUAD Lab AD75019 switch driver: the gate, plus repository-specific cases.

Add cases, never remove the check_driver call.  The fake answers with the clone's firmware strings
(helpers/firmware.ino); every other value below is test data.
"""

import json
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import Cancelled, DriverFailed, OutcomeUnknown, build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
CONNECT = "x-cap.squad-lab.mux_connect.v1"
STATUS = "x-cap.squad-lab.mux_status.v1"
RESET = "x-cap.squad-lab.mux_reset.v1"
SITE_LIMITS = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))


class _StaleRstThenRoute:
    """A reset *RST and the next SWITCH32 run, but their lines stay unread until after both queries time out.

    The following *RST is written and does not run with that write. When ``run_own_after`` lines have been read,
    the firmware's *RST handler runs, which is when 'Clear complete' and 'Reset complete' for that command exist.
    ``run_own_after is None`` never runs it: the stale pair sits in the buffer and further reads time out.
    """

    def __init__(self, firmware, *, run_own_after):
        self.firmware = firmware
        self.run_own_after = run_own_after
        self.original_query = firmware.query
        self.hidden: list[str] = []
        self.phase = "withhold"
        self.returned = 0
        self.own_ran = False
        self.route_before_own = None
        firmware.query = self.query
        firmware.read = self.read

    def query(self, command):
        firmware = self.firmware
        if self.phase == "withhold" and (command == "*RST" or str(command).startswith("SWITCH32")):
            firmware._receive(command)
            self.hidden.extend(firmware._lines)
            firmware._lines.clear()
            if str(command).startswith("SWITCH32"):
                firmware._lines.extend(self.hidden)
                self.hidden.clear()
                self.phase = "stale"
            raise TimeoutError("placeholder: read timed out; the lines arrive afterwards")
        if self.phase == "stale" and command == "*RST":
            firmware._commands.append(command)
            self.phase = "reading"
            return self.read()
        return self.original_query(command)

    def read(self):
        firmware = self.firmware
        if self.phase != "reading":
            if not firmware._lines:
                raise TimeoutError("placeholder: VISA read timed out (no line printed)")
            return firmware._lines.pop(0)
        if not firmware._lines:
            raise TimeoutError("placeholder: this *RST has not printed its lines")
        line = firmware._lines.pop(0)
        self.returned += 1
        if self.run_own_after is not None and self.returned == self.run_own_after and not self.own_ran:
            self.route_before_own = set(firmware._routes32)
            before = len(firmware._commands)
            firmware._receive("*RST")
            if len(firmware._commands) == before + 1 and firmware._commands[-1] == "*RST":
                firmware._commands.pop()
            self.own_ran = True
        return line


class _WithholdEveryReply:
    """Every query runs the sketch and hides its lines, until ``release`` puts them back in order.

    A served invoke reads ``*IDN?`` before and after the action. Those lines are part of the same debt as a
    timed-out ``*RST`` and a timed-out ``SWITCH32``. After ``release``, the next ``*RST`` is written and does
    not run until ``run_own_after`` lines have been read (``None`` never runs it).
    """

    def __init__(self, firmware, *, run_own_after):
        self.firmware = firmware
        self.run_own_after = run_own_after
        self.original_query = firmware.query
        self.hidden: list[str] = []
        self.phase = "withhold"
        self.returned = 0
        self.own_ran = False
        self.route_before_own = None
        firmware.query = self.query
        firmware.read = self.read

    def release(self):
        self.firmware._lines[0:0] = self.hidden
        self.hidden.clear()
        self.phase = "stale"

    def query(self, command):
        firmware = self.firmware
        if self.phase == "withhold":
            firmware._receive(command)
            self.hidden.extend(firmware._lines)
            firmware._lines.clear()
            raise TimeoutError("placeholder: read timed out; the lines arrive afterwards")
        if self.phase == "stale" and command == "*RST":
            firmware._commands.append(command)
            self.phase = "reading"
            return self.read()
        return self.original_query(command)

    def read(self):
        firmware = self.firmware
        if self.phase != "reading":
            if not firmware._lines:
                raise TimeoutError("placeholder: VISA read timed out (no line printed)")
            return firmware._lines.pop(0)
        if not firmware._lines:
            raise TimeoutError("placeholder: this *RST has not printed its lines")
        line = firmware._lines.pop(0)
        self.returned += 1
        if self.run_own_after is not None and self.returned == self.run_own_after and not self.own_ran:
            self.route_before_own = set(firmware._routes32)
            before = len(firmware._commands)
            firmware._receive("*RST")
            if len(firmware._commands) == before + 1 and firmware._commands[-1] == "*RST":
                firmware._commands.pop()
            self.own_ran = True
        return line


class _CancellingLock:
    """A lock that sets the operation's cancel event as it is entered (the e-stop's cancel, landing meanwhile)."""

    def __init__(self, event):
        self._lock = threading.RLock()   # the driver's line lock is re-entrant (connect holds it across two exchanges)
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


class SquadAd75019MuxCases(unittest.TestCase):
    def serve(self, site_limits=SITE_LIMITS):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        self.driver = driver
        return client, driver.native.visa_handle

    def test_identity_is_the_firmware_line(self) -> None:
        client, firmware = self.serve()
        state = client.read("main", **self.ids)["state"]
        self.assertEqual(state["identity"], "SQUAD, Arduino AD75019 Switch, 1.0, 1.0")   # firmware.ino:48
        self.assertIn("*IDN?", firmware._commands)

    def test_connect_reports_the_route_and_reads_it_back(self) -> None:
        client, firmware = self.serve()
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"], {"x": 1, "y": 2, "reply": "Route added 32x32", "routed": True})
        self.assertIn("SWITCH32 1,2", firmware._commands)
        self.assertIn("STAT? 1,2", firmware._commands)
        self.assertEqual(firmware._routes32, {(1, 2)})
        self.assertEqual(firmware._lines, [], "every printed line was read")

    def test_status_reads_the_route_buffer(self) -> None:
        client, firmware = self.serve()
        self.assertEqual(client.invoke(STATUS, {"x": 3, "y": 4}, **self.ids)["output"],
                         {"x": 3, "y": 4, "routed": False})
        self.assertEqual(client.invoke(CONNECT, {"x": 3, "y": 4}, **self.ids)["status"], "completed")
        self.assertEqual(client.invoke(STATUS, {"x": 3, "y": 4}, **self.ids)["output"],
                         {"x": 3, "y": 4, "routed": True})
        self.assertEqual(firmware._lines, [])

    def test_reset_reads_both_lines_and_keeps_the_stream_in_step(self) -> None:
        # The earlier package read one *RST line and left 'Reset complete' as the next command's reply.
        client, firmware = self.serve()
        client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        reset = client.invoke(RESET, {}, **self.ids)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertEqual(reset["output"], {"lines": ["Clear complete", "Reset complete"]})
        self.assertEqual(firmware._routes32, set())
        applied = client.invoke(CONNECT, {"x": 1, "y": 3}, **self.ids)
        self.assertEqual(applied["output"]["reply"], "Route added 32x32")
        self.assertEqual(firmware._lines, [])

    def test_estop_sends_rst_reads_both_lines_and_latches(self) -> None:
        client, firmware = self.serve()
        client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertIn("*RST", firmware._commands)
        self.assertEqual(firmware._routes32, set())
        self.assertEqual(firmware._lines, [])
        refused = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(firmware._routes32, set())

    def test_connect_reads_its_own_line_after_a_timed_out_rst(self) -> None:
        # *RST times out with both reply lines still unread. They then arrive. The connect must not take
        # "Clear complete" as the SWITCH32 reply; it skips the two owed lines and reads "Route added 32x32".
        # driver.call, not the server: a served invoke also reads *IDN?, which would drain the debt first.
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        hidden: list[str] = []
        original_query = firmware.query
        original_receive = firmware._receive

        def query(command):
            if command == "*RST" and not hidden and "*RST" not in firmware._commands:
                original_receive(command)
                hidden.extend(firmware._lines)
                firmware._lines.clear()
                raise TimeoutError("placeholder: *RST read timed out; lines arrive later")
            if hidden:
                firmware._lines[0:0] = hidden
                hidden.clear()
            return original_query(command)

        firmware.query = query
        with self.assertRaises(DriverFailed):
            driver.call(RESET, {}, {})
        self.assertEqual(driver._mux_lines_owed, 2)
        self.assertEqual(firmware._routes32, set())
        applied = driver.call(CONNECT, {"x": 1, "y": 2}, {})
        self.assertEqual(applied["reply"], "Route added 32x32")
        self.assertEqual(applied["routed"], True)
        self.assertEqual(firmware._routes32, {(1, 2)})
        self.assertEqual(firmware._lines, [])
        self.assertEqual(driver._mux_lines_owed, 0)

    def test_estop_fails_when_the_reset_lines_never_come(self) -> None:
        client, firmware = self.serve()

        def silent(command):
            firmware._commands.append(command)
            raise TimeoutError("placeholder: VISA read timed out")

        firmware.query = silent
        stopped = client.estop("silent firmware", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_estop_fails_without_the_clear_line(self) -> None:
        client, firmware = self.serve()
        original = firmware._receive

        def no_clear(command):
            original(command)
            if command == "*RST":
                firmware._lines.remove("Clear complete")

        firmware._receive = no_clear
        stopped = client.estop("no clear line", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")

    def test_disabled_pins_are_refused_by_the_firmware(self) -> None:
        wide = json.loads(json.dumps(SITE_LIMITS))
        wide["devices"]["mhs://localhost/squad-ad75019-mux"][CONNECT]["x"]["max"] = 31
        client, firmware = self.serve(site_limits=wide)
        refused = client.invoke(CONNECT, {"x": 12, "y": 2}, **self.ids)
        self.assertEqual(refused["status"], "failed", refused)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.DEVICE.PRECONDITION_UNMET")
        self.assertEqual(firmware._routes32, set())

    def test_an_unexpected_reply_is_an_unknown_outcome(self) -> None:
        client, firmware = self.serve()
        firmware._lines.append("Clear complete")      # a stale line ahead of the SWITCH32 reply
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "unknown", applied)

    def test_a_timeout_after_switch32_is_an_unknown_outcome(self) -> None:
        client, firmware = self.serve()
        original = firmware._receive

        def lost_reply(command):
            original(command)
            if command.startswith("SWITCH32"):
                firmware._lines.clear()               # the route was added; its reply is lost

        firmware._receive = lost_reply
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "unknown", applied)
        self.assertEqual(firmware._routes32, {(1, 2)})

    def test_operator_required_pins_refuse_without_an_overlay(self) -> None:
        client, firmware = self.serve(site_limits=None)
        refused = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")
        self.assertNotIn("SWITCH32 1,2", firmware._commands)

    def test_the_example_overlay_narrows_the_pins(self) -> None:
        client, firmware = self.serve()
        refused = client.invoke(CONNECT, {"x": 16, "y": 2}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
        self.assertEqual(firmware._routes32, set())

    def test_closing_the_driver_closes_the_handle(self) -> None:
        driver = load_driver(HERE, backend="fake")
        handle = driver.native.visa_handle
        driver.close()
        self.assertTrue(handle._closed)

    def test_a_connect_cancelled_while_it_waits_for_the_line_sends_nothing(self) -> None:
        # The guard of race_fixes.py: an e-stop cancels before it takes the line for *RST, so a connect that gets the
        # line afterwards must not send SWITCH32.
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        event = threading.Event()
        driver._mux_line_lock = _CancellingLock(event)
        with self.assertRaises(Cancelled):
            driver.call(CONNECT, {"x": 1, "y": 2}, {"cancel_event": event})
        self.assertNotIn("SWITCH32 1,2", firmware._commands)
        self.assertEqual(firmware._routes32, set())

    # -- review round 1 (Sonnet safety finding F1) -------------------------------------------------------------------
    def test_a_route_that_reads_back_0_fails(self) -> None:
        # The firmware answers 'Route added 32x32', but STAT? reads the 32x32 bit as 0 (the fake drops the route right
        # after SWITCH32): the connect must not report the route as made.
        client, firmware = self.serve()
        original = firmware._receive

        def dropped_route(command):
            original(command)
            if command.startswith("SWITCH32"):
                firmware._routes32.clear()

        firmware._receive = dropped_route
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "failed", applied)
        self.assertEqual(applied["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertIn("STAT? 1,2", firmware._commands)
        self.assertEqual(firmware._lines, [])

    def test_an_estop_waits_for_a_connect_that_holds_the_line(self) -> None:
        # The connect holds the line lock from SWITCH32 through its STAT? read-back.  Here an e-stop lands between the
        # two exchanges: its *RST must wait for the read-back, so the route is read back as made and then cleared.
        client, firmware = self.serve()
        driver = self.driver
        read_status, reset_matrix = driver._read_status, driver._reset_matrix
        at_the_line = threading.Event()
        receipts, workers = [], []

        def reset_at_the_line(**kwargs):
            at_the_line.set()                  # the e-stop is about to take the line lock (or, unlocked, write *RST)
            return reset_matrix(**kwargs)

        def status_after_an_estop_landed(x, y, *, effect):
            worker = threading.Thread(target=lambda: receipts.append(client.estop("during a connect", **self.ids)))
            workers.append(worker)
            worker.start()
            at_the_line.wait(10)
            deadline = time.monotonic() + 0.5
            while "*RST" not in firmware._commands and time.monotonic() < deadline:
                time.sleep(0.01)               # a *RST written now would fall between SWITCH32 and STAT?
            return read_status(x, y, effect=effect)

        driver._read_status = status_after_an_estop_landed
        driver._reset_matrix = reset_at_the_line
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        workers[0].join(15)
        self.assertTrue(at_the_line.is_set())
        commands = firmware._commands
        self.assertLess(commands.index("SWITCH32 1,2"), commands.index("STAT? 1,2"))
        self.assertLess(commands.index("STAT? 1,2"), commands.index("*RST"))
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(applied["output"]["routed"], True)
        self.assertEqual(receipts[0]["status"], "completed", receipts)
        self.assertEqual(firmware._routes32, set())
        self.assertEqual(firmware._lines, [])

    def test_a_reset_cancelled_while_it_waits_for_the_line_sends_nothing(self) -> None:
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        firmware._routes32.add((1, 2))
        event = threading.Event()
        driver._mux_line_lock = _CancellingLock(event)
        with self.assertRaises(Cancelled):
            driver.call(RESET, {}, {"cancel_event": event})
        self.assertNotIn("*RST", firmware._commands)
        self.assertEqual(firmware._routes32, {(1, 2)})

    def _timed_out_reset_and_connect(self, *, run_own_after):
        # Direct driver calls. A served invoke reads identity around the command and would drain the
        # unread lines before the caller saw the receipt; the debt still has to be right without that.
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        script = _StaleRstThenRoute(firmware, run_own_after=run_own_after)
        with self.assertRaises(DriverFailed):
            driver.call(RESET, {}, {})
        self.assertEqual(driver._mux_lines_owed, 2)
        with self.assertRaises(OutcomeUnknown):
            driver.call(CONNECT, {"x": 1, "y": 2}, {})
        self.assertEqual(firmware._routes32, {(1, 2)}, "SWITCH32 added a route after the timed-out *RST")
        self.assertEqual(driver._mux_lines_owed, 3)
        self.assertEqual(firmware._lines, ["Clear complete", "Reset complete", "Route added 32x32"])
        return driver, firmware, script

    def test_estop_does_not_confirm_before_its_own_rst_has_run(self) -> None:
        # BL-19. The stale 'Clear complete', 'Reset complete' pair is readable, and a route was added after
        # the *RST that printed it. The e-stop's own *RST has been written and has not run. Confirming on the
        # stale pair would report the safe state while that route is still closed.
        driver, firmware, script = self._timed_out_reset_and_connect(run_own_after=None)
        with self.assertRaises(DriverFailed) as caught:
            driver.estop("stale pair")
        self.assertEqual(caught.exception.code, "MHS.DEVICE.FAULTED")
        self.assertFalse(script.own_ran)
        self.assertEqual(firmware._routes32, {(1, 2)})
        self.assertEqual(firmware._commands, ["*RST", "SWITCH32 1,2", "*RST"])
        # Five lines were required (3 owed + this *RST's 2) and the three owed lines were read. The two that
        # this *RST has not printed stay owed.
        self.assertEqual(driver._mux_lines_owed, 2)

    def test_estop_confirms_only_after_its_own_rst_runs(self) -> None:
        # The same sequence, and the firmware runs this *RST only once the three owed lines have been read.
        # Those three are the earlier pair plus 'Route added 32x32'. The route is still closed until then.
        driver, firmware, script = self._timed_out_reset_and_connect(run_own_after=3)
        stopped = driver.estop("own pair")
        self.assertEqual(stopped["estop"], "engaged")
        self.assertTrue(script.own_ran)
        self.assertEqual(script.route_before_own, {(1, 2)})
        self.assertEqual(firmware._routes32, set())
        self.assertEqual(firmware._lines, [])
        self.assertEqual(driver._mux_lines_owed, 0)
        self.assertEqual(firmware._commands, ["*RST", "SWITCH32 1,2", "*RST"])

    def _served_timed_out_reset_and_connect(self, *, run_own_after):
        # client.invoke reads *IDN? before and after the action (a state read). Every one of those reads times
        # out here, so the debt is the seven sketch lines, not only the three of the direct-driver sequence.
        client, firmware = self.serve()
        script = _WithholdEveryReply(firmware, run_own_after=run_own_after)
        reset = client.invoke(RESET, {}, **self.ids)
        self.assertEqual(reset["status"], "failed", reset)
        self.assertEqual(reset["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertEqual(self.driver._mux_lines_owed, 4)
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "unknown", applied)
        self.assertEqual(applied["error"]["mhs_code"], "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(self.driver._mux_lines_owed, 7)
        self.assertEqual(firmware._routes32, {(1, 2)})
        self.assertEqual(script.hidden, [
            "SQUAD, Arduino AD75019 Switch, 1.0, 1.0",
            "Clear complete", "Reset complete",
            "SQUAD, Arduino AD75019 Switch, 1.0, 1.0",
            "SQUAD, Arduino AD75019 Switch, 1.0, 1.0",
            "Route added 32x32",
            "SQUAD, Arduino AD75019 Switch, 1.0, 1.0",
        ])
        script.release()
        return client, firmware, script

    def test_served_estop_does_not_confirm_on_the_stale_pair(self) -> None:
        # The stale pair is lines 2 and 3 of the seven. driver.estop, not client.estop: a failed client.estop
        # starts a background retry, and a later *RST would clear the route the assertion is about.
        _client, firmware, script = self._served_timed_out_reset_and_connect(run_own_after=None)
        with self.assertRaises(DriverFailed) as caught:
            self.driver.estop("served stale pair")
        self.assertEqual(caught.exception.code, "MHS.DEVICE.FAULTED")
        self.assertFalse(script.own_ran)
        self.assertEqual(firmware._routes32, {(1, 2)})
        self.assertEqual(firmware._commands, ["*IDN?", "*RST", "*IDN?", "*IDN?", "SWITCH32 1,2", "*IDN?", "*RST"])
        self.assertEqual(self.driver._mux_lines_owed, 2)

    def test_served_estop_confirms_only_after_its_own_rst_runs(self) -> None:
        client, firmware, script = self._served_timed_out_reset_and_connect(run_own_after=7)
        stopped = client.estop("served own pair", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertTrue(script.own_ran)
        self.assertEqual(script.route_before_own, {(1, 2)})
        self.assertEqual(firmware._routes32, set())
        self.assertEqual(firmware._lines, [])
        self.assertEqual(self.driver._mux_lines_owed, 0)
        self.assertEqual(firmware._commands, ["*IDN?", "*RST", "*IDN?", "*IDN?", "SWITCH32 1,2", "*IDN?", "*RST",
                                               "*IDN?"])

    def test_a_slow_reply_drain_does_not_delay_the_estop_rst(self) -> None:
        # SAFE-040. Forty owed *IDN? lines, each delivered only after 0.15 s, would hold the line lock past the
        # 5000 ms budget if the ordinary read drained them all. client.read has no cancel context. The drain must
        # yield when estop_epoch moves, and *RST must be on the wire before that budget. After *RST is written the
        # remaining lines return at once, so this stop can also confirm.
        client, firmware = self.serve()
        applied = client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids)
        self.assertEqual(applied["status"], "completed", applied)
        self.assertEqual(firmware._routes32, {(1, 2)})
        pending: list[str] = []
        withholding = {"on": True}
        entered = threading.Event()
        rst_at: list[float] = []

        def delayed_read():
            entered.set()
            if not rst_at:
                time.sleep(0.15)
            if not pending:
                raise TimeoutError("placeholder: no line was printed")
            return pending.pop(0)

        def query(command):
            if str(command) == "*RST":
                rst_at.append(time.monotonic())
            firmware._receive(str(command))
            pending.extend(firmware._lines)
            firmware._lines.clear()
            if withholding["on"]:
                raise TimeoutError("placeholder: the line is withheld until the read is slow")
            return delayed_read()

        firmware.query, firmware.read = query, delayed_read
        for _ in range(40):
            with self.assertRaises(DriverFailed):
                self.driver.identity()
        self.assertEqual(self.driver._lines_owed(), 40)
        self.assertEqual(len(pending), 40)
        self.assertFalse(entered.is_set(), "a withheld identity must not enter the slow read")
        withholding["on"] = False
        box: list[object] = []

        def run_read() -> None:
            try:
                box.append(client.read("main", **self.ids))
            except BaseException as exc:  # noqa: BLE001 - the yielded read is an outcome, not a test error
                box.append(exc)

        worker = threading.Thread(target=run_read, daemon=True)
        worker.start()
        self.assertTrue(entered.wait(2), "the ordinary read did not start")
        started = time.monotonic()
        stopped = client.estop("slow owed lines", **self.ids)
        self.assertTrue(rst_at, stopped)
        rst_first_sent_s = rst_at[0] - started
        self.assertLess(rst_first_sent_s, 1.0, {"rst_first_sent_s": round(rst_first_sent_s, 3),
                                                 "status": stopped.get("status"),
                                                 "routes": sorted(firmware._routes32)})
        self.assertEqual(sorted(firmware._routes32), [])
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        self.assertEqual(self.driver._lines_owed(), 0)
        worker.join(5)
        self.assertFalse(worker.is_alive(), "the ordinary read still holds the exchange")

    def test_an_ordinary_prefix_drain_releases_the_line_at_the_hold_bound(self) -> None:
        # No e-stop and no cancel. Twelve owed lines at 0.05 s each would take longer than the shortened hold.
        # The identity read must stop, leave a debt, and drop the line lock.
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        driver._ordinary_prefix_hold_s = 0.12
        pending: list[str] = []
        release = {"on": False}

        def slow_read():
            time.sleep(0.05)
            if not pending:
                raise TimeoutError("placeholder: no line was printed")
            return pending.pop(0)

        def query(command):
            firmware._receive(str(command))
            pending.extend(firmware._lines)
            firmware._lines.clear()
            if not release["on"]:
                raise TimeoutError("placeholder: withheld")
            return slow_read()

        firmware.query, firmware.read = query, slow_read
        for _ in range(12):
            with self.assertRaises(DriverFailed):
                driver.identity()
        self.assertEqual(driver._lines_owed(), 12)
        release["on"] = True
        started = time.monotonic()
        with self.assertRaises(DriverFailed) as caught:
            driver.identity()
        self.assertEqual(caught.exception.code, "MHS.DEVICE.FAULTED")
        self.assertLess(time.monotonic() - started, 0.45)
        self.assertGreater(driver._lines_owed(), 0)
        self.assertLess(driver._lines_owed(), 13)
        lock = driver._line_lock()
        self.assertTrue(lock.acquire(timeout=0.2))
        lock.release()

    def test_a_cancelled_exchange_stops_reading_owed_lines(self) -> None:
        # Cancellation is checked between owed lines, not only before the write. The unread count stays.
        driver = load_driver(HERE, backend="fake")
        firmware = driver.native.visa_handle
        pending: list[str] = []
        event = threading.Event()
        reads = {"n": 0}

        def slow_read():
            reads["n"] += 1
            event.set()
            time.sleep(0.02)
            if not pending:
                raise TimeoutError("placeholder: no line was printed")
            return pending.pop(0)

        def query(command):
            firmware._receive(str(command))
            pending.extend(firmware._lines)
            firmware._lines.clear()
            if reads["n"] == 0 and str(command) == "*IDN?":
                raise TimeoutError("placeholder: withheld")
            return slow_read()

        firmware.query, firmware.read = query, slow_read
        for _ in range(8):
            with self.assertRaises(DriverFailed):
                driver.identity()
        self.assertEqual(driver._lines_owed(), 8)
        self.assertEqual(len(pending), 8)
        with self.assertRaises(Cancelled):
            driver.call(CONNECT, {"x": 1, "y": 2}, {"cancel_event": event})
        self.assertLess(reads["n"], 8)
        self.assertGreater(reads["n"], 0)
        self.assertGreater(driver._lines_owed(), 0)
        lock = driver._line_lock()
        self.assertTrue(lock.acquire(timeout=0.2))
        lock.release()

    def test_one_owed_line_does_not_let_a_served_connect_block_the_estop_rst(self) -> None:
        # SAFE-040. One owed *IDN? line, then a served connect. Each successful read takes 1.6 s, under the 2000 ms
        # VISA timeout, so the 2.0 s prefix hold does not fire. After that owed line the connect used to read its
        # own SWITCH32 reply and both STAT? lines on the same lock: four reads, *RST after 6.4 s. The check after
        # the last owed line must yield before those reads. Later lines return at once so this stop can confirm.
        client, firmware = self.serve()
        pending: list[str] = []
        entered = threading.Event()
        rst_at: list[float] = []
        first_identity = {"on": True}

        def slow_read():
            if not rst_at:
                time.sleep(1.6)
            if not pending:
                raise TimeoutError("placeholder: no line was printed")
            return pending.pop(0)

        def query(command):
            command = str(command)
            if command == "*RST":
                rst_at.append(time.monotonic())
            firmware._receive(command)
            pending.extend(firmware._lines)
            firmware._lines.clear()
            if command == "*IDN?" and first_identity["on"]:
                first_identity["on"] = False
                raise TimeoutError("placeholder: the pre-invoke identity reply arrives after the timeout")
            if command.startswith("SWITCH32"):
                entered.set()
            return slow_read()

        firmware.query, firmware.read = query, slow_read
        box: list[object] = []

        def run_connect() -> None:
            try:
                box.append(client.invoke(CONNECT, {"x": 1, "y": 2}, **self.ids))
            except BaseException as exc:  # noqa: BLE001 - the yielded connect is an outcome, not a test error
                box.append(exc)

        worker = threading.Thread(target=run_connect, daemon=True)
        worker.start()
        self.assertTrue(entered.wait(3), "the served connect did not reach SWITCH32")
        self.assertEqual(self.driver._lines_owed(), 1)
        started = time.monotonic()
        stopped = client.estop("one owed line", **self.ids)
        self.assertTrue(rst_at, stopped)
        rst_first_sent_s = rst_at[0] - started
        self.assertLess(rst_first_sent_s, 3.0, {"rst_first_sent_s": round(rst_first_sent_s, 3),
                                                 "status": stopped.get("status"),
                                                 "routes": sorted(firmware._routes32)})
        self.assertEqual(sorted(firmware._routes32), [])
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(stopped["output"]["estop"], "engaged")
        worker.join(8)
        self.assertFalse(worker.is_alive(), "the served connect still holds the line")


if __name__ == "__main__":
    unittest.main()
