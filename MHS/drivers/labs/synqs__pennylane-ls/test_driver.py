"""Acceptance run of the SYNQS single-qudit package: the gate, plus cases for what is specific to this driver.

Add cases, never remove the check_driver call.  The package is blocked on the missing native stop (RESULT.json); the
gate case below therefore reports the expected G3 failure.  The other cases exercise the fake and the action.
"""

import unittest
from pathlib import Path

from mhs.adapter import close_server, load
from mhs.testing import check_driver, client_for

HERE = Path(__file__).resolve().parent
LIMITS_UNSET = "MHS.SAFETY.LIMITS_UNSET"
ENVELOPE = "MHS.SAFETY.ENVELOPE_VIOLATION"


def _run(observable="ZObs", shots=4, parameter=0.5):
    return {"operations": [{"operation": "RLZ", "parameters": [parameter]}],
            "shots": shots, "observable": observable}


class DriverGate(unittest.TestCase):
    def test_gate(self) -> None:
        report = check_driver(HERE, backend="fake")
        self.assertEqual(report["failed"], [], report)


class SynqsCases(unittest.TestCase):
    def serve(self, site_limits=None):
        server = load(HERE, backend="fake", site_limits=site_limits)
        self.addCleanup(close_server, server)
        client = client_for(server)
        device_id = client.hello()["devices"][0]["device_id"]
        session = client.open_session(device_ids=[device_id])["session_id"]
        self.ids = {"device_id": device_id, "session_id": session}
        return client

    def state(self, client):
        return client.read("main", **self.ids)["state"]

    def test_reads_before_a_job(self) -> None:
        client = self.serve()
        state = self.state(client)
        self.assertEqual((state["qdim"], state["shots"], state["job_id"], state["job_status"]), (2, 1, "", "NONE"))
        self.assertTrue(state["endpoint"])

    def test_the_fake_runs_the_native_job_flow(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        receipt = client.invoke("x-cap.synqs.run_experiment.v1", _run(), **self.ids)
        self.assertEqual(receipt["status"], "completed", receipt)
        output = receipt["output"]
        self.assertEqual((len(output["samples"]), output["qdim"]), (4, 2))
        self.assertTrue(output["job_id"])
        state = self.state(client)
        self.assertEqual(state["job_status"], "DONE")
        self.assertEqual(state["shots"], 4)                  # the payload's shots, not the configured default

    def test_without_the_operator_overlay_the_action_is_refused(self) -> None:
        client = self.serve()
        refused = client.invoke("x-cap.synqs.run_experiment.v1", _run(), **self.ids)
        self.assertEqual(refused["status"], "rejected")
        self.assertEqual(refused["error"]["mhs_code"], LIMITS_UNSET)
        state = self.state(client)
        self.assertEqual((state["job_id"], state["job_status"]), ("", "NONE"))

    def test_the_example_overlay_refuses_out_of_envelope_values(self) -> None:
        client = self.serve(str(HERE / "site-limits.example.json"))
        refused = client.invoke("x-cap.synqs.run_experiment.v1", _run(shots=101), **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        refused = client.invoke("x-cap.synqs.run_experiment.v1", _run(parameter=100.0), **self.ids)
        self.assertEqual(refused["error"]["mhs_code"], ENVELOPE)
        state = self.state(client)
        self.assertEqual((state["job_id"], state["job_status"]), ("", "NONE"))


if __name__ == "__main__":
    unittest.main()
