"""Principals bound to bearer tokens (plan 3.6 step 1, WP-04 step 4b).

Ports: sdk-core ``e5.py`` / ``e6.py`` (a caller claimed ``human:alice`` and
another principal's session reset a latch, SDK-04) and the endpoint part of
verify-integration-surfaces ``session_hijack.py`` (a leaked operator session id
let the model act as the operator, SURF-02).
"""

from __future__ import annotations

import http.client
import json
import unittest
from unittest import mock

from mhs.errors import MHSError
from mhs.schema import SchemaStore
from mhs.server import _StdioDispatcher

from ._strict_support import JOINTS, TOKENS, RecordWarnings, TokenRpc, arm_device, arm_server, strict_warnings
from ._support import error_code, open_session

STORE = SchemaStore()


def _command(rpc, session, **extra):
    return rpc.raw("mhs.command", session_id=session, capability_id=JOINTS,
                   input={"joint_positions": [0.1]}, deadline_ms=2000, **extra)


class TokenPrincipalTests(unittest.TestCase):
    def test_the_token_principal_wins_over_a_claimed_one(self) -> None:
        for strict in (True, None):
            with self.subTest(strict=strict):
                server, rpc, device, bridge = arm_server(strict=strict, auth_tokens=TOKENS,
                                                         auth_token="agent-token")
                session = open_session(rpc, device, principal={"id": "human:eve", "kind": "human"})
                receipt = _command(rpc, session)["result"]
                self.assertEqual(receipt["principal"]["id"], "agent:model")
                self.assertEqual(receipt["principal"]["kind"], "agent")
                self.assertEqual(receipt["principal"]["x-meta"]["claimed_principal"],
                                 {"id": "human:eve", "kind": "human"})
                self.assertTrue(receipt["principal"]["x-meta"]["authenticated"])
                self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_an_operator_token_is_a_human_operator_on_the_wire(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, auth_tokens=TOKENS, auth_token="operator-token")
        session = open_session(rpc, device)
        receipt = _command(rpc, session)["result"]
        self.assertEqual(receipt["principal"]["kind"], "human")
        self.assertEqual(receipt["principal"]["x-meta"]["role"], "operator")
        self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])
        self.assertEqual(server._sessions[session].kind, "operator")  # noqa: SLF001

    def test_an_unknown_token_is_unauthenticated(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, auth_tokens=TOKENS)
        response = TokenRpc(server, "not-a-token").raw("mhs.session.open", mode="simulated")
        self.assertEqual(error_code(response), "MHS.AUTH.UNAUTHENTICATED")

    def test_tokens_are_compared_in_constant_time(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, auth_tokens=TOKENS)
        import hmac as _hmac

        with mock.patch("mhs.server.hmac.compare_digest", wraps=_hmac.compare_digest) as compare:
            principal = server._principal_for_token("agent-token")  # noqa: SLF001
        self.assertEqual(principal["id"], "agent:model")
        self.assertEqual(compare.call_count, len(TOKENS), "every token is compared, no early exit")


