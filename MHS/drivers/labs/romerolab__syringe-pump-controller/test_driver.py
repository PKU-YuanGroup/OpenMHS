"""Acceptance run of the New Era syringe-pump package: the gate, plus cases specific to this driver.

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
        for patch in ({"flow_rate": 1000.0}, {"diameter": 10.0}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET, patch)
        refused = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["flow_rate"], 0.0)          # the fake's placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        self.assertEqual(self.configure(client, flow_rate=6000.0)["status"], "completed")
        self.assertEqual(self.state(client)["flow_rate"], 6000.0)       # the MH branch reads back as UH
        self.assertEqual(self.configure(client, flow_rate=4999.0)["status"], "completed")
        self.assertEqual(self.state(client)["flow_rate"], 4999.0)       # the UH branch
        self.assertEqual(self.configure(client, diameter=8.585)["status"], "completed")
        self.assertEqual(self.state(client)["diameter"], 8.585)
        for patch in ({"flow_rate": 3600001.0}, {"diameter": 50.1}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_a_dispense_reports_the_volume_and_sets_the_rate(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke(PUMP, {"flow_rate": 50, "direction": "forward", "volume": 500,
                                       "duration_s": 10}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"dispensed_volume": 500.0, "duration_s": 10.0})
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 180000.0)                  # 50 uL/s in uL/hr
        self.assertEqual(state["direction"], "forward")
        reverse = client.invoke(PUMP, {"flow_rate": 40, "direction": "reverse", "volume": 400,
                                       "duration_s": 10}, **self.ids)
        self.assertEqual(reverse["output"]["dispensed_volume"], 400.0)
        state = self.state(client)
        self.assertEqual(state["flow_rate"], -144000.0)                # WDR is reported as a negative rate
        self.assertEqual(state["direction"], "reverse")

    def test_prime_uses_the_upstream_sequence_and_the_estop_latches(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        primed = client.invoke("x-cap.romerolab.prime_pump.v1", {}, **self.ids)
        self.assertEqual(primed["status"], "completed")
        self.assertEqual(primed["output"], {"priming": True})
        self.assertEqual(self.state(client)["flow_rate"], 10000.0)      # RAT10.0MH
        client.estop("test", **self.ids)
        state = self.state(client)
        self.assertEqual(state["flow_rate"], 10000.0)                   # the e-stop leaves the rate, not the pump
        refused = client.invoke("x-cap.romerolab.prime_pump.v1", {}, **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
