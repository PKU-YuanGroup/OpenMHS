"""Event-driven stock-server regressions for late native mutation and recovery."""
from __future__ import annotations

import asyncio
import copy
import concurrent.futures
import threading
import unittest
from mhs import signals
from mhs.bridge.base import BridgeContext
from mhs.driver import Action, Field, PythonObjectDriver, close_server
from tests.driver.support import serve

CAP = "x-cap.retention.set.v1"
FIDELITY = {"engine": "controlled Python native", "fidelity_level": "F0",
            "determinism": {"kind": "none", "seed_control": "none"}, "timestep_ms": 0,
            "realtime_factor": 0, "clock": "lockstep", "reset": "partial", "snapshot_restore": False,
            "gaps": ["No upstream, external process, physical device or real transport"]}


class Parameter:
    def __init__(self):
        self.value = 0.
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()

    def set(self, value):
        self.calls.append(("enter", value))
        self.entered.set()
        if not self.release.wait(3):
            raise RuntimeError("fixture release missing")
        self.value = value
        self.calls.append(("effect", value))
        self.finished.set()
        return value

    def get(self):
        return self.value


class Native:
    def __init__(self):
        self.parameter = Parameter()
        self.events = []
        self.off_entered, self.off_release = threading.Event(), threading.Event()
        self.off_release.set()
        self.reset_entered, self.reset_release = threading.Event(), threading.Event()
        self.reset_release.set()
        self.closed = threading.Event()

    def off(self):
        self.events.append("off")
        self.off_entered.set()
        if not self.off_release.wait(3):
            raise RuntimeError("fixture stop release missing")
        self.parameter.value = 0.

    def reset_fault(self):
        self.events.append("reset")
        self.reset_entered.set()
        if not self.reset_release.wait(3):
            raise RuntimeError("fixture reset release missing")

    def close(self):
        self.events.append("close")
        self.closed.set()


class Fixture(PythonObjectDriver):
    device_id, device_kind, mode, risk = "retention", "world.sim", "simulated", "R0"
    native = "tests.bridges.test_python_retention:Native"
    fidelity = FIDELITY
    parameters = {"value": Field("number", unit="1", writable=True)}
    reads = {"value": "parameter.get"}
    writes = {"value": {"native": "parameter.set", "invoke": "call", "timeout_ms": 30}}
    commands = {CAP: {"native": "parameter.set", "args": {"value": {"from": "input.value"}},
                      "concurrency": "exclusive", "timeout_ms": 30,
                      "result": {"map": {"value": "output.$"}}}}
    actions = {CAP: Action(name="set_value", input={"value": Field("number", unit="1")},
                           output={"value": Field("number", unit="1")}, cancellable=True)}
    safety_bindings = {"estop": {"native": "off", "timeout_ms": 40},
                       "safe_state": {"native": "off", "timeout_ms": 40},
                       "reset": {"native": "reset_fault", "timeout_ms": 40}}
    safe_state = "Controlled native off after all earlier writes have settled"
    native_close = "close"


class FixtureHelpers:

    def attach(self, raw=None, cls=Fixture):
        raw = raw or Native()
        driver = cls(native=raw)
        server, client = serve(driver)
        def cleanup():
            raw.parameter.release.set()
            raw.off_release.set()
            raw.reset_release.set()
            close_server(server)
        self.addCleanup(cleanup)
        return raw, driver.inner, client

    def settled(self, bridge):
        with bridge._activity:
            self.assertTrue(bridge._activity.wait_for(lambda: not bridge._executions, timeout=2))

    def reset_result(self, client):
        return client.reset().get("result", {})



