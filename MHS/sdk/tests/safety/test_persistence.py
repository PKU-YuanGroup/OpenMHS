"""Endpoint state across restarts: ``MHSServer(state_dir=...)`` (WP-04 step 4f).

Port of finding SDK-10 (sdk-core): every receipt, the idempotency store and the
e-stop latch lived in memory only, so a restarted endpoint forgot the latch
(SAFE-065), re-executed a retried ``command_id`` (OP-006) and started a new
evidence chain.  The reviewer's ``sdk-core/e10.py`` measured the in-memory
growth; the restart cases below are the scenario of the finding itself.

A "restart" is :meth:`MHSServer.close` followed by a new server on the same
``state_dir``.  A "crash" is a copy of the state directory taken while a command
is still running (what a killed process leaves on disk).
"""

from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
import unittest
import warnings
from pathlib import Path
from unittest import mock

from mhs.schema import SchemaStore
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope
from mhs._server import state as state_module
from mhs._server.state import StateDirError

from ._support import (
    DEVICE_ID,
    FIDELITY,
    LONG,
    MOVE,
    READ,
    STOP,
    NativeStopBridge,
    Rpc,
    StubBridge,
    error_code,
    in_thread,
    open_session,
    release_retry,
    stub_capabilities,
    stub_server,
    ulid,
    wait_until,
)

LATCH = state_module.LATCH_FILE
JOURNAL = state_module.JOURNAL_FILE
EVIDENCE = state_module.EVIDENCE_FILE
DOSE = "x-cap.test.dose.v1"


class _StateDirCase(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="mhs-wp04-4f-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state_dir = self.root / "state"

    def serve(self, bridge: StubBridge | None = None, *, state_dir: Path | None = None, **kwargs):
        server, rpc, device, bridge = stub_server(
            bridge, state_dir=state_dir if state_dir is not None else self.state_dir, **kwargs)
        self.addCleanup(server.close)
        return server, rpc, device, bridge

    def move(self, rpc: Rpc, session: str, pos: int, command_id: str | None = None, **params):
        return rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": pos},
                   command_id=command_id or ulid(), deadline_ms=2000, **params)

    def latch_document(self) -> dict:
        return json.loads((self.state_dir / LATCH).read_text(encoding="utf-8"))


