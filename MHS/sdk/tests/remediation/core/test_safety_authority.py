"""Regression tests for SAFE-001..004 (review counterexamples)."""

from __future__ import annotations

import copy
import sys
import threading
import unittest
from pathlib import Path

from mhs import canonical, connect
from mhs.errors import MHSError

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "core"))
import _device_server  # noqa: E402


def _two_device_server():
    from mhs.server import Device

    server = _device_server.build_server()
    base = next(iter(server.devices.values()))
    second = Device(
        "mhs://localhost/tests/tiny2",
        base.display_name,
        mode=base.mode,
        resources=copy.deepcopy(base.resources),
        capabilities=copy.deepcopy(base.capabilities),
        safety=copy.deepcopy(base.safety),
        fidelity=copy.deepcopy(base.fidelity),
        bridge=_device_server.TinyBridge(),
        instance_id=canonical.ulid(),
    )
    server.devices[second.device_id] = second
    server._revisions[second.device_id] = 0
    server._device_locks[second.device_id] = threading.Lock()
    server._latched[second.device_id] = False
    return server, base.device_id, second.device_id


class ResourceWriteAuthorityTests(unittest.TestCase):
    """SAFE-001: resource.write is not a generic mutation escape hatch."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = self._start()
        self.session = self.client.open_session(
            [self.device_id], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]
        self.world = self.client.capability_resource(
            "cap.device.configure.v1", device_id=self.device_id
        )

    def _start(self, two=False):
        if two:
            server, first, second = _two_device_server()
            extra = {"second": second}
        else:
            server = _device_server.build_server()
            extra = {}
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        manifest = client.devices()[0]
        test = self
        test._extra = extra
        return server, handle, client, manifest["device_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()
        close = getattr(self.server, "close", None)
        if callable(close):
            close()

    def test_read_only_session_cannot_write(self):
        session = self.client.open_session(
            [self.device_id], capabilities=["cap.world.state.v1"],
            mode="simulated", ttl_s=300,
        )["session_id"]
        with self.assertRaises(MHSError) as ctx:
            self.client.write("world", {"tick": 5}, device_id=self.device_id,
                              session_id=session)
        self.assertIn(ctx.exception.code, (
            "MHS.RESOURCE.NOT_WRITABLE", "MHS.SESSION.CAPABILITY_NOT_GRANTED",
        ))
        self.assertEqual(
            self.client.read("world", device_id=self.device_id)["state"]["tick"], 0
        )

    def test_open_interlock_blocks_write_and_leaves_state_unchanged(self):
        # Bind the write capability to the door interlock for this test.
        device = self.server.devices[self.device_id]
        for interlock in device.safety.interlocks:
            if interlock.get("id") == "door_closed":
                interlock.setdefault("required_for", []).append(
                    "cap.device.configure.v1"
                )
        self.client.invoke("cap.test.set_door.v1", {"state": "open"},
                           device_id=self.device_id)
        before = self.client.read("world", device_id=self.device_id)["state"]
        receipt = self.client.write("world", {"tick": 42}, device_id=self.device_id)
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.INTERLOCK_OPEN")
        after = self.client.read("world", device_id=self.device_id)["state"]
        self.assertEqual(after["tick"], before["tick"])

    def test_no_write_capability_is_rejected(self):
        device = self.server.devices[self.device_id]
        device.capabilities = [
            cap for cap in device.capabilities
            if cap.capability_id != "cap.device.configure.v1"
        ]
        device.__post_init__()
        with self.assertRaises(MHSError) as ctx:
            self.client.write("world", {"tick": 1}, device_id=self.device_id)
        self.assertEqual(ctx.exception.code, "MHS.RESOURCE.NOT_WRITABLE")

    def test_write_on_other_device_needs_session_authority(self):
        self.client.close()
        self.handle.shutdown()
        self.server, first, second = _two_device_server()
        self.handle = self.server.start_http("127.0.0.1", 0)
        self.client = connect(self.handle.url)
        self.device_id = first
        session = self.client.open_session(
            [first], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]
        with self.assertRaises(MHSError) as ctx:
            self.client.write("world", {"tick": 9}, device_id=second,
                              session_id=session)
        self.assertIn(ctx.exception.code, (
            "MHS.SESSION.CAPABILITY_NOT_GRANTED", "MHS.CAPABILITY.INPUT_INVALID",
        ))


class PermitBindingTests(unittest.TestCase):
    """SAFE-002: permits are bound to session, device, resource and action."""

    def setUp(self):
        self.server, self.handle, self.client, self.device_id = _start_two()
        self.first, self.second = self.device_id, _SECOND[0]
        self.session = self.client.open_session(
            [self.first, self.second], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]

    def tearDown(self):
        self.client.close()
        self.handle.shutdown()

    def test_permit_from_another_session_is_rejected(self):
        permit = self.client.permit(
            "cap.actuation.valve.v1", {"gate": "divert"},
            resource="world", device_id=self.first, session_id=self.session,
        )
        other = self.client.open_session(
            [self.first], capabilities=None, mode="simulated", ttl_s=300
        )["session_id"]
        receipt = self.client.invoke(
            "cap.actuation.valve.v1", {"gate": "divert"}, device_id=self.first,
            session_id=other, permit_id=permit["permit_id"],
        )
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.PERMIT_INVALID")

    def test_permit_for_another_device_is_rejected(self):
        permit = self.client.permit(
            "cap.actuation.valve.v1", {"gate": "divert"},
            resource="world", device_id=self.first, session_id=self.session,
        )
        receipt = self.client.invoke(
            "cap.actuation.valve.v1", {"gate": "divert"}, device_id=self.second,
            session_id=self.session, permit_id=permit["permit_id"],
        )
        self.assertEqual(receipt["status"], "rejected")
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.PERMIT_INVALID")

    def test_permit_for_nonexistent_resource_is_rejected(self):
        with self.assertRaises(MHSError) as ctx:
            self.client.permit(
                "cap.actuation.valve.v1", {"gate": "divert"},
                resource="does_not_exist", device_id=self.first,
                session_id=self.session,
            )
        self.assertEqual(ctx.exception.code, "MHS.SAFETY.PERMIT_INVALID")


_SECOND: list[str] = []


def _start_two():
    server, first, second = _two_device_server()
    _SECOND[:] = [second]
    handle = server.start_http("127.0.0.1", 0)
    client = connect(handle.url)
    return server, handle, client, first


class ApprovalTrustTests(unittest.TestCase):
    """SAFE-003: R3 hardware approvals require a trusted approval authority."""

    def _server(self, verifier=None):
        server = _device_server.build_server()
        device = next(iter(server.devices.values()))
        device.mode = "hardware"
        device.safety.risk_class = "R3"
        server._approval_verifier = verifier
        handle = server.start_http("127.0.0.1", 0)
        return server, handle, connect(handle.url)

    def test_r3_hardware_session_fails_closed_without_authority(self):
        server, handle, client = self._server()
        try:
            with self.assertRaises(MHSError) as ctx:
                client.open_session([], capabilities=None, mode=None, ttl_s=60)
            self.assertEqual(ctx.exception.code, "MHS.SAFETY.APPROVAL_REQUIRED")
            self.assertEqual(
                (ctx.exception.data or {}).get("reason"),
                "approval_authority_unavailable",
            )
        finally:
            client.close()
            handle.shutdown()

    def test_client_asserted_human_is_not_authority(self):
        server, handle, client = self._server()
        try:
            with self.assertRaises(MHSError) as ctx:
                client.open_session(
                    [], capabilities=None, mode=None, ttl_s=60,
                    approvals=[{"principal": "human:arbitrary", "method": "human_click"}],
                )
            self.assertEqual(ctx.exception.code, "MHS.SAFETY.APPROVAL_REQUIRED")
        finally:
            client.close()
            handle.shutdown()

    def test_verified_human_approval_opens_and_permits(self):
        def verifier(request):
            methods = {a.get("method") for a in request.get("approvals") or []}
            if "human_click" not in methods:
                return {"verified": False}
            return {
                "verified": True,
                "approvals": [{"principal": "human:alice", "method": "human_click",
                               "approved_at": canonical.now_rfc3339()}],
            }

        server, handle, client = self._server(verifier)
        try:
            session = client.open_session(
                [], capabilities=None, mode=None, ttl_s=60,
                approvals=[{"principal": "human:alice", "method": "human_click"}],
            )["session_id"]
            device_id = client.devices()[0]["device_id"]
            permit = client.permit(
                "cap.actuation.valve.v1", {"gate": "divert"},
                approvals=[{"principal": "human:alice", "method": "human_click"}],
                resource="world", device_id=device_id, session_id=session,
            )
            self.assertIn("permit_id", permit)
        finally:
            client.close()
            handle.shutdown()


class CumulativeLimitTests(unittest.TestCase):
    """SAFE-004: declared rolling windows are enforced across sessions."""

    def test_rolling_window_is_cumulative_and_survives_session_churn(self):
        server = _device_server.build_server()
        device = next(iter(server.devices.values()))
        device.safety.envelope["cap.world.step.v1"] = {
            "ticks": {"max": 10, "per": "rolling_24h", "unit": "1"}
        }
        handle = server.start_http("127.0.0.1", 0)
        client = connect(handle.url)
        try:
            session = client.open_session(
                [device.device_id], capabilities=None, mode="simulated", ttl_s=300
            )["session_id"]
            first = client.invoke("cap.world.step.v1", {"ticks": 6},
                                  device_id=device.device_id, session_id=session)
            self.assertEqual(first["status"], "completed")
            client.request("mhs.session.close", {"session_id": session})
            session2 = client.open_session(
                [device.device_id], capabilities=None, mode="simulated", ttl_s=300
            )["session_id"]
            second = client.invoke("cap.world.step.v1", {"ticks": 6},
                                   device_id=device.device_id, session_id=session2)
            # 6 used + 6 requested exceeds the declared 10-per-24h budget even
            # though a single 6 is inside the per-call max.
            self.assertEqual(second["status"], "rejected")
            self.assertEqual(second["error"]["mhs_code"], "MHS.SAFETY.CUMULATIVE_LIMIT")
            details = second["error"]["details"]
            self.assertEqual(details["used"], 6)
            self.assertEqual(details["limit"], 10)
            self.assertEqual(details["window"], "rolling_24h")
        finally:
            client.close()
            handle.shutdown()


if __name__ == "__main__":
    unittest.main()