class RetentionTests(FixtureHelpers, unittest.TestCase):
    def test_stock_timeout_cannot_ack_stop_or_reset_before_late_write(self):
        raw, bridge, client = self.attach()
        command = client.command(CAP, {"value": 5.})
        self.assertEqual(command["status"], "unknown", command)
        stopped = client.estop()
        self.assertFalse(stopped["output"]["safe_state_achieved"], stopped)
        self.assertNotEqual(self.reset_result(client).get("status"), "completed")
        self.assertEqual(client.read()["state"]["value"], 0.)
        self.assertNotEqual(client.write({"value": 6.})["status"], "completed")
        self.assertEqual(raw.parameter.calls, [("enter", 5.)])
        raw.parameter.release.set()
        self.settled(bridge)
        self.assertEqual(raw.parameter.value, 5.)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception):
            bridge.reset()
        self.assertTrue(client.estop()["output"]["safe_state_achieved"])
        self.assertEqual(raw.parameter.value, 0.)
        self.assertEqual(self.reset_result(client)["status"], "completed")
        self.assertEqual(client.write({"value": 7.})["status"], "completed")

    def test_missing_stop_binding_never_confirms_unresolved_work(self):
        class NoStop(Fixture):
            safety_bindings = {}
        raw, bridge, client = self.attach(cls=NoStop)
        self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
        self.assertFalse(client.estop()["output"]["safe_state_achieved"])
        with self.assertRaises(Exception): bridge.safe_state()
        raw.parameter.release.set(); self.settled(bridge)
        with self.assertRaises(Exception): bridge.safe_state()
        with self.assertRaises(Exception): bridge.reset()

    def test_native_timeout_is_fenced_before_another_call_can_enter(self):
        raw = Native()
        def timeout(value):
            raw.parameter.calls.append(("enter", value))
            raise TimeoutError("remote outcome unknown")
        raw.parameter.set = timeout
        _, bridge, client = self.attach(raw)
        self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
        self.assertTrue(bridge._uncertain)
        with self.assertRaises(Exception): bridge.call(CAP, {"value": 2.})
        self.assertEqual(raw.parameter.calls, [("enter", 1.)])
        bridge.estop(); bridge.reset()

    def test_cancelled_synchronous_dispatch_retains_late_worker(self):
        raw, bridge, _ = self.attach()
        bridge._caps[CAP]["call"].timeout_ms = 1000
        event = threading.Event(); context = BridgeContext(cancel_event=event, deadline_ms=1000)
        errors = []
        def call():
            try: bridge.call(CAP, {"value": 1.}, context)
            except BaseException as exc: errors.append(exc)
        worker = threading.Thread(target=call); worker.start()
        try:
            self.assertTrue(raw.parameter.entered.wait(1))
            event.set(); worker.join(1)
            self.assertIsInstance(errors[0], signals.Cancelled)
            with self.assertRaises(Exception): bridge.estop()
            with self.assertRaises(Exception): bridge.reset()
            self.assertTrue(bridge._executions)
        finally:
            raw.parameter.release.set(); worker.join(2); self.settled(bridge)

    def test_setup_timeout_retains_target_until_deferred_cleanup(self):
        from mhs.bridge.python import PythonObjectBridge
        raw = Native()
        raw.setup = lambda: raw.parameter.set(1.)
        globals()["SETUP_NATIVE"] = raw
        bridge = PythonObjectBridge({"target": __name__ + ":SETUP_NATIVE", "factory": {"kind": "none"},
                                     "setup": {"native": "setup", "timeout_ms": 30}, "close": "close"}, load=False)
        try:
            with self.assertRaises(Exception): bridge._ensure_loaded()
            self.assertTrue(bridge.closed)
            self.assertFalse(raw.closed.is_set())
            self.assertIs(bridge._target, raw)
            raw.parameter.release.set()
            self.assertTrue(raw.closed.wait(1))
            self.assertTrue(bridge._cleanup_done.wait(1))
            self.assertIsNone(bridge._target)
        finally:
            raw.parameter.release.set(); bridge.close()
            globals().pop("SETUP_NATIVE", None)

    def test_safety_timeout_capacity_is_bounded_and_never_confirms(self):
        raw, bridge, _ = self.attach()
        raw.off_release.clear()
        try:
            for _ in range(8):
                with self.assertRaises(signals.OutcomeUnknown): bridge._run_safety("estop", None)
            with self.assertRaises(signals.DriverFailed): bridge._run_safety("estop", None)
            self.assertEqual(len(bridge._executions), 8)
            self.assertEqual(raw.events.count("off"), 8)
            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        finally:
            raw.off_release.set(); self.settled(bridge)
        bridge.estop(); bridge.reset()

    def test_resource_write_timeout_blocks_command_and_keeps_readable_state(self):
        raw, bridge, client = self.attach()
        receipt = client.write({"value": 3.})
        self.assertEqual(receipt["status"], "unknown", receipt)
        rejected = client.command(CAP, {"value": 4.})
        self.assertNotEqual(rejected["status"], "completed")
        self.assertEqual(raw.parameter.calls, [("enter", 3.)])
        self.assertEqual(client.read()["state"]["value"], 0.)
        raw.parameter.release.set()
        self.settled(bridge)
        with self.assertRaises(Exception):
            bridge.write("main", {"value": 4.})

    def test_configure_command_uses_retained_write_path(self):
        raw, bridge, client = self.attach()
        receipt = client.command("cap.device.configure.v1", {"value": 3.})
        self.assertEqual(receipt["status"], "unknown", receipt)
        self.assertFalse(client.estop()["output"]["safe_state_achieved"])
        raw.parameter.release.set()
        self.settled(bridge)

    def test_queued_write_is_fenced_after_first_command_timeout(self):
        raw, bridge, _ = self.attach()
        results = []
        def invoke():
            try: bridge.call(CAP, {"value": 2.})
            except BaseException as exc: results.append(exc)
        worker = threading.Thread(target=invoke)
        worker.start()
        self.assertTrue(raw.parameter.entered.wait(1))
        with self.assertRaises(Exception):
            bridge.write("main", {"value": 8.})
        worker.join(1)
        self.assertFalse(worker.is_alive())
        self.assertEqual(raw.parameter.calls, [("enter", 2.)])
        raw.parameter.release.set()
        self.settled(bridge)

    def test_shared_command_cannot_bypass_uncertainty(self):
        class Shared(Fixture):
            commands = copy.deepcopy(Fixture.commands)
            commands[CAP]["concurrency"] = "shared"
        raw, bridge, client = self.attach(cls=Shared)
        self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
        with self.assertRaises(Exception): bridge.call(CAP, {"value": 2.})
        self.assertEqual(raw.parameter.calls, [("enter", 1.)])
        raw.parameter.release.set()
        self.settled(bridge)

    def test_reset_native_timeout_is_retained_and_not_reinvoked(self):
        raw, bridge, client = self.attach()
        self.assertTrue(client.estop()["output"]["safe_state_achieved"])
        raw.reset_release.clear()
        result = self.reset_result(client)
        self.assertNotEqual(result.get("status"), "completed", result)
        self.assertTrue(raw.reset_entered.is_set())
        self.assertNotEqual(self.reset_result(client).get("status"), "completed")
        self.assertEqual(raw.events.count("reset"), 1)
        raw.reset_release.set()
        self.settled(bridge)
        with self.assertRaises(Exception): bridge.reset()
        bridge.estop()
        bridge.reset()
        self.assertEqual(raw.events.count("reset"), 2)

    def test_estop_during_reset_prevents_reset_commit(self):
        raw, bridge, _ = self.attach()
        raw.reset_release.clear()
        bridge._safety["reset"]["call"].timeout_ms = 1000
        errors = []
        def reset():
            try: bridge.reset()
            except BaseException as exc: errors.append(exc)
        thread = threading.Thread(target=reset)
        thread.start()
        try:
            self.assertTrue(raw.reset_entered.wait(1))
            with self.assertRaises(Exception): bridge.estop()
        finally:
            raw.reset_release.set()
            thread.join(2)
        self.assertTrue(errors)
        self.assertTrue(bridge._uncertain)
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_stop_started_before_write_finishes_cannot_be_reused(self):
        raw, bridge, client = self.attach()
        self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
        raw.off_release.clear()
        raw.off_entered.clear()
        bridge._safety["estop"]["call"].timeout_ms = 1000
        errors = []
        def stop():
            try: bridge.estop()
            except BaseException as exc: errors.append(exc)
        worker = threading.Thread(target=stop)
        worker.start()
        try:
            self.assertTrue(raw.off_entered.wait(1))
            raw.parameter.release.set()
            self.assertTrue(raw.parameter.finished.wait(1))
            raw.off_release.set()
            worker.join(2)
            self.assertTrue(errors)
            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        finally:
            raw.off_release.set()
            worker.join(2)

    def test_close_defers_cleanup_and_cannot_reopen(self):
        raw, bridge, client = self.attach()
        self.assertEqual(client.command(CAP, {"value": 9.})["status"], "unknown")
        bridge.close()
        self.assertFalse(raw.closed.is_set())
        with self.assertRaises(Exception): bridge.reset()
        with self.assertRaises(Exception): bridge.call(CAP, {"value": 7.})
        raw.parameter.release.set()
        self.assertTrue(raw.closed.wait(1))
        self.assertTrue(bridge._cleanup_done.wait(1))
        bridge.close()
        self.assertEqual(raw.events.count("close"), 1)

    def test_native_future_remains_running_after_caller_timeout(self):
        raw = Native()
        future = concurrent.futures.Future()
        future.set_running_or_notify_cancel()
        raw.parameter.set = lambda value: future
        _, bridge, client = self.attach(raw)
        self.assertEqual(client.command(CAP, {"value": 2.})["status"], "unknown")
        self.assertFalse(future.cancelled())
        self.assertFalse(client.estop()["output"]["safe_state_achieved"])
        future.set_result(2.)
        self.settled(bridge)
        with self.assertRaises(Exception): bridge.reset()
        bridge.estop(); bridge.reset()

    def test_cancelled_pending_future_settles_without_assuming_physical_stop(self):
        raw = Native(); future = concurrent.futures.Future()
        raw.parameter.set = lambda value: future
        _, bridge, client = self.attach(raw)
        self.assertEqual(client.command(CAP, {"value": 2.})["status"], "unknown")
        self.settled(bridge)
        self.assertTrue(future.cancelled())
        with self.assertRaises(Exception): bridge.reset()
        bridge.estop(); bridge.reset()

    def test_restore_uses_same_retention_and_refusal(self):
        raw, bridge, _ = self.attach()
        bridge.config["restore"] = {"method": "parameter.set", "args": {"value": {"from": "snapshot.value"}}}
        worker = threading.Thread(target=lambda: self._capture_restore(bridge))
        worker.start()
        try:
            self.assertTrue(raw.parameter.entered.wait(1))
            with self.assertRaises(Exception): bridge.estop()
            with self.assertRaises(Exception): bridge.reset()
        finally:
            raw.parameter.release.set(); worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(bridge._uncertain)

    @staticmethod
    def _capture_restore(bridge):
        try: bridge.restore({"value": 4.})
        except Exception: pass

    def test_partial_write_retains_unknown_status(self):
        raw, bridge, _ = self.attach()
        original = bridge._writes["main"]["params"]["value"]
        bridge._writes["main"]["params"]["first"] = copy.copy(original)
        bridge._writes["main"]["params"]["first"]["call"] = copy.copy(original["call"])
        bridge._writes["main"]["params"]["first"]["call"].native = "first"
        raw.first = lambda value: value
        with self.assertRaises(signals.OutcomeUnknown):
            bridge.write("main", {"first": 1., "value": 2.})
        self.assertTrue(bridge._uncertain)
        raw.parameter.release.set()
        self.settled(bridge)


