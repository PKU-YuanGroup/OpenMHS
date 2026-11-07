# GYM-FACTS-SOURCE — the Gymnasium facts.md pages give the step bound's present source

DUCKIETOWN-ACTION found 117 Gymnasium `facts.md` pages whose Limits paragraph still gives the step bound the source
`<env_id>:action_space`, which no reference has said since GYM-LIMITS (`MHS/changes/DUCKIETOWN-ACTION.md`, "Found, not
fixed"). Each page now says what its `reference.json` says: no source and the fake backend's space, or `upstream_code`
and the line its `action_space_ref` cites. Only `facts.md` changed, and no gate digest did.

## The scan

- `scan.py` lists every `MHS/drivers/*/*/facts.md` that writes a backticked name ending in `:action_space`, a name with a
  space in it included (deformable_gym writes `<env id>:action_space`): 118 pages, each with one such name. 103 name the
  upstream environment by its id or class (`GenWurtzExtract-v2:action_space`, `PandaReach-v3:action_space`,
  `TradingEnv:action_space`), 9 the fake's class (`FakeOT2Env:action_space`) and 6 a placeholder (`<env_id>`, `<env>`,
  `<env id>`, or nothing before the colon).
- For each page it reads the limits of `cap.world.step.v1` in `reference.json` (source, ref, min and max) and the
  matching rows of `REFERENCE.md`. On every page the bounds share one source and one ref (five pages have two bounds,
  for example `action.steering` and `action.motor`), and `REFERENCE.md` prints that ref as `(no source: ...)` or
  `(upstream_code: ...)`. On 69 pages the bound had no source and the ref `action_space of the fake backend .fake:FakeX`
  (GYM-LIMITS); on 49 it was `upstream_code` with a `path:LINE` ref, and each of those 49 packages sets
  `GymnasiumDriver.action_space_ref` (GYM-SPACE-REF, GYM-SPACE-REF-2), while none of the 69 did.
- No `reference.json` under `MHS/drivers` has a ref ending in `:action_space` any more, so none of the 118 pages
  describes a bound the bridge builds itself (`gymnasium.make`), and none was left alone for that reason.
- The numbers the paragraphs give for the bounds were compared with min and max: on 108 of the 117 rewritten pages the
  paragraph shows every value; the other nine describe the values instead of listing them there (`min_joints`/
  `max_joints`, `num_dcs - 1`, "the 12 effort bounds").
- The 118th page, `MHS/drivers/robots/cognitiveaisystems__blindvla/facts.md`, belongs to the BLINDVLA-ACTION session,
  which rewrote that package during this work, its Limits paragraph included, and asked in its claim note that this
  change leave the page alone. It was left to that session; it no longer names `Empty-v1:action_space`.

## The rewrite

- Only the clause that names the source changed. With an unsourced bound it now gives no source and the ref
  `action_space of the fake backend .fake:FakeX`; with an `upstream_code` bound it gives the source `upstream_code` and
  the cited `path:LINE`, as `MHS/drivers/robots/duckietown__gym-duckietown/facts.md` has done since DUCKIETOWN-ACTION.
  68 of the 117 pages have the first kind, 49 the second.
- `apply.py` replaces the five common forms of the clause (83 pages; `E` is the old name, such as
  `PandaReach-v3:action_space`, and `R` the reference's ref):

| the old clause | unsourced bound | `upstream_code` bound | pages |
|---|---|---|---|
| with the source `E` | with no source and the ref `R` | with the source `upstream_code` and the ref `R` | 53 |
| with source `upstream_code` and ref `E` | with no source and ref `R` | with source `upstream_code` and ref `R` | 6 |
| source `upstream_code`, ref `E` | no source, ref `R` | source `upstream_code`, ref `R` | 7 |
| with source `E` | with no source and ref `R` | (no page) | 1 |
| source `E` after a comma, semicolon or parenthesis | no source, ref `R` | source `upstream_code`, ref `R` | 16 |

- The other 34 pages (23 unsourced, 11 `upstream_code`) got an edit of their own (`MANUAL` in `apply.py`), because the
  sentence also said something about the old ref that the new one makes false: "(the fake's stand-in class)" (pc-gym),
  "not a `path:LINE` device bound" (drl-nav), "G4 skips a derived limit whose ref is not `path:LINE`" (plasticinelab),
  "its ref is the environment id (...), not a clone line" (himloco_lab), "not a clone line (G4 skips derived simulator
  limits)" (surgvla), "carry no source/ref of their own" (dexpoint-release), "the bridge labels that bound ..." (pyflyt,
  deepmimic_mujoco) or "Their source is the environment itself (...)" (home-platform). Plasticinelab and surgvla now say
  that G4 checks their cited line: G4 checks the ref of every limit with a source (`mhs/driver/check.py:1469`) and
  skips a simulator family's derived limit only when its ref is not a `path:LINE` (`:1470-1471`). A remark that still
  holds stays as written, such as bsk_rl's "that reference is deliberately not a `path:LINE` and G4 does not check it
  as one" and deformable_gym's "the family path is exempt from the clone-line reference check (`_derived` in the gate)".
