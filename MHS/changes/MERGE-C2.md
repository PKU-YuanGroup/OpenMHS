# MERGE-C2 — WP-08 and WP-10 merged into the project root

Two isolated workspaces were merged into the repository root:
- `ws/wp08`: WP-08 steps 08a, 08b and 08c (MCP, CLI, code files, discovery, the OpenAI4S reference host);
- `ws/wp10`: WP-10 steps 10a and 10b from workflow C0 (registry triage, task cards, overlays, archive).

Only paths each WP owns (`WORK_PACKAGES.json` `files_owned`) were copied. Then every open verifier issue
of both WPs was reproduced and fixed. The details are in `MHS/changes/WP-08.md` and `MHS/changes/WP-10.md`,
in their "MERGE-C2" sections.

## Procedure

1. `diff -rq --exclude=__pycache__ --exclude=.DS_Store <ws>/MHS MHS`, the same for `integration/`, the
   top-level files and `_archive/`. Symlinked research directories were not compared.
2. Classify by owner, then copy (`cp -p`, or `rsync -a --exclude=__pycache__` for directories).
3. Check for unowned edits made by the workspaces' own steps.
4. Run GREEN, then fix the open issues and run GREEN again.
5. Re-run the acceptance checks of both WPs.

No project file changed after the `ws/wp08` snapshot was taken (`find -newer`), and the project's
`MHS/registry` was identical to the baseline. So nothing had to be merged by hand.

## Copied paths

### WP-08 (from `ws/wp08`; every difference was owned)

- `MHS/sdk/src/mhs/`: `mcp.py`, `client.py`, `cli.py`, `__main__.py`, `run.py` (new), `discovery.py` (new)
- `MHS/sdk/docs/`: `mcp-projection.md`, `cli.md` (new), `code-files.md` (new)
- `MHS/sdk/tests/`: `core/test_http_cli.py`, `endpoints/support.py`, `surfaces/**` (new directory)
- `MHS/changes/WP-08.md` (new)
- `integration/openai4s/`:
  - `README.md`, `DESIGN.md`, `openai4s-core.patch` (new), `openai4s-mhs.patch`
  - `demo/`: `run_demo.py`, `mcp_adapter.py`, `demo-report.json`
  - `openai4s_mhs/`: `__init__.py`, `cli.py`, `config.py`, `corepatch.py` (new), `emergency.py`, `host.py`,
    `hostroute.py`, `mcp_invoke.py`, `mcp_register.py`, `mcpconfig.py`, `operator_route.py` (new),
    `tools.py`
  - `tests/`: `__init__.py`, `fake_endpoint.py`, `host_remediation_support.py`, `long_running_endpoint.py`
    (new), `test_core_patch.py` (new), `test_dispatcher.py`, `test_emergency_stop.py`,
    `test_governed_outcomes.py` (new), `test_host.py`, `test_host_policy.py`, `test_long_running.py` (new),
    `test_mcp_interop.py`, `test_operator_route.py` (new), `test_stock_host_route.py`

### WP-10 (from `ws/wp10`)

Moves, done with `mv` in the project root, as the 10b merge note says. Nothing was deleted.
- `MHS/registry/manifests.py` -> `_archive/registry/manifests.pre-wp10.py` (equal to
  `baseline/MHS/registry/manifests.py`)
