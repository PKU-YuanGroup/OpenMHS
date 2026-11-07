"""RECHECK-CODE-001: malformed evidence metadata must not raise TypeError.

``verify_bundle`` is the public offline verifier: a bundle that is valid JSON but
carries the wrong field type (array/object/null/bool/number) must produce a
structured ``valid: false`` report with a field-specific error.  The old code
performed ``value in frozenset(...)`` before any type check, so ``[]``/``{}``
escaped as ``TypeError``.  A blanket ``except`` that returns ``valid: true`` is
equally wrong; every case below also pins the truthful signature status.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from mhs import canonical
from mhs.evidence import EvidenceLog, verify_bundle

from .support import TempDir


def _json_roundtrip(value):
    return json.loads(json.dumps(value))


def _receipt(*, ticks: int = 1) -> dict:
    return {
        "receipt_id": canonical.ulid(),
        "command_id": canonical.ulid(),
        "session_id": "mhs_s_0123456789abcdefghijklmn",
        "endpoint_id": "mhs://localhost:7400",
        "device_id": "mhs://localhost:7400/lab/test",
        "capability_id": "cap.world.step.v1",
        "input_digest": canonical.digest({"ticks": ticks}),
        "status": "completed",
        "mode": "simulated",
        "accepted_at": canonical.now_rfc3339(),
        "output": {"ticks": ticks},
    }


class VerifyBundleMetadataTests(unittest.TestCase):
    """Type-safe metadata handling with truthful signature/valid semantics."""

    def setUp(self):
        self._tmp = TempDir()
        self.tmp = self._tmp.__enter__()
        log = EvidenceLog("mhs://localhost:7400", path=Path(self.tmp) / "evidence.jsonl",
                          fsync=False)
        log.append_receipt(_receipt(ticks=1))
        log.append_receipt(_receipt(ticks=2))
        self.bundle = _json_roundtrip(log.export())
        log.close()

    def tearDown(self):
        self._tmp.__exit__(None, None, None)

    # -- helpers -----------------------------------------------------------
    def _verify(self, bundle):
        """Call verify_bundle and convert any escape into a test failure."""

        try:
            return verify_bundle(_json_roundtrip(bundle))
        except Exception as exc:  # noqa: BLE001 - the defect under test
            self.fail(
                f"verify_bundle raised {type(exc).__name__}: {exc} "
                f"for ordinary JSON-domain input"
            )

    def _assert_structured_failure(self, report, *, field: str, code: str) -> None:
        self.assertFalse(report["valid"], report)
        self.assertTrue(report["errors"], report)
        messages = " | ".join(str(item.get("detail")) for item in report["errors"])
        self.assertIn(field, messages, messages)
        self.assertIn(code, [item.get("mhs_code") for item in report["errors"]], messages)
        # A report must always be JSON serializable.
        json.dumps(dict(report))

    # -- positive controls -------------------------------------------------
    def test_valid_bundle_still_verifies(self):
        report = self._verify(self.bundle)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["checked"], 2)
        self.assertEqual(report["signature"], "absent")
        self.assertEqual(report["schema"], "validated")

    def test_supported_bundle_versions_are_accepted(self):
        for version in ("1.0", "1.0.0"):
            bundle = dict(self.bundle)
            bundle["bundle_version"] = version
            report = self._verify(bundle)
            self.assertTrue(report["valid"], f"{version}: {report['errors']}")

    def test_absent_bundle_version_uses_default(self):
        bundle = dict(self.bundle)
        bundle.pop("bundle_version", None)
        report = self._verify(bundle)
        self.assertTrue(report["valid"], report["errors"])

    # -- bundle_version wrong types ---------------------------------------
    def test_bundle_version_wrong_types_are_structured(self):
        for value in ([], {}, None, True, False, 1, 0, 1.5, ["1.0"], {"v": "1.0"}):
            with self.subTest(value=repr(value)):
                bundle = dict(self.bundle)
                bundle["bundle_version"] = value
                report = self._verify(bundle)
                self._assert_structured_failure(
                    report, field="bundle_version", code="MHS.EVIDENCE.CHAIN_BROKEN"
                )
                self.assertEqual(report["signature"], "absent")

    def test_unsupported_string_bundle_version_is_structured(self):
        for value in ("99.0", "1", "", "1.0.0.0"):
            with self.subTest(value=value):
                bundle = dict(self.bundle)
                bundle["bundle_version"] = value
                report = self._verify(bundle)
                self._assert_structured_failure(
                    report, field="bundle_version", code="MHS.EVIDENCE.CHAIN_BROKEN"
                )

    # -- signature.alg wrong types ----------------------------------------
    def test_signature_alg_wrong_types_are_structured(self):
        for value in ([], {}, None, True, False, 1, 1.5, ["EdDSA"], {"alg": "EdDSA"}):
            with self.subTest(value=repr(value)):
                bundle = dict(self.bundle)
                bundle["signature"] = {"alg": value, "key_id": "k", "jws": "x"}
                report = self._verify(bundle)
                self._assert_structured_failure(
                    report, field="signature.alg", code="MHS.EVIDENCE.SIGNATURE_INVALID"
                )
                self.assertEqual(report["signature"], "invalid")
                self.assertFalse(report["valid"])

    def test_unsupported_string_signature_alg_is_structured(self):
        bundle = dict(self.bundle)
        bundle["signature"] = {"alg": "HS256", "key_id": "k", "jws": "x"}
        report = self._verify(bundle)
        self._assert_structured_failure(
            report, field="signature.alg", code="MHS.EVIDENCE.SIGNATURE_INVALID"
        )
        self.assertEqual(report["signature"], "invalid")

    def test_signature_shape_wrong_types_are_structured(self):
        cases = {
            "signature_array": [],
            "signature_object": {},
            "signature_string": "signed",
            "signature_bool": True,
            "signature_number": 1,
        }
        for name, value in cases.items():
            with self.subTest(name=name):
                bundle = dict(self.bundle)
                bundle["signature"] = value
                report = self._verify(bundle)
                self._assert_structured_failure(
                    report, field="signature", code="MHS.EVIDENCE.SIGNATURE_INVALID"
                )
                self.assertEqual(report["signature"], "invalid")
        for field in ("key_id", "jws"):
            for value in (None, True, 1, [], {}):
                with self.subTest(field=field, value=repr(value)):
                    bundle = dict(self.bundle)
                    bundle["signature"] = {"alg": "EdDSA", "key_id": "k", "jws": "x"}
                    bundle["signature"][field] = value
                    report = self._verify(bundle)
                    self._assert_structured_failure(
                        report, field=f"signature.{field}",
                        code="MHS.EVIDENCE.SIGNATURE_INVALID",
                    )

    # -- truthful signature statuses ---------------------------------------
    def test_well_formed_signature_without_resolver_is_unverifiable(self):
        bundle = dict(self.bundle)
        bundle["signature"] = {"alg": "EdDSA", "key_id": "unavailable", "jws": "proof"}
        report = self._verify(bundle)
        self.assertFalse(report["valid"])
        self.assertEqual(report["signature"], "unverifiable")
        self.assertIn(
            "MHS.EVIDENCE.SIGNATURE_UNVERIFIABLE",
            [item.get("mhs_code") for item in report["errors"]],
        )

    def test_resolver_accepts_and_rejects(self):
        bundle = dict(self.bundle)
        bundle["signature"] = {"alg": "ES256", "key_id": "k", "jws": "proof"}
        seen = {}

        def accept(signature, head_digest):
            seen["signature"] = signature
            seen["head"] = head_digest
            return True

        report = verify_bundle(_json_roundtrip(bundle), key_resolver=accept)
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(report["signature"], "valid")
        self.assertEqual(seen["signature"]["alg"], "ES256")
        self.assertEqual(seen["head"], self.bundle["head_digest"])

        report = verify_bundle(_json_roundtrip(bundle), key_resolver=lambda *_: False)
        self.assertFalse(report["valid"])
        self.assertEqual(report["signature"], "invalid")

    def test_non_object_bundle_is_structured(self):
        for bundle in ([], [], "bundle", 1, True, None):
            with self.subTest(bundle=repr(bundle)):
                try:
                    report = verify_bundle(bundle)
                except Exception as exc:  # noqa: BLE001
                    self.fail(f"verify_bundle raised {type(exc).__name__} for {bundle!r}")
                self.assertFalse(report["valid"])
                self.assertEqual(report["checked"], 0)

    def test_receipt_digest_and_chain_checks_still_fail_closed(self):
        tampered = json.loads(json.dumps(self.bundle))
        tampered["receipts"][0]["output"] = {"ticks": 999}
        report = self._verify(tampered)
        self.assertFalse(report["valid"])
        self.assertIn("digest", " | ".join(
            str(item.get("detail")) for item in report["errors"]
        ).lower())

        broken_head = json.loads(json.dumps(self.bundle))
        broken_head["head_digest"] = "sha256:" + "0" * 64
        report = self._verify(broken_head)
        self.assertFalse(report["valid"])
        self.assertIn("head_digest", " | ".join(
            str(item.get("detail")) for item in report["errors"]
        ))


if __name__ == "__main__":
    unittest.main()