class ClaimedPrincipalTests(unittest.TestCase):
    """sdk-core e5: 'session.open ... claiming principal human:alice -> True'."""

    def test_strict_mode_treats_a_self_declared_human_as_an_agent(self) -> None:
        for kind in ("human", "operator"):
            with self.subTest(kind=kind):
                server, rpc, device, bridge = arm_server(strict=True)
                session = open_session(rpc, device, principal={"id": "human:alice", "kind": kind})
                receipt = _command(rpc, session)["result"]
                self.assertEqual(receipt["principal"]["kind"], "agent")
                self.assertEqual(receipt["principal"]["id"], "human:alice")
                self.assertEqual(receipt["principal"]["x-meta"]["claimed_principal"],
                                 {"id": "human:alice", "kind": kind})
                self.assertFalse(receipt["principal"]["x-meta"]["authenticated"])
                self.assertEqual(server._sessions[session].kind, "agent")  # noqa: SLF001
                self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_compatibility_mode_trusts_it_with_a_warning(self) -> None:
        server, rpc, device, bridge = arm_server(strict=None)
        with RecordWarnings() as warned:
            session = open_session(rpc, device, principal={"id": "human:alice", "kind": "human"})
        receipt = _command(rpc, session)["result"]
        self.assertEqual(receipt["principal"], {"id": "human:alice", "kind": "human"})
        self.assertTrue(any("claimed_principal" in text for text in strict_warnings(warned)))

    def test_agents_and_services_are_kept(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        for principal in ({"id": "agent:x", "kind": "agent"}, {"id": "svc", "kind": "service"}):
            session = open_session(rpc, device, principal=principal)
            self.assertEqual(_command(rpc, session)["result"]["principal"], principal)


FORGED_META = {"authenticated": True, "role": "operator",
               "claimed_principal": {"id": "operator:ada", "kind": "operator"}, "note": "kept"}


class ForgedMetaTests(unittest.TestCase):
    """Verifier probe p1 (4b): an unauthenticated caller forged ``x-meta.authenticated`` / ``role``.

    ``session.open`` with ``{"id": "agent:x", "kind": "agent", "x-meta":
    {"authenticated": true, "role": "operator"}}`` and no token produced
    receipts indistinguishable from a token principal's.  The endpoint owns
    ``authenticated``, ``role`` and ``claimed_principal``: the caller's are
    dropped and ``authenticated`` states the endpoint's truth.
    """

    def test_an_agent_or_service_claim_cannot_forge_endpoint_meta(self) -> None:
        for strict in (True, None):
            for kind in ("agent", "service"):
                with self.subTest(strict=strict, kind=kind):
                    server, rpc, device, bridge = arm_server(strict=strict, auth_tokens=TOKENS)
                    session = open_session(rpc, device, principal={"id": f"{kind}:x", "kind": kind,
                                                                   "x-meta": dict(FORGED_META)})
                    receipt = _command(rpc, session)["result"]
                    principal = receipt["principal"]
                    self.assertEqual(principal["kind"], kind)
                    self.assertEqual(principal["x-meta"], {"authenticated": False, "note": "kept"}, principal)
                    self.assertFalse(server._sessions[session].authenticated)  # noqa: SLF001
                    self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_a_human_or_operator_claim_cannot_forge_it_either(self) -> None:
        for strict in (True, None):
            for kind in ("human", "operator"):
                with self.subTest(strict=strict, kind=kind), RecordWarnings():
                    server, rpc, device, bridge = arm_server(strict=strict, auth_tokens=TOKENS)
                    session = open_session(rpc, device, principal={"id": "human:eve", "kind": kind,
                                                                   "x-meta": dict(FORGED_META)})
                    receipt = _command(rpc, session)["result"]
                    principal = receipt["principal"]
                    meta = principal["x-meta"]
                    self.assertIs(meta["authenticated"], False, principal)
                    self.assertFalse(server._sessions[session].authenticated)  # noqa: SLF001
                    self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])
                    if strict:
                        self.assertEqual(principal["kind"], "agent")
                        self.assertEqual(meta["claimed_principal"], {"id": "human:eve", "kind": kind})
                        self.assertNotIn("role", meta)
                        continue
                    self.assertEqual(principal["kind"], "human")
                    self.assertNotIn("claimed_principal", meta)
                    # Compatibility mode trusts the declared kind (warned): an
                    # operator's role comes from that kind, never from the
                    # caller's x-meta, and the receipt says it is unauthenticated.
                    if kind == "operator":
                        self.assertEqual(meta["role"], "operator")
                    else:
                        self.assertNotIn("role", meta)

    def test_strict_mode_keeps_only_principal_members(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True)
        session = open_session(rpc, device, principal={"id": "agent:x", "kind": "agent", "display_name": "X",
                                                       "authenticated": True, "role": "operator"})
        receipt = _command(rpc, session)["result"]
        self.assertEqual(receipt["principal"], {"id": "agent:x", "kind": "agent", "display_name": "X"})
        self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_compatibility_mode_drops_top_level_lookalikes(self) -> None:
        """WP-04 4b verifier minor (probe v2 'top-level-authenticated'): compatibility
        mode kept top-level ``authenticated`` / ``role`` members on receipts, which
        were then schema-invalid and looked like endpoint-owned identity."""
        server, rpc, device, bridge = arm_server(strict=None)
        session = open_session(rpc, device, principal={"id": "agent:x", "kind": "agent", "display_name": "X",
                                                       "authenticated": True, "role": "operator",
                                                       "claimed_principal": {"id": "human:alice"}})
        receipt = _command(rpc, session)["result"]
        for name in ("authenticated", "role", "claimed_principal"):
            self.assertNotIn(name, receipt["principal"])
        self.assertEqual(receipt["principal"]["display_name"], "X")
        self.assertEqual(STORE.validate(receipt, "receipt.schema.json"), [])

    def test_token_principals_still_say_authenticated(self) -> None:
        server, rpc, device, bridge = arm_server(strict=True, auth_tokens=TOKENS, auth_token="agent-token")
        session = open_session(rpc, device, principal={"id": "agent:model", "kind": "agent",
                                                       "x-meta": {"authenticated": False}})
        meta = _command(rpc, session)["result"]["principal"]["x-meta"]
        self.assertIs(meta["authenticated"], True)
        self.assertTrue(server._sessions[session].authenticated)  # noqa: SLF001

    def test_plain_unauthenticated_principals_are_unchanged(self) -> None:
        for strict in (True, None):
            with self.subTest(strict=strict):
                server, rpc, device, bridge = arm_server(strict=strict)
                session = open_session(rpc, device, principal={"id": "agent:x", "kind": "agent"})
                self.assertEqual(_command(rpc, session)["result"]["principal"], {"id": "agent:x", "kind": "agent"})


