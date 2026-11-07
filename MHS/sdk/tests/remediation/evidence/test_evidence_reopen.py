"""CODE-001 regression: a persisted evidence log must reopen and stay appendable.

The pre-fix ``EvidenceLog._load`` passed the genesis digest as ``expected_head``,
so every nonempty strict reopen failed with ``CHAIN_BROKEN`` and appends were
refused.  These tests also recompute the chain with the independent encoder in
``_independent`` rather than trusting the library's own digest routine.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mhs import canonical
from mhs.evidence import (
    EvidenceError,
    EvidenceLog,
    compute_genesis_digest,
    verify_bundle,
)

from ._independent import independent_genesis_digest, recompute_chain


def make_receipt(index: int) -> dict[str, object]:
    return {
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
        "output": {"ticks": index},
    }


class EvidenceReopenTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-code001-")
        self.path = Path(self._tmp.name) / "evidence.jsonl"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_append_close_strict_reopen_then_append(self) -> None:
        log = EvidenceLog("mhs://localhost:7400", path=self.path, fsync=True)
        first = log.append_receipt(make_receipt(1))
        before_close = log.verify()
        self.assertTrue(before_close.valid, before_close.errors)
        log.close()

        reopened = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.assertEqual(reopened.load_errors, [])
        self.assertEqual(reopened.count, 1)
        self.assertEqual(reopened.head, first["evidence"]["digest"])
        self.assertEqual(reopened.seq, 1)

        head_before_append = reopened.head
        second = reopened.append_receipt(make_receipt(2))
        self.assertEqual(second["evidence"]["seq"], 2)
        self.assertEqual(second["evidence"]["prev_digest"], head_before_append)
        report = reopened.verify()
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.checked, 2)
        self.assertEqual(report.head_digest, reopened.head)
        reopened.close()

        again = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.assertEqual(again.load_errors, [])
        self.assertEqual(again.count, 2)
        self.assertEqual(again.head, report.head_digest)

    def test_reopened_chain_matches_independent_recomputation(self) -> None:
        log = EvidenceLog("mhs://localhost:7400", path=self.path)
        for index in range(1, 4):
            log.append_receipt(make_receipt(index))
        log.close()

        reopened = EvidenceLog("mhs://localhost:7400", path=self.path)
        records = reopened.records()
        digests, head = recompute_chain(reopened.genesis, records)
        self.assertEqual(head, reopened.head)
        self.assertEqual(reopened.genesis_digest, independent_genesis_digest(reopened.genesis))
        for index, (record, expected_digest) in enumerate(zip(records, digests)):
            self.assertEqual(record["evidence"]["digest"], expected_digest)
            expected_prev = (
                reopened.genesis_digest if index == 0 else digests[index - 1]
            )
            self.assertEqual(record["evidence"]["prev_digest"], expected_prev)
        bundle = reopened.export()
        self.assertEqual(verify_bundle(bundle).head_digest, head)
        self.assertTrue(verify_bundle(bundle).valid)

    def test_tampered_log_is_still_rejected_on_strict_reopen(self) -> None:
        log = EvidenceLog("mhs://localhost:7400", path=self.path)
        log.append_receipt(make_receipt(1))
        log.append_receipt(make_receipt(2))
        log.close()

        lines = self.path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[2])
        tampered["output"] = {"tampered": True}
        lines[2] = json.dumps(tampered, ensure_ascii=False)
        self.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        with self.assertRaises(EvidenceError):
            EvidenceLog("mhs://localhost:7400", path=self.path)

        lenient = EvidenceLog("mhs://localhost:7400", path=self.path, strict=False)
        self.assertTrue(lenient.load_errors)
        with self.assertRaises(EvidenceError):
            lenient.append_receipt(make_receipt(3))

    def test_genesis_document_is_preserved_across_reopen(self) -> None:
        log = EvidenceLog("mhs://localhost:7400", path=self.path)
        genesis = log.genesis
        digest = log.genesis_digest
        log.append_receipt(make_receipt(1))
        log.close()

        reopened = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.assertEqual(reopened.genesis, genesis)
        self.assertEqual(reopened.genesis_digest, digest)
        self.assertEqual(compute_genesis_digest(reopened.genesis), digest)

    def test_empty_existing_file_is_initialised_with_genesis(self) -> None:
        self.path.write_text("", encoding="utf-8")
        log = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.assertEqual(log.count, 0)
        self.assertEqual(log.load_errors, [])
        self.assertEqual(log.seq, 0)
        record = log.append_receipt(make_receipt(1))
        self.assertEqual(record["evidence"]["seq"], 1)
        lines = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([line.get("kind", "receipt") for line in lines], ["genesis", "receipt"])


class TornTailTests(unittest.TestCase):
    """recover_torn_tail (WP-04 step 4f): a crash during an append cut the last line short."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-torn-")
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "evidence.jsonl"
        log = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.first = log.append_receipt(make_receipt(1))
        log.append_receipt(make_receipt(2))
        log.close()
        self.lines = self.path.read_bytes().splitlines(keepends=True)

    def test_a_torn_last_line_is_refused_by_default(self) -> None:
        torn = self.lines[-1][:40]
        self.path.write_bytes(b"".join(self.lines[:-1]) + torn)
        with self.assertRaises(EvidenceError):
            EvidenceLog("mhs://localhost:7400", path=self.path)

    def test_a_torn_last_line_is_kept_aside_and_the_chain_continues(self) -> None:
        torn = self.lines[-1][:40]
        self.path.write_bytes(b"".join(self.lines[:-1]) + torn)
        log = EvidenceLog("mhs://localhost:7400", path=self.path, recover_torn_tail=True)
        self.assertEqual(log.load_errors, [])
        self.assertEqual(log.count, 1)
        self.assertEqual(log.head, self.first["evidence"]["digest"])
        self.assertEqual(log.recovered_tail["bytes"], len(torn))
        self.assertEqual(Path(log.recovered_tail["kept_as"]).read_bytes(), torn)
        self.assertEqual(self.path.read_bytes(), b"".join(self.lines[:-1]))
        appended = log.append_receipt(make_receipt(3))
        self.assertEqual(appended["evidence"]["seq"], 2)
        log.close()
        reopened = EvidenceLog("mhs://localhost:7400", path=self.path)
        self.assertTrue(reopened.verify().valid)
        self.assertEqual(reopened.count, 2)

    def test_a_complete_last_record_without_its_newline_gets_it_back(self) -> None:
        self.path.write_bytes(b"".join(self.lines)[:-1])
        log = EvidenceLog("mhs://localhost:7400", path=self.path, recover_torn_tail=True)
        self.assertEqual(log.recovered_tail, {"newline_added": True})
        self.assertEqual(log.count, 2)
        log.append_receipt(make_receipt(3))
        log.close()
        self.assertEqual(EvidenceLog("mhs://localhost:7400", path=self.path).count, 3)

    def test_damage_before_the_last_line_is_never_repaired(self) -> None:
        damaged = list(self.lines)
        damaged[1] = b"{not json\n"
        self.path.write_bytes(b"".join(damaged) + b"{torn")
        with self.assertRaises(EvidenceError):
            EvidenceLog("mhs://localhost:7400", path=self.path, recover_torn_tail=True)


if __name__ == "__main__":
    unittest.main()
