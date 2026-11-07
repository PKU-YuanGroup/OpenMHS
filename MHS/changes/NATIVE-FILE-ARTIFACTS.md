# NATIVE-FILE-ARTIFACTS — files a native wrote, published as artifacts; the dodal Eiger re-authored

A direct driver can now publish files that its native wrote to disk through the endpoint's existing local artifact
store: `mhs.file_artifacts.NativeFileDirectory` reads bounded regular files of one declared directory without following
links and publishes one file or a deterministic ZIP bundle, with the sha256 and media type of every file in the
receipt. With it, and with a stop route that carries the operator's `DetectorParams`, the blocked dodal Eiger package
(triage class C, `NEEDS_ARTIFACTS` and `G6.ESTOP_FAILED`) passes after repair. No passing package's gate digest moved.

Draft written by Claude (claude-opus-5-5, a model and not a human) as phase-4 agent p4-artifacts in a private copy of
`snapshot-5` (`work/handoff-runs/claude-20261104/development/p4-artifacts/`); not yet applied to the tree. The SDK code
and the package repair are Claude-written; by the user's decisions of 2026-11-04 and 2026-11-05 a Claude Sonnet model
reviews them before they are merged. Evidence is fake `contract_checked` only: no detector, EPICS IOC, Odin file
writer or config server was contacted, and `reviewed_by` stays null.

## SDK changes

- `mhs/file_artifacts.py` (new, standard library only). `NativeFileDirectory(directory, *, media_types,
  max_file_bytes, cleanup, max_files=1, max_entries=4096)` declares one directory: its real absolute path (no
  symbolic link in any component, not the file-system root, not writable by every user), 1..16 suffix-to-media-type
  entries, a per-file bound of at most 16 MiB, at most 8 files per artifact and at most 65,536 directory entries per
  scan. `cleanup` must be `"keep"`: the SDK never modifies, renames or removes a file the native wrote; the published
  copy is the store's private blob, removed on expiry or endpoint close. The declaration fixes the directory's device
  and inode; each publication reopens the path from the root one component at a time with `O_NOFOLLOW` and refuses a
  replaced, relinked or world-writable directory. `publish(ctx, name)` publishes one file as its own bytes;
  `publish(ctx, [names])` a ZIP bundle (stored members, fixed dates and modes, `manifest.json` then `files/<name>`
  sorted). A name is one component of `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`; each file is checked with `lstat` before it
  is opened (links, directories, FIFOs, sockets and devices are never opened), opened with `O_NOFOLLOW` relative to
  the directory, must be the same inode, have one link and 1..`max_file_bytes` bytes, and is read in a bounded loop
  and refused when its size, mtime, ctime, link count or name binding changed. Sizes and the 4096-byte descriptor
  metadata are checked before any byte is read. `matching(pattern)` lists the regular files whose whole name matches,
  sorted, and refuses more than `max_files` matches or `max_entries` entries instead of truncating. Refusals are
  `MHS.CAPABILITY.OUTPUT_INVALID` with `details.reason` (`file_name`, `file_type`, `file_link`, `file_missing`,
  `file_size`, `file_count`, `file_changed`, `file_directory`, `file_unreadable`); no store is
  `MHS.DEVICE.NOT_READY`; a cancelled or e-stopped command raises `Cancelled` before the directory is opened, between
  files and before publication. The receipt descriptor keeps the store's digest, media type, size and expiry and adds
  `x-vendor["openmhs.native_files"]` = `{format: "openmhs.native-files.v1", cleanup, files: [{name, size_bytes,
  sha256, media_type}]}`. Publication goes through the command's existing `ArtifactPublisher`, so prepare, commit,
  abort, the original-session read rule, MCP resource reads and expiry are unchanged.
- `mhs/driver/check.py`: the gate's default artifact store (2 MiB per artifact, 32 MiB, 128 grants, 300 s) is also
  given to a driver with any binding whose resolved output declares `artifact_ref` or `image_ref`
  (`_declares_artifact_output`); before, only the image and point-cloud classes and three families got one. A driver
  that publishes nothing behaves the same with or without the store. `mhs.file_artifacts` joins `_GATE_MODULES` and
  `_CORE_MODULES`, so package code that patches it is reported as `G3.GATE_TAMPERED`.
