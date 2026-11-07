"""Project identifiers are defined once, in ``mhs._ids``, and used consistently."""

from __future__ import annotations

import re
import unittest
from urllib.parse import urljoin, urlsplit

import mhs
from mhs import _ids

from ._paths import SDK

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    tomllib = None


class IdentifierValuesTests(unittest.TestCase):
    def test_exact_values(self) -> None:
        self.assertEqual(_ids.PROJECT_NAME, "OpenMHS")
        self.assertEqual(_ids.DIST_NAME, "openmhs")
        self.assertEqual(_ids.SPEC_VERSION, "0.9")
        self.assertEqual(_ids.SDK_VERSION, "0.9.0.dev0")
        self.assertEqual(_ids.WIRE_VERSION, "1.0")
        self.assertEqual(_ids.SCHEMA_BASE, "https://mhs.openai4s.org/schema/0.9/")
        # The legacy prefix is spelled only in _ids.py (the one place the old
        # namespace may appear outside appendix D); check its shape instead.
        legacy = urlsplit(_ids.LEGACY_SCHEMA_PREFIX)
        self.assertEqual((legacy.scheme, legacy.path), ("https", "/schema/"))
        self.assertNotEqual(legacy.hostname, urlsplit(_ids.SCHEMA_BASE).hostname)
        self.assertEqual(_ids.REGISTRY_ID, "openmhs-registry")
        self.assertEqual(_ids.ADAPTER_ID_PREFIX, "openmhs:")

    def test_previous_schema_namespace_still_resolves(self) -> None:
        from mhs.schema import default_store
        store = default_store()
        current = store.resolve_public(_ids.SCHEMA_BASE + "device.schema.json")
        previous = store.resolve_public(_ids.PLACEHOLDER_SCHEMA_PREFIX + "device.schema.json")
        self.assertEqual(previous, current)
        self.assertEqual(_ids.SITE_URL, "https://mhs.openai4s.org")

    def test_module_defines_only_the_identifiers(self) -> None:
        public = {name for name in vars(_ids) if name.isupper()}
        self.assertEqual(public, set(_ids.__all__))

    def test_schema_base_supports_relative_refs(self) -> None:
        # Schemas use relative $ref, so the base must be a hierarchical URL.
        self.assertTrue(_ids.SCHEMA_BASE.startswith("https://"))
        self.assertTrue(_ids.SCHEMA_BASE.endswith("/"))
        self.assertEqual(
            urljoin(_ids.SCHEMA_BASE + "device.schema.json", "defs.schema.json"),
            _ids.SCHEMA_BASE + "defs.schema.json",
        )

    def test_non_affiliation_is_one_complete_sentence(self) -> None:
        text = _ids.NON_AFFILIATION
        self.assertTrue(text.startswith("OpenMHS is an independent open-source project"))
        self.assertTrue(text.endswith("."))
        self.assertEqual(text.count(". "), 0, "one sentence only")
        for phrase in ("not affiliated with", "endorsed by Anthropic",
                       "reimplementation", "compatible dialect", "research preview"):
            self.assertIn(phrase, text)
        self.assertNotIn("\n", text)

    def test_package_version_comes_from_ids(self) -> None:
        self.assertEqual(mhs.__version__, _ids.SDK_VERSION)
        self.assertIn("__version__", mhs.__all__)


@unittest.skipIf(tomllib is None, "tomllib needs Python 3.11+")
class PyprojectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pyproject = tomllib.loads((SDK / "pyproject.toml").read_text(encoding="utf-8"))
        cls.project = cls.pyproject["project"]

    def test_name_and_version_match_ids(self) -> None:
        self.assertEqual(self.project["name"], _ids.DIST_NAME)
        self.assertEqual(self.project["version"], _ids.SDK_VERSION)

    def test_licence_is_spdx_with_files(self) -> None:
        self.assertEqual(self.project["license"], "MIT")
        self.assertEqual(self.project["license-files"], ["LICENSE", "NOTICE"])
        requirement = self.pyproject["build-system"]["requires"][0]
        match = re.fullmatch(r"setuptools>=(\d+)", requirement)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 77, "PEP 639 licence fields need setuptools 77")

    def test_alpha_classifier_and_description(self) -> None:
        self.assertIn("Development Status :: 3 - Alpha", self.project["classifiers"])
        self.assertIn("Model Hardware Standard", self.project["description"])
        self.assertEqual(self.project["dependencies"], [])

    def test_console_scripts(self) -> None:
        self.assertEqual(
            self.project["scripts"], {"mhs": "mhs.cli:main", "openmhs": "mhs.cli:main"}
        )

    def test_package_data_is_frozen(self) -> None:
        self.assertEqual(
            self.pyproject["tool"]["setuptools"]["package-data"]["mhs"],
            ["_data/**/*", "conformance/*.json", "driver/templates/**/*"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
