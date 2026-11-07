"""Acceptance run of the FluentControl package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
POST = "x-cap.aaronslaff.post_transfer_session.v1"
START = "x-cap.aaronslaff.start_transfer_session.v1"
STATUS = "x-cap.aaronslaff.transfer_status.v1"
CANCEL = "x-cap.aaronslaff.cancel_transfer_session.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class FluentControlCases(unittest.TestCase):
    def serve(self, with_limits: bool = True):
        limits = str(HERE / "site-limits.example.json") if with_limits else None
        server = load(HERE, backend="fake", site_limits=limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def transfer_payload(self, volume=50.0):
        return {
            "source_position": "A1",
            "destination_position": "A2",
            "volume_ul": volume,
            "liquid_class": "Standard",
            "tip_type": "Standard_200uL",
        }

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_volume_waits_for_the_site(self) -> None:
        client = self.serve(with_limits=False)
        refused = client.invoke(POST, self.transfer_payload(), **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["transfer_status"], {})

    def test_the_example_overlay_supplies_the_volume_range(self) -> None:
        client = self.serve()
        created = client.invoke(POST, self.transfer_payload(), **self.ids)
        self.assertEqual(created["status"], "completed", created)
        session_id = created["output"]["session_id"]
        self.assertTrue(session_id)
        self.assertEqual(self.state(client)["transfer_status"]["status"], "pending")

        started = client.invoke(START, {"session_id": session_id}, **self.ids)
        self.assertEqual(started["status"], "completed", started)
        status = client.invoke(STATUS, {"session_id": session_id}, **self.ids)
        self.assertEqual(status["output"], {"session_id": session_id, "status": "running"})
        cancelled = client.invoke(CANCEL, {"session_id": session_id}, **self.ids)
        self.assertEqual(cancelled["output"], {"session_id": session_id})
        self.assertEqual(self.state(client)["transfer_status"]["status"], "cancelled")

    def test_the_reads_return_the_fake_state(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["instrument_status"], {"state": "idle"})
        self.assertEqual(state["deck_layout"], {"positions": []})
        self.assertEqual(state["transfer_status"], {})

    def test_the_estop_cancels_the_tracked_session_and_latches(self) -> None:
        client = self.serve()
        created = client.invoke(POST, self.transfer_payload(), **self.ids)
        self.assertEqual(created["status"], "completed", created)
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["transfer_status"]["status"], "cancelled")
        refused = client.invoke(POST, self.transfer_payload(), **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
