# SUBMODULES-AND-FACTORY-ENVIRONMENTS — git submodules read at their gitlink, and a G7 rule for factory-built environments

The gate, `show_refs.py` and `collect.py` now read a citation into a git submodule of a pinned clone (`<submodule path>/...`) at the commit the pinned tree's gitlink records, from the submodule's own object store, and only while the submodule is declared, checked out and at exactly that commit; anything else fails closed. Gate G7 gains a rule for a Gymnasium environment that a factory function of the clone builds from a class outside it (`native_factory`). RoboPianist passes on them; vision-agh/crazyflie-sim's submodule finding is resolved, but it stays blocked on its stop.

Written by Claude (claude-opus-5-5, a model and not a human) as the phase-3 agent p3-sdk-gaps-a in a private copy of snapshot-3 (`work/handoff-runs/claude-20261104/development/p3-sdk-gaps-a/`); not yet applied to the tree. By the user's decisions of 2026-11-04 and 2026-11-05 a Claude Sonnet model reviews the SDK change and both packages before they are merged. Evidence is `contract_checked` on fakes only: no RoboPianist, dm_control, MuJoCo, ROS, Gazebo or CrazySim code was installed or run, and nothing here claims a live or hardware run.

## Git submodules (SDK, `mhs/driver/upstream.py`)

- A path that the pinned tree cannot read is checked against the submodules of the pinned `.gitmodules` (read from the object store and parsed without git: a name or path that is not a clean relative path, a section with two paths, a path claimed by two names or a continued line leaves that entry out). When the path lies under a declared path that `ls-tree` shows as a gitlink (mode 160000), the rest of the path is read with `git --git-dir=<submodule git dir> cat-file` at the gitlink commit. The same read-only plumbing as for the parent (`--no-optional-locks`, an empty hooks directory) is used; nothing is checked out or written.
- The submodule is read only when its checkout path has no symbolic link, its `.git` is a `gitdir:` file naming exactly `<parent git dir>/modules/<name>` (or, the layout of git before 1.7.8, a directory), that git directory lies inside the clone and has an object store, its `HEAD` (read from the file, a detached id or a loose or packed ref) equals the gitlink, and the store holds the commit. Otherwise nothing under it is read, and `UpstreamTree.submodule_refusals` holds the reason: absent from the checkout, not checked out (empty), checked out at another commit, a `.git` file naming another directory, declared without a gitlink, or the commit missing. Nested submodules are followed one level (depth 2); a dirty submodule checkout never matters because the object store is read.
- `UpstreamTree.submodules` lists every submodule a read went into (path, name, gitlink commit, git directory). `files()` and `grep()` stay those of the clone's own tree, and `pinned` is now asked of git once per tree.
- A git submodule is a source root for the `native` symbol only, and only when the clone's own tree has no match (`_find_module(..., submodules=True)` in `class_surface`, `definition_surface` and the factory rule). Following imports and base classes never searches submodules as roots: the first version did, and two passing packages changed (`gh.lightwheelai/lw-benchhub`'s native base `TaskBase` resolved into its IsaacLab-Arena submodule and turned five `MAYBE_ABSENT` warnings into `NOT_UPSTREAM` errors; `gh.notfoundthisperson/robocas-v0`'s base `BaseEnv` resolved into ManiSkill and two warnings disappeared). An exact path into a submodule (a citation, a relative import, a `pyfile:` selector) is still read.
- Gates: G4 reads citations through the tree, and its `REF_MISSING` message carries the refusal reason; G7 and `pyfile:` selectors (`source_surface.regular_source`) read the native the same way (a path naming the gitlink itself is still an error); a missing module names the refused submodules. G1 (after the other gates) adds one warning `G1.SUBMODULE_SOURCE` per submodule the gates read: path, name, gitlink commit, object store, and that its licence is not the card's.
- Tools: `show_refs.py` reads a citation under a path of the clone's `.gitmodules` through the SDK's tree at the gitlink commit (never the checkout) and prints which submodule and commit it read; a refused submodule is a bad citation with the reason. `collect.py` prints a `SUBMODULE_SOURCE` note for each `G1.SUBMODULE_SOURCE` finding (never failing) and its residue check reads cited submodule lines through the same tree.

