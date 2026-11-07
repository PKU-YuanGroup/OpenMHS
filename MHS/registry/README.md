OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# OpenMHS registry

Generated **2026-10-20T00:00:00Z** by `MHS/registry/build_registry.py` (registry version 0.9.0, publisher id `openmhs-registry`). Stdlib only, offline and deterministic: a rebuild from the same inputs is byte-identical (`MHS_REGISTRY_DATE` sets the date; `SOURCE_DATE_EPOCH` is ignored).

The registry has one record and one task card for each of the **2967** upstream clones of the OpenAI4S corpus. The record is the catalogue entry (what the repo is, how it is integrated, which commit and licence); the task card is the unit of work for a driver author, human or model. Nothing here was installed or run; evidence states say how much was checked.

## Files

| Path | Content |
|---|---|
| `repos/<track>/<owner>__<repo>.json` | registry record (2967), `MHS/schema/registry-record.schema.json` |
| `tasks/<track>/<owner>__<repo>.json` | task card (2967), `schema/taskcard.schema.json` |
| `tasks/pilot-candidates.json` | the pilot pool: top-ranked cards per bucket for `MHS/handoff/pilot-20.json` |
| `tasks/SPOTCHECK.md` | a reviewer's verdicts on 290 random cards in 11 samples (`spotcheck.py`) |
| `families/<family>.md` | one recipe per family: bridge_status, launch line, capability mapping |
| `overrides/*.json` | curated triage decisions (`schema/overrides.schema.json`); read, never written |
| `corpus.lock.jsonl` | git remote and HEAD of every clone (`corpus_lock.py`) |
| `uncloned.json` | catalogue rows without a local clone |
| `coverage.md` | counts by decision, wave, family, licence and evidence |
| `index.json`, `index.jsonl`, `records.csv` | aggregates built by `build_index.py`; git-ignored |

Archived: the 1,967 skeleton adapter manifests of the 1.0 registry are in `_archive/registry/manifests-skeleton-2026-10/` (moved, not deleted); records carry `adapter.manifest_ref: null`.

## Pipeline

