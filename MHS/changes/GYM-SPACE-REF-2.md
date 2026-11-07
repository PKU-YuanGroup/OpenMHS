# GYM-SPACE-REF-2 — G4 reads `np.ones(n)`, and four placeholder action spaces turn out to be copies

GYM-SPACE-REF set `action_space_ref` on 71 of the 207 Gymnasium packages and left two lines of work
(`MHS/changes/GYM-SPACE-REF.md`, "Found, not fixed"). This change takes both. G4 now reads `np.ones(n)` and
`-np.ones([n])` as 1 and -1, so gymfc and pybullet_multigoal_gym cite their `Box`, and a model review of five fakes that
marked an upstream-looking space `# placeholder` found four exact copies, which now cite their line; squint's is not the
upstream's space.

## G4 reads `np.ones(n)`

gymfc's upstream writes its action space `spaces.Box(-np.ones(4), np.ones(4), dtype=np.float32)`
(`examples/gymfc_nf/envs/base.py:37`), pybullet_multigoal_gym's `spaces.Box(-np.ones([4]), np.ones([4]))`
(`pybullet_multigoal_gym/robots/kuka.py:113`). G4 read only the shape's 4 on these lines (and gymfc's 32 of `float32`),
not the bounds -1 and 1, so a ref to them would have warned `G4.REF_VALUE`. `_numbers_in` (`mhs.driver.check`) now reads a NumPy array of ones that is a whole
bound as 1, and with a unary minus as -1:

- the forms read: `np.ones(4)`, `np.ones([4])`, `np.ones((n,), dtype=np.float32)` and `numpy.ones(...)`, after `(`, `[`,
  `,`, `:` or `=`; the shape may be any expression, since G4 compares the numbers a line shows, never a width;
- the forms not read: an array that an operator scales or offsets on either side (`np.ones(n) * self.max_torque`,
  `2 * np.ones(n)`, `-1 * np.ones(size)`, `high - np.ones(2)`, `high += np.ones(2)`), one compared (`x == np.ones(2)`),
  one followed by an attribute or a subscript
  (`np.ones(4).astype(...)`), and `jnp.ones`, `self.np.ones` and `np.ones_like`. Where the scale is a literal
  (`np.ones(n) * -1.`), G4 already reads the literal.

The reading is narrow on purpose: a number more that a line shows can only remove a `REF_VALUE` warning, and a reading that
is too eager would hide a ref that cites the wrong line.

**No other package's findings change.** Before the change, a scan read every cited span G4 could value-check, as G4 reads
it (the clone at the pinned commit): the ref of every limit with a `source` in every package's `reference.json`, and every
`path:LINE` string in every `driver.py`, 3,534 spans in all. Three limit spans write `np.ones(`: isaacgymenvs and
omniisaacgymenvs scale theirs by the literals `-1.` and `1.`, which G4 already reads, and mujoco-drones-gym's span also
writes `[-1, 1]` in a docstring. `_unshown` gives the same result under the old and the new `check.py` for every limit rule;
after the change the same comparison differs for the two new refs only (the old reading misses all eight bounds, the new one
none). The one `REF_VALUE` in any package's `check-report.json` (as7265x-spectrometer, 254 on `spectrometer.py:280`) is
not on such a line.

## The `VAR` packages

GYM-SPACE-REF gave 48 packages no ref because their upstream builds the bounds from names or computes them (reason `VAR` in
its `decisions.json`). Each was re-read for the new reading: the lines of the pinned upstream's Python code that the
reading reads a 1 or -1 from (`git grep` at the commit, filtered by the new expression), and the code that builds the space
the package serves.

| Outcome | Packages |
|---|---|
| unlocked: the served space is a `Box` of `-np.ones` and `np.ones` | 2 (gymfc, pybullet_multigoal_gym) |
| `Box(-high, high)` over an array of ones, scaled or not: one line shows the upper bound, none writes the lower | 5 (pybullet-gym, phoenix-drone-simulation, gym-dart, roboverse, fancy_gym) |
| every `np.ones` the reading reads lies outside the served action space: another environment, a training wrapper, an observation bound, a mask, a gain or a test | 24 |
| no line the reading reads | 17 |

