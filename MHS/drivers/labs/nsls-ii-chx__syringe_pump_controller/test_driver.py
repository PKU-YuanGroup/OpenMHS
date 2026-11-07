"""Acceptance run of the CHX syringe-pump package: the gate, plus cases specific to this driver.

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
PUMP = "cap.actuation.pump.v1"
STOP = "x-cap.nsls-ii-chx.stop_pump.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SyringePumpCases(unittest.TestCase):
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

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_every_numeric_input_waits_for_the_site(self) -> None:
        client = self.serve()
        for patch in ({"flow_rate": 3000.0}, {"volume": 500.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        state = self.state(client)
        self.assertEqual((state["flow_rate"], state["volume"]), (0.0, 0.0))   # the fake's placeholders, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, flow_rate=3000.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 3000.0)
        self.assertEqual(state["direction"], "forward")
        self.assertEqual(self.configure(client, flow_rate=-3000.0)["status"], "completed")
        state = self.state(client)
        self.assertEqual(state["flow_rate"], -3000.0)                       # WDR is reported as a negative rate
        self.assertEqual(state["direction"], "reverse")
        self.assertEqual(self.configure(client, volume=500.0)["status"], "completed")
        self.assertEqual(self.state(client)["volume"], 500.0)
        for patch in ({"flow_rate": 6001.0}, {"flow_rate": -6001.0}, {"volume": 1001.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_a_dispense_reports_the_volume_and_sets_the_rate(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500,
                                       "duration_s": 10}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"dispensed_volume": 500.0, "duration_s": 10.0})
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 3000.0)                       # 50 uL/s in uL/min
        self.assertEqual(state["direction"], "forward")
        self.assertEqual(state["volume"], 500.0)
        self.assertEqual(state["dispensed_volume"], 500.0)
        reverse = client.invoke(PUMP, {"flow_rate": 40, "direction": "reverse", "volume": 400,
                                       "duration_s": 10}, **self.ids)
        self.assertEqual(reverse["status"], "completed")
        self.assertEqual(reverse["output"]["dispensed_volume"], 400.0)
        state = self.state(client)
        self.assertEqual(state["flow_rate"], -2400.0)                      # WDR is reported as a negative rate
        self.assertEqual(state["direction"], "reverse")

    def test_the_safe_state_action_and_the_estop_latch(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        stopped = client.invoke(STOP, {}, **self.ids)
        self.assertEqual(stopped["status"], "completed")
        self.assertEqual(stopped["output"], {"stopped": True})
        client.estop("test", **self.ids)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
