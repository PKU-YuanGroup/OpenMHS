"""Registry loading, filtering and PackageRecord accessors."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from mhs.registry import PackageRecord, Registry, load_registry

REPO = Path(__file__).resolve().parents[4]


class RepositoryRegistryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry.load(REPO / "MHS" / "registry")

    def test_loads_index(self):
        self.assertGreater(len(self.registry), 100)
        self.assertIsInstance(self.registry.packages[0], PackageRecord)
        self.assertTrue(self.registry.generated_at)
        self.assertEqual(self.registry.stats.get("total"), len(self.registry))

    def test_loads_the_record_files_without_the_aggregates(self):
        # index.json / index.jsonl / records.csv are git-ignored build outputs
        repos = Registry.load(REPO / "MHS" / "registry" / "repos")
        self.assertEqual(len(repos), len(self.registry))
        self.assertTrue(repos.generated_at)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "repos" / "labs").mkdir(parents=True)
            (root / "tasks" / "labs").mkdir(parents=True)
            (root / "repos" / "labs" / "a__b.json").write_text(json.dumps({
                "record_type": "package", "package_id": "gh.a/b", "updated_at": "2026-10-20T00:00:00Z"}),
                encoding="utf-8")
            (root / "tasks" / "labs" / "a__b.json").write_text(json.dumps({
                "card_version": "0.9", "package_id": "gh.a/b"}), encoding="utf-8")
            loaded = Registry.load(root)
            self.assertEqual(len(loaded), 1)   # the task card is not a second record
            self.assertEqual(loaded.generated_at, "2026-10-20T00:00:00Z")

    def test_get_and_accessors(self):
        record = self.registry.get("gh.7jameslondon/magscope")
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.package_id, "gh.7jameslondon/magscope")
        self.assertIsInstance(record.family, str)
        self.assertTrue(record.family)
        self.assertIn("Python", record.languages)
        self.assertTrue(record.capabilities)
        self.assertTrue(all(c.startswith("cap.") for c in record.capabilities))
        # skeleton manifests are archived: no record points at one
        self.assertFalse(record.has_manifest)
        self.assertIsNone(record.manifest_ref)
        # The adapter state follows the package of the record: magscope got a passing one in wave B.
        result = REPO / "MHS" / "drivers" / "labs" / "7jameslondon__magscope" / "RESULT.json"
        passed = result.is_file() and json.loads(result.read_text(encoding="utf-8")).get("status") == "pass"
        self.assertEqual(record.adapter_state, "runnable" if passed else "none")
        self.assertIn("simulated", record.modes)
        self.assertEqual(record.modes[0], "hardware")   # hardware first for a dual-mode package
        self.assertIsNone(self.registry.get("gh.does/not-exist"))

    def test_integration_fields(self):
        record = self.registry.get("gh.tiagocoutinho/julabo")
        assert record is not None
        self.assertEqual(record.strategy, "direct-driver")
        self.assertEqual(record.role, "device-driver")
        self.assertEqual(record.wave, 0)
        self.assertIsInstance(record.rank, int)
        self.assertEqual(record.blocked_on, [])
        self.assertFalse(record.quarantine)
        self.assertIsNone(record.variant_of)
        self.assertRegex(record.source_commit or "", r"^[0-9a-f]{40}$")
        self.assertTrue(record.license_spdx)
        self.assertIn(record.license_class, ("permissive", "weak-copyleft", "copyleft", "network-copyleft",
                                             "source-available", "proprietary", "unknown"))
        self.assertEqual(record.task_card, "tasks/labs/tiagocoutinho__julabo.json")
        # Its driver package (MHS/drivers/labs/tiagocoutinho__julabo) passed the gate: a passing package is
        # maintained, not dispatched again.  An exemplar whose package does not exist yet is still dispatched.
        self.assertEqual(record.evidence_state, "contract_checked")
        self.assertFalse(record.dispatchable)
        summary = record.summary()
        self.assertEqual(summary["strategy"], "direct-driver")
        self.assertEqual(summary["wave"], 0)
        exemplars = ["gh.farama-foundation/gymnasium", "gh.thinksrs/srsinst.sr860", "gh.tiagocoutinho/julabo",
                     "gh.xarm-developer/xarm-python-sdk"]
        queue = self.registry.search(dispatchable=True, wave=0)
        self.assertEqual(sorted(r.package_id for r in queue), sorted(
            pid for pid in exemplars if self.registry.get(pid).evidence_state != "contract_checked"))
        self.assertEqual(self.registry.get("gh.thinksrs/srsinst.sr860").evidence_state, "contract_checked")
        skipped = self.registry.search(strategy="skip", limit=5)
        self.assertTrue(skipped)
        self.assertTrue(all(not r.dispatchable for r in skipped))
        self.assertGreater(self.registry.stats.get("total", 0), 0)

    def test_search_by_capability_and_filters(self):
        hits = self.registry.search(capability="cap.thermal.setpoint.v1", limit=10)
        self.assertTrue(hits)
        self.assertTrue(all("cap.thermal.setpoint.v1" in hit.capabilities for hit in hits))
        self.assertLessEqual(len(hits), 10)
        for hit in hits:
            self.assertIsInstance(hit, PackageRecord)
            self.assertTrue(hit.offers_capability("cap.thermal.setpoint.v1"))

        families = self.registry.search(family="gymnasium", limit=5)
        self.assertTrue(families)
        self.assertTrue(all("gymnasium" in item.families for item in families))

        both = self.registry.search(family="gymnasium", mode="simulated", track="labs", limit=5)
        for item in both:
            self.assertEqual(item.track, "labs")
            self.assertIn("simulated", item.modes)

        self.assertEqual(self.registry.search(query="no-such-package-xyzzy"), [])
        self.assertTrue(self.registry.search(query="microscope", limit=5))

    def test_summary_is_jsonable(self):
        record = self.registry.packages[0]
        summary = record.summary()
        json.dumps(summary)
        self.assertEqual(summary["package_id"], record.package_id)
        self.assertIn("families", summary)
        self.assertEqual(json.loads(json.dumps(record.to_dict())), record.to_dict())

    def test_default_discovery(self):
        self.assertGreater(len(load_registry()), 0)


class SyntheticRegistryTest(unittest.TestCase):
    def _record(self, **overrides):
        record = {
            "record_type": "package",
            "package_id": "gh.example/arm",
            "repo_url": "https://github.com/example/arm",
            "track": "robots",
            "owner": "example",
            "repo": "arm",
            "title": "Example arm",
            "description": "A robot arm for tests",
            "families": ["python-object"],
            "tier": "A",
            "ring": 1,
            "modes": ["simulated"],
            "capabilities_offered": ["cap.motion.joint_position.v1"],
            "adapter": {"state": "runnable", "bridge": "python-object"},
            "evidence": {"state": "runtime_tested", "read_by": "runtime"},
            "license": "MIT",
            "simulation": True,
        }
        record.update(overrides)
        return record

    def test_jsonl_and_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "index.jsonl").write_text(
                json.dumps(self._record()) + "\n" + json.dumps(self._record(package_id="gh.example/two")),
                encoding="utf-8",
            )
            registry = Registry.load(root)
            self.assertEqual(len(registry), 2)

            records_dir = root / "records"
            records_dir.mkdir()
            (records_dir / "one.json").write_text(json.dumps(self._record()), encoding="utf-8")
            registry2 = Registry.load(records_dir)
            self.assertEqual(len(registry2), 1)
            self.assertEqual(registry2.get("gh.example/arm").tier, "A")

    def test_csv_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.csv"
            path.write_text(
                "package_id,track,owner,repo,tier,ring,modes,interfaces,license,repo_url\n"
                "gh.example/arm,robots,example,arm,A,1,simulated|hardware,CLI,MIT,https://example\n",
                encoding="utf-8",
            )
            registry = Registry.load(path)
            record = registry.get("gh.example/arm")
            self.assertIsNotNone(record)
            assert record is not None
            self.assertEqual(record.modes, ["simulated", "hardware"])
            self.assertEqual(record.ring, 1)

    def test_integration_accessors_on_full_records_and_projections(self):
        full = PackageRecord(self._record(integration={"strategy": "family-config", "role": "sim-env",
                                                       "reason_code": "family:gymnasium"},
                                          blocked_on=[], wave=2, rank=5, quarantine=False,
                                          adapter={"state": "none", "bridge": "gymnasium"},
                                          source={"repo_url": "https://github.com/example/arm", "commit": "a" * 40}))
        self.assertEqual((full.strategy, full.role, full.reason_code), ("family-config", "sim-env", "family:gymnasium"))
        self.assertEqual((full.wave, full.rank, full.source_commit), (2, 5, "a" * 40))
        self.assertTrue(full.dispatchable)
        self.assertTrue(full.matches(strategy="family-config", wave=2, dispatchable=True))
        self.assertFalse(full.matches(wave=3))
        blocked = PackageRecord(self._record(integration={"strategy": "family-config"}, blocked_on=["helper:ros"]))
        self.assertFalse(blocked.dispatchable)
        # a driver package that passed the gate (adapter state runnable) is not dispatched again
        done = PackageRecord(self._record(integration={"strategy": "family-config"}, blocked_on=[]))
        self.assertEqual(done.adapter_state, "runnable")
        self.assertFalse(done.dispatchable)
        self.assertTrue(PackageRecord(self._record(integration={"strategy": "family-config"}, blocked_on=[],
                                                   adapter={"state": "packaged"})).dispatchable)
        self.assertFalse(blocked.matches(dispatchable=True))
        projection = PackageRecord({"package_id": "gh.example/arm", "strategy": "skip", "commit": "b" * 40,
                                    "task_card": "tasks/robots/example__arm.json", "quarantine": True})
        self.assertEqual(projection.strategy, "skip")
        self.assertEqual(projection.source_commit, "b" * 40)
        self.assertEqual(projection.task_card, "tasks/robots/example__arm.json")
        self.assertFalse(projection.dispatchable)

    def test_csv_integration_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "records.csv"
            path.write_text("package_id,track,strategy,wave,rank,blocked_on,quarantine,variant_of\n"
                            "gh.example/arm,robots,family-config,5,3,helper:ros,false,\n", encoding="utf-8")
            record = Registry.load(path).get("gh.example/arm")
            assert record is not None
            self.assertEqual((record.wave, record.rank, record.blocked_on), (5, 3, ["helper:ros"]))
            self.assertFalse(record.quarantine)
            self.assertIsNone(record.variant_of)

    def test_matches_query_and_glob(self):
        record = PackageRecord(self._record())
        self.assertTrue(record.matches(query="robot", capability="cap.motion.*"))
        self.assertTrue(record.matches(capability="cap.motion"))
        self.assertFalse(record.matches(capability="cap.optics.*"))
        self.assertFalse(record.matches(mode="hardware"))
        self.assertTrue(record.matches(mode="simulated", tier=("A", "B")))
        self.assertFalse(record.matches(tier=("C",)))


if __name__ == "__main__":
    unittest.main()
