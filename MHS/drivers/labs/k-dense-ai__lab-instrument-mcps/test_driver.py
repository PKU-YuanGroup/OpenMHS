"""Acceptance run of the labmcp-julabo package: the gate, plus cases for this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
SAFE_STATE_UNREACHED = "MHS.SAFETY.SAFE_STATE_UNREACHED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class JulaboCases(unittest.TestCase):
    def serve(self, site_limits=None, **options):
        server = load(HERE, backend="fake", site_limits=site_limits, options=options or None)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_set_point_waits_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, setpoint=37)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["setpoint"], 20.0)  # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_range(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, setpoint=36.666)["status"], "completed")
        self.assertEqual(self.state(client)["setpoint"], 36.67)  # two decimals, as the upstream encoder
        for value in (4.99, 90.01):
            refused = self.configure(client, setpoint=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["setpoint"], 36.67)

    def test_the_reads_and_the_circulation(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["temperature"], 21.5)
        self.assertEqual(state["setpoint"], 20.0)
        self.assertEqual(state["running"], False)
        self.assertEqual(state["status"], "02 REMOTE STOP")
        started = client.invoke("x-cap.k-dense-ai.start_circulation.v1", {}, **self.ids)
        self.assertEqual(started["output"], {"running": True})
        self.assertTrue(self.state(client)["running"])
        stopped = client.invoke("x-cap.k-dense-ai.stop_circulation.v1", {}, **self.ids)
        self.assertEqual(stopped["output"], {"running": False})
        self.assertFalse(self.state(client)["running"])

    def test_the_estop_stops_and_latches(self) -> None:
        client = self.serve()
        client.invoke("x-cap.k-dense-ai.start_circulation.v1", {}, **self.ids)
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["running"])
        refused = client.invoke("x-cap.k-dense-ai.start_circulation.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_an_unconfirmed_stop_keeps_the_latch(self) -> None:
        client = self.serve(stop_confirmed=False)  # fake test hook: out_mode_05 0 is never confirmed
        client.invoke("x-cap.k-dense-ai.start_circulation.v1", {}, **self.ids)
        receipt = client.estop("test", **self.ids)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["error"]["mhs_code"], SAFE_STATE_UNREACHED)
        self.assertTrue(receipt["output"]["latched"])
        self.assertFalse(receipt["output"]["safe_state_achieved"])
        refused = client.invoke("x-cap.k-dense-ai.start_circulation.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


    def test_start_refuses_a_stored_target_outside_the_site_envelope(self) -> None:
        driver = load_driver(HERE, "fake")
        # Fault injection: a front-panel change outside the example overlay's 5..90 Cel range.
        driver.native._setpoint_c = 150.0  # placeholder; no physical device is used
        server = build_server(driver, site_limits=str(HERE / "site-limits.example.json"))
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke("x-cap.k-dense-ai.start_circulation.v1", {},
                                device_id=device_id, session_id=session_id)
        self.assertNotEqual(receipt["status"], "completed", receipt)
        self.assertFalse(driver.native.is_running())


if __name__ == "__main__":
    unittest.main()
