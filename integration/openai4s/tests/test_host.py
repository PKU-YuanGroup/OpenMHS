"""MHSHost invariants: hardware gating, permits, unknown outcomes, evidence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openai4s_mhs.config import EndpointSpec, MHSConfig
from openai4s_mhs.host import MHSHost, MHSHostError
from openai4s_mhs.tools import read_state

from .fake_endpoint import FakeMHSServer, fake_connect

try:
    from mhs.canonical import digest as canonical_digest
except Exception:  # pragma: no cover
    canonical_digest = None


def _config(tmp: str, *, allow_hardware: bool = False) -> MHSConfig:
    return MHSConfig(
        endpoints=[
            EndpointSpec(id="fake", command=["python3", "-m", "fake.endpoint"])
        ],
        evidence_log=str(Path(tmp) / "evidence.jsonl"),
        allow_hardware=allow_hardware,
        command_timeout_ms=5000,
    )


class HostTestCase(unittest.TestCase):
    def make_host(self, server: FakeMHSServer, **config_kwargs) -> MHSHost:
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-host-test-")
        self.addCleanup(self._tmp.cleanup)
        host = MHSHost(
            _config(self._tmp.name, **config_kwargs), sdk_connect=fake_connect(server)
        )
        self.addCleanup(host.close)
        return host


class DiscoveryAndReadTests(HostTestCase):
    def test_devices_disclose_mode_risk_and_fidelity(self) -> None:
        server = FakeMHSServer()
        host = self.make_host(server)
        devices = host.devices()
        self.assertEqual(len(devices), 1)
        device = devices[0]
        self.assertEqual(device["mode"], "simulated")
        self.assertEqual(device["risk_class"], "R1")
        self.assertEqual(device["fidelity"]["level"], "F0")
        self.assertIn("no physics", device["fidelity"]["gaps"][0])
        self.assertEqual(device["endpoint_id"], "fake")
        self.assertEqual(len(device["capabilities"]), 3)

    def test_read_opens_only_the_read_capability(self) -> None:
        server = FakeMHSServer()
        host = self.make_host(server)
        state = host.read("conveyor")
        self.assertEqual(state["revision"], 0)
        self.assertEqual(len(server.sessions), 1)
        session = next(iter(server.sessions.values()))
        self.assertEqual(session["capabilities"], ["cap.world.state.v1"])

    def test_domain_manifest_read_uses_a_safe_capability_grant(self) -> None:
        server = FakeMHSServer()
        base_manifest = server.manifest

        def domain_manifest() -> dict:
            manifest = base_manifest()
            manifest["capabilities"] = [
                cap
                for cap in manifest["capabilities"]
                if not cap["capability_id"].startswith("cap.world.state")
            ]
            manifest["capabilities"].append(
                {
                    "capability_id": "cap.fluid.level.v1",
                    "title": "Read well levels",
                    "resource": "world",
                }
            )
            return manifest

        server.manifest = domain_manifest  # type: ignore[method-assign]
        host = self.make_host(server)
        state = read_state(host, "conveyor")
        self.assertEqual(state["via_capability"], "cap.fluid.level.v1")
        self.assertEqual(state["revision"], 0)
        self.assertEqual(len(server.sessions), 1)
        session = next(iter(server.sessions.values()))
        self.assertEqual(session["capabilities"], ["cap.fluid.level.v1"])

    def test_unknown_device_is_a_coded_error(self) -> None:
        host = self.make_host(FakeMHSServer())
        with self.assertRaises(MHSHostError) as caught:
            host.read("does-not-exist")
        self.assertEqual(caught.exception.code, "MHS.HOST.DEVICE_NOT_FOUND")
        self.assertIn("mhs_code", caught.exception.to_dict())


class HardwareGateTests(HostTestCase):
    def test_hardware_device_is_refused_by_default(self) -> None:
        server = FakeMHSServer(mode="hardware")
        host = self.make_host(server, allow_hardware=False)
        with self.assertRaises(MHSHostError) as caught:
            host.read("conveyor")
        self.assertEqual(caught.exception.code, "MHS.HOST.HARDWARE_GATED")
        self.assertEqual(server.sessions, {})

    def test_hardware_device_allowed_when_operator_opts_in(self) -> None:
        server = FakeMHSServer(mode="hardware")
        host = self.make_host(server, allow_hardware=True)
        state = host.read("conveyor")
        self.assertEqual(state["revision"], 0)
        self.assertEqual(len(server.sessions), 1)


class PermitTests(HostTestCase):
    def test_high_risk_simulated_command_denied_without_approval(self) -> None:
        server = FakeMHSServer(risk_class="R2", permit_patterns=("cap.actuation.*",))
        host = self.make_host(server)
        with self.assertRaises(MHSHostError) as caught:
            host.command("conveyor", "cap.actuation.valve.v1", {"gate": "divert"})
        self.assertEqual(caught.exception.code, "MHS.SAFETY.APPROVAL_REQUIRED")
        self.assertEqual(server.permits, {})
        self.assertEqual(server.receipts, [])

    def test_approved_permit_is_bound_to_the_input_digest(self) -> None:
        server = FakeMHSServer(risk_class="R2", permit_patterns=("cap.actuation.*",))
        seen: list[dict] = []

        def approve(request: dict) -> dict:
            seen.append(request)
            return {
                "approved": True,
                "principal": "test:human",
                "method": "unit_test",
            }

        host = self.make_host(server)
        host.approval_provider = approve
        payload = {"gate": "divert"}
        receipt = host.command("conveyor", "cap.actuation.valve.v1", payload)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["mode"], "simulated")
        self.assertEqual(seen[0]["risk_class"], "R2")
        self.assertEqual(seen[0]["capability_id"], "cap.actuation.valve.v1")
        self.assertEqual(len(server.permits), 1)
        permit = next(iter(server.permits.values()))
        if canonical_digest is not None:
            self.assertEqual(permit["input_digest"], canonical_digest(payload))
        self.assertEqual(permit["capability_id"], "cap.actuation.valve.v1")
        self.assertEqual(permit["approvals"][0]["principal"], "test:human")

    def test_r0_r1_simulated_commands_need_no_permit(self) -> None:
        server = FakeMHSServer(risk_class="R1")
        host = self.make_host(server)
        receipt = host.command("conveyor", "cap.world.step.v1", {"ticks": 3})
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(server.permits, {})


class OutcomeTests(HostTestCase):
    def test_unknown_outcome_is_returned_not_retried(self) -> None:
        server = FakeMHSServer(risk_class="R0", unknown_once=True)
        host = self.make_host(server)
        receipt = host.command("conveyor", "cap.world.step.v1", {"ticks": 5})
        self.assertEqual(receipt["status"], "unknown")
        self.assertEqual(receipt["error"]["code"], "MHS.OUTCOME.UNKNOWN")
        self.assertEqual(server.tick, 0)
        self.assertEqual(len(server.receipts), 1)

    def test_estop_then_command_returns_a_rejection_receipt(self) -> None:
        server = FakeMHSServer(risk_class="R1")
        host = self.make_host(server)
        stop = host.estop("conveyor", "unit test")
        self.assertEqual(stop["status"], "completed")
        rejected = host.command("conveyor", "cap.world.step.v1", {"ticks": 1})
        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(rejected["error"]["code"], "MHS.SAFETY.INTERLOCK_OPEN")
        status = host.safety_status("conveyor")
        self.assertEqual(status["estop"], "engaged")
        self.assertTrue(status["latched"])
        host.reset("conveyor")
        self.assertEqual(host.safety_status("conveyor")["estop"], "released")

    def test_receipts_are_appended_to_the_local_ledger_and_chain(self) -> None:
        server = FakeMHSServer()
        host = self.make_host(server)
        receipt = host.command("conveyor", "cap.world.step.v1", {"ticks": 2})
        ledger = host.ledger()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["receipt_id"], receipt["receipt_id"])
        self.assertEqual(ledger[0]["command_id"], receipt["command_id"])
        self.assertEqual(ledger[0]["status"], "completed")
        self.assertTrue(Path(host.config.evidence_log).exists())
        stored = [
            json.loads(line)
            for line in Path(host.config.evidence_log).read_text().splitlines()
        ]
        self.assertEqual(stored[0]["receipt_id"], receipt["receipt_id"])

        bundle = host.evidence_export()
        self.assertEqual(bundle["head_digest"], receipt["evidence"]["digest"])
        report = host.evidence_verify(bundle)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["checked"], 1)
        self.assertEqual(report["head_digest"], bundle["head_digest"])

    def test_operations_and_cancel(self) -> None:
        server = FakeMHSServer()
        server.operations["op_1"] = {"operation_id": "op_1", "status": "running"}
        host = self.make_host(server)
        listing = host.operations()
        self.assertEqual(listing["operations"][0]["operation_id"], "op_1")
        cancelled = host.cancel("op_1")
        self.assertEqual(cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
