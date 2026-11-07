"""Nested attribute recording, value boundaries and real server/G6 regressions."""

from __future__ import annotations

import array
import inspect
import threading
import unittest
from dataclasses import dataclass
from pathlib import Path

from mhs.driver import Driver, Limit, close_server, estop, read, write
from mhs.testing import Recorder, log_of
from mhs.testing.recorder import _CHILD_CACHE_SIZE

from tests.driver import gate_support as gs
from tests.driver.support import serve


class Motor:
    def __init__(self):
        self.value = 0.0
        self.enabled = True
        self.fail_next = False
        self.mutations = []

    def get(self):
        return self.value

    def set(self, value):
        if self.fail_next:
            self.fail_next = False
            raise ValueError("native failure")
        self.value = value
        self.mutations.append(("set", value))

    def stop(self):
        self.enabled = False
        self.mutations.append(("stop",))

    def use(self, other, *, keyword):
        return other is self and keyword is self


class Native:
    def __init__(self):
        self.motor = Motor()
        self.alias = self.motor
        self.self_ref = self

    def returned_motor(self):
        return self.motor


class Probe(Driver):
    device_id, device_kind = "nested-recorder", "thermal.zone"
    mode, risk = "simulated", "R0"
    fidelity = {"engine": "test", "fidelity_level": "F0", "determinism": {"kind": "exact"}, "timestep_ms": 0,
                "realtime_factor": 0, "reset": "full", "snapshot_restore": False, "gaps": ["test only"]}
    backends = {"fake": Native}

    @read("value", unit="Cel")
    def value(self):
        return self.native.motor.get()

    @write("value", unit="Cel", limit=Limit(min=0, max=10, source="vendor_doc", ref="manual.md:1"))
    def set_value(self, value):
        self.native.motor.set(value)

    @estop(native="motor.stop")
    def stop(self):
        self.native.motor.stop()


class AssignmentProbe(Probe):
    @write("value", unit="Cel", limit=Limit(min=0, max=10, source="vendor_doc", ref="manual.md:1"))
    def set_value(self, value):
        self.native.motor.value = value