The five of the second row are the near misses: pybullet-gym writes `high = np.ones([action_dim])` and then
`gym.spaces.Box(-high, high)` (`robot_bases.py:24-25`), so the two lines show 1 and not -1. Reading `-high` as -1 would read
through a name, which G4 does not do. The decision and its reason for each of the 48 are in
`work/handoff-runs/gym-space-ref-2/decisions.json` (not exported).

## The placeholder spaces

Five fakes marked `# placeholder` a space whose numbers looked like the upstream's. Each was reviewed as a model reviewer
(`MHS/handoff/REVIEW.md` section 5) against the upstream at the pinned commit: the registered environment, the configuration
the package serves (`env_kwargs`, the registration's kwargs, the defaults), every class on the way that could replace the
space, and the line that writes its numbers. The mark was dropped, and the line cited, only where the fake's bounds and
width are an exact copy for that configuration.

| Package | Verdict | `action_space_ref` |
|---|---|---|
| gym-duckietown (`MultiMap-v0`) | copy. `MultiMapEnv` copies the space of the `DuckietownEnv` it builds (`multimap_env.py:22`), and `DuckietownEnv` replaces the Simulator's `Box(-1, 1, shape=(2,))` with the same bounds | `src/gym_duckietown/envs/duckietown_env.py:19`, not the `simulator.py:309` the fake's comment named |
| softgym (`PourWaterPosControl-v0`) | copy of the `rotation_bottom` space that the driver's `env_kwargs` select; `gym.make` wraps no `NormalizedEnv` | `softgym/envs/pour_water.py:52-53`, the lines that write the bounds the `Box` takes |
| maniskill-vitac2025 (`PegInsertionRandomizedMarkerEnv-v1`) | copy: `Box(low=-1, high=1, shape=(3,))` for every configuration, since `peg_insertion.py:292` asserts the width; the registration passes no kwargs and the subclass sets no space | `Track_1/envs/peg_insertion.py:294-296` |
| jsbgym (`C172-HeadingControlTask-Shaping.STANDARD-NoFG-v0`) | copy: `JsbSimEnv` takes the `Box` that `FlightTask.get_action_space` builds (`tasks.py:236-239`) from HeadingControlTask's three action variables (`tasks.py:279`), each -1..1; `NoFGJsbSimEnv` sets no space | `jsbgym/properties.py:93-101`, the three properties that write the bounds |
| squint (`SO101LiftCube-v1`) | **not a copy**: the fake's bounds are the `pd_joint_target_delta_pos` controller's per-step deltas, which ManiSkill rescales from a `[-1, 1]` action (below) | none; the mark stays |

In each of the four packages `fake.py` no longer marks the two action-bound constants `# placeholder`, and their comment
cites the line they copy; where the module docstring said that every number of the file is placeholder test data
(duckietown, maniskill-vitac2025, jsbgym), it now excepts the action bounds. `driver.py` sets `action_space_ref`.

## The packages

- **Drivers.** The six `driver.py` got one line after `backends`, as in GYM-SPACE-REF: an f-string over the module constant
  that names the cited file (`f"{KUKA}:113"`, `f"{BASE}:37"`, `f"{POUR}:52-53"`, `f"{PEG}:294-296"`,
  `f"{PROPERTIES}:93-101"`), and a string literal for gym-duckietown, whose driver names no constant for that file.
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md` of the six. A
  comparison with the originals shows only the `cap.world.step.v1` `action.values` limit, now `source: upstream_code` with the
  cited ref instead of `ref: action_space of the fake backend .fake:FakeX`, and `provenance.manifest_digest`.
- **Gate.** `python3 -m mhs.driver check <dir> --backend fake` passes for all six with no G4 finding. Every digest is the one
  `RESULT.json` already recorded: the stable digest covers the gate's findings, and no finding changed. A baseline run with the
  new SDK before the package edits gave the same six digests.
- **Results.** Each `RESULT.json` got the digest of that run and one sentence at the end of its `MODEL REVIEW` paragraph that
  names the files changed (`driver.py`; `fake.py` too in the four reviewed packages) and the ref. `driver.lock.json` is
  untouched: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- **Tool sizes.** The MCP projection never prints a limit's `source` or `ref`, so no tool description changes.
- **Originals.** Every file of the six packages as it was, and `check.py`, `test_ref_values.py`, `REVIEW.md`,
  `driver-authoring.md` and `CHANGELOG.md`, are in `work/handoff-runs/gym-space-ref-2/originals/` (not exported), with the
  scripts that made the change (`apply.py`, `run_gates.py`, `update_results.py`, `scan_refs.py`, `make_decisions.py`) and
  their logs.

## Tests and docs

- `tests/driver/test_ref_values.py` `test_an_array_of_ones_shows_one`: gymfc's and pybullet_multigoal_gym's lines and
  `Box(low=-np.ones(11), high=numpy.ones((11,), ...))` show -1 and 1; `high = np.ones([action_dim])` shows 1 and not -1; a
  bound past them is still reported; scaled, offset and compared arrays, `jnp.ones` and `np.ones_like` show no 1 or -1.
- `MHS/handoff/REVIEW.md` item 2 lists `np.ones(4)` and `-np.ones([4])` among the forms G4 reads, and says that a scaled one
  is not read. `MHS/sdk/docs/driver-authoring.md` section 5 says that `Box(-np.ones(4), np.ones(4))` shows -1 and 1, and
  that `Box(-high, high)` over `high = np.ones(n)` gets no ref.

## Found, not fixed

- **squint's step bounds are too tight.** The fake serves the deltas `[-0.1] * 5 + [-0.2]` .. `[0.1] * 5 + [0.2]` of the
  `pd_joint_target_delta_pos` controller (`envs/robot/so101.py:97-109`), the default of `envs/lift.py:61`. That config does
  not set `normalize_action`, whose default is True (`mani_skill/agents/controllers/pd_joint_pos.py:131`), and a normalised
  controller replaces its space with `Box(-1, 1)` of the same shape and rescales the action to the deltas
  (`base_controller.py:70-72`, `gym_utils.py:110-112`). So the upstream action space is `Box(-1, 1, (6,))`, and the step
  contract refuses most of it. Read in the ManiSkill clone `robots/mani-skill/maniskill` at `62ff3a58`, because squint
  depends on an unpinned `mani_skill_nightly` (`environment.yaml:15`). A fix would serve `[-1, 1]` in the fake, with the
  controller's scaling in its step and its tests.
- **gym-duckietown's action meaning.** The Fact on `simulator.py:308-309` ("the two wheel torques", also a row of
  `facts.md`), the fake's `step` ("Apply two wheel torques") and the `RESULT.json` note ("-1 to 1 per wheel") describe the
  Simulator's action, but
  `MultiMap-v0` serves `DuckietownEnv`'s, whose `step` reads a velocity and a steering angle and converts them to wheel
  commands (`envs/duckietown_env.py:36-63`). The bounds are equal, so the ref holds; the meaning the package gives them does
  not. The fake's dynamics are a placeholder either way.
- **`Box(-high, high)` over an array of ones.** pybullet-gym, phoenix-drone-simulation, gym-dart, roboverse and fancy_gym
  write the upper bound on one line and its negation through the name on the next. They could cite their space only if G4
  read the negation of a name defined in the cited span; that reads through names and was not done.

## Result

- The SDK suite passes: 2,114 tests (1 new), 4 skipped.
- The registry suite (276 tests) and `validate.py --no-corpus` pass. `build_registry.py --check` finds no generated file
  that differs: the registry copies `gate.digest`, which did not change. (A check that the SRB-WIDTH session ran while the
  six packages were being edited stopped because `MHS/drivers/**` changed during the build; its re-run after the edits and
  this change's own run find no difference.)
- `collect.py --strict` over the 576 passing packages, in six parallel chunks of 96 because collect.py runs one gate at a
  time: all 576 pass the gate, and only `gh.amsikking/thorlabs_mcm3000` warns, as before (its PDF citation waits for a
  human, `MHS/changes/WAVE-B2.md`). No package reports `RESULT_DIGEST_STALE`.
- `tools/build_changelog.py` indexes this record.
- `tools/oss_export_check.py`, run after the checks above, passes: in a fresh export of the 13,255 tracked files it runs the
  generators' `--check` modes, the SDK, registry and spec suites, the site build and its freshness check, the thermostat
  gate, the gates of the four exemplars and the OpenAI4S integration tests. Only this section of the record was written
  after it.
