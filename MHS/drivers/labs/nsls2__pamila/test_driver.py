"""Acceptance run of the PAMILA read-only variable-list package: the gate plus repository-specific cases.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load_driver
from mhs.errors import MHSError
from mhs.driver import build_server
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
PRECONDITION = "MHS.DEVICE.PRECONDITION_UNMET"
NAMES = ["PLACEHOLDER_MLV_A", "PLACEHOLDER_MLV_B", "PLACEHOLDER_MLV_C"]


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class PamilaVariableListCases(unittest.TestCase):
    def serve(self):
        driver = load_driver(HERE, backend="fake")
        server = build_server(driver)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client, driver.native

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_state_lists_members_values_and_units(self) -> None:
        client, _fake = self.serve()
        state = self.state(client)
        self.assertEqual(state["mlv_count"], 3)                          # placeholder
        self.assertEqual(state["mlv_names"], NAMES)                      # placeholder
        self.assertEqual(state["enabled_mlv_names"], NAMES)              # placeholder
        self.assertEqual(state["enabled_status"], [True, True, True])
        self.assertEqual(state["values"], [1.5, 2.5, 3.5])               # placeholder
        self.assertEqual(state["value_units"], ["A", "m", "1"])          # placeholder

    def test_read_channels_selects_an_enabled_member(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke("cap.sensing.read.v1", {"fields": ["PLACEHOLDER_MLV_B"]}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"], {"PLACEHOLDER_MLV_B": 2.5})   # placeholder
        self.assertIn("sampled_at", receipt["output"])

    def test_read_channels_without_fields_returns_every_enabled_member(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke("cap.sensing.read.v1", {}, **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(receipt["output"]["values"],
                         {"PLACEHOLDER_MLV_A": 1.5, "PLACEHOLDER_MLV_B": 2.5, "PLACEHOLDER_MLV_C": 3.5})  # placeholder

    def test_the_reads_follow_the_list_enabled_members(self) -> None:
        # The package serves no write (model review): the enabled set is the list's own, changed outside OpenMHS.
        client, fake = self.serve()
        fake.put_enabled_status([True, False, True])
        state = self.state(client)
        self.assertEqual(state["enabled_status"], [True, False, True])
        self.assertEqual(state["enabled_mlv_names"], ["PLACEHOLDER_MLV_A", "PLACEHOLDER_MLV_C"])  # placeholder
        self.assertEqual(state["values"], [1.5, 3.5])                    # placeholder

    def test_no_write_is_served(self) -> None:
        client, _fake = self.serve()
        with self.assertRaises(MHSError) as raised:
            client.write("main", {"enabled_status": [True, False, True]}, **self.ids)
        self.assertEqual(raised.exception.code, "MHS.RESOURCE.NOT_WRITABLE")
        self.assertEqual(client.hello()["devices"][0]["risk_class"], "R0")

    def test_an_unknown_member_is_refused(self) -> None:
        client, _fake = self.serve()
        receipt = client.invoke("cap.sensing.read.v1", {"fields": ["NOT_A_MEMBER"]}, **self.ids)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], PRECONDITION)

    def test_the_estop_is_the_software_latch_only(self) -> None:
        # R0, no native stop (model review): the e-stop latches the endpoint and calls nothing on the list.
        client, fake = self.serve()
        stopped = client.estop("test", **self.ids)
        self.assertEqual(stopped["status"], "completed", stopped)
        self.assertTrue(fake._parallel_get_enabled)                      # the list's switch is untouched
        self.assertEqual(self.state(client)["values"], [1.5, 2.5, 3.5])  # placeholder; reads stay available


if __name__ == "__main__":
    unittest.main()
