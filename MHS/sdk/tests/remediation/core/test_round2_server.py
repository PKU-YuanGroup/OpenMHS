"""Lead's round-2 server regressions: permit/budget atomicity, restore postcondition, deadline follow-up."""

from __future__ import annotations

import inspect
import sys
import threading
import time
import unittest
from pathlib import Path

from mhs import canonical
from mhs.reference import build_endpoint, build_server
from mhs.server import MHSServer

HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE / "core"))
import _device_server  # noqa: E402


def _rpc(server, method, **params):
    raw = server.handle({"jsonrpc": "2.0", "id": canonical.ulid(), "method": method, "params": params})
    return raw.to_dict() if hasattr(raw, "to_dict") else raw


def _result(raw):
    assert "result" in raw, raw
    return raw["result"]


def _code(raw):
    err = raw.get("error") or (raw.get("result", {}) or {}).get("error") or {}
    return err.get("mhs_code") or (err.get("data") or {}).get("mhs_code")


def _line_of(fragment: str, within=None) -> int:
    """The line of ``fragment`` in server.py (only inside the function ``within`` when given)."""
    source = Path(inspect.getsourcefile(MHSServer)).read_text().splitlines()
    first, last = 1, len(source)
    if within is not None:
        lines, first = inspect.getsourcelines(within)
        last = first + len(lines) - 1
    hits = [index for index, line in enumerate(source, 1)
            if first <= index <= last and line.strip() == fragment.strip()]
    assert len(hits) == 1, (fragment, hits)
    return hits[0]


class _Server:
    def __init__(self):
        self.server = _device_server.build_server()
        self.device = next(iter(self.server.devices.values()))
        self.device.safety.envelope["cap.world.step.v1"] = {
            "ticks": {"min": 0, "max": 10, "per": "rolling_24h", "unit": "1"}
        }
        rpc_hello = _rpc(self.server, "mhs.hello", protocol_versions=["1.0"])
        assert "result" in rpc_hello
        self.session = _result(_rpc(
            self.server, "mhs.session.open",
            device_ids=[self.device.device_id], mode="simulated",
            principal={"id": "agent:lead", "kind": "agent"}, ttl_s=60,
        ))["session_id"]

    def command(self, cap, payload, permit=None, command_id=None):
        # The rendezvous of the atomicity tests can hold one request in its
        # pre-checks for the barrier timeout (5 s).  Since WP-04 4e the
        # deadline counts from the request (PROTO-011), so it must cover that.
        return _rpc(
            self.server, "mhs.command", session_id=self.session,
            device_id=self.device.device_id, capability_id=cap, input=payload,
            command_id=command_id or canonical.ulid(), deadline_ms=10000,
            **({"permit_id": permit} if permit else {}),
        )

    def permit(self):
        return _result(_rpc(
            self.server, "mhs.safety.permit", session_id=self.session,
            device_id=self.device.device_id, capability_id="cap.actuation.valve.v1",
            resource="world", ttl_s=60,
            input_digest=canonical.digest(
                {"capability_id": "cap.actuation.valve.v1", "resource": "world",
                 "input": {"gate": "divert"}}
            ),
        ))["permit_id"]


