"""CODE-002 regression: receipt schema validation is real and never silent.

``verify_bundle`` must validate every receipt with
``mhs.schema.store.default_store()``, report violations as structured errors
carrying the receipt ``seq``, and report ``schema: "unavailable"`` (a failed,
incomplete verification state) when the schema set is missing or malformed.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import mhs.evidence as evidence
from mhs import canonical
from mhs.evidence import EvidenceLog, verify_bundle
from mhs.schema import clear_default_store, default_store

from ._independent import recompute_chain


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


class ReceiptSchemaVerificationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_schema_dir = os.environ.get("MHS_SCHEMA_DIR")
        self._tmp = tempfile.TemporaryDirectory(prefix="mhs-code002-")
        clear_default_store()

    def tearDown(self) -> None:
        if self._old_schema_dir is None:
            os.environ.pop("MHS_SCHEMA_DIR", None)
        else:
            os.environ["MHS_SCHEMA_DIR"] = self._old_schema_dir
        clear_default_store()
        self._tmp.cleanup()

    def _use_schema_dir(self, directory: Path) -> None:
        os.environ["MHS_SCHEMA_DIR"] = str(directory)
        clear_default_store()

    def _invalid_receipt_bundle(self) -> dict:
        log = EvidenceLog("mhs://localhost:7400")
        log.append_receipt({"only": "this is not a receipt"})
        return log.export()

    def test_private_helper_calls_real_default_store(self) -> None:
        receipt = {"only": "this is not a receipt"}
        direct = default_store().validate(receipt, "receipt.schema.json")
        helper = evidence._receipt_schema_errors(receipt)
        self.assertEqual(helper, direct)
        self.assertGreaterEqual(len(direct), 10)
        self.assertTrue(any("missing required property" in item for item in direct))
        self.assertTrue(any("additional property 'only'" in item for item in direct))

    def test_correctly_chained_schema_invalid_receipt_fails(self) -> None:
        bundle = self._invalid_receipt_bundle()

        # The chain links themselves are correct: only the receipt shape is bad.
        digests, head = recompute_chain(
            bundle["genesis"]["genesis_document"], bundle["receipts"]
        )
        self.assertEqual(head, bundle["head_digest"])
        self.assertEqual(
            [record["evidence"]["digest"] for record in bundle["receipts"]],
            digests,
        )

        report = verify_bundle(bundle)
        self.assertFalse(report.valid)
        self.assertEqual(report.checked, 1)
        self.assertEqual(report.schema, "validated")
        schema_errors = [
            error for error in report.errors if error.get("mhs_code") == "MHS.EVIDENCE.SCHEMA_INVALID"
        ]
        self.assertTrue(schema_errors)
        self.assertTrue(all(error.get("seq") == 1 for error in schema_errors))
        details = " ".join(str(error.get("detail")) for error in schema_errors)
        self.assertIn("missing required property 'receipt_id'", details)
        self.assertIn("additional property 'only'", details)
        # Schema failures must not be misreported as chain-link failures.
        self.assertNotIn("MHS.EVIDENCE.CHAIN_BROKEN", {e.get("mhs_code") for e in report.errors})

    def test_valid_bundle_reports_schema_validated(self) -> None:
        log = EvidenceLog("mhs://localhost:7400")
        log.append_receipt(good_receipt())
        report = verify_bundle(log.export())
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.schema, "validated")
        self.assertEqual(report.errors, [])
        self.assertEqual(report.to_dict()["schema"], "validated")

    def test_unavailable_schema_set_is_an_explicit_failure(self) -> None:
        bundle = self._invalid_receipt_bundle()
        directory = Path(self._tmp.name) / "incomplete"
        directory.mkdir()
        (directory / "unrelated.schema.json").write_text('{"type":"object"}\n', encoding="utf-8")
        self._use_schema_dir(directory)
        self.assertNotIn("receipt.schema.json", default_store().names())

        report = verify_bundle(bundle)
        self.assertFalse(report.valid)
        self.assertEqual(report.schema, "unavailable")
        codes = {error.get("mhs_code") for error in report.errors}
        self.assertIn("MHS.EVIDENCE.SCHEMA_UNAVAILABLE", codes)
        self.assertTrue(
            any(error.get("seq") == 1 for error in report.errors),
            report.errors,
        )
        self.assertNotIn("MHS.EVIDENCE.CHAIN_BROKEN", codes)

    def test_malformed_receipt_schema_is_an_explicit_failure(self) -> None:
        bundle = self._invalid_receipt_bundle()
        directory = Path(self._tmp.name) / "malformed"
        directory.mkdir()
        (directory / "receipt.schema.json").write_text(
            '{"type": "object", broken json}\n', encoding="utf-8"
        )
        self._use_schema_dir(directory)

        report = verify_bundle(bundle)
        self.assertFalse(report.valid)
        self.assertEqual(report.schema, "unavailable")
        self.assertIn(
            "MHS.EVIDENCE.SCHEMA_UNAVAILABLE",
            {error.get("mhs_code") for error in report.errors},
        )

    def test_unavailable_schema_helper_raises_instead_of_returning_empty(self) -> None:
        directory = Path(self._tmp.name) / "empty"
        directory.mkdir()
        (directory / "unrelated.schema.json").write_text('{"type":"object"}\n', encoding="utf-8")
        self._use_schema_dir(directory)
        with self.assertRaises(Exception):
            evidence._receipt_schema_errors(good_receipt())


if __name__ == "__main__":
    unittest.main()
