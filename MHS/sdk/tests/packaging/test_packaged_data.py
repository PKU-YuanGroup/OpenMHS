"""An SDK copied outside the repository finds its packaged ``_data``.

Each test copies ``MHS/sdk/src/mhs`` into a temporary directory outside the
checkout, optionally populates ``mhs/_data`` with ``tools/sync_data.py``, and
runs a fresh ``python -I`` there with ``MHS_SCHEMA_DIR`` unset, so neither the
repository walk nor the environment can supply the schemas.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ._paths import EXAMPLE_DEVICE, MHS_ROOT, PACKAGE, SCHEMA_DIR, WORKSPACE, load_sync_tool

PROBE = r"""
import json, sys, warnings
sys.path.insert(0, sys.argv[1])
warnings.simplefilter("error")          # a stale-data warning would fail the probe
from mhs.schema import default_store, find_schema_dir, packaged_data_dir
store = default_store()
with open(sys.argv[2], encoding="utf-8") as handle:
    example = json.load(handle)
found = find_schema_dir()
data = packaged_data_dir()
print(json.dumps({
    "schema_dir": str(found) if found else None,
    "data_dir": str(data) if data else None,
    "documents": len(store),
    "errors": store.validate(example, "device.schema.json") if len(store) else ["no schemas"],
    "public": store.resolve_public("device.schema.json")[1] if len(store) else None,
}))
"""


def _clean_env() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items()
           if key != "MHS_SCHEMA_DIR" and not key.startswith("PYTHON")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


class PackagedDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="openmhs-wheel-like-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.assertNotIn(WORKSPACE.resolve(), self.tmp.parents, "the copy must live outside the repo")
        self.site = self.tmp / "site-packages"
        shutil.copytree(
            PACKAGE, self.site / "mhs",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_data"),
        )

    def _probe(self, cwd: Path | None = None) -> dict:
        completed = subprocess.run(
            [sys.executable, "-I", "-c", PROBE, str(self.site), str(EXAMPLE_DEVICE)],
            cwd=str(cwd or self.tmp), env=_clean_env(), capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout.strip().splitlines()[-1])

    def test_packaged_data_is_found_without_env_or_checkout(self) -> None:
        sync = load_sync_tool()
        sync.sync(MHS_ROOT, self.site / "mhs" / "_data")
        result = self._probe()
        expected = (self.site / "mhs" / "_data" / "schema").resolve()
        self.assertEqual(Path(result["schema_dir"]), expected)
        self.assertEqual(Path(result["data_dir"]), expected.parent)
        self.assertEqual(result["documents"], len(list(SCHEMA_DIR.glob("*.schema.json"))))
        self.assertEqual(result["errors"], [])
        self.assertEqual(Path(result["public"]).parent, expected)
        for name in ("capabilities.json", "errors.json"):
            self.assertTrue((expected.parent / "spec" / name).is_file(), name)

    def test_without_packaged_data_nothing_is_found(self) -> None:
        # Negative control: the copy alone has no schemas, so the result above
        # really comes from mhs/_data.
        result = self._probe()
        self.assertIsNone(result["schema_dir"])
        self.assertIsNone(result["data_dir"])
        self.assertEqual(result["documents"], 0)

    def test_env_override_wins_over_packaged_data(self) -> None:
        sync = load_sync_tool()
        sync.sync(MHS_ROOT, self.site / "mhs" / "_data")
        override = self.tmp / "override"
        override.mkdir()
        shutil.copy(SCHEMA_DIR / "device.schema.json", override / "device.schema.json")
        shutil.copy(SCHEMA_DIR / "defs.schema.json", override / "defs.schema.json")
        env = _clean_env()
        env["MHS_SCHEMA_DIR"] = str(override)
        completed = subprocess.run(
            [sys.executable, "-I", "-c", PROBE, str(self.site), str(EXAMPLE_DEVICE)],
            cwd=str(self.tmp), env=env, capture_output=True, text=True, timeout=60,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout.strip().splitlines()[-1])
        self.assertEqual(Path(result["schema_dir"]), override.resolve())
        self.assertEqual(result["documents"], 2)


class CheckoutDriftTests(unittest.TestCase):
    """In a source checkout, stale packaged data never shadows ``MHS/schema``."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="openmhs-checkout-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.mhs = self.tmp / "MHS"
        shutil.copytree(SCHEMA_DIR, self.mhs / "schema", ignore=shutil.ignore_patterns("examples"))
        (self.mhs / "spec").mkdir(parents=True)
        for name in ("capabilities.json", "errors.json"):
            shutil.copy(MHS_ROOT / "spec" / name, self.mhs / "spec" / name)
        self.src = self.mhs / "sdk" / "src"
        shutil.copytree(PACKAGE, self.src / "mhs",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_data"))
        load_sync_tool().sync(self.mhs, self.src / "mhs" / "_data")

    def _run(self) -> subprocess.CompletedProcess:
        code = (
            "import sys; sys.path.insert(0, sys.argv[1]);"
            "from mhs.schema import find_schema_dir; print(find_schema_dir())"
        )
        return subprocess.run(
            [sys.executable, "-I", "-W", "always", "-c", code, str(self.src)],
            cwd=str(self.tmp), env=_clean_env(), capture_output=True, text=True, timeout=60,
        )

    def test_in_sync_data_is_used(self) -> None:
        completed = self._run()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(Path(completed.stdout.strip()),
                         (self.src / "mhs" / "_data" / "schema").resolve())
        self.assertNotIn("RuntimeWarning", completed.stderr)

    def test_stale_data_falls_back_to_the_checkout_with_a_warning(self) -> None:
        target = self.mhs / "schema" / "permit.schema.json"
        document = json.loads(target.read_text(encoding="utf-8"))
        document["description"] = "edited after the last sync"
        target.write_text(json.dumps(document), encoding="utf-8")
        completed = self._run()
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(Path(completed.stdout.strip()), (self.mhs / "schema").resolve())
        self.assertIn("RuntimeWarning", completed.stderr)
        self.assertIn("sync_data.py", completed.stderr)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