class NestedRecorderTests(unittest.TestCase):
    def test_nested_calls_sets_deletes_and_missing_paths_share_one_log(self):
        native = Native()
        recorder = Recorder(native)
        motor = recorder.motor
        log = log_of(recorder)
        self.assertIs(log_of(motor), log)
        self.assertIs(recorder.motor, motor)
        self.assertEqual(list(inspect.signature(motor.set).parameters), ["value"])
        motor.set(2)
        motor.enabled = False
        del motor.enabled
        with self.assertRaises(AttributeError):
            motor.absent()
        self.assertEqual(native.motor.value, 2)
        self.assertFalse(hasattr(native.motor, "enabled"))
        self.assertEqual([(c.name, c.kind) for c in log.actuations()],
                         [("motor.set", "call"), ("motor.enabled", "set"), ("motor.enabled", "del")])
        self.assertEqual(log.found, {"motor"})  # G7 compares only root native members.
        self.assertEqual(log.missing, set())
        self.assertIn("motor.set", log.found_paths)
        self.assertIn("motor.absent", log.missing_paths)

    def test_full_path_failures_precede_calls_assignments_and_deletions(self):
        native = Native()
        recorder = Recorder(native)
        log = log_of(recorder)
        with log.fail(names=["motor.set"]) as failure:
            with self.assertRaises(RuntimeError):
                recorder.motor.set(3)
            recorder.alias.set(4)  # A distinct access path is not selected.
        self.assertEqual(failure.raised, 1)
        self.assertEqual(native.motor.mutations, [("set", 4)])
        with log.fail(names=["motor.enabled"]):
            with self.assertRaises(RuntimeError):
                recorder.motor.enabled = False
            with self.assertRaises(RuntimeError):
                del recorder.motor.enabled
        self.assertTrue(native.motor.enabled)

    def test_native_fail_next_is_not_hidden_or_consumed_by_injected_failure(self):
        native = Native()
        recorder = Recorder(native)
        recorder.motor.fail_next = True
        log = log_of(recorder)
        with log.fail(names=["motor.set"]):
            with self.assertRaisesRegex(RuntimeError, "injected native failure"):
                recorder.motor.set(1)
        self.assertTrue(native.motor.fail_next)
        with self.assertRaisesRegex(ValueError, "native failure"):
            recorder.motor.set(2)
        self.assertFalse(native.motor.fail_next)
        recorder.motor.set(3)
        self.assertEqual(native.motor.mutations, [("set", 3)])

    def test_aliases_cycles_replacement_and_cache_eviction_keep_path_recording(self):
        native = Native()
        recorder = Recorder(native)
        original = recorder.motor
        recorder.alias.stop()
        recorder.self_ref.motor.stop()
        log = log_of(recorder)
        self.assertEqual([c.name for c in log.actuations()], ["alias.stop", "self_ref.motor.stop"])
        # Repeated cyclic traversal must not recurse eagerly or retain an
        # unbounded proxy graph; an evicted external handle still records.
        current = recorder
        for _ in range(_CHILD_CACHE_SIZE + 12):
            current = current.self_ref
        self.assertLessEqual(len(log._children), _CHILD_CACHE_SIZE)
        mark = log.mark()
        original.stop()
        self.assertEqual([c.name for c in log.actuations(mark)], ["motor.stop"])
        replacement = Motor()
        native.motor = replacement
        self.assertIsNot(recorder.motor, original)
        recorder.motor.set(8)
        self.assertEqual(replacement.value, 8)
        self.assertEqual(native.alias.value, 0)

    def test_direct_proxy_arguments_and_assignments_do_not_enter_native_state(self):
        native = Native()
        recorder = Recorder(native)
        child = recorder.motor
        self.assertTrue(child.use(child, keyword=child))
        recorder.alias = child
        self.assertIs(native.alias, native.motor)
        child.link = recorder
        self.assertIs(native.motor.link, native)

    def test_value_container_buffer_and_array_protocols_are_identity_preserving(self):
        @dataclass
        class Value:
            amount: int

        class ArrayLike:
            @property
            def __array_interface__(self):
                raise AssertionError("selection must never evaluate an array descriptor")

        class SequenceLike:
            def __getitem__(self, index):
                return index

        values = [None, True, 4, 2.0, "name", b"bytes", bytearray(b"x"), memoryview(b"x"),
                  [1, 2], (1, 2), {"x": 1}, {1, 2}, array.array("d", [1, 2]), Path("file"),
                  Value(1), ArrayLike(), SequenceLike()]
        recorder = Recorder(attributes={"value": None})
        for value in values:
            with self.subTest(type=type(value).__name__):
                recorder.value = value
                self.assertIs(recorder.value, value)
        # Item mutations intentionally retain native semantics and are outside
        # nested attribute recording, as are values returned by native calls.
        items = [Motor()]
        recorder.value = items
        mark = log_of(recorder).mark()
        recorder.value[0].stop()
        self.assertFalse(items[0].enabled)
        self.assertEqual(log_of(recorder).actuations(mark), [])
        native = Native()
        self.assertIs(Recorder(native).returned_motor(), native.motor)

    def test_scientific_numpy_array_is_not_wrapped_when_available(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy is optional; protocol exclusion is tested without it")
        data = np.arange(6).reshape(2, 3)
        recorder = Recorder(attributes={"data": data})
        self.assertIs(recorder.data, data)
        self.assertEqual((recorder.data + 1).tolist(), [[1, 2, 3], [4, 5, 6]])
        recorder.data[0, 0] = 9
        self.assertEqual(data[0, 0], 9)

    def test_slots_objects_and_standalone_child_attributes_are_recorded(self):
        class Slotted:
            __slots__ = ("value",)

            def __init__(self):
                self.value = 0

        child = Slotted()
        recorder = Recorder(attributes={"child": child})
        recorder.child.value = 7
        self.assertEqual(child.value, 7)
        self.assertEqual([c.name for c in log_of(recorder).actuations()], ["child.value"])

    def test_phase_windows_and_failure_selection_apply_to_nested_helper_threads(self):
        native = Native()
        recorder = Recorder(native)
        log = log_of(recorder)
        seen = []

        def worker():
            try:
                recorder.motor.stop()
            except RuntimeError:
                seen.append("failed")

        with log.window("estop"), log.fail(phases=["estop"], names=["motor.stop"]):
            thread = threading.Thread(target=worker)
            thread.start()
            thread.join(3)
            self.assertFalse(thread.is_alive())
        self.assertEqual(seen, ["failed"])
        self.assertTrue(native.motor.enabled)
        self.assertEqual([(c.name, c.phase) for c in log.in_phase("estop")], [("motor.stop", "estop")])


class NestedServerTests(unittest.TestCase):
    def endpoint(self, cls=Probe):
        native = Native()
        recorder = Recorder(native)
        driver = cls(backend="fake", native=recorder)
        server, client = serve(driver)
        self.addCleanup(close_server, server)
        return native, log_of(recorder), client

    def test_out_of_envelope_and_latched_input_make_zero_nested_native_mutations(self):
        for cls in (Probe, AssignmentProbe):
            with self.subTest(driver=cls.__name__):
                native, log, client = self.endpoint(cls)
                mark = log.mark()
                denied = client.write({"value": 11})
                self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION")
                self.assertEqual(log.actuations(mark), [])
                self.assertEqual(native.motor.value, 0)
                self.assertEqual(native.motor.mutations, [])
                stopped = client.estop()
                self.assertEqual(stopped["status"], "completed", stopped)
                self.assertEqual([(c.name, c.phase) for c in log.in_phase("estop")],
                                 [("motor.stop", "estop")])
                before = list(native.motor.mutations)
                mark = log.mark()
                denied = client.write({"value": 5})
                self.assertEqual(denied["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")
                self.assertEqual(log.actuations(mark), [])
                self.assertEqual(native.motor.mutations, before)

    def test_nested_injected_and_native_failure_produce_failed_receipts(self):
        native, log, client = self.endpoint()
        for injected in (False, True):
            with self.subTest(injected=injected):
                if injected:
                    with log.fail(names=["motor.set"]):
                        receipt = client.write({"value": 4})
                else:
                    native.motor.fail_next = True
                    receipt = client.write({"value": 4})
                self.assertEqual(receipt["status"], "failed", receipt)
                self.assertEqual(native.motor.value, 0)
                self.assertEqual(native.motor.mutations, [])
        mark = log.mark()
        self.assertEqual(client.write({"value": 4})["status"], "completed")
        self.assertEqual([(c.name, c.kind) for c in log.actuations(mark)], [("motor.set", "call")])
        self.assertTrue(all(c.phase == "read" for c in log.since(mark) if c.name == "motor.get"))


class NestedGateTests(unittest.TestCase):
    def package(self, *, swallowed=False, noop_stop=False):
        directory = gs.copy_tutorial(self)
        # Synthetic SDK fixture only: no upstream corpus source is modified or
        # executed. G7 still checks the root's motor attribute against source.
        gs.edit(directory, "fake.py", "        self.lid = True", "        self.lid = True\n        self.motor = Motor(self)")
        with (directory / "fake.py").open("a") as stream:
            stream.write("\n\nclass Motor:\n"
                         "    def __init__(self, controller):\n        self.controller = controller\n"
                         "    def stop(self):\n        self.controller.emergency_off()\n"
                         "    def set(self, value):\n        self.controller.set_setpoint(value)\n")
        # Append a property without shifting existing source citations.
        with (directory / "vendor/thermo/controller.py").open("a") as stream:
            stream.write("\n    @property\n    def motor(self):\n        return Motor(self)\n\n\n"
                         "class Motor:\n"
                         "    def __init__(self, controller):\n        self.controller = controller\n"
                         "    def stop(self):\n        self.controller.emergency_off()\n"
                         "    def set(self, value):\n        self.controller.set_setpoint(value)\n")
        gs.edit(directory, "driver.py", "        self.native.emergency_off()",
                "        self.native.motor" if noop_stop else "        self.native.motor.stop()")
        nested_write = "        self.native.motor.set(value)"
        if swallowed:
            nested_write = "        try:\n            self.native.motor.set(value)\n        except RuntimeError:\n            pass"
        gs.edit(directory, "driver.py", "        self.native.set_setpoint(value)", nested_write)
        gs.regenerate(directory)
        return directory

    def test_real_g6_counts_nested_stop_and_write_and_g7_keeps_root_members(self):
        report = gs.check(self.package(), gates=["G1", "G2", "G3", "G6", "G7"])
        self.assertEqual(report["failed"], [], gs.findings(report))

    def test_real_g6_still_rejects_lookup_only_stop(self):
        report = gs.check(self.package(noop_stop=True), gates=["G1", "G2", "G3", "G6"])
        self.assertIn("G6.ESTOP_NO_NATIVE", gs.findings(report, "G6"))

    def test_real_g6_detects_swallowed_nested_failure(self):
        report = gs.check(self.package(swallowed=True), gates=["G1", "G2", "G3", "G6"])
        self.assertIn("G6.FAILURE_HIDDEN", gs.findings(report, "G6"))


if __name__ == "__main__":
    unittest.main()