- `MHS/registry/manifests/` (1,967 files) -> `_archive/registry/manifests-skeleton-2026-10/` (identical to the
  workspace's archived copy)

Copied:
- `_archive/registry/manifests.py` (the 10a generator) and `_archive/registry/README.md`.
- `MHS/registry/**` by `rsync`, without `__pycache__`.
  - New files: `.gitignore`, `build_index.py`, `catalog_view.py`, `corpus.lock.jsonl`, `corpus_lock.py`,
    `licenses.py`, `overlays.py`, `source_scan.py`, `spotcheck.py`, `taskcards.py`, `triage.py`,
    `overrides/` (4 files and a README), `schema/` (2 schemas and an example), `tasks/` (2,967 cards,
    `pilot-candidates.json`, `SPOTCHECK.md`), 9 test modules and 2 family recipes.
  - Changed files: `README.md`, `coverage.md`, `build_registry.py`, `docs.py`, `family_data.py`,
    `recipes.py`, `validate.py`, `uncloned.json`, 35 family recipes, 2,967 records, 2 test modules, and the
    git-ignored aggregates `index.json`, `index.jsonl` and `records.csv`.
- `MHS/sdk/src/mhs/registry.py`, `MHS/sdk/tests/core/test_registry.py` and `MHS/changes/WP-10.md`.

Right after the copy, `build_registry.py --jobs 8 --check` in the project root reported
`0 generated file(s) differ`.

## Conflicts and unowned differences

- `ws/wp08`: none. Its step reports list no edit outside WP-08 ownership.
- `ws/wp10`: it predates the WP-04 to WP-07 merges, so about 100 unowned files differ (server, bridges,
  conformance, reference, driver and their tests). None was copied. The non-registry files it changed against
  the baseline were checked: `schema/conformance-report.schema.json`, `_data`, `test_http_cli.py`,
  `test_fidelity_replay.py` and `safety_lib/*` carry WP-01 to WP-03 state, which the project already has in a
  newer form. WP-10's own steps edited only WP-10 files.
- Integration breakages between the merged packages: none. GREEN passed right after the copy.

## Open issues resolved

Every listed issue was reproduced before it was fixed.

- WP-10 major (C0 10b, safety-relevant): hardware-capable repos were recorded as simulated only. Fixed in
  `build_registry.final_modes` and checked by `validate.check_hardware_evidence`. 14 records are now
  hardware first, among them `scpi-instrument-control`, the four `tiagocoutinho` controllers,
  `talos-2d-transfer`, `aero-hand-open` and `universal-robot-mcp`.
- WP-10 minors (10b and the 10a ones still open), all fixed:
  - the julabo siblings (overrides plus card ranking);
  - `pymodaq_plugins_teaching`;
  - the false pycont partner;
  - `agx` as an external engine;
  - README GPU and asset phrasing;
  - camelCase getters and setters, and motor control commands;
  - the pilot shortfall (`shortfall` field and a WP-11 followup);
  - the stale `docs.py` spot-check text;
  - the triage CLI count;
  - the strict-correct rate in `SPOTCHECK.md`;
  - the installer and link-shortener quarantine;
  - the stretch_mujoco justification;
  - the corpus_lock parent work tree;
  - the `--only` help text;
  - the rule-5 deviation note.
- WP-08 minors (08a: 7, 08b: 4, 08c: 6), all fixed or documented:
  - the queued `notifications/cancelled` call is no longer dispatched;
  - a guard test for the SSE close stall;
  - `enabled` needs a JSON `true`;
  - `include_bundle` is hidden from the model;
  - the limit unit fills a missing schema unit;
  - doc precision fixes, and the retry-token caveat in the doc (scoping replay by principal is a followup);
  - `lab()` honours an entry's `cwd`, and an unreadable `token_file` is an auth error;
  - `mhs conform --token-file`;
  - `mhs+stdio://` parsing;
  - `safety reset` finds the device's endpoint;
  - a missing operator token file is exit 2;
  - `test_core_patch` passes on a pristine checkout;
  - unsafe shared settings block agent rows;
  - the README TTY wording;
  - the emitted-MHS-code registry test.

## Test counts

Run from the project root with `PYTHONDONTWRITEBYTECODE=1`.

| suite | before the merge | after the copy | after the fixes |
|---|---|---|---|
| SDK (`MHS/sdk/tests`) | 1,738 OK (5 skipped) | 1,863 OK (4 skipped) | 1,869 OK (4 skipped) |
| registry (`MHS/registry/tests`) | 27 OK | 234 OK | 258 OK |
| OpenAI4S integration | 93 OK | 122 OK | 127 OK |
| site check | OK, 1 warning | OK, 1 warning | OK, 1 warning |

- The remaining SDK skips are optional dependencies: gymnasium, mujoco, pyserial and pyvisa-sim. 08b's
  `tests/endpoints/support.py` fix makes the OpenAI4S interop test run.
- The site warning predates this step: "downloads are stale against this checkout: 55 input(s) changed",
  mostly the regenerated family recipes. The site owner rebuilds `_site`.
- `MHS/drivers/EXEMPLARS.txt` does not exist yet (WP-11).
- `python3 -m mhs.driver check MHS/sdk/examples/thermostat --backend fake`: PASS, exit 0.
- The integration suite's child processes wrote no `.pyc` files during either GREEN run (the 08c
  `PYTHONDONTWRITEBYTECODE` fix).

