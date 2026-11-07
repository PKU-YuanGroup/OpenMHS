"""MuJoCo checkpoint protocol: real served state, validated before native writes."""
from __future__ import annotations

import copy
from concurrent.futures import Future
import threading
import unittest
from types import SimpleNamespace

from mhs import canonical
from mhs.bridge.mujoco import MujocoBridge
from mhs.driver import close_server
from mhs.schema import validate
from tests.bridges import support as bs
from tests.driver import support
from tests.driver.test_families import Pendulums, fake_mujoco_module


def native_with_equality():
    """Controlled native boundary: record unsafe byte conversion, never run C."""
    native = fake_mujoco_module()
    native.mjtState = SimpleNamespace(**vars(native.mjtState))
    native.mjtState.mjSTATE_EQ_ACTIVE = 256
    native.mjtState.mjSTATE_INTEGRATION |= 256
    size, get, put = native.mj_stateSize, native.mj_getState, native.mj_setState
    native.eq_value = 1.0
    native.invalid_dispatches = []

    def state_size(model, mask):
        return size(model, mask & 63) + bool(mask & 256)

    def get_state(model, data, values, mask):
        get(model, data, values, mask & 63)
        if mask & 256:
            values[size(model, mask & 63)] = native.eq_value

    def set_state(model, data, values, mask):
        if mask & 256:
            value = float(values[size(model, mask & 63)])
            if not value.is_integer() or not 0 <= value <= 255:
                native.invalid_dispatches.append(value)
                raise ValueError("controlled native guard: unsafe byte conversion")
            native.eq_value = value
        put(model, data, values, mask & 63)

    native.mj_stateSize, native.mj_getState, native.mj_setState = state_size, get_state, set_state
    return native


class EqualityPendulums(Pendulums):
    backends = {"fake": native_with_equality}


class MujocoEqualityCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.driver = EqualityPendulums(backend="fake")
        self.server, self.client = support.serve(self.driver)
        self.addCleanup(close_server, self.server)
        self.ids = {"session_id": self.client.session_id, "device_id": self.client.device_id, "deadline_ms": 1000}

    def envelope(self, value):
        saved = self.client.rpc("mhs.snapshot", self.ids)
        saved["state"]["world"]["native_checkpoint"]["values"][-1] = value
        saved["snapshot"] = copy.deepcopy(saved["state"])
        saved["state_hash"] = canonical.state_hash(saved["state"]["world"])
        saved["snapshot_digest"] = canonical.digest(saved["state"])
        return saved

    def test_invalid_equality_activation_refuses_before_native_setter(self):
        for value in (0.5, -1.0, 2.0, 255.0, 256.0, 1e300, True):
            with self.subTest(value=value):
                saved = self.envelope(value)
                before = self.driver.native.calls.count("mj_setState")
                result = self.client.rpc("mhs.restore", {**self.ids, "snapshot": saved,
                                                         "command_id": canonical.ulid()})
                self.assertEqual(result["status"], "rejected", result)
                self.assertEqual(self.driver.native.calls.count("mj_setState"), before)
                self.assertEqual(self.driver.native.invalid_dispatches, [])
                self.assertEqual(self.driver.native.eq_value, 1.0)

    def test_numeric_zero_and_one_restore_through_stock_server(self):
        for value in (0.0, 1, 0, 1.0):
            with self.subTest(value=value):
                saved = self.envelope(value)
                result = self.client.rpc("mhs.restore", {**self.ids, "snapshot": saved,
                                                         "command_id": canonical.ulid()})
                self.assertEqual(result["status"], "completed", result)
                self.assertEqual(self.driver.native.eq_value, value)
                self.assertEqual(self.client.read()["state"], saved["state"]["world"])


class MujocoCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.driver = Pendulums(backend="fake")
        self.server, self.client = support.serve(self.driver)
        self.addCleanup(close_server, self.server)
        self.ids = {"session_id": self.client.session_id, "device_id": self.client.device_id, "deadline_ms": 1000}

    def snapshot(self):
        return self.client.rpc("mhs.snapshot", self.ids)

    def restore(self, snapshot):
        return self.client.rpc("mhs.restore", {**self.ids, "snapshot": snapshot, "command_id": canonical.ulid()})

    def advance(self, ticks=2):
        receipt = self.client.command("cap.world.step.v1", {"ticks": ticks, "action": {"ctrl": [0.3, 0.1]}})
        self.assertEqual(receipt["status"], "completed", receipt)
        return receipt

    def test_served_snapshot_and_actual_restored_state_have_identical_hash(self):
        self.advance()
        snapshot = self.snapshot()
        self.assertEqual(snapshot["state"]["world"], self.client.read()["state"])
        schema = self.client.device()["resources"][0]["state_schema"]
        self.assertEqual(validate(snapshot["state"]["world"], schema), [])
        self.assertEqual(snapshot["state_hash"], canonical.state_hash(snapshot["state"]["world"]))
        self.advance(3)
        expected = self.client.read()["state"]
        before = self.client.read()["revision"]
        receipt = self.restore(snapshot)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["state_hash_after"], snapshot["state_hash"])
        self.assertGreater(receipt["state_revision_after"], before)
        self.advance(3)
        self.assertEqual(self.client.read()["state"], expected)

    def test_forward_that_mutates_inputs_is_not_called_during_restore(self):
        data = self.driver.inner._data
        data.qacc_warmstart[:] = [7.0, -3.0]
        self.advance()
        snapshot = self.snapshot()
        self.advance(1)
        original = self.driver.native.mj_forward
        calls = []
        def destructive_forward(model, target):
            calls.append(True)
            target.qacc_warmstart[:] = [99.0, 99.0]
            target.ctrl[:] = [-0.8, -0.4]
            original(model, target)
        self.driver.native.mj_forward = destructive_forward
        receipt = self.restore(snapshot)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(calls, [])
        self.assertEqual(self.client.read()["state"], snapshot["state"]["world"])

    def test_invalid_checkpoint_contents_refuse_before_setter(self):
        self.advance()
        original = self.snapshot()
        cases = {
            "short vector": lambda w: w["native_checkpoint"]["values"].pop(),
            "different profile": lambda w: w["native_checkpoint"].update(profile="unknown"),
            "different signature": lambda w: w["native_checkpoint"].update(signature=0),
            "different engine": lambda w: w["native_checkpoint"].update(engine_version="different"),
            "false dimension": lambda w: w["native_checkpoint"]["dimensions"].__setitem__(0, True),
            "different seed": lambda w: w.update(seed=5),
            "negative tick": lambda w: w.update(tick=-1),
            "false tick": lambda w: w.update(tick=True),
            "extra field": lambda w: w.update(opaque="no"),
            "different public qpos": lambda w: w["qpos"].__setitem__(0, 6.0),
            "different time": lambda w: w.update(time_ms=100),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label):
                snapshot = copy.deepcopy(original)
                mutate(snapshot["state"]["world"])
                snapshot["snapshot"] = copy.deepcopy(snapshot["state"])
                snapshot["state_hash"] = canonical.state_hash(snapshot["state"]["world"])
                snapshot["snapshot_digest"] = canonical.digest(snapshot["state"])
                before = self.driver.native.calls.count("mj_setState")
                receipt = self.restore(snapshot)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(self.driver.native.calls.count("mj_setState"), before)

    def test_basic_profile_restores_nonempty_act_and_exact_native_time(self):
        model = bs.FakeMjModel()
        model.na = 2
        data = bs.FakeMjData(model)
        data.act = [0.1, -0.4]
        data.time = 0.00025
        native = bs.fake_mujoco()
        del native.mj_getState
        bridge = MujocoBridge(prebuilt=(model, data), mujoco=native, seed=17)
        self.addCleanup(bridge.close)
        saved = bridge.snapshot()
        self.assertEqual(saved["world"]["native_checkpoint"]["profile"], "mujoco_basic_v1")
        data.act[:] = [0.9, 0.8]
        data.time = 0.5
        bridge.restore(saved)
        self.assertEqual(data.act, [0.1, -0.4])
        self.assertEqual(data.time, 0.00025)
        self.assertEqual(bridge.read("world"), saved["world"])

    def test_native_size_and_model_timestep_change_fail_before_restore(self):
        saved = self.snapshot()
        before = self.driver.native.calls.count("mj_setState")
        self.driver.inner._model.opt = type("Opt", (), {"timestep": 0.003})()
        receipt = self.restore(saved)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.driver.native.calls.count("mj_setState"), before)

    def test_pending_setter_never_confirms_safe_state_or_allows_reset(self):
        saved = self.snapshot()
        self.advance()
        release = threading.Event()
        done = threading.Event()
        future = Future()
        native_setter = self.driver.native.mj_setState
        def delayed_setter(model, data, values, signature):
            def worker():
                try:
                    release.wait(5)
                    native_setter(model, data, values, signature)
                    future.set_result(None)
                finally:
                    done.set()
            threading.Thread(target=worker, daemon=True).start()
            return future
        self.driver.native.mj_setState = delayed_setter
        try:
            restored = self.restore(saved)
            self.assertEqual(restored["status"], "unknown", restored)
            stop = self.client.rpc("mhs.safety.estop", {**self.ids, "command_id": canonical.ulid(), "reason": "test"})
            self.assertFalse(stop["output"]["safe_state_achieved"], stop)
            reset = self.client.rpc("mhs.safety.reset", {**self.ids, "command_id": canonical.ulid()})
            self.assertEqual(reset["status"], "rejected", reset)
            self.assertFalse(future.done())
        finally:
            release.set()
            self.assertTrue(done.wait(2))
        self.assertFalse(self.driver.inner.safety_status()["safe_state"]["achieved"])

    def test_synchronous_native_setter_retains_lane_after_caller_deadline(self):
        saved = self.snapshot()
        self.advance()
        release = threading.Event()
        entered = threading.Event()
        native_setter = self.driver.native.mj_setState
        def delayed_setter(model, data, values, signature):
            entered.set()
            release.wait(5)
            native_setter(model, data, values, signature)
        self.driver.native.mj_setState = delayed_setter
        try:
            command_id = canonical.ulid()
            response = self.client.call("mhs.restore", {**self.ids, "deadline_ms": 30,
                "snapshot": saved, "command_id": command_id})
            self.assertTrue(entered.is_set())
            if "error" in response:
                self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.OUTCOME.TIMEOUT", response)
                self.assertEqual(response["error"]["data"]["details"]["command_id"], command_id)
            else:
                self.assertEqual(response["result"]["status"], "unknown", response)
            before = self.driver.native.calls.count("mj_step")
            step = self.client.command("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.1, 0.1]}}, deadline_ms=30)
            self.assertNotEqual(step["status"], "completed", step)
            self.assertEqual(self.driver.native.calls.count("mj_step"), before)
            stop = self.client.rpc("mhs.safety.estop", {**self.ids, "command_id": canonical.ulid(), "reason": "test"})
            self.assertFalse(stop["output"]["safe_state_achieved"], stop)
            reset = self.client.rpc("mhs.safety.reset", {**self.ids, "command_id": canonical.ulid()})
            self.assertEqual(reset["status"], "rejected", reset)
        finally:
            release.set()

    def test_descriptor_resolution_is_owned_across_stop_and_reset(self):
        saved = self.snapshot()
        self.advance()
        release, entered = threading.Event(), threading.Event()
        original = self.driver.native
        class NativeProxy:
            def __getattr__(self, name):
                if name == "mj_setState":
                    entered.set()
                    release.wait(5)
                return getattr(original, name)
        self.driver.inner._mujoco = NativeProxy()
        before = original.calls.count("mj_setState")
        result = {}
        def run():
            result["receipt"] = self.restore(saved)
        worker = threading.Thread(target=run)
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            stop = self.client.rpc("mhs.safety.estop", {**self.ids, "command_id": canonical.ulid(), "reason": "test"})
            self.assertFalse(stop["output"]["safe_state_achieved"], stop)
            reset = self.client.rpc("mhs.safety.reset", {**self.ids, "command_id": canonical.ulid()})
            self.assertEqual(reset["status"], "rejected", reset)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertNotEqual(result["receipt"]["status"], "completed", result)
        self.assertEqual(original.calls.count("mj_setState"), before)
        next_step = self.client.command("cap.world.step.v1", {"ticks": 1, "action": {"ctrl": [0.1, 0.1]}})
        self.assertEqual(next_step["status"], "rejected", next_step)

    def test_partial_setter_failure_is_verified_rollback_or_unknown(self):
        saved = self.snapshot()
        native_setter = self.driver.native.mj_setState
        for fail_rollback in (False, True):
            with self.subTest(fail_rollback=fail_rollback):
                self.advance()
                previous = self.client.read()["state"]
                calls = []
                def broken_setter(model, data, values, signature):
                    calls.append(True)
                    if len(calls) == 1:
                        native_setter(model, data, values, signature)
                        raise RuntimeError("native setter failed after mutation")
                    if fail_rollback:
                        raise RuntimeError("rollback cannot be established")
                    native_setter(model, data, values, signature)
                self.driver.native.mj_setState = broken_setter
                try:
                    receipt = self.restore(saved)
                finally:
                    self.driver.native.mj_setState = native_setter
                self.assertEqual(receipt["status"], "unknown" if fail_rollback else "failed", receipt)
                actual = self.client.read()["state"]
                self.assertEqual(receipt["state_hash_after"], canonical.state_hash(actual))
                if not fail_rollback:
                    self.assertEqual(actual, previous)

    def test_nonfinite_boolean_and_oversized_native_values_are_pre_effect_refused(self):
        original = self.driver.snapshot()
        for bad in (float("nan"), float("inf"), True):
            saved = copy.deepcopy(original)
            saved["world"]["native_checkpoint"]["values"][0] = bad
            before = self.driver.native.calls.count("mj_setState")
            with self.assertRaises(Exception) as caught:
                self.driver.restore(saved)
            self.assertEqual(getattr(caught.exception, "code", None), "MHS.CONFLICT.SNAPSHOT_MISMATCH")
            self.assertEqual(self.driver.native.calls.count("mj_setState"), before)
        saved = copy.deepcopy(original)
        saved["world"]["native_checkpoint"]["values"] = [0.0] * 32769
        with self.assertRaises(Exception):
            self.driver.restore(saved)


if __name__ == "__main__":
    unittest.main()