## Factory-built environments (SDK, `mhs/driver/factory_check.py`, `families.py`, `check.py`)

`GymnasiumDriver.native_factory = {"returns": "package.module.Class", "ref": "path:LINE-END"}` declares that `native` names a module-level function of the clone that returns an instance of a class outside the clone. G7 then checks with `ast` at the pinned commit: the function is undecorated, synchronous and not a generator (`FACTORY_NOT_FUNCTION`); every return is a call of exactly `returns`, resolved through a module-level import of the function's file, and the function cannot fall off its end (`FACTORY_RETURN`); `ref` cites that file and covers each return statement (`FACTORY_REF`); the class is not defined in the clone (`FACTORY_IN_CLONE`); and the fake and the driver use only the environment interface of the backend's profile, dm_env's (`reset`, `step`, `action_spec`, `observation_spec`, `reward_spec`, `discount_spec`, `close` and dm_control's `control_timestep`) under `dm_env_v1`, Gymnasium's otherwise (`NOT_UPSTREAM`). A malformed declaration is a definition error; on another family G7 fails `FACTORY_FAMILY`. The declaration changes no manifest or reference. Not proven: that the external class has that interface, its behaviour, and the factory's keyword arguments.

## Registry

`MHS/registry/overrides/robots.json`: `gh.google-research/robopianist` moves from family `mujoco` to `gymnasium` (`override:source-review`; the two confirmed entry symbols stay). A rebuild then gives its card `GymnasiumDriver`, no blocked codes and `package_status: pass`, and drops `SDK_BUG` from crazyflie-sim's card; 371 other cards change their rank only.

## Packages

