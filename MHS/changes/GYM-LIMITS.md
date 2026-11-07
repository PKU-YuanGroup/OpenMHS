# GYM-LIMITS — action limits derived from a Gymnasium fake no longer claim to be upstream code

Wave D found that the Gymnasium bridge labels every bound it derives from an action space `source: upstream_code`,
whichever object supplied the space (`MHS/changes/WAVE-D.md`, "Found, not fixed"). Driver packages render their reference
on the fake backend, so 207 Gymnasium packages published their fake's action bounds as upstream code, many of them
placeholder test data. Those bounds now carry no source and a `ref` that names the fake backend. A driver can cite the
upstream line its fake copies with the new `action_space_ref`, which gate G4 checks. No bound changed.

## The defect

`GymnasiumBridge.action_limits()` returned `{"min", "max", "source": "upstream_code", "ref": "<env_id>:action_space"}` for
every space. A `GymnasiumDriver` hands the bridge the environment its `backends` entry built (the package's fake), and the
reference is rendered from that view (`mhs.driver reference <dir>`), so the fake's space became a bound "of upstream code".

- Wave D's Go2 task of `gh.sallu-786/go2_isaac_ros2` published -1..1 over three values, all `# placeholder` in its fake,
  for a 12-joint Isaac Lab task.
- Gate G4 skipped these refs, because `<env_id>:action_space` is not a `path:LINE`, so nothing checked the claim.
- `MHS/handoff/REVIEW.md` item 7 (a placeholder number appears in no Fact or Limit) could not hold for these packages.

## The fix

The derived limits now say which environment their space came from (`mhs.bridge.gymnasium`, `mhs.driver.families`):

| The environment | The derived limits |
|---|---|
| built by the bridge (`gymnasium.make(env_id)`, the `env_spec` factory) | `upstream_code`, `ref` `<env_id>:action_space`, as before |
| pre-built and passed in (`env=`): a driver's `backends` entry, a test double | no `source`; `ref` `action_space of <env_origin>` |
| either, with `action_space_ref` | `upstream_code`, `ref` the cited `path:LINE` |

- **Bridge.** `GymnasiumBridge` takes `env_origin` (what a pre-built `env` is) and `action_space_ref`. Without an origin a
  pre-built environment is named by its class (`action_space of the FakeBoxEnv object passed to the bridge`).
- **Driver.** `GymnasiumDriver.make_bridge` passes `env_origin = "the <backend> backend <target>"` for an environment a
  `backends` entry built; the Go2 bound now reads `ref: "action_space of the fake backend .fake:FakeGo2Env"`. The new class
  attribute `action_space_ref` (`path/in/clone:LINE` of the upstream code that defines the space the fake copies) must
  parse as a reference inside the clone, or the driver does not resolve.
- **Limit engine.** `EffectiveRule.to_json` dropped a `ref` whose rule states no `source`; it now publishes it. No rule of
  any reference had a ref without a source before.
- **Gate.** `BindingModel.derived_limits` records the paths a simulator family derived from its backend. G3's
  `UNSOURCED_LIMIT` rule is about the driver's `Limit`s, so it skips a derived path without a source; a `Limit` the driver
  declares on the step without a source still fails. G4 already checked a derived limit whose `ref` is a `path:LINE`, so an
  `action_space_ref` is checked like the ref of any limit (`REF_MISSING`, `REF_LINE`, and `REF_VALUE` when the line does not
  show the bounds, which `collect.py` lists as `UNSOURCED_LIMIT_GATE_WARNING`).
- **Reference.** `REFERENCE.md` prints an unsourced bound with `(no source: <ref>)`, or `(no source)` without a ref; no
  reference had an unsourced bound before.
- **Review tool.** `show_refs.py` lists `action_space_ref` next to the other citations of `driver.py`.

Why a `ref` and not a `reason`. The first version put the note in `reason` (`derived from the action space of the fake
backend (...), not from a cited upstream line`). The MCP projection writes every limit's reason into the tool description
(clipped to 60 characters), so the step tools of the packages with several derived limits grew by about 63 bytes per
limit, and three of them failed `G8.TOOL_SIZE`: `gh.snu-pi/humanoidtoolbench` (7 limits, 2,032 -> 2,473 bytes),
`gh.robotcontrolstack/duobench` (1,897 -> 2,149) and `gh.robocasa/robocasa-gr1-tabletop-tasks` (1,756 -> 2,071). The
note says where the bound came from, which is what `ref` is for; the projection never prints a ref, so every tool
description is byte for byte what it was, and `reason` keeps meaning why a bound is what it is.

Two other directions were set aside:
- `Limit.operator_required` for every fake-derived bound would drop bounds the fake view enforces, and bounds that are right:
  many fakes copy the upstream space and cite it (the CartPole exemplar copies `Discrete(2)`, cited at
  `gymnasium/envs/classic_control/cartpole.py:151` in a Fact).
- A new `source` value for "derived from a fake" would change `defs.schema.json` and the spec (CORE-040); the rule grammar
  already carries a bound without a source.

MuJoCo is unchanged. `MujocoDriver` packages label their `actuator_ctrlrange` bounds `upstream_code` with
`<model>:actuator_ctrlrange`; 60 of the 61 load the card's MJCF from the clone, the 61st carries a copy of it, and their
fakes read the ranges from that file.

## Tests

- `tests/bridges/test_gym_limit_provenance.py` (new): a space the bridge builds is `upstream_code`; a pre-built environment
  publishes and enforces its bounds without a source, and its refusal claims no provenance; `env_origin` names the backend
  in every rule of a `Dict` space, and the effective rule keeps the ref; `action_space_ref` gives `upstream_code` with that
  ref; a blank or oversized ref is refused.
- `tests/driver/test_families.py`: a fake-backed `GymnasiumDriver` publishes its bound with the backend's ref and no
  source, records the derived path and has no strict refusal; `action_space_ref` makes the bound `upstream_code`; a ref
  that is not `path:LINE` inside the clone does not resolve.
- `tests/driver/test_check.py`: a Gymnasium package passes G3, G4 and G5 with the unsourced bound and prints `no source:` in
  `REFERENCE.md`; a declared step `Limit` without a source still fails G3; a correct `action_space_ref` passes G4 and is
  published, and a line without the bounds, a line past the end and a missing file give `REF_VALUE`, `REF_LINE` and
  `REF_MISSING`.
- `tests/safety_lib/test_limits.py`: a ref without a source is published. `tests/safety_lib/test_reference_file.py`: an
  unsourced bound prints `(no source: <ref>)`, or `(no source)`.
- `tests/handoff/test_tools.py`: `show_refs.py` lists an `action_space_ref`.

## Docs

- `MHS/sdk/docs/driver-authoring.md`: section 5 says how a `GymnasiumDriver`'s bounds are labelled and when to set
  `action_space_ref`; section 6 names the fake's action space as the one place fake numbers reach the reference; the gate
  table's G4 row names `action_space_ref`.
- `MHS/sdk/docs/bridges.md`: the Gymnasium section says where the derived limits come from.
- `MHS/handoff/REVIEW.md`: item 2 reads an `action_space_ref` against its line; item 7 says how the fake's bounds appear in
  the reference and that an `action_space_ref` for a placeholder space is rejected.
- `MHS/handoff/PROMPT.md` (rule 2) and `MHS/handoff/PLAYBOOK.md` say the same to the authoring model.

## Packages

All 207 Gymnasium packages that publish a limit derived from an action space have a `backends["fake"]` factory, so
all 207 changed: the 206 that pass, and `gh.simpler-env/simplerenv` (skip-proposed as a duplicate; its gate fails G4 and
G7 as before, with the same findings).

- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md` of each. A
  comparison with the files before shows 234 changed limits and nothing else: each lost `source: upstream_code` and the
  `ref` `<env>:action_space`, and got a `ref` that says where the space came from, with the same bounds;
  `provenance.manifest_digest` changed with the manifest. 231 refs name the fake backend. Three packages build their own
  `GymnasiumBridge` in `make_bridge`
  and pass no origin (`gh.maximilianb2/pc-gym`, `gh.emb-ai/robobenchmart`, `gh.sjtu-visys-team/visfly`); their ref
  names the class of the environment object, for example `action_space of the FakePcGymEnv object passed to the bridge`.
- **Gate.** `python3 -m mhs.driver check <dir> --backend fake` ran on all 207 and rewrote `check-report.json`. The 206
  passing packages pass again, and the digest each run printed is the one its `RESULT.json` `gate.digest` already
  records: the stable digest covers the gate's findings, not the bytes of the reference, and no finding changed. So no
  `RESULT.json` changed; `authored_by` and `reviewed_by` are untouched.
- **Tests.** No `test_driver.py` pins the old bounds or their source; none changed.
- **Tool sizes.** The step tool of every one of the 207 has the size it had before (largest 2,032 bytes, of 2,048).
- **Originals.** The files the refresh could touch (`reference.json`, `REFERENCE.md`, `RESULT.json`, `check-report.json`,
  `test_driver.py`) are kept as they were in `work/handoff-runs/gym-limits/originals/` (not exported). Only
  `reference.json`, `REFERENCE.md` and `check-report.json` differ from them.

## Found, not fixed

- **No package cites its space yet.** `action_space_ref` is a package edit and a reading of the upstream line, so no
  package sets it. A rough text scan of the 207 fakes finds a `path:LINE` within a few lines of the action space in 113 of
  them (24 of those also say `placeholder` there) and a `placeholder` mark without a citation in 27 more, so perhaps 90
  could get `upstream_code` back after a review of the cited line. The first
  candidate is the CartPole exemplar `gh.farama-foundation/gymnasium` (`Discrete(2)`, `cartpole.py:151`), because
  `mhs.driver new --like` copies its driver.
- **Packages with their own `make_bridge`.** The three above could pass `env_origin`, so their ref names the backend.
- **Four blocked packages with stale references.** `gh.cfpark00/smartem`, `gh.dwinters42/liquidhandler`,
  `gh.erikbgithub/python3-tecan-genesis` and `gh.sciencecorp/galago-tools` (blocked, `HELPER_MISSING`) have had stale
  references since the wave C review removed their e-stops (`MHS/changes/WAVE-C.md`). This fix does not touch them, and
  they were left as they are.

## Result

- The SDK suite passes: 2,112 tests (14 of them new), 4 skipped.
- The registry suite (276 tests) and `validate.py --no-corpus` pass. `build_registry.py --check` finds no generated file
  that differs, so the registry needs no rebuild: its records copy `gate.digest`, which did not change.
- `collect.py --strict` over the 576 passing packages: all 576 pass the gate, and only `gh.amsikking/thorlabs_mcm3000`
  warns, as before (its PDF citation waits for a human, `MHS/changes/WAVE-B2.md`).
- `tools/oss_export_check.py` passes: the static checks and, inside the export, the SDK, registry and spec suites, the
  site build and check, the gates of the tutorial and of the four exemplars (the Gymnasium one included), and the
  OpenAI4S integration tests.
- `tools/build_changelog.py` indexes this record.
