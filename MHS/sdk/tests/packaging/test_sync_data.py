"""``tools/sync_data.py`` mirrors the normative JSON and detects drift."""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from mhs._ids import LEGACY_SCHEMA_PREFIX, SCHEMA_BASE

from ._paths import MHS_ROOT, SCHEMA_DIR, load_sync_tool


class SyncDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sync = load_sync_tool()
        self.tmp = Path(tempfile.mkdtemp(prefix="openmhs-sync-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "_data"

    def _main(self, *argv: str) -> tuple[int, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            status = self.sync.main(list(argv))
        return status, out.getvalue() + err.getvalue()

    def test_plan_covers_schemas_and_spec_registries(self) -> None:
        plan = self.sync.plan(MHS_ROOT)
        schemas = {f"schema/{p.name}" for p in SCHEMA_DIR.glob("*.json")}
        self.assertEqual({k for k in plan if k.startswith("schema/")}, schemas)
        self.assertIn("spec/capabilities.json", plan)
        self.assertIn("spec/errors.json", plan)
        self.assertFalse(any("examples" in key for key in plan))

    def test_sync_then_check_is_clean_and_byte_identical(self) -> None:
        changed = self.sync.sync(MHS_ROOT, self.data)
        self.assertEqual(sorted(changed), sorted(self.sync.plan(MHS_ROOT)))
        self.assertEqual(self.sync.drift(MHS_ROOT, self.data), [])
        for rel, source in self.sync.plan(MHS_ROOT).items():
            self.assertEqual((self.data / rel).read_bytes(), source.read_bytes(), rel)
        self.assertEqual(self.sync.sync(MHS_ROOT, self.data), [], "second sync is a no-op")
        status, output = self._main("--check", "--data-dir", str(self.data))
        self.assertEqual(status, 0, output)

    def test_a_directory_that_is_not_package_data_is_never_pruned(self) -> None:
        stranger = self.tmp / "my-project"
        (stranger / "schema").mkdir(parents=True)
        precious = stranger / "schema" / "notes.json"
        precious.write_text("{}", encoding="utf-8")
        status, output = self._main("--data-dir", str(stranger))
        self.assertEqual(status, 2, output)
        self.assertIn("refusing", output)
        self.assertTrue(precious.exists(), "a refused sync must not touch the directory")
        # an empty directory, and one an earlier sync marked, are fine
        empty = self.tmp / "fresh"
        empty.mkdir()
        self.assertEqual(self._main("--data-dir", str(empty))[0], 0)
        self.assertTrue((empty / self.sync.MARKER).is_file())
        (empty / "schema" / "stale.schema.json").write_text("{}", encoding="utf-8")
        self.assertEqual(self._main("--data-dir", str(empty))[0], 0)
        self.assertFalse((empty / "schema" / "stale.schema.json").exists())

    def test_drift_is_reported_and_check_exits_1(self) -> None:
        status, output = self._main("--check", "--data-dir", str(self.data))
        self.assertEqual(status, 1)
        self.assertIn("missing schema/device.schema.json", output)
        self.sync.sync(MHS_ROOT, self.data)
        (self.data / "schema" / "device.schema.json").write_text("{}", encoding="utf-8")
        (self.data / "schema" / "stale.schema.json").write_text("{}", encoding="utf-8")
        (self.data / "spec" / "errors.json").unlink()
        messages = self.sync.drift(MHS_ROOT, self.data)
        self.assertIn("differs schema/device.schema.json", messages)
        self.assertIn("extra schema/stale.schema.json", messages)
        self.assertIn("missing spec/errors.json", messages)
        status, _ = self._main("--check", "--data-dir", str(self.data))
        self.assertEqual(status, 1)
        # A sync repairs all three, including removing the extra file.
        self.sync.sync(MHS_ROOT, self.data)
        self.assertEqual(self.sync.drift(MHS_ROOT, self.data), [])
        self.assertFalse((self.data / "schema" / "stale.schema.json").exists())

    def test_invalid_source_json_is_a_usage_error(self) -> None:
        root = self.tmp / "MHS"
        shutil.copytree(SCHEMA_DIR, root / "schema", ignore=shutil.ignore_patterns("examples"))
        (root / "spec").mkdir()
        (root / "spec" / "capabilities.json").write_text("{not json", encoding="utf-8")
        (root / "spec" / "errors.json").write_text("{}", encoding="utf-8")
        status, output = self._main("--mhs-root", str(root), "--data-dir", str(self.data))
        self.assertEqual(status, 2)
        self.assertIn("not valid JSON", output)


class SchemaIdCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sync = load_sync_tool()
        self.tmp = Path(tempfile.mkdtemp(prefix="openmhs-ids-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "schema").mkdir()

    def _write(self, name: str, schema_id: str) -> None:
        (self.tmp / "schema" / name).write_text(json.dumps({"$id": schema_id}), encoding="utf-8")

    def test_all_legacy_ids_only_warn(self) -> None:
        self._write("a.schema.json", LEGACY_SCHEMA_PREFIX + "a.schema.json")
        self._write("b.schema.json", LEGACY_SCHEMA_PREFIX + "b.schema.json")
        errors, warnings = self.sync.check_ids(self.tmp, SCHEMA_BASE)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)

    def test_check_activates_once_a_schema_adopts_the_base(self) -> None:
        self._write("a.schema.json", SCHEMA_BASE + "a.schema.json")
        self._write("b.schema.json", LEGACY_SCHEMA_PREFIX + "b.schema.json")
        errors, warnings = self.sync.check_ids(self.tmp, SCHEMA_BASE)
        self.assertEqual(len(errors), 1)
        self.assertIn("b.schema.json", errors[0])
        self.assertEqual(warnings, [])

    def test_all_current_ids_pass_and_names_must_match(self) -> None:
        self._write("a.schema.json", SCHEMA_BASE + "a.schema.json")
        self.assertEqual(self.sync.check_ids(self.tmp, SCHEMA_BASE), ([], []))
        self._write("b.schema.json", SCHEMA_BASE + "other.schema.json")
        errors, _ = self.sync.check_ids(self.tmp, SCHEMA_BASE)
        self.assertEqual(len(errors), 1)
        self.assertIn("does not end with the file name", errors[0])

    def test_strict_flag_enforces_before_adoption(self) -> None:
        self._write("a.schema.json", LEGACY_SCHEMA_PREFIX + "a.schema.json")
        errors, warnings = self.sync.check_ids(self.tmp, SCHEMA_BASE, strict=True)
        self.assertEqual(len(errors), 1)
        self.assertEqual(warnings, [])

    def test_default_base_comes_from_ids(self) -> None:
        self.assertEqual(self.sync.load_ids().SCHEMA_BASE, SCHEMA_BASE)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
