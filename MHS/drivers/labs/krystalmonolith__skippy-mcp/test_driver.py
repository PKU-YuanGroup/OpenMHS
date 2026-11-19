"""Acceptance run of the SkippyMCP package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  Every number below is a placeholder of fake.py, not a fact.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"

#: The fake placeholders (fake.py): the state of a freshly opened in-memory scope.
START = {
    "identity": "RIGOL TECHNOLOGIES,MSO5204,FAKE00000000,00.01.03.02.02",  # placeholder
    "channel1_enabled": True,  # placeholder
    "channel1_scale_v_per_div": 0.5,  # placeholder
    "channel1_offset_v": 0.0,  # placeholder
    "channel1_coupling": "dc",  # placeholder
    "channel1_probe_ratio": 10.0,  # placeholder
    "channel1_bandwidth_limit": "20m",  # placeholder
    "trigger_mode": "edge",  # placeholder
    "trigger_edge_source": "ch1",  # placeholder
    "trigger_edge_slope": "rising",  # placeholder
    "trigger_edge_level_v": 0.0,  # placeholder
}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class DriverCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def configure(self, client, **patch):
        """``completed``, or the code the write was refused with."""
        receipt = client.invoke("cap.device.configure.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def trigger(self, client, **patch):
        """``completed``, or the code the trigger action was refused with."""
        receipt = client.invoke("x-cap.krystalmonolith.scope_trigger.v1", patch, **self.ids)
        return receipt["error"]["mhs_code"] if receipt["status"] == "rejected" else receipt["status"]

    def measure(self, client, item="vpp", source="ch1"):
        return client.invoke("x-cap.krystalmonolith.scope_measure.v1",
                             {"item": item, "source": source}, **self.ids)

    def state(self, client, fields=None):
        return client.read("main", fields=fields, **self.ids)["state"]

    def test_the_start_state_of_the_served_channel(self) -> None:
        client = self.serve()
        self.assertEqual(self.state(client), START)

    def test_a_write_changes_the_state_it_reports(self) -> None:
        client = self.serve()
        self.assertEqual(self.configure(client, channel1_enabled=False), "completed")
        self.assertEqual(self.configure(client, channel1_scale_v_per_div=2.0), "completed")
        self.assertEqual(self.configure(client, channel1_coupling="ac"), "completed")
        self.assertEqual(self.configure(client, channel1_bandwidth_limit="off"), "completed")
        state = self.state(client)
        self.assertFalse(state["channel1_enabled"])
        self.assertEqual(state["channel1_scale_v_per_div"], 2.0)
        self.assertEqual(state["channel1_coupling"], "ac")
        self.assertEqual(state["channel1_bandwidth_limit"], "off")

    def test_the_envelope_of_the_upstream_enums_and_scale(self) -> None:
        client = self.serve()
        for patch in (
            {"channel1_scale_v_per_div": 0.0},
            {"channel1_scale_v_per_div": 20.0},
            {"channel1_coupling": "differential"},
            {"channel1_bandwidth_limit": "on"},
        ):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)
        for patch in (
            {"channel1_scale_v_per_div": 0.0005},
            {"channel1_scale_v_per_div": 10.0},
            {"channel1_coupling": "gnd"},
            {"channel1_bandwidth_limit": "20m"},
        ):
            self.assertEqual(self.configure(client, **patch), "completed", patch)

    def test_the_operator_supplies_the_span_and_probe_ranges(self) -> None:
        client = self.serve()
        for patch in (
            {"channel1_offset_v": 0.2},
            {"channel1_probe_ratio": 100.0},
        ):
            self.assertEqual(self.configure(client, **patch), LIMITS_UNSET, patch)
        client = self.serve(str(HERE / "site-limits.example.json"))
        for patch in (
            {"channel1_offset_v": 0.2},
            {"channel1_probe_ratio": 100.0},
        ):
            self.assertEqual(self.configure(client, **patch), "completed", patch)
        state = self.state(client)
        self.assertEqual(state["channel1_offset_v"], 0.2)
        self.assertEqual(state["channel1_probe_ratio"], 100.0)
        for patch in (
            {"channel1_offset_v": 5.0},
            {"channel1_probe_ratio": 0.5},
        ):
            self.assertEqual(self.configure(client, **patch), ENVELOPE, patch)

    def test_the_trigger_action_reads_the_mode_back(self) -> None:
        client = self.serve()
        receipt = client.invoke("x-cap.krystalmonolith.scope_trigger.v1",
                                {"mode": "edge", "source": "ch2", "slope": "falling"},
                                **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"mode": "edge"})
        state = self.state(client, ["trigger_mode", "trigger_edge_source", "trigger_edge_slope"])
        self.assertEqual(state["trigger_mode"], "edge")
        self.assertEqual(state["trigger_edge_source"], "ch2")
        self.assertEqual(state["trigger_edge_slope"], "falling")
        self.assertEqual(self.trigger(client, mode="pattern"), "completed")
        self.assertEqual(self.state(client, ["trigger_mode"])["trigger_mode"], "pattern")
        self.assertEqual(self.trigger(client, mode="nonsense"), ENVELOPE)

    def test_the_trigger_level_is_operator_required(self) -> None:
        client = self.serve()
        self.assertEqual(self.trigger(client, mode="edge", trigger_level_v=1.5), LIMITS_UNSET)
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.trigger(client, mode="edge", trigger_level_v=1.5), "completed")
        self.assertEqual(self.state(client, ["trigger_edge_level_v"])["trigger_edge_level_v"], 1.5)
        self.assertEqual(self.trigger(client, mode="edge", trigger_level_v=6.0), ENVELOPE)

    def test_the_measurement_action_returns_a_scalar_and_its_unit(self) -> None:
        client = self.serve()
        receipt = self.measure(client, "vpp", "ch1")
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"value": 3.3, "unit": "V"})  # placeholder
        self.assertEqual(self.measure(client, "freq", "ch2")["output"]["unit"], "Hz")
        receipt = client.invoke("x-cap.krystalmonolith.scope_measure.v1",
                                {"item": "unknown", "source": "ch1"}, **self.ids)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.CAPABILITY.INPUT_INVALID")

    def test_the_capture_action(self) -> None:
        client = self.serve()
        for action in ("stop", "run", "single"):
            receipt = client.invoke("x-cap.krystalmonolith.scope_capture.v1",
                                    {"capture_action": action}, **self.ids)
            self.assertEqual(receipt["status"], "completed", action)
            self.assertEqual(receipt["output"], {"accepted": True}, action)
        receipt = client.invoke("x-cap.krystalmonolith.scope_capture.v1",
                                {"capture_action": "hold"}, **self.ids)
        self.assertEqual(receipt["error"]["mhs_code"], ENVELOPE)

    def test_the_estop_stops_the_native_acquisition(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        self.assertTrue(driver.native._running)
        driver.estop("test")
        self.assertFalse(driver.native._running)


if __name__ == "__main__":
    unittest.main()