class AtomicityTests(unittest.TestCase):
    def test_single_permit_cannot_be_used_twice_concurrently(self):
        fixture = _Server()
        fixture.device._by_capability["cap.actuation.valve.v1"].exclusive = False
        permit = fixture.permit()
        barrier = threading.Barrier(2)
        outputs: dict[str, dict] = {}
        rendezvous = _line_of("with self._permit_lock:", within=MHSServer._consume_permit)
        source = inspect.getsourcefile(MHSServer)

        def run(tag):
            def trace(frame, event, arg):
                if event == "line" and frame.f_code.co_filename == source and frame.f_lineno == rendezvous:
                    try:
                        barrier.wait(timeout=5)
                    except threading.BrokenBarrierError:
                        pass
                return trace
            sys.settrace(trace)
            try:
                outputs[tag] = fixture.command(
                    "cap.actuation.valve.v1", {"gate": "divert"}, permit=permit
                )
            finally:
                sys.settrace(None)

        threads = [threading.Thread(target=run, args=(tag,)) for tag in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        statuses = sorted(_result(raw)["status"] for raw in outputs.values())
        self.assertEqual(statuses, ["completed", "rejected"])
        rejected = next(_result(raw) for raw in outputs.values() if _result(raw)["status"] == "rejected")
        self.assertEqual(rejected["error"]["mhs_code"], "MHS.SAFETY.PERMIT_INVALID")
        self.assertEqual(fixture.device.bridge.state["gate"], "divert")
        self.assertEqual(fixture.server._revisions[fixture.device.device_id], 1)

    def test_cumulative_budget_is_atomic_across_concurrent_requests(self):
        fixture = _Server()
        barrier = threading.Barrier(2)
        outputs: dict[str, dict] = {}
        rendezvous = _line_of("for rule, requested in draws:")
        source = inspect.getsourcefile(MHSServer)

        def run(tag):
            def trace(frame, event, arg):
                if event == "line" and frame.f_code.co_filename == source and frame.f_lineno == rendezvous:
                    try:
                        barrier.wait(timeout=5)
                    except threading.BrokenBarrierError:
                        pass
                return trace
            sys.settrace(trace)
            try:
                outputs[tag] = fixture.command("cap.world.step.v1", {"ticks": 6})
            finally:
                sys.settrace(None)

        threads = [threading.Thread(target=run, args=(tag,)) for tag in ("a", "b")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        statuses = sorted(_result(raw)["status"] for raw in outputs.values())
        self.assertEqual(statuses, ["completed", "rejected"])
        rejected = next(_result(raw) for raw in outputs.values() if _result(raw)["status"] == "rejected")
        self.assertEqual(rejected["error"]["mhs_code"], "MHS.SAFETY.CUMULATIVE_LIMIT")
        self.assertEqual(fixture.device.bridge.state["tick"], 6)
        usage = sum(
            item["amount"]
            for items in fixture.server._cumulative_usage.values()
            for item in items
        )
        self.assertEqual(usage, 6)


class RestorePostconditionTests(unittest.TestCase):
    def test_unrestorable_snapshot_is_never_reported_completed(self):
        import copy

        spec = build_endpoint("arm", endpoint_id="mhs://lead-restore.local:7400", noise=True)
        server = build_server(spec, log_ready=False)
        try:
            _result(_rpc(server, "mhs.hello", protocol_versions=["1.0"]))
            device_id = spec.devices[0]["device_id"]
            session = _result(_rpc(
                server, "mhs.session.open", device_ids=[device_id], mode="simulated", ttl_s=60
            ))["session_id"]
            snapshot = _result(_rpc(server, "mhs.snapshot", session_id=session,
                                    device_id=device_id, deadline_ms=2000))
            candidate = copy.deepcopy(snapshot)
            candidate["snapshot"]["arm"]["noise_enabled"] = False
            candidate["state_hash"] = canonical.state_hash(candidate["snapshot"]["arm"], [])
            candidate["snapshot_digest"] = canonical.digest(candidate["snapshot"])
            receipt = _result(_rpc(
                server, "mhs.restore", session_id=session, device_id=device_id,
                snapshot=candidate, command_id=canonical.ulid(), deadline_ms=2000,
            ))
            self.assertNotEqual(receipt["status"], "completed")
            self.assertIn(receipt["status"], ("failed", "unknown", "rejected"))
            if receipt.get("state_hash_after"):
                self.assertNotEqual(receipt["state_hash_after"], candidate["state_hash"])
        finally:
            spec.close()

    def test_exact_and_seeded_roundtrips_still_pass(self):
        for noise in (False, True):
            spec = build_endpoint("arm", endpoint_id="mhs://lead-roundtrip.local:7400", noise=noise)
            server = build_server(spec, log_ready=False)
            try:
                _result(_rpc(server, "mhs.hello", protocol_versions=["1.0"]))
                device_id = spec.devices[0]["device_id"]
                session = _result(_rpc(
                    server, "mhs.session.open", device_ids=[device_id], mode="simulated", ttl_s=60
                ))["session_id"]
                snapshot = _result(_rpc(server, "mhs.snapshot", session_id=session,
                                        device_id=device_id, deadline_ms=2000))
                receipt = _result(_rpc(
                    server, "mhs.restore", session_id=session, device_id=device_id,
                    snapshot=snapshot, command_id=canonical.ulid(), deadline_ms=2000,
                ))
                self.assertEqual(receipt["status"], "completed", receipt.get("error"))
                self.assertEqual(receipt["state_hash_after"], snapshot["state_hash"])
            finally:
                spec.close()


class DeadlineFollowUpTests(unittest.TestCase):
    def test_estop_timeout_still_reaches_the_endpoint(self):
        server = _device_server.build_server()
        device = next(iter(server.devices.values()))
        original = device.bridge.estop
        device.bridge.estop = lambda reason: (time.sleep(0.12), original(reason))[1]
        _result(_rpc(server, "mhs.hello", protocol_versions=["1.0"]))
        session = _result(_rpc(
            server, "mhs.session.open", device_ids=[device.device_id], mode="simulated", ttl_s=60
        ))["session_id"]
        started = time.monotonic()
        response = _rpc(server, "mhs.safety.estop", session_id=session,
                        device_id=device.device_id, command_id=canonical.ulid(), deadline_ms=10)
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 0.08)
        # WP-04 4a1 (SAFE-040): the latch is engaged before the slow native stop,
        # and an unconfirmed e-stop is a failed receipt, never a bare timeout.
        self.assertTrue(server._latched[device.device_id])
        receipt = _result(response)
        self.assertEqual(receipt["status"], "failed", receipt)
        self.assertEqual(receipt["error"]["mhs_code"], "MHS.SAFETY.SAFE_STATE_UNREACHED")
        deadline = time.monotonic() + 3.0
        while not server._estop_state[device.device_id]["confirmed"] and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(server._latched[device.device_id])
        self.assertTrue(server._estop_state[device.device_id]["confirmed"],
                        "the late native stop was not recorded as a confirmation")


if __name__ == "__main__":
    unittest.main()
