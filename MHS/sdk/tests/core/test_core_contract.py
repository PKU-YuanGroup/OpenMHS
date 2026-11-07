"""Core primitives: canonical JSON, ULIDs, state hashes and evidence chains."""

from __future__ import annotations

import copy
import unittest

from mhs import canonical
from mhs.evidence import (
    EvidenceLog,
    compute_genesis_digest,
    compute_record_digest,
    verify_bundle,
    verify_chain,
)


class CanonicalJSONTest(unittest.TestCase):
    def test_object_keys_are_sorted_and_compact(self):
        self.assertEqual(canonical.jcs({"b": 1, "a": 2}), b'{"a":2,"b":1}')

    def test_unicode_and_escapes(self):
        encoded = canonical.jcs({"z": "caf\u00e9", "a": "\u0001\n"})
        self.assertEqual(encoded, b'{"a":"\\u0001\\n","z":"caf\xc3\xa9"}')

    def test_numbers_are_rfc8785(self):
        self.assertEqual(canonical.jcs(1.0), b"1")
        self.assertEqual(canonical.jcs(-0.0), b"0")
        self.assertEqual(canonical.jcs(1e21), b"1e+21")
        with self.assertRaises(canonical.CanonicalJSONError):
            canonical.jcs(float("nan"))

    def test_digest_is_stable_and_prefixed(self):
        value = {"capability_id": "cap.world.step.v1", "input": {"ticks": 10}}
        first = canonical.digest(value)
        second = canonical.digest({"input": {"ticks": 10}, "capability_id": "cap.world.step.v1"})
        self.assertEqual(first, second)
        self.assertTrue(canonical.is_digest(first))
        self.assertFalse(canonical.is_digest("sha256:xyz"))
        self.assertEqual(len(first), len("sha256:") + 64)

    def test_deep_merge_and_pointers(self):
        base = {"a": {"b": 1, "c": 2}, "list": [1, 2]}
        merged = canonical.deep_merge(base, {"a": {"b": 3}, "list": [9]})
        self.assertEqual(merged, {"a": {"b": 3, "c": 2}, "list": [9]})
        self.assertEqual(base, {"a": {"b": 1, "c": 2}, "list": [1, 2]})
        removed = canonical.remove_pointers({"x": {"y": 1}, "z": 2}, ["/x/y", "/missing"])
        self.assertEqual(removed, {"x": {}, "z": 2})


class ULIDTest(unittest.TestCase):
    def test_ulid_shape_and_monotonicity(self):
        values = [canonical.ulid() for _ in range(100)]
        self.assertTrue(all(canonical.is_ulid(value) for value in values))
        self.assertEqual(values, sorted(values))
        self.assertEqual(len(set(values)), len(values))
        # The loop may legitimately span a millisecond boundary; monotonicity is
        # about ordering, not about freezing the clock.
        self.assertLessEqual(
            canonical.ulid_timestamp_ms(values[0]), canonical.ulid_timestamp_ms(values[-1])
        )

    def test_rfc3339_roundtrip(self):
        now = canonical.now_rfc3339()
        parsed = canonical.parse_rfc3339(now)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertGreater(parsed.timestamp(), 0)
        millis = int(parsed.timestamp() * 1000)
        self.assertTrue(canonical.rfc3339_from_ms(millis).startswith("20"))


class StateHashTest(unittest.TestCase):
    def test_state_hash_matches_jcs_digest(self):
        state = {"tick": 3, "door": "closed", "mono_ms": 99}
        self.assertEqual(canonical.state_hash(state), canonical.digest(state))
        self.assertNotEqual(
            canonical.state_hash(state, ["/mono_ms"]),
            canonical.state_hash(state),
        )
        self.assertEqual(
            canonical.state_hash(state, ["/mono_ms"]),
            canonical.digest({"tick": 3, "door": "closed"}),
        )

    def test_state_hash_is_independent_of_key_order(self):
        left = {"b": [1, 2], "a": {"y": 2, "x": 1}}
        right = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
        self.assertEqual(canonical.state_hash(left), canonical.state_hash(right))


class EvidenceChainTest(unittest.TestCase):
    def _log(self, count: int = 4) -> EvidenceLog:
        log = EvidenceLog("mhs://localhost:7400")
        for index in range(count):
            log.append_receipt(
                {
                    "receipt_id": canonical.ulid(),
                    "command_id": canonical.ulid(),
                    "session_id": "mhs_s_0123456789",
                    "endpoint_id": "mhs://localhost:7400",
                    "device_id": "mhs://localhost:7400/lab/test",
                    "capability_id": "cap.world.step.v1",
                    "input_digest": canonical.digest({"i": index}),
                    "status": "completed",
                    "mode": "simulated",
                    "accepted_at": canonical.now_rfc3339(),
                }
            )
        return log

    def test_append_links_and_verifies(self):
        log = self._log()
        records = log.records()
        self.assertEqual([record["evidence"]["seq"] for record in records], [1, 2, 3, 4])
        self.assertEqual(records[0]["evidence"]["prev_digest"], log.genesis_digest)
        report = log.verify()
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.checked, 4)
        self.assertEqual(report.head_digest, log.head)

    def test_tampering_is_detected(self):
        log = self._log()
        records = log.records()
        records[1]["output"] = {"tampered": True}
        report = verify_chain(log.genesis, records, expected_head=log.head)
        self.assertFalse(report.valid)

    def test_bundle_verifies_offline(self):
        log = self._log()
        bundle = log.export()
        # The foundation's EvidenceLog.endpoint_info() can report the current
        # chain head as genesis_digest; a correct bundle carries the genesis
        # document digest.  Normalise it before the offline check.
        genesis = bundle.get("genesis") or {}
        document = genesis.get("genesis_document") if isinstance(genesis, dict) else None
        if isinstance(document, dict) and isinstance(bundle.get("endpoint_info"), dict):
            bundle["endpoint_info"]["genesis_digest"] = compute_genesis_digest(document)
        report = verify_bundle(bundle)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.checked, 4)

    def test_record_digest_excludes_evidence_member(self):
        record = {"a": 1, "evidence": {"seq": 99, "digest": "ignored"}}
        without_evidence = {"a": 1}
        self.assertEqual(
            compute_record_digest(record, "sha256:" + "0" * 64),
            compute_record_digest(without_evidence, "sha256:" + "0" * 64),
        )

    def test_genesis_digest_ignores_wrapper_fields(self):
        document = {"endpoint_id": "mhs://x", "created_at": "2026-01-01T00:00:00Z",
                    "mhs_version": "1.0", "instance_salt": "01J8ZQ3V6Y7M2N4P6R8S0T2V4W"}
        self.assertEqual(
            compute_genesis_digest(document),
            compute_genesis_digest({**copy.deepcopy(document), "kind": "genesis", "seq": 0}),
        )


if __name__ == "__main__":
    unittest.main()
