# Companion locks: fetched companion clones, a stall read-back and a list-element read-back

A companion source may now be a clone fetched at one pinned commit under `work/companions` and listed in its `LOCK.json` (a `lock` alias in the reviewed override). Gate G1 checks the clone's LOCK.json entry, HEAD, untracked files and write bits, and `tools/fetch_companions.py` puts the clones back, offline first. Two read-back forms join the companion-cited e-stop: a stall read-back (E1: the world's simulation time, read at least twice, must not advance) and a list-element predicate (E4). Eight more simulator packages pass. Seven of them offer no unpause.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 as the phase-3 agent p3-companion-2.

- **Where:** a private project copy (`work/handoff-runs/claude-20261104/development/p3-companion-2/`). The copy is of the p3-companion project as its accepted review left it, which is `snapshot-3` plus the companion-source change (`COMPANION-SOURCES.md`).
- **From:** the design in `development/p3-companion-preflight-2/` (`DESIGN-2.json`, `DESIGN-2.txt`, `PREFLIGHT-2.json`).
- **Status:** not integrated. A Claude Sonnet review follows, as the user decided.
- **What was run:** no hardware, Gazebo, ROS graph, network fetch or human review anywhere below. Every result is `contract_checked` on fakes.

## Why

**Two user decisions of 2026-11-05.**

1. Decision 1 in `work/handoff-runs/claude-20261104/user-decisions-20261105.json`: a stop may cite a locally cloned companion repository, limited to local pinned commits.
2. The authorisation recorded in `work/handoff-runs/claude-20261104/user-authorization-companion-clones.json`: shallow clones at fixed commits of the companion repositories that the 12 version-mismatch simulator packages need. The 17 clones are read-only under `work/companions/` and listed in `work/companions/LOCK.json`.

**What the preflight found.** `COMPANION-SOURCES.md` left those 12 rows blocked. Preflight 2 sorted them as follows:

| Group | Count | Packages | What they need |
|---|---|---|---|
| Ready with the fetched clones | 4 | rotors_simulator, crazys, ur5_ros-gazebo, panda_simulation | nothing more |
| Need E1 | 3 | ROS 2 Humble packages | the stall read-back |
| Need E4 | 1 | bcr_arm | the list-element predicate |
| Need E2 and E3 | 3 | gz-sim packages | a topic read-back and an operator bridge |
| Not a stop | 1 | panda_gz_moveit2 | — |

**The orchestrator's SAFE-042 condition** (`review/ORCHESTRATOR-DECISIONS.md`, the p3-companion-preflight-2 row, and the brief): an unpause re-enable must not resume a stored motion command. Where the stored command cannot be cleared before unpausing (cite it), the package offers no unpause re-enable and says how the operator recovers.

## Design

### Lock companions (DESIGN-2 items 1 to 6)

**Declaration.**
- A companion entry of the reviewed override may add `lock`, the LOCK.json alias, for example `ros-simulation__gazebo_ros_pkgs@2.5.21`. This change adds the new override file `MHS/registry/overrides/companion-sources-lock.json` and a `lock` field in `overrides.schema.json`.
- The entry's `commit` and `profile` must be those of the LOCK.json entry.
- Its `package_id` must be the `gh.<owner>/<repo>` (lower case) that the entry's `repo_url` names. It need not be a corpus record.
- The card's package must be in the entry's `needed_by`.
- An entry without `lock` keeps the corpus rules of the first design. A card may mix both kinds of entry, at most three in all.

**Where the shape and rules are checked.**
- `triage.check_companions` checks the shape: the alias pattern of `COMPANION_LOCK_RE`.
- `triage.companion_problems` applies the LOCK rules through `triage.lock_problems`, which also checks that the LOCK.json `path` is `work/companions/<owner>__<repo>@<commit[:12]>` and, with the corpus present, that the clone exists at the pinned HEAD. `companion_problems` then reads every version-evidence range in the fetched clone.

**Pin source.**
- `build_registry.py` `attach_companions` reads `work/companions/LOCK.json` once.
- It copies the following onto the card (`taskcard.schema.json`):
  - `ref`, the LOCK.json `path` as `local_path`, and `repo_url`.
  - The licence: `license_spdx` when the LOCK.json text is an SPDX expression. Otherwise the licence is `NOASSERTION` with a `licence_note` (`triage.lock_licence`). The gazebo_ros_pkgs clones say "Apache-2.0 AND BSD (per package.xml; no licence file in the repository)".
- `driver.lock.json` repeats `{package_id, commit, lock}` (`driver-lock.schema.json`, mirrored by `sync_data.py`). The scaffold `mhs.driver new` copies `lock` into it.
- `validate.py` repeats the rules against LOCK.json. With `--no-corpus` it checks only the card's shape (`lock_shape_problems`).

