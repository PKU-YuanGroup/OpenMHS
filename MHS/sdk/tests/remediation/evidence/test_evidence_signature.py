"""CODE-004 regression: truthful signature status in ``verify_bundle``.

EVID-017: verification without the signing key must report
``signature: "unverifiable"`` -- not success and not a chain failure.  The
optional ``key_resolver(signature, head_digest) -> bool`` hook distinguishes
``valid`` from ``invalid``; malformed signature objects are always ``invalid``.
"""

from __future__ import annotations

import copy
import unittest

from mhs import canonical
from mhs.evidence import EvidenceLog, verify_bundle


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


JWS = {"alg": "EdDSA", "key_id": "review-key-1", "jws": "detached-jws-value"}


class SignatureStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        log = EvidenceLog("mhs://localhost:7400")
        log.append_receipt(good_receipt())
        self.bundle = log.export()
        self.signed = copy.deepcopy(self.bundle)
        self.signed["signature"] = dict(JWS)

    def test_absent_signature(self) -> None:
        for bundle in (self.bundle, {**self.bundle, "signature": None}):
            report = verify_bundle(bundle)
            self.assertTrue(report.valid, report.errors)
            self.assertEqual(report.signature, "absent")
            self.assertEqual(report.to_dict()["signature"], "absent")

    def test_present_without_resolver_is_unverifiable(self) -> None:
        report = verify_bundle(self.signed)
        self.assertFalse(report.valid)
        self.assertEqual(report.signature, "unverifiable")
        codes = {error.get("mhs_code") for error in report.errors}
        self.assertIn("MHS.EVIDENCE.SIGNATURE_UNVERIFIABLE", codes)
        # EVID-017: this is not a chain failure.
        self.assertNotIn("MHS.EVIDENCE.CHAIN_BROKEN", codes)

    def test_resolver_accepting_signature_is_valid(self) -> None:
        report = verify_bundle(self.signed, key_resolver=lambda signature, head: True)
        self.assertTrue(report.valid, report.errors)
        self.assertEqual(report.signature, "valid")
        self.assertEqual(report.errors, [])

    def test_resolver_rejecting_signature_is_invalid(self) -> None:
        report = verify_bundle(self.signed, key_resolver=lambda signature, head: False)
        self.assertFalse(report.valid)
        self.assertEqual(report.signature, "invalid")
        self.assertIn(
            "MHS.EVIDENCE.SIGNATURE_INVALID",
            {error.get("mhs_code") for error in report.errors},
        )

    def test_malformed_signature_objects_are_invalid(self) -> None:
        malformed = [
            "not-an-object",
            [],
            {},
            {"alg": "EdDSA"},
            {"alg": "HS256", "key_id": "k", "jws": "x"},
            {"alg": "EdDSA", "key_id": "", "jws": "x"},
            {"alg": "EdDSA", "key_id": "k", "jws": ""},
        ]
        for signature in malformed:
            with self.subTest(signature=signature):
                bundle = copy.deepcopy(self.bundle)
                bundle["signature"] = signature
                called = []
                report = verify_bundle(
                    bundle,
                    key_resolver=lambda sig, head: called.append(True) or True,
                )
                self.assertFalse(report.valid)
                self.assertEqual(report.signature, "invalid")
                self.assertEqual(called, [])  # malformed never reaches the resolver

    def test_resolver_failure_is_unverifiable_not_an_exception(self) -> None:
        def broken(signature, head):
            raise RuntimeError("key store offline")

        report = verify_bundle(self.signed, key_resolver=broken)
        self.assertFalse(report.valid)
        self.assertEqual(report.signature, "unverifiable")

    def test_resolver_non_boolean_is_unverifiable(self) -> None:
        report = verify_bundle(self.signed, key_resolver=lambda signature, head: "yes")
        self.assertFalse(report.valid)
        self.assertEqual(report.signature, "unverifiable")

    def test_resolver_receives_signature_and_recomputed_head(self) -> None:
        seen = {}

        def resolver(signature, head):
            seen["signature"] = dict(signature)
            seen["head"] = head
            return True

        report = verify_bundle(self.signed, key_resolver=resolver)
        self.assertTrue(report.valid)
        self.assertEqual(seen["signature"], JWS)
        self.assertEqual(seen["head"], report.head_digest)
        self.assertEqual(seen["head"], self.bundle["head_digest"])

    def test_chain_tampering_is_still_a_chain_failure(self) -> None:
        tampered = copy.deepcopy(self.bundle)
        tampered["receipts"][0]["output"] = {"tampered": True}
        report = verify_bundle(tampered)
        self.assertFalse(report.valid)
        self.assertEqual(report.signature, "absent")
        self.assertIn(
            "MHS.EVIDENCE.CHAIN_BROKEN",
            {error.get("mhs_code") for error in report.errors},
        )


if __name__ == "__main__":
    unittest.main()
