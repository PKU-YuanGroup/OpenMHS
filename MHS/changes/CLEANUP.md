# CLEANUP — final clean-up of the site, the generated data and the leftovers of earlier steps

Written by the orchestrator after the exemplar drivers, the handoff kit and the archive step. It closes the follow-ups that the
earlier steps assigned to "final cleanup": the site no longer states a class status that the catalogue contradicts, its checker
notices a stale build of any page and not only of a download, the Pages template works in a clean clone, and the sync tool
refuses to prune a directory it did not create.

## What changed

- **Class status on the site is the catalogue's.** The governance page said "no capability class is currently deprecated; all
  classes are `active`", but `MHS/spec/capabilities.json` has 44 `stable`, 13 `experimental` and 6 `deprecated` classes (the six
  duplicate a protocol method and stay valid). The sentence is now produced from the catalogue (`class_status_summary`), cards of
  classes that are not stable carry a badge, and the status is part of the catalogue filter. The download page no longer says "62
  classes" by hand (the catalogue has 63).
- **`check.py --fresh` covers the pages, not only the downloads.** The download manifest gains `page_sources`: the digests of the
  specification text, the SDK guides, the published conformance reports, the site assets and deploy files, the host design
  document and `build.py` itself (`page_source_paths()`). A site built before any of them changed is stale: a warning, or an error
  with `--fresh`. The gate was seen to work while this fragment was written: a build made a few minutes earlier failed `--fresh`
  because the specification text had been edited since.
- **The capability-id gate no longer skips the specification pages.** It scans them too and allows exactly the two ids the text
  cites on purpose (`SPEC_EXAMPLE_IDS`: `cap.motion.move.v1`, a forbidden example, and `cap.fluid.aspirate.v2`). Any other unknown
  id on any page is an error.
- **`--site-url`** refuses a host with whitespace or characters outside a host name, and credentials in the URL; IPv6 literals
  such as `http://[::1]:8000/` are accepted.
- **GitHub Pages template.** `deploy/.github/workflows/pages.yml` now builds the registry aggregates first (`index.json`,
  `index.jsonl` and `records.csv` are git-ignored, so a clean clone has none and `build.py --release` would have failed), and its
  `paths` filter includes `LICENSE`, `LICENSE-docs`, `NOTICE` and the host design document that the site reads. The deploy and site
  READMEs say so.
- **The site follows the realigned specification (WP-09).** The document map gains the core, the driver profile and the optional
  profiles, and the home, specification, governance and about pages state the new precedence (schemas, core, driver profile,
  chapters, appendices; the architecture overview is informative) instead of "MHS-000 wins". The markdown renderer accepts a fence
  with attributes after the language (` ```json validate=adapter.schema.json `, the form the doctest tool reads): the old pattern
  took such a line for a paragraph and the next closing fence for an opener, so whole sections (9.3 to 10 of the architecture
  overview, 12 of the wire protocol) were rendered inside a code block. `SPLIT_DOCS` publishes the architecture overview in two
  pages, like the capability registry, because it grew past the checker's 100 KiB page budget; three hard-coded links were
  re-pointed to the renamed and moved sections.
- **The open-source export runs the suites.** `tools/oss_export_check.py` (without `--skip-suites`) runs the SDK, registry, site and
  integration suites inside the clean export; it found that `test_published_reports` required the private `_archive/` directory.
  The assertion about the archive now applies only when the directory exists.
- **`sync_data.py`** only prunes a data directory it created (a `.openmhs-data` marker is written after a sync); anything else is
  refused with exit 2 instead of being emptied.
- **`reference.schema.json`**: `measures[].inputs` items are optional parameters; `required: true` and a `limit` member are
  rejected, with an invalid example and an `expected-failures.json` entry.
- **Driver gate G4 reads `2 * math.pi`** and the other radian expressions that robot SDKs use for joint ranges
  (`mhs.driver.check._numbers_in`), found while the xArm exemplar was checked.

## Follow-ups that were checked and need nothing

Every item the earlier steps filed under "final cleanup" or "leftover minors" was compared with the tree. Already done in the
step that filed it: the WP-03 limits overlay order, units overflow, canonical bounds, drift through `$ref`/`allOf`, measures that
keep their inputs and the overlay record (see `WP-03.md`, "Leftover minors fixed"); the WP-10 residuals (hardware first, teaching
repositories, the false Tecan partner, `agx`, the pilot shortfall, the strict spot-check rate, entry-class ranking, generic
transports, the corpus-lock parent work tree; see `MERGE-C2.md` and `WP-10.md`); the pass-through of `PYTHONDONTWRITEBYTECODE` to
the connector child process (`mcp_invoke._CONNECTOR_ENV`, `mcpconfig`).

## Tests

- `MHS/sdk/tests/packaging/test_site.py` (new, 14 tests): the `--site-url` rules, the class-status text and badges derived from
  the catalogue, the page sources the staleness gate records, the two example ids, fences with attributes, and the split
  documents (every split marker still opens a section of its chapter).
- `MHS/sdk/tests/packaging/test_sync_data.py`: the marker guard.
- `MHS/sdk/tests/driver/test_ref_values.py`: the π expressions.
