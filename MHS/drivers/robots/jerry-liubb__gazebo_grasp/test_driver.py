"""Acceptance run of the gazebo_grasp object-state package: the gate plus repository cases.

Add cases, never remove the ``check_driver`` call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class ObjectStateCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def test_object_info_returns_the_origin_pose(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.jerry-liubb.object_info.v1", {"name": "cube1"}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["name"], "cube1")
        self.assertEqual(output["frame_id"], "world")
        self.assertAlmostEqual(output["x"], 0.2)
        self.assertAlmostEqual(output["y"], 0.0)
        self.assertAlmostEqual(output["z"], 0.76)
        self.assertTrue(output["success"])
        self.assertEqual(output["error_code"], 0)

    def test_missing_object_is_a_failed_receipt_without_output(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.jerry-liubb.object_info.v1", {"name": "missing"},
                                **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_objects_topic_subscription_returns_a_sample(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.jerry-liubb.objects.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["name"], "cube1")
        self.assertAlmostEqual(receipt["output"]["z"], 0.76)

    def test_a_silent_topic_waits_and_fails_at_its_deadline(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.silent = True
        with self.assertRaises(MHSError) as caught:
            driver.call("x-cap.jerry-liubb.objects.v1", {})
        self.assertEqual(caught.exception.code, "MHS.DEVICE.NOT_READY")

    def test_a_failed_service_is_not_hidden(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_service = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.jerry-liubb.object_info.v1", {"name": "cube1"})

    def test_an_application_rejection_is_a_failure(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        driver.native.fail_application = True
        with self.assertRaises(DriverFailed):
            driver.call("x-cap.jerry-liubb.object_info.v1", {"name": "cube1"})

    def test_the_estop_latches_extension_observations(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = client.invoke("x-cap.jerry-liubb.object_info.v1", {"name": "cube1"}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
