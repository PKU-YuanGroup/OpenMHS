"""README.md and coverage.md of the OpenMHS registry (deterministic; every number is computed)."""

from __future__ import annotations

import os
import re
import sys
from collections import Counter

import recipes as RECIPES
import taskcards as TC
import triage as T

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sdk", "src"))
from mhs import _ids  # noqa: E402


def spotcheck_summary(path=None):
    """'<cards> cards in <samples> samples' read from ``tasks/SPOTCHECK.md`` (the same round headings and verdict
    rows ``tests/test_shipped_registry.py`` counts), so the README never goes stale against the file."""
    path = path or os.path.join(TC.TASKS_DIR, "SPOTCHECK.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return "a reviewer's verdicts on random cards (`spotcheck.py`)"
    parts = re.split(r"^## Round \d+ \(seed \d+, [a-z ]+\)$", text, flags=re.MULTILINE)[1:]
    cards = sum(len(re.findall(r"^\| *\d+ *\| *`gh\.[^`]+` *\|.*\| *(?:correct|debatable|\*\*wrong\*\*) *\|",
                               body.split("\n## ", 1)[0], re.MULTILINE)) for body in parts)
    return f"a reviewer's verdicts on {cards} random cards in {len(parts)} samples (`spotcheck.py`)"


def _table(rows, headers):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def render_readme(records, cards, summary, stats, uncloned, manifest, build_ts, decisions_summary) -> str:
    total = len(records)
    waves = summary["by_wave"]
    lines = [_ids.NON_AFFILIATION, "", "# OpenMHS registry", "",
             f"Generated **{build_ts}** by `MHS/registry/build_registry.py` (registry version "
             f"{manifest['registry_version']}, publisher id `{manifest['registry_id']}`). Stdlib only, offline and "
             "deterministic: a rebuild from the same inputs is byte-identical (`MHS_REGISTRY_DATE` sets the date; "
             "`SOURCE_DATE_EPOCH` is ignored).", "",
             f"The registry has one record and one task card for each of the **{total}** upstream clones of the "
             "OpenAI4S corpus. The record is the catalogue entry (what the repo is, how it is integrated, which "
             "commit and licence); the task card is the unit of work for a driver author, human or model. Nothing "
             "here was installed or run; evidence states say how much was checked.", "",
             "## Files", "",
             _table([
                 ("`repos/<track>/<owner>__<repo>.json`", f"registry record ({total}), `MHS/schema/registry-record.schema.json`"),
                 ("`tasks/<track>/<owner>__<repo>.json`", f"task card ({len(cards)}), `schema/taskcard.schema.json`"),
                 ("`tasks/pilot-candidates.json`", "the pilot pool: top-ranked cards per bucket for `MHS/handoff/pilot-20.json`"),
                 ("`tasks/SPOTCHECK.md`", spotcheck_summary()),
                 ("`families/<family>.md`", "one recipe per family: bridge_status, launch line, capability mapping"),
                 ("`overrides/*.json`", "curated triage decisions (`schema/overrides.schema.json`); read, never written"),
                 ("`corpus.lock.jsonl`", "git remote and HEAD of every clone (`corpus_lock.py`)"),
                 ("`uncloned.json`", "catalogue rows without a local clone"),
                 ("`coverage.md`", "counts by decision, wave, family, licence and evidence"),
                 ("`index.json`, `index.jsonl`, `records.csv`", "aggregates built by `build_index.py`; git-ignored"),
             ], ["Path", "Content"]), "",
             "Archived: the 1,967 skeleton adapter manifests of the 1.0 registry are in "
             f"`{manifest['archived_manifests']}/` (moved, not deleted); records carry `adapter.manifest_ref: null`.",
             "", "## Pipeline", "",
             "1. `scan_corpus.py` and the catalogue classify each clone (catalogue family and tier).",
             "2. `source_scan.py` parses the clone's Python with `ast` (nothing is imported or executed): device "
             "classes, gym registrations, licence file, packaging metadata, mocks and limit-like constants.",
             "3. `triage.py` applies the eleven ordered rules (first match wins); `overrides/*.json` win over the rules.",
             "4. `licenses.py` resolves `license_spdx` (catalogue, then the LICENSE file, then packaging metadata) "
             "and `license_class`. A LICENSE file is identified by the title, grant or SPDX id that comes first in "
             "its head, so a licence named further down (a GPL-3.0 section on the Affero GPL, a bundle's "
             "components) never decides; an EULA or an all-rights-reserved file is proprietary.",
             "5. `overlays.py` reads `MHS/drivers/<track>/<owner>__<repo>/` (driver.lock.json, RESULT.json, "
             "check-report.json) as evidence; it never writes there.",
             "6. `taskcards.py` writes the cards, the waves and the ranks; `recipes.py` and `docs.py` write the "
             "recipes and this file; `build_index.py` writes the aggregates.", "",
             "## Triage rules", "",
             "1. tier X or an empty clone: `skip:empty`",
             "2. no source code, an analyst docs-only flag the scan confirms, a curated list, a course or tutorial: "
             "`skip:not-device`",
             "3. a download lure or binary-only installer: `skip:quarantine` (`quarantine` is set whatever rule decides)",
             "4. an earlier MHS implementation: `reference:prior-art`",
             "5. a fork or duplicate of another corpus repo: `skip:duplicate_of` with `variant_of`",
             "6. a protocol stack, framework or engine behind a helper: `bridge-runtime:<family|engine>`",
             "7. an orchestrator, host or MCP wrapper of a covered backend: `reference:host`; tooling: `skip:tooling`",
             "8. tier D (peripheral, not a device): `skip:peripheral`; a catalogue software row counts as tier D "
             "only when the code shows no device evidence, no driver directory (`hal/`, `drivers/`, `hardware/` ...) "
             "and no device-named class. When the catalogue calls a repo a model or a simulation (measurement "
             "model, task environment, direct simulation backend, digital twin), device evidence also needs a class "
             "that uses a hardware transport (serial, VISA, USB, fieldbus, a vendor SDK)",
             "9. a family with a helper plus a structural marker (import, package.xml, gym registration, MJCF): "
             "`family:<family>` (family-config); gym envs that need an external simulator (Isaac, CARLA, AirSim, "
             "Newton, Gazebo world files or plugins ...) have no helper and fall through. Gym registrations and "
             "MJCF files under examples, tests, docs, fixtures or vendored trees are no marker; the MuJoCo marker "
             "is a loadable scene or robot model with actuators (object and fixture assets, fragments and "
             "templates alone are none); a GUI application without a device class takes no protocol family",
             "10. Python code with an AST device entry class (score at least 9 with three API members, or the "
             "transport-using class of a catalogue device SDK; simulators, mocks and dummies of the device never "
             "count): `PY_SDK_WITH_ENTRY` (direct-driver)",
             "11. everything else: `untriaged:<why>` (a recon-only card)", "",
             "Simulator families come only from structural markers in the code. Pilot helpers are available "
             "(PythonObjectDriver, SerialDriver, ScpiDriver, GymnasiumDriver, MujocoDriver); every other family "
             "waits for a post-pilot helper and its cards carry `blocked_on: helper:<name>`.", "",
             "## Task cards and waves", "",
             "A card is dispatched only when `decision` is direct-driver or family-config, `helper_status` is "
             "available, `blocked_on` is empty, `quarantine` is false and `package_status` is none or in_progress "
             "(a driver package whose RESULT.json passed is maintained, not dispatched again). A python-object card "
             "with neither an entry symbol nor candidate classes (a serial or SCPI card: nor an install file) is "
             "blocked on `recon:entry_symbol` (wave 4). Entry "
             "symbols come from the AST scan with file and line: `ast` when the class definition is in the clone, "
             "`recon` for a gym registration whose class is not defined in the clone. Simulator cards list the "
             "package's gym registrations, else (sim-env cards) its environment classes, while a twin candidate's "
             "entry is its model; device cards list device classes, never GUI widgets and never "
             "a simulator, mock or dummy of the device when a real class exists (those go to `mock_strategy`). "
             "MuJoCo cards name the models a MujocoDriver loads in `models` (`{file, line, kind}`, the main scene "
             "or robot model first); a MuJoCo card without one carries `needs_recon: model`. `needs_recon` also "
             "flags `artifacts` (the README downloads assets, models or LFS objects the clone does not hold), "
             "`motion` (a robot hardware card whose motion API was not found) and `mode` (a recon card of a "
             "simulation repo whose code also drives hardware; the recon decides which mode the driver serves). "
             "Install commands appear only "
             "when a root file backs them, and `install.system_deps` names software pip does not install that the "
             "package code imports (mujoco-py's MuJoCo 2.1 binaries); `safety.risk_floor` is the highest catalogue risk class of the candidate "
             "classes. Hints are suggestions, never a specification. Pilot candidates also need an `ast` entry "
             "symbol (or, for MuJoCo, a main model), candidate classes, no system dependency and no `artifacts` or "
             "`motion` flag; a bucket served by two helpers takes its cards from both families in turn.",
             "", _table([(w, text, waves.get(str(w), 0)) for w, text in TC.WAVES.items()], ["wave", "meaning", "cards"]),
             "", "Rank within a wave (published and deterministic):", "", "```", TC.RANK_FORMULA, "```", "",
             "## Records", "",
             "- `integration.strategy`, `integration.role` and `integration.reason_code` come from triage; "
             "`blocked_on`, `wave` and `rank` from the card; `quarantine` and `variant_of` from triage.",
             "- `repo_url` and `source{repo_url, commit}` come from the clone's git remote and HEAD "
             "(`corpus.lock.jsonl`); a different catalogue URL is kept in `x-vendor.catalog.repo_url`.",
             "- `license` and `license_spdx` are SPDX expressions; `license_class` is permissive, weak-copyleft, "
             "copyleft, network-copyleft, source-available (SSPL, PolyForm, BUSL, non-commercial), proprietary or "
             "unknown. The catalogue's own text stays in `x-vendor.catalog.license_raw`.",
             "- `modes` lists hardware first. A dual-mode repo plans a hardware device plus a simulated device that "
             "names it in `models` (`x-vendor.device_plan`). Tier D and X records have no modes.",
             "- English fields contain no Chinese text; the catalogue originals stay in `x-vendor`.",
             "- `capabilities_offered` are the card's candidate classes (code-derived suggestions, empty for tier D/X).",
             "- Evidence ladder: `declared` < `static_scan` < `agent_read` < `contract_checked` (a driver package "
             "passed the gate on a fake or simulated backend) < `hardware_checked` (an operator-run hardware check). "
             "Ring 0 needs hardware_checked, ring 1 contract_checked, ring 2 a dispatchable card, ring 3 the rest.",
             "", "## Regenerate and check", "", "```sh",
             "python3 MHS/registry/build_registry.py --jobs 8      # records, cards, recipes, docs, aggregates",
             "python3 MHS/registry/build_registry.py --check       # exit 1 when a committed file is stale",
             "python3 MHS/registry/build_index.py                  # aggregates only, no corpus needed",
             "python3 MHS/registry/validate.py --no-corpus         # everything that needs only MHS/",
             "python3 MHS/registry/validate.py                     # plus clone and entry-symbol checks",
             "python3 MHS/registry/triage.py --jobs 8              # decision distribution",
             "python3 MHS/registry/corpus_lock.py --check          # exit 1 when a clone moved",
             "python3 MHS/registry/spotcheck.py --seed 2030 --n 30 # a sample of tasks/SPOTCHECK.md",
             "```", "",
             "A full build needs the corpus (`labs/`, `robots/`, `work/`, the catalogue). `--cache DIR` or "
             "`$MHS_TRIAGE_CACHE` keeps the source-scan facts per commit.", "",
             "## Counts", "",
             f"- records: **{total}** ({', '.join(f'{k} {v}' for k, v in stats['by_track'].items())})",
             "- decisions: " + ", ".join(f"{k} {v}" for k, v in summary["by_decision"].items()),
             f"- dispatchable now: **{summary['dispatchable_now']}** (strict-ready {summary['strict_ready']}); "
             f"waiting for a helper: {stats['blocked_on_helper']}; quarantined: {stats['quarantine']}; "
             f"forks and duplicates: {stats['variants']}",
             f"- pinned commits: {stats['pinned_commits']}; dual-mode records: {stats['dual_mode']}",
             "- licence classes: " + ", ".join(f"{k} {v}" for k, v in stats["by_license_class"].items()),
             f"- cards needing a publication review: {summary['publish_review_required']}",
             "- evidence: " + ", ".join(f"{k} {v}" for k, v in stats["by_evidence"].items()),
             f"- catalogue rows without a clone: {len(uncloned)}", "",
             "## Provenance", "",
             f"- catalogue: `{manifest['catalog']['path']}` ({manifest['catalog']['rows']} rows, "
             f"`{manifest['catalog']['sha256'][:19]}...`)",
             f"- capability catalogue: `{manifest['capabilities']['path']}` ({manifest['capabilities']['classes']} classes)",
             f"- corpus lock: `{manifest['corpus_lock']['path']}`; overrides: "
             + ", ".join(f"`{f}`" for f in manifest["overrides"]["files"]),
             f"- analyst profiles: {manifest['analyst_profiles']['rows']}; recon notes: "
             f"{manifest['recon_notes']['per_repo_files']}", ""]
    return "\n".join(lines)


def render_coverage(records, cards, summary, stats, uncloned, build_ts, decisions_summary) -> str:
    lines = [_ids.NON_AFFILIATION, "", "# OpenMHS registry coverage", "",
             f"Generated {build_ts} by `MHS/registry/build_registry.py`; every number is computed from the records "
             "and cards.", "", "## Decisions", ""]
    lines.append(_table(sorted(decisions_summary["by_strategy_role"].items()), ["strategy / role", "repos"]))
    lines += ["", "Deciding rule: " + ", ".join(f"{k} {v}" for k, v in decisions_summary["by_rule"].items()), ""]
    lines += ["## Waves", "", _table([(w, summary["by_wave"].get(str(w), 0), text) for w, text in TC.WAVES.items()],
                                     ["wave", "cards", "meaning"]), ""]
    fam_rows = []
    by_family = Counter(r["families"][0] for r in records)
    for family, count in sorted(by_family.items(), key=lambda kv: (-kv[1], kv[0])):
        status, helper, prerequisite, _ex = RECIPES.bridge_status(family)
        fam_cards = [cards[r["package_id"]] for r in records if r["families"][0] == family]
        fam_rows.append((family, count, status + (f" ({prerequisite})" if prerequisite else ""), helper or "-",
                         sum(1 for c in fam_cards if TC.dispatchable_now(c)),
                         sum(1 for c in fam_cards if c["decision"] == "untriaged")))
    lines += ["## Families", "", _table(fam_rows, ["family", "repos", "bridge_status", "helper", "dispatchable now",
                                                   "untriaged"]), ""]
    helper_rows = Counter(b for c in cards.values() for b in c["blocked_on"] if b.startswith("helper:"))
    lines += ["## Waiting for a helper", "", _table(sorted(helper_rows.items(), key=lambda kv: (-kv[1], kv[0])),
                                                   ["prerequisite", "cards"]), ""]
    lines += ["## Licences", "", _table(sorted(stats["by_license_class"].items()), ["licence class", "repos"]), "",
              _table(sorted(Counter(r["x-vendor"]["license"]["source"] for r in records).items()),
                     ["licence source", "repos"]), ""]
    lines += ["## Modes and evidence", "",
              _table(sorted(stats["by_mode"].items()), ["mode", "repos"]), "",
              _table(sorted(stats["by_evidence"].items()), ["evidence", "repos"]), "",
              _table(sorted(stats["by_ring"].items()), ["ring", "repos"]), ""]
    lines += ["## Card quality", "",
              f"- with entry symbols: {summary['with_entry_symbols']} (an `ast` class located in the clone: "
              f"{summary['with_ast_entry']}); blocked on `recon:entry_symbol`: {summary['recon_blocked']}",
              f"- with install commands backed by a root file: {summary['with_install']}",
              "- mock strategy: " + ", ".join(f"{k} {v}" for k, v in summary["by_mock"].items()),
              "- risk floors: " + ", ".join(f"{k} {v}" for k, v in summary["by_risk_floor"].items()), ""]
    top = sorted((c for c in cards.values() if TC.dispatchable_now(c)), key=lambda c: (c["wave"], c["rank"]))[:50]
    lines += ["## First 50 dispatchable cards", "",
              _table([(c["wave"], c["rank"], f"`{c['package_id']}`", c["decision"], c["helper"],
                       c["safety"]["risk_floor"]) for c in top],
                     ["wave", "rank", "package", "decision", "helper", "risk floor"]), ""]
    lines += ["## Catalogue rows without a local clone", ""]
    if uncloned:
        lines.append(_table([(u["catalog_row"], f"`{u['owner']}/{u['repo']}`", u.get("category") or "-",
                              u.get("analyst_status") or "-") for u in uncloned],
                            ["catalogue row", "repo", "category", "source status"]))
    else:
        lines.append("none")
    no_row = [r for r in records if (r["x-vendor"]["catalog"].get("join") or "none") == "none"]
    lines += ["", "## Clones without a catalogue row", ""]
    lines.append(_table([(f"`{r['package_id']}`", r["track"], r["families"][0], r["tier"]) for r in no_row],
                        ["package", "track", "family", "tier"]) if no_row else "none")
    lines.append("")
    return "\n".join(lines)


def render_docs(records, cards, summary, stats, uncloned, manifest, build_ts, out_dir, decisions_summary):
    return {
        os.path.join(out_dir, "README.md"): render_readme(records, cards, summary, stats, uncloned, manifest, build_ts,
                                                          decisions_summary),
        os.path.join(out_dir, "coverage.md"): render_coverage(records, cards, summary, stats, uncloned, build_ts,
                                                              decisions_summary),
    }


__all__ = ["render_docs", "render_readme", "render_coverage", "T"]
