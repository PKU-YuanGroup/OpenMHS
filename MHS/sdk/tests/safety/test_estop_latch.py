"""E-stop latch semantics (plan 3.6, SAFE-040; findings SDK-01, DRV-03, SPEC-03).

Ports of the reviewer repros ``sdk-core/e12.py`` (hung bridge.estop),
``drv-verify/estop_probe.py`` (bridge.estop raising), ``sdk-core/e9.py``
(sessionless e-stop, default Bridge.estop) and the MISSED item on
``cap.motion.estop.v1`` routing.  The latch is server state set before any
bridge I/O; a stop path that does not confirm within its budget gives a
``failed`` receipt with ``MHS.SAFETY.SAFE_STATE_UNREACHED`` and keeps the latch.
"""

from __future__ import annotations

import threading
import time
import unittest

from mhs.errors import MHSError
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

from ._support import (
    DEVICE_ID,
    FIDELITY,
    Rpc,
    MOVE,
    READ,
    STOP,
    NativeStopBridge,
    StubBridge,
    conveyor,
    error_code,
    in_thread,
    open_session,
    release_retry,
    stub_capabilities,
    stub_server,
    ulid,
    wait_until,
)


class HungEstopTests(unittest.TestCase):
    """e12: the device does not answer the native e-stop (sleeps 3 s)."""

    def setUp(self) -> None:
        self.server, self.rpc, self.device, self.session = conveyor()
        self.release = threading.Event()

        def hung_estop(reason="", ctx=None):  # noqa: ANN001
            self.release.wait(3.0)
            return {}

        self.device.bridge.estop = hung_estop

    def tearDown(self) -> None:
        self.release.set()

    def test_hung_native_estop_latches_first_and_fails_truthfully(self) -> None:
        device_id = self.device.device_id
        started = time.monotonic()
        thread, holder = in_thread(lambda: self.rpc.raw(
            "mhs.safety.estop", session_id=self.session, reason="operator", deadline_ms=1000))
        self.assertTrue(wait_until(lambda: self.server._latched[device_id], timeout=1.0, step=0.0005))
        latched_after = time.monotonic() - started
        self.assertLess(latched_after, 0.05, f"latched only after {latched_after * 1000:.1f} ms")
        thread.join(2.0)
        self.assertFalse(thread.is_alive(), "mhs.safety.estop blocked behind the hung native e-stop")
        self.assertLess(holder["elapsed"], 1.0)
        response = holder["result"]
        self.assertIn("result", response, response)
        receipt = response["result"]
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertTrue(receipt["output"]["latched"])
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertEqual(receipt["capability_id"], "cap.internal.safety_estop.v1")
        self.assertTrue(self.server._latched[device_id])

        status = self.rpc("mhs.safety.status", deadline_ms=1000)
        self.assertTrue(status["estop"]["engaged"])

        command = self.rpc("mhs.command", session_id=self.session, capability_id="cap.world.step.v1",
                           input={"ticks": 10}, deadline_ms=2000)
        self.assertEqual(command["status"], "rejected", command)
        self.assertEqual(error_code(command), "MHS.SAFETY.ESTOP_ENGAGED", command)

    def test_short_caller_deadline_still_returns_a_receipt(self) -> None:
        response = self.rpc.raw("mhs.safety.estop", session_id=self.session, reason="x", deadline_ms=10)
        self.assertIn("result", response, response)
        self.assertEqual(response["result"]["status"], "failed")
        self.assertEqual(error_code(response["result"]), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(self.server._latched[self.device.device_id])


class RaisingEstopTests(unittest.TestCase):
    """estop_probe: bridge.estop raises an MHSError or any other exception."""

    def _run(self, exc: BaseException) -> None:
        class Raising(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                raise exc

        server, rpc, device, bridge = stub_server(Raising())
        session = open_session(rpc, device)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        self.assertTrue(receipt["output"]["latched"])
        self.assertTrue(server._latched[device.device_id])
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 3},
                    deadline_ms=1000)
        self.assertEqual(moved["status"], "rejected", moved)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(bridge.count(MOVE), 0)

    def test_mhs_error_from_bridge(self) -> None:
        self._run(MHSError("MHS.DEVICE.FAULTED", "boom"))

    def test_runtime_error_from_bridge(self) -> None:
        self._run(RuntimeError("boom"))

    def test_failed_native_estop_is_retried_in_the_background(self) -> None:
        class Flaky(NativeStopBridge):
            failures = 2

            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                if self.count("estop") <= self.failures:
                    raise RuntimeError("serial link down")
                return {"estop": "engaged"}

        server, rpc, device, bridge = stub_server(Flaky())
        session = open_session(rpc, device)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="test", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed")
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= 3, timeout=5.0),
                        f"native e-stop was not retried: {bridge.calls}")
        self.assertTrue(wait_until(
            lambda: server._estop_state[device.device_id].get("confirmed") is True, timeout=3.0))
        self.assertTrue(server._latched[device.device_id], "a background retry must keep the latch")
        confirmations = [
            record for record in server.export_evidence().get("receipts", [])
            if isinstance(record, dict)
            and record.get("capability_id") == "cap.internal.safety_estop.v1"
            and (record.get("output") or {}).get("confirms") == receipt["command_id"]
        ]
        self.assertEqual(len(confirmations), 1, "the late confirmation is not in the evidence log")
        self.assertEqual(confirmations[0]["status"], "completed")
        status = rpc("mhs.safety.status", deadline_ms=1000)
        self.assertTrue(status["estop"]["engaged"])


class _AlwaysFails(NativeStopBridge):
    def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
        self._record("estop")
        raise RuntimeError("serial link down")


