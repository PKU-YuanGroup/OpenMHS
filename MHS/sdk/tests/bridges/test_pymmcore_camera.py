"""Primary pixels and retained camera ownership with controlled SDK-local peers."""
import io
import threading
import time
import unittest

import numpy as np
from PIL import Image

from mhs import signals
from mhs.artifacts import ArtifactScope, CONTEXT_KEY, LocalArtifactStore
from mhs.bridge.base import BridgeContext
from mhs.bridge.camera_pixels import detach_pixels
from mhs.bridge.pymmcore_camera import CAPTURE, CameraFactory, PymmcoreCameraBridge
from tests.bridges.pymmcore_fixture import CameraScenario, CameraCore, CameraManager


class CameraPixelsTests(unittest.TestCase):
    def check_pixels(self, value, mode):
        expected = value.copy()
        pixels = detach_pixels(value, pixel_format=mode, width=value.shape[1], height=value.shape[0],
                               max_pixels=10000, max_bytes=100000)
        if value.flags.writeable:
            value[...] = 0
        encoded = pixels.png(100000)
        with Image.open(io.BytesIO(encoded)) as image:
            image.load()
            np.testing.assert_array_equal(np.asarray(image), expected)
            self.assertEqual(image.size, (expected.shape[1], expected.shape[0]))
        return pixels

    def test_complete_mono8_and_rgb8_samples(self):
        for mode, value in (("mono8", np.array([[0, 1, 253], [17, 128, 255]], dtype="u1")),
                            ("rgb8", np.array([[[255, 0, 13], [11, 9, 231], [4, 55, 19]],
                                               [[1, 2, 3], [98, 4, 65], [22, 44, 199]]], dtype="u1"))):
            with self.subTest(mode=mode):
                self.check_pixels(value, mode)

    def test_all_mono16_bits_both_byte_orders(self):
        for dtype in ("<u2", ">u2"):
            with self.subTest(dtype=dtype):
                self.check_pixels(np.array([[0, 1, 255, 256], [1023, 32768, 65535, 4097]], dtype=dtype), "mono16")

    def test_strides_transpose_readonly_and_owned_copy(self):
        for transform in (lambda a: a.T, lambda a: a[::-1, ::-1], lambda a: a[::2, 1::2]):
            with self.subTest(transform=transform):
                self.check_pixels(transform(np.arange(48, dtype="u2").reshape(6, 8)), "mono16")
        source = np.arange(12, dtype="u1").reshape(3, 4)
        readonly = source.view()
        readonly.flags.writeable = False
        pixels = self.check_pixels(readonly, "mono8")
        source[...] = 255
        self.assertEqual(pixels.data, bytes(range(12)))

    def test_invalid_dtype_shape_and_array_hook_never_cast(self):
        class Trap:
            def __array__(self):
                raise AssertionError("must not invoke arbitrary array conversion")
        values = [Trap(), np.zeros((2, 3), dtype="f4"), np.zeros((2, 3), dtype="i2"),
                  np.zeros((2, 3), dtype="u4"), np.zeros((2, 3), dtype=object),
                  np.zeros((2, 3, 4), dtype="u1"), np.zeros((2, 3, 3), dtype="u2"),
                  np.zeros((0, 3), dtype="u1"), np.zeros((3, 2), dtype="u1")]
        for value in values:
            with self.subTest(value=type(value)), self.assertRaises(ValueError):
                detach_pixels(value, pixel_format="mono8", width=3, height=2, max_pixels=6, max_bytes=100)

    def test_png_exact_encoded_byte_limit(self):
        value = np.arange(12, dtype="u1").reshape(3, 4)
        pixels = detach_pixels(value, pixel_format="mono8", width=4, height=3, max_pixels=12, max_bytes=12)
        encoded = pixels.png(4096)
        self.assertEqual(pixels.png(len(encoded)), encoded)
        with self.assertRaises(ValueError):
            pixels.png(len(encoded) - 1)


