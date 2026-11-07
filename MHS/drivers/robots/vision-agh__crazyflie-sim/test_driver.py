"""Acceptance run of the CrazyFlie simulation world-step package: the gate plus package-specific cases.

Add cases, never remove the ``check_driver`` call.  These cases run on the analytic fake in ``fake.py``; nothing
here opens ROS, Gazebo, rclpy or the upstream simulator.

Model review (2026-11-05): the pinned step_simulation returns None for an answered and an unanswered ControlWorld
call alike, so the e-stop sends the pause request and then reports SAFE_STATE_UNREACHED with the latch held, and an
unanswered step is not detected.  The gate case fails (G4 and G7 cannot read the evs_gz_utils submodule at the
pinned parent commit; G6.ESTOP_FAILED for the unacknowledged stop): the package is blocked.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
STEP = "cap.world.step.v1"
PAUSE = "x-cap.vision-agh.pause.v1"
INPUT_INVALID = "MHS.CAPABILITY.INPUT_INVALID"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class WorldStepCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        self.fake = driver.native
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        del self.fake._calls[:]
        return client

    def step(self, client, ticks=1):
        return client.invoke(STEP, {"ticks": ticks}, **self.ids)

    def state(self, client):
        return client.read("world", **self.ids)["state"]

    def test_a_single_step_uses_the_upstream_step_flag(self) -> None:
        client = self.serve()
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["observation"], {"stepped": 1, "pause_requested": True})
        self.assertEqual(receipt["output"]["tick"], 1)
        self.assertTrue(receipt["output"]["state_hash"].startswith("sha256:"))
        self.assertEqual(len(receipt["output"]["state_hash"]), len("sha256:") + 64)
        self.assertTrue(self.fake.pause_request)
        self.assertTrue(self.fake.step_request)
        self.assertIsNone(self.fake.multi_step_request)
        self.assertEqual(self.fake._called("step_simulation"), [(1,)])

    def test_multiple_steps_use_multi_step_and_accumulate_the_tick(self) -> None:
        client = self.serve()
        first = self.step(client, 3)
        self.assertEqual(first["status"], "completed", first)
        self.assertEqual(first["output"]["tick"], 3)
        self.assertFalse(self.fake.step_request)
        self.assertEqual(self.fake.multi_step_request, 3)
        second = self.step(client, 2)
        self.assertEqual(second["output"]["tick"], 5)
        self.assertEqual(self.state(client), {"tick": 5})
        self.assertEqual(self.fake._called("step_simulation"), [(3,), (2,)])

    def test_the_pause_request_is_the_zero_step_path(self) -> None:
        client = self.serve()
        receipt = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"], {"pause_requested": True})
        self.assertTrue(self.fake.pause_request)
        self.assertFalse(self.fake.step_request)
        self.assertEqual(self.fake.multi_step_request, 0)
        self.assertEqual(self.fake._called("step_simulation"), [(0,)])

    def test_out_of_schema_steps_are_refused_without_a_native_call(self) -> None:
        client = self.serve()
        for ticks in (0, 10001):
            receipt = self.step(client, ticks)
            self.assertEqual(receipt["status"], "rejected", receipt)
            self.assertEqual(receipt["error"]["mhs_code"], INPUT_INVALID)
        self.assertEqual(self.fake._calls, [])

    def test_an_unanswered_step_is_not_detected(self) -> None:
        # The upstream method logs and returns None when the ControlWorld call gets no result, as on success
        # (gz_step_example.py:44-49): the driver cannot tell, so the step completes.  A known weakness, not a check.
        client = self.serve()
        self.fake._fail_next = True
        receipt = self.step(client, 1)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(self.fake.unanswered, 1)
        self.assertEqual(self.state(client), {"tick": 1})

    def test_the_estop_sends_the_pause_but_does_not_claim_a_safe_state(self) -> None:
        client = self.serve()
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertIn((0,), self.fake._called("step_simulation"))
        refused = self.step(client, 1)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)
        refused = client.invoke(PAUSE, {}, **self.ids)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_an_unanswered_estop_is_not_reported_completed_either(self) -> None:
        client = self.serve()
        self.fake._fail_all = True
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], UNREACHED, receipt)
        self.assertGreaterEqual(self.fake.unanswered, 1)
        self.fake._fail_all = False
        refused = self.step(client, 1)
        self.assertEqual(refused["status"], "rejected", refused)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_the_fake_only_exposes_the_upstream_step_method(self) -> None:
        self.serve()
        public = {name for name in dir(type(self.fake)) if not name.startswith("_")}
        self.assertEqual(public, {"step_simulation"})


if __name__ == "__main__":
    unittest.main()
