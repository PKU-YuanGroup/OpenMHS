"""The acceptance gate owns bounded artifact stores for image-producing fakes."""
from __future__ import annotations

import base64
import hashlib
import unittest
from unittest.mock import patch

from mhs.artifacts import DEFAULT_ARTIFACT_BYTES, LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver.check import _Context, stable_digest
from mhs.errors import MHSError
from mhs.mcp import MCPPolicy, MCPProjection
from tests.driver import gate_support as gs

CAP = "cap.sensing.image.v1"
FRAME = b"\x00\x23\x56\xff"
MEDIA = "application/vnd.openmhs.test-raw8"

DRIVER = '''from mhs.driver import Driver, Field, Limit, action, estop, read, reset, write
from mhs.artifacts import publisher_from_context
from mhs.errors import MHSError

class Camera(Driver):
    device_id, device_kind, mode, risk = "gate-camera", "sensor.camera", "hardware", "R1"
    native = "camera:Camera"
    backends = {"fake": ".fake:FakeCamera", "hardware": ".native:connect"}
    safe_state = "Capture stopped"

    @read("exposure_ms", unit="ms", description="Exposure duration")
    def exposure(self):
        return self.native.get_exposure()

    @write("exposure_ms", unit="ms", description="Exposure duration",
           limit=Limit(min=1, max=20, source="upstream_code", ref="camera.py:1"))
    def set_exposure(self, value):
        self.native.set_exposure(value)

    @action(cap="cap.sensing.image.v1", description="Capture a synthetic four-pixel image",
            input={"exposure_ms": Field(unit="ms", description="Exposure duration",
                   limit=Limit(min=1, max=20, source="upstream_code", ref="camera.py:1"))})
    def capture(self, exposure_ms=None):
        publisher = publisher_from_context(self.ctx)
        if publisher is None:
            raise MHSError("MHS.DEVICE.NOT_READY", "An endpoint artifact store is required")
        if exposure_ms is not None:
            self.native.set_exposure(exposure_ms)
        data = self.native.capture()
        artifact = publisher.publish(data, "application/vnd.openmhs.test-raw8")
        return {"image_ref": artifact["uri"], "width": 2, "height": 2,
                "media_type": "application/vnd.openmhs.test-raw8"}

    @estop
    def stop(self):
        self.native.stop()

    @reset
    def reset_camera(self):
        self.native.reset()
'''
NATIVE = '''# Synthetic source contract: exposure duration is 1 to 20 ms.
class Camera:
    def __init__(self):
        self.exposure = 5.0
        self.stopped = False
    def get_exposure(self):
        return self.exposure
    def set_exposure(self, value):
        if self.stopped:
            raise RuntimeError("camera stopped")
        self.exposure = value
    def capture(self):
        if self.stopped:
            raise RuntimeError("camera stopped")
        return b"\\x00\\x23\\x56\\xff"
    def stop(self):
        self.stopped = True
    def reset(self):
        self.stopped = False
'''


def image_package(test):
    directory = gs.copy_tutorial(test)
    (directory / "driver.py").write_text(DRIVER)
    (directory / "vendor" / "camera.py").write_text(NATIVE)
    (directory / "fake.py").write_text(NATIVE.replace("class Camera:", "class FakeCamera:"))
    (directory / "native.py").write_text(
        'def connect(**options):\n    raise AssertionError("Hardware factory must never run in the gate")\n')
    gs.edit_json(directory, "task.json", safety={"expected_mode": "hardware", "risk_floor": "R1"},
                 entry_symbols=[{"symbol": "camera:Camera", "file": "camera.py", "line": 2, "confidence": "ast"}])
    gs.edit_json(directory, "driver.lock.json", backends={"hardware": ".native:connect", "fake": ".fake:FakeCamera"})
    gs.edit_json(directory, "site-limits.example.json", devices={
        "mhs://localhost/gate-camera": {CAP: {"exposure_ms": {"min": 2, "max": 19, "unit": "ms",
            "source": "operator", "reason": "Synthetic gate test overlay"}}}})
    gs.regenerate(directory)
    return directory


