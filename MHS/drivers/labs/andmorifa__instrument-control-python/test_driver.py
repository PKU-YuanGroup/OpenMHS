"""Acceptance run of the Red Pitaya package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
ESTOP = "MHS.SAFETY.ESTOP_ENGAGED"
QUERY = "x-cap.andmorifa.scpi_query.v1"


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class RedPitayaCases(unittest.TestCase):
    def serve(self):
        server = load(HERE, backend="fake")
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_the_connection_read(self) -> None:
        client = self.serve()
        self.assertTrue(self.state(client)["connected"])

    def test_the_query_forwards_the_caller_supplied_command(self) -> None:
        client = self.serve()
        receipt = client.invoke(QUERY, {"command": "TEST?"}, **self.ids)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["output"], {"response": "OK: TEST?"})   # the fake's placeholder reply
        self.assertTrue(self.state(client)["connected"])

    def test_the_estop_closes_the_socket_and_latches(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        self.assertFalse(self.state(client)["connected"])
        refused = client.invoke(QUERY, {"command": "TEST?"}, **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], ESTOP)

    def test_an_operator_reset_reopens_the_socket(self) -> None:
        client = self.serve()
        client.estop("test", **self.ids)
        client.reset(**self.ids)
        self.assertTrue(self.state(client)["connected"])
        receipt = client.invoke(QUERY, {"command": "TEST?"}, **self.ids)
        self.assertEqual(receipt["status"], "completed")


if __name__ == "__main__":
    unittest.main()