- `mhs/file_artifacts.py` decides POSIX support from `os.name` and the flags, not from `os.open in
  os.supports_dir_fd`: the gate's device guard wraps `os.open` in its child processes, which made the first draft
  refuse every declaration inside the gate.
- Documentation: `sdk/docs/file-artifacts.md` (new: declaration, publication, bundle format, refusal table, what it
  does not do, the gate), a pointer in `sdk/docs/image-artifacts.md` and in the `NEEDS_ARTIFACTS` bullet of
  `sdk/docs/driver-authoring.md`. No spec, schema, catalogue or registry text changed; `INTERFACE.md` is unchanged
  (`--print-interface` gives no difference).
- Tests: `sdk/tests/test_file_artifacts.py` (26 tests: declaration, single files, names, links, hard links, special
  files, sizes, store bounds and capacity, cancellation, changes while reading including a swap to a link between the
  check and the open, replaced and relinked directories, bundles and their determinism, matching, a decorated driver
  through the endpoint with and without a store, the gate's store selection, a full G1-G8 gate run of a synthetic
  file-publishing package, and an MCP resource read of the published file).
- Mutants (`development/p4-artifacts/scripts/mutants.py`, logs `mutants-r0..r4.json`): 12 of the SDK rules and the
  gate rule and 7 of the package guards; all 19 are killed by the final tests. Round 0 left three survivors: the
  declaration's realpath check (also enforced by the `O_NOFOLLOW` walk; a test now asserts that the link is named),
  the e-stop clearing the package's staged flag and the package's acquisition-id check (tests added for both).

## Package

`gh.diamondlightsource/dodal` (`MHS/drivers/labs/diamondlightsource__dodal`): pass after repair (was blocked,
`HELPER_MISSING`, `NEEDS_ARTIFACTS`; the gate failed only `G6.ESTOP_FAILED`). Repaired as reviewer-author: the
DeepSeek attribution (`deepseek-v4.1-flash:1017`, run `helper-wave-1-007`), the source pin and the null `reviewed_by`
are kept, and the repair is the last `MODEL REVIEW` paragraph of `RESULT.json` (claude-opus-5-5, labelled second
review). The originals of every file are in the agent's `originals/packages/diamondlightsource__dodal/`.