class OperationOwnerTests(unittest.TestCase):
    """Verifier probe p1 P2: a self-declared id equal to a token principal's saw its operations."""

    def setUp(self) -> None:
        self.server, self.anonymous, self.device, self.bridge = arm_server(strict=True, auth_tokens=TOKENS)
        self.operator = TokenRpc(self.server, "operator-token")
        session = open_session(self.operator, self.device)
        self.operation_id = _command(self.operator, session)["result"]["operation_id"]

    def test_an_unauthenticated_claim_of_the_owners_id_sees_nothing(self) -> None:
        for kind in ("agent", "operator", "human"):
            with self.subTest(kind=kind):
                spoof = open_session(self.anonymous, self.device, principal={"id": "operator:ada", "kind": kind})
                for method in ("mhs.operations.get", "mhs.operations.cancel"):
                    response = self.anonymous.raw(method, session_id=spoof, operation_id=self.operation_id,
                                                  deadline_ms=1000)
                    self.assertEqual(error_code(response), "MHS.OPERATION.UNKNOWN", response)

    def test_another_session_of_the_same_token_principal_sees_it(self) -> None:
        other = open_session(self.operator, self.device)
        response = self.operator.raw("mhs.operations.get", session_id=other, operation_id=self.operation_id,
                                     deadline_ms=1000)
        self.assertEqual(response["result"]["operation_id"], self.operation_id, response)

    def test_a_token_principal_does_not_see_an_unauthenticated_namesakes_operation(self) -> None:
        claim = open_session(self.anonymous, self.device, principal={"id": "agent:model", "kind": "agent"})
        operation_id = _command(self.anonymous, claim)["result"]["operation_id"]
        model = TokenRpc(self.server, "agent-token")
        response = model.raw("mhs.operations.get", session_id=open_session(model, self.device),
                             operation_id=operation_id, deadline_ms=1000)
        self.assertEqual(error_code(response), "MHS.OPERATION.UNKNOWN", response)