## Acceptance re-run

WP-08:
- The surfaces suite: 127 OK. It includes the tools/list name snapshot, the 2 KB description bound and the
  unit text of every input property.
- The CLI exit-code table test: OK.
- `mhs devices -e http://127.0.0.1:<closed port> --json`: `MHS.TRANSPORT.UNAVAILABLE`, exit 3.
- The `mhs run` three-device ledger verifies against the endpoint evidence (in `test_codefile`).
- `mhs serve MHS/sdk/examples/thermostat --stdio` answers `mhs.hello`.
- `git apply --check` of `openai4s-core.patch` and `openai4s-mhs.patch` in a scratch `git clone --shared` at
  base `f48f216c81fe400444857c8a5d84d7407398918c`: OK.

WP-10:
- `build_registry.py --jobs 8 --check` gives 0 differing files, also with an empty scan cache. The build
  guards `MHS/drivers/**` and `overrides/**` against writes.
- `validate.py --no-corpus` and the full `validate.py`: PASS.
- A copy of `MHS/` alone: validate PASS, registry tests 258 OK, SDK registry tests 12 OK.
- All 2,967 cards validate.
- `grep -c CAP_RISK` gives 0. `MHS/registry/manifests` is gone and the archive exists.
- `spotcheck.py --n 30` prints 30 cards.
- `corpus_lock.py --check` and `build_index.py --check`: OK.

## Followups

- WP-11: the robot-SDK pilot bucket has 4 pilot repos plus the exemplar; HANDOFF pilot-20 wants 5. Re-pick
  `pilot-20.json` from the regenerated `tasks/pilot-candidates.json`.
- WP-01 (final cleanup): rebuild `MHS/site/_site`.
- WP-09/WP-04: scope MCP retry-token replay by principal (TPT-036). Today the caveat is documented in
  `mcp-projection.md`.
- WP-12: `MHS/sdk/examples/*/check-report.json` is rewritten by the GREEN driver check; ignore it, or commit
  the regenerated file.
- The earlier followups in `WP-08.md` and `WP-10.md` stand.

## Fix after the MERGE-C2 verification

The independent verification passed the merge itself and every listed open issue. It failed the step on one
safety-relevant major that was not on the list, and it raised three WP-10 minors. All four were reproduced,
then fixed in WP-08 or WP-10 files. The details are in the "MERGE-C2 fix" sections of `MHS/changes/WP-08.md`
and `MHS/changes/WP-10.md`.

| finding | owner | fix |
|---|---|---|
| major: `MHSConfig.load` read `allow_hardware` with `bool()`, so `"allow_hardware": "false"` opened the `MHSHost` hardware gate. `mhs.mcp` read the same document strictly. | WP-08 | `integration/openai4s/openai4s_mhs/config.py`: only a JSON `true` turns `allow_hardware` (and `enabled`) on. A non-boolean policy flag is listed in the new `MHSConfig.notices` (shown by `status`; it blocks nothing). A non-object settings document is a `ValueError`. README §3 states the rule. The verifier's repro now prints `MHSHost hardware gate: refused`. |
| minor: untriaged sim-env cards whose code drives hardware stayed simulated only (11 cards) | WP-10 | `build_registry.final_modes` / `validate.check_hardware_evidence`: an `untriaged` card with hardware evidence is hardware first whatever its role. The card adds `needs_recon: mode`. Decided gymnasium/MuJoCo family-configs stay simulated (a listed known limit). |
| minor: julabo-sibling hints merged the same-named Tango server class | WP-10 | `taskcards.device_hints` skips a server, GUI or CLI front end named after a class already read. |
| minor: part of the 10b SPOTCHECK fix hint was not done and not listed | WP-10 | `taskcards.ranked_classes` and `device_hints`: `debug_*.py` classes are never listed; PyMoDAQ plugins, Qt wrappers and vendored RL libraries rank lower and give no hints when a device class is ranked. What stays open is listed under "Known limits" in `WP-10.md`. |