**G1 for a lock companion** (`check.py`, `_g1_companion_lock`, and `upstream.py`):

| Check | Fails when |
|---|---|
| `COMPANION_LOCK` | LOCK.json is missing or unreadable; the alias is absent; `commit`, `path`, `profile` or `ref` differ from the card; `repo_url` names another repository; the package is not in `needed_by` (`lock_entry_problems`) |
| `COMPANION_HEAD` | the HEAD is not the pin |
| `COMPANION_MODIFIED` | a modified tracked file, or an untracked file. Untracked files count only for a lock companion: `UpstreamTree.modified(untracked=True)` |
| `COMPANION_WRITTEN` | a tracked file changes during the run, or, for a lock companion, a new file appears |
| `COMPANION_WRITABLE` (new) | the work tree has a write bit. The check is an `lstat` walk that skips `.git` and symlinks (`UpstreamTree.writable_entries`) |
| `NO_COMPANION_CLONE` | the clone is missing |

All of these are errors. G2 compares `{package_id, commit, lock}`. G4 and G7 read the clone exactly as they read a corpus companion.

**Exported tree.**
- `work/` does not travel, so an export fails G1 (`NO_COMPANION_CLONE`, `COMPANION_LOCK`) until the clones are back.
- `--companions-root DIR` points the gate at the clones and their LOCK.json elsewhere: `DIR/LOCK.json` and `DIR/<basename of local_path>`. These carry the option:
  - `python3 -m mhs.driver check`, the gate child `_gate.py`, `run_check` and `run_check_isolated`.
  - `MHS_DRIVER_GATE_COMPANIONS` (the inner G9 environment).
  - `collect.py` and `show_refs.py`.
- `collect.py` keeps the gate's verdict and adds the note `COMPANION_SOURCE`. The note names the lock alias, or says where the clone is missing and how to fetch it.
- `show_refs.py` prints the LOCK.json entry in each companion header and counts the following as bad citations: `!! LOCK mismatch`, `!! writable work tree` and `!! clone missing`.
- `tools/oss_export_check.py` passes `--companions-root <root>/work/companions` to the exemplar gate run when the exemplar's card has lock companions. Without `work/companions/LOCK.json` it skips that exemplar's gate with a printed note, as it already does for an exemplar whose package clone is missing. No exemplar has a lock companion today.

**Re-fetch.** `tools/fetch_companions.py` is new. It takes a driver directory, a package id, or `--lock FILE [ALIAS ...]`, and works offline first:

1. An existing destination is verified (HEAD, clean, read-only) and never deleted, reset or chmod-ed.
2. `--from DIR`: another workspace's `work/companions`, or a `<name>.bundle`. The copy goes to a temporary sibling. It is accepted only when its HEAD is the commit, `git fsck --full` passes and its tree is clean. It is then made read-only and renamed into place.
3. The network is used only with `--network`: one depth-1 fetch of the pinned commit.

Every git call runs with:
- no hooks, no credential helper and no prompt;
- `GIT_LFS_SKIP_SMUDGE=1`;
- the system and global git configuration ignored, and `GIT_CONFIG_PARAMETERS` dropped.

The LOCK.json merge never re-pins and never widens an existing entry's `needed_by`. Widening it is a reviewed LOCK.json edit. A new entry lists the packages of this run. This agent never ran the tool against `work/companions`, and never with `--network`. Its tests run on temporary repositories, and their network step is answered in place of git.

### E1: the stall read-back (`DESIGN-2.json`, `E1-STALL-READBACK`)

ROS 2 gazebo_ros 3.9.0 has no service that reports the paused flag. Its `get_model_list` stamps the answer with the world's simulation time:
- The factory serves `get_model_list` (`gazebo_ros_factory.cpp:139-143`), and its callback sets `header.stamp` from `world_->SimTime()` (line 168).
- `World::Step` of Gazebo 11.15.1 advances that time only while the world is not paused, a step is pending or a reset is due (`World.cc:835-854`).

**The binding.** `safety_bindings.safe_state` (a fixed service call with a success predicate, and only that binding) may add:

```
stall: {"path": "header.stamp", "samples": 2..4, "interval_ms": 100..2000, "unchanged": true}
```

`RosBridge._binding` validates it with `_stall`. The stall is part of the binding's stop-request identity (`_stop_request_identity`, CORE-074), so a single answer of another binding to the same service never counts as the stall's confirmation.

