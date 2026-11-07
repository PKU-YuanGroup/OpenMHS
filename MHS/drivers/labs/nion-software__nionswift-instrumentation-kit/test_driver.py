"""Acceptance run of the Nion instrument package: the gate, plus cases for what is specific to this driver.

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


class NionInstrumentCases(unittest.TestCase):
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

    def test_the_reads_see_the_value_manager(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual(state["beam_voltage"], 200000.0)       # placeholder: fake.py starting value
        self.assertEqual(state["defocus_m"], 0.0)               # placeholder: fake.py starting value
        self.assertEqual(state["energy_offset_ev"], 0.0)        # placeholder: fake.py starting value
        self.assertEqual(state["beam_current_a"], 1.0e-11)      # placeholder: fake.py starting value

    def test_the_writes_wait_for_the_site(self) -> None:
        client = self.serve()
        refused = self.configure(client, beam_voltage=100000)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        self.assertEqual(self.state(client)["beam_voltage"], 200000.0)  # placeholder, untouched

    def test_the_example_overlay_supplies_the_ranges(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        completed = self.configure(client, beam_voltage=100000, defocus_m=2.5e-7, energy_offset_ev=-150)
        self.assertEqual(completed["status"], "completed", completed)
        self.assertEqual(completed["output"]["applied"],
                         {"beam_voltage": 100000.0, "defocus_m": 2.5e-7, "energy_offset_ev": -150.0})
        state = self.state(client)
        self.assertEqual(state["beam_voltage"], 100000.0)
        self.assertEqual(state["defocus_m"], 2.5e-7)
        self.assertEqual(state["energy_offset_ev"], -150.0)
        for patch in ({"beam_voltage": 300001}, {"defocus_m": 2.0e-6}, {"energy_offset_ev": 1001}):
            refused = self.configure(client, **patch)
            self.assertEqual(refused["status"], "rejected", patch)
            self.assertEqual(refused["error"]["mhs_code"], ENVELOPE, patch)

    def test_the_high_tension_off_action_is_the_safe_state(self) -> None:
        client = self.serve()
        result = client.invoke("x-cap.nion-software.high_tension_off.v1", {}, **self.ids)
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(result["output"], {"high_tension_off": True})
        self.assertEqual(self.state(client)["beam_voltage"], 0.0)

    def test_the_estop_removes_the_high_tension_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertEqual(self.state(client)["beam_voltage"], 0.0)
        # A safe-state action stays callable while latched so the runtime can always reach the safe state.
        safe = client.invoke("x-cap.nion-software.high_tension_off.v1", {}, **self.ids)
        self.assertEqual(safe["status"], "completed", safe)
        refused_write = self.configure(client, beam_voltage=100000)
        self.assertEqual(refused_write["error"]["mhs_code"], ESTOP)


if __name__ == "__main__":
    unittest.main()
