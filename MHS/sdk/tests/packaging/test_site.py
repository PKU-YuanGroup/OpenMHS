"""The site generator and its checker: the ``--site-url`` rules, the class-status text and the staleness inputs."""

import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]


def load_module(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


def load_build():
    return load_module("openmhs_site_build_under_test", "MHS/site/build.py")


class SiteUrlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.normalize = staticmethod(load_build().normalize_site_url)

    def test_valid_origins_lose_only_the_trailing_slash(self):
        self.assertEqual(self.normalize("https://example.invalid/"), "https://example.invalid")
        self.assertEqual(self.normalize("http://127.0.0.1:8080/"), "http://127.0.0.1:8080")
        self.assertEqual(self.normalize("http://[::1]:8000/docs/"), "http://[::1]:8000/docs")
        self.assertEqual(self.normalize("  "), "")

    def test_hosts_with_whitespace_or_odd_characters_are_refused(self):
        for bad in ("https://a b", "https://exa mple.org", "https://ex$ample.org", "https://exa\tmple.org"):
            with self.subTest(bad), self.assertRaises(SystemExit):
                self.normalize(bad)

    def test_credentials_queries_and_other_schemes_are_refused(self):
        for bad in ("https://user@host.example/", "https://u:p@host.example/", "https://host.example/?x=1",
                    "https://host.example/#frag", "ftp://host.example/", "host.example"):
            with self.subTest(bad), self.assertRaises(SystemExit):
                self.normalize(bad)


class LeadDescriptionTests(unittest.TestCase):
    def test_search_descriptions_preserve_identifiers_and_literal_code(self):
        build = load_build()
        document = (REPO / "MHS/sdk/docs/ros-pointcloud-artifacts.md").read_text()
        self.assertIn("cap.sensing.point_cloud.v1", build.extract_lead(document))
        self.assertNotIn("cap.sensing.pointcloud.v1", build.extract_lead(document))
        for body, expected in [
            ("Use `cap.motion.joint_position.v1` with **bold** and _emphasis_.",
             "Use cap.motion.joint_position.v1 with bold and emphasis."),
            ("Keep `a_b*c` and [`named_value`](guide.md).", "Keep a_b*c and named_value."),
        ]:
            with self.subTest(body=body):
                self.assertEqual(build.extract_lead("# Example\n\n" + body + "\n"), expected)


class MarkdownFenceTests(unittest.TestCase):
    """A fence with attributes after the language ("```json validate=x.schema.json") is a code block, not a paragraph."""

    @classmethod
    def setUpClass(cls):
        cls.build = load_build()

    def render(self, text):
        renderer = self.build.MarkdownRenderer(set(), "MHS/spec/x.md", "spec/x.html")
        html, _toc = renderer.render(text, skip_first_h1=False)
        return html

    def test_a_fence_with_attributes_does_not_swallow_the_headings_after_it(self):
        html = self.render("# T\n\n## 1. Before\n\n```json validate=adapter.schema.json\n{\"a\": 1}\n```\n\n## 2. After\n\ntext\n\n"
                           "```python\nx = 1\n```\n\n## 3. Last\n")
        for heading in ("1-before", "2-after", "3-last"):
            self.assertIn(f'id="{heading}"', html)
        self.assertEqual(html.count('class="codeblock"'), 2)
        self.assertIn('data-lang="json"', html)
        self.assertNotIn("validate=", html, "the attributes are for the doctest tool and are not shown")

    def test_a_closing_fence_with_text_does_not_close_the_block(self):
        html = self.render("```text\nline\n```not a closer\nstill code\n```\n\nafter\n")
        self.assertEqual(html.count('class="codeblock"'), 1)
        self.assertIn("still code", html)
        self.assertIn("<p>after</p>", html)

    def test_plain_and_tilde_fences_still_work(self):
        html = self.render("```\nplain\n```\n\n~~~sh\nls\n~~~\n")
        self.assertEqual(html.count('class="codeblock"'), 2)


class SplitDocumentTests(unittest.TestCase):
    """A long specification chapter is published in two pages; the heading that starts part 2 must still exist."""

    @classmethod
    def setUpClass(cls):
        cls.build = load_build()

    def test_every_split_marker_is_in_the_chapter_it_splits(self):
        for rel, (marker, labels) in self.build.SPLIT_DOCS.items():
            text = (REPO / "MHS/spec" / rel).read_text(encoding="utf-8")
            with self.subTest(rel):
                self.assertEqual(text.count("\n" + marker), 1, f"{marker!r} must open exactly one section of {rel}")
                self.assertEqual(len(labels), 2)

    def test_the_real_documents_come_out_in_two_parts_and_nothing_is_lost(self):
        docs = self.build.discover_docs()
        parts = self.build.build_doc_parts(docs)
        for rel in self.build.SPLIT_DOCS:
            mine = [part for part in parts if part.doc.rel == rel]
            with self.subTest(rel):
                self.assertEqual([part.number for part in mine], [1, 2])
                self.assertTrue(mine[1].output.endswith("-part-2.html"))
                self.assertEqual((mine[0].body + mine[1].body).replace("\n", ""), mine[0].doc.body.replace("\n", ""))


class ClassStatusTests(unittest.TestCase):
    """The status of a capability class is published as the catalogue states it, never as a fixed phrase."""

    @classmethod
    def setUpClass(cls):
        cls.build = load_build()
        cls.caps = cls.build.load_capabilities()

    def test_counts_add_up_to_the_catalogue(self):
        counts = self.caps.status_counts
        self.assertEqual(sum(counts.values()), self.caps.count)
        data = json.loads((REPO / "MHS/spec/capabilities.json").read_text(encoding="utf-8"))
        expected = {}
        for item in data["capabilities"]:
            expected[item["status"]] = expected.get(item["status"], 0) + 1
        self.assertEqual(counts, expected)

    def test_only_classes_that_are_not_stable_carry_a_badge(self):
        for cap in self.caps.items:
            card = self.build.capability_card(cap)
            with self.subTest(cap["_slug"]):
                if cap["_status"] == "stable":
                    self.assertNotIn('class="badge', card)
                else:
                    self.assertIn(f'>{cap["_status"]}</span>', card)
                self.assertIn(cap["_status"], card.split('data-search="', 1)[1].split('"', 1)[0].split())

    def test_the_summary_states_the_real_split(self):
        counts = self.caps.status_counts
        note = self.build.class_status_summary(self.caps)
        for status, number in counts.items():
            self.assertIn(f"{number} <code>{status}</code>", note)
        self.assertLess(note.index("<code>stable</code>"), note.index("<code>deprecated</code>"))

    def test_an_unknown_status_is_listed_not_dropped_and_an_empty_catalogue_says_so(self):
        odd = types.SimpleNamespace(status_counts={"stable": 2, "sunset": 1, "experimental": 1})
        self.assertEqual(self.build.class_status_summary(odd),
                         "2 <code>stable</code>, 1 <code>experimental</code>, 1 <code>sunset</code>")
        self.assertEqual(self.build.class_status_summary(types.SimpleNamespace(status_counts={})), "none are recorded")


class StalenessInputTests(unittest.TestCase):
    """``check.py --fresh`` compares these files with the digests recorded by the build."""

    @classmethod
    def setUpClass(cls):
        cls.build = load_build()

    def test_page_sources_cover_what_the_pages_are_rendered_from(self):
        listed = {path.relative_to(REPO).as_posix() for path in self.build.page_source_paths()}
        for expected in ("MHS/spec/00-architecture.md", "MHS/spec/core.md", "MHS/sdk/README.md", "MHS/sdk/docs/driver-authoring.md",
                         "MHS/conformance/reports/conveyor-cl4.json", "MHS/site/build.py", "MHS/site/assets/style.css",
                         "integration/openai4s/DESIGN.md"):
            with self.subTest(expected):
                self.assertIn(expected, listed)
        self.assertFalse([name for name in listed if "_site/" in name or "__pycache__" in name or name.startswith(("labs/", "robots/", "work/"))])

    def test_spec_example_ids_are_the_two_the_text_cites(self):
        check = load_module("openmhs_site_check_under_test", "MHS/site/check.py")
        self.assertEqual(check.SPEC_EXAMPLE_IDS, {"cap.motion.move.v1", "cap.fluid.aspirate.v2"})
        catalogue = {item["capability_id"] for item in json.loads((REPO / "MHS/spec/capabilities.json").read_text(encoding="utf-8"))["capabilities"]}
        self.assertFalse(check.SPEC_EXAMPLE_IDS & catalogue, "an example id that became a real class no longer needs the exemption")


if __name__ == "__main__":
    unittest.main()
