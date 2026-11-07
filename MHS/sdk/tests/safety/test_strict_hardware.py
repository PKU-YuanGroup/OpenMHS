"""Strict-mode hardware rules: arming, verified permits, operator reset (WP-04 4b).

Ports: the endpoint parts of verify-integration-surfaces ``hw_mcp.py`` (a
model-issued permit on R2 hardware drove the valve, SURF-01) and
``reset_noallow.py`` (the model reset an e-stop the operator had engaged, and
the operator's script resumed), sdk-core ``e6.py`` (another principal's
session reset the latch, SDK-04).
"""

from __future__ import annotations

import unittest

from mhs.server import Capability, action_digest

from ._strict_support import (DESCRIBE, JOINTS, STOP, TOKENS, TORQUE, RecordWarnings, TokenRpc,
                              arm_capabilities, arm_device, arm_safety, arm_server, strict_warnings)
from ._support import error_code, open_session

TORQUE_INPUT = {"joint_torques": [0.5], "duration_s": 0.1}


def _hardware(strict=True, risk="R1", torque=False, **server_kwargs):
    return arm_server(arm_device(mode="hardware", risk=risk, torque=torque), strict=strict, **server_kwargs)


class ArmingTests(unittest.TestCase):
    def test_strict_mode_refuses_unarmed_hardware_actuation(self) -> None:
        server, rpc, device, bridge = _hardware()
        session = open_session(rpc, device)
        receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED")
        self.assertEqual(receipt["error"]["details"]["reason"], "not_armed")
        self.assertEqual(bridge.count(JOINTS), 0)
        self.assertEqual(receipt["state_revision_after"], receipt["state_revision_before"])

    def test_reads_stops_and_estops_are_never_refused_for_arming(self) -> None:
        server, rpc, device, bridge = _hardware()
        session = open_session(rpc, device)
        for capability_id in (DESCRIBE, STOP):
            with self.subTest(capability=capability_id):
                receipt = rpc("mhs.command", session_id=session, capability_id=capability_id, input={},
                              deadline_ms=2000)
                self.assertEqual(receipt["status"], "completed", receipt)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="stop", deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"])

    def test_armed_devices_actuate(self) -> None:
        for armed in (True, ["mhs://localhost/strict/arm"]):
            with self.subTest(armed=armed):
                server, rpc, device, bridge = _hardware(armed=armed)
                session = open_session(rpc, device)
                receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                              input={"joint_positions": [0.1]}, deadline_ms=2000)
                self.assertEqual(receipt["status"], "completed", receipt)
        server, rpc, device, bridge = _hardware(armed=["mhs://localhost/other"])
        receipt = rpc("mhs.command", session_id=open_session(rpc, device), capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED")

    def test_compatibility_mode_arms_implicitly_with_a_warning(self) -> None:
        with RecordWarnings() as warned:
            server, rpc, device, bridge = _hardware(strict=None)
        self.assertTrue(any("hardware-armed-implicitly" in text for text in strict_warnings(warned)))
        receipt = rpc("mhs.command", session_id=open_session(rpc, device), capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_an_explicit_disarm_holds_in_compatibility_mode(self) -> None:
        server, rpc, device, bridge = _hardware(strict=None, armed=False)
        receipt = rpc("mhs.command", session_id=open_session(rpc, device), capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED")
        self.assertEqual(bridge.count(JOINTS), 0)

    def test_simulated_devices_need_no_arming(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, armed=False)
        receipt = rpc("mhs.command", session_id=open_session(rpc, device), capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_armed_must_be_a_bool_or_device_ids(self) -> None:
        with self.assertRaises(TypeError):
            _hardware(armed="mhs://localhost/strict/arm")


class AchievedByArmingTests(unittest.TestCase):
    """Verifier probe p2 P5: an ``achieved_by`` actuation class ran on unarmed hardware with any input.

    Plan 3.6 exempts ``achieved_by`` actions from the latch (step 5), not from
    arming (step 6).  Only reads and stop classes need no arming; the e-stop
    path runs the safe-state actions itself, whatever the arming.
    """

    def _server(self, **server_kwargs):
        device = arm_device(mode="hardware", safety=arm_safety(achieved_by=(STOP, JOINTS)))
        return arm_server(device, **server_kwargs)

    def _move(self, rpc, session):
        return rpc("mhs.command", session_id=session, capability_id=JOINTS,
                   input={"joint_positions": [1.5, -1.0]}, deadline_ms=2000)

    def test_an_achieved_by_actuation_needs_arming(self) -> None:
        for strict, armed in ((True, None), (True, False), (None, False)):
            with self.subTest(strict=strict, armed=armed):
                with RecordWarnings():
                    server, rpc, device, bridge = self._server(strict=strict, armed=armed)
                session = open_session(rpc, device)
                receipt = self._move(rpc, session)
                self.assertEqual(receipt["status"], "rejected", receipt)
                self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED")
                self.assertEqual(bridge.count(JOINTS), 0)
                self.assertEqual(rpc("mhs.command", session_id=session, capability_id=STOP, input={},
                                     deadline_ms=2000)["status"], "completed", "a stop class needs no arming")

    def test_the_estop_still_runs_it_and_the_latch_does_not_arm_it(self) -> None:
        server, rpc, device, bridge = self._server(strict=True)
        session = open_session(rpc, device)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="stop", deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"])
        ran = bridge.count(JOINTS)
        self.assertGreaterEqual(ran, 1, "the stop path runs the safe-state actions on unarmed hardware")
        receipt = self._move(rpc, session)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED", receipt)
        self.assertEqual(bridge.count(JOINTS), ran)

    def test_armed_hardware_runs_it_while_latched(self) -> None:
        server, rpc, device, bridge = self._server(strict=True, armed=True)
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="stop", deadline_ms=1000)
        self.assertEqual(self._move(rpc, session)["status"], "completed", "the latch exempts it (SAFE-029)")


class LateDeviceTests(unittest.TestCase):
    """Verifier probe p3: a device put in ``server.devices`` after a strict server was built ran in compat mode."""

    LATE = "mhs://localhost/strict/late"

    def _late(self, server, **device_kwargs):
        device = arm_device(device_id=self.LATE, **device_kwargs)
        server.devices[device.device_id] = device
        return device

    def test_a_strict_server_applies_the_hardware_rules_to_it(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, auth_tokens=TOKENS)
        late = self._late(server, mode="hardware")
        session = open_session(rpc, late)
        receipt = rpc("mhs.command", session_id=session, capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED", receipt)
        self.assertEqual(late.bridge.count(JOINTS), 0)
        receipt = rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"])
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(error_code(receipt), "MHS.AUTH.FORBIDDEN", receipt)
        self.assertEqual(late.bridge.count("reset"), 0)

    def test_a_strict_server_serves_its_resolved_contract(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        late = self._late(server)
        listed = {item["device_id"]: item for item in rpc("mhs.devices.list", detail="full")["devices"]}
        joints = next(cap for cap in listed[self.LATE]["capabilities"] if cap["capability_id"] == JOINTS)
        self.assertEqual(joints.get("verb"), "invoke", "listed with its resolved contract")
        receipt = rpc("mhs.command", session_id=open_session(rpc, late), capability_id=JOINTS,
                      input={"joint_positions": "not-an-array"}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.CAPABILITY.INPUT_INVALID", receipt)
        self.assertEqual(late.bridge.count(JOINTS), 0)
        self.assertEqual(late.capability(JOINTS).verb, "invoke")
        self.assertTrue(late.capability(JOINTS).publish_verb)

    def test_a_late_device_strict_mode_refuses_is_not_served(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        typo = Capability("cap.motion.joint_positon.v1", "arm")
        late = self._late(server, capabilities=arm_capabilities(extra=[typo]))
        response = rpc.raw("mhs.session.open", device_ids=[late.device_id], mode="simulated")
        self.assertEqual(error_code(response), "MHS.ADAPTER.MANIFEST_INVALID", response)
        self.assertIn("unknown-capability",
                      [item["rule"] for item in response["error"]["data"]["details"]["findings"]])
        self.assertEqual([item["device_id"] for item in rpc("mhs.devices.list")["devices"]], [device.device_id])
        receipt = rpc("mhs.safety.estop", device_id=late.device_id, reason="x", deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"], "every caller may still stop it")

    def test_hello_and_the_default_session_skip_a_refused_late_device(self) -> None:
        """WP-04 4b verifier minor (probe v3_misc M1): hello still listed a late device
        strict mode refuses, and ``session.open`` without ``device_ids`` failed for
        every device with MHS.ADAPTER.MANIFEST_INVALID."""
        server, rpc, device, bridge = arm_server(strict=True)
        typo = Capability("cap.motion.joint_positon.v1", "arm")
        self._late(server, capabilities=arm_capabilities(extra=[typo]))
        hello = rpc("mhs.hello", protocol_versions=["1.0"])
        self.assertEqual([item["device_id"] for item in hello["devices"]], [device.device_id])
        opened = rpc("mhs.session.open", mode="simulated")
        self.assertEqual(rpc("mhs.session.open", mode="simulated")["session_id"][:6], "mhs_s_")
        self.assertNotIn(self.LATE, [item.get("device_id") for item in opened.get("granted") or []])
        receipt = rpc("mhs.command", session_id=opened["session_id"], capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_a_late_strict_device_on_a_compatibility_server(self) -> None:
        server, rpc, device, bridge = arm_server(strict=None)
        late = arm_device(mode="hardware", device_id=self.LATE, strict=True)
        server.devices[late.device_id] = late
        receipt = rpc("mhs.command", session_id=open_session(rpc, late), capability_id=JOINTS,
                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.AUTH.HARDWARE_DISABLED", receipt)

    def test_compatibility_servers_keep_serving_late_devices_as_before(self) -> None:
        server, rpc, device, bridge = arm_server(strict=None)
        late = self._late(server, mode="hardware")
        with RecordWarnings() as warned:
            receipt = rpc("mhs.command", session_id=open_session(rpc, late), capability_id=JOINTS,
                          input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertEqual(strict_warnings(warned), [])


class HardwarePermitTests(unittest.TestCase):
    """hw_mcp.py: 'model self-permit on R2 hardware: False [policy_rule]' then the valve ran."""

    def _permit(self, rpc, session):
        return rpc.raw("mhs.safety.permit", session_id=session, capability_id=TORQUE, input=TORQUE_INPUT,
                       input_digest=action_digest(TORQUE, "arm", TORQUE_INPUT), ttl_s=60)

    def test_strict_mode_fails_closed_without_an_approval_verifier(self) -> None:
        server, rpc, device, bridge = _hardware(risk="R2", torque=True, armed=True)
        session = open_session(rpc, device)
        response = self._permit(rpc, session)
        self.assertEqual(error_code(response), "MHS.SAFETY.APPROVAL_REQUIRED", response)
        receipt = rpc("mhs.command", session_id=session, capability_id=TORQUE, input=TORQUE_INPUT,
                      deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.PERMIT_INVALID")
        self.assertEqual(bridge.count(TORQUE), 0)

    def test_a_verified_human_approval_issues_the_permit(self) -> None:
        requests = []

        def verifier(request):
            requests.append(request)
            return {"verified": True, "approvals": [{"principal": "human:operator", "method": "human_click"}]}

        server, rpc, device, bridge = _hardware(risk="R2", torque=True, armed=True, approval_verifier=verifier)
        session = open_session(rpc, device)
        permit = self._permit(rpc, session)["result"]
        self.assertEqual(permit["approvals"][0]["method"], "human_click")
        self.assertEqual(requests[0]["risk_class"], "R2")
        receipt = rpc("mhs.command", session_id=session, capability_id=TORQUE, input=TORQUE_INPUT,
                      deadline_ms=2000, permit_id=permit["permit_id"])
        self.assertEqual(receipt["status"], "completed", receipt)

    def test_an_unverified_approval_is_refused(self) -> None:
        server, rpc, device, bridge = _hardware(risk="R2", torque=True, armed=True,
                                                approval_verifier=lambda request: {"verified": False})
        response = self._permit(rpc, open_session(rpc, device))
        self.assertEqual(error_code(response), "MHS.SAFETY.APPROVAL_REQUIRED")

    def test_compatibility_mode_still_issues_it_with_a_warning(self) -> None:
        server, rpc, device, bridge = _hardware(strict=None, risk="R2", torque=True)
        session = open_session(rpc, device)
        with RecordWarnings() as warned:
            permit = self._permit(rpc, session)["result"]
        self.assertEqual(permit["approvals"][0]["method"], "policy_rule")
        self.assertTrue(any("approval_verifier" in text for text in strict_warnings(warned)))

    def test_simulated_r2_permits_keep_the_fixture_policy(self) -> None:
        server, rpc, device, bridge = arm_server(arm_device(risk="R2", torque=True), strict=True)
        permit = self._permit(rpc, open_session(rpc, device))["result"]
        self.assertEqual(permit["approvals"][0]["method"], "policy_rule")


class OperatorResetTests(unittest.TestCase):
    """reset_noallow.py: 'model reset with allow_hardware=false: completed'; e6: another principal reset it."""

    def setUp(self) -> None:
        self.server, self.anonymous, self.device, self.bridge = _hardware(
            armed=True, auth_tokens=TOKENS)
        self.operator = TokenRpc(self.server, "operator-token")
        self.model = TokenRpc(self.server, "agent-token")
        self.operator_session = open_session(self.operator, self.device)
        self.model_session = open_session(self.model, self.device)
        receipt = self.operator("mhs.safety.estop", session_id=self.operator_session, reason="operator panic",
                                deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"])

    def tearDown(self) -> None:
        self.operator.raw("mhs.safety.reset", session_id=self.operator_session, deadline_ms=1000)

    def _assert_refused(self, receipt) -> None:
        self.assertEqual(receipt["status"], "rejected", receipt)
        self.assertEqual(error_code(receipt), "MHS.AUTH.FORBIDDEN")
        self.assertEqual(receipt["error"]["details"]["reason"], "operator_required")
        self.assertEqual(self.bridge.count("reset"), 0)
        self.assertTrue(self.server._latched[self.device.device_id])  # noqa: SLF001

    def test_an_agent_cannot_reset_a_hardware_latch(self) -> None:
        self._assert_refused(self.model("mhs.safety.reset", session_id=self.model_session, deadline_ms=1000))
        receipt = self.operator("mhs.command", session_id=self.operator_session, capability_id=JOINTS,
                                input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(error_code(receipt), "MHS.SAFETY.ESTOP_ENGAGED", "nothing resumes")

    def test_a_self_declared_operator_cannot_either(self) -> None:
        session = open_session(self.anonymous, self.device, principal={"id": "operator", "kind": "operator"})
        self._assert_refused(self.anonymous("mhs.safety.reset", session_id=session, deadline_ms=1000))
        human = open_session(self.anonymous, self.device, principal={"id": "operator", "kind": "human"})
        self._assert_refused(self.anonymous("mhs.safety.reset", session_id=human, deadline_ms=1000))

    def test_a_human_token_is_not_an_operator(self) -> None:
        human = TokenRpc(self.server, "human-token")
        self._assert_refused(human("mhs.safety.reset", session_id=open_session(human, self.device),
                                   deadline_ms=1000))

    def test_the_operator_resets(self) -> None:
        receipt = self.operator("mhs.safety.reset", session_id=self.operator_session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertFalse(self.server._latched[self.device.device_id])  # noqa: SLF001
        self.assertEqual(self.bridge.count("reset"), 1)


class CompatibilityResetTests(unittest.TestCase):
    def test_compatibility_mode_lets_any_principal_reset_with_a_warning(self) -> None:
        server, rpc, device, bridge = _hardware(strict=None)
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        with RecordWarnings() as warned:
            receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)
        self.assertTrue(any("reset" in text and "operator" in text for text in strict_warnings(warned)))

    def test_strict_simulated_devices_keep_any_principal_reset(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        session = open_session(rpc, device)
        rpc("mhs.safety.estop", session_id=session, reason="x", deadline_ms=1000)
        receipt = rpc("mhs.safety.reset", session_id=session, deadline_ms=1000)
        self.assertEqual(receipt["status"], "completed", receipt)


if __name__ == "__main__":
    unittest.main()
