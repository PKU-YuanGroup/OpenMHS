"""Licence, notice and landing files exist, agree and carry the notice."""

from __future__ import annotations

import hashlib
import re
import unittest
from urllib.parse import urlsplit

from mhs._ids import LEGACY_SCHEMA_PREFIX, NON_AFFILIATION

from ._paths import MHS_ROOT, SDK, WORKSPACE

LEGACY_HOST = urlsplit(LEGACY_SCHEMA_PREFIX).hostname.split(".")[0]
MIT_SHA256 = "5c84c1ea5a5b00492b7c978bb717213a08cb8a82b4aa9bb81e49b18b2bc7a93a"
# Private research directories that the landing pages must not point at.
PRIVATE_PATTERNS = [
    r"(?<![\w/.-])review/",
    r"(?<![\w/.-])remediation[\w-]*/",
    r"(?<![\w/.-])work/",
    r"(?<![\w/.-])reports/",
    r"clone_audit",
    r"openai4s_backend_catalog",
    r"verification/",
]


def _read(path):
    return path.read_text(encoding="utf-8")


class SdkLicenceFilesTests(unittest.TestCase):
    def test_sdk_licence_is_the_mit_text(self) -> None:
        data = (SDK / "LICENSE").read_bytes()
        self.assertTrue(data.startswith(b"MIT License"))
        self.assertEqual(hashlib.sha256(data).hexdigest(), MIT_SHA256)

    def test_sdk_notice_names_holder_and_non_affiliation(self) -> None:
        text = _read(SDK / "NOTICE")
        self.assertIn("Copyright (c) 2026 PKU-YUAN-Lab", text)
        self.assertIn(" ".join(NON_AFFILIATION.split()), " ".join(text.split()))

    def test_sdk_readme_starts_with_a_heading(self) -> None:
        self.assertTrue(_read(SDK / "README.md").startswith("# "))


@unittest.skipUnless((WORKSPACE / "LICENSE").is_file(), "repository root files not present")
class RootFilesTests(unittest.TestCase):
    def test_sdk_copies_are_byte_identical(self) -> None:
        for name in ("LICENSE", "NOTICE"):
            with self.subTest(name=name):
                self.assertEqual((WORKSPACE / name).read_bytes(), (SDK / name).read_bytes())

    def test_docs_licence_is_cc_by_4_with_carve_out(self) -> None:
        text = _read(WORKSPACE / "LICENSE-docs")
        self.assertIn("Creative Commons Attribution 4.0 International Public License", text)
        for section in range(1, 9):
            self.assertIn(f"Section {section} --", text)
        self.assertIn("Creative Commons may be contacted at creativecommons.org.", text)
        self.assertIn("appendix-d-anthropic-mhs.md", text)
        self.assertIn("not licensed\nby this project", text)

    def test_code_of_conduct_is_contributor_covenant_2_1(self) -> None:
        text = _read(WORKSPACE / "CODE_OF_CONDUCT.md")
        self.assertTrue(text.startswith("# Contributor Covenant Code of Conduct"))
        self.assertIn("version 2.1", text)
        self.assertNotIn("[INSERT CONTACT METHOD]", text)

    def test_security_policy_treats_safety_like_security(self) -> None:
        text = _read(WORKSPACE / "SECURITY.md")
        flat = " ".join(text.replace("**", "").split())
        self.assertIn("safety defects exactly like security defects", flat)
        self.assertIn("private vulnerability reporting", flat)
        self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), "no e-mail address")

    def test_landing_pages_start_with_a_heading_and_stay_public(self) -> None:
        for path in (WORKSPACE / "README.md", MHS_ROOT / "README.md", SDK / "README.md"):
            with self.subTest(path=path.relative_to(WORKSPACE)):
                text = _read(path)
                self.assertTrue(text.startswith("# "))
                self.assertNotIn(LEGACY_HOST, text)
                self.assertNotIn("BEGIN GENERATED: current-verification", text)
                for pattern in PRIVATE_PATTERNS:
                    self.assertIsNone(re.search(pattern, text), pattern)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
