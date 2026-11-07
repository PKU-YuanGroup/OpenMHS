"""Acceptance run of the remote STAR package: the gate, plus cases for what is specific to this driver."""

import threading
import time
import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SITE = HERE / "site-limits.example.json"
ASPIRATE = "x-cap.koeng101.aspirate_pip.v1"
MOVE_ALL = "x-cap.koeng101.move_all_channels_in_z_safety.v1"
HALT = "x-cap.koeng101.halt.v1"


class _FailingHalt:
    """Pass everything to the fake except halt, which fails, so the native e-stop path can be tested."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        if name == "halt":
            async def fail():
                raise RuntimeError("halt failed")
            return fail
        return getattr(self._inner, name)


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class StarRemoteCases(unittest.TestCase):
    def setUp(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        self.client = client_for(server)
        device_id = self.client.hello()["devices"][0]["device_id"]
        session = self.client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}

    def invoke(self, capability, payload):
        return self.client.invoke(capability, payload, **self.ids)

    def test_reads_expose_the_remote_position_maps_and_version(self) -> None:
        state = self.client.read("main", **self.ids)["state"]
        self.assertIsInstance(state["channel_y_positions"], dict)
        self.assertIsInstance(state["channel_z_positions"], dict)
        self.assertIsInstance(state["iswap_version"], str)

    def test_z_safety_and_halt_complete(self) -> None:
        moved = self.invoke(MOVE_ALL, {})
        self.assertEqual(moved["status"], "completed", moved)
        self.assertTrue(moved["output"]["moved"])
        halted = self.invoke(HALT, {})
        self.assertEqual(halted["status"], "completed", halted)
        self.assertTrue(halted["output"]["halted"])

    def test_the_operator_envelope_is_required_before_aspiration(self) -> None:
        receipt = self.invoke(ASPIRATE, {"channel": 0, "x_position": 1000, "y_position": 1000,
                                         "volume": 100, "speed": 500})
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.LIMITS_UNSET")

    def test_the_example_overlay_admits_a_fixture_aspiration(self) -> None:
        server = load(HERE, backend="fake", site_limits=str(SITE))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(ASPIRATE, {"channel": 0, "x_position": 1000, "y_position": 1000,
                                          "volume": 100, "speed": 500},
                                device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["aspirated_volume"], 100)

    def test_the_e_stop_sends_halt_but_does_not_claim_a_safe_state(self) -> None:
        # Model review: STARBackend.halt is outside the clone, so the e-stop sends Halt and still reports
        # SAFE_STATE_UNREACHED with the latch held.
        stopped = self.client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertEqual(stopped["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED", stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"])
        self.assertEqual(stopped["output"]["safe_state"]["achieved_by"], [], stopped)
        receipt = self.invoke(MOVE_ALL, {})
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.ESTOP_ENGAGED")

    def test_halt_cannot_be_sent_while_a_blocking_rpc_holds_the_event_loop(self) -> None:
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver, site_limits=str(SITE))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        fake = driver.native
        fake.block_s = 2.5                      # placeholder: one aspirate RPC that holds the loop
        outcome = {}
        worker = threading.Thread(target=lambda: outcome.update(receipt=client.invoke(
            ASPIRATE, {"channel": 0, "x_position": 1000, "y_position": 1000, "volume": 100, "speed": 500},
            device_id=device_id, session_id=session)))
        worker.start()
        time.sleep(0.3)
        stopped = client.estop("test", device_id=device_id, session_id=session)
        halts_when_the_estop_answered = fake._halts
        worker.join(10)
        self.assertEqual(stopped["status"], "failed", stopped)
        self.assertFalse(stopped["output"]["safe_state_achieved"])
        self.assertEqual(halts_when_the_estop_answered, 0)

    def test_a_failed_native_halt_is_reported_by_the_e_stop(self) -> None:
        driver = load_driver(HERE, backend="fake", native_wrapper=_FailingHalt)
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.estop("test", device_id=device_id, session_id=session)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        self.assertFalse(receipt["output"]["safe_state_achieved"])


if __name__ == "__main__":
    unittest.main()