class SessionOwnershipTests(unittest.TestCase):
    """session_hijack.py: 'model call under operator session: completed {human:alice}'."""

    def setUp(self) -> None:
        self.server, self.operator, self.device, self.bridge = arm_server(
            strict=None, auth_tokens=TOKENS, auth_token="operator-token")
        self.session = open_session(self.operator, self.device)

    def test_a_token_bound_session_refuses_other_callers(self) -> None:
        for token in (None, "agent-token", "human-token"):
            with self.subTest(token=token):
                response = _command(TokenRpc(self.server, token), self.session)
                self.assertEqual(error_code(response), "MHS.SESSION.UNKNOWN", response)
        self.assertEqual(self.bridge.count(JOINTS), 0)
        self.assertEqual(_command(self.operator, self.session)["result"]["status"], "completed")

    def test_an_estop_naming_it_still_latches_attributed_to_the_caller(self) -> None:
        model = TokenRpc(self.server, "agent-token")
        receipt = model("mhs.safety.estop", session_id=self.session, reason="model stop", deadline_ms=1000)
        self.assertTrue(receipt["output"]["latched"])
        self.assertEqual(receipt["principal"]["id"], "agent:model")
        self.assertNotEqual(receipt["session_id"], self.session)
        self.assertTrue(self.server._latched[self.device.device_id])  # noqa: SLF001
        self.operator("mhs.safety.reset", session_id=self.session, deadline_ms=1000)

    def test_stdio_pipe_principal(self) -> None:
        principal = self.server._principal_for_token("agent-token")  # noqa: SLF001
        sent = []
        dispatcher = _StdioDispatcher(self.server, sent.append, auth=principal)
        dispatcher.submit({"jsonrpc": "2.0", "id": 1, "method": "mhs.session.open",
                           "params": {"mode": "simulated", "principal": {"id": "human:x", "kind": "human"}}})
        dispatcher.close(timeout=5)
        session_id = sent[0]["result"]["session_id"] if isinstance(sent[0], dict) else sent[0].to_dict()["result"]["session_id"]
        self.assertEqual(self.server._sessions[session_id].principal["id"], "agent:model")  # noqa: SLF001
        self.assertTrue(self.server._sessions[session_id].authenticated)  # noqa: SLF001
        with self.assertRaises(MHSError) as caught:
            self.server.run_stdio(auth_token="not-a-token")
        self.assertEqual(caught.exception.code, "MHS.AUTH.UNAUTHENTICATED")


class HttpPrincipalTests(unittest.TestCase):
    """SDK-04: the HTTP bearer token now decides the principal, not params.principal."""

    def setUp(self) -> None:
        self.server, _, self.device, self.bridge = arm_server(strict=True, auth_tokens=TOKENS)
        self.handle = self.server.start_http("127.0.0.1", 0)
        self.addCleanup(self.handle.shutdown)

    def _post(self, token, method, **params):
        connection = http.client.HTTPConnection("127.0.0.1", self.handle.port, timeout=5)
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        connection.request("POST", "/mhs/v1/rpc", body=body, headers={
            "Content-Type": "application/json", "Authorization": f"Bearer {token}"})
        response = connection.getresponse()
        payload = json.loads(response.read() or b"null")
        connection.close()
        return response.status, payload

    def test_bearer_principal_and_session_ownership(self) -> None:
        status, opened = self._post("agent-token", "mhs.session.open", mode="simulated",
                                    principal={"id": "human:alice", "kind": "human"})
        self.assertEqual(status, 200, opened)
        session = opened["result"]["session_id"]
        status, response = self._post("agent-token", "mhs.command", session_id=session, capability_id=JOINTS,
                                      input={"joint_positions": [0.1]}, deadline_ms=2000)
        self.assertEqual(response["result"]["principal"]["id"], "agent:model")
        self.assertEqual(response["result"]["principal"]["x-meta"]["claimed_principal"]["id"], "human:alice")
        status, response = self._post("operator-token", "mhs.command", session_id=session, capability_id=JOINTS,
                                      input={"joint_positions": [0.2]}, deadline_ms=2000)
        self.assertEqual(response["error"]["data"]["mhs_code"], "MHS.SESSION.UNKNOWN", response)

    def test_sse_streams_only_to_the_sessions_principal(self) -> None:
        status, opened = self._post("agent-token", "mhs.session.open", mode="simulated")
        session = opened["result"]["session_id"]
        for token, expected in (("operator-token", 403), ("agent-token", 200)):
            with self.subTest(token=token):
                connection = http.client.HTTPConnection("127.0.0.1", self.handle.port, timeout=5)
                connection.request("GET", f"/mhs/v1/events?session_id={session}",
                                   headers={"Authorization": f"Bearer {token}"})
                response = connection.getresponse()
                self.assertEqual(response.status, expected)
                connection.close()


if __name__ == "__main__":
    unittest.main()
