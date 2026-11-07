"""Acceptance run of the Unity UR3 pick-and-place planner package: the gate plus repository cases.

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
from mhs.errors import MHSError
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SITE = HERE / "site-limits.example.json"  # the operator fills every operator_required bound (example values)
CAPABILITY = "x-cap.unity-technologies.pick_place_plan.v1"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
JOINTS = ["shoulder_pan_joint", "shoulder_lift_joint", "elbow_joint", "wrist_1_joint", "wrist_2_joint",
          "wrist_3_joint"]


def request(start=(0, 0, 0, 0, 0, 0)):
    return {
        "start_joints_deg": list(start),
        "pick_position": [0.25, 0.1, 0.95],
        "pick_orientation": [0.0, 0.707, 0.0, 0.707],
        "place_position": [0.25, -0.2, 0.97],
        "place_orientation": [0.0, 0.707, 0.0, 0.707],
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
        self.fake = fake_module().FakeUr3MoverService()
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

    def test_a_plan_has_five_trajectories_of_the_six_arm_joints(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertIs(output["executed"], False)
        self.assertEqual(len(output["joint_names"]), 5)
        self.assertEqual(len(output["points"]), 5)
        for names, points in zip(output["joint_names"], output["points"]):
            self.assertEqual(names, JOINTS)  # the planner's order, as returned
            self.assertTrue(points)
            for point in points:
                self.assertEqual(len(point["positions"]), 6)
                self.assertEqual(set(point["time_from_start"]), {"secs", "nsecs"})

    def test_the_request_carries_degrees_and_every_pose_leaf(self) -> None:
        driver = self.driver()
        driver.call(CAPABILITY, request(start=(90, -45, 30, 0, -90, 180)))
        [call] = driver.native.calls
        self.assertEqual(call["service"], "/ur3_moveit")
        self.assertEqual(call["type"], "ur3_moveit/MoverService")
        args = call["args"]
        self.assertEqual(sorted(args), ["joints_input", "pick_pose", "place_pose"])
        self.assertEqual(args["joints_input"], {f"joint_0{i}": value
                                                for i, value in enumerate((90, -45, 30, 0, -90, 180))})
        self.assertEqual(args["pick_pose"], {"position": {"x": 0.25, "y": 0.1, "z": 0.95},
                                             "orientation": {"x": 0.0, "y": 0.707, "z": 0.0, "w": 0.707}})
        self.assertEqual(args["place_pose"], {"position": {"x": 0.25, "y": -0.2, "z": 0.97},
                                              "orientation": {"x": 0.0, "y": 0.707, "z": 0.0, "w": 0.707}})

    def test_the_first_plan_starts_at_the_requested_angles_in_radians(self) -> None:
        driver = self.driver()
        output = driver.call(CAPABILITY, request(start=(90, -45, 30, 0, -90, 180)))
        first = output["points"][0][0]["positions"]
        for got, want in zip(first, [math.radians(v) for v in (90, -45, 30, 0, -90, 180)]):
            self.assertAlmostEqual(got, want)

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

    def test_the_published_output_contract_fixes_five_plans_of_six_joints(self) -> None:
        client = self.serve()
        [entry] = client.inspect(self.ids["device_id"])["capabilities"]
        output = entry["output_schema"]
        self.assertEqual(output["required"], ["joint_names", "points", "executed"])
        names = output["properties"]["joint_names"]
        self.assertEqual((names["minItems"], names["maxItems"]), (5, 5))
        self.assertEqual((names["items"]["minItems"], names["items"]["maxItems"]), (6, 6))
        self.assertEqual(names["items"]["items"]["enum"], JOINTS)
        points = output["properties"]["points"]
        self.assertEqual((points["minItems"], points["maxItems"]), (5, 5))
        positions = points["items"]["items"]["properties"]["positions"]
        self.assertEqual((positions["minItems"], positions["maxItems"], positions["items"]["x-mhs-unit"]),
                         (6, 6, "rad"))
        self.assertEqual(output["properties"]["executed"]["enum"], [False])
        start = entry["input_schema"]["properties"]["start_joints_deg"]
        self.assertEqual((start["minItems"], start["maxItems"], start["items"]["x-mhs-unit"]), (6, 6, "deg"))

    def test_a_malformed_input_never_reaches_the_service(self) -> None:
        client = self.serve()
        bad = request()
        bad["start_joints_deg"] = [0, 0, 0, 0, 0]  # five angles
        receipt = client.invoke(CAPABILITY, bad, **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_the_manifest_is_a_software_latch_and_an_exclusive_command(self) -> None:
        # integrator v4 (2026-11-05): the plan call changes the planner's state, so it is a command, never a read
        client = self.serve()
        manifest = client.inspect(self.ids["device_id"])
        [entry] = manifest["capabilities"]
        self.assertEqual(entry["capability_id"], CAPABILITY)
        self.assertEqual(entry["verb"], "invoke")
        self.assertTrue(entry["exclusive"], entry)
        self.assertEqual(manifest["mode"], "simulated")
        self.assertEqual(type(self.driver()).mode, "simulated")  # the class itself, not only the served view
        self.assertEqual(entry["limits"], {f"{name}[*]": "operator_required" for name in (
            "start_joints_deg", "pick_position", "pick_orientation", "place_position", "place_orientation")})
        self.assertEqual(manifest["safety"]["estop"]["kind"], "software")
        self.assertIsNone(manifest["safety"]["estop"]["native"])
        self.assertEqual(manifest["safety"]["risk_class"], "R1")

    def test_the_binding_names_the_advertised_service(self) -> None:
        # the cited name is the name the callback is advertised under (mover.py:141), the service the call reaches
        from importlib import import_module

        module = import_module(type(load_driver(HERE, "fake")).__module__)
        self.assertEqual(module._PLAN["source_name"], module._PLAN["service"].lstrip("/"))
        self.assertEqual(module._PLAN["service"], "/ur3_moveit")

    def test_every_input_needs_the_operator_bounds(self) -> None:
        client = self.serve(site_limits=None)
        receipt = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET", receipt)
        self.assertEqual(self.fake.calls, [])

    def test_an_angle_outside_the_operator_envelope_is_refused(self) -> None:
        client = self.serve()
        receipt = client.invoke(CAPABILITY, request(start=(0, 0, 0, 0, 0, 200)), **self.ids)
        self.assertEqual(receipt["status"], "rejected", receipt)
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
                self.assertEqual(self.fake.calls, [])

    def test_a_non_finite_input_never_reaches_the_service(self) -> None:
        driver = self.driver()
        for name, value in (("start_joints_deg", [0, 0, 0, 0, 0, float("nan")]),
                            ("pick_position", [0.25, float("inf"), 0.95]),
                            ("place_orientation", [0.0, float("nan"), 0.0, 0.707])):
            with self.subTest(name=name):
                bad = request()
                bad[name] = value
                with self.assertRaises(DriverFailed) as caught:
                    driver.call(CAPABILITY, bad)
                self.assertEqual(caught.exception.code, "MHS.CAPABILITY.INPUT_INVALID")
        self.assertEqual(driver.native.calls, [])

    def test_a_second_planning_call_is_not_sent_while_one_is_pending(self) -> None:
        client = self.serve()
        self.fake.silent = True  # the first plan stays unanswered until its deadline
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
        self.assertEqual(len(self.fake.calls), 1)  # the endpoint serialises its own planning calls
        first.join(10)
        second.join(10)
        self.assertEqual(len(receipts), 2)
        self.assertTrue(all(receipt["status"] != "completed" for receipt in receipts), receipts)

    def test_the_estop_latches_planning(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        refused = client.invoke(CAPABILITY, request(), **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        self.assertEqual(self.fake.calls, [])

    def test_the_estop_does_not_wait_for_a_plan_in_flight_and_the_plan_is_not_completed(self) -> None:
        client = self.serve()
        self.fake.silent = True  # the planner has not answered yet
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


if __name__ == "__main__":
    unittest.main()
