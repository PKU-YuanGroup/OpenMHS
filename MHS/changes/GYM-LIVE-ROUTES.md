# GYM-LIVE-ROUTES — asynchronous environments, dm_env environments and resets that integrate physics

Three opt-in Gymnasium profiles serve live routes the synchronous bridge could not: an owned event loop for `async def step` (`asyncio_owned_loop_v1`), a dm_env adapter that maps a `TimeStep` explicitly (`dm_env_v1`), and physics timing for resets that integrate physics, with an explicit checkpoint opt-out. Undeclared backends keep their behavior and gate digests. ProjectAirSim and SimplerEnv pass after review; RoboPianist stays blocked.

Draft written by Claude (claude-opus-5-5, a model and not a human) in a private copy of the 2026-11-05 snapshot (`work/handoff-runs/claude-20261104/development/b1-gym-features/`); not yet applied to the tree. The SDK code is Claude-written; by the user's decision of 2026-11-04 it was reviewed by Claude Sonnet (review s8: the SDK change and SimplerEnv to fix, ProjectAirSim accepted). Every s8 finding was fixed in a second round (below); the two package passes depend on the SDK change.

## SDK changes

- `mhs/bridge/gym_async.py` (new). `asyncio_owned_loop_v1` declares, per backend, which of `step` and `reset` are coroutines, the exact native `reset` keywords, local bounds for step, reset and close, and optionally a remote stop and a stop probe (public attribute paths) with their own bounds. One daemon thread runs one event loop and is the only thread that calls step, reset, close, stop and probe. A call that outlives its bound is never cancelled locally: the command's outcome is `unknown`, the call stays owned (new native work is refused with `MHS.DEVICE.BUSY`, safety status reports the safe state unachieved, safety reset is refused, cleanup is deferred), its late outcome is recorded and never applied, and steps need an explicit world reset afterwards. No world call is dispatched after an e-stop engaged or after the operation was cancelled (checked atomically with submission). The e-stop runs the declared stop on the owned loop, then the probe (only exactly `True` confirms), then a bounded wait for owned work; otherwise the outcome is unknown, a queued stop stays owned and is never duplicated, the endpoint keeps the latch and retries, and each retry stops afresh. Without a declared stop, the e-stop is the software latch and the endpoint reports `SAFE_STATE_UNREACHED` while work is owned. Close stops, closes and shuts the loop down, each bounded, exactly once, deferred while work is owned; a hung close is reported `unsettled`. An environment whose native reset takes no seed serves no seed capability and claims no seeded determinism; its reset input `seed` stays for the class contract, described as not used (the MuJoCo family's precedent).
- `mhs/bridge/dm_env_adapter.py` (new). `dm_env_v1` wraps a dm_env environment: `reset` must be `FIRST`; `LAST` with discount 0 is terminated and with a positive discount truncated; a `FIRST` from `step`, a missing reward, a missing or out-of-range discount or an unknown step type is a fault. `action_spec` becomes the step envelope (`BoundedArray` bounds broadcast per element, `DiscreteArray` a Discrete, an unbounded `Array` no limits); actions are converted to the spec's dtype and shape and validated by the spec. Independently of the profile, the Gymnasium tuple path now refuses any result carrying `step_type` and `discount`, so a `TimeStep` is never read as `(observation, reward, done, info)`.
- `mhs/bridge/simulation_timing.py`. `physics_ticks_v1` accepts `reset_advances_physics: true` with a required `reset_clock` (`restart` or `continue`) and `max_reset_ticks`. Every reset is measured; a count off the timestep grid or beyond the bound is a timing fault. Reset ticks are never episode ticks; the reset binding carries the descriptor and its receipt reports `reset_integrated_ticks` (step receipts of such a backend report reset ticks inside the command). Declarations without it produce byte-identical descriptors and receipts (pinned by a test against the original output).
- Synchronous simulators (review finding S8-01, present before this change): every Gymnasium and MuJoCo bridge holds its mutation lock while a native step, reset or checkpoint call runs, and the Gym bridge now reports the safe state unachieved while it is held, as the MuJoCo bridge already did. The endpoint's e-stop attempt (`server.py`) gives such a bridge the rest of the e-stop budget for that call to end (`settle_native_work`); the wait observes the lock without the server lock and is bounded, so it cannot deadlock. After the re-check (R8-01) the endpoint consults only the SDK's own Gym and MuJoCo methods, compared by function object (a package override or instance attribute is ignored), and bounds the call itself with a daemon thread joined for the remaining budget; a hook that raises or does not return counts as not settled, and `safety_status` decides. After the integrator found
`test_descriptor_resolution_is_owned_across_stop_and_reset` failing (R9), the attempt no longer waits while a checkpoint
restore owns the device: the e-stop had spent its 1000 ms budget waiting on the lock of a restore that the test
releases only after the e-stop answers, so that restore missed its own 1000 ms deadline. The settle step never blocked
the restore itself (the restore reads the e-stop sequence set at latch time), but the attempt already reports a restore
unachieved and the restore's end re-asserts the stop path, so the wait gained nothing; steps and resets keep it. A call that ends in time gives a confirmed e-stop; otherwise `SAFE_STATE_UNREACHED` with the latch kept and the background retry (SAFE-040). A command cancelled while it waited for the lock now dispatches nothing (the implicit first reset ran before the per-tick check), and Gym safety reset is refused while a native call runs.
- dm_env strictness (S8-02, S8-03): a step type must be an exact integer (int, the enum or a NumPy integer; a float or a string is refused, not converted), and an integer-dtype action spec publishes integer items, so a non-integral value is refused before any native call; the adapter refuses it again instead of truncating.
- `mhs/bridge/gym_checkpoint.py`, `mhs/driver/families.py`. `checkpoint_by_backend` accepts `{"profile": "none", "reason": ...}`: no snapshots on that backend, the reason in its fidelity gaps, a `snapshot_restore=True` claim for it refused, projection across backends refused. `GymnasiumDriver` gains `async_by_backend` and `dm_env_by_backend`, publishes a declared remote stop as the native e-stop path, operating notes, and the reset input and determinism adjustments above.
- Documentation: `sdk/docs/gym-live-routes.md` (new: also the synchronous e-stop, the idempotent remote stop, the endpoint's cancel-then-stop order the dispatch guard relies on, construction outside the owned loop, and the informational MID discount), `simulation-timing.md`, `gym-checkpoints.md`, `bridges.md`, `sdk/docs/README.md`.

Self-review closed three issues before any package used the code: a step admitted just before an e-stop could have been dispatched after the remote stop (now refused under the loop's lock); a cancelled operation could reach the loop after the call-start check (same guard); and a waiter could, in principle, see its own settled call as still owned because `concurrent.futures` wakes waiters before done-callbacks (ownership is now released inside the coroutine before delivery; a 2,000-iteration counterfactual did not reproduce the old order under CPython's GIL, so this is recorded as a theoretical race, not a reproduced defect).

## Packages

- `gh.iamaisim/projectairsim`: pass after repair (was blocked, HELPER_MISSING; accepted by review s8, whose text additions were made: the stop cannot interrupt the blocking `continue_for_sim_time`, and `is_paused` reads the scene clock without Unreal's confirmation; the lock lists the documented client install and the `gym==0.18.3` pin). Both backends declare the owned loop with the native calling convention (coroutine step, argument-free reset) and the remote stop `world.pause` read back by `world.is_paused` (the scene's clock is steppable and pauses on start; the server's ContinueForSimTime returns paused). The fake keeps that convention with analytic kinematics; `sim.py` builds the pinned environment lazily and disconnects a client that a failed constructor connected. Gate digest changed (intended: seed capability removed, native e-stop path, new cases).
- `gh.simpler-env/maniskill2_real2sim`: pass after repair (was blocked, SDK_BUG; its `safe_state` now says exactly what holds after review s8: no new step or reset after an e-stop, and a running native step or reset completes before the e-stop confirms). The live backend counts each completed `scene.step()` at its two integration sites (a package-owned counter: SAPIEN exposes no physics clock to the pinned code) and declares 25 physics ticks per control call and settling resets of at most 1,250 ticks; it opts out of snapshots (native `get_state` is incomplete). The fake, its JSON checkpoint and the gate digest are unchanged.
- `gh.google-research/robopianist`: blocked retained (no package code). The adapter removes the misreading risk, but the card routes to MujocoDriver, the served composer Environment lies outside the clone (G7 has no rule for factory-built environments and would pass only on MAYBE_ABSENT warnings with the Task class as native), importing the package needs a downloaded soundfont, and the hand action bounds live in a git submodule the pinned tree cannot read. Authoring is a new author task.

Every package keeps its source pin, model authorship and null `reviewed_by`; each review is the last paragraph of its `RESULT.json`.

## Found, not fixed

- G7 rule for environments built by a factory function in the clone whose class is outside it (RoboPianist; also the BiGym env-factory item of `WAVE-A.md`).
- Citations into git submodules (the pinned tree cannot read them; RoboPianist's hand XML).
- The asynchronous profile does not combine with physics timing or JSON checkpoints, and the dm_env profile does not combine with timing or checkpoints; dm_control's physics clock could serve timing later.
- The Gym bridge keeps no latch of its own: its dispatch guard relies on the endpoint cancelling operations before it engages the stop path (true of the stock server); a direct caller without a cancel event is not refused.
- A declared remote stop is sent once per e-stop attempt and once before close; it must be idempotent (a deployment assumption).

## Result

In the private copy (Python 3.14.7, the validated environment, no bytecode), after the review fix round:

- New SDK tests: 60 (`tests/bridges/test_gym_async.py` 21, `test_gym_dm_env.py` 12, `test_gymnasium_timing_reset.py` 9,
  `test_gym_sync_safety.py` 11, `tests/driver/test_gym_live_routes.py` 7); the first 55 passed five of five repetitions
  before the re-check round added the four hook-trust cases (a raising hook, a hook that does not return, package
  overrides and instance attributes ignored, the driver's delegate) and R9 the held-restore case. With the pre-R9
  server both that case and `test_descriptor_resolution_is_owned_across_stop_and_reset` fail; with R9 both pass.
- Final SDK suite (after R9): 3,272 tests OK, 6 skipped (the 3,212 of the snapshot plus the 60 new), 501 s;
  `tests/test_mujoco_checkpoint.py` 12, `tests/safety` 478, `tests/bridges` 634 and `tests/driver` 753 OK. The original
  physics_ticks_v1 descriptor and report are byte-identical (pinned). Counterfactuals: without the settle hook the
  bounded-wait e-stop test fails; with the snapshot's Gym `safety_status` an in-flight step is reported safe; without
  the owned-work refusal in `OwnedLoop.shutdown` the new shutdown test fails.
- SDK suite: 3,267 tests OK, 6 skipped (the 3,212 of the snapshot plus the then 55 new), 544 s, before the re-check
  round; after it `tests/bridges` and `tests/driver` were run again (results below, R8 line). (Before the fix round, two full runs made while other agents loaded the machine failed only
  on timing-bound tests outside the Gym code, which an unmodified snapshot copy also failed under the same load.)
- Re-check round (R8): `tests/bridges` 633 and `tests/driver` 753 OK; both package gates and `collect.py --strict`
  over all 349 passing Gymnasium and MuJoCo packages pass with no digest moved; `show_refs.py` reports 0 bad
  citations for ProjectAirSim (its `action_space_ref` is now a literal path:LINE).
- Package cases: ProjectAirSim 13 (`check_driver` kept), SimplerEnv 19. Full G1-G9 gates pass: ProjectAirSim
  `sha256:8735254511be6088b86d3acc864bccaf022a953fd4932166a921f397cef1c7b3` (was
  `sha256:e536012ab81f07ed82bfff4a6088c0b90cecc353a9a25dd7ee753a3e66f53f2e`, re-recorded: the seed capability, the
  native e-stop path and the cases changed), SimplerEnv `sha256:11756923a6dd882aa348a47ed0f157ce59c7aea99e4aade3b4210d14e2f050c7`
  (unchanged). RoboPianist's gate fails G1, G2, G3 and G9 (no package code), as before.
- `collect.py --strict`: before the fix round over all 683 passing packages (681 plus the two repairs), after it over
  all 349 passing Gymnasium and MuJoCo packages. Every package passes, every fresh digest equals its `RESULT.json`, and
  only ProjectAirSim's digest differs from the snapshot; the only warning is the pre-existing `UNVERIFIABLE_CITATION`
  of `gh.amsikking/thorlabs_mcm3000` (not a Gym or MuJoCo package).
- `validate.py --no-corpus` (first round) reports only the four comparisons a registry rebuild settles (card
  `package_status` and record evidence of the two repaired packages) and passes with `--allow-stale-cards`; the
  registry suite then passed 309 of 310, the exception being the same four comparisons.
- `tools/build_changelog.py` regenerated the index (97 fragments); `--check` passes. `MHS/sdk/INTERFACE.md` is unchanged.

Not run: the registry rebuild and `prepare.py --sync` (the two cards still say blocked until the rebuild; then both
gates must be re-run), `build_registry.py --check`, the OpenAI4S integration tests, `tools/oss_export_check.py`, any
Project AirSim server, Unreal, flight controller, SAPIEN, dm_control, MuJoCo or hardware.