class BackgroundRetryGenerationTests(unittest.TestCase):
    """A failed e-stop is retried in the background however soon after a reset it lands.

    Port of the verifier probes ``verify-WP-04/4a1/r1/probes/q_supervisor_race.py``
    and ``q_supervisor_race_gap2.py``: e-stop 1 fails and its background retry
    is backing off; the device is reset; e-stop 2 fails too while the retry
    thread of e-stop 1 is still winding down.  E-stop 2's receipt says
    ``retrying: true``, so its stop path must actually be retried.
    """

    def test_failed_estop_right_after_a_reset_is_retried(self) -> None:
        for gap in (0.0, 0.015):
            with self.subTest(gap_ms=int(gap * 1000)):
                bridge = _AlwaysFails()
                server, rpc, device, _ = stub_server(bridge)
                session = open_session(rpc, device)
                self.addCleanup(release_retry, server, rpc, device, session)
                first = rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
                self.assertEqual(first["status"], "failed", first)
                # The first retry runs after 0.25 s; the next one waits 0.5 s.
                self.assertTrue(wait_until(lambda: bridge.count("estop") >= 2, timeout=2.0), bridge.calls)
                time.sleep(0.05)
                reset = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
                self.assertEqual(reset["status"], "completed", reset)
                time.sleep(gap)
                second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
                self.assertEqual(second["status"], "failed", second)
                self.assertTrue(second["error"]["details"]["retrying"], second)
                calls = bridge.count("estop")
                self.assertTrue(
                    wait_until(lambda: bridge.count("estop") >= calls + 2, timeout=2.0),
                    f"the second e-stop was not retried: {bridge.count('estop')} native calls, "
                    f"{calls} when it was answered",
                )
                state = server._estop_state[device.device_id]
                self.assertTrue(state["supervisor"].is_alive())
                self.assertEqual(state.get("supervisor_generation"), state["generation"])
                self.assertTrue(server._latched[device.device_id])
                self.assertFalse(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"])


class _SecondCallSucceeds(NativeStopBridge):
    """The native e-stop answers only on its second call (the first background retry)."""

    def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
        self._record("estop")
        if self.count("estop") == 2:
            return {"estop": "engaged"}
        raise RuntimeError("serial link down")


def _confirmations_of(server: MHSServer, command_id: str) -> list[dict]:
    return [
        record for record in server.export_evidence().get("receipts", [])
        if isinstance(record, dict) and record.get("capability_id") == "cap.internal.safety_estop.v1"
        and command_id in ((record.get("output") or {}).get("confirms_command_ids") or [])
    ]


class ConfirmationRaceTests(unittest.TestCase):
    """A background confirmation is tied to the attempt it confirms (MERGE-B fix round).

    Ports of ``verify-WP-04/4a1/r2/probes/s_confirm_race.py`` and
    ``s_confirm_race_nodelay.py``: e-stop 1 fails and its background retry
    succeeds; while the retry thread confirms it, e-stop 2 starts a new attempt
    whose native stop fails.  Before the fix the old confirmation set
    ``confirmed: true`` over e-stop 2's failure (``mhs.safety.status`` reported
    a confirmed stop after a ``SAFE_STATE_UNREACHED`` receipt), and the retry
    thread then ended, so e-stop 2 (``retrying: true``) was never retried.
    """

    def _server(self, bridge: NativeStopBridge):
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        self.addCleanup(release_retry, server, rpc, device, session)
        return server, rpc, device, session

    def test_a_newer_failed_estop_is_not_confirmed_by_an_older_attempt(self) -> None:
        bridge = _SecondCallSucceeds()
        server, rpc, device, session = self._server(bridge)
        entered, gate = threading.Event(), threading.Event()
        self.addCleanup(gate.set)
        original = server._confirm_estop

        def gated(*args, **kwargs):  # noqa: ANN002, ANN003
            entered.set()   # the retry succeeded; hold its confirmation
            gate.wait(5.0)
            return original(*args, **kwargs)

        server._confirm_estop = gated
        first = rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        self.assertEqual(first["status"], "failed", first)
        self.assertTrue(entered.wait(3.0), f"the background retry never succeeded: {bridge.calls}")
        second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
        self.assertEqual(second["status"], "failed", second)
        self.assertEqual(error_code(second), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertTrue(second["error"]["details"]["retrying"], second)
        calls = bridge.count("estop")
        gate.set()
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= calls + 1, timeout=3.0),
                        f"the second e-stop was never retried: {bridge.calls}")
        state = server._estop_state[device.device_id]
        self.assertIsNot(state.get("confirmed"), True)
        self.assertIs(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"], False)
        self.assertEqual(_confirmations_of(server, second["command_id"]), [])
        self.assertIn(second["command_id"], state.get("unconfirmed") or [])
        self.assertTrue(server._latched[device.device_id])
        self.assertTrue(state["supervisor"].is_alive())

    def test_an_estop_during_a_slow_confirmation_read_is_retried(self) -> None:
        class SlowConfirmRead(_SecondCallSucceeds):
            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                # The first state read after the retry succeeded is the
                # confirmation receipt's: make it slow (0.3 s).
                if self.count("estop") >= 2 and self.count("slow_read") == 0:
                    self._record("slow_read")
                    time.sleep(0.3)
                return dict(self.state)

        bridge = SlowConfirmRead()
        server, rpc, device, session = self._server(bridge)
        first = rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        self.assertEqual(first["status"], "failed", first)
        self.assertTrue(wait_until(lambda: bridge.count("slow_read") >= 1, timeout=3.0), bridge.calls)
        second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
        self.assertEqual(second["status"], "failed", second)
        self.assertTrue(second["error"]["details"]["retrying"], second)
        calls = bridge.count("estop")
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= calls + 1, timeout=3.0),
                        f"the second e-stop was never retried: {bridge.calls}")
        self.assertIs(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"], False)
        self.assertTrue(server._estop_state[device.device_id]["supervisor"].is_alive())
        # The older attempt really did succeed: its receipt confirms e-stop 1 only.
        self.assertTrue(wait_until(lambda: len(_confirmations_of(server, first["command_id"])) == 1,
                                   timeout=2.0))
        self.assertEqual(_confirmations_of(server, second["command_id"]), [])

    def test_the_confirmation_receipt_read_is_bounded(self) -> None:
        release = threading.Event()
        self.addCleanup(release.set)

        class HungConfirmRead(_SecondCallSucceeds):
            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                # The confirmation receipt's state read (the first after the
                # retry succeeded) hangs.
                if self.count("estop") >= 2 and self.count("hung_read") == 0:
                    self._record("hung_read")
                    release.wait(3.0)
                return dict(self.state)

        bridge = HungConfirmRead()
        server, rpc, device, session = self._server(bridge)
        rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        self.assertTrue(wait_until(lambda: bridge.count("hung_read") >= 1, timeout=3.0), bridge.calls)
        started = time.monotonic()
        self.assertTrue(wait_until(
            lambda: server._estop_state[device.device_id].get("confirmed") is True, timeout=1.0),
            "the confirmation waited on a hung state read")
        self.assertLess(time.monotonic() - started, 1.0)

    def test_back_to_back_estops_never_report_a_false_confirmation(self) -> None:
        class FailsAfterSecond(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                if self.count("estop") == 2:
                    return {"estop": "engaged"}
                raise RuntimeError("serial link down")

        for trial in range(3):
            with self.subTest(trial=trial):
                bridge = FailsAfterSecond()
                server, rpc, device, session = self._server(bridge)
                rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
                state = server._estop_state[device.device_id]

                def retry_done() -> bool:
                    # The retry worker can call the bridge before its new
                    # attempt is published under the server lock. Read the
                    # attempt and call count under that same lock, so an old
                    # completed attempt cannot satisfy the new call count.
                    with server._lock:
                        attempt = state.get("attempt")
                        return bridge.count("estop") >= 2 and attempt is not None and attempt.done.is_set()

                self.assertTrue(wait_until(retry_done, timeout=3.0, step=0.0005))
                second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
                self.assertEqual(second["status"], "failed", second)
                calls = bridge.count("estop")
                self.assertTrue(wait_until(lambda: bridge.count("estop") >= calls + 1, timeout=3.0),
                                f"lost retry: {bridge.calls}")
                self.assertIs(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["confirmed"], False)


class ResetHoldTests(unittest.TestCase):
    """An e-stop pressed while ``bridge.reset()`` runs lifts the retry hold (MERGE-B fix round).

    Port of ``verify-WP-04/4a1/r2/probes/s_hold_new_estop.py``: background
    retries wait for a reset inside ``bridge.reset()`` (it may release the
    latch); a reset during which a new e-stop was engaged is refused anyway,
    so that e-stop's failed stop path must be retried at once, not after
    ``bridge.reset()`` returns.
    """

    def test_a_new_estop_during_a_slow_reset_is_retried_before_the_reset_returns(self) -> None:
        entered, release = threading.Event(), threading.Event()

        class SlowReset(_AlwaysFails):
            def reset(self, ctx=None):  # noqa: ANN001
                self._record("reset")
                entered.set()
                release.wait(3.0)
                return {"reset": True}

        bridge = SlowReset()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        self.addCleanup(release_retry, server, rpc, device, session)
        self.addCleanup(release.set)
        rpc("mhs.safety.estop", session_id=session, reason="first", deadline_ms=1000)
        state = server._estop_state[device.device_id]
        self.assertTrue(wait_until(lambda: not _stop_path_running(state), timeout=2.0))
        thread, holder = in_thread(lambda: rpc("mhs.safety.reset", session_id=session, deadline_ms=5000))
        self.assertTrue(entered.wait(2.0), f"the reset never reached bridge.reset(): {holder}")
        second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
        self.assertEqual(second["status"], "failed", second)
        calls = bridge.count("estop")
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= calls + 1, timeout=1.5),
                        f"no retry while bridge.reset() ran: {bridge.calls}")
        self.assertFalse(release.is_set())
        release.set()
        thread.join(3.0)
        receipt = holder["result"]
        self.assertEqual(error_code(receipt), "MHS.SAFETY.RESET_REFUSED", receipt)
        self.assertTrue(server._latched[device.device_id])


