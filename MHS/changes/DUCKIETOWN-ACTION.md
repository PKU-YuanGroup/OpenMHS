# DUCKIETOWN-ACTION — gym-duckietown's two action values are a velocity and a steering angle

GYM-SPACE-REF-2 found that `gh.duckietown/gym-duckietown` calls the two values of the `MultiMap-v0` action wheel torques,
while the environment the package serves reads them as a velocity and a steering angle (`MHS/changes/GYM-SPACE-REF-2.md`,
"Found, not fixed"). A reading of the clone at the pinned commit `c76a7fec7f739db4f624f40ca83ce99383665558` confirms it.
The Facts, `facts.md`, the driver's docstring and the fake now say so, and the fake converts the two values to wheel
commands as the upstream does. The bounds, the `action_space_ref` and the gate's findings and digest did not change.

## The reading

- `MultiMap-v0` is registered with the entry point `gym_duckietown.envs:MultiMapEnv` and no kwargs
  (`src/gym_duckietown/__init__.py:48`). `MultiMapEnv` builds one `DuckietownEnv(map_name=..., **kwargs)` for each map,
  copies its action space (`src/gym_duckietown/envs/multimap_env.py:17-24`) and hands every action to the current one
  (`:51-54`).
- `DuckietownEnv`'s class docstring says that it controls the simulator with a velocity and a steering angle instead of
  differential drive motor velocities (`src/gym_duckietown/envs/duckietown_env.py:9-13`). It replaces the Simulator's
  `Box(-1, 1, shape=(2,))` (`simulator.py:308-309`, commented as a two-tuple of wheel torques) with
  `Box(low=[-1, -1], high=[1, 1], float32)` (`:19`).
- Its `step` unpacks the action as `vel, angle` (`:37`), computes the two motors' rotation rates
  `(vel +/- 0.5 * angle * wheel_dist) / radius` (`:40`, `:50-51`), converts them to duty cycles with `(gain +/- trim) / k`
  (`:47-48`, `:53-55`), limits each to `+/-limit` (`:57-59`) and calls `Simulator.step` with `[left, right]` (`:61-63`).
  So the Simulator's clip to [-1, 1] (`simulator.py:1670`) and its `info["Simulator"]["action"]` (`:1592`) see the two duty
  cycles, never the agent's values. `DuckietownEnv.step` adds its own `info["DuckietownEnv"]` (`:64-71`).
- The defaults are gain 1.0, trim 0.0, radius 0.0318, k 27.0 and limit 1.0 (`:15`), and `MultiMap-v0` keeps them. The
  wheel distance is the Simulator's `wheel_dist`, its nominal `WHEEL_DIST` 0.102 (`simulator.py:134`) perturbed at every
  reset (`:597`) under the default `domain_rand=True` (`:213`).

So the reading holds. The bounds are the same, -1 to 1 for each value, so the package's `action_space_ref`
(`envs/duckietown_env.py:19`) holds; the meaning the package gave the values did not. With these defaults and the nominal
wheel distance, a velocity alone gives both wheels `vel / 0.8586`, a steering angle alone gives them -/+ `0.0594 * angle`,
and at velocity 1 both duty cycles reach the limit whatever the steering. The upstream itself names the Simulator's
input three ways: wheel torques (`simulator.py:308`), differential drive motor velocities (`envs/duckietown_env.py:12`)
and duty cycles (`:53`); the package states none of them as a Fact about the agent's action any more.

## The package

- **`driver.py`.** The Fact on `simulator.py:308-309` ("The action space is Box(low=-1, high=1, shape=(2,),
  dtype=float32): the two wheel torques") is now three Facts on `envs/duckietown_env.py`: the class docstring (`:9-13`),
  the space (`:19`) and the conversion of `step` (`:36-63`). The Fact on `simulator.py:1670` names `Simulator.step`
  ("Simulator.step clips its action to [-1, 1] before applying it"), since under `DuckietownEnv` that action is the pair of
  duty cycles. The module docstring names the values `[vel, angle]` where it said `[left, right]`. A module constant
  `DUCKIETOWN` names the file, and `action_space_ref = f"{DUCKIETOWN}:19"` is the same string as before. A fifth fidelity
  gap says that the fake converts the two values as `DuckietownEnv.step` does, with its default constants and the nominal
  wheel distance, and moves its pose from the wheel commands with a placeholder speed and turn rate.
- **`fake.py`.** `step` reads `vel, angle` and computes the wheel commands with `DuckietownEnv.step`'s formula. Its
  constants `GAIN`, `TRIM`, `WHEEL_RADIUS`, `MOTOR_CONSTANT` and `WHEEL_LIMIT` copy the defaults of `:15` and are not
  marked placeholder; `WHEEL_DIST` (0.102) is marked `# placeholder`, because the upstream randomizes it. The pose update
  from the two commands is the fake's placeholder differential drive, unchanged (`MAX_SPEED`, `TURN_RATE`).
  `info["Simulator"]["action"]` now holds the wheel commands, as the upstream's does, and `info["DuckietownEnv"]` holds the
  upstream's six keys (`"train"` is the upstream's key for the trim). The module docstring, which said that every number
  but the action bounds is placeholder data, now excepts the conversion constants as well.