**The runtime** (`RosBridge._stall_read_back`):
1. The read-back is called `samples` times.
2. Each later call is sent at least `interval_ms` after the previous answer arrived, on the monotonic clock. While it waits, the bridge must stay open and the call must not be cancelled.
3. A later call is sent only while that wait and the call's own timeout still fit in the remaining budget. Otherwise the result is `MHS.OUTCOME.TIMEOUT`.
4. Every answer must satisfy `success`, and the values at `path` must be identical (`_equal`). Each value must be a finite number or a ROS time (`{sec, nanosec}` or `{secs, nsecs}`, integers; `_stall_sample_ok`, integrator edit I1): null, an empty value, a string, a list, a boolean or any other object fails closed.
5. A failed call, a missing value or a change leaves the e-stop unconfirmed: `MHS.SAFETY.SAFE_STATE_UNREACHED`, with the latch held and the existing background retry. `safe_state()` repeats the same check.

**The gate.**
- **G7** (`ros_check.py`):
  - A stall only on the read-back of a companion-cited e-stop (`ROS_STALL_SCOPE`).
  - A stall path other than `$`.
  - The read-back's `state_ref` must show the path's last segment (`stamp`).
  - A Fact must cite a declared companion.
- **G3** (`families.py` `_stall_budget`, SAFE-028): the worst case must fit in `estop_latency_ms`, which is 1000 ms when it is not declared. The worst case is: stop timeout + `samples` x read-back timeout + (`samples` - 1) x `interval_ms`.
- **G6** (`behaviour.py`):
  - The gate installs `StallFilter` through a new `native_filter` argument of `open_driver` and `endpoint`. The filter rewrites the stall value on every read-back answer.
  - The gate requires the e-stop to fail with `SAFE_STATE_UNREACHED`, `safe_state_achieved` false and the latch held (`STALL_FAIL_OPEN`).

The three packages use 2 samples, 250 ms apart, with a 400 ms pause and 300 ms read-backs. They declare `estop_latency_ms = 1500`.

### E4: the list-element predicate (`DESIGN-2.json`, `E4-LIST-ELEMENT`)

The predicate form is:

```
success: {"path": "controller", "where": {"name": "joint_trajectory_controller"}, "field": "state", "equals": "inactive"}
```

It passes only when:
- the value at `path` is a list;
- exactly one element is an object whose `where` keys all equal their values. There may be 1 to 4 plain field names, with JSON scalar values compared type-strictly;
- that element's `field` equals `equals`.

No element, several elements, a value that is not a list or a missing field fails. This is `_passes` in `bridge/ros.py`, used for service answers and action results. `_binding` validates the shape.

G7 wants the read-back's `state_ref` to show the selected `field` and every `where` key (`controller_state.name`, `controller_state.state` at `controller_manager.cpp:1752-1755`).

### Deviations from DESIGN-2

- **No unpause re-enable.** DESIGN-2 gave the four ready packages the re-enable `/gazebo/unpause_physics`. Under the orchestrator's stricter condition, none of the seven Gazebo packages offers an unpause, neither as the re-enable nor as an ordinary command. Each `safe_state` and `facts.md` names the stored command that would resume, the cited lines, and the operator's recovery outside MHS. rotors_simulator's author had declared `x-cap.ethz-asl.sim_start.v1`, which is the same unpause; it is removed.
- **The E1 fact check.** It asks for a Fact that cites a declared companion, not specifically the step gate at `World.cc:835-847`. The gate cannot tell which companion line is the step loop. REVIEW.md item 13 asks the reviewer to check it, and each of the three packages cites `World.cc:835-854`.
- **Where things live.**
  - The G3 arithmetic is in `families.py`, beside the other G3 definition checks, not in `check.py`.
  - The new tests are in new files (below) rather than in `test_companion_sources.py` and `test_companion_overrides.py`.
  - The bridge tests are in `tests/bridges/`, the existing directory.
- **oss_export_check.** It passes `--companions-root` when the exemplar's card has lock companions, rather than whenever `work/companions` exists.

## The eight packages

All eight keep their `authored_by` (`deepseek-v4.1-flash:1017`, run ids `ros-wave-c-*`) and their source pins. Each gets a MODEL REVIEW paragraph in RESULT.json, and each RESULT.json moves from `blocked` (`HELPER_MISSING`) to `pass`. The author text before the paragraph is shortened with ` [...]` where the notes would exceed 8000 characters; the originals are in `development/p3-companion-2/originals/packages/`.

**What each package now has:**
- Its card's companions come from the reviewed `companion-sources-lock.json` override.
- `facts.md` is rewritten: the companions header, the facts table from `reference.json`, the safety section, and the stale scope and fidelity sentences.
- Its fake keeps the simulator state its stop acts on, with negative switches. These are: no answer to the stop, a failed read-back, a world that another client resumed (or a controller re-activated), and, for E1, a stamp that keeps advancing.
- Its tests cover:
  - the confirmed e-stop;
  - each failure path: a failed receipt with `SAFE_STATE_UNREACHED` and the latch held;
  - the reset that leaves the world paused, or the controller inactive;
  - the absence of an unpause, or bcr_arm's re-enable.