def _stop_path_running(state) -> bool:  # noqa: ANN001
    attempt = state.get("attempt")
    return attempt is not None and not attempt.done.is_set()


class ReassertPendingAttemptTests(unittest.TestCase):
    """A re-asserted stop path never hides an older native e-stop still in flight (MERGE-B fix round).

    WP-04 4a1 verifier minor: ``_reassert_estop`` (after ``estop_during_reset``)
    replaced the current attempt while it was still pending, so a later reset
    passed the ``stop_path_pending`` check with the older native e-stop still
    running; it could land after the reset.
    """

    def test_a_reset_waits_for_every_native_estop_in_flight(self) -> None:
        in_reset, release_reset, hang = threading.Event(), threading.Event(), threading.Event()

        class Bridge2(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                if self.count("estop") == 2:
                    hang.wait(5.0)   # the e-stop pressed during the reset hangs
                return {"estop": "engaged"}

            def reset(self, ctx=None):  # noqa: ANN001
                self._record("reset")
                in_reset.set()
                release_reset.wait(3.0)
                return {"reset": True}

        bridge = Bridge2()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        self.addCleanup(release_retry, server, rpc, device, session)
        self.addCleanup(hang.set)
        self.addCleanup(release_reset.set)
        self.assertEqual(rpc("mhs.safety.estop", session_id=session, reason="first",
                             deadline_ms=1000)["status"], "completed")
        thread, holder = in_thread(lambda: rpc("mhs.safety.reset", session_id=session, deadline_ms=5000))
        self.assertTrue(in_reset.wait(2.0))
        second = rpc("mhs.safety.estop", session_id=session, reason="second", deadline_ms=1000)
        self.assertEqual(second["status"], "failed", second)   # its native stop hangs
        release_reset.set()
        thread.join(3.0)
        refused = holder["result"]
        self.assertEqual((refused["error"]["details"] or {}).get("reason"), "estop_during_reset", refused)
        self.assertEqual(refused["status"], "failed", refused)  # bridge.reset() ran
        self.assertTrue(wait_until(lambda: bridge.count("estop") >= 3, timeout=2.0), bridge.calls)
        # The second native e-stop is still in flight: no reset may pass.
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["details"]["reason"], "stop_path_pending", receipt)
        self.assertTrue(server._latched[device.device_id])
        hang.set()
        self.assertTrue(wait_until(lambda: rpc("mhs.safety.reset", session_id=session,
                                               deadline_ms=1000)["status"] == "completed", timeout=3.0))


