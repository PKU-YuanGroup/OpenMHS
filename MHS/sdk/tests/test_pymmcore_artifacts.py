"""Stock camera family/server/client/MCP; complete pixels and failed-commit controls."""
import base64
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from mhs import canonical
from mhs.artifacts import ArtifactPublisher, LocalArtifactStore
from mhs.bridge.pymmcore_camera import CAPTURE
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import PymmcorePlusDriver, build_manifest, build_server, close_server
from mhs.errors import MHSError
from mhs.evidence import verify_bundle
from mhs.mcp import MCPPolicy, MCPProjection
from tests.bridges.pymmcore_fixture import CameraScenario

CONFIGURE = "cap.device.configure.v1"


class PymmcoreEndpointTests(unittest.TestCase):
    def make(self, frame=None, mode="mono8", *, store_options=None, with_store=True, overlay=False):
        scenario = CameraScenario(np.array([[0, 255, 3], [7, 128, 13]], dtype="u1") if frame is None else frame, mode)
        class Camera(PymmcorePlusDriver):
            device_id, device_kind, mode, risk = "pymmcore_fixture", "sensor.camera", "hardware", "R0"
            camera_profile = scenario.profile(timeout_ms=2000)
            backends = {"fake": scenario.factory}
        store = LocalArtifactStore(**(store_options or {})) if with_store else None
        site = {"openmhs": "0.9", "site": "controlled-camera", "issued_by": {"id": "operator:fixture"},
                "issued_at": "2026-11-04T00:00:00Z", "devices": {
                    "mhs://localhost/pymmcore_fixture": {
                        "exposure_ms": {"min": .1, "max": 10, "unit": "ms", "source": "operator"},
                        "binning": {"min": 1, "max": 2, "unit": "1", "source": "operator"},
                        "roi.x": {"min": 0, "max": 11, "unit": "1", "source": "operator"},
                        "roi.y": {"min": 0, "max": 7, "unit": "1", "source": "operator"},
                        "roi.width": {"min": 1, "max": 12, "unit": "1", "source": "operator"},
                        "roi.height": {"min": 1, "max": 8, "unit": "1", "source": "operator"},
                        CAPTURE: {"width": {"min": 1, "max": 12, "unit": "1", "source": "operator"},
                                  "height": {"min": 1, "max": 8, "unit": "1", "source": "operator"},
                                  "exposure_ms": {"min": .1, "max": 10, "unit": "ms", "source": "operator"}}}}} if overlay else None
        driver = Camera()
        server = build_server(driver, artifact_store=store, site_limits=site)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server)); client.hello()
        device = next(iter(server.devices))
        client.open_session([device], capabilities=[CAPTURE, CONFIGURE])
        return scenario, driver, store, server, client, device

    def projection(self, client):
        projection = MCPProjection(client, policy=MCPPolicy(enabled=True, allow_hardware=False))
        self.addCleanup(projection.close)
        self.rpc(projection, "initialize", {"protocolVersion": "2025-11-25", "capabilities": {},
                                           "clientInfo": {"name": "camera-tests", "version": "1"}})
        tools = self.rpc(projection, "tools/list")["result"]["tools"]
        return projection, next(x["name"] for x in tools if x["name"].endswith("sensing_image"))

    def rpc(self, projection, method, params=None):
        return projection.handle_message({"jsonrpc": "2.0", "id": canonical.ulid(), "method": method, "params": params or {}})

    def test_complete_primary_pixels_through_mcp_and_evidence(self):
        values = [("mono8", np.array([[0, 255, 17], [128, 13, 1]], dtype="u1")),
                  ("mono16", np.array([[0, 255, 256], [1023, 32768, 65535]], dtype=">u2")),
                  ("rgb8", np.array([[[255, 0, 3], [11, 9, 231], [14, 16, 18]],
                                      [[19, 17, 15], [13, 11, 9], [7, 5, 3]]], dtype="u1"))]
        for mode, value in values:
            with self.subTest(mode=mode):
                scenario, driver, store, server, client, device = self.make(value, mode)
                self.assertEqual(scenario.trace, [])
                projection, tool = self.projection(client)
                result = self.rpc(projection, "tools/call", {"name": tool, "arguments": {}})["result"]
                receipt = result["structuredContent"]["receipt"]
                self.assertEqual(receipt["status"], "completed", receipt)
                descriptor = receipt["artifacts"][0]
                links = [item for item in result["content"] if item["type"] == "resource_link"]
                self.assertEqual([x["uri"] for x in links], [descriptor["uri"]])
                contents = self.rpc(projection, "resources/read", {"uri": descriptor["uri"]})["result"]["contents"]
                blob = base64.b64decode(contents[0]["blob"], validate=True)
                with Image.open(io.BytesIO(blob)) as image:
                    np.testing.assert_array_equal(np.asarray(image), value)
                    self.assertEqual(image.size, (3, 2))
                self.assertEqual(descriptor["digest"], "sha256:" + hashlib.sha256(blob).hexdigest())
                self.assertEqual(descriptor["size_bytes"], len(blob))
                self.assertEqual(receipt["output"]["exposure_ms"], 1)
                self.assertTrue(verify_bundle(client.export_evidence()).valid)
                client.read("main", device_id=device)
                self.assertEqual(scenario.counts("start"), 1)
                binding = next(b for b in build_manifest(driver)["capabilities"] if b["capability_id"] == CAPTURE)
                self.assertTrue(binding["exclusive"])
                self.assertFalse(binding["constraints"]["cancellable"])

    def test_replay_keeps_original_artifact_expiry_and_one_exposure(self):
        scenario, driver, store, server, client, device = self.make()
        command = canonical.ulid()
        first = client.invoke(CAPTURE, {}, command_id=command, device_id=device)
        second = client.invoke(CAPTURE, {}, command_id=command, device_id=device)
        self.assertEqual(first["receipt_id"], second["receipt_id"])
        self.assertEqual(first["artifacts"], second["artifacts"])
        self.assertEqual(scenario.counts("start"), 1)

    def test_disabled_or_known_full_store_refuses_before_exposure(self):
        scenario, driver, store, server, client, device = self.make(with_store=False)
        receipt = client.invoke(CAPTURE, {}, device_id=device)
        self.assertNotEqual(receipt["status"], "completed")
        self.assertEqual(scenario.trace, [])
        scenario, driver, store, server, client, device = self.make(store_options={"max_artifacts": 1})
        first = client.invoke(CAPTURE, {}, device_id=device)
        self.assertEqual(first["status"], "completed", first)
        old = copy.deepcopy(first["artifacts"])
        second = client.invoke(CAPTURE, {}, device_id=device)
        self.assertNotEqual(second["status"], "completed")
        self.assertNotIn("artifacts", second)
        self.assertEqual(first["artifacts"], old)
        self.assertTrue(client.read_artifact(old[0]["uri"], session_id=client.session_id)["data"])
        self.assertEqual(scenario.counts("start"), 1)

    def test_wrong_session_foreign_endpoint_expiry_and_close(self):
        now = [0.0]
        scenario, driver, store, server, client, device = self.make(store_options={"ttl_s": 1, "clock": lambda: now[0]})
        receipt = client.invoke(CAPTURE, {}, device_id=device)
        uri = receipt["output"]["image_ref"]
        other = MHSClient(InProcessTransport(server)); other.hello(); other.open_session([device], capabilities=[CAPTURE])
        with self.assertRaises(MHSError): other.read_artifact(uri, session_id=other.session_id)
        with self.assertRaises(MHSError): client.read_artifact(uri.replace("localhost", "foreign"), session_id=client.session_id)
        self.assertTrue(client.read_artifact(uri, session_id=client.session_id)["data"])
        now[0] = 2
        with self.assertRaises(MHSError): client.read_artifact(uri, session_id=client.session_id)
        close_server(server)
        self.assertTrue(driver.inner.safety_status()["closed"])
        self.assertEqual(scenario.counts("unload"), 1)

    def test_operator_configuration_limits_reject_before_native_write(self):
        scenario, driver, store, server, client, device = self.make()
        receipt = client.invoke(CONFIGURE, {"exposure_ms": 2}, device_id=device)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(scenario.counts("set_exposure"), 0)
        scenario, driver, store, server, client, device = self.make(overlay=True)
        for value in (.1, 10):
            result = client.invoke(CONFIGURE, {"exposure_ms": value}, device_id=device)
            self.assertEqual(result["status"], "completed", result)
            self.assertEqual(scenario.core.exposure, value)
        before = scenario.counts("set_exposure")
        result = client.invoke(CONFIGURE, {"exposure_ms": 11}, device_id=device)
        self.assertEqual(result["status"], "rejected", result)
        self.assertEqual(scenario.counts("set_exposure"), before)

    def test_capture_assertions_need_capability_scoped_operator_limits(self):
        scenario, driver, store, server, client, device = self.make()
        initial = client.read("main", device_id=device)["state"]
        self.assertIsNone(initial["binning"])
        self.assertTrue(initial["state_stale"])
        for args in ({"width": 3}, {"height": 2}, {"exposure_ms": 1}):
            result = client.invoke(CAPTURE, args, device_id=device)
            self.assertEqual(result["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", result)
        self.assertEqual(scenario.trace, [])
        scenario, driver, store, server, client, device = self.make(overlay=True)
        result = client.invoke(CAPTURE, {"width": 3, "height": 2, "exposure_ms": 1}, device_id=device)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(scenario.counts("start"), 1)
        before = list(scenario.trace)
        for args in ({"width": 13}, {"height": 9}, {"exposure_ms": 11}):
            result = client.invoke(CAPTURE, args, device_id=device)
            self.assertEqual(result["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", result)
        self.assertEqual(scenario.trace[:len(before)], before)
        self.assertTrue(all(item[0] in {"devices", "geometry", "exposure_read", "running"}
                            for item in scenario.trace[len(before):]), scenario.trace[len(before):])

    def test_binning_and_roi_limits_precede_any_configuration_effect(self):
        scenario, driver, store, server, client, device = self.make()
        roi = {"x": 1, "y": 2, "width": 3, "height": 2}
        for value in ({"binning": 2}, {"roi": roi}):
            result = client.write("main", value, device_id=device)
            self.assertEqual(result["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", result)
        self.assertEqual(scenario.trace, [])
        scenario, driver, store, server, client, device = self.make(overlay=True)
        for value in ({"binning": 2}, {"roi": roi}):
            result = client.write("main", value, device_id=device)
            self.assertEqual(result["status"], "completed", result)
        self.assertEqual((scenario.core.binning, scenario.core.roi), (2, (1, 2, 3, 2)))
        before = list(scenario.trace)
        for value in ({"binning": 3}, {"roi": roi | {"x": 12}}):
            result = client.write("main", value, device_id=device)
            self.assertEqual(result["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", result)
        self.assertEqual(scenario.trace[:len(before)], before)
        self.assertTrue(all(item[0] in {"devices", "geometry", "exposure_read", "running"}
                            for item in scenario.trace[len(before):]), scenario.trace[len(before):])

    def test_public_non_cancellable_owner_is_retained_and_estop_still_attempts(self):
        scenario, driver, store, server, client, device = self.make()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def hold():
            entered.set()
            if not release.wait(3): raise TimeoutError("pop was not released")
        scenario.hooks["pop"] = hold
        early = client.invoke(CAPTURE, {}, device_id=device, deadline_ms=40)
        self.assertTrue(entered.wait(1)); self.assertEqual(early["status"], "unknown", early)
        operation = server._operations[early["operation_id"]]
        retained = driver.inner._jobs["acquisition"]
        try:
            with self.assertRaises(MHSError) as refused:
                client.cancel(early["operation_id"])
            self.assertEqual(refused.exception.code, "MHS.OPERATION.NOT_CANCELLABLE")
            self.assertFalse(operation.cancel_event.is_set())
            self.assertIs(driver.inner._jobs["acquisition"], retained)
            before = scenario.counts("stop")
            stopped = client.estop("controlled camera stop", device_id=device)
            self.assertFalse(stopped["output"]["safe_state_achieved"])
            self.assertGreater(scenario.counts("stop"), before)
        finally:
            release.set()
            self.assertTrue(operation.done.wait(1))
        self.assertNotEqual(operation.final_receipt["status"], "completed")
        self.assertEqual(store._grants, {})
        self.assertEqual(scenario.counts("start"), 1)

    def test_estop_after_staging_discards_grant_before_commit(self):
        scenario, driver, store, server, client, device = self.make()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        original = ArtifactPublisher.publish
        staged = []
        def blocked(publisher, *args):
            descriptor = original(publisher, *args)
            staged.append(descriptor)
            entered.set()
            if not release.wait(3): raise TimeoutError("publication was not released")
            return descriptor
        with patch.object(ArtifactPublisher, "publish", blocked):
            early = client.invoke(CAPTURE, {}, device_id=device, deadline_ms=40)
            self.assertTrue(entered.is_set())
            with self.assertRaises(MHSError): client.read_artifact(staged[0]["uri"], session_id=client.session_id)
            client.estop("staged camera image", device_id=device)
            release.set()
            operation = server._operations[early["operation_id"]]
            self.assertTrue(operation.done.wait(1))
        self.assertNotEqual(operation.final_receipt["status"], "completed")
        self.assertNotIn("artifacts", operation.final_receipt)
        self.assertEqual(store._grants, {})

    def test_failed_evidence_commit_never_activates_grant(self):
        scenario, driver, store, server, client, device = self.make()
        original = server._record_receipt
        def fail_image(receipt):
            if receipt.get("artifacts"):
                raise RuntimeError("controlled evidence commit failure")
            return original(receipt)
        with patch.object(server, "_record_receipt", fail_image):
            result = client.invoke(CAPTURE, {}, device_id=device)
        self.assertNotEqual(result["status"], "completed", result)
        self.assertNotIn("artifacts", result)
        self.assertEqual(store._grants, {})

    def test_model_and_policy_identity_cannot_change_after_resolution(self):
        for mutation in ("model", "profile", "backend"):
            with self.subTest(mutation=mutation):
                scenario, driver, store, server, client, device = self.make()
                if mutation == "model": driver._model = copy.deepcopy(driver._model)
                if mutation == "profile": driver._camera_profile = scenario.profile(timeout_ms=2000)
                if mutation == "backend": driver.backend = "hardware"
                with self.assertRaises(Exception): driver.call(CAPTURE, {})
                self.assertEqual(scenario.trace, [])

    def test_native_and_runtime_hook_overrides_are_refused(self):
        scenario, driver, store, server, client, device = self.make()
        for backend in ("hardware", "sim"):
            instance = type(driver)(backend=backend)
            with self.assertRaises(Exception): instance.open()
            self.assertEqual(scenario.trace, [])
        class Override(type(driver)):
            def open_native(self):
                raise AssertionError("bypass must be rejected before runtime")
        with self.assertRaises(Exception): Override()

    def test_base_import_requires_no_numpy_pillow_or_native_dependency(self):
        root = Path(__file__).resolve().parents[1] / "src"
        code = ("import sys;sys.path.insert(0," + repr(str(root)) + ");"
                "import mhs.driver;from mhs.bridge import pymmcore_camera;"
                "assert not any(k.split('.')[0] in {'numpy','PIL','pymmcore','pymmcore_plus','imswitch'} for k in sys.modules)")
        result = subprocess.run([sys.executable, "-S", "-c", code], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