Files changed in this fix:
- WP-08: `integration/openai4s/openai4s_mhs/config.py`, `integration/openai4s/tests/test_config.py`,
  `integration/openai4s/README.md`, `MHS/changes/WP-08.md`.
- WP-10: `MHS/registry/build_registry.py`, `MHS/registry/taskcards.py`, `MHS/registry/validate.py`,
  `MHS/registry/docs.py`, `MHS/registry/schema/taskcard.schema.json`, `MHS/registry/tests/test_merge_c2.py`,
  `MHS/changes/WP-10.md`.
- Regenerated by `build_registry.py`: `MHS/registry/README.md`, `coverage.md`, 25 family recipes
  (`families/*.md`, whose card listings carry ranks), the git-ignored aggregates `index.json`, `index.jsonl` and
  `records.csv`, and 27 records and 30 cards in substance. About
  1,800 more cards and records changed only in `rank` or the `next_action` text that quotes it, because
  vacuubrand moved from wave 2 to wave 3.
- This file.

Registry results: triage unchanged (`triage.py --out` sha256 `62d149a4...1f92`; 0 of 2,967 strategy/role pairs
differ). Dual-mode records 219 (was 208). Dispatchable now 386 (unchanged). Strict-ready 189 (was 190). The
pilot pool is unchanged.

### Test counts after the fix

| suite | after the first fixes | after this fix |
|---|---|---|
| SDK (`MHS/sdk/tests`) | 1,869 OK (4 skipped) | 1,869 OK (4 skipped) |
| registry (`MHS/registry/tests`) | 258 OK | 266 OK (+8 in `test_merge_c2.py`) |
| OpenAI4S integration | 127 OK | 129 OK (+2 in `test_config.py`) |
| site check | OK, 1 warning | OK, 1 warning (the same stale-downloads warning, 55 inputs) |

- `MHS/drivers/EXEMPLARS.txt` still does not exist (WP-11).
  `python3 -m mhs.driver check MHS/sdk/examples/thermostat --backend fake --no-report`: PASS, exit 0.
  `--no-report` runs the same gates and leaves WP-06's `check-report.json` untouched.
- The integration run prints a `ResourceWarning: unclosed database` at exit. The verification's own run
  shows it too, so it is not from this fix.
- No `.pyc` was written under `MHS/` or `integration/` (every run used `PYTHONDONTWRITEBYTECODE=1`).

### Acceptance re-run after the fix

WP-08:
- The verifier's `allow_hardware_string.py` now prints `MHSConfig.allow_hardware: False`,
  `MCPPolicy.allow_hardware: False` and `MHSHost hardware gate: refused`.
- `python3 -m openai4s_mhs status` with `"allow_hardware": "true"` lists the value under `notices`.
- The mutant `bool(raw.get("allow_hardware", False))` fails 7 subtests of `test_only_a_json_true_allows_hardware`.
- `mhs devices -e http://127.0.0.1:9 --json`: `MHS.TRANSPORT.UNAVAILABLE`, exit 3.
- `mhs serve MHS/sdk/examples/thermostat --stdio` answers `mhs.hello`.
- `openai4s_mhs core-patch check --json`: applies true, matches true, ok true.

WP-10:
- `build_registry.py --jobs 8 --cache <empty dir> --check`: 0 generated files differ.
- Full `validate.py` and `validate.py --no-corpus`: PASS. `corpus_lock.py --check`: OK.
  `build_index.py --check`: no stale aggregate.
- `triage.py --out` sha256 `62d149a4eb0f6c5efba937c4fbf03157bdd48b07caa9a1a5d814c29dd8df1f92`; it matches every
  shipped record.
- A scan of every record finds no `untriaged` record that has hardware evidence and does not list hardware
  first.
- `spotcheck.py --n 30` (seeds default and 2030): 30 cards each.
- A copy of `MHS/` alone: `validate.py --no-corpus` PASS, registry tests 266 OK, SDK `core/test_registry.py`
  12 OK.

### Followups added by this fix

- WP-10 (later) or WP-11: a recon card's planned hardware device with no candidate class has
  `estop_required: false` (189 records). Consider defaulting it to true on the robots track.