class SafeStateWhileNativeHangsTests(unittest.TestCase):
    """safe_state.achieved_by is an independent path to the safe state.

    Verifier finding (4a1 r1): with a hung native e-stop the software
    safe-state actions never ran until the native call returned.  They now run
    once the device's e-stop budget is spent, while the native call is pending.
    """

    def test_safe_state_actions_run_while_the_native_estop_hangs(self) -> None:
        release = threading.Event()
        self.addCleanup(release.set)

        class Hung(NativeStopBridge):
            def estop(self, reason: str = "", ctx=None):  # noqa: ANN001
                self._record("estop")
                release.wait(3.0)
                self._record("estop_returned")
                return {"estop": "engaged"}

        bridge = Hung()
        server, rpc, device, _ = stub_server(bridge)  # latency_ms 50, achieved_by [STOP]
        session = open_session(rpc, device)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["details"]["reason"], "timeout")
        self.assertTrue(wait_until(lambda: bridge.count(STOP) == 1, timeout=1.0),
                        f"no safe-state action ran while the native e-stop hung: {bridge.calls}")
        self.assertEqual(bridge.count("estop_returned"), 0, "the native e-stop is still pending")
        self.assertFalse(server._estop_state[device.device_id]["confirmed"])
        release.set()
        self.assertTrue(wait_until(
            lambda: server._estop_state[device.device_id]["confirmed"] is True, timeout=3.0))
        self.assertEqual(bridge.count(STOP), 1, bridge.calls)
        self.assertTrue(server._latched[device.device_id])

    def test_order_is_native_first_when_the_native_estop_answers(self) -> None:
        bridge = NativeStopBridge()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual([c for c in bridge.calls if c in ("estop", STOP)], ["estop", STOP])


class SessionlessEstopTests(unittest.TestCase):
    """e9: e-stop must not depend on a live session."""

    def test_estop_with_expired_session(self) -> None:
        server, rpc, device, _session = conveyor()
        expired = rpc("mhs.session.open", mode="simulated", ttl_s=1)["session_id"]
        server._sessions[expired].expires_at = time.time() - 1
        receipt = rpc("mhs.safety.estop", session_id=expired, reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(server._latched[device.device_id])

    def test_estop_without_any_session(self) -> None:
        server, rpc, device, _session = conveyor()
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["session_id"].startswith("mhs_s_"))
        self.assertTrue(server._latched[device.device_id])

    def test_estop_with_unknown_session(self) -> None:
        server, rpc, device, _session = conveyor()
        receipt = rpc("mhs.safety.estop", session_id="mhs_s_doesnotexist", device_id=device.device_id,
                      reason="x", deadline_ms=1000)
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_malformed_command_id_does_not_refuse_the_estop(self) -> None:
        server, rpc, device, session = conveyor()
        receipt = rpc("mhs.safety.estop", session_id=session, command_id="not-a-ulid", reason="x",
                      deadline_ms=1000)
        self.assertTrue(server._latched[device.device_id])
        self.assertNotEqual(receipt["command_id"], "not-a-ulid")

    def test_estop_replay_while_latched_returns_the_retained_receipt(self) -> None:
        server, rpc, device, session = conveyor()
        command_id = ulid()
        first = rpc("mhs.safety.estop", session_id=session, command_id=command_id, reason="x",
                    deadline_ms=1000)
        again = rpc("mhs.safety.estop", session_id=session, command_id=command_id, reason="x",
                    deadline_ms=1000)
        self.assertEqual(again["receipt_id"], first["receipt_id"])
        self.assertTrue(again["replayed"])

    def test_estop_of_a_device_outside_the_session(self) -> None:
        first_bridge, second_bridge = NativeStopBridge("mhs://localhost/safety/a"), NativeStopBridge(
            "mhs://localhost/safety/b")
        devices = []
        for bridge in (first_bridge, second_bridge):
            devices.append(Device(
                bridge.device_id, mode="simulated",
                resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
                capabilities=stub_capabilities(),
                safety=SafetyEnvelope(risk_class="R1",
                                      safe_state={"description": "stopped", "achieved_by": [STOP]}),
                fidelity=dict(FIDELITY), bridge=bridge,
            ))
        server = MHSServer("mhs://localhost/safety", devices, log_ready=False)
        rpc = Rpc(server)
        rpc("mhs.hello", protocol_versions=["1.0"])
        session = rpc("mhs.session.open", device_ids=[devices[0].device_id], mode="simulated",
                      capabilities=[READ])["session_id"]
        receipt = rpc("mhs.safety.estop", session_id=session, device_id=devices[1].device_id,
                      reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["device_id"], devices[1].device_id)
        self.assertEqual(second_bridge.count("estop"), 1)
        self.assertEqual(first_bridge.count("estop"), 0)
        self.assertTrue(server._latched[devices[1].device_id])
        self.assertFalse(server._latched[devices[0].device_id])
        # A stop that names no device is not refused on a multi-device endpoint: it stops every device
        # (CORE-076; WP-09 follow-up F6; tests/safety/test_estop_failsafe.py has the rest of the rule).
        everything = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(everything["x-vendor"]["estop"]["scope"], "all_devices")
        self.assertTrue(server._latched[devices[0].device_id])
        self.assertEqual(first_bridge.count("estop"), 1)


