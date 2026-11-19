"""Acceptance run of the zscan camera package: the gate, plus cases specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
import importlib.util
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.artifacts import LocalArtifactStore
from mhs.client import InProcessTransport, MHSClient
from mhs.driver import DriverFailed, build_server
from mhs.pixels import PNG_SIGNATURE
from mhs.testing import check_driver

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class CameraCases(unittest.TestCase):
    def serve(self, artifact_store=None):
        server = load(HERE, backend="fake", artifact_store=artifact_store)
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        hello = client.hello()
        device_id = hello["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reads_report_the_configured_allocation(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["configured_width"], state["configured_height"]), (1280, 1024))

    def test_capture_returns_a_png_artifact(self) -> None:
        client = self.serve(artifact_store=LocalArtifactStore())
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((output["width"], output["height"]), (8, 8))   # the fake's placeholder frame
        self.assertEqual(output["media_type"], "image/png")
        self.assertTrue(output["image_ref"].startswith("mhs+artifact://"), output)
        artifact = client.read_artifact(output["image_ref"], session_id=client.session_id)
        self.assertTrue(artifact["data"].startswith(PNG_SIGNATURE), artifact["descriptor"])

    def test_capture_without_an_artifact_store_refuses(self) -> None:
        client = self.serve()
        receipt = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.NOT_READY", receipt)

    def test_estop_latches_and_refuses_the_capture(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["estop"], "software_only", receipt)
        refused = client.invoke("cap.sensing.image.v1", {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP, refused)

    def test_teardown_releases_the_native_camera(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertIsNotNone(driver.native.mem_ptr)
        driver.close()
        self.assertIsNone(driver.native.mem_ptr)
        self.assertIsNone(driver.native.mem_id)


class CameraNativeCases(unittest.TestCase):
    """Exercise only package code with SDK-shaped stubs; never import camera.py or a vendor SDK."""

    class Sdk:
        IS_SUCCESS, IS_CM_MONO8, IS_WAIT = 0, 6, 1  # placeholder status/mode tokens

        def __init__(self, fail=None):
            self.fail = fail
            self.calls = []

        def HIDS(self, value):
            return value

        def c_mem_p(self):
            return object()

        def INT(self):
            return object()

        def status(self, operation):
            self.calls.append(operation)
            return 7 if self.fail == operation else self.IS_SUCCESS  # placeholder failure code

        def is_InitCamera(self, handle, window):
            return self.status("init")

        def is_SetColorMode(self, handle, mode):
            return self.status("mono")

        def is_AllocImageMem(self, handle, width, height, bits, pointer, memory_id):
            return self.status("alloc")

        def is_SetImageMem(self, handle, pointer, memory_id):
            return self.status("active")

        def is_FreezeVideo(self, handle, wait):
            return self.status("freeze")

        def get_data(self, pointer, width, height, bits, pitch, copy):
            self.calls.append("data")
            return [[7]]  # placeholder old buffer contents, not a source-backed image

        def is_FreeImageMem(self, handle, pointer, memory_id):
            return self.status("free")

        def is_ExitCamera(self, handle):
            return self.status("exit")

    def backend(self, sdk):
        spec = importlib.util.spec_from_file_location("zscan_checked_native_test", HERE / "native.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._CheckedCamera(sdk, lambda data, shape: data)

    def test_initialization_failures_are_not_swallowed(self) -> None:
        for operation in ("init", "mono", "alloc", "active"):
            with self.subTest(operation=operation):
                sdk = self.Sdk(fail=operation)
                with self.assertRaises(DriverFailed):
                    self.backend(sdk)
                if operation != "init":
                    self.assertIn("exit", sdk.calls)
                if operation == "active":
                    self.assertIn("free", sdk.calls)

    def test_failed_freeze_never_publishes_old_buffer_as_a_new_image(self) -> None:
        sdk = self.Sdk(fail="freeze")
        driver = load_driver(HERE, "fake")
        driver.native = self.backend(sdk)
        server = build_server(driver, artifact_store=LocalArtifactStore())
        self.addCleanup(close_server, server)
        client = MHSClient(InProcessTransport(server))
        self.addCleanup(client.close)
        device = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device])["session_id"]
        receipt = client.invoke("cap.sensing.image.v1", {}, device_id=device, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.DEVICE.FAULTED")
        self.assertNotIn("data", sdk.calls)
        self.assertNotIn("image_ref", receipt.get("output") or {})

    def test_exit_is_attempted_when_freeing_memory_fails(self) -> None:
        sdk = self.Sdk(fail="free")
        backend = self.backend(sdk)
        with self.assertRaises(DriverFailed):
            backend.release()
        self.assertIn("exit", sdk.calls)

    def test_successful_capture_and_repeated_release(self) -> None:
        sdk = self.Sdk()
        backend = self.backend(sdk)
        self.assertEqual(backend.capture_image(), [[7]])  # placeholder SDK buffer
        backend.release()
        backend.release()
        self.assertEqual(sdk.calls.count("exit"), 1)


if __name__ == "__main__":
    unittest.main()
