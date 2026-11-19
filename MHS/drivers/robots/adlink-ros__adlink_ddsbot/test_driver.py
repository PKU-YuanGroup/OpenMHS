"""Acceptance run and repository-specific cases for the ADLINK DDSBot base driver."""

import importlib.util
import json
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"


def _fake_class():
    """Load fake.py by path: the gate runs this file without the package directory on sys.path."""
    spec = importlib.util.spec_from_file_location("adlink_ddsbot_fake_for_tests", HERE / "fake.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FakeBaseControl


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class BaseCases(unittest.TestCase):
    def test_pinned_firmware_reply_is_zero_during_a_nonzero_request(self) -> None:
        fake = _fake_class()()
        fake.trans_x = 0.1
        fake.timerCmdCB(None)
        self.assertNotEqual(float(fake.serial.last_command.split(",")[0]), 0.0)
        self.assertEqual(fake.serial.readline(), "0,0\r\n")

    def test_unacknowledged_stop_fails_and_keeps_the_latch(self) -> None:
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        ids = {"device_id": device_id, "session_id": session}
        receipt = client.estop("unacknowledged serial stop", **ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", receipt)
        refused = client.invoke("cap.motion.mobile_base.v1",
                                {"linear_velocity": 0.05, "angular_velocity": 0.0, "duration_s": 0.05}, **ids)
        self.assertEqual(refused["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED", refused)

    def test_checksum_frame_matches_the_upstream_writer(self) -> None:
        fake = _fake_class()()
        fake.trans_x, fake.rotat_z = 0.1, 0.0
        fake.timerCmdCB(None)
        fields = fake.serial.last_command.split(",")
        self.assertEqual(len(fields), 3)
        self.assertEqual(int(fields[2]), len(fields[0]) + len(fields[1]))
        left = float(fields[0])
        right = float(fields[1])
        self.assertAlmostEqual(left, 0.1 / fake.wheelRad * 180.0 / 3.141592653589793, places=6)
        self.assertAlmostEqual(right, left, places=6)

    def test_action_needs_the_operator_envelope(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(
            "cap.motion.mobile_base.v1",
            {"linear_velocity": 0.05, "angular_velocity": 0.0, "duration_s": 0.05},
            device_id=device_id,
            session_id=session,
        )
        self.assertEqual(receipt["error"]["mhs_code"], LIMITS_UNSET, receipt)

    def test_mobile_base_action_through_the_stock_server(self) -> None:
        overlay = json.loads((HERE / "site-limits.example.json").read_text(encoding="utf-8"))
        server = load(HERE, backend="fake", site_limits=overlay)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(
            "cap.motion.mobile_base.v1",
            {"linear_velocity": 0.05, "angular_velocity": 0.0, "duration_s": 0.05},
            device_id=device_id,
            session_id=session,
        )
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertGreaterEqual(receipt["output"]["distance_m"], 0.0)
        self.assertAlmostEqual(receipt["output"]["heading_rad"], 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