class AsyncAndStatusTests(FixtureHelpers, unittest.TestCase):
    def test_cancel_suppressed_async_cleanup_stays_tracked(self):
        raw = Native()
        entered, cancelled, release = threading.Event(), threading.Event(), threading.Event()
        async def setter(value):
            entered.set()
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancelled.set()
                while not release.is_set():
                    await asyncio.sleep(.001)
                raw.parameter.value = value
                return value
        raw.parameter.set = setter
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
            self.assertTrue(cancelled.wait(1))
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            self.assertNotEqual(self.reset_result(client).get("status"), "completed")
            release.set()
            self.settled(bridge)
            self.assertEqual(raw.parameter.value, 5.)
            self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        finally: release.set()

    def test_pending_status_cancel_dispatch_is_not_terminal_acknowledgment(self):
        class Status:
            done, success = False, True
            def __init__(self): self.cancelled = threading.Event(); self.release = threading.Event()
            def wait(self, timeout):
                if not self.release.wait(timeout): raise TimeoutError()
                self.done = True
            def cancel(self): self.cancelled.set()
        raw = Native(); status = Status()
        raw.parameter.set = lambda value: status
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
            self.assertTrue(status.cancelled.wait(1))
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            self.assertFalse(status.done)
            status.release.set(); self.settled(bridge)
            with self.assertRaises(Exception): bridge.reset()
        finally: status.release.set()

    def test_status_wait_error_with_done_false_does_not_release_mutation_fence(self):
        class Status:
            done, success = False, False
            def wait(self, timeout): raise RuntimeError("readback failed while operation is active")
        raw = Native(); status = Status()
        raw.parameter.set = lambda value: status
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            status.done = True; self.settled(bridge)
        finally: status.done = True

    def test_cancel_callback_that_outlives_status_is_retained(self):
        class Status:
            done, success = False, True
            def __init__(self): self.entered = threading.Event(); self.release = threading.Event()
            def wait(self, timeout):
                if not self.done: raise TimeoutError()
            def cancel(self):
                self.entered.set(); self.done = True
                if not self.release.wait(3): raise RuntimeError("cancel callback release missing")
        raw = Native(); status = Status()
        raw.parameter.set = lambda value: status
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 1.})["status"], "unknown")
            self.assertTrue(status.entered.wait(1))
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            status.release.set(); self.settled(bridge)
        finally: status.release.set()