1. `scan_corpus.py` and the catalogue classify each clone (catalogue family and tier).
2. `source_scan.py` parses the clone's Python with `ast` (nothing is imported or executed): device classes, gym registrations, licence file, packaging metadata, mocks and limit-like constants.
3. `triage.py` applies the eleven ordered rules (first match wins); `overrides/*.json` win over the rules.
4. `licenses.py` resolves `license_spdx` (catalogue, then the LICENSE file, then packaging metadata) and `license_class`. A LICENSE file is identified by the title, grant or SPDX id that comes first in its head, so a licence named further down (a GPL-3.0 section on the Affero GPL, a bundle's components) never decides; an EULA or an all-rights-reserved file is proprietary.
5. `overlays.py` reads `MHS/drivers/<track>/<owner>__<repo>/` (driver.lock.json, RESULT.json, check-report.json) as evidence; it never writes there.
6. `taskcards.py` writes the cards, the waves and the ranks; `recipes.py` and `docs.py` write the recipes and this file; `build_index.py` writes the aggregates.

## Triage rules

1. tier X or an empty clone: `skip:empty`
2. no source code, an analyst docs-only flag the scan confirms, a curated list, a course or tutorial: `skip:not-device`
3. a download lure or binary-only installer: `skip:quarantine` (`quarantine` is set whatever rule decides)
4. an earlier MHS implementation: `reference:prior-art`
5. a fork or duplicate of another corpus repo: `skip:duplicate_of` with `variant_of`
6. a protocol stack, framework or engine behind a helper: `bridge-runtime:<family|engine>`
7. an orchestrator, host or MCP wrapper of a covered backend: `reference:host`; tooling: `skip:tooling`
8. tier D (peripheral, not a device): `skip:peripheral`; a catalogue software row counts as tier D only when the code shows no device evidence, no driver directory (`hal/`, `drivers/`, `hardware/` ...) and no device-named class. When the catalogue calls a repo a model or a simulation (measurement model, task environment, direct simulation backend, digital twin), device evidence also needs a class that uses a hardware transport (serial, VISA, USB, fieldbus, a vendor SDK)
9. a family with a helper plus a structural marker (import, package.xml, gym registration, MJCF): `family:<family>` (family-config); gym envs that need an external simulator (Isaac, CARLA, AirSim, Newton, Gazebo world files or plugins ...) have no helper and fall through. Gym registrations and MJCF files under examples, tests, docs, fixtures or vendored trees are no marker; the MuJoCo marker is a loadable scene or robot model with actuators (object and fixture assets, fragments and templates alone are none); a GUI application without a device class takes no protocol family
10. Python code with an AST device entry class (score at least 9 with three API members, or the transport-using class of a catalogue device SDK; simulators, mocks and dummies of the device never count): `PY_SDK_WITH_ENTRY` (direct-driver)
11. everything else: `untriaged:<why>` (a recon-only card)

Simulator families come only from structural markers in the code. Pilot helpers are available (PythonObjectDriver, SerialDriver, ScpiDriver, GymnasiumDriver, MujocoDriver); every other family waits for a post-pilot helper and its cards carry `blocked_on: helper:<name>`.

## Task cards and waves

A card is dispatched only when `decision` is direct-driver or family-config, `helper_status` is available, `blocked_on` is empty, `quarantine` is false and `package_status` is none or in_progress (a driver package whose RESULT.json passed is maintained, not dispatched again). A python-object card with neither an entry symbol nor candidate classes (a serial or SCPI card: nor an install file) is blocked on `recon:entry_symbol` (wave 4). Entry symbols come from the AST scan with file and line: `ast` when the class definition is in the clone, `recon` for a gym registration whose class is not defined in the clone. Simulator cards list the package's gym registrations, else (sim-env cards) its environment classes, while a twin candidate's entry is its model; device cards list device classes, never GUI widgets and never a simulator, mock or dummy of the device when a real class exists (those go to `mock_strategy`). MuJoCo cards name the models a MujocoDriver loads in `models` (`{file, line, kind}`, the main scene or robot model first); a MuJoCo card without one carries `needs_recon: model`. `needs_recon` also flags `artifacts` (the README downloads assets, models or LFS objects the clone does not hold), `motion` (a robot hardware card whose motion API was not found) and `mode` (a recon card of a simulation repo whose code also drives hardware; the recon decides which mode the driver serves). Install commands appear only when a root file backs them, and `install.system_deps` names software pip does not install that the package code imports (mujoco-py's MuJoCo 2.1 binaries); `safety.risk_floor` is the highest catalogue risk class of the candidate classes. Hints are suggestions, never a specification. Pilot candidates also need an `ast` entry symbol (or, for MuJoCo, a main model), candidate classes, no system dependency and no `artifacts` or `motion` flag; a bucket served by two helpers takes its cards from both families in turn.

| wave | meaning | cards |
|---|---|---|
| 0 | exemplars, done before the handoff (curated overrides) | 4 |
| 1 | pilot pool: the non-exemplar cards of tasks/pilot-candidates.json (MHS/handoff/pilot-20.json dispatches 20 of them) | 54 |
| 2 | strict-ready: Python, pip install backed by a root file with no system dependency, no GPU, licence known, AST entry symbol (or, for MuJoCo, a main scene or robot model), candidate classes, no artifact download | 149 |
| 3 | other dispatchable cards with an available helper | 425 |
| 4 | recon-only cards (decision untriaged, or a dispatchable card blocked on recon:entry_symbol): confirm an entry symbol and a decision | 0 |
| 5 | family members waiting for a post-pilot helper (blocked_on helper:<name>) | 73 |
| 6 | cards that need a GPU, Windows or an external engine without a helper (Isaac, Unity, Unreal, Habitat, AirSim, CARLA, Gazebo) | 116 |
| 9 | never dispatched as a repo task: skip, reference and bridge-runtime cards | 2146 |

Rank within a wave (published and deterministic):

```
rank_score = 40*partner + 20*hardware_mode + 10*helper_available + 8*has_tests + 5*log10(stars+1) - 15*gpu - 20*license_unknown; sorted by descending score, ties by package_id
```

## Records

- `integration.strategy`, `integration.role` and `integration.reason_code` come from triage; `blocked_on`, `wave` and `rank` from the card; `quarantine` and `variant_of` from triage.
- `repo_url` and `source{repo_url, commit}` come from the clone's git remote and HEAD (`corpus.lock.jsonl`); a different catalogue URL is kept in `x-vendor.catalog.repo_url`.
- `license` and `license_spdx` are SPDX expressions; `license_class` is permissive, weak-copyleft, copyleft, network-copyleft, source-available (SSPL, PolyForm, BUSL, non-commercial), proprietary or unknown. The catalogue's own text stays in `x-vendor.catalog.license_raw`.
- `modes` lists hardware first. A dual-mode repo plans a hardware device plus a simulated device that names it in `models` (`x-vendor.device_plan`). Tier D and X records have no modes.
- English fields contain no Chinese text; the catalogue originals stay in `x-vendor`.
- `capabilities_offered` are the card's candidate classes (code-derived suggestions, empty for tier D/X).
- Evidence ladder: `declared` < `static_scan` < `agent_read` < `contract_checked` (a driver package passed the gate on a fake or simulated backend) < `hardware_checked` (an operator-run hardware check). Ring 0 needs hardware_checked, ring 1 contract_checked, ring 2 a dispatchable card, ring 3 the rest.

## Regenerate and check

```sh
python3 MHS/registry/build_registry.py --jobs 8      # records, cards, recipes, docs, aggregates
python3 MHS/registry/build_registry.py --check       # exit 1 when a committed file is stale
python3 MHS/registry/build_index.py                  # aggregates only, no corpus needed
python3 MHS/registry/validate.py --no-corpus         # everything that needs only MHS/
python3 MHS/registry/validate.py                     # plus clone and entry-symbol checks
python3 MHS/registry/triage.py --jobs 8              # decision distribution
python3 MHS/registry/corpus_lock.py --check          # exit 1 when a clone moved
python3 MHS/registry/spotcheck.py --seed 2030 --n 30 # a sample of tasks/SPOTCHECK.md
```

A full build needs the corpus (`labs/`, `robots/`, `work/`, the catalogue). `--cache DIR` or `$MHS_TRIAGE_CACHE` keeps the source-scan facts per commit.

## Counts

- records: **2967** (labs 1045, robots 1922)
- decisions: bridge-runtime 273, direct-driver 278, family-config 543, reference 320, skip 1553
- dispatchable now: **0** (strict-ready 197); waiting for a helper: 3; quarantined: 4; forks and duplicates: 25
- pinned commits: 2962; dual-mode records: 172
- licence classes: copyleft 205, network-copyleft 28, permissive 1910, proprietary 17, source-available 43, unknown 708, weak-copyleft 56
- cards needing a publication review: 816
- evidence: agent_read 46, contract_checked 746, declared 6, static_scan 2169
- catalogue rows without a clone: 3

## Provenance

- catalogue: `openai4s_backend_catalog_all_sources/openai4s_backend_catalog.csv` (2975 rows, `sha256:89eee687e7a4...`)
- capability catalogue: `MHS/spec/capabilities.json` (63 classes)
- corpus lock: `MHS/registry/corpus.lock.jsonl`; overrides: `companion-sources-lock.json`, `companion-sources.json`, `exemplars.json`, `helper-wave-1-routing.json`, `labs.json`, `mode-corrections.json`, `p3-reauthor-routing.json`, `p5-reauthor-pf400-routing.json`, `partners.json`, `robots.json`, `ros-routing-20261102.json`, `ros-wave-b-routing.json`, `ros-wave-c-routing.json`, `waiting-routing.json`
- analyst profiles: 2967; recon notes: 54
