"""Stock client/server timing receipts using deterministic, in-process peers."""
import copy
import threading
import time
import unittest

from mhs import canonical
from mhs.client import MHSClient
from mhs.driver import build_server, close_server
from mhs.schema import validate
from mhs.schema.store import default_store
from tests.bridges.test_gymnasium_timing import ClockEnv, STEP, ACTION, CHECKPOINT
from tests.driver.test_gymnasium_timing import timed_driver

NS = "openmhs_simulation_timing"


class SimulationTimingReceiptTests(unittest.TestCase):
    def make(self, env=None, *, autoreset=False, long_running=False, decimation=5,
             backend="sim", checkpoint=False):
        env = env or ClockEnv()
        driver = timed_driver(env, autoreset=autoreset, long_running=long_running, decimation=decimation,
                              backend=backend, checkpoint=checkpoint)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = MHSClient(server)
        client.hello()
        device = next(iter(server.devices.values()))
        client.open_session([device.device_id], mode="simulated")
        return env, server, client, device.device_id

    def invoke(self, client, device, ticks, **kwargs):
        return client.invoke(STEP, {"ticks": ticks, "action": ACTION}, device_id=device, **kwargs)

    def assert_valid(self, receipt):
        self.assertEqual(default_store().validate(dict(receipt), "receipt.schema.json"), [])

    def test_final_receipt_uses_completed_ticks_and_keeps_wall_duration(self):
        env, server, client, device = self.make(ClockEnv(terminate_after=2))
        receipt = self.invoke(client, device, 15)
        self.assertEqual(receipt["status"], "completed", receipt)
        note = receipt["x-vendor"][NS]
        self.assertEqual((note["requested_ticks"], note["completed_ticks"], note["simulated_duration_ms"]),
                         (15, 10, 20))
        self.assertEqual(receipt["progress"]["ticks"], 10)
        self.assertIn("duration_ms", receipt["x-vendor"])
        self.assert_valid(receipt)

    def test_input_refusal_reports_zero_without_native_reset(self):
        env, server, client, device = self.make()
        for ticks in (1, 6, True):
            receipt = self.invoke(client, device, ticks)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["x-vendor"][NS]["completed_ticks"], 0)
            self.assertEqual(receipt["progress"]["ticks"], 0)
            self.assert_valid(receipt)
        self.assertEqual((env.calls, env.resets), (0, 0))

    def test_autoreset_and_native_failure_keep_distinct_accounting(self):
        env, server, client, device = self.make(ClockEnv(terminate_after=2), autoreset=True)
        receipt = self.invoke(client, device, 15)
        self.assertEqual(receipt["output"]["tick"], 5)
        self.assertEqual(receipt["x-vendor"][NS]["completed_ticks"], 15)
        self.assert_valid(receipt)
        env.advance, env.failure = 3, "raise"
        receipt = self.invoke(client, device, 5)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["x-vendor"][NS]["simulated_duration_ms"], 6)
        self.assert_valid(receipt)

    def test_timeout_late_completion_replay_and_queued_command_are_isolated(self):
        env, server, client, device = self.make()
        entered, release, queued = threading.Event(), threading.Event(), threading.Event()
        first_id, second_id = canonical.ulid(), canonical.ulid()
        class ClockProbe:
            value = 0.0
            owner = None
            foreign_read = False
            @property
            def time(self):
                if entered.is_set() and not release.is_set() and threading.get_ident() != self.owner:
                    self.foreign_read = True
                return self.value
            @time.setter
            def time(self, value):
                self.value = value
        probe = ClockProbe()
        env.data = probe
        self.addCleanup(release.set)
        def block_first(e):
            if e.calls == 1:
                probe.owner = threading.get_ident()
                entered.set()
                if not release.wait(3):
                    raise AssertionError("test did not release native call")
        env.after_physics = block_first
        first_result = {}
        def first():
            first_result["receipt"] = self.invoke(client, device, 15, command_id=first_id, deadline_ms=120)
        first_thread = threading.Thread(target=first)
        first_thread.start()
        self.assertTrue(entered.wait(1))
        started = time.monotonic()
        first_thread.join(1)
        self.assertFalse(first_thread.is_alive())
        self.assertLess(time.monotonic() - started, 1)
        unknown = first_result["receipt"]
        self.assertEqual(unknown["status"], "unknown", unknown)
        frozen = copy.deepcopy(dict(unknown))
        note = unknown["x-vendor"][NS]
        self.assertEqual((note["known_completed_ticks"], note["in_flight"]), (0, True))
        self.assertIsNone(note["completed_ticks"])
        self.assertIsNone(note["simulated_duration_ms"])
        self.assertFalse(probe.foreign_read, "timeout accounting read the running native clock")
        self.assert_valid(unknown)
        second_result = {}
        def second():
            queued.set()
            second_result["receipt"] = self.invoke(client, device, 10, command_id=second_id, deadline_ms=2500)
        second_thread = threading.Thread(target=second)
        second_thread.start()
        self.assertTrue(queued.wait(1))
        self.assertEqual(env.calls, 1)
        release.set()
        first_op = server._operations[unknown["operation_id"]]
        self.assertTrue(first_op.done.wait(2))
        second_thread.join(2)
        self.assertFalse(second_thread.is_alive())
        final = self.invoke(client, device, 15, command_id=first_id)
        self.assertTrue(final["replayed"])
        self.assertEqual(final["status"], "completed", final)
        self.assertEqual(final["x-vendor"][NS]["completed_ticks"], 15)
        self.assertEqual(final["x-vendor"][NS]["simulated_duration_ms"], 30)
        self.assertEqual(final["x-vendor"]["reconciles"]["receipt_id"], unknown["receipt_id"])
        second_receipt = second_result["receipt"]
        self.assertEqual(second_receipt["status"], "completed", second_receipt)
        self.assertEqual(second_receipt["x-vendor"][NS]["completed_ticks"], 10)
        self.assertEqual(second_receipt["x-vendor"][NS]["simulated_duration_ms"], 20)
        self.assertEqual((env.calls, second_receipt["output"]["tick"]), (5, 25))
        self.assertEqual(dict(unknown), frozen)
        self.assert_valid(final)
        self.assert_valid(second_receipt)

    def test_running_progress_and_cancel_count_the_finished_opaque_block(self):
        env, server, client, device = self.make(long_running=True)
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def blocked(e):
            entered.set()
            if not release.wait(3):
                raise AssertionError("native release missing")
        env.after_physics = blocked
        receipt = self.invoke(client, device, 15, deadline_ms=70)
        self.assertTrue(entered.is_set())
        self.assertEqual(receipt["status"], "running", receipt)
        self.assertIsNone(receipt["x-vendor"][NS]["completed_ticks"])
        self.assertEqual(receipt["progress"]["ticks"], 0)
        self.assert_valid(receipt)
        result = {}
        thread = threading.Thread(target=lambda: result.update(
            receipt=client.cancel(receipt["operation_id"], deadline_ms=1000)))
        thread.start()
        operation = server._operations[receipt["operation_id"]]
        self.assertTrue(operation.cancel_event.wait(1))
        release.set()
        thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(operation.done.wait(1))
        final = operation.final_receipt
        self.assertEqual(final["status"], "cancelled", final)
        self.assertEqual(final["x-vendor"][NS]["completed_ticks"], 5)
        self.assertEqual(final["x-vendor"][NS]["simulated_duration_ms"], 10)
        self.assertEqual(env.calls, 1)
        self.assert_valid(final)

    def test_clock_fault_is_not_published_as_zero_duration(self):
        env, server, client, device = self.make()
        env.after_physics = lambda e: setattr(e.data, "time", 0.0)
        receipt = self.invoke(client, device, 5)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt["x-vendor"][NS]["completed_ticks"])
        self.assertIsNone(receipt["x-vendor"][NS]["simulated_duration_ms"])
        self.assert_valid(receipt)

    def test_failed_implicit_and_auto_reset_make_duration_unknown(self):
        for bad_on, requested, known in ((1, 5, 0), (2, 15, 5)):
            class AdvancingReset(ClockEnv):
                def reset(self, **kwargs):
                    result = super().reset(**kwargs)
                    if self.resets == bad_on:
                        self.data.time = 0.006
                    return result
            env = AdvancingReset(terminate_after=1)
            env, server, client, device = self.make(env, autoreset=True)
            receipt = self.invoke(client, device, requested)
            self.assertEqual(receipt["status"], "failed", receipt)
            note = receipt["x-vendor"][NS]
            self.assertEqual(note["known_completed_ticks"], known)
            self.assertIsNone(note["completed_ticks"])
            self.assertIsNone(note["simulated_duration_ms"])
            self.assertEqual(note["accounting"], "unknown")
            self.assertEqual((note["reset_calls_started"], note["reset_calls_verified"]), (bad_on, bad_on - 1))
            self.assertEqual(note["stop_reason"], "reset_fault")
            self.assert_valid(receipt)

    def test_invalid_first_observation_stops_same_and_later_commands(self):
        class FirstBadObservation(ClockEnv):
            def step(self, action):
                result = super().step(action)
                return (object(), *result[1:]) if self.calls == 1 else result
        env, server, client, device = self.make(FirstBadObservation())
        first = self.invoke(client, device, 15)
        self.assertEqual(first["status"], "failed", first)
        self.assertEqual(first["x-vendor"][NS]["stop_reason"], "invalid_result")
        self.assertEqual(first["x-vendor"][NS]["completed_ticks"], 5)
        self.assertEqual(first["x-vendor"][NS]["simulated_duration_ms"], 10)
        second = self.invoke(client, device, 5)
        self.assertNotEqual(second["status"], "completed", second)
        self.assertEqual(env.calls, 1)
        self.assert_valid(first)

    def test_failed_reset_observation_cannot_clear_timing_fault(self):
        class BadResetObservation(ClockEnv):
            bad_reset = False
            def reset(self, **kwargs):
                result = super().reset(**kwargs)
                return (object(), {}) if self.bad_reset else result
        env, server, client, device = self.make(BadResetObservation())
        env.failure = "raise"
        self.assertEqual(self.invoke(client, device, 5)["status"], "failed")
        env.failure, env.bad_reset = None, True
        reset = client.invoke("cap.world.reset.v1", {}, device_id=device)
        self.assertEqual(reset["status"], "failed", reset)
        self.assertIsNotNone(next(iter(server.devices.values())).bridge.inner._timing_fault)
        self.assertNotEqual(self.invoke(client, device, 5)["status"], "completed")
        self.assertEqual(env.calls, 1)
        env.bad_reset = False
        self.assertEqual(client.invoke("cap.world.reset.v1", {}, device_id=device)["status"], "completed")
        self.assertEqual(self.invoke(client, device, 5)["status"], "completed")
        self.assertEqual(env.calls, 2)

    def test_timeout_during_reset_is_in_flight_and_failed_reset_stays_unknown(self):
        entered, release = threading.Event(), threading.Event()
        class BlockedReset(ClockEnv):
            def reset(self, **kwargs):
                result = super().reset(**kwargs)
                self.data.time = 0.006
                entered.set()
                if not release.wait(3):
                    raise AssertionError("reset release missing")
                return result
        env, server, client, device = self.make(BlockedReset())
        self.addCleanup(release.set)
        command_id = canonical.ulid()
        unknown = self.invoke(client, device, 5, command_id=command_id, deadline_ms=80)
        self.assertTrue(entered.is_set())
        self.assertEqual(unknown["status"], "unknown", unknown)
        note = unknown["x-vendor"][NS]
        self.assertTrue(note["in_flight"])
        self.assertIsNone(note["simulated_duration_ms"])
        self.assertEqual((note["control_calls_started"], note["reset_calls_started"]), (0, 1))
        frozen = copy.deepcopy(dict(unknown))
        release.set()
        self.assertTrue(server._operations[unknown["operation_id"]].done.wait(2))
        final = self.invoke(client, device, 5, command_id=command_id)
        self.assertEqual(final["status"], "failed", final)
        self.assertIsNone(final["x-vendor"][NS]["completed_ticks"])
        self.assertIsNone(final["x-vendor"][NS]["simulated_duration_ms"])
        self.assertEqual(dict(unknown), frozen)
        self.assertEqual(env.calls, 0)
        self.assert_valid(final)

    def test_accumulated_clock_snapshot_and_large_decimation_are_valid(self):
        for decimation in (5, 10000):
            env = ClockEnv(terminate_after=100000)
            env.advance = decimation
            env, server, client, device = self.make(env, decimation=decimation, backend="fake", checkpoint=True)
            receipt = self.invoke(client, device, 10000)
            self.assertEqual(receipt["status"], "completed", receipt)
            self.assertEqual(receipt["x-vendor"][NS]["completed_ticks"], 10000)
            self.assertEqual(receipt["x-vendor"][NS]["simulated_duration_ms"], 20000)
            snapshot = client.snapshot(device)
            world = snapshot["state"]["world"]
            descriptor = client.device(device).manifest()
            self.assertEqual(default_store().validate(snapshot, "snapshot.schema.json"), [])
            self.assertEqual(validate(world, descriptor["resources"][0]["state_schema"]), [])
            self.assertTrue(descriptor["fidelity"]["snapshot_restore"])
            self.assertEqual(descriptor["fidelity"]["determinism"]["kind"], "seeded")
            self.assertEqual(snapshot["instance_id"], descriptor["instance_id"])
            self.assertEqual(snapshot["device_id"], device)
            self.assertEqual(snapshot["fidelity_digest"], canonical.digest(descriptor["fidelity"]))
            self.assertEqual(snapshot["snapshot"], snapshot["state"])
            self.assertEqual(snapshot["snapshot_digest"], canonical.digest(snapshot["state"]))
            self.assertEqual(snapshot["state_hash"], canonical.state_hash(world))
            self.assertEqual(client.read("world", device_id=device)["state"], world)
            self.assertEqual(world["native_checkpoint"]["configuration_digest"], canonical.digest(CHECKPOINT))
            self.assertEqual(world["native_checkpoint"]["native_state"], env.get_state())
            self.assertLessEqual(len(canonical.jcs(world)), CHECKPOINT["max_bytes"])
            foreign = copy.deepcopy(snapshot)
            foreign["instance_id"] = canonical.ulid()
            self.assertEqual(client.restore(foreign, device)["status"], "rejected")
            self.assertEqual(env.restores, 0)
            followup = self.invoke(client, device, decimation)
            self.assertEqual(followup["status"], "completed", followup)
            self.assertEqual(env.calls, 10000 // decimation + 1)
            expected_native = env.get_state()
            restored = client.restore(snapshot, device)
            self.assertEqual(restored["status"], "completed", restored)
            self.assertEqual(client.read("world", device_id=device)["state"], world)
            self.assertEqual(env.get_state(), world["native_checkpoint"]["native_state"])
            self.assertEqual(env.restores, 1)
            continued = self.invoke(client, device, decimation)
            self.assertEqual(continued["status"], "completed", continued)
            self.assertEqual(continued["output"], followup["output"])
            self.assertEqual(env.get_state(), expected_native)
            self.assertEqual(env.calls, 10000 // decimation + 2)
            self.assertEqual(env.native_steps, env.calls, "native lifetime diagnostics must not rewind")
            bridge = server.devices[device].bridge.inner
            self.assertEqual(bridge._total_steps, env.calls)
            bridge._max_steps = env.calls
            self.assertEqual(client.restore(snapshot, device)["status"], "completed")
            self.assertNotEqual(self.invoke(client, device, decimation)["status"], "completed")
            self.assertEqual(env.calls, 10000 // decimation + 2, "restore must not refill the native budget")


if __name__ == "__main__":
    unittest.main()
