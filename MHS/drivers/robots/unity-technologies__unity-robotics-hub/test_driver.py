"""Acceptance run of the Unity Niryo pick-and-place planner package: the gate plus repository cases.

Add cases, never remove the ``check_driver`` call. The fake is the package's own recording transport
(``fake.py``); the pose values below are test data.
"""

import importlib
import math
import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import DriverFailed
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SITE = HERE / "site-limits.example.json"
CAPABILITY = "x-cap.unity-technologies.niryo_pick_place_plan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
JOINTS = ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"]
URDF = "tutorials/pick_and_place/ROS/src/niryo_one_urdf/niryo_one.urdf.xacro"


def request(start=(0, 0, 0, 0, 0, 0)):
    return {
        "start_joints_rad": list(start),
        "pick_position": [0.2, 0.1, 0.3],
        "pick_orientation": [0.0, 0.0, 0.0, 1.0],
        "place_position": [0.2, -0.1, 0.3],
        "place_orientation": [0.0, 0.0, 0.0, 1.0],
    }


def fake_module():
    """The package's fake.py, imported through the loaded driver's package."""
    cls = type(load_driver(HERE, backend="fake"))
    return importlib.import_module(cls.__module__.rsplit(".", 1)[0] + ".fake")


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PlannerCases(unittest.TestCase):
    def serve(self, site_limits=SITE):
        self.fake = fake_module().FakeNiryoMoverService()
        server = load(HERE, backend="fake", site_limits=site_limits, native=self.fake)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def driver(self):
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        return driver

    def test_a_plan_has_four_trajectories_of_the_six_arm_joints(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertIs(output["executed"], False)
        self.assertEqual(len(output["joint_names"]), 4)
        self.assertEqual(len(output["points"]), 4)
        for names, points in zip(output["joint_names"], output["points"]):
            self.assertEqual(names, JOINTS)
            self.assertTrue(points)
            for point in points:
                self.assertEqual(len(point["positions"]), 6)
                self.assertEqual(set(point["time_from_start"]), {"secs", "nsecs"})

    def test_the_request_carries_radians_and_leaves_the_poses_unchanged(self) -> None:
        driver = self.driver()
        start = (0.2, 0.1, -0.5, 0.3, -0.4, 0.5)
        driver.call(CAPABILITY, request(start=start))
        [call] = driver.native.calls
        self.assertEqual(call["service"], "/niryo_moveit")
        self.assertEqual(call["type"], "niryo_moveit/MoverService")
        args = call["args"]
        self.assertEqual(sorted(args), ["joints_input", "pick_pose", "place_pose"])
        self.assertEqual(args["joints_input"], {"joints": list(start)})
        self.assertEqual(args["pick_pose"], {"position": {"x": 0.2, "y": 0.1, "z": 0.3},
                                             "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}})
        self.assertEqual(args["place_pose"], {"position": {"x": 0.2, "y": -0.1, "z": 0.3},
                                              "orientation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}})

    def test_the_first_plan_starts_at_the_requested_radians_unchanged(self) -> None:
        driver = self.driver()
        start = (0.2, 0.1, -0.5, 0.3, -0.4, 0.5)
        output = driver.call(CAPABILITY, request(start=start))
        first = output["points"][0][0]["positions"]
        for got, want in zip(first, start):
            self.assertEqual(got, want)
        self.assertNotEqual(first, [math.radians(value) for value in start])

    def test_each_plan_starts_where_the_previous_ends(self) -> None:
        driver = self.driver()
        output = driver.call(CAPABILITY, request())
        for before, after in zip(output["points"], output["points"][1:]):
            self.assertEqual(before[-1]["positions"], after[0]["positions"])

    def test_a_failed_plan_is_a_failed_receipt_without_output(self) -> None:
        client = self.serve()
        self.fake.fail_planning = True
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_an_empty_trajectory_list_is_a_failed_receipt(self) -> None:
        client = self.serve()
        self.fake.empty_response = True
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)
        self.assertIsNone(receipt.get("output"))

    def test_a_short_answer_is_a_failed_receipt(self) -> None:
        client = self.serve()
        self.fake.short_response = True
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)

    def test_a_foreign_joint_is_a_failed_receipt(self) -> None:
        client = self.serve()
        self.fake.foreign_joint = True
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)

    def test_a_point_without_six_positions_is_a_failed_receipt(self) -> None:
        client = self.serve()
        self.fake.truncated_point = True
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.OUTPUT_INVALID", receipt)

    def test_the_published_output_contract_fixes_four_plans_of_six_joints(self) -> None:
        client = self.serve()
        [entry] = client.inspect(self.ids["device_id"])["capabilities"]
        output = entry["output_schema"]
        self.assertEqual(output["required"], ["joint_names", "points", "executed"])
        names = output["properties"]["joint_names"]
        self.assertEqual((names["minItems"], names["maxItems"]), (4, 4))
        self.assertEqual((names["items"]["minItems"], names["items"]["maxItems"]), (6, 6))
        self.assertEqual(names["items"]["items"]["enum"], JOINTS)
        points = output["properties"]["points"]
        self.assertEqual((points["minItems"], points["maxItems"]), (4, 4))
        self.assertEqual(points["items"]["minItems"], 1)
        positions = points["items"]["items"]["properties"]["positions"]
        self.assertEqual((positions["minItems"], positions["maxItems"], positions["items"]["x-mhs-unit"]),
                         (6, 6, "rad"))
        self.assertEqual(output["properties"]["executed"]["enum"], [False])
        start = entry["input_schema"]["properties"]["start_joints_rad"]
        self.assertEqual((start["minItems"], start["maxItems"], start["items"]["x-mhs-unit"]), (6, 6, "rad"))

    def test_a_malformed_input_never_reaches_the_service(self) -> None:
        client = self.serve()
        bad = request()
        bad["start_joints_rad"] = [0, 0, 0, 0, 0]
        receipt = client.invoke(CAPABILITY, bad, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_the_manifest_is_a_software_latch_and_an_exclusive_command(self) -> None:
        client = self.serve()
        manifest = client.inspect(self.ids["device_id"])
        [entry] = manifest["capabilities"]
        self.assertEqual(entry["capability_id"], CAPABILITY)
        self.assertEqual(entry["verb"], "invoke")
        self.assertTrue(entry["exclusive"], entry)
        self.assertEqual(manifest["mode"], "simulated")
        self.assertEqual(type(self.driver()).mode, "simulated")
        limits = entry["limits"]
        self.assertEqual(limits["start_joints_rad[0]"], {
            "min": -3.05433, "max": 3.05433, "unit": "rad", "source": "upstream_code", "ref": URDF + ":39-40"})
        self.assertEqual(limits["start_joints_rad[1]"], {
            "min": -1.91986, "max": 0.640187, "unit": "rad", "source": "upstream_code", "ref": URDF + ":41-42"})
        self.assertEqual(limits["start_joints_rad[2]"], "operator_required")
        self.assertEqual(limits["start_joints_rad[3]"], {
            "min": -3.05433, "max": 3.05433, "unit": "rad", "source": "upstream_code", "ref": URDF + ":45-46"})
        self.assertEqual(limits["start_joints_rad[4]"], {
            "min": -1.74533, "max": 1.91986, "unit": "rad", "source": "upstream_code", "ref": URDF + ":47-48"})
        self.assertEqual(limits["start_joints_rad[5]"], {
            "min": -2.57436, "max": 2.57436, "unit": "rad", "source": "upstream_code", "ref": URDF + ":49-50"})
        for name in ("pick_position", "pick_orientation", "place_position", "place_orientation"):
            self.assertEqual(limits[f"{name}[*]"], "operator_required")
        self.assertEqual(manifest["safety"]["estop"]["kind"], "software")
        self.assertIsNone(manifest["safety"]["estop"]["native"])
        self.assertEqual(manifest["safety"]["risk_class"], "R0")

    def test_the_binding_names_the_advertised_service(self) -> None:
        module = importlib.import_module(type(load_driver(HERE, "fake")).__module__)
        self.assertEqual(module._PLAN["source_name"], module._PLAN["service"].lstrip("/"))
        self.assertEqual(module._PLAN["service"], "/niryo_moveit")
        self.assertEqual(module._PLAN["operation"], "read")

    def test_the_elbow_and_the_poses_need_the_operator_bounds(self) -> None:
        client = self.serve(site_limits=None)
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_a_joint_outside_a_cited_urdf_limit_is_refused(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(start=(3.2, 0, 0, 0, 0, 0)), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_the_closed_urdf_bound_is_accepted(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(start=(3.05433, 0, 0, 0, 0, 0)), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(len(self.fake.calls), 1)

    def test_an_elbow_outside_the_example_overlay_is_refused(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(start=(0, 0, 2.0, 0, 0, 0)), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ENVELOPE_VIOLATION", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_a_zero_quaternion_never_reaches_the_service(self) -> None:
        client = self.serve()
        for name in ("pick_orientation", "place_orientation"):
            with self.subTest(name=name):
                bad = request()
                bad[name] = [0.0, 0.0, 0.0, 0.0]
                receipt = client.invoke(CAPABILITY, bad, **self.ids)
                self.assertNotEqual(receipt["status"], "completed", receipt)
                self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID", receipt)
                self.assertIn("zero quaternion", receipt["error"]["message"])
                self.assertEqual(self.fake.calls, [])

    def test_a_non_finite_input_never_reaches_the_service(self) -> None:
        driver = self.driver()
        for name, value in (("start_joints_rad", [0, 0, 0, 0, 0, float("nan")]),
                            ("pick_position", [0.2, float("inf"), 0.3]),
                            ("place_orientation", [0.0, float("nan"), 0.0, 1.0])):
            with self.subTest(name=name):
                bad = request()
                bad[name] = value
                with self.assertRaises(DriverFailed) as caught:
                    driver.call(CAPABILITY, bad)
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.INPUT_INVALID")
                self.assertIn("finite", caught.exception.message)
        self.assertEqual(driver.native.calls, [])

    def test_a_second_planning_call_is_not_sent_while_one_is_pending(self) -> None:
        client = self.serve()
        self.fake.silent = True
        receipts = []

        def plan():
            receipts.append(client.invoke(CAPABILITY, request(), deadline_ms=1500, **self.ids))

        first = threading.Thread(target=plan)
        first.start()
        for _ in range(200):
            if self.fake.calls:
                break
            time.sleep(0.01)
        second = threading.Thread(target=plan)
        second.start()
        time.sleep(0.3)
        self.assertEqual(len(self.fake.calls), 1)
        first.join(10)
        second.join(10)
        self.assertEqual(len(receipts), 2)
        self.assertTrue(all(receipt["status"] != "completed" for receipt in receipts), receipts)

    def test_the_estop_latches_planning(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.fake.calls, [])

    def test_the_estop_does_not_wait_for_a_plan_in_flight_and_the_plan_is_not_completed(self) -> None:
        client = self.serve()
        self.fake.silent = True
        outcome = {}

        def plan():
            outcome["receipt"] = client.invoke(CAPABILITY, request(), deadline_ms=5000, **self.ids)

        worker = threading.Thread(target=plan)
        worker.start()
        for _ in range(200):
            if self.fake.calls:
                break
            time.sleep(0.01)
        self.assertEqual(len(self.fake.calls), 1)
        started = time.monotonic()
        receipt = client.estop("plan in flight", deadline_ms=2000, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertLess(time.monotonic() - started, 1.5)
        worker.join(10)
        self.assertFalse(worker.is_alive())
        self.assertNotEqual(outcome["receipt"]["status"], "completed", outcome["receipt"])
        self.assertIsNone(outcome["receipt"].get("output"))

    def test_a_deadline_does_not_retire_a_plan_already_sent(self) -> None:
        # A 100 ms deadline returns unknown while the service request stays unanswered.
        # Exclusive can still reject the next call for a short time after that receipt.
        # Once the local lease drops, the next call is sent. The first request is not
        # cancelled, and a later e-stop adds no ROS message.
        client = self.serve()
        self.fake.silent = True
        first = client.invoke(CAPABILITY, request(), deadline_ms=100, **self.ids)
        self.assertEqual(first["status"], "unknown", first)
        self.assertIsNone(first.get("output"))
        self.assertEqual(len(self.fake.calls), 1)
        first_id = self.fake.calls[0].get("id")
        second = None
        started = time.monotonic()
        while time.monotonic() - started < 2.0:
            second = client.invoke(CAPABILITY, request(), deadline_ms=100, **self.ids)
            if second["status"] == "unknown":
                break
            self.assertEqual(second["status"], "rejected", second)
            self.assertEqual(second["error"]["mhs_code"], "MHS.DEVICE.BUSY", second)
            self.assertEqual(len(self.fake.calls), 1)
            self.assertEqual(self.fake.calls[0].get("id"), first_id)
            time.sleep(0.05)
        self.assertEqual(second["status"], "unknown", second)
        self.assertIsNone(second.get("output"))
        self.assertEqual(len(self.fake.calls), 2)
        self.assertEqual(self.fake.calls[0].get("id"), first_id)
        self.assertNotEqual(self.fake.calls[1].get("id"), first_id)
        for call in self.fake.calls:
            self.assertEqual(call.get("op"), "call_service")
            self.assertEqual(call.get("service"), "/niryo_moveit")
        stopped = client.estop("deadlines left the plans running", deadline_ms=500, **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertEqual([call.get("op") for call in self.fake.calls], ["call_service", "call_service"])


if __name__ == "__main__":
    unittest.main()
