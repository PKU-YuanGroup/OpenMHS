"""CODE-005 regression: malformed evidence links never escape as exceptions.

Untrusted/damaged bundles must always produce a :class:`VerifyReport` with
structured ``{seq, mhs_code, detail}`` errors: digest shapes are validated
before hashing (``sha256:<64 lowercase hex>``), non-JSON-domain values are
reported, and a non-ASCII ``prev_digest`` cannot raise ``UnicodeEncodeError``.
"""

from __future__ import annotations

import copy
import unittest

from mhs import canonical
from mhs.evidence import EvidenceLog, VerifyReport, verify_bundle


def good_receipt() -> dict[str, object]:
    return {
        "receipt_id": canonical.ulid(),
        "command_id": canonical.ulid(),
        "session_id": "mhs_s_0123456789",
        "endpoint_id": "mhs://localhost:7400",
        "device_id": "mhs://localhost:7400/lab/test",
        "capability_id": "cap.world.step.v1",
        "input_digest": canonical.digest({"ticks": 1}),
        "status": "completed",
        "mode": "simulated",
        "accepted_at": canonical.now_rfc3339(),
        "output": {"ticks": 1},
    }


class MalformedEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        log = EvidenceLog("mhs://localhost:7400")
        log.append_receipt(good_receipt())
        self.bundle = log.export()

    def _mutated(self, mutate) -> dict:
        bundle = copy.deepcopy(self.bundle)
        mutate(bundle)
        return bundle

    def _assert_structured_failure(self, bundle, *, seq=1) -> VerifyReport:
        report = verify_bundle(bundle)  # must not raise
        self.assertIsInstance(report, VerifyReport)
        self.assertFalse(report.valid)
        self.assertTrue(report.errors)
        for error in report.errors:
            self.assertIn("seq", error)
            self.assertIn("mhs_code", error)
            self.assertIn("detail", error)
        if seq is not None:
            self.assertIn(seq, [error.get("seq") for error in report.errors])
        return report

    def test_non_ascii_prev_digest_is_structured(self) -> None:
        bundle = self._mutated(
            lambda b: b["receipts"][0]["evidence"].__setitem__(
                "prev_digest", "not-an-ascii-digest-\u2603"
            )
        )
        report = self._assert_structured_failure(bundle)
        details = " ".join(str(error.get("detail")) for error in report.errors)
        self.assertIn("prev_digest is not a valid sha256 digest", details)
        self.assertIn("MHS.EVIDENCE.CHAIN_BROKEN", {e.get("mhs_code") for e in report.errors})

    def test_bad_prev_digest_shapes_are_structured(self) -> None:
        for value in [
            None,
            "",
            "not-a-digest",
            "sha256:XYZ",
            "sha256:" + "a" * 63,
            "sha256:" + "a" * 65,
            "sha256:" + "A" * 64,
            "x" * 64,
            123,
            b"sha256:" + b"a" * 64,
        ]:
            with self.subTest(value=value):
                bundle = self._mutated(
                    lambda b, value=value: b["receipts"][0]["evidence"].__setitem__(
                        "prev_digest", value
                    )
                )
                self._assert_structured_failure(bundle)

    def test_bad_claimed_digest_shapes_are_structured(self) -> None:
        for value in [
            None,
            123,
            "sha256:XYZ",
            "sha256:" + "A" * 64,
            "sha256:" + "a" * 63,
            "\u2603",
            b"bytes",
        ]:
            with self.subTest(value=value):
                bundle = self._mutated(
                    lambda b, value=value: b["receipts"][0]["evidence"].__setitem__(
                        "digest", value
                    )
                )
                self._assert_structured_failure(bundle)

    def test_malformed_seq_values_are_structured(self) -> None:
        for value in ["1", 1.0, True, None, [1]]:
            with self.subTest(value=value):
                bundle = self._mutated(
                    lambda b, value=value: b["receipts"][0]["evidence"].__setitem__(
                        "seq", value
                    )
                )
                report = self._assert_structured_failure(bundle)
                self.assertIn(
                    "evidence.seq must be an integer",
                    " ".join(str(error.get("detail")) for error in report.errors),
                )

    def test_missing_or_non_object_evidence_link_is_structured(self) -> None:
        for mutation in (
            lambda b: b["receipts"][0].pop("evidence"),
            lambda b: b["receipts"][0].__setitem__("evidence", []),
            lambda b: b["receipts"][0].__setitem__("evidence", "link"),
        ):
            with self.subTest(mutation=mutation):
                self._assert_structured_failure(self._mutated(mutation))

    def test_non_json_receipt_values_are_structured(self) -> None:
        for value in [
            {"value": float("nan")},
            {"value": float("inf")},
            {"value": 2**60},
            {"value": b"\xff"},
            {"value": {1, 2}},
            {"value": object()},
        ]:
            with self.subTest(value=value):
                bundle = self._mutated(
                    lambda b, value=value: b["receipts"][0].__setitem__("output", value)
                )
                report = self._assert_structured_failure(bundle)
                details = " ".join(str(error.get("detail")) for error in report.errors)
                self.assertIn("cannot be canonicalised", details)

    def test_malformed_genesis_document_is_structured(self) -> None:
        for mutation in (
            lambda b: b["genesis"]["genesis_document"].__setitem__("endpoint_id", b"\xff"),
            lambda b: b["genesis"]["genesis_document"].__setitem__("bad", 2**60),
            lambda b: b["genesis"]["genesis_document"].__setitem__("bad", float("nan")),
        ):
            with self.subTest(mutation=mutation):
                report = self._assert_structured_failure(self._mutated(mutation), seq=None)
                self.assertIn(
                    "genesis document is not canonical JSON",
                    " ".join(str(error.get("detail")) for error in report.errors),
                )

    def test_malformed_head_digest_shapes_are_structured(self) -> None:
        for value in [None, "not-a-digest", 123, "sha256:XYZ", "sha256:" + "A" * 64]:
            with self.subTest(value=value):
                bundle = self._mutated(lambda b, value=value: b.__setitem__("head_digest", value))
                report = self._assert_structured_failure(bundle, seq=None)
                self.assertIn(
                    "head_digest is not a valid sha256 digest",
                    " ".join(str(error.get("detail")) for error in report.errors),
                )

    def test_top_level_malformed_bundle_shapes_are_structured(self) -> None:
        for bundle in (
            [],
            "bundle",
            {**self.bundle, "receipts": {}},
            {**self.bundle, "receipts": ["x"]},
            {**self.bundle, "receipts": None},
        ):
            with self.subTest(bundle=type(bundle).__name__):
                report = verify_bundle(bundle)
                self.assertFalse(report.valid)
                self.assertTrue(report.errors)

    def test_valid_bundle_still_passes(self) -> None:
        report = verify_bundle(self.bundle)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.signature, "absent")
        self.assertEqual(report.schema, "validated")
        self.assertEqual(canonical.is_digest(report.head_digest), True)


if __name__ == "__main__":
    unittest.main()
