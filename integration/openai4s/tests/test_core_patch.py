"""openai4s-core.patch: the recorded OpenAI4S core change of the governed host route.

The governed route lives partly in OpenAI4S core files, so the integration ships
that change as a patch against one upstream commit.  These tests keep the claim
honest: the patch names its base commit, applies to a clean tree at that commit
(a temporary ``git clone --shared``; the checkout is only read), still equals
the checkout's diff, and contains the hooks ``hostroute`` relies on.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import shutil
import unittest

from openai4s_mhs import corepatch
from openai4s_mhs.cli import main

CORE_FILES = ["openai4s/host/mcp.py", "openai4s/host_dispatch.py"]


def _checkout_has_base() -> bool:
    if shutil.which("git") is None or not (corepatch.DEFAULT_SOURCE / ".git").exists():
        return False
    try:
        base = corepatch.load().base_commit
        return corepatch._git(  # noqa: SLF001 - read-only probe
            ["cat-file", "-e", f"{base}^{{commit}}"], cwd=corepatch.DEFAULT_SOURCE, check=False
        ).returncode == 0
    except corepatch.CorePatchError:
        return False


class RecordedPatchTests(unittest.TestCase):
    def test_header_names_upstream_base_commit_and_files(self) -> None:
        patch = corepatch.load()
        self.assertRegex(patch.base_commit, r"^[0-9a-f]{40}$")
        self.assertEqual(patch.header["Upstream"], corepatch.UPSTREAM_URL)
        self.assertEqual(patch.header["OpenAI4S-Version"], "0.3.1")
        self.assertEqual(patch.files, CORE_FILES)
        self.assertEqual(patch.header["Files"].split(), CORE_FILES)
        self.assertTrue(patch.body.startswith("diff --git a/openai4s/host/mcp.py"))
        self.assertIn("not affiliated with or endorsed by", patch.text)

    def test_stat_header_matches_the_body(self) -> None:
        patch = corepatch.load()
        added = sum(1 for line in patch.body.splitlines()
                    if line.startswith("+") and not line.startswith("+++"))
        removed = sum(1 for line in patch.body.splitlines()
                      if line.startswith("-") and not line.startswith("---"))
        self.assertEqual(
            patch.header["Stat"],
            f"{len(patch.files)} files changed, {added} insertions(+), {removed} deletions(-)",
        )

    def test_patch_contains_the_hooks_hostroute_relies_on(self) -> None:
        body = corepatch.load().body
        for needle in (
            "from openai4s_mhs import hostroute",
            "hostroute.governed_call(",
            "hostroute.trusted_emergency_stop(",
            "def is_trusted_estop(self, spec: dict) -> bool:",
            "def emergency_stop(self, spec: dict) -> Any:",
            "def _m_mhs_emergency_stop(self, spec: dict) -> Any:",
        ):
            self.assertIn(needle, body)

    def test_overlay_hook_is_a_separate_optional_patch(self) -> None:
        overlay = corepatch.load(corepatch.OVERLAY_PATCH_FILE)
        self.assertEqual(overlay.files, ["openai4s/__init__.py"])
        self.assertEqual(overlay.base_commit, corepatch.load().base_commit)
        self.assertFalse(set(overlay.files) & set(CORE_FILES))

    def test_header_lines_are_not_patch_syntax(self) -> None:
        text = corepatch.PATCH_FILE.read_text(encoding="utf-8")
        header = text[: text.index("diff --git ")]
        for line in header.splitlines():
            self.assertIsNone(re.match(r"^(diff |--- |\+\+\+ |@@ |index |Index: )", line), line)

    def test_missing_checkout_is_a_setup_error(self) -> None:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["core-patch", "check", "--source", "/nonexistent/openai4s"])
        self.assertEqual(code, 2)
        self.assertIn("MHS.HOST.CONFIG_REQUIRED", err.getvalue())


def _checkout_carries_the_patch() -> bool:
    """The checkout has the core change applied (a diff in the core files against HEAD).

    A pristine OpenAI4S checkout at the base commit only supports the ``applies`` checks: there is no change
    to compare with the recorded patch (README section 7).
    """
    if not _checkout_has_base():
        return False
    return corepatch._git(  # noqa: SLF001 - read-only probe
        ["diff", "--quiet", "HEAD", "--", *CORE_FILES], cwd=corepatch.DEFAULT_SOURCE, check=False
    ).returncode == 1


@unittest.skipUnless(_checkout_has_base(), "no git or no OpenAI4S checkout containing the base commit")
class CheckoutTests(unittest.TestCase):
    def test_patch_applies_at_the_base_commit_and_matches_the_checkout(self) -> None:
        result = corepatch.check()
        self.assertTrue(result["applies"], result)
        if not _checkout_carries_the_patch():
            self.skipTest("the checkout does not carry the core change; only `applies` is checked")
        if result.get("source_head") == result["base_commit"]:
            self.assertTrue(result["matches"], result)
        self.assertTrue(result["ok"], result)

    def test_overlay_applies_at_the_base_commit(self) -> None:
        result = corepatch.check(corepatch.OVERLAY_PATCH_FILE, compare=False)
        self.assertTrue(result["applies"], result)

    def test_cli_check_reports_ok_as_json(self) -> None:
        if not _checkout_carries_the_patch():
            self.skipTest("the checkout does not carry the core change; drift cannot be compared")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = main(["core-patch", "check", "--json"])
        self.assertEqual(code, 0, err.getvalue())
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["files"], CORE_FILES)

    def test_capture_reproduces_the_recorded_patch(self) -> None:
        head = corepatch._git(["rev-parse", "HEAD"], cwd=corepatch.DEFAULT_SOURCE).stdout.strip()  # noqa: SLF001
        if head != corepatch.load().base_commit:
            self.skipTest("the checkout moved off the base commit")
        if not _checkout_carries_the_patch():
            self.skipTest("the checkout does not carry the core change")
        self.assertEqual(corepatch.captured_text(), corepatch.PATCH_FILE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