**Common to the seven Gazebo packages.**
- Topics published from world updates are silent while paused. The device resource reads none of them (where one did, it became an explicit read capability), so a reset device stays readable: after an e-stop and a reset, each of the seven fakes is still paused and `read("main")` answers `{}`.
- Where a command's effect was observed only through such a topic, the command's receipt now reports the values it sent (TCAP-003).

**Risk** (REVIEW.md item 12, `MHS/spec/04-safety.md`). ur5_ros-gazebo, panda_simulation and bcr_arm command an arm, and unitree_ros2_sim publishes `/cmd_vel`: all four keep their authors' R2. sjtu_drone rises from the author's R1 to R2: its `cmd_vel`, `takeoff`, `land` and `reset` command the vehicle, and the server applies the device risk to every capability. rotors_simulator has no command left (R0). crazys and quadruped_sim2sim kept their authors' R0 here, as inputs of the clones' own controllers; the integrator raised both to R2 (edit I6 below), because no fact cites that only a simulator consumes either command topic. A risk change adds no gate finding, so no digest moved.

**Where to read each package's case.** The facts, `safe_state` and the facts.md Safety section cite every line named below.

| Package | Gates the original failed | Stop and read-back | SAFE-042: the unpause | Other changes | Stable digest |
|---|---|---|---|---|---|
| `robots/ethz-asl__rotors_simulator` (R0) | G6 | `/gazebo/pause_physics`, confirmed by `/gazebo/get_physics_properties` with `pause == true`. gazebo_ros 2.5.21 and Gazebo 7.16.1 (Kinetic). | None. The lee position controller's waypoint (`lee_position_controller_node.cpp:144-146`) and the motor model's rotor-speed reference (`gazebo_motor_model.cpp:344-348`) resume. The package commands neither. The author's `sim_start` (the same unpause) was removed. Recovery: `README.md:145-150`. | Two fact lines corrected: `spawn_mav.launch:24` became `:26`, and `gazebo_odometry_plugin.cpp:574-582` became `574-583`. | `sha256:421d0701d93ade1dafee1dc6606823cc004bc5db69a30a0e45c72749df7f69f9` |
| `robots/gsilano__crazys` (R2 since integrator edit I6; R0 here) | G6 | As rotors (Kinetic). | None. The Crazyflie controller stores the last roll, pitch, yaw rate and thrust with no timeout (`roll_pitch_yawrate_thrust_crazyflie_node.cpp:93-99`, `roll_pitch_yawrate_thrust_crazyflie.cpp:223-228`). The motor models keep the last rotor speed (`gazebo_motor_model.cpp:237-239`). The clone states no hover thrust, and zero thrust is not a hold. | The odometry left the resource. The command receipt reports the four values sent. | `sha256:110e987035c65cae8e975deb7198b87a95df8d04e78a3483e47c70f151e57e62` |
| `robots/lihuang3__ur5_ros-gazebo` (R2) | G6, G8 | As rotors (Kinetic). The author's vacuum-off e-stop is an ordinary command again, because releasing the vacuum drops the payload. The vacuum plugin is cited as a companion fact. | None. ur5_mp's MoveIt trajectory and each vacuum channel's stored state resume (`gazebo_ros_vacuum_gripper.cpp:172-230`). The vacuum services answer while paused (`136-142, 235-243`). Recovery: stop ur5_mp (`ur5_mp.py:57, 149-158`), then unpause. | The three topic reads are silent while paused (disclosed). | `sha256:1ffb853b96e17ef2f5d2863c0185cca2c5a91e54c30dadd0b555f40f6dbdf2f0` |
| `robots/erdalpekel__panda_simulation` (R2) | G6, G8 | As rotors, with gazebo_ros 2.8.7 and Gazebo 9.19.0 (Melodic). `/robot_control_stop` is an ordinary request again, because it acknowledges unconditionally (`robot_control_node.cpp:56-61`). | None. The custom controller's stored `command_` (`joint_position_controller.cpp:38-47`) and any accepted trajectory resume. No command value means hold. | `/joint_states` became the read `x-cap.erdalpekel.joint_states.v1`. The joint-position receipt reports the positions sent. | `sha256:0b3aa1d740f97d42385654a25b2c1667643ba4ef4578775b12d60b7a413ed96e` |
| `robots/atharva-05__unitree_ros2_sim` (R2) | G6, G8 | E1: `/pause_physics`, then two `/get_model_list` answers 250 ms apart with the same `header.stamp`. gazebo_ros 3.9.0, gazebo_ros2_control 0.4.12 and the corpus Gazebo 11.15.1 (Humble). `estop_latency_ms = 1500`. | None. junior_ctrl's loop runs on the system clock through the pause, on stale states (`main.cpp:106-110`, `FSM.cpp:38-66`). A zero Twist alone does not decide what the legs do. Recovery: key 2 for fixed_stand (`KeyBoard.cpp:25-30`), then unpause. | `/odom` became the read `x-cap.atharva-05.odometry.v1`. The cmd_vel receipt reports the values sent. | `sha256:e5a4e9317d073d1f22a90e99c56effe12bae4d3c08ac6e7e66764103d1630446` |
| `robots/evronix__quadruped_sim2sim` (R2 since integrator edit I6; R0 here) | G6 | E1, as unitree. | None. The policy node publishes efforts every 5 ms from its last setpoint (0.15 at start) on the system clock (`load_dreamwaq_policy.py:167, 182, 230-270`, `README.md:86-90`). | none to the resource | `sha256:fd568a5994a0ca14008bc31cc59b917c906cbe2c38a65d41f7fae168b5a9d4b2` |
| `robots/novog93__sjtu_drone` (R2; the author's R1) | G6, G8 | E1, with gazebo_ros 3.9.0 and the corpus Gazebo 11.15.1 (profile fixed to Humble). `/reset_world` stays an ordinary command. | None. In position control, cmd_vel's linear fields are position targets (`plugin_drone_private.cpp:492-520`). A take-off continues (`573-585`). `CmdCallback` adds drift noise (`227-254`). The bringup's teleop publishes on the same topics. | The cmd_vel resource read became `x-cap.novog93.last_cmd_vel.v1`. The receipt reports the six values sent. | `sha256:d550997ea4bc756962572a0cbe8ecee1e79560b6528d7a63fa3e3360686915ea` |
| `robots/blackcoffeerobotics__bcr_arm` (R2) | G6, G8 | E4: `/controller_manager/switch_controller` deactivates `joint_trajectory_controller` (STRICT, a 0.4 s wait; `controller_manager.cpp:557-560, 1980-2031, 1307-1331`). Confirmed by `/controller_manager/list_controllers`: the one element with that name must be `inactive` (`537-539, 1748-1755`). controller_manager 2.54.4, joint_trajectory_controller 2.54.1 and gz_ros2_control 0.7.21 (Humble and Fortress). | Declared re-enable `x-cap.blackcoffeerobotics.activate_controller.v1` (CORE-086). Deactivation drops the stored trajectory (`joint_trajectory_controller.cpp:1055-1106`), and activation starts by holding the state it starts from (`1027-1029, 1617-1626`): with this deployment's position-only command interface that is the measured position (integrator edit I5 below). Nothing resumes: the stop itself clears the command. | The fake models the controller lifecycle and rejects goals while the controller is inactive. | `sha256:73851954e93d31032f21b4702470d7c02bf3be3ce619a083db82cbfcfb9c0d10` |

## Four rows stay blocked

These classes and reasons are DESIGN-2's, not re-traced here.

| Package | Simulator | Why it stays blocked |
|---|---|---|
| linorobot/linorobot2 | gz-sim 8, Jazzy and Harmonic | The WorldControl pause's reply confirms nothing, because the request is queued. The only paused flag is `WorldStatistics.paused` on a topic that none of the clones bridges. These rows need E2 (a topic read-back) and E3 (an operator-run bridge). |
| osrf/vrx | gz-sim 8, Jazzy and Harmonic | as linorobot2 |
| rigbetellabs/tortoisebot | Ignition Fortress, Humble | as linorobot2 |
| andrejorsula/panda_gz_moveit2 | — | Deactivating the effort trajectory controller leaves ign_ros2_control writing the last effort, so it is not a stop. |

E2, E3 and the run-time world name (E5) stay for later, as the brief says.

## Validation

**New tests.** All of them pass.

| Test file | Tests | What it covers |
|---|---|---|
| `MHS/sdk/tests/driver/test_companion_lock.py` | 17 | `companion_sources` for lock entries; `read_companion_lock`; `lock_entry_problems`; G1 on a real package with a temporary `work/companions` (a tiny git repository and its LOCK.json): the passing case, each `COMPANION_LOCK` case, `COMPANION_HEAD`, `COMPANION_MODIFIED` and `COMPANION_WRITTEN` for untracked files, `COMPANION_WRITABLE`, `NO_COMPANION_CLONE` and `--companions-root`; G2; the scaffold's lock; the gate child's option; a corpus companion beside a lock companion |
| `MHS/sdk/tests/bridges/test_ros_stall_readback.py` | 9 | a paused world confirms; a world that still advances does not; a change on a later sample, a failed answer and an answer without the stamp; `safe_state()` alone; a budget that cannot hold the next sample; cancellation between samples; one answer never standing for a stall read-back; the stall only on `safe_state`; malformed stalls |
| `MHS/sdk/tests/bridges/test_ros_list_predicate.py` | 8 | exactly one selected element; none, several, a wrong type and a missing field; the plain predicate unchanged; a controller switch confirmed by its list read-back; a list naming the controller twice; a command service answer; malformed and well-formed shapes |
| `MHS/sdk/tests/driver/test_companion_stall_gate.py` | 6 | scratch stall and list packages through G1 to G8; G3 refusing a worst case beyond the budget; G7 refusing a stall without its scope, fact or field, and a `state_ref` without the selected field and keys; G6 catching a bridge that confirms the stall from one answer |
| `MHS/sdk/tests/handoff/test_fetch_companions.py` | 15 | `fetch_companions.py`, `show_refs.py` and `collect.py` for lock companions (the cases its docstring lists) |
| `MHS/registry/tests/test_companion_locks.py` | 13 | the override shape and schema; `lock_licence`; each LOCK rule; the clone and its HEAD; evidence read in the fetched clone; `build_registry.py` resolving an entry from LOCK.json; the validator with and without LOCK.json; the package lock; the shipped override file |

The existing `test_companion_sources.py` (32) and `test_companion_overrides.py` (16) pass unchanged.

**Mutation check.** `development/p3-companion-2/scripts/mutants.py` killed 44 of 44 mutants (`logs/mutants-1.log`, `logs/mutants-2-tools.log`):

| Area | Count | Mutants |
|---|---|---|
| Lock | 9 | no LOCK.json check, no write-bit check, another profile, a package outside `needed_by`, untracked files ignored, the driver lock without `lock`, `--companions-root` ignored, a local path of another commit, a `repo_url` naming another repository |
| E1 | 13 | samples never compared, one sample, no wait, a stall on any safety binding, no budget check, a sample without the value, `unchanged` not required, no G7 scope, no `state_ref` word, no companion fact, no G3 budget, no G6 check, the stall left out of the request identity |
| E4 | 6 | several matches, `where` ignored, type-loose `where`, a non-list passed through, no G7 check of the `where` keys, the key names and count unchecked |
| Registry | 7 | no LOCK rules, no `needed_by` rule, no path rule, a non-SPDX licence kept, no shape check without LOCK.json, any lock text, a re-pinned commit |
| Tools | 9 | a re-pinning LOCK entry, `needed_by` widened, an existing destination not verified, a copy not verified, a copy left writable, git keeping the caller's configuration, show_refs ignoring write bits or a missing clone, collect ignoring `--companions-root` |

No tool mutant could reach the network: the only `--network` test answers git's fetch in place.

**The eight packages.**
- Each passes all nine gates with the digest above (`logs/write-results-1.log`). A second gate run after the final registry rebuild and `prepare.py --sync` gave the same eight digests (`logs/write-results-digests.log`). sjtu_drone's gate after its risk change gave the same digest again (`logs/write-results-digests-sjtu-risk.log`).
- Their own suites pass: rotors 11, crazys 13, ur5 10, panda 16, unitree 14, quadruped 13, sjtu 13 and bcr_arm 12 tests (`logs/package-tests-1.log`). sjtu_drone's 13 passed again after the risk change (`logs/package-tests-sjtu-risk.log`).

**Digests against `snapshot-3`** (`logs/digests-vs-snapshot3-2.json`):
- 701 packages pass, against 688 in `snapshot-3`. Every one of the 688 keeps its `snapshot-3` digest.
- 13 newly pass: the five of p3-companion, with that item's recorded digests, and the eight here.
- None was lost.

**Collect.** `collect.py --strict` ran over all 701 passing packages of the private copy, in six chunks (`logs/collect-1/`, `scripts/collect_chunks.py`).
- All 701 pass the gate with their recorded digests. There is no `RESULT_DIGEST_STALE`.
- The only warning is the known MCM3000 PDF citation (`UNVERIFIABLE_CITATION`, user-owned). It sets chunk 0's exit code to 1, as in phase 2 and p3-companion.
- Each of the eight packages gets one `COMPANION_SOURCE` note per companion. Each note names the lock alias and the count of fact citations.

**Show refs.** `show_refs.py` ran over the 701 passing packages, with this tool and with the base's tool on the base tree (`logs/show-refs-all-2.json`, after the risk change). It did not crash, it found no bad citation, and the two tools gave the same result for the 693 packages both trees pass.

**SDK suite.** It ran twice, the most the brief allows (`logs/sdk-suite-1.log`, `logs/sdk-suite-2.log`).
- **Run 1:** 3,515 tests with 11 errors, all in `tests.handoff.test_tools.CollectVerdictTests`. They were not timing failures. `collect.summarise` passed `companions_root` to `run_gate` as a third positional argument, but those tests replace `run_gate` with a two-argument test double.
- **The fix:** `summarise` now makes the two-argument call when no companions root is given. `tests.handoff.test_tools`, `test_facts_limits` and `test_fetch_companions` then passed (96 tests).
- **Run 2:** after the fix, 3,515 tests OK (5 skipped), at a load average of about 4 to 5 (`logs/sdk-suite-2.timing`).
- No timing test failed in either run.

**Registry and generators.**
- The registry suite ran 358 tests: OK.
- `validate.py` passed with and without the corpus.
- `build_registry.py --check`: 0 files differ.
- The `sync_data.py`, `build_applicability.py`, `gen_appendices.py`, `gen_errors.py` and `build_changelog.py` checks pass (`logs/generator-checks-1.log`).
- `MHS/sdk/INTERFACE.md` was regenerated: the `check` usage line gains `--companions-root`, and it equals `--print-interface`.
- `dispatch.py --stats` is unchanged (done 827, dispatch 15), and `--check-pilot` gives 20 of 20.
- No `__pycache__` is left in the tree.

**Generated changes from the rebuild.**
- The registry rebuild moved the eight cards from rule 9 to the override (deciding rule 9: 307 to 299; override: 1252 to 1260; `contract_checked`: 693 to 701). It also re-ranks 330 other cards. Only `rank` changes, plus the rank number quoted in five `next_action` texts. This is a global effect of eight more passing packages.
- Six family pages change. The ros1, tag-bridge, qcodes and pylabrobot pages change their quoted ranks. The gazebo and ros2 pages change their wave counts, because the eight cards moved from wave 5 to wave 3.
- `prepare.py --sync` refreshes 333 `task.json` files: the eight here and 325 re-ranked.
- These files are generated and were never edited by hand.

## Residual risk

**Gazebo packages.**
- The read-back confirms the paused flag (ROS 1) or a frozen simulation time (ROS 2), not a sensed standstill.
- A hung but unpaused server also shows a frozen time. Nothing advances then either, and this is disclosed.
- Any client can step or unpause the world after the e-stop, and MHS does not watch. The Gazebo GUI, a WorldControl step and rosbridge itself (panda's launch serves port 9090) can all do it.
- After the reset the world stays paused. Commands sent then are stored for the next unpause, which the operator performs outside MHS after the recovery each `safe_state` names.

**bcr_arm.** Deactivation keeps each position command at its last value. A joint still converges to the last commanded point of the dropped trajectory. Any client can re-activate the controller, and a paused world makes the switch time out, which fails closed.

**Versions.** The deployment's simulator stack must be the pinned releases (the profiles above). rosbridge cannot read their versions.

**Clones.**
- The fetched clones are depth-1, so the cited blocks cannot be compared with older releases.
- An offline `--from` copy is trusted only as far as `git fsck` and the SHA-1 commit id go.
- In an export, LOCK.json is rebuilt from the card. The card-to-LOCK comparison is then tautological, and the HEAD, clean and read-only checks carry the integrity.

**Licences.** The gazebo_ros_pkgs licence is `NOASSERTION` with a note, because its package.xml files differ and no licence file is at the pins. Companion facts are short statements with citations, not copies.

## Rule deviations

1. **Bytecode in the SDK.** One early command ran without `PYTHONDONTWRITEBYTECODE`. It wrote 45 bytecode files into five `__pycache__` directories under `MHS/sdk/src/mhs` (`.`, `driver`, `bridge`, `schema`, `_server`). They were moved aside to `development/p3-companion-2/moved-aside/pycache-1/`. No package directory received bytecode.
2. **One `rmdir`.** It removed an empty directory, `development/p3-companion-2/originals-before-edit`, that this agent had created in an earlier command, not in the same command.

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and required six integrator edits when it was
composed onto the actual tree (`snapshot-5`, the tree after phase 3). Each is logged with its before and after sha256
in the integrator's `MERGE-LOG.json`; the mutants named are in its `merge/mutants/` and `logs/mutants-*.json`.

| Edit | Finding | What changed | Tests |
|---|---|---|---|
| I1 | Safety F1: a stall sample that is not a clock (null, an empty value, a string, a list, a boolean, another object) never changes, so the comparison alone would confirm the stop. | `RosBridge._stall_read_back` accepts a sample only when `_stall_sample_ok` holds: a finite number, or a ROS time (`{sec, nanosec}` or `{secs, nsecs}`, integers, the nanoseconds in `[0, 10^9)`); anything else fails closed. | `test_ros_stall_readback.py` `StallSampleKindTests` (20 bad kinds fail closed with the latch held, 5 good kinds confirm, the rule itself); 5 of 5 mutants killed. |
| I2 | Safety F2: a hung simulator freezes sim time as a pause does. | Not implemented, and listed: a sample before the pause request would delay every e-stop by a read-back round trip (a hung server exhausts its timeout) and would never confirm an already paused world (a second e-stop, the gate's repeated e-stops). For the cited companions the hung case is fail-safe once the pause was answered: `OnPause` sets the world's paused flag (`gazebo_ros_init.cpp:328-333`). | none (no change) |
| I3 | Safety F3: no test refused a LOCK.json entry whose `needed_by` is missing or not a list. | Tests for the gate rule and the registry rule; `show_refs.py` and `tools/fetch_companions.py` compared a string `needed_by` as a substring and now refuse any `needed_by` that is not a list. | `test_companion_lock.py` (+2), `test_fetch_companions.py` (+1 test, +1 case), registry `test_companion_locks.py` (+3 cases); 5 of 5 mutants killed. |
| I4 | Safety F4: `fetch_companions.py` ran `git status` and `git fsck` in a copied clone with that clone's own `.git/config`; git 2.54 runs a repository's `core.fsmonitor` hook and its `filter` clean command there. | `repository_problems` reads the clone's configuration without git before any git command: `.git` must be a plain directory without `commondir` or `config.worktree`, and `.git/config` may carry only what `git init`, `git remote add` and the authorised fetch write; anything else refuses the clone, which is never repaired. Every git command adds `-c core.fsmonitor=false` and drops the caller's `GIT_DIR`-style and `GIT_CONFIG_COUNT/KEY/VALUE` variables. The 17 clones in `work/companions` pass unchanged. | `test_fetch_companions.py` `CopiedConfigTests` (a copied fsmonitor hook and filter driver never run; 12 other configurations refused; an existing hostile destination left as it is) and `test_git_runs_hardened`; 7 of 7 mutants killed. |
| I5 | Evidence EP-1: bcr_arm's re-enable said the controller "holds the current position". | At the pin, activation restores the last command-interface values only when `set_last_command_interface_value_as_state_on_activation` (default true, `joint_trajectory_controller_parameters.yaml:75-79`) holds and the command read succeeds (`joint_trajectory_controller.cpp:1004-1020`); the read fails when a velocity state interface has no velocity command interface (`498-510`), and bcr_arm's controller commands position only and reads position and velocity (`ros2_controllers.yaml:22-26`, the Gazebo launch's default, `bcr_arm.gazebo.launch.py:118-130`). The wording now states this rule, that this deployment holds the measured position, and that a configuration that also commanded velocity would hold the last position command, which can differ from the measured position. The orchestrator's literal wording ("restores the last command-interface value") was not used, because the cited source contradicts it for this deployment. | The gate: all nine gates pass with the unchanged digest; four facts added, two reworded. |
| I6 | Evidence EP-2: crazys and quadruped_sim2sim stay R0 only if a fact cites that their command topics are simulator-only. | No fact does: crazys publishes on the RotorS command topic of a stack that also ships a hardware-in-the-loop autopilot interface (`hil_plugin.py:45-47, 90-92`); quadruped_sim2sim's setpoint drives learned policies that write joint efforts to a ros2_control effort controller, and the README only says real-robot integration is "Coming soon..." (`README.md:113-115`). Both are R2 (a flying vehicle is mobile hardware; a legged robot), with the reason in driver.py, facts.md and RESULT.json. | Both gates pass with unchanged digests (the risk is not in the stable digest). |

| I7 | The hand merges join two inputs inside one function; no SDK test ran G6 with the sensed sources, and a dropped `sensed=` leaves no finding on a passing package. | New `tests/driver/test_phase3b_coherence.py`: `_g6` hands `BehaviourRun` both `sensed` and `stall`; `run()` dispatches each check on its own; a compiled binding keeps `then` and `stall`; both upstream surfaces are exported; `show_refs` has both readers. | 8 tests; 6 of 6 counterfactual SDK copies fail them. |

The packages' RESULT.json files gained one sentence each in their claude-opus-5-5 MODEL REVIEW paragraph (rule 2);
crazys's author text was shortened by 319 characters to stay within 8000 (the original is in the integrator's
`reviewer-originals/integrator-v4/`). Its composition with the phase-3 tree needed five hand merges (`show_refs.py`,
`behaviour.py`, `check.py`, `bridge/ros.py`, `upstream.py`): every one is a union of additions at one anchor, and the
`native_filter` argument that this change and the sensed-confirmation stop (SAFE-049) both added to the gate's
`open_driver` and `endpoint` is one signature, with G6 passing both `sensed` and `stall` to `BehaviourRun`.
