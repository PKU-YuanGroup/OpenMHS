"""SURF-02 / SURF-04: sessions belong to the projection.

Ports of ``integration-surfaces/session_hijack.py`` (a session id the model
learnt from the evidence is refused) and ``ttl_test.py`` (the projection keeps
working after its sessions outlive their TTL), plus the lazy heartbeat and the
agent principal.
"""

from __future__ import annotations

import unittest
import warnings

from mhs.mcp import SESSION_TTL_S

from tests.surfaces import _support as s


class SessionOwnershipTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.server = s.reference("conveyor")
        self.addCleanup(self.spec.close)
        self.operator = s.client(self.server)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # compat mode warns about the unauthenticated human claim
            self.op_session = self.operator.open_session(
                [s.CONVEYOR], mode="simulated", principal={"id": "human:alice", "kind": "human"})["session_id"]
        self.operator.invoke("cap.world.step.v1", {"ticks": 1}, device_id=s.CONVEYOR)

    def _receipts_of(self, session_id: str) -> int:
        bundle = self.operator.export_evidence()
        return sum(1 for item in bundle["receipts"] if item.get("session_id") == session_id)

    def test_session_hijack_a_foreign_session_id_is_refused(self) -> None:
        mcp = s.Mcp(self.server)
        evidence = mcp.call("mhs__evidence", {})
        self.assertIn(self.op_session, str(evidence))  # the model can learn it ...
        before = self._receipts_of(self.op_session)
        tick = s.tick(self.spec)
        mark = mcp.mark()
        result = mcp.call(mcp.tool("__world_step"), {"ticks": 1, "session_id": self.op_session})
        self.assertTrue(result["isError"], result)  # ... but cannot use it
        self.assertEqual(s.mhs_error(result)["mhs_code"], "MHS.SESSION.UNKNOWN")
        self.assertIsNone(result["structuredContent"]["receipt"])
        self.assertNotIn("mhs.command", mcp.sent_since(mark))
        self.assertEqual(self._receipts_of(self.op_session), before)
        self.assertEqual(s.tick(self.spec), tick)
        forged = mcp.call(mcp.tool("__world_step"), {"ticks": 1, "session_id": "sess_forged"})
        self.assertEqual(s.mhs_error(forged)["mhs_code"], "MHS.SESSION.UNKNOWN")

    def test_projection_sessions_are_agent_sessions_and_its_own_ids_are_accepted(self) -> None:
        mcp = s.Mcp(self.server, client_name="Claude Code")
        step = mcp.tool("__world_step")
        first = s.receipt(mcp.call(step, {"ticks": 1}))
        self.assertEqual(first["status"], "completed")
        self.assertEqual(first["principal"], {"id": "agent:mcp/Claude-Code", "kind": "agent"})
        again = mcp.call(step, {"ticks": 1, "session_id": first["session_id"]})
        self.assertFalse(again["isError"], again)
        self.assertEqual(s.receipt(again)["session_id"], first["session_id"])

    def test_allow_external_sessions_passes_a_foreign_session_through(self) -> None:
        mcp = s.Mcp(self.server, policy=s.policy(allow_external_sessions=True))
        result = mcp.call(mcp.tool("__world_step"), {"ticks": 1, "session_id": self.op_session})
        self.assertFalse(result["isError"], result)
        self.assertEqual(s.receipt(result)["session_id"], self.op_session)


class SessionLifetimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.spec, self.server = s.reference("conveyor")
        self.addCleanup(self.spec.close)
        self.mcp = s.Mcp(self.server)
        self.addCleanup(self.mcp.close)
        self.step = self.mcp.tool("__world_step")

    def test_ttl_tools_keep_working_after_the_session_expires(self) -> None:
        first = self.mcp.call(self.step, {"ticks": 1})
        self.assertEqual(s.receipt(first)["status"], "completed")
        old_session = s.receipt(first)["session_id"]
        tick = s.tick(self.spec)
        s.age_sessions(self.server)  # 61 minutes later

        lapsed = self.mcp.call(self.step, {"ticks": 1})
        self.assertTrue(lapsed["isError"], lapsed)
        error = s.mhs_error(lapsed)
        self.assertIn(error["mhs_code"], ("MHS.SESSION.EXPIRED", "MHS.SESSION.UNKNOWN"))
        self.assertTrue(error["session_renewed"])
        self.assertIn("NOT executed", lapsed["content"][0]["text"])
        self.assertIn("re-read", lapsed["content"][0]["text"])
        self.assertEqual(s.tick(self.spec), tick)  # never retried automatically

        retried = self.mcp.call(self.step, {"ticks": 1})
        self.assertFalse(retried["isError"], retried)
        self.assertEqual(s.receipt(retried)["status"], "completed")
        self.assertNotEqual(s.receipt(retried)["session_id"], old_session)
        self.assertEqual(s.tick(self.spec), tick + 1)

    def test_reads_reopen_a_lapsed_session_transparently(self) -> None:
        self.mcp.call("mhs__read", {"device_id": s.CONVEYOR, "resource_id": "workcell"})
        s.age_sessions(self.server)
        read = self.mcp.call("mhs__read", {"resource_id": "workcell"})
        self.assertFalse(read["isError"], read)
        self.assertIn("revision", read["structuredContent"]["read"])

    def test_lazy_heartbeat_when_a_third_of_the_ttl_is_left(self) -> None:
        self.mcp.call(self.step, {"ticks": 1})
        owned = list(self.mcp.projection._sessions.values())
        self.assertEqual([entry.ttl_s for entry in owned], [SESSION_TTL_S])
        session = self.server._sessions[owned[0].session_id]
        expires = session.expires_at
        mark = self.mcp.mark()
        self.mcp.call(self.step, {"ticks": 1})
        self.assertNotIn("mhs.session.heartbeat", self.mcp.sent_since(mark))  # plenty of TTL left
        owned[0].renew_at = 0.0  # less than a third left
        mark = self.mcp.mark()
        self.assertEqual(s.receipt(self.mcp.call(self.step, {"ticks": 1}))["status"], "completed")
        sent = self.mcp.sent_since(mark)
        self.assertLess(sent.index("mhs.session.heartbeat"), sent.index("mhs.command"))
        self.assertGreater(session.expires_at, expires)

    def test_heartbeat_finding_an_expired_session_sends_no_command(self) -> None:
        self.mcp.call(self.step, {"ticks": 1})
        tick = s.tick(self.spec)
        s.age_sessions(self.server)
        for entry in self.mcp.projection._sessions.values():
            entry.renew_at = 0.0
        mark = self.mcp.mark()
        lapsed = self.mcp.call(self.step, {"ticks": 1})
        self.assertTrue(lapsed["isError"])
        self.assertTrue(s.mhs_error(lapsed)["session_renewed"])
        self.assertNotIn("mhs.command", self.mcp.sent_since(mark))
        self.assertEqual(s.tick(self.spec), tick)

    def test_close_releases_every_owned_session(self) -> None:
        self.mcp.call(self.step, {"ticks": 1})
        self.mcp.call("mhs__read", {"resource_id": "workcell"})
        owned = [entry.session_id for entry in self.mcp.projection._sessions.values()]
        self.assertEqual(len(owned), 2)
        self.mcp.close()
        for session_id in owned:
            self.assertNotIn(session_id, self.server._sessions)


if __name__ == "__main__":
    unittest.main()