class CompletionChainTests(FixtureHelpers, unittest.TestCase):
    def test_cancellation_returned_status_remains_active_after_readback_error(self):
        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous):
                class Followup:
                    done, success = False, True
                    def wait(self, timeout):
                        if not self.done:
                            raise RuntimeError("cancellation cleanup still active; readback unavailable")
                raw = Native(); followup = Followup(); returned = threading.Event()
                class Primary:
                    done, success = False, True
                    def wait(self, timeout):
                        if not self.done: raise TimeoutError()
                    def cancel(self):
                        self.done = True; returned.set(); return followup
                status = Primary()
                if asynchronous:
                    async def cancel():
                        status.done = True; returned.set(); return followup
                    status.cancel = cancel
                raw.parameter.set = lambda value: status
                _, bridge, client = self.attach(raw)
                try:
                    self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
                    self.assertTrue(returned.wait(1))
                    self.assertTrue(bridge._executions)
                    self.assertFalse(client.estop()["output"]["safe_state_achieved"])
                    self.assertNotEqual(self.reset_result(client).get("status"), "completed")
                    raw.parameter.value = 9.; followup.done = True
                    self.settled(bridge)
                    self.assertEqual(raw.parameter.value, 9.)
                    self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
                    with self.assertRaises(Exception): bridge.reset()
                    bridge.estop(); bridge.reset()
                    self.assertEqual(raw.parameter.value, 0.)
                finally: followup.done = True

    def test_unknown_done_and_success_do_not_imply_terminal_completion(self):
        class Status:
            done = None
            success = None
            def wait(self, timeout): return None
        status = Status(); raw = Native()
        raw.parameter.set = lambda value: status
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
            self.assertTrue(bridge._executions)
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            self.assertNotEqual(self.reset_result(client).get("status"), "completed")
            status.done = True; status.success = True
            self.settled(bridge)
        finally: status.done = True; status.success = True

    def test_terminal_status_unknown_success_is_unknown_not_success(self):
        class Status:
            done = True
            success = None
            def wait(self, timeout): return None
        raw = Native(); raw.parameter.set = lambda value: Status()
        _, bridge, client = self.attach(raw)
        self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
        self.settled(bridge)
        self.assertTrue(bridge._uncertain)
        with self.assertRaises(Exception): bridge.reset()
        bridge.estop(); bridge.reset()

    def test_native_status_operation_timeout_is_unknown_and_fenced(self):
        class StatusTimeoutError(Exception): pass
        class Status:
            done, success = True, False
            def wait(self, timeout): raise StatusTimeoutError("native operation deadline expired")
        raw = Native(); raw.parameter.set = lambda value: Status()
        _, bridge, client = self.attach(raw)
        self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
        self.assertTrue(bridge._uncertain)
        with self.assertRaises(Exception): bridge.reset()
        bridge.estop(); bridge.reset()

    def test_wait_slice_timeout_racing_with_done_is_not_native_failure(self):
        class Status:
            done, success = False, True
            def wait(self, timeout):
                if not self.done:
                    self.done = True
                    raise TimeoutError("slice expired just before the terminal update")
        _, bridge, _ = self.attach()
        self.assertEqual(bridge._resolve_retained(Status(), label="race"), {"done": True, "success": True})

    def test_wait_only_status_slice_timeout_keeps_native_work_retained(self):
        release = threading.Event()
        class Status:
            def wait(self, timeout):
                if not release.wait(timeout): raise TimeoutError("polling timeout")
        raw = Native(); raw.parameter.set = lambda value: Status()
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
            self.assertTrue(bridge._executions)
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            release.set(); self.settled(bridge)
        finally: release.set()

    def test_async_result_containing_pending_status_remains_retained(self):
        class Status:
            done, success = False, True
            def wait(self, timeout):
                if not self.done: raise TimeoutError()
        status = Status(); raw = Native()
        async def setter(value): return status
        raw.parameter.set = setter
        _, bridge, client = self.attach(raw)
        try:
            self.assertEqual(client.command(CAP, {"value": 5.})["status"], "unknown")
            self.assertTrue(bridge._executions)
            self.assertFalse(client.estop()["output"]["safe_state_achieved"])
            status.done = True; self.settled(bridge)
        finally: status.done = True


if __name__ == "__main__": unittest.main()