class CameraLifecycleTests(unittest.TestCase):
    def make(self, frame=None, mode="mono8", **profile):
        scenario = CameraScenario(np.array([[0, 1, 255], [7, 129, 3]], dtype="u1") if frame is None else frame, mode)
        bridge = PymmcoreCameraBridge(scenario.profile(**profile), scenario.factory())
        self.addCleanup(bridge.close)
        store = LocalArtifactStore()
        store.bind("mhs://camera-tests")
        self.addCleanup(store.close)
        return scenario, bridge, store

    def context(self, store, deadline_ms=500, cancel_event=None):
        publisher = store.publisher(ArtifactScope("session", "device", "main", CAPTURE, str(time.monotonic_ns())), lambda: None)
        self.addCleanup(publisher.abort)
        return BridgeContext(deadline_ms=deadline_ms, cancel_event=cancel_event, extra={CONTEXT_KEY: publisher}), publisher

    def capture(self, bridge, store, args=None, deadline_ms=500, cancel_event=None):
        context, publisher = self.context(store, deadline_ms, cancel_event)
        output = bridge.call(CAPTURE, args or {}, context)
        descriptors = publisher.prepare(output)
        publisher.commit()
        data = store.read(output["image_ref"], "session", lambda _: None)["data"]
        return output, descriptors[0], data

    def worker(self, fn):
        result = {}
        def run():
            try:
                result["value"] = fn()
            except BaseException as exc:
                result["error"] = exc
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, result

    def hold(self, scenario, stage):
        entered, release = threading.Event(), threading.Event()
        def hook(*_):
            entered.set()
            if not release.wait(3):
                raise TimeoutError("controlled camera barrier was not released")
        scenario.hooks[stage] = hook
        self.addCleanup(release.set)
        return entered, release

    def joined(self, thread):
        thread.join(1)
        self.assertFalse(thread.is_alive())

    def settle(self, bridge):
        until = time.monotonic() + 1
        while time.monotonic() < until:
            status = bridge.safety_status()
            if not status["pending_native"] and status["request_owner"] is None:
                return
            time.sleep(.002)
        self.fail(f"camera owners did not settle: {bridge.safety_status()}")

    def test_complete_capture_all_three_profiles_and_no_snapshot_exposure(self):
        for mode, frame in (("mono8", np.arange(6, dtype="u1").reshape(2, 3)),
                            ("mono16", np.array([[0, 256, 65535], [1234, 32768, 17]], dtype=">u2")),
                            ("rgb8", np.arange(18, dtype="u1").reshape(2, 3, 3))):
            with self.subTest(mode=mode):
                scenario, bridge, store = self.make(frame, mode)
                self.assertIsNone(bridge.read("main")["width"])
                self.assertEqual(scenario.trace, [])
                output, descriptor, blob = self.capture(bridge, store)
                with Image.open(io.BytesIO(blob)) as image:
                    np.testing.assert_array_equal(np.asarray(image), frame)
                self.assertEqual((output["width"], output["height"]), (3, 2))
                self.assertEqual(scenario.counts("start"), 1)
                self.assertEqual(scenario.counts("acquire_entry"), 1)
                self.assertFalse(bridge.read("main")["acquiring"])
                self.assertEqual(scenario.counts("start"), 1)
                self.assertIn(("stop", "Camera"), scenario.trace)
                self.assertTrue(all(row[2] is False for row in scenario.trace if row[0] == "release"))

    def test_disabled_artifacts_and_invalid_input_do_not_construct(self):
        scenario, bridge, store = self.make()
        for args in ({"format": "jpeg"}, {"camera": "Other"}, {"unknown": 1}):
            with self.assertRaises(Exception):
                self.capture(bridge, store, args)
        with self.assertRaises(Exception):
            bridge.call(CAPTURE, {})
        self.assertEqual(scenario.trace, [])

    def test_geometry_and_exposure_are_pre_capture_assertions(self):
        for args in ({"width": 4}, {"height": True}, {"exposure_ms": 2}):
            with self.subTest(args=args):
                scenario, bridge, store = self.make()
                with self.assertRaises(Exception):
                    self.capture(bridge, store, args)
                self.assertEqual(scenario.counts("start"), 0)
                self.assertEqual(scenario.counts("set_exposure"), 0)

    def test_wrong_native_shape_or_status_never_publishes(self):
        for wrong in ("shape", "cached", "dtype"):
            with self.subTest(wrong=wrong):
                scenario, bridge, store = self.make()
                if wrong == "shape":
                    scenario.hooks["manager_constructed"] = lambda: setattr(scenario.core, "width", 2)
                elif wrong == "cached":
                    scenario.status = "timeout"
                    scenario.hooks["manager_constructed"] = lambda: setattr(scenario.manager, "_latest", scenario.frame)
                else:
                    scenario.frame = scenario.frame.astype("f4")
                with self.assertRaises(Exception):
                    self.capture(bridge, store)
                self.assertEqual(store._grants, {})
                self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_unsupported_preflight_layout_and_foreign_live_owner_no_start(self):
        for kind in ("layout", "running", "claim", "foreign", "shutter", "trigger"):
            with self.subTest(kind=kind):
                scenario, bridge, store = self.make()
                def change():
                    if kind == "layout": scenario.forced_layout = (4, 1)
                    if kind == "running": scenario.core.running = True
                    if kind == "claim": scenario.manager._exclusiveOwner = "GUI"
                    if kind == "foreign": scenario.core.loaded.append("Laser")
                    if kind == "shutter": scenario.core.auto_shutter = True
                    if kind == "trigger": scenario.manager._triggerMode = "external"
                scenario.hooks["manager_constructed"] = change
                with self.assertRaises(Exception):
                    self.capture(bridge, store)
                self.assertEqual(scenario.counts("start"), 0)
                self.assertEqual(scenario.counts("clear"), 0)

    def test_configuration_bounds_readback_and_no_multi_write(self):
        scenario, bridge, store = self.make()
        for value in (True, float("nan"), float("inf"), -1, 101):
            with self.assertRaises(Exception): bridge.write("main", {"exposure_ms": value})
        for patch in ({"gain": 1}, {"binning": 3}, {"roi": {"x": 11, "y": 0, "width": 2, "height": 1}},
                      {"exposure_ms": 2, "binning": 2}):
            with self.assertRaises(Exception): bridge.write("main", patch)
        self.assertEqual(scenario.trace, [])
        self.assertEqual(bridge.write("main", {"exposure_ms": .1})["exposure_ms"], .1)
        self.assertEqual(bridge.write("main", {"exposure_ms": 100})["exposure_ms"], 100)
        self.assertEqual(bridge.write("main", {"binning": 2})["binning"], 2)
        roi = {"x": 1, "y": 2, "width": 3, "height": 2}
        self.assertEqual(bridge.write("main", {"roi": roi})["roi"], roi)
        scenario.fail_readback = True
        with self.assertRaises(Exception): bridge.write("main", {"exposure_ms": 10})
        self.assertEqual(scenario.core.exposure, 100)
        with self.assertRaises(Exception): self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 0)

    def test_pre_cancel_has_zero_native_effects(self):
        scenario, bridge, store = self.make()
        event = threading.Event(); event.set()
        with self.assertRaises(Exception): self.capture(bridge, store, cancel_event=event)
        self.assertEqual(scenario.trace, [])

    def test_timeout_retains_native_owner_and_never_starts_replacement(self):
        scenario, bridge, store = self.make()
        entered, release = self.hold(scenario, "start")
        owner, result = self.worker(lambda: self.capture(bridge, store, deadline_ms=30))
        self.assertTrue(entered.wait(1))
        self.joined(owner)
        self.assertIsInstance(result["error"], signals.OutcomeUnknown)
        retained = bridge._jobs["acquisition"]
        for _ in range(3):
            with self.assertRaises(Exception): self.capture(bridge, store)
            with self.assertRaises(Exception): bridge.reset()
            self.assertIs(bridge._jobs["acquisition"], retained)
        release.set(); self.assertTrue(retained.done.wait(1)); self.settle(bridge)
        self.assertEqual(store._grants, {})
        bridge.safe_state(); bridge.reset()
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        self.capture(bridge, store)
        self.assertEqual(scenario.counts("start"), 2)

    def test_early_stop_then_late_start_requires_post_settlement_stop(self):
        scenario, bridge, store = self.make()
        entered, release = self.hold(scenario, "start")
        owner, result = self.worker(lambda: self.capture(bridge, store))
        self.assertTrue(entered.wait(1))
        with self.assertRaises(Exception): bridge.estop("controlled race")
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])
        with self.assertRaises(Exception): bridge.reset()
        release.set(); self.joined(owner); self.settle(bridge)
        self.assertIn("error", result)
        prior = scenario.counts("stop")
        self.assertEqual(bridge.safe_state(), {"achieved": True})
        self.assertGreater(scenario.counts("stop"), prior)
        self.assertEqual(bridge.reset(), {"reset": True, "resumed": False})
        self.assertEqual(scenario.counts("start"), 1)
        self.assertEqual(store._grants, {})

    def test_stop_timeout_retains_single_owner_and_retries_after_settlement(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        entered, release = self.hold(scenario, "stop")
        with self.assertRaises(Exception): bridge.estop()
        self.assertTrue(entered.is_set())
        retained = bridge._jobs["stop"]
        before = scenario.counts("stop")
        for _ in range(3):
            with self.assertRaises(Exception): bridge.safe_state()
            self.assertIs(bridge._jobs["stop"], retained)
        self.assertEqual(scenario.counts("stop"), before)
        release.set(); self.assertTrue(retained.done.wait(1)); self.settle(bridge)
        bridge.safe_state(); bridge.reset()
        self.assertEqual(scenario.counts("start"), 1)

    def test_historical_native_fault_allows_protection_but_never_reset(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        def fail(*_): raise RuntimeError("native stop failed")
        scenario.hooks["stop"] = fail
        with self.assertRaises(Exception): bridge.estop()
        scenario.hooks.pop("stop")
        before = scenario.counts("stop")
        with self.assertRaises(Exception): bridge.safe_state()
        self.assertGreater(scenario.counts("stop"), before)
        with self.assertRaises(Exception): bridge.reset()
        self.assertFalse(bridge.safety_status()["safe_state"]["achieved"])

    def test_late_constructor_and_close_keep_core_until_owned_cleanup(self):
        scenario, bridge, store = self.make()
        entered, release = self.hold(scenario, "initialize")
        owner, result = self.worker(lambda: self.capture(bridge, store, deadline_ms=30))
        self.assertTrue(entered.wait(1)); self.joined(owner)
        self.assertIs(bridge.lease.core, scenario.core)
        before = time.monotonic(); bridge.close()
        self.assertLess(time.monotonic() - before, .3)
        self.assertFalse(bridge.safety_status()["closed"])
        self.assertEqual(scenario.counts("unload"), 0)
        release.set(); self.settle(bridge)
        self.assertTrue(bridge.safety_status()["closed"])
        self.assertEqual(scenario.counts("core_creation"), 1)
        self.assertEqual(scenario.counts("unload"), 1)
        self.assertEqual(scenario.counts("start"), 0)
        self.assertEqual(store._grants, {})
        old = list(scenario.trace); bridge.close(); self.assertEqual(scenario.trace, old)

    def test_partial_constructor_failures_retain_and_release_registered_core(self):
        for stage in ("load", "initialize", "manager_init", "manager_constructed"):
            with self.subTest(stage=stage):
                scenario, bridge, store = self.make()
                def fail(*_): raise RuntimeError("constructor failure")
                scenario.hooks[stage] = fail
                with self.assertRaises(Exception): self.capture(bridge, store)
                self.assertIs(bridge.lease.core, scenario.core)
                bridge.close(); self.settle(bridge)
                self.assertTrue(bridge.safety_status()["closed"])
                self.assertEqual(scenario.counts("unload"), 1)
                self.assertEqual(scenario.counts("start"), 0)

    def test_close_while_acquiring_keeps_owner_and_disallows_late_pixels(self):
        scenario, bridge, store = self.make()
        entered, release = self.hold(scenario, "pop")
        owner, result = self.worker(lambda: self.capture(bridge, store))
        self.assertTrue(entered.wait(1))
        bridge.close()
        self.assertFalse(bridge.safety_status()["closed"])
        release.set(); self.joined(owner); self.settle(bridge)
        self.assertIn("error", result)
        self.assertTrue(bridge.safety_status()["closed"])
        self.assertEqual(store._grants, {})

    def test_manager_or_core_method_shadow_and_policy_replacement_refused(self):
        for subject in ("manager", "core", "profile"):
            with self.subTest(subject=subject):
                scenario, bridge, store = self.make()
                self.capture(bridge, store)
                if subject == "manager": scenario.manager.acquireSingleFrame = lambda **kw: (scenario.frame, "done")
                if subject == "core": scenario.core.getImageWidth = lambda: 3
                if subject == "profile": bridge.profile = scenario.profile()
                with self.assertRaises(Exception): self.capture(bridge, store)
                self.assertEqual(scenario.counts("start"), 1)

    def test_borrowed_core_and_wrong_receiver_types_are_rejected(self):
        scenario, bridge, store = self.make()
        self.capture(bridge, store)
        def borrowed(lease):
            lease.register_core(scenario.core)
            return scenario.manager
        other = PymmcoreCameraBridge(scenario.profile(), CameraFactory(borrowed, CameraCore, CameraManager))
        self.addCleanup(other.close)
        with self.assertRaises(Exception): self.capture(other, store)
        other.close()
        self.assertEqual(scenario.counts("unload"), 0)
        self.assertEqual(scenario.counts("start"), 1)

    def test_native_backend_refused_before_factory_or_optional_imports(self):
        scenario, bridge, store = self.make()
        for backend in ("hardware", "sim"):
            with self.assertRaises(Exception):
                PymmcoreCameraBridge(scenario.profile(), scenario.factory(), backend=backend)
        self.assertEqual(scenario.trace, [])


if __name__ == "__main__":
    unittest.main()