- **`test_driver.py`.** A new case, `test_the_action_is_a_velocity_and_a_steering_angle`, reads the step's info from the
  world state: a velocity alone gives both wheels `0.5 / (0.0318 * 27)`, a steering angle alone gives them
  -/+ `0.5 * 0.102 / (0.0318 * 27)`, velocity 1 with steering 1 puts both at the limit, and `omega_r` and `omega_l` are the
  rotation rates. `test_an_invalid_pose_ends_the_episode` stepped `[1.0, 0.0]` for 60 ticks, which is now full speed
  straight ahead and stays in the lane; it steps `[0.5, 1.0]` for up to 150 ticks, and the episode ends at tick 98.
- **`facts.md`.** The table follows the Facts. The Limits paragraph names the two values and gives the bound's present
  source, `upstream_code` with the ref `src/gym_duckietown/envs/duckietown_env.py:19`, where it named
  `MultiMap-v0:action_space`, which has not been the bound's source since GYM-LIMITS. The fidelity paragraph names the
  new gap.
- **References.** `python3 -m mhs.driver reference <dir>` regenerated `reference.json` and `REFERENCE.md`: the facts, the
  gaps (only `reference.json` lists them) and `provenance.manifest_digest` changed, nothing else. The step bound is still
  `[-1.0, -1.0] .. [1.0, 1.0]`, `upstream_code: src/gym_duckietown/envs/duckietown_env.py:19`.
- **Tool descriptions.** The MCP projection prints the first six Facts and the first two fidelity gaps into each tool
  description (`mhs/mcp.py`). The replaced Fact was the seventh and the new gap is the fifth, so no tool description
  changes.
- **Result.** `RESULT.json` got one sentence at the end of its `MODEL REVIEW` paragraph that names the changed files and
  says that the "-1 to 1 per wheel" of the author's paragraph is -1 to 1 for each of the two values
  (`MHS/handoff/REVIEW.md` section 5); the author's paragraph stays as written, as in SRB-WIDTH. `gate.digest` is the
  re-run gate's, `sha256:7a38d6c5...`, the value it had: the stable digest covers the gate's findings, and none changed.
  `driver.lock.json` is untouched: `authored_by.kind` stays `model` and `reviewed_by` stays null.
- **Originals.** Every file of the package as it was, and `CHANGELOG.md`, are in
  `work/handoff-runs/duckietown-action/originals/` (not exported), with `update_result.py`, which wrote the sentence, and
  the logs.

## Result

- `python3 -m mhs.driver check <dir> --backend fake` passes. G4 has no finding; the warnings are the ones `RESULT.json`
  names (G6.NO_NATIVE_CALL, G8.NO_UNIT x4); G9, which runs the package's cases with the new one, passes; the digest is
  unchanged. A baseline run before the edits printed the same digest, and the nine `MultiMapCases` also pass on their own.
- `collect.py <dir> --strict` passes, with no note beyond the gate's warnings.
- `validate.py --no-corpus` passes.
- `build_registry.py --check`, run after the package edits (04:07-04:18 PDT), finds no generated file that differs, so the
  registry needs no rebuild: its record of the package copies the gate digest, the status and the evidence state, and none
  of them changed.
- `tools/build_changelog.py` indexes this record.
- Follow-up verification on 2026-11-02: `tools/oss_export_check.py` passes on the combined state containing this
  change and the other completed changes. In a fresh export of the 13,259 tracked files, the handoff baseline run
  checks the generators, the SDK, registry and spec suites, the site build and its freshness, the thermostat gate,
  the gates of the four exemplars and the OpenAI4S integration tests. This is the subsequent baseline result, not a
  check run during the original focused session.

## Found, not fixed

- **Other `facts.md` pages name an old source.** 117 other Gymnasium packages' `facts.md` (a scan of the pages that write
  `` `<env_id>:action_space` ``) give that as the source of the step bound, while their `reference.json` gives the fake
  backend's space (GYM-LIMITS) or a cited line (GYM-SPACE-REF, GYM-SPACE-REF-2). `facts.md` is written by hand, and no
  check compares it with the reference.
- **The fake's `msg`.** The fake puts the done code (`invalid-pose`, `max-steps-reached`, `in-progress`) in
  `info["Simulator"]["msg"]`; the upstream puts its sentence there, empty while the episode runs
  (`simulator.py:1681`, `:1685-1705`).
- **Weak steering in the fake.** The steering value moves the duty cycles by at most 0.0594 each, and the fake's placeholder
  `TURN_RATE` 2.0 turns that into about 0.12 rad/s, so the fake turns slowly. Its dynamics are a named gap and were not
  tuned.