- Native and stop route. The triage row offered `with_params`/`set_detector_parameters` with `stage`/`unstage`, or the
  ophyd-async FastCS Eiger; the FastCS Eiger is another repository's class that i03 builds only with `skip=True`
  (`src/dodal/beamlines/i03.py:193-200`), so the package keeps the card's classic `EigerDetector`. `native.connect`
  sets the deployment's config client as i03's fixture does (`i03.py:102-110`), validates the operator's
  `DetectorParams` (refusing parameters without `run_number`, because otherwise the acquisition id is derived again
  from the directory's nexus files on every access, `detector/detector.py:62-68`, `utils.py:128-142`), builds the
  device as i03 does (`i03.py:185-190`) and applies the parameters with `set_detector_parameters`
  (`eiger.py:101-120`); `with_params` is not used because it builds a device without an EPICS prefix
  (`eiger.py:89-99`). The driver refuses to open without `DetectorParams`. The native `stop()` then completes
  (`eiger.py:186-211`: Odin stopped, start timeout set, camera acquire cleared, ROI disabled at full size, dev/shm off);
  `disarm_detector` stays the safe-state action. The e-stop is reported unconfirmed (`OutcomeUnknown`, hence
  `SAFE_STATE_UNREACHED`) while `arming_status` is not done, because after a timed-out arming wait the upstream
  `finally` marks the disarm finished and every later `stop()` is a no-op (`eiger.py:210-213`) while the arming chain,
  which ends with `set_cam_acquire` (`eiger.py:462`), may still re-arm the camera.
- Surface. `stage` and `unstage` replace the `armed` write, which called `set_cam_acquire` outside the arming chain;
  `unstage` calls the upstream only for a collection this connection armed (otherwise `disarm_detector` only, because
  upstream `unstage` waits on `filewriters_finished`, which only the arming chain creates, `eiger.py:174, 405`, and
  would raise after disarming). A new read `acquisition_id` (`AcquisitionID_RBV`). A new action
  `x-cap.diamondlightsource.eiger-files.v1` publishes, as one ZIP, the regular `.h5` files directly in
  `DetectorParams.directory` whose names start with the acquisition id Odin reports and `_` (at most 8, each at most
  16 MiB, within the store's bound), refused while the meta listener or any node reports `Writing_RBV` 1
  (`create_finished_status`, `eiger_odin.py:125-129`). A data directory the helper refuses (for example one every
  user may write) disables only the file action, never the stop. Four extension capabilities are listed as catalogue
  requests.
- Fake. Follows `stage`, `async_stage`, `unstage`, `stop`, `change_roi_mode`, `disarm_detector`, `set_cam_acquire`,
  `is_armed`, the `disarming_status`/`arming_status`/`filewriters_finished` logic and Odin's `stop` and
  writers-finished condition; its arming chain applies only the steps that change what the package reads. When its
  writers finish it writes two placeholder files into its own private temporary directory (removed when the fake is
  collected); it starts disarmed with one earlier collection on disk. `test_driver.py` has 15 cases (the gate, a full
  collection with the published bytes and hashes checked against the files, the refusals, the e-stop cleanup, the
  no-op later stop, a stop waiting for an arming, the arming-chain guard, an unstage that raised, a refused data
  directory that disables only the file action).
- Facts: 32, every one checked with `show_refs.py` against the clone at `f96fef4e`.

| Package | Status | Gate digest |
|---|---|---|
| gh.diamondlightsource/dodal | pass (was blocked) | sha256:34177d668db2444e45c37994af3258a9fc5dd39e0fae5a9a231f6f2526cad433 |

The card still says `package_status: blocked` with the two blocked codes; it changes at the next registry rebuild,
and `prepare.py --sync` then refreshes `task.json`. The card's family stays `ophyd` (`OphydDriver`); `collect.py`
notes the `DECISION_DEVIATION` (a direct `Driver`), as it did before.

## Found, not fixed

- The python-object family has no binding for native files; a package whose native writes its output to files is a
  direct `Driver` (`file-artifacts.md`).
- Only the cleanup policy `keep` exists. A policy that removes the native's file after the receipt commits would need
  a post-commit hook in `ArtifactPublisher` and is not built: no package needs it, and removing a native's data file is
  the deployment's decision.
- The names Odin gives its files are not stated in the dodal clone; another naming makes the file action find nothing
  (fail-closed), and a human reviewer confirms it. A full-size Eiger 16M collection exceeds the artifact bound and is
  refused. The endpoint's 1 s default e-stop budget is shorter than the upstream waits inside `stop()` (an arming or an
  unfinished unstage, up to 60 s each); no sourced latency is declared, so such a stop reports unreached and is retried.
- A writer of the declared directory that swaps a regular file for a device node between the `lstat` and the
  `O_NOFOLLOW` open makes the endpoint open (never read) that node; the inode check then refuses the publication.
- The gate's child processes end with `os._exit`, so a fake that writes files cleans up only when it is
  garbage-collected. The dodal fake holds a weak reference back to itself from its Odin part (no cycle), which cut
  the directories left in the system temporary directory from about 50 to about 8 per gate run; the rest are fakes
  that uncollected SDK objects still reference when the child process exits. Package code cannot collect them (the
  gate forbids `gc`); a gate-side hook that closes fakes before `os._exit` would be an SDK change.
- The isolated-process simulator host and the Unity ROS-TCP route (the other class-C items) are other phase-4 items.

## Checks

Run in the agent's copy (logs in `development/p4-artifacts/logs/`), 2026-11-05:

- SDK suite (run once, after the last SDK change): 3,649 tests OK, 5 skipped (snapshot-5: 3,623; the 26 new tests).
  `tests/test_file_artifacts.py`: 26 OK. The dodal `test_driver.py`: 15 OK. Mutants: 19 of 19 killed
  (`mutants-r4.json`, after the last package change).
- The dodal gate: G1-G9 pass (G8 warns `SAFE014_NOT_APPLICABLE`, as before: no actuating input has a numeric bound),
  digest `sha256:34177d668db2444e45c37994af3258a9fc5dd39e0fae5a9a231f6f2526cad433`; `show_refs.py` read for all 32
  facts.
- `collect.py --strict` over every passing package: 716 of 716 pass; 715 digests equal snapshot-5's `RESULT.json`
  (which equal snapshot-3's for the 688 packages that passed there); one new pass (dodal); the only warning is the
  historical MCM3000 `UNVERIFIABLE_CITATION`.
- `validate.py --no-corpus`: 2 errors, both the dodal overlay against its unrebuilt card (`package_status`, record
  evidence). `build_registry.py --check`: 473 generated files differ, all from dodal's card change. A registry rebuild
  in a scratch copy (`scratch/registry-trial/`) moves dodal from wave 5 to wave 2 and changes 476 files under
  `MHS/registry/`: 233 cards and 233 records (dodal's two, and 464 that differ only in a renumbered `rank` in waves 2
  and 5), five family pages, `README.md` and `coverage.md` (wave counts), `index.json`, `index.jsonl` and
  `records.csv`. After that rebuild and `prepare.py --sync`
  (233 `task.json` refreshed, dodal's now `pass` with no blocked code), `validate.py --no-corpus` passes with 0 errors,
  the registry suite gives 345 OK and `collect.py --strict` passes dodal and four refreshed packages. The first
  `--check` run stopped with exit 2 because the agent edited the dodal package while it ran.
- OpenAI4S integration suite: 129 OK. The documentation site built into a scratch directory passes `site/check.py`
  (links, fragments, notices; `sdk/docs/file-artifacts.html` generated). `build_changelog.py --check`: OK (109
  fragments). `python3 -m mhs.driver --print-interface` equals `INTERFACE.md`.

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and required these edits when it was composed
with five other inputs onto the actual tree (`snapshot-5`). Each is logged with its before and after sha256 in the
integrator's `MERGE-LOG.json`.

| Edit | Review item | What changed |
|---|---|---|
| I15 | safety lens D1 | The dodal file action also refuses (`MHS.DEVICE.PRECONDITION_UNMET`) while an arming chain runs or the detector is armed: the upstream offers `is_armed()` (`src/dodal/devices/eiger.py:134-135`, `odin.fan.ready` 1 and `cam.acquire` 1), already a cited fact of the package. Between the arming and the first frame `Writing_RBV` may still be 0, so the files under the acquisition id may be an earlier collection's; `facts.md` now says that same-id files of an earlier collection cannot be told apart. |
| I15 | evidence lens F1 | The e-stop's upstream waits are disclosed and reported unreached: `facts.md` lists the safe-state disarm's wait (`disarm_detector`, up to the general status timeout, 20 s on i03, `eiger.py:425-426`) next to `stop()`'s 60 s waits, and `safe_state` says a `stop()` or disarm beyond the 1 s budget reports `SAFE_STATE_UNREACHED`, latched and retried. No `estop_latency_ms` is declared: no source states how long the waits take on a working detector. |
| I17 | safety lens M1 | A test of the final check alone: the descriptor unchanged, the name naming another inode, refused `file_changed` ("was replaced while it was read"). On this platform a rename changes the ctime, so the earlier `fstat` comparison refuses a real rename first; the test says so. |

Results: dodal `test_driver.py` 17 cases OK (2 new: the file action waits until the collection ended; a disarm that
outlasts the budget reports unreached with the latch held); 4 package mutants of I15 killed (no arming check, no
`is_armed` check, no `Writing_RBV` check, disarm not the safe state), unmutated control passes. The gate's findings are
unchanged, so the digest stays sha256:34177d668db2444e45c37994af3258a9fc5dd39e0fae5a9a231f6f2526cad433; one sentence
was added to the `MODEL REVIEW` paragraph of `RESULT.json`. `MHS/sdk/tests/test_file_artifacts.py`: 27 OK; the M1
mutant (the check replaced by `if False:`) is killed. No SDK code changed.