class LatchPersistenceTests(_StateDirCase):
    """SAFE-065: a latched device stays latched across a restart."""

    def test_restart_keeps_the_latch_until_a_reset(self) -> None:
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        estop_id = ulid()
        engaged = rpc("mhs.safety.estop", session_id=session, reason="operator", command_id=estop_id,
                      deadline_ms=1000)
        self.assertEqual(engaged["status"], "completed", engaged)
        self.assertTrue(engaged["output"]["latch_persisted"], engaged)
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve(NativeStopBridge())
        self.assertTrue(restarted._latched[DEVICE_ID], "the restarted endpoint forgot the e-stop latch")
        status = rpc2("mhs.safety.status", device_id=DEVICE_ID, deadline_ms=1000)
        self.assertTrue(status["estop_engaged"], status)
        self.assertTrue(status["estop"]["engaged"], status)
        self.assertTrue(status["estop"]["restored"], status)
        self.assertFalse(status["estop"]["confirmed"], "nothing confirmed the stop path since the restart")
        session2 = open_session(rpc2, device2)
        moved = self.move(rpc2, session2, 3)
        self.assertEqual(moved["status"], "rejected", moved)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
        self.assertEqual(bridge2.count(MOVE), 0, "a latched device was actuated after a restart")
        replay = rpc2("mhs.safety.estop", session_id=session2, reason="operator", command_id=estop_id,
                      deadline_ms=1000)
        self.assertTrue(replay["replayed"], replay)
        self.assertEqual(replay["receipt_id"], engaged["receipt_id"])

        reset = rpc2("mhs.safety.reset", session_id=session2, deadline_ms=1000)
        self.assertEqual(reset["status"], "completed", reset)
        self.assertFalse(self.latch_document()["devices"][DEVICE_ID]["latched"])
        restarted.close()

        third, rpc3, device3, bridge3 = self.serve()
        self.assertFalse(third._latched[DEVICE_ID], "a completed reset must survive the restart too")
        session3 = open_session(rpc3, device3)
        self.assertEqual(self.move(rpc3, session3, 4)["status"], "completed")
        self.assertEqual(bridge3.count(MOVE), 1)

    def test_latch_is_on_disk_before_the_native_stop_runs(self) -> None:
        seen: list[bool] = []
        state_dir = self.state_dir

        class Probe(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                document = json.loads((state_dir / LATCH).read_text(encoding="utf-8"))
                seen.append(document["devices"][DEVICE_ID]["latched"])
                return super().estop(reason, ctx)

        server, rpc, device, _bridge = self.serve(Probe())
        self.assertFalse(self.latch_document()["devices"][DEVICE_ID]["latched"])
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="probe", deadline_ms=1000)
        self.assertEqual(seen, [True], "the latch file must say latched before bridge.estop() runs")

    def test_hung_native_estop_is_latched_on_disk_within_50_ms(self) -> None:
        release = threading.Event()
        self.addCleanup(release.set)

        class Hung(StubBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                release.wait(3.0)
                return {}

        server, rpc, device, _bridge = self.serve(Hung())
        session = open_session(rpc, device)
        started = time.monotonic()
        thread, holder = in_thread(lambda: rpc.raw("mhs.safety.estop", session_id=session,
                                                   reason="hung", deadline_ms=1000))
        self.assertTrue(wait_until(lambda: self._latched_on_disk(), timeout=1.0, step=0.0005))
        self.assertLess(time.monotonic() - started, 0.05)
        thread.join(2.0)
        receipt = holder["result"]["result"]
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        release.set()
        rpc.raw("mhs.safety.reset", session_id=session, deadline_ms=1000)

    def _latched_on_disk(self) -> bool:
        try:
            return self.latch_document()["devices"][DEVICE_ID]["latched"] is True
        except (OSError, ValueError, KeyError):
            return False

    def test_unreadable_latch_file_starts_latched(self) -> None:
        server, _rpc, _device, _bridge = self.serve()
        server.close()
        cases = {
            "not json": b"{not json",
            "empty": b"",
            "binary": b"\x00\xff\x00",
            "array": b"[]",
            "devices not an object": json.dumps(
                {"format": state_module.LATCH_FORMAT, "endpoint_id": "mhs://localhost/safety",
                 "devices": []}).encode(),
            "latched not a boolean": json.dumps(
                {"format": state_module.LATCH_FORMAT, "endpoint_id": "mhs://localhost/safety",
                 "devices": {DEVICE_ID: {"latched": "no"}}}).encode(),
            "unknown format": json.dumps({"format": "something/9", "devices": {}}).encode(),
        }
        for name, content in cases.items():
            with self.subTest(name):
                (self.state_dir / LATCH).write_bytes(content)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    restarted, rpc, device, bridge = self.serve()
                self.assertTrue(any("unreadable" in str(item.message) for item in caught),
                                [str(item.message) for item in caught])
                self.assertTrue(restarted._latched[DEVICE_ID], "an unreadable latch file must fail latched")
                kept = sorted(self.state_dir.glob(LATCH + ".unreadable-*"))
                self.assertTrue(kept, "the unreadable latch file is kept for inspection")
                self.assertEqual(kept[-1].read_bytes(), content)
                self.assertTrue(self.latch_document()["devices"][DEVICE_ID]["latched"])
                session = open_session(rpc, device)
                moved = self.move(rpc, session, 1)
                self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
                self.assertEqual(bridge.count(MOVE), 0)
                status = rpc("mhs.safety.status", device_id=DEVICE_ID, deadline_ms=1000)
                self.assertTrue(status["estop"]["engaged"])
                self.assertEqual(rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)["status"],
                                 "completed")
                restarted.close()

    def test_a_refused_start_leaves_the_unreadable_latch_file_in_place(self) -> None:
        """Fail closed twice: a start refused for another reason must not lose the latch file."""
        server, rpc, device, _bridge = self.serve()
        self.move(rpc, open_session(rpc, device), 1)
        server.close()
        (self.state_dir / LATCH).write_bytes(b"{damaged")
        journal = self.state_dir / JOURNAL
        good_journal = journal.read_bytes()
        lines = good_journal.splitlines(keepends=True)
        journal.write_bytes(lines[0] + b"{garbage\n" + b"".join(lines[1:]))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(StateDirError):
                stub_server(state_dir=self.state_dir)
        self.assertEqual((self.state_dir / LATCH).read_bytes(), b"{damaged",
                         "the refused start must leave the unreadable latch file where it was")
        self.assertEqual(list(self.state_dir.glob(LATCH + ".unreadable-*")), [])

        journal.write_bytes(good_journal)  # the operator repaired the journal
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            restarted, rpc2, device2, bridge2 = self.serve()
        self.assertTrue(restarted._latched[DEVICE_ID], "still fails latched")
        moved = self.move(rpc2, open_session(rpc2, device2), 2)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
        self.assertEqual([path.read_bytes() for path in self.state_dir.glob(LATCH + ".unreadable-*")],
                         [b"{damaged"])

    def test_a_restored_latch_covers_a_device_added_after_start(self) -> None:
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
        server.close()

        empty = MHSServer("mhs://localhost/safety", [], log_ready=False, state_dir=self.state_dir)
        self.addCleanup(empty.close)
        self.assertTrue(self.latch_document()["devices"][DEVICE_ID]["latched"],
                        "an absent device keeps its latch entry")
        bridge = StubBridge()
        late = Device(DEVICE_ID, "Safety stub", mode="simulated",
                      resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
                      capabilities=stub_capabilities(),
                      safety=SafetyEnvelope(risk_class="R1",
                                            estop={"kind": "software", "latching": True, "latency_ms": 50},
                                            safe_state={"description": "axis stopped", "achieved_by": [STOP]}),
                      fidelity=dict(FIDELITY), bridge=bridge)
        empty.devices[DEVICE_ID] = late
        rpc2 = Rpc(empty)
        rpc2("mhs.hello", protocol_versions=["1.0"])
        session2 = open_session(rpc2, late)
        moved = self.move(rpc2, session2, 2)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
        self.assertEqual(bridge.count(MOVE), 0)

    def test_a_state_dir_of_another_endpoint_is_refused(self) -> None:
        other = MHSServer("mhs://localhost/other", [], log_ready=False, state_dir=self.state_dir)
        other.close()
        with self.assertRaises(StateDirError) as caught:
            stub_server(state_dir=self.state_dir)
        self.assertIn("mhs://localhost/other", str(caught.exception))

    def test_a_failed_latch_write_keeps_the_latch_and_the_previous_file(self) -> None:
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        before = (self.state_dir / LATCH).read_bytes()
        session = open_session(rpc, device)
        with mock.patch.object(state_module.os, "replace", side_effect=OSError("disk full")), \
                self.assertLogs("mhs.server", "ERROR") as logged:
            receipt = rpc("mhs.safety.estop", session_id=session, reason="disk", deadline_ms=1000)
        self.assertIn("was not persisted", "\n".join(logged.output))
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(receipt["output"]["latch_persisted"], receipt)
        self.assertTrue(server._latched[DEVICE_ID], "a disk error never prevents the latch")
        self.assertEqual((self.state_dir / LATCH).read_bytes(), before, "the old file is intact")
        self.assertEqual(sorted(path.name for path in self.state_dir.iterdir() if ".tmp" in path.name), [],
                         "no temporary file is left behind")
        status = rpc("mhs.safety.status", device_id=DEVICE_ID, deadline_ms=1000)
        self.assertFalse(status["estop"]["persisted"], status)
        moved = self.move(rpc, session, 1)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
        # The next latch write (here the reset) succeeds and is atomic again.
        self.assertEqual(rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)["status"], "completed")
        self.assertFalse(self.latch_document()["devices"][DEVICE_ID]["latched"])

    def test_latch_writes_leave_no_temporary_files(self) -> None:
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        for _ in range(5):
            rpc("mhs.safety.estop", session_id=session, reason="cycle", deadline_ms=1000)
            self.assertEqual(rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)["status"],
                             "completed")
        names = sorted(path.name for path in self.state_dir.iterdir())
        self.assertEqual([name for name in names if ".tmp" in name], [], names)
        self.assertFalse(self.latch_document()["devices"][DEVICE_ID]["latched"])

    # -- the latch is also derived from the verified evidence (4f fix round) --
    def _restart_latched(self, *, expect_warning: str) -> tuple[MHSServer, Rpc, Device, StubBridge]:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            restarted, rpc, device, bridge = self.serve()
        messages = [str(item.message) for item in caught]
        self.assertTrue(any(expect_warning in message for message in messages), messages)
        self.assertTrue(restarted._latched[DEVICE_ID], "the restart came back unlatched")
        moved = self.move(rpc, open_session(rpc, device), 1)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED", moved)
        self.assertEqual(bridge.count(MOVE), 0, "a latched device was actuated after a restart")
        self.assertTrue(self.latch_document()["devices"][DEVICE_ID]["latched"], "latch.json is repaired")
        return restarted, rpc, device, bridge

    def test_a_deleted_latch_file_starts_latched(self) -> None:
        """Verifier repro ``latch_cases.py`` case 1: latch.json lost after an e-stop.

        The endpoint never leaves a directory whose evidence holds receipts
        without a latch file, so an absent one is lost state: fail latched,
        like an unreadable one (whatever the evidence says).
        """
        for index, scenario in enumerate(("after an e-stop", "after a reset")):
            with self.subTest(scenario):
                self.state_dir = self.root / f"state-{index}"
                server, rpc, device, _bridge = self.serve(NativeStopBridge())
                session = open_session(rpc, device)
                rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
                if scenario == "after a reset":
                    self.assertEqual(rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)["status"],
                                     "completed")
                server.close()
                (self.state_dir / LATCH).unlink()
                restarted, rpc2, device2, _bridge2 = self._restart_latched(expect_warning="missing")
                session2 = open_session(rpc2, device2)
                self.assertEqual(rpc2("mhs.safety.reset", session_id=session2, deadline_ms=1000)["status"],
                                 "completed")
                restarted.close()

    def test_an_absent_latch_file_without_receipts_is_a_fresh_directory(self) -> None:
        server, _rpc, _device, _bridge = self.serve()
        server.close()
        (self.state_dir / LATCH).unlink()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            restarted, _rpc2, _device2, _bridge2 = self.serve()
        self.assertFalse(restarted._latched[DEVICE_ID])
        self.assertEqual([str(item.message) for item in caught if "latch" in str(item.message)], [])

    def test_an_estop_whose_latch_write_failed_is_latched_after_restart(self) -> None:
        """Verifier repro ``latch_cases.py`` case 2: the e-stop receipt is in the evidence,
        latch.json still says unlatched (a nearly full disk: the small evidence append
        succeeded, creating the temp latch file did not)."""
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        with mock.patch.object(state_module.os, "replace", side_effect=OSError("disk full")), \
                self.assertLogs("mhs.server", "ERROR"):
            engaged = rpc("mhs.safety.estop", session_id=session, reason="disk", deadline_ms=1000)
        self.assertFalse(engaged["output"]["latch_persisted"], engaged)
        server.close()
        self.assertFalse(self.latch_document()["devices"][DEVICE_ID]["latched"], "the file still says unlatched")

        restarted, rpc2, device2, _bridge2 = self._restart_latched(expect_warning=engaged["receipt_id"])
        session2 = open_session(rpc2, device2)
        # A completed reset is the end of the latch the evidence derives.
        self.assertEqual(rpc2("mhs.safety.reset", session_id=session2, deadline_ms=1000)["status"], "completed")
        restarted.close()
        third, rpc3, device3, bridge3 = self.serve()
        self.assertFalse(third._latched[DEVICE_ID], "the reset receipt releases the evidence latch")
        self.assertEqual(self.move(rpc3, open_session(rpc3, device3), 2)["status"], "completed")
        self.assertEqual(bridge3.count(MOVE), 1)

    def test_a_latch_file_that_disagrees_with_the_evidence_fails_latched(self) -> None:
        """Verifier repro ``latch_cases.py`` case 5: a valid latch.json without the latch."""
        edits = {
            "entry removed": lambda document: document["devices"].clear(),
            "entry says unlatched": lambda document: document["devices"][DEVICE_ID].update(
                latched=False, reason=None, since=None),
        }
        for index, (name, edit) in enumerate(edits.items()):
            with self.subTest(name):
                self.state_dir = self.root / f"state-{index}"
                server, rpc, device, _bridge = self.serve(NativeStopBridge())
                session = open_session(rpc, device)
                engaged = rpc("mhs.safety.estop", session_id=session, reason="operator", deadline_ms=1000)
                server.close()
                document = self.latch_document()
                edit(document)
                (self.state_dir / LATCH).write_text(json.dumps(document), encoding="utf-8")
                restarted, rpc2, device2, _bridge2 = self._restart_latched(expect_warning=engaged["receipt_id"])
                self.assertEqual(rpc2("mhs.safety.reset", session_id=open_session(rpc2, device2),
                                      deadline_ms=1000)["status"], "completed")
                restarted.close()

    def test_a_latch_file_that_cannot_be_replaced_refuses_the_start(self) -> None:
        """Verifier repro ``latch_cases.py`` case 3: ``StateDirError``, not a raw ``OSError``."""
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        rpc("mhs.safety.estop", session_id=open_session(rpc, device), reason="operator", deadline_ms=1000)
        server.close()
        (self.state_dir / LATCH).unlink()
        (self.state_dir / LATCH).mkdir()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            with self.assertRaises(StateDirError) as caught:
                stub_server(state_dir=self.state_dir)
        self.assertIn(LATCH, str(caught.exception))
        self.assertEqual(sorted(path.name for path in self.state_dir.iterdir() if ".tmp" in path.name), [])
        (self.state_dir / LATCH).rmdir()  # the refused start released the directory
        restarted, _rpc2, _device2, _bridge2 = self._restart_latched(expect_warning="missing")
        restarted.close()

    def test_a_replayed_estop_reruns_the_stop_path_of_a_restored_latch(self) -> None:
        """SAFE-040 after a restart: nothing confirmed the stop path of a restored latch."""
        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        estop_id = ulid()
        engaged = rpc("mhs.safety.estop", session_id=session, reason="operator", command_id=estop_id,
                      deadline_ms=1000)
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve(NativeStopBridge())
        session2 = open_session(rpc2, device2)
        replay = rpc2("mhs.safety.estop", session_id=session2, reason="operator", command_id=estop_id,
                      deadline_ms=1000)
        self.assertTrue(replay["replayed"], replay)
        self.assertEqual(replay["receipt_id"], engaged["receipt_id"])
        self.assertEqual(bridge2.count("estop"), 1, "the stop path of a restored latch must run again")
        status = rpc2("mhs.safety.status", device_id=DEVICE_ID, deadline_ms=1000)
        self.assertTrue(status["estop"]["confirmed"], status)
        rpc2("mhs.safety.estop", session_id=session2, reason="operator", command_id=estop_id, deadline_ms=1000)
        self.assertEqual(bridge2.count("estop"), 1, "a confirmed latch is not stopped again by a replay")
        self.assertEqual(rpc2("mhs.safety.reset", session_id=session2, deadline_ms=1000)["status"], "completed")

    def test_a_restored_latch_whose_stop_path_fails_is_retried(self) -> None:
        class FailsOnce(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                result = super().estop(reason, ctx)
                if self.count("estop") == 1:
                    raise RuntimeError("the stop path did not answer")
                return result

        server, rpc, device, _bridge = self.serve(NativeStopBridge())
        session = open_session(rpc, device)
        estop_id = ulid()
        rpc("mhs.safety.estop", session_id=session, reason="operator", command_id=estop_id, deadline_ms=1000)
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve(FailsOnce())
        session2 = open_session(rpc2, device2)
        self.addCleanup(release_retry, restarted, rpc2, device2, session2)
        rpc2("mhs.safety.estop", session_id=session2, reason="operator", command_id=estop_id, deadline_ms=1000)
        self.assertTrue(wait_until(lambda: bridge2.count("estop") >= 2, timeout=3.0),
                        "a failed stop path of a restored latch is retried in the background")
        self.assertTrue(wait_until(
            lambda: rpc2("mhs.safety.status", device_id=DEVICE_ID, deadline_ms=1000)["estop"]["confirmed"],
            timeout=3.0))


class IdempotencyPersistenceTests(_StateDirCase):
    """OP-006: the idempotency store survives a restart (and a crash)."""

    def test_completed_command_replays_after_restart(self) -> None:
        server, rpc, device, bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        first = self.move(rpc, session, 5, command_id)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(bridge.count(MOVE), 1)
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        replay = self.move(rpc2, session2, 5, command_id)
        self.assertTrue(replay["replayed"], replay)
        self.assertEqual(replay["receipt_id"], first["receipt_id"])
        self.assertEqual(replay["evidence"], first["evidence"])
        self.assertEqual({key: value for key, value in replay.items() if key != "replayed"},
                         {key: value for key, value in first.items() if key != "replayed"})
        self.assertEqual(bridge2.count(MOVE), 0, "a retried command_id was executed again after the restart")

        reuse = self.move(rpc2, session2, 6, command_id)
        self.assertEqual(reuse["status"], "rejected", reuse)
        self.assertEqual(error_code(reuse), "MHS.CONFLICT.COMMAND_ID_REUSE", reuse)
        self.assertEqual(bridge2.count(MOVE), 0)

    def test_a_rejected_attempt_is_not_the_outcome_after_restart(self) -> None:
        server, rpc, device, bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        refused = self.move(rpc, session, 5, command_id, expected_revision=99)
        self.assertEqual(error_code(refused), "MHS.CONFLICT.REVISION", refused)
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        again = self.move(rpc2, session2, 5, command_id)
        self.assertEqual(again["status"], "completed", again)
        self.assertFalse(again["replayed"])
        self.assertEqual(bridge2.count(MOVE), 1)

    def test_a_command_in_flight_at_a_crash_is_unknown_after_restart(self) -> None:
        gate = threading.Event()
        entered = threading.Event()
        self.addCleanup(gate.set)

        class Blocking(StubBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == MOVE:
                    entered.set()
                    gate.wait(5.0)
                return super().call(capability_id, args, ctx)

        server, rpc, device, _bridge = self.serve(Blocking())
        session = open_session(rpc, device)
        command_id = ulid()
        thread, holder = in_thread(lambda: self.move(rpc, session, 7, command_id))
        self.assertTrue(entered.wait(2.0))
        crashed = self.root / "crashed"
        shutil.copytree(self.state_dir, crashed)  # what a killed process leaves on disk
        gate.set()
        thread.join(3.0)
        self.assertEqual(holder["result"]["status"], "completed")

        restarted, rpc2, device2, bridge2 = self.serve(state_dir=crashed)
        session2 = open_session(rpc2, device2)
        retry = self.move(rpc2, session2, 7, command_id)
        self.assertEqual(retry["status"], "unknown", retry)
        self.assertTrue(retry["replayed"], retry)
        self.assertEqual(error_code(retry), "MHS.OUTCOME.UNKNOWN", retry)
        self.assertFalse(retry["error"]["retryable"])
        self.assertEqual(retry["error"]["details"]["reason"], "endpoint_restarted", retry)
        self.assertEqual(retry["capability_id"], MOVE)
        self.assertEqual(retry["session_id"], session)
        self.assertEqual(bridge2.count(MOVE), 0, "a command that may have actuated was executed again")
        exported = rpc2("mhs.evidence.export")
        reconciled = [item for item in exported["receipts"] if item.get("command_id") == command_id]
        self.assertEqual([item["status"] for item in reconciled], ["unknown"])
        self.assertEqual(SchemaStore().validate(reconciled[0], "receipt.schema.json"), [])
        report = rpc2("mhs.evidence.verify")
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["schema"], "validated", report)
        restarted.close()

        again, rpc3, device3, bridge3 = self.serve(state_dir=crashed)
        session3 = open_session(rpc3, device3)
        retry3 = self.move(rpc3, session3, 7, command_id)
        self.assertEqual(retry3["receipt_id"], retry["receipt_id"], "reconciled once, then retained")
        self.assertEqual(bridge3.count(MOVE), 0)

    def test_a_rejected_duplicate_does_not_settle_a_command_in_flight(self) -> None:
        """Verifier repro ``dup_settles.py`` ('reuse'): a COMMAND_ID_REUSE refusal of a
        duplicate sent while the command blocks in the bridge must neither end its
        write-ahead record nor settle it at the restart (double actuation)."""
        gate = threading.Event()
        entered = threading.Event()
        self.addCleanup(gate.set)

        class Blocking(StubBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == MOVE and not entered.is_set():
                    entered.set()
                    gate.wait(5.0)
                return super().call(capability_id, args, ctx)

        server, rpc, device, _bridge = self.serve(Blocking())
        session = open_session(rpc, device)
        command_id = ulid()
        thread, holder = in_thread(lambda: self.move(rpc, session, 7, command_id))
        self.assertTrue(entered.wait(2.0))
        duplicate = self.move(rpc, session, 8, command_id)
        self.assertEqual(error_code(duplicate), "MHS.CONFLICT.COMMAND_ID_REUSE", duplicate)
        crashed = self.root / "crashed"
        shutil.copytree(self.state_dir, crashed)  # the crash: the refusal is on disk, the outcome is not
        gate.set()
        thread.join(3.0)
        self.assertEqual(holder["result"]["status"], "completed")

        restarted, rpc2, device2, bridge2 = self.serve(state_dir=crashed)
        session2 = open_session(rpc2, device2)
        retry = self.move(rpc2, session2, 7, command_id)
        self.assertEqual(retry["status"], "unknown", retry)
        self.assertEqual(retry["error"]["details"]["reason"], "endpoint_restarted", retry)
        self.assertEqual(bridge2.count(MOVE), 0, "a command that may have actuated was executed again")

    def test_a_failed_write_ahead_record_refuses_an_effectful_command(self) -> None:
        """Verifier repro ``begin_fail.py``: without its ``begin`` line a crash would re-run
        the command, so an effectful command is refused before any bridge I/O.  Reads and
        stop classes are not (they need no crash protection)."""
        server, rpc, device, bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        real_append = state_module.StateDir.append

        def failing(store, entry):  # noqa: ANN001
            if entry.get("op") == "begin":
                raise OSError(28, "No space left on device")
            return real_append(store, entry)

        command = lambda capability_id, cid=None: rpc(  # noqa: E731
            "mhs.command", session_id=session, capability_id=capability_id, input={},
            command_id=cid or ulid(), deadline_ms=2000)
        with mock.patch.object(state_module.StateDir, "append", failing), \
                self.assertLogs("mhs.server", "ERROR") as logged:
            refused = self.move(rpc, session, 7, command_id)
            stopped = command(STOP)
            read = command(READ)
        self.assertIn("begin", "\n".join(logged.output))
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(error_code(refused), "MHS.INTERNAL.ERROR", refused)
        self.assertEqual(refused["error"]["details"]["reason"], "journal_write_failed", refused)
        self.assertEqual(bridge.count(MOVE), 0, "the command reached the bridge without a write-ahead record")
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual(bridge.count(STOP), 1)
        self.assertEqual(read["status"], "completed", read)
        self.assertEqual(server._inflight, {}, "a refused reservation is released")
        # Nothing ran: once the journal is writable the same command id runs, once.
        again = self.move(rpc, session, 7, command_id)
        self.assertEqual(again["status"], "completed", again)
        self.assertEqual(bridge.count(MOVE), 1)

    def test_the_reconciling_final_receipt_survives_restart(self) -> None:
        server, rpc, device, bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        answered = rpc("mhs.command", session_id=session, capability_id=LONG, input={"ms": 300},
                       command_id=command_id, deadline_ms=60)
        self.assertEqual(answered["status"], "unknown", answered)
        self.assertTrue(wait_until(
            lambda: rpc("mhs.command", session_id=session, capability_id=LONG, input={"ms": 300},
                        command_id=command_id, deadline_ms=1000)["status"] == "completed", timeout=3.0))
        server.close()

        restarted, rpc2, device2, bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        replay = rpc2("mhs.command", session_id=session2, capability_id=LONG, input={"ms": 300},
                      command_id=command_id, deadline_ms=1000)
        self.assertEqual(replay["status"], "completed", replay)
        self.assertEqual(replay["x-vendor"]["reconciles"]["receipt_id"], answered["receipt_id"], replay)
        self.assertEqual(bridge2.count(LONG), 0)

    def test_the_evidence_chain_continues_across_restart(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        first = self.move(rpc, session, 1)
        before = rpc("mhs.evidence.export")
        server.close()

        restarted, rpc2, device2, _bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        second = self.move(rpc2, session2, 2)
        after = rpc2("mhs.evidence.export")
        self.assertEqual(after["endpoint_info"]["genesis_digest"], before["endpoint_info"]["genesis_digest"])
        self.assertEqual(second["evidence"]["prev_digest"], before["head_digest"])
        self.assertEqual(second["evidence"]["seq"], first["evidence"]["seq"] + 1)
        ids = [item["receipt_id"] for item in after["receipts"]]
        self.assertIn(first["receipt_id"], ids)
        report = rpc2("mhs.evidence.verify")
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checked"], len(before["receipts"]) + 1)

    def test_the_revision_never_goes_back_after_restart(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        moved = self.move(rpc, session, 9)
        self.assertEqual(moved["state_revision_after"], 1, moved)
        server.close()

        restarted, rpc2, device2, _bridge2 = self.serve()
        revision = restarted._current_revision(device2)
        self.assertGreater(revision, 1, "a pre-restart revision must never be current again")
        session2 = open_session(rpc2, device2)
        stale = self.move(rpc2, session2, 10, expected_revision=1)
        self.assertEqual(error_code(stale), "MHS.CONFLICT.REVISION", stale)
        fresh = self.move(rpc2, session2, 10, expected_revision=revision)
        self.assertEqual(fresh["status"], "completed", fresh)
        self.assertEqual(fresh["state_revision_after"], revision + 1)
        restarted.close()

        third, _rpc3, device3, _bridge3 = self.serve()
        self.assertGreater(third._current_revision(device3), revision + 1)

    def test_a_torn_journal_tail_is_recovered_from_the_evidence(self) -> None:
        server, rpc, device, bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        first = self.move(rpc, session, 5, command_id)
        server.close()
        journal = self.state_dir / JOURNAL
        lines = journal.read_bytes().splitlines(keepends=True)
        ops = [json.loads(line)["op"] for line in lines]
        self.assertEqual(ops[-2:], ["put", "end"], ops)
        # The crash hit while the index entry was written: only half of it is there.
        journal.write_bytes(b"".join(lines[:-2]) + lines[-2][: len(lines[-2]) // 2])

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            restarted, rpc2, device2, bridge2 = self.serve()
        self.assertTrue(any("torn" in str(item.message) for item in caught),
                        [str(item.message) for item in caught])
        session2 = open_session(rpc2, device2)
        replay = self.move(rpc2, session2, 5, command_id)
        self.assertTrue(replay["replayed"], replay)
        self.assertEqual(replay["receipt_id"], first["receipt_id"])
        self.assertEqual(bridge2.count(MOVE), 0)
        statuses = [item["status"] for item in rpc2("mhs.evidence.export")["receipts"]
                    if item.get("command_id") == command_id]
        self.assertEqual(statuses, ["completed"], "the evidence already had the outcome: nothing to reconcile")

    def test_a_lost_evidence_tail_makes_the_command_unknown(self) -> None:
        """A power failure without fsync=True can keep the journal's tail and lose the evidence's."""
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        first = self.move(rpc, session, 5, command_id)
        server.close()
        evidence = self.state_dir / EVIDENCE
        lines = evidence.read_bytes().splitlines(keepends=True)
        self.assertEqual(json.loads(lines[-1])["receipt_id"], first["receipt_id"])
        evidence.write_bytes(b"".join(lines[:-1]))

        restarted, rpc2, device2, bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        retry = self.move(rpc2, session2, 5, command_id)
        self.assertEqual(retry["status"], "unknown", retry)
        self.assertEqual(retry["error"]["details"]["lost_receipt_id"], first["receipt_id"], retry)
        self.assertEqual(bridge2.count(MOVE), 0, "a command whose receipt was lost ran again")
        self.assertTrue(rpc2("mhs.evidence.verify")["valid"])

    def test_a_torn_evidence_tail_is_kept_aside_and_the_command_is_unknown(self) -> None:
        """A crash during the evidence append of a receipt: its line is cut short."""
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        first = self.move(rpc, session, 5, command_id)
        server.close()
        evidence = self.state_dir / EVIDENCE
        lines = evidence.read_bytes().splitlines(keepends=True)
        torn = lines[-1][: len(lines[-1]) // 2]
        evidence.write_bytes(b"".join(lines[:-1]) + torn)
        # The journal line for that receipt was not written yet either.
        journal = self.state_dir / JOURNAL
        journal.write_bytes(b"".join(line for line in journal.read_bytes().splitlines(keepends=True)
                                     if json.loads(line)["op"] not in ("put", "end")))

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            restarted, rpc2, device2, bridge2 = self.serve()
        self.assertTrue(any("torn" in str(item.message) for item in caught),
                        [str(item.message) for item in caught])
        kept = list(self.state_dir.glob(EVIDENCE + ".torn-*"))
        self.assertEqual([path.read_bytes() for path in kept], [torn])
        session2 = open_session(rpc2, device2)
        retry = self.move(rpc2, session2, 5, command_id)
        self.assertEqual(retry["status"], "unknown", retry)
        self.assertNotEqual(retry["receipt_id"], first["receipt_id"])
        self.assertEqual(bridge2.count(MOVE), 0)
        self.assertTrue(rpc2("mhs.evidence.verify")["valid"])

    def test_a_damaged_evidence_line_refuses_to_start(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        self.move(rpc, session, 5)
        self.move(rpc, session, 6)
        server.close()
        evidence = self.state_dir / EVIDENCE
        lines = evidence.read_bytes().splitlines(keepends=True)
        record = json.loads(lines[1])
        self.assertEqual(record["output"], {"pos": 5})
        record["output"]["pos"] = 50  # an edited receipt in the middle of the chain
        lines[1] = (json.dumps(record) + "\n").encode()
        evidence.write_bytes(b"".join(lines))
        with self.assertRaises(StateDirError) as caught:
            stub_server(state_dir=self.state_dir)
        self.assertIn(EVIDENCE, str(caught.exception))

    def test_a_lost_evidence_tail_without_a_begin_refuses_to_start(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        self.move(rpc, session, 5)
        server.close()
        evidence = self.state_dir / EVIDENCE
        evidence.write_bytes(b"".join(evidence.read_bytes().splitlines(keepends=True)[:-1]))
        journal = self.state_dir / JOURNAL
        kept = [line for line in journal.read_bytes().splitlines(keepends=True)
                if json.loads(line)["op"] != "begin"]
        journal.write_bytes(b"".join(kept))
        with self.assertRaises(StateDirError) as caught:
            stub_server(state_dir=self.state_dir)
        self.assertIn("past the end", str(caught.exception))

    def test_a_missing_journal_is_rebuilt_from_the_evidence(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        command_id = ulid()
        first = self.move(rpc, session, 5, command_id)
        server.close()
        (self.state_dir / JOURNAL).unlink()

        restarted, rpc2, device2, bridge2 = self.serve()
        session2 = open_session(rpc2, device2)
        replay = self.move(rpc2, session2, 5, command_id)
        self.assertEqual(replay["receipt_id"], first["receipt_id"], replay)
        self.assertEqual(bridge2.count(MOVE), 0)

    def test_a_corrupt_journal_refuses_to_start(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        self.move(rpc, session, 5)
        server.close()
        journal = self.state_dir / JOURNAL
        lines = journal.read_bytes().splitlines(keepends=True)
        journal.write_bytes(lines[0] + b"{garbage\n" + b"".join(lines[1:]))
        with self.assertRaises(StateDirError) as caught:
            stub_server(state_dir=self.state_dir)
        self.assertIn(JOURNAL, str(caught.exception))

    def test_a_journal_entry_the_evidence_does_not_hold_refuses_to_start(self) -> None:
        server, rpc, device, _bridge = self.serve()
        session = open_session(rpc, device)
        self.move(rpc, session, 5)
        server.close()
        journal = self.state_dir / JOURNAL
        lines = journal.read_bytes().splitlines(keepends=True)
        entries = [json.loads(line) for line in lines]
        put = next(index for index, entry in enumerate(entries) if entry["op"] == "put")
        entries[put]["receipt_id"] = ulid()
        journal.write_text("".join(json.dumps(entry) + "\n" for entry in entries), encoding="utf-8")
        with self.assertRaises(StateDirError):
            stub_server(state_dir=self.state_dir)

    def test_the_cumulative_budget_survives_restart(self) -> None:
        def dose_server(state_dir: Path):
            caps = stub_capabilities(extra=[Capability(
                DOSE, "axis",
                input_schema={"type": "object", "properties": {"dose": {"type": "number", "x-mhs-unit": "mL"}}})])
            safety = SafetyEnvelope(
                risk_class="R1", envelope={DOSE: {"dose": {"max": 10, "per": "rolling_1h", "unit": "mL"}}},
                estop={"kind": "software", "latching": True, "latency_ms": 50},
                safe_state={"description": "axis stopped", "achieved_by": [STOP]})
            return self.serve(capabilities=caps, safety=safety, state_dir=state_dir)

        server, rpc, device, bridge = dose_server(self.state_dir)
        session = open_session(rpc, device)
        dose = lambda r, s, amount: r("mhs.command", session_id=s, capability_id=DOSE,  # noqa: E731
                                      input={"dose": amount}, command_id=ulid(), deadline_ms=2000)
        self.assertEqual(dose(rpc, session, 8)["status"], "completed")
        server.close()

        restarted, rpc2, device2, bridge2 = dose_server(self.state_dir)
        session2 = open_session(rpc2, device2)
        over = dose(rpc2, session2, 3)
        self.assertEqual(error_code(over), "MHS.SAFETY.CUMULATIVE_LIMIT",
                         "a restart must not refill the rolling budget")
        self.assertEqual(over["error"]["details"]["used"], 8, over)
        self.assertEqual(bridge2.count(DOSE), 0)
        self.assertEqual(dose(rpc2, session2, 2)["status"], "completed")

    def test_hello_advertises_the_receipt_store(self) -> None:
        server, rpc, _device, _bridge = self.serve()
        self.assertEqual(rpc("mhs.hello", protocol_versions=["1.0"])["limits"]["receipt_store"], "state_dir")
        memory, rpc_memory, _d, _b = stub_server()
        self.assertEqual(rpc_memory("mhs.hello", protocol_versions=["1.0"])["limits"]["receipt_store"], "memory")

    @unittest.skipUnless(state_module.HAVE_FLOCK, "advisory file locks are POSIX-only")
    def test_a_state_dir_in_use_is_refused(self) -> None:
        server, _rpc, _device, _bridge = self.serve()
        with self.assertRaises(StateDirError) as caught:
            stub_server(state_dir=self.state_dir)
        self.assertIn("in use", str(caught.exception))
        server.close()
        server.close()  # idempotent
        restarted, _rpc2, _device2, _bridge2 = self.serve()
        self.assertFalse(restarted._latched[DEVICE_ID])

    def test_fsync_true_syncs_every_append(self) -> None:
        server, rpc, device, _bridge = self.serve(fsync=True)
        session = open_session(rpc, device)
        real_fsync = state_module.os.fsync
        with mock.patch.object(state_module.os, "fsync", side_effect=real_fsync) as synced:
            self.assertEqual(self.move(rpc, session, 1)["status"], "completed")
        # The evidence append, and the journal's begin, put and end lines.
        self.assertGreaterEqual(synced.call_count, 4, synced.call_args_list)
        server.close()
        restarted, rpc2, device2, _bridge2 = self.serve()
        self.assertEqual(len(rpc2("mhs.evidence.export")["receipts"]), 1)

    def test_without_state_dir_nothing_is_written(self) -> None:
        import builtins
        import io
        import os

        opened: list[str] = []
        real_open = builtins.open

        def recording_open(file, mode="r", *args, **kwargs):  # noqa: ANN001
            if any(flag in mode for flag in "wax+"):
                opened.append(f"{file} ({mode})")
            return real_open(file, mode, *args, **kwargs)

        previous = os.getcwd()
        os.chdir(self.root)  # a relative path anywhere would land here
        self.addCleanup(os.chdir, previous)
        with mock.patch.object(state_module, "StateDir", side_effect=AssertionError("StateDir constructed")) \
                as constructed, \
                mock.patch.object(state_module, "atomic_write_bytes",
                                  side_effect=AssertionError("atomic write")) as written, \
                mock.patch.object(builtins, "open", recording_open), \
                mock.patch.object(io, "open", recording_open):
            server, rpc, device, _bridge = stub_server()
            session = open_session(rpc, device)
            self.move(rpc, session, 1)
            rpc("mhs.safety.estop", session_id=session, reason="memory", deadline_ms=1000)
            self.assertNotIn("latch_persisted", rpc("mhs.safety.estop", session_id=session, reason="again",
                                                    deadline_ms=1000)["output"])
            rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
            server.close()
        self.assertEqual(constructed.call_count, 0)
        self.assertEqual(written.call_count, 0)
        self.assertEqual(opened, [], "the in-memory endpoint opened a file for writing")
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIsNone(server.state_dir)


class ReservationOwnershipTests(unittest.TestCase):
    """The command id reservation belongs to the request that made it (4f fix round).

    A rejected duplicate (``COMMAND_ID_REUSE`` while the command is in flight)
    used to release the in-flight reservation of the command it collided with,
    which (in memory) let an identical retry run the command a second time and
    (with ``state_dir``) wrote the ``end`` line that made a crash re-run it.
    """

    PULSE = "x-cap.test.pulse.v1"

    def test_a_rejected_duplicate_keeps_the_reservation_of_the_command_in_flight(self) -> None:
        gate = threading.Event()
        entered = threading.Event()
        self.addCleanup(gate.set)
        pulse = self.PULSE

        class Blocking(StubBridge):
            def call(self, capability_id, args=None, ctx=None):  # noqa: ANN001
                if capability_id == pulse and not entered.is_set():
                    entered.set()
                    gate.wait(5.0)
                return super().call(capability_id, args, ctx)

        caps = stub_capabilities(extra=[Capability(
            pulse, "axis", input_schema={"type": "object", "properties": {"n": {"type": "integer"}}},
            exclusive=False)])  # no device lock to hide the double run
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            server, rpc, device, bridge = stub_server(Blocking(), capabilities=caps)
        self.addCleanup(server.close)
        session = open_session(rpc, device)
        command_id = ulid()
        command = lambda n: rpc("mhs.command", session_id=session, capability_id=pulse,  # noqa: E731
                                input={"n": n}, command_id=command_id, deadline_ms=2000)
        thread, holder = in_thread(lambda: command(1))
        self.assertTrue(entered.wait(2.0))
        duplicate = command(2)
        self.assertEqual(error_code(duplicate), "MHS.CONFLICT.COMMAND_ID_REUSE", duplicate)
        self.assertIn((DEVICE_ID, command_id), server._inflight, "the duplicate released the reservation")
        retry = command(1)
        self.assertNotEqual(retry["status"], "completed", retry)
        # The original is still blocked inside the bridge (it records its call
        # once it returns): any call recorded now is the retry's.
        self.assertEqual(bridge.count(pulse), 0, "the identical retry ran the command a second time")
        gate.set()
        thread.join(3.0)
        self.assertEqual(holder["result"]["status"], "completed")
        self.assertEqual(bridge.count(pulse), 1)
        self.assertNotIn((DEVICE_ID, command_id), server._inflight)
        replay = command(1)
        self.assertTrue(replay["replayed"], replay)


class JournalSettleTests(unittest.TestCase):
    """:meth:`StateDir.load_journal`: only the command's own outcome settles its ``begin``."""

    DIGEST = "sha256:" + "a" * 64
    OTHER = "sha256:" + "b" * 64

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="mhs-wp04-4f-settle-")
        self.addCleanup(tmp.cleanup)
        self.store = state_module.StateDir(Path(tmp.name), "mhs://localhost/safety")
        self.addCleanup(self.store.close)
        self.key = (DEVICE_ID, ulid())
        begin = {"op": "begin", "device_id": self.key[0], "command_id": self.key[1],
                 "input_digest": self.DIGEST, "capability_id": MOVE, "evidence_seq": 0}
        self.store.journal_path.write_text(json.dumps(begin) + "\n", encoding="utf-8")

    def receipt(self, status: str, digest: str, seq: int = 1) -> dict:
        return {"receipt_id": ulid(), "device_id": self.key[0], "command_id": self.key[1],
                "capability_id": MOVE, "input_digest": digest, "status": status,
                "evidence": {"seq": seq}}

    def test_settling(self) -> None:
        cases = {
            "own outcome": (self.receipt("completed", self.DIGEST), False),
            "own unknown": (self.receipt("unknown", self.DIGEST), False),
            "a rejected duplicate with other input": (self.receipt("rejected", self.OTHER), True),
            "a rejected identical duplicate (DEVICE.BUSY)": (self.receipt("rejected", self.DIGEST), True),
            "another action under the same id": (self.receipt("completed", self.OTHER), True),
            "a receipt before the begin": (self.receipt("completed", self.DIGEST, seq=0), True),
        }
        for name, (record, pending) in cases.items():
            with self.subTest(name):
                journal = self.store.load_journal([record])
                self.assertEqual(self.key in journal.pending, pending, journal.pending)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