class GateArtifactTests(unittest.TestCase):
    def context(self, directory=None):
        ctx = _Context(directory or image_package(self), "fake", None, None, False)
        self.addCleanup(ctx.close)
        self.assertIsNone(ctx.import_error)
        self.assertIsNone(ctx.model_error)
        return ctx

    def client(self, server):
        client = MHSClient(InProcessTransport(server))
        client.hello()
        device_id = next(iter(server.devices))
        client.open_session([device_id], capabilities=[CAP])
        return client, device_id

    def projection(self, server):
        client = MHSClient(InProcessTransport(server))
        client.hello()
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)
        self.rpc(projection, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                 "clientInfo": {"name": "gate-artifact-test", "version": "1"}})
        return projection

    @staticmethod
    def rpc(projection, method, params=None):
        return projection.handle_message({"jsonrpc": "2.0", "id": method, "method": method,
                                          "params": params or {}})

    def test_complete_image_package_g6_g8_and_every_store_is_fresh_and_closed(self):
        directory = image_package(self)
        stores = []
        # Observe construction through the trusted gate helper, leaving the SDK class intact.
        original = _Context._artifact_store
        def observe(driver):
            store = original(driver)
            if store is not None:
                stores.append(store)
            return store
        with patch.object(_Context, "_artifact_store", staticmethod(observe)):
            report = gs.check(directory)
        self.assertTrue(report["passed"], report)
        self.assertEqual(gs.statuses(report)["G6"], "pass")
        self.assertEqual(gs.statuses(report)["G8"], "pass")
        self.assertGreater(len(stores), 5)
        self.assertEqual(len(stores), len({id(store) for store in stores}))
        for store in stores:
            self.assertEqual(store.max_artifact_bytes, DEFAULT_ARTIFACT_BYTES)
            self.assertEqual(store.max_total_bytes, 32 * 1024 * 1024)
            self.assertEqual(store.max_artifacts, 128)
            self.assertEqual(store.ttl_s, 300)
            self.assertTrue(store._closed)
            self.assertFalse(store._root.exists())

    def test_isolated_cli_gate_and_repository_harness_can_publish(self):
        directory = image_package(self)
        done = gs.run_cli("check", str(directory), "--backend", "fake")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        import json
        report = json.loads((directory / "check-report.json").read_text())
        self.assertEqual(report["failed"], [])
        self.assertEqual(gs.statuses(report)["G9"], "pass")
        self.assertEqual(report["evidence_state"], "contract_checked")

    def test_g6_endpoint_and_g8_factory_publish_authorized_bytes_and_mcp_digest(self):
        ctx = self.context()
        for factory in (ctx.endpoint, ctx.server_factory()):
            with self.subTest(factory=factory):
                opened = factory()
                server, close = opened if isinstance(opened, tuple) else (opened.server, opened.close)
                self.addCleanup(close)
                projection = self.projection(server)
                tools = self.rpc(projection, "tools/list")["result"]["tools"]
                tool = next(t["name"] for t in tools if t["name"].endswith("sensing_image"))
                result = self.rpc(projection, "tools/call", {"name": tool, "arguments": {}})["result"]
                receipt = result["structuredContent"]["receipt"]
                self.assertEqual(receipt["status"], "completed", receipt)
                artifact = receipt["artifacts"][0]
                response = self.rpc(projection, "resources/read", {"uri": artifact["uri"]})
                content = response["result"]["contents"][0]
                self.assertEqual(base64.b64decode(content["blob"], validate=True), FRAME)
                self.assertEqual(artifact["digest"], "sha256:" + hashlib.sha256(FRAME).hexdigest())
                self.assertEqual(artifact["size_bytes"], len(FRAME))
                self.assertEqual(content["mimeType"], MEDIA)
                foreign, _ = self.client(server)
                with self.assertRaises(MHSError):
                    foreign.read_artifact(artifact["uri"], session_id=foreign.session_id)
                for uri in ("file:///etc/passwd", "https://example.invalid/frame.raw"):
                    self.assertIn("error", self.rpc(projection, "resources/read", {"uri": uri}))
                store = server._artifact_store
                close()
                self.assertTrue(store._closed)
                self.assertFalse(store._root.exists())
                self.assertIn("error", self.rpc(projection, "resources/read", {"uri": artifact["uri"]}))

    def test_hardware_view_serves_only_fake_native_and_owns_store(self):
        endpoint = self.context().hardware_endpoint()
        self.addCleanup(endpoint.close)
        self.assertEqual(endpoint.server.devices[endpoint.device_id].mode, "hardware")
        receipt = endpoint.session.command(CAP, {})
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.AUTH.HARDWARE_DISABLED")
        # An explicit test operator arms only this fake-backed hardware view;
        # construction must retain the real server's default arming restriction.
        endpoint.server.armed = True
        receipt = endpoint.session.command(CAP, {})
        self.assertEqual(receipt["status"], "completed", receipt)
        client = MHSClient(InProcessTransport(endpoint.server))
        data = client.read_artifact(receipt["output"]["image_ref"], session_id=endpoint.session.session_id)
        self.assertEqual(data["data"], FRAME)
        store = endpoint.server._artifact_store
        endpoint.close()
        self.assertFalse(store._root.exists())

    def test_default_size_limit_refuses_without_grant_or_orphan_file(self):
        ctx = self.context()
        endpoint = ctx.endpoint()
        self.addCleanup(endpoint.close)
        driver = endpoint.server.devices[endpoint.device_id].bridge
        fake_cls = type(object.__getattribute__(driver._native_value, "_mhs_target"))
        with patch.object(fake_cls, "capture", return_value=b"x" * (DEFAULT_ARTIFACT_BYTES + 1)):
            receipt = endpoint.session.command(CAP, {})
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertNotIn("artifacts", receipt)
        store = endpoint.server._artifact_store
        self.assertEqual(store._grants, {})
        self.assertEqual(list(store._root.iterdir()), [])

    def test_failure_cleanup_for_constructor_harness_session_and_restore(self):
        for kind in ("endpoint", "hardware_endpoint", "server_factory"):
            stages = ("constructor",) if kind == "server_factory" else ("constructor", "harness", "session", "restore")
            for stage in stages:
                with self.subTest(kind=kind, stage=stage):
                    ctx = self.context()
                    driver = ctx.open_driver()
                    self.addCleanup(driver.close)
                    stores = []
                    original = _Context._artifact_store
                    def observe(candidate):
                        store = original(candidate)
                        stores.append(store)
                        return store
                    construct = ((lambda: ctx.server_factory()()) if kind == "server_factory" else getattr(ctx, kind))
                    target = ("mhs.server.MHSServer" if kind == "hardware_endpoint" else "mhs.driver.build.build_server")
                    targets = {"constructor": target, "harness": "mhs.conformance.inprocess.Harness",
                               "session": "mhs.driver.behaviour.Session"}
                    with patch.object(ctx, "open_driver", return_value=driver), \
                         patch.object(_Context, "_artifact_store", staticmethod(observe)), \
                         patch.object(driver, "close", wraps=driver.close) as closed:
                        if stage == "restore":
                            opened = construct()
                            with patch.object(opened.harness, "restore", side_effect=RuntimeError("restore failed")):
                                with self.assertRaisesRegex(RuntimeError, "restore failed"):
                                    opened.close()
                        else:
                            with patch(targets[stage], side_effect=RuntimeError("controlled construction failure")):
                                with self.assertRaisesRegex(RuntimeError, "controlled construction failure"):
                                    construct()
                        self.assertEqual(closed.call_count, 1)
                    self.assertEqual(len(stores), 1)
                    self.assertTrue(stores[0]._closed)
                    self.assertFalse(stores[0]._root.exists())

    def test_driver_cleanup_error_cannot_leak_a_store_after_construction_failure(self):
        for kind in ("endpoint", "hardware_endpoint", "server_factory"):
            with self.subTest(kind=kind):
                ctx = self.context()
                driver = ctx.open_driver()
                self.addCleanup(driver.close)
                store = LocalArtifactStore()
                self.addCleanup(store.close)
                target = ("mhs.server.MHSServer" if kind == "hardware_endpoint" else "mhs.driver.build.build_server")
                construct = (lambda: ctx.server_factory()()) if kind == "server_factory" else getattr(ctx, kind)
                with patch.object(ctx, "open_driver", return_value=driver), \
                     patch.object(_Context, "_artifact_store", staticmethod(lambda candidate: store)), \
                     patch.object(driver, "close", side_effect=RuntimeError("driver cleanup failed")), \
                     patch(target, side_effect=RuntimeError("construction failed")):
                    with self.assertRaisesRegex(RuntimeError, "driver cleanup failed"):
                        construct()
                self.assertTrue(store._closed)
                self.assertFalse(store._root.exists())

    def test_non_image_gate_digest_and_manifests_do_not_depend_on_storage(self):
        directory = gs.copy_tutorial(self)
        with patch.object(_Context, "_artifact_store", staticmethod(lambda driver: None)):
            baseline = gs.check(directory)
        with patch("mhs.artifacts.LocalArtifactStore", side_effect=AssertionError("no allocation for non-images")):
            current = gs.check(directory)
        self.assertTrue(baseline["passed"], baseline)
        self.assertTrue(current["passed"], current)
        self.assertEqual(stable_digest(baseline), stable_digest(current))

    def test_terminal_stop_reset_refusal_remains_a_g8_failure(self):
        directory = image_package(self)
        gs.edit(directory, "driver.py", "        self.native.reset()",
                '        raise MHSError("MHS.SAFETY.RESET_REFUSED", "New endpoint required after closing")')
        gs.regenerate(directory)
        report = gs.check(directory, gates=("G3", "G6", "G8"))
        self.assertFalse(report["passed"])
        self.assertEqual(gs.statuses(report)["G6"], "pass")
        self.assertEqual(gs.statuses(report)["G8"], "fail")
        self.assertIn(("G8.TEST", "TSAFE-001"), gs.coded(report, "G8"))


if __name__ == "__main__":
    unittest.main()