class DefaultEstopTests(unittest.TestCase):
    """e9: a bridge that does not implement estop()."""

    def test_default_estop_on_simulated_device_is_software_only(self) -> None:
        server, rpc, device, bridge = stub_server(StubBridge())
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only")
        self.assertTrue(receipt["output"]["latched"])
        self.assertEqual(bridge.count(STOP), 1, "the declared safe-state action did not run")
        self.assertTrue(receipt["output"]["safe_state_achieved"])

    def test_default_estop_on_hardware_without_a_stop_path_is_unreached(self) -> None:
        safety = SafetyEnvelope(risk_class="R2", estop={"kind": "both", "latching": True, "latency_ms": 50},
                                safe_state={"description": "none declared", "achieved_by": []})
        server, rpc, device, bridge = stub_server(StubBridge(), mode="hardware", safety=safety)
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertEqual(receipt["output"]["estop"], "software_only")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertTrue(server._latched[device.device_id])

    def test_native_estop_is_reported_engaged(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertEqual(bridge.count("estop"), 1)
        effects = receipt["effects"]
        self.assertEqual(effects[0]["kind"], "safety.estop")
        self.assertFalse(effects[0]["reversible"])


class SafeStateTests(unittest.TestCase):
    """safe_state.achieved_by: validated at construction, all must succeed."""

    def test_unknown_achieved_by_id_is_refused_on_hardware(self) -> None:
        safety = SafetyEnvelope(risk_class="R1", safe_state={"description": "x",
                                                             "achieved_by": ["cap.motion.stpo.v1"]})
        with self.assertRaises(ValueError) as caught:
            stub_server(NativeStopBridge(), mode="hardware", safety=safety)
        self.assertIn("cap.motion.stpo.v1", str(caught.exception))

    def test_unknown_achieved_by_id_on_a_simulator_warns_and_is_unreached(self) -> None:
        safety = SafetyEnvelope(risk_class="R1", safe_state={"description": "x",
                                                             "achieved_by": ["cap.motion.stpo.v1"]})
        # One MHSStrictWarning (a RuntimeWarning) per strict-mode finding since
        # WP-04 4b; the achieved_by one names the unbound id.
        with self.assertWarnsRegex(RuntimeWarning, r"cap\.motion\.stpo\.v1") as caught:
            server, rpc, device, bridge = stub_server(NativeStopBridge(), safety=safety)
        self.assertIn("cap.motion.stpo.v1", str(caught.warning))
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        details = receipt["error"]["details"]
        self.assertEqual(details["reason"], "safe_state_unbound")
        self.assertFalse(details["retrying"], "a manifest error is not retried")
        self.assertTrue(server._latched[device.device_id])

    def test_every_safe_state_action_must_succeed(self) -> None:
        pump = Capability("x-cap.test.pump_off.v1", "axis", input_schema={"type": "object"})
        safety = SafetyEnvelope(risk_class="R1", estop={"kind": "software", "latching": True},
                                safe_state={"description": "axis stopped, pump off",
                                            "achieved_by": [STOP, "x-cap.test.pump_off.v1"]})
        bridge = NativeStopBridge()
        bridge.fail_actions.add("x-cap.test.pump_off.v1")
        server, rpc, device, _ = stub_server(bridge, safety=safety,
                                             capabilities=stub_capabilities(extra=[pump]))
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(bridge.count(STOP), 1)
        self.assertEqual(bridge.count("x-cap.test.pump_off.v1"), 1)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        self.assertIn("x-cap.test.pump_off.v1", str(receipt["error"].get("details")))
        self.assertTrue(server._latched[device.device_id])


class LatchScopeTests(unittest.TestCase):
    """While latched every effectful command is refused; reads stay available."""

    def test_effectful_refused_read_allowed(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1},
                    deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertEqual(bridge.count(MOVE), 0)
        read = rpc("mhs.command", session_id=session, capability_id=READ, input={}, deadline_ms=1000)
        self.assertEqual(read["status"], "completed", read)

    def test_latch_precedes_schema_validation(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": "far"},
                    deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")

    def test_estop_during_the_restore_rollback_read_refuses_the_restore(self) -> None:
        """Port of ``verify-WP-04/4a1/r1/probes/q_restore_race.py``: the latch is
        re-checked after the slow rollback snapshot, right before bridge.restore()."""
        server, rpc, device, session = conveyor()
        snapshot = rpc("mhs.snapshot", session_id=session, deadline_ms=2000)
        bridge = device.bridge
        original_snapshot, original_restore = bridge.snapshot, bridge.restore
        entered = threading.Event()
        restored: list[bool] = []

        def slow_snapshot(*args, **kwargs):  # noqa: ANN002, ANN003
            entered.set()
            time.sleep(0.2)
            return original_snapshot(*args, **kwargs)

        def recording_restore(state, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            restored.append(bool(server._latched[device.device_id]))
            return original_restore(state, *args, **kwargs)

        bridge.snapshot = slow_snapshot
        bridge.restore = recording_restore
        thread, holder = in_thread(lambda: rpc(
            "mhs.restore", session_id=session, snapshot=snapshot, deadline_ms=3000))
        self.assertTrue(entered.wait(2.0), "the restore never read its rollback snapshot")
        estop = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertTrue(estop["output"]["latched"])
        thread.join(3.0)
        receipt = holder["result"]
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ESTOP_ENGAGED", receipt)
        self.assertEqual(restored, [], "bridge.restore() ran on a latched device")
        self.assertTrue(server._latched[device.device_id])


    def test_estop_during_bridge_restore_reasserts_the_stop_path(self) -> None:
        """Port of ``verify-WP-04/4a1/r2/probes/s_restore_reassert.py``: an e-stop
        that lands while ``bridge.restore()`` runs is followed by the stop path
        again once the restore returned (the restore may rewrite the stopped state)."""
        server, rpc, device, session = conveyor()
        snapshot = rpc("mhs.snapshot", session_id=session, deadline_ms=2000)
        bridge = device.bridge
        original_restore, original_estop = bridge.restore, bridge.estop
        events: list[str] = []
        entered = threading.Event()

        def slow_restore(state, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
            events.append("restore_enter")
            entered.set()
            time.sleep(0.3)
            result = original_restore(state, *args, **kwargs)
            events.append("restore_exit")
            return result

        def recording_estop(*args, **kwargs):  # noqa: ANN002, ANN003
            events.append("estop")
            return original_estop(*args, **kwargs)

        bridge.restore = slow_restore
        bridge.estop = recording_estop
        thread, _holder = in_thread(lambda: rpc.raw(
            "mhs.restore", session_id=session, snapshot=snapshot, deadline_ms=3000))
        self.assertTrue(entered.wait(2.0))
        estop = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertTrue(estop["output"]["latched"])
        thread.join(3.0)
        self.assertTrue(wait_until(lambda: events.count("estop") >= 2, timeout=2.0), events)
        exit_at = events.index("restore_exit")
        self.assertIn("estop", events[:exit_at], events)
        self.assertIn("estop", events[exit_at + 1:], f"no stop path after the restore: {events}")
        self.assertTrue(server._latched[device.device_id])


class MotionEstopCapabilityTests(unittest.TestCase):
    """SAFE-040: cap.motion.estop.v1 engages the same latch as mhs.safety.estop."""

    def test_command_estop_routes_to_the_latch(self) -> None:
        estop_cap = Capability(
            "cap.motion.estop.v1", "axis",
            input_schema={"type": "object", "properties": {"reason": {"type": "string"}},
                          "required": ["reason"]},
            exclusive=True,
        )
        safety = SafetyEnvelope(risk_class="R1", estop={"kind": "software", "latching": True},
                                requires_permit=["cap.motion.*"],
                                safe_state={"description": "axis stopped", "achieved_by": [STOP]})
        bridge = NativeStopBridge()
        server, rpc, device, _ = stub_server(bridge, safety=safety,
                                             capabilities=stub_capabilities(extra=[estop_cap]))
        session = open_session(rpc, device)
        long_thread, holder = in_thread(lambda: rpc(
            "mhs.command", session_id=session, capability_id="x-cap.test.long.v1",
            input={"ms": 2000}, deadline_ms=5000))
        self.assertTrue(wait_until(lambda: bridge.state["moving"], timeout=2.0))
        receipt = rpc("mhs.command", session_id=session, capability_id="cap.motion.estop.v1",
                      input={"reason": "operator"}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["capability_id"], "cap.motion.estop.v1")
        self.assertTrue(receipt["output"]["engaged"])
        self.assertTrue(receipt["output"]["latched"])
        self.assertTrue(server._latched[device.device_id])
        self.assertEqual(bridge.count("estop"), 1, "the routed e-stop must use the same native stop")
        long_thread.join(3.0)
        self.assertEqual(holder["result"]["status"], "cancelled", holder)
        moved = rpc("mhs.command", session_id=session, capability_id=MOVE, input={"pos": 1},
                    permit_id="none", deadline_ms=1000)
        self.assertEqual(error_code(moved), "MHS.SAFETY.ESTOP_ENGAGED")
        self.assertTrue(rpc("mhs.safety.status", deadline_ms=1000)["estop"]["engaged"])

    def test_bound_motion_estop_is_the_native_stop_for_safety_estop(self) -> None:
        estop_cap = Capability(
            "cap.motion.estop.v1", "axis",
            input_schema={"type": "object", "properties": {"reason": {"type": "string"}}},
        )
        bridge = StubBridge()  # no estop() override: the binding is the native stop
        server, rpc, device, _ = stub_server(bridge, capabilities=stub_capabilities(extra=[estop_cap]))
        receipt = rpc("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "engaged")
        self.assertEqual(bridge.count("cap.motion.estop.v1"), 1)

    def test_command_estop_is_never_refused_by_command_gates(self) -> None:
        """cap.motion.estop.v1 via mhs.command latches before session, id and deadline checks."""
        estop_cap = Capability(
            "cap.motion.estop.v1", "axis",
            input_schema={"type": "object", "properties": {"reason": {"type": "string"}}},
        )
        cases = {
            "unknown session": {"session_id": "mhs_s_doesnotexist", "deadline_ms": 1000},
            "expired session": {"expire": True, "deadline_ms": 1000},
            "no session": {"deadline_ms": 1000},
            "malformed command_id": {"live": True, "command_id": "not-a-ulid", "deadline_ms": 1000},
            "input not an object": {"live": True, "input": ["stop"], "deadline_ms": 1000},
            "no deadline_ms": {"live": True},
            "string deadline_ms": {"live": True, "deadline_ms": "500"},
        }
        for label, case in cases.items():
            with self.subTest(label):
                bridge = NativeStopBridge()
                server, rpc, device, _ = stub_server(
                    bridge, capabilities=stub_capabilities(extra=[estop_cap]))
                params = {key: value for key, value in case.items() if key not in ("expire", "live")}
                if case.get("live") or case.get("expire"):
                    params["session_id"] = open_session(rpc, device)
                if case.get("expire"):
                    server._sessions[params["session_id"]].expires_at = time.time() - 1
                params.setdefault("input", {"reason": "operator"})
                response = rpc.raw("mhs.command", capability_id="cap.motion.estop.v1", **params)
                self.assertTrue(server._latched[device.device_id], f"{label}: not latched: {response}")
                self.assertIn("result", response, response)
                self.assertEqual(response["result"]["capability_id"], "cap.motion.estop.v1")
                self.assertTrue(response["result"]["output"]["latched"])
                self.assertEqual(bridge.count("estop"), 1)


class DeclaredVerbTests(unittest.TestCase):
    """The latch exempts a read only when the catalogue says the class is a read.

    Port of the verifier probe ``verify-WP-04/4a1/probes/p_verb.py``: a binding
    that labels an effectful class ``verb='read'`` must not run while latched.
    """

    def _latched(self, capability: Capability):
        caps = [c for c in stub_capabilities() if c.capability_id != capability.capability_id]
        caps.append(capability)
        bridge = NativeStopBridge()
        server, rpc, device, _ = stub_server(bridge, capabilities=caps)
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        return server, rpc, device, bridge, session

    def test_effectful_class_declared_read_is_refused_while_latched(self) -> None:
        for capability_id, payload in (
            (MOVE, {"pos": 7}),                       # not catalogued
            ("cap.motion.home.v1", {}),               # catalogued verb "invoke"
            ("cap.thermal.setpoint.v1", {}),          # catalogued verb "write"
        ):
            with self.subTest(capability_id):
                capability = Capability(capability_id, "axis", input_schema={"type": "object"}, verb="read")
                server, rpc, device, bridge, session = self._latched(capability)
                receipt = rpc("mhs.command", session_id=session, capability_id=capability_id,
                              input=payload, deadline_ms=1000)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.SAFETY.ESTOP_ENGAGED")
                self.assertEqual(bridge.count(capability_id), 0)
                self.assertEqual(bridge.state["pos"], 0)

    def test_catalogued_read_stays_callable(self) -> None:
        capability = Capability(READ, "axis", input_schema={"type": "object"}, verb="read")
        server, rpc, device, bridge, session = self._latched(capability)
        receipt = rpc("mhs.command", session_id=session, capability_id=READ, input={}, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_extension_declared_read_is_latched(self) -> None:
        """Verifier finding (4a1 r1): the catalogue cannot confirm an extension's
        verb, so an extension id never counts as a read for the latch (fail closed)."""
        for capability_id in ("x-cap.test.level.v1", "cap.x.test.level.v1"):
            with self.subTest(capability_id):
                capability = Capability(capability_id, "axis", input_schema={"type": "object"}, verb="read")
                server, rpc, device, bridge, session = self._latched(capability)
                receipt = rpc("mhs.command", session_id=session, capability_id=capability_id,
                              input={}, deadline_ms=1000)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.SAFETY.ESTOP_ENGAGED")
                self.assertEqual(bridge.count(capability_id), 0)

    def test_catalogued_read_class_declared_invoke_is_latched(self) -> None:
        capability = Capability(READ, "axis", input_schema={"type": "object"}, verb="invoke")
        server, rpc, device, bridge, session = self._latched(capability)
        receipt = rpc("mhs.command", session_id=session, capability_id=READ, input={}, deadline_ms=1000)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ESTOP_ENGAGED")


class BoundedReceiptTests(unittest.TestCase):
    """The e-stop answers within its deadline even when bridge.read() hangs.

    Port of the verifier probe ``verify-WP-04/4a1/probes/p_hung_read.py``: the
    native stop answers at once, but the state read for the receipt blocks (a
    serial driver whose read waits on the lock a running call holds).
    """

    def test_estop_answers_within_its_deadline_when_read_hangs(self) -> None:
        release = threading.Event()

        class HungRead(NativeStopBridge):
            hang = False

            def read(self, resource_id, fields=None, ctx=None):  # noqa: ANN001
                if self.hang:
                    release.wait(3.0)
                return dict(self.state)

        bridge = HungRead()
        server, rpc, device, _ = stub_server(bridge)
        session = open_session(rpc, device)
        bridge.hang = True
        try:
            started = time.monotonic()
            response = rpc.raw("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
            elapsed = time.monotonic() - started
        finally:
            release.set()
        self.assertLess(elapsed, 1.0, f"e-stop answered after {elapsed * 1000:.0f} ms (deadline 1000 ms)")
        receipt = response["result"]
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(receipt["output"]["latched"])
        self.assertTrue(server._latched[device.device_id])


class EstopGateTests(unittest.TestCase):
    """Generic protocol gates never refuse an e-stop without latching.

    Ports of the verifier probes ``p_params.py`` and ``p_hello.py``.
    """

    def test_invalid_or_missing_deadline_still_latches(self) -> None:
        for label, extra in (
            ("missing", {}),
            ("string", {"deadline_ms": "500"}),
            ("zero", {"deadline_ms": 0}),
            ("negative", {"deadline_ms": -5}),
            ("bool", {"deadline_ms": True}),
            ("over the maximum", {"deadline_ms": 10 ** 9}),
        ):
            with self.subTest(label):
                server, rpc, device, bridge = stub_server(NativeStopBridge())
                response = rpc.raw("mhs.safety.estop", reason="x", **extra)
                self.assertIn("result", response, response)
                self.assertEqual(response["result"]["status"], "completed", response)
                self.assertTrue(server._latched[device.device_id])
                self.assertEqual(bridge.count("estop"), 1)

    def test_estop_before_hello_latches(self) -> None:
        bridge = NativeStopBridge()
        device = Device(
            DEVICE_ID, "x", mode="simulated",
            resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
            capabilities=stub_capabilities(),
            safety=SafetyEnvelope(risk_class="R1", safe_state={"description": "x", "achieved_by": [STOP]}),
            fidelity=dict(FIDELITY), bridge=bridge,
        )
        server = MHSServer("mhs://localhost/safety", [device], log_ready=False)
        rpc = Rpc(server)
        response = rpc.raw("mhs.safety.estop", reason="x", deadline_ms=1000)
        self.assertIn("result", response, response)
        self.assertTrue(server._latched[device.device_id])
        refused = rpc.raw("mhs.devices.list")
        self.assertEqual(error_code(refused), "MHS.PROTOCOL.INVALID_REQUEST",
                         "other methods still require mhs.hello")


class NonFiniteEstopTests(unittest.TestCase):
    """NaN / Infinity in an e-stop's params never refuse it (plan 3.6).

    Port of the verifier probe ``verify-WP-04/4a2/repros/estop_inf.py``: the
    4a2 NaN gate answered ``MHS.PROTOCOL.PARSE_ERROR`` before the e-stop
    exemption, so the device was not latched.  Every other method is still
    refused (``test_endpoint_methods.NotificationTests``).
    """

    VALUES = (float("inf"), -float("inf"), float("nan"))

    def _estop_cap(self) -> Capability:
        return Capability(
            "cap.motion.estop.v1", "axis",
            input_schema={"type": "object", "properties": {"reason": {"type": "string"}}},
        )

    def test_safety_estop_with_a_non_finite_deadline_latches(self) -> None:
        for value in self.VALUES:
            with self.subTest(value=value):
                server, rpc, device, bridge = stub_server(NativeStopBridge())
                with self.assertLogs("mhs.server", level="WARNING") as logs:
                    response = rpc.raw("mhs.safety.estop", reason="x", deadline_ms=value)
                self.assertTrue(any("replaced by null" in line for line in logs.output), logs.output)
                self.assertIn("result", response, response)
                self.assertEqual(response["result"]["status"], "completed", response)
                self.assertTrue(response["result"]["output"]["latched"])
                self.assertTrue(server._latched[device.device_id])
                self.assertEqual(bridge.count("estop"), 1)

    def test_safety_estop_with_a_non_finite_extra_param_latches(self) -> None:
        for value in self.VALUES:
            with self.subTest(value=value):
                server, rpc, device, bridge = stub_server(NativeStopBridge())
                with self.assertLogs("mhs.server", level="WARNING"):
                    response = rpc.raw("mhs.safety.estop", reason="x", deadline_ms=1000,
                                       extra={"v": [1, value]})
                self.assertIn("result", response, response)
                self.assertTrue(server._latched[device.device_id])
                self.assertEqual(bridge.count("estop"), 1)
                self.assertTrue(rpc("mhs.evidence.verify")["valid"])

    def test_command_estop_with_non_finite_values_latches(self) -> None:
        for value in self.VALUES:
            with self.subTest(value=value):
                bridge = NativeStopBridge()
                server, rpc, device, _ = stub_server(
                    bridge, capabilities=stub_capabilities(extra=[self._estop_cap()]))
                session = open_session(rpc, device)
                with self.assertLogs("mhs.server", level="WARNING"):
                    response = rpc.raw("mhs.command", session_id=session,
                                       capability_id="cap.motion.estop.v1",
                                       input={"reason": "operator", "speed": value}, deadline_ms=value)
                self.assertIn("result", response, response)
                self.assertEqual(response["result"]["capability_id"], "cap.motion.estop.v1")
                self.assertTrue(response["result"]["output"]["latched"])
                self.assertTrue(server._latched[device.device_id])
                self.assertEqual(bridge.count("estop"), 1)
                self.assertTrue(rpc("mhs.evidence.verify")["valid"])
                moved = rpc.raw("mhs.command", session_id=session, capability_id=MOVE,
                                input={"pos": 1}, deadline_ms=1000)
                self.assertEqual(error_code(moved["result"]), "MHS.SAFETY.ESTOP_ENGAGED", moved)

    def test_estop_notification_with_a_non_finite_deadline_latches(self) -> None:
        server, rpc, device, bridge = stub_server(NativeStopBridge())
        with self.assertLogs("mhs.server", level="WARNING"):
            result = server.handle({"jsonrpc": "2.0", "method": "mhs.safety.estop",
                                    "params": {"reason": "x", "deadline_ms": float("nan")}})
        self.assertIsNone(result)
        self.assertTrue(server._latched[device.device_id])


if __name__ == "__main__":
    unittest.main()