- `gh.google-research/robopianist`: **pass** (new package; authored by claude-opus-5-5; Sonnet review pending). Was a code-less blocked record (`HELPER_MISSING`). `native = "robopianist.suite:load"` with `native_factory` for `mujoco_utils.composer_utils.Environment` (`robopianist/suite/__init__.py:87-93`); both backends on the dm_env adapter; 45-element action (each hand's 20 Menagerie actuators and 2 forearm degrees of freedom, then the sustain pedal) whose bounds are cited from the Menagerie submodule at its gitlink `1afc8be`, the hand and piano code; the soundfont is an install fact; the e-stop is the software latch of a synchronous simulator. The live `sim` backend (never run) calls `suite.load(environment_name, seed)` with Python's standard output sent to standard error while it builds the environment. Gate digest `sha256:85c1fd1276190b69f9fb50f66105bbf7095acd9e2dde3bd6f38bfff1f70ba34b`.
- `gh.vision-agh/crazyflie-sim`: **blocked retained**, now on `HELPER_MISSING` only (`SDK_BUG` removed): G4 and G7 pass with `evs_gz_utils` read at `b8893f58`; the gate fails only `G6.ESTOP_FAILED` (stable digest `sha256:290fbbc61c2a7264e5179cb0420f98ca3bcb733f178833d953008cdfeac0a042`, was `sha256:de5dfe7e7bc31b4b4d46e0349daa7d542bcc94d5eb91daad0587a3716d46a246`). The stop could not be re-authored from this clone: a RosDriver binding needs an exact endpoint literal, but `/world/<world_name>/control` is composed at run time from a parameter (`gz_step_example.py:19-27`, `gz_step.launch.py:9-33`); the pinned `step_simulation` spins without a timeout and discards the ControlWorld response (`:44-49`), and reading it otherwise needs rclpy and ros_gz calls the clone does not show; nothing reads a paused world back. Changed: driver.py (docstring), facts.md, RESULT.json (a MODEL REVIEW paragraph); reference files regenerate byte-identical.

## Found, not fixed

- `check_recon.py` and `RECON-PROMPT.md` still refuse a recon entry file inside a submodule (they check the parent tree with `git cat-file`); a card entry whose file is in a submodule would now be readable by the gate.
- A run-time endpoint composed from a declared deployment parameter (RosDriver), and a pause confirmation for gz-sim worlds, are what crazyflie-sim needs; the companion design (phase 3) deferred the same item.
- Base classes inside a submodule are followed only through exact paths, never through a submodule used as a source root (see above).
- A submodule's licence is not on the card; `G1.SUBMODULE_SOURCE` and the collect note name each one for the publication decision (REVIEW.md item 11).

## Result

In the private copy (Python 3.14.7, the validated environment, no bytecode):

- New SDK tests: 33. `tests/driver/test_submodules.py` 20 (gitlink reads, the object store over a dirty checkout,
  `files`/`grep` unchanged, fail-closed cases: another commit, absent, empty, a `gitdir:` file naming another
  directory, a symbolic link, an undeclared gitlink, a declared path without a gitlink; a nested submodule; native
  lookup after the clone's own tree; bases never searched in a submodule root; `pyfile:` selectors; the `.gitmodules`
  parser; HEAD reading; three gate cases: a package citing a submodule passes with `G1.SUBMODULE_SOURCE`, the
  submodule at another commit fails G4 and G7, a dirty submodule checkout is not read),
  `tests/driver/test_factory_environments.py` 10, and `tests/handoff/test_tools.py` 3 (`show_refs.py` reads a
  submodule citation at the gitlink and refuses one at another commit; the collect note). Helper:
  `tests/driver/submodule_support.py` builds the submodule layout of `git submodule update` in temporary directories.
- SDK suite (one full run): 3,459 tests (snapshot-3's 3,426 plus 33), 5 skipped, 832 s; 7 failures, all in modules
  this change does not touch and that are timing-bound under load: six in `tests/test_mcp_stdio_contract.py`
  (`MHS.DEVICE.BUSY` "MCP lane retains an abandoned request" after a 592 ms request) and one in
  `tests/bridges/test_ros_action_safety_retirement.py`. Re-run on their own, both modules pass (27 tests OK).
- `collect.py --strict` over the 66 passing packages whose clones have a `.gitmodules`, before the full run: with
  the first version two digests moved (above); with the final one 66 of 66 pass with their recorded digests.
- `collect.py --strict` over all 689 passing packages (the 688 of snapshot-3 and RoboPianist), in four chunks: 689
  pass and every recorded digest equals its gate run (no `RESULT_DIGEST_STALE`), so no passing digest moved. Strict
  warnings: the pre-existing `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`, and an `EXEMPLAR_RESIDUE`
  in RoboPianist's `test_driver.py` (it used `CartPole-v1` as an invalid environment name), fixed and collected
  again clean. The only `SUBMODULE_SOURCE` note among them is RoboPianist's (crazyflie-sim, blocked, shows its own
  when collected alone).
- Registry: two rebuilds (`build_registry.py --jobs 8`) and `prepare.py --sync`, then `build_registry.py --check`
  0 differ, `validate.py --no-corpus` PASS, registry suite 329 OK. `tools/build_changelog.py --check` OK (102
  fragments). `MHS/sdk/INTERFACE.md` regenerates unchanged. `show_refs.py`: 0 bad citations for both packages (10
  crazyflie-sim and 4 RoboPianist citations read from submodules). Neither clone has a file newer than the start of
  the run.

Not run: any upstream code, the OpenAI4S integration tests and `tools/oss_export_check.py`. The agent ran no git command in a clone: the gitlinks and submodule HEADs were also checked by reading the `.git` object files with a stdlib reader in the session scratchpad; the SDK itself reads clones with git plumbing as before.
