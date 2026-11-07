"""Acceptance run of the Rigol DS1000Z package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The numbers asserted below are the fake's placeholder values
(fake.py), not facts about an instrument.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load, load_driver
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
SETTINGS = "x-cap.pmezydlo.settings.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class Reads(unittest.TestCase):
    def test_the_reads_use_the_queries_of_the_clone(self) -> None:
        driver = load_driver(HERE, "fake")
        self.addCleanup(driver.close)
        # setup() ran get_active_channel(), which queried the four configured channels of the fake.
        self.assertEqual(driver.native.active_chan, ["CHAN1", "CHAN3"])
        self.assertEqual(driver.native.queries[:4], [":CHAN1:DISP?", ":CHAN2:DISP?", ":CHAN3:DISP?", ":CHAN4:DISP?"])
        state = driver.read("main")
        self.assertEqual(state["manufacturer"], "RIGOL TECHNOLOGIES")
        self.assertEqual(state["instrument_model"], "DS1054Z")
        self.assertEqual(state["serial_number"], "FAKE000000")
        self.assertEqual(state["firmware_version"], "00.04.04.SP4")
        self.assertEqual(state["active_channels"], ["CHAN1", "CHAN3"])
        self.assertEqual(state["timebase_scale_s_per_div"], 0.001)
        self.assertEqual(state["timebase_offset_s"], 0.0)
        self.assertIn(":TIM:SCAL?", driver.native.queries)
        self.assertIn(":TIM:OFFS?", driver.native.queries)


class Settings(unittest.TestCase):
    def test_the_action_reads_each_active_channel(self) -> None:
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session_id = client.open_session(device_ids=[device_id])["session_id"]
        receipt = client.invoke(SETTINGS, {}, device_id=device_id, session_id=session_id)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual(output["instrument_model"], "DS1054Z")
        self.assertEqual(output["active_channels"], ["CHAN1", "CHAN3"])
        self.assertEqual(output["timebase_scale_s_per_div"], 0.001)
        self.assertEqual(output["timebase_offset_s"], 0.0)
        self.assertEqual(output["channel_scales_v_per_div"], [0.5, 0.5])
        self.assertEqual(output["channel_offsets_v"], [0.0, 0.0])


if __name__ == "__main__":
    unittest.main()
