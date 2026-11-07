"""Acceptance run of the UC480 camera package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class UC480Cases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        return client.invoke("cap.device.configure.v1", patch, **self.ids)

    def invoke(self, client, capability_id, payload=None):
        return client.invoke(capability_id, payload or {}, **self.ids)

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_scalar_state_is_read(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["trigger_mode"], "software")          # placeholder: fake starting value
        self.assertFalse(state["auto_exposure"])                      # placeholder: fake starting value
        self.assertEqual((state["width"], state["height"]), (3, 2))   # placeholder: fake frame shape
        self.assertEqual(state["bytes_per_line"], 3)                  # placeholder: fake line stride
        self.assertEqual(state["exposure_time"], 10.0)                # placeholder: fake starting value
        self.assertEqual(state["gamma"], 1.0)                         # placeholder: fake starting value
        self.assertTrue(state["is_open"])                             # placeholder: fake starting value

    def test_the_auto_exposure_switch_reaches_the_fake(self) -> None:
        client = self.serve()
        applied = self.configure(client, auto_exposure=True)
        self.assertEqual(applied["status"], "completed")
        self.assertTrue(self.state(client)["auto_exposure"])
        applied = self.configure(client, auto_exposure=False)
        self.assertEqual(applied["status"], "completed")
        self.assertFalse(self.state(client)["auto_exposure"])

    def test_gamma_uses_the_range_the_clone_states(self) -> None:
        client = self.serve()
        applied = self.configure(client, gamma=5.25)
        self.assertEqual(applied["status"], "completed")
        self.assertEqual(self.state(client)["gamma"], 5.25)
        for value in (0.99, 10.01):
            refused = self.configure(client, gamma=value)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, value)
        self.assertEqual(self.state(client)["gamma"], 5.25)

    def test_the_two_numeric_ranges_wait_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"trigger_delay": 250.0}, {"exposure_time": 5.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected")
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        self.assertEqual(self.state(client)["trigger_delay"], 0.0)    # placeholder: fake starting value
        self.assertEqual(self.state(client)["exposure_time"], 10.0)   # placeholder: fake starting value

    def test_the_example_overlay_supplies_both_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, trigger_delay=250.0)["status"], "completed")
        self.assertEqual(self.configure(client, exposure_time=5.0)["status"], "completed")
        self.assertEqual(self.state(client)["trigger_delay"], 250.0)
        self.assertEqual(self.state(client)["exposure_time"], 5.0)
        for patch in ({"trigger_delay": 100001.0}, {"exposure_time": 1001.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_trigger_capture_and_live_video_actions(self) -> None:
        client = self.serve()
        trigger = self.invoke(client, "x-cap.mabuchilab.configure_trigger.v1",
                              {"mode": "hardware", "edge": "rising"})
        self.assertEqual(trigger["status"], "completed")
        self.assertEqual(trigger["output"], {"trigger_mode": "hardware", "edge": "rising"})
        self.assertEqual(self.state(client)["trigger_mode"], "hardware")

        captured = self.invoke(client, "x-cap.mabuchilab.capture.v1")
        self.assertEqual(captured["status"], "completed")
        self.assertEqual(captured["output"], {"width": 3, "height": 2, "frames": 1})  # placeholder frame shape

        started = self.invoke(client, "x-cap.mabuchilab.start_live_video.v1")
        self.assertEqual(started["status"], "completed")
        self.assertEqual(started["output"], {"trigger_mode": "off"})
        stopped = self.invoke(client, "x-cap.mabuchilab.stop_live_video.v1")
        self.assertEqual(stopped["status"], "completed")

    def test_the_safe_state_closes_and_the_estop_latches(self) -> None:
        client = self.serve()
        closed = self.invoke(client, "x-cap.mabuchilab.close_camera.v1")
        self.assertEqual(closed["output"], {"is_open": False})
        self.assertFalse(self.state(client)["is_open"])

        client = self.serve()
        self.invoke(client, "x-cap.mabuchilab.start_live_video.v1")
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["is_open"])
        refused = self.configure(client, auto_exposure=True)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