- **Layout.** The edited line is refilled together with the lines after it, at the page's width (its widest prose line,
  at most 120 columns), until the fill reaches one of the paragraph's own line ends with a line of at least three
  quarters of that width; from there on the paragraph keeps its lines. A code span is never split, and a page that puts
  two spaces after a sentence keeps them.
- **Checks of the rewrite** (`verify.py`, `logs/verify.log`). On every one of the 117 pages the changed lines lie in the
  paragraph that named the old source; with whitespace collapsed, the page is its original with the one clause replaced;
  no changed line is wider than the page or ends in whitespace; the paragraph names the reference's ref and says "no
  source" or `upstream_code`. No `facts.md` under `MHS/drivers` names `<env_id>:action_space` any more. No new clause
  holds a word that `collect.py` looks for as the residue of another exemplar.
- **Working files** (not exported): `work/handoff-runs/gym-facts-source/` holds `originals/` (the 117 pages and
  `CHANGELOG.md` as they were), `scan.py` with `scan.json`, `apply.py` with `edits.json` (the form and the new clause of
  each page) and `applied.diff`, `verify.py`, `collect/`, `logs/` and `dronesim-path/` (below). The first `apply.py`
  run (06:13 PDT) stopped at the blindvla page, which had changed since the scan, after it had written the 22 pages
  before it. `SKIP` and a check that a page is still its kept original or its rewrite were added; the second run
  (06:15) recomputed those 22 from their originals, found them as written and wrote the other 95 (`logs/apply.log`).

## The dronesim path name

The Limits paragraph of `gh.enac-drones/dronesim` said that the bridge publishes the bound "as `action.0` limits",
while the reference names the path `action.values` (`[0.0, 0.0, 0.0, 0.0] .. [1.0, 1.0, 1.0, 1.0]`). The page's next
paragraph says why: the fake serves the single tello's four PWM commands as one Box(4), not as upstream's Dict keyed by
the drone index, because `action.0` is not a valid bridge limit path. At the user's request a second step renamed the
path in the Limits paragraph to `action.values` (`dronesim-path/rename.py`); the next paragraph keeps `action.0`, where
it is right. The page as the first step left it is in `dronesim-path/originals/`, the diff in
`dronesim-path/logs/rename.diff`, and `verify.py` checks the page with the rename.

## Result

- `collect.py --strict` over the 117 packages (six chunks, one gate at a time in each; `collect/chunk*.log`): 116 pass
  the gate with no warning. `gh.simpler-env/simplerenv` fails G4 and G7, as it did before this change: its `RESULT.json`
  is `skip-proposed` (the card duplicates `gh.simpler-env/maniskill2_real2sim`, and the facts it cites lie in a submodule
  the gate cannot read), and the stable digest of this gate run, `sha256:65ae9bc8...`, is that of the `check-report.json`
  the package kept from its last regeneration (the same 31 findings). After the dronesim rename `collect.py --strict`
  on that package passes again with no warning, with its digest unchanged (`sha256:55bb1490...`,
  `dronesim-path/logs/collect.log`).
- **Digests.** For each of the 116 the digest of this gate run is its `RESULT.json` `gate.digest` and the stable digest
  of its kept `check-report.json` (`logs/digests.log`). No `RESULT.json`, `reference.json`, `REFERENCE.md`,
  `check-report.json` or `driver.lock.json` was edited: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- `validate.py --no-corpus` passes (`logs/validate.log`, and after the rename `dronesim-path/logs/validate.log`).
- `build_registry.py --check`, run after the last page was written (06:19-06:36 PDT, `logs/build_registry-check.log`),
  finds no generated file that differs, so the registry needs no rebuild: its record of a package copies the gate
  digest, the status and the evidence state, and none of them changed. The BLINDVLA-ACTION session's own check
  (06:15:51-06:33:24), which also began after that write, found none either, and neither did a third run after the
  dronesim rename (06:44:39-06:55:22, `dronesim-path/logs/build_registry-check.log`).
- `tools/build_changelog.py` indexes this record.
- Follow-up verification on 2026-11-02: `tools/oss_export_check.py` passes on the combined state containing this
  change and the other completed changes. In a fresh export of the 13,259 tracked files, the handoff baseline run
  checks the generators, the SDK, registry and spec suites, the site build and its freshness, the thermostat gate,
  the gates of the four exemplars and the OpenAI4S integration tests. This is the subsequent baseline result, not a
  check run during the original focused session.

## Found, not fixed

- **No check.** Nothing compares a `facts.md` with its reference, so a later change of a derived bound can leave a page
  behind again, as GYM-LIMITS, GYM-SPACE-REF and GYM-SPACE-REF-2 left these 118. A `collect.py` note that compares the
  refs a Limits paragraph names with the step bounds of `reference.json` would catch it.
