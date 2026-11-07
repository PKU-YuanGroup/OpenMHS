# SIM-HOST — an isolated simulator host for environments that own a ROS and Gazebo lifecycle

A `GymnasiumDriver` backend can now declare `isolated_process_v1`: its environment is built and driven in a child process that the endpoint starts and owns, an exit or a global ROS shutdown inside the environment ends only that process, every call is bounded, and the e-stop is the declared simulator stop confirmed by a declared state read-back, or an unreached safe state. gh.rickstaa/ros-gazebo-gym passes on it (risk raised to R2); gh.ut-amrl/socialgym2 stays blocked because its simulator has no stop with a read-back.

Draft written by Claude (claude-opus-5-5, a model and not a human) as phase-4 agent p4-sim-host in a private copy of
`snapshot-5` (`work/handoff-runs/claude-20261104/development/p4-sim-host/`); not yet applied to the tree. The SDK code
and the package repair are Claude-written; by the user's decisions of 2026-11-04 and 2026-11-05 a Claude Sonnet model
reviews them before they are merged. Evidence is fake `contract_checked` only: no ROS graph, Gazebo, MoveIt, UTMRS
simulator or hardware was run, and `reviewed_by` stays null everywhere. Both packages were blocked by the user's
decision of 2026-11-04 ("simulator packages whose declared live route is known incompatible stay blocked until the SDK
supports the route"; `blocked-triage-2/TRIAGE-2.json`, class C: process isolation).

## SDK

- `mhs/bridge/sim_host.py` (new): `ProcessProfile` (`isolated_process_v1`) and `ProcessHost`, the endpoint side. The
  profile names the exact native reset keywords, bounds for start, step, reset, close, each stop or read-back round
  trip and the settle wait, the stop (a public attribute path called with no argument) and the read-back (a path, an
  optional field, the exact stopped value). It refuses a read-back equal to the stop or ending in an acknowledgement
  name (`success`, `status`, `status_message`, `ok`, `result` ...), a float, list or null as the stopped value, and
  unknown keys. The host spawns `<python> sim_host_child.py` with its standard streams on `/dev/null`, a new session
  and two private pipes (JSON lines); `MHS_SIM_HOST_PYTHON` selects another interpreter (ROS Noetic's 3.8). Every
  request waits at most its bound; a world call past its bound stays owned until the child answers (late answers are
  recorded, never applied). The stop sets the endpoint-side fence before anything can block; a dead child fails every
  pending request (sent: the outcome is unknown). Close: stop and read-back, a world call in flight, `env.close()`,
  the pipe closed, the exit awaited; SIGTERM, then SIGKILL of the process group; `settled` only when the stop was
  confirmed, the close returned and the child exited by itself. The write end is closed only under the send lock, so
  a request being written never meets a reused descriptor number.
- `mhs/bridge/sim_host_child.py` (new): the child, standard library only and Python 3.8 syntax, never importing the
  SDK; it drops its own directory from `sys.path` (the SDK's `http.py` and `serial.py` live there). It imports the
  driver directory as a private package, applies the gate's process guard first when `MHS_PROCESS_GUARDED=1` (or
  refuses to start), builds the environment on its main thread, and serves a world lane (step, reset, close) and a
  control lane (stop, read-back) on two worker threads. A stop sets the child's fence atomically with reading whether
  a world call runs; step and reset are refused while fenced. Every call into package or upstream code is inside
  `except BaseException`: `SystemExit` and `KeyboardInterrupt` are reported, after which only close is accepted. A step
  or reset whose result cannot be sent is reported as having taken effect. Paths resolve on `env.unwrapped`. When its
  request pipe closes without a close (the endpoint died), it stops, waits for a running call and closes, each at most
  10 s, and exits; SIGTERM leads to an ordinary exit, so the environment's `atexit` cleanup runs.
- `mhs/bridge/gymnasium.py`: `GymnasiumBridge(process=..., host=...)`. World calls go through the host with a dispatch
  guard that refuses a call admitted before an e-stop or a cancellation (checked under the host's send lock just
  before the write). Host outcomes map to `MHS.DEVICE.BUSY` (owned work, nothing sent), `MHS.OUTCOME.UNKNOWN`
  (`may_have_effect`: past the bound, died during the call, result lost), `MHS.DEVICE.NOT_READY`, cancelled (fenced),
  and `MHS.DEVICE.FAULTED` for an exit the host contained; an unknown outcome needs an explicit world reset before the
  next step. `_estop_hosted`: fence and stop; when a world call was running, wait for it (settle bound) and stop
  again; then the read-back must equal the declared value exactly; otherwise `MHS.OUTCOME.UNKNOWN` and the stop stays
  unconfirmed. `safety_status` is unachieved while a world call is owned, the stop is unconfirmed or the host is not
  running; `settle_native_work` also waits for the host; safety reset is refused in those cases and otherwise lifts
  the host's fence. Close runs the host's close once. Undeclared backends are unchanged (the existing Gym tests and
  every passing package's digest, below).
- `mhs/driver/families.py`: `GymnasiumDriver.process_by_backend` (validated per backend: no hardware key, a
  package-relative `.module:attribute` entry, not combined with the asynchronous, dm_env or timing profile on one
  backend). `open_native` builds the `ProcessHost` (it never imports the entry), the bridge gets the profile and the
  host, and a manifest is never projected between backends whose profiles differ.
- Gate: G6 `HOST_FAIL_OPEN` (`mhs/driver/behaviour.py`, `HostFilter`): a gate filter on the host makes the read-back
  answer another value, makes the stop fail, or kills the host before the stop; each e-stop must end `failed`
  `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held. G7 (`mhs/driver/check.py`): the host's own members are not
  looked up upstream, and `HOST_PATH` checks every declared path of every backend (the first name an attribute of
  `native` in the clone, every further name and every read-back field name present in the clone at the pin).
  `mhs/driver/_repotests.py`: `guard_process()` sets `MHS_PROCESS_GUARDED=1` and `GUARDED`, so a host started under
  the gate applies the same network and device guard.
- Documentation: `sdk/docs/sim-host.md` (new), `sdk/docs/README.md`, `sdk/docs/bridges.md`,
  `sdk/docs/gym-live-routes.md`; `handoff/REVIEW.md` item 5 (what a reviewer traces for a hosted stop).
  `MHS/sdk/INTERFACE.md` is unchanged. No spec requirement changed.

## Packages

- `gh.rickstaa/ros-gazebo-gym`: pass after repair (was blocked, HELPER_MISSING). Both backends run in the host:
  `.fake:FakePandaReachEnv` and the new `.host:make_env` (`gymnasium.make("PandaReach-v1")` after importing
  `ros_gazebo_gym`; never run here). The stop is `gazebo.pause_proxy`, the rospy service proxy of
  `/gazebo/pause_physics` (`core/gazebo_connection.py:50`, `:136-148`), not `pause_sim`, which retries for seconds,
  then calls `ros_exit_gracefully`, and returns without pausing once rospy is shut down (`:328-356`). The read-back is
  `gazebo.get_physics_properties().pause == True` (`:562-580`, `:805-808`). A step unpauses the world before it
  applies its action (`robot_gazebo_goal_env.py:157-163`), which is why a step in flight is waited for and the pause
  sent again. Risk R0 -> R2 (REVIEW.md item 12): with the shipped `direct_control: True` (`panda_reach.yaml:7`) a step
  publishes the joint efforts on `panda_arm_joint_effort_controller/command` (`robot_envs/panda_env.py:100`,
  `:643-657`). The fake models the pause state (construction ends unpaused, a step unpauses then pauses after, a reset
  ends paused) and has two test switches (`stop_ignored`, `step_delay_s`). Disclosed in facts, `safe_state` and the
  fidelity gaps: the controllers keep the last effort command, which acts when the next step unpauses; other clients
  or the GUI can unpause; construction can clone missing packages and fetch remotes, and its rebuild asks before
  `sudo rosdep install` (standard input is `/dev/null` in the host); the meaning of the pause and of the `pause` field
  is gazebo_ros's, outside the clone (in the local `ros-simulation/gazebo_ros_pkgs` at its corpus pin `cd9cc952`:
  `gazebo_ros/src/gazebo_ros_api_plugin.cpp:1725-1729` `pausePhysics` sets the world paused, `:1479-1489`
  `getPhysicsProperties` returns `pause = world_->IsPaused()`; read, not cited by the package, which has no
  companion). The `sim` backend publishes its own F1 fidelity contract (Gazebo's clock, timestep not declared).
  Changed `driver.py`, `fake.py`, new `host.py`, `test_driver.py` (17 cases, `check_driver` kept), `facts.md` (47
  facts), `driver.lock.json` (backends), `reference.json`, `REFERENCE.md`, `RESULT.json` (a HISTORICAL marker and the
  MODEL REVIEW paragraph). G1-G9 pass with the same warnings as before (`G6.NO_NATIVE_CALL` for the seed class,
  `G8.NO_UNIT` x4); the gate digest is `sha256:ec3be2c57949f5884d947ba594f2e472d9ebde16bbaa2ab3e0414df7eef4efaf`, the
  value the blocked RESULT.json already recorded (the digest covers the findings, which did not change).
- `gh.ut-amrl/socialgym2`: blocked retained (`ENTRY_UNVERIFIED` kept). The host would own its lifecycle, but the brief
  asks for the externally launched UTMRS simulator's independent stop with a read-back, and the clone has none: the
  simulator (submodule `submodules/ut_multirobot_sim`, gitlink `b724b60d`, read through the SDK at the pin) advertises
  only two services, `utmrsStepper` and `utmrsReset` (`src/simulator/simulator_main.cpp:248-251`; its topics are
  odometry, scans, markers and states published while it steps); in its default service mode (`:63-64`)
  it only spins (`:259-263`) and advances inside `StepService` (`:182-208`); `sim_start_stop` toggles a state only
  the non-service loop reads (`:67-75`, `:264-290`), and `sim_state` is published only there (`:283-286`). The stop
  would be the host's fence alone, with nothing to confirm it. The shipped `launch.launch` (the constructor default,
  `src/environment/ros_social_gym.py:99`, `:194-200`) does not start the simulator; a generated file
  (`scripts/create_env_template.py:272-287`) or the operator does. `reset()` retries up to 1000 times with one-second
  sleeps and steps the simulator inside (`ros_social_gym.py:293-330`). Only `RESULT.json` changed (a MODEL REVIEW
  paragraph); the fake gate digest is unchanged
  (`sha256:00395b01f7599c836af68774161cb18d8941baef4623d989188ea6bd5d075051`).

Every package keeps its source pin, model authorship and null `reviewed_by`; each review is the last paragraph of its
`RESULT.json`.

## Found, not fixed

- A lockstep simulator whose world advances only on step calls (UTMRS in service mode) has no stop with a read-back;
  the host's fence plus service-mode evidence could become a reviewed "lockstep fence" stop kind (socialgym2), which
  needs a decision.
- `native_factory` with a hosted backend is not supported (G7 does not resolve the paths and reports the host's
  members); no package needs it.
- The facts of rickstaa cannot cite gazebo_ros for the pause semantics without a companion override for a Gymnasium
  card; the companion mechanism serves ROS cards today.
- The host does not pace, does not snapshot, and cannot interrupt a call inside the environment: a call that never
  returns keeps the e-stop unreached until close kills the host. Processes the environment started in their own
  sessions (ROS nodes) can survive a killed host.
- After a registry rebuild the rickstaa card becomes `pass` (no override needed); `prepare.py --sync` then refreshes its
  `task.json`, and the gate must be re-run.

## Results

In the private copy (Python 3.14.7, the validated environment, no bytecode; the shared machine was loaded by other
agents):

- New SDK tests: 47 (`tests/bridges/test_sim_host.py` 38: profile 4, host 22, bridge 12; `tests/driver/
  test_sim_host_driver.py` 9: gate 3, stock server 4, definition 2), with a stdlib-only fixture environment
  (`tests/bridges/sim_host_fixture.py`) that the host imports in a real child process. They include a child under
  another interpreter (`/usr/bin/python3`, 3.9.6), a guarded process (`guard_process()` in a subprocess, then a
  constructor that opens a socket is refused), the endpoint's own streams staying clean while the environment
  prints, an orphaned host stopping and closing its environment, and a package that skips the read-back failing
  `G6.HOST_FAIL_OPEN`. rickstaa's `test_driver.py`: 17 cases.
- Mutants: 34 of 34 killed (`development/p4-sim-host/scripts/mutants.py`; each mutation applied to the source,
  the named tests run, the file restored and its digest re-checked): ten in the endpoint host (fence, ownership, exact
  read-back comparison, refused declarations, dead-host settlement, stop and confirmation before close, standard
  output, guard propagation), eight in the child (its fence, the running-call report, exit containment, refusal after
  an exit, the orphan stop, `unwrapped`, the guard, `sys.path`), nine in the bridge (second stop, read-back
  comparison, dispatch guard, safety status, unfence, reset refusal, unknown outcome, settle hook, unsettled close),
  two in the driver (class-level entry check, projection) and five in the gate (host members, `HOST_PATH`,
  `HOST_FAIL_OPEN`, its read-back filter, `guard_process`). The first round left one survivor (the class-level entry
  check, also refused later by the host constructor); a class-level test now pins it. The second round showed the
  second-stop mutant killed only by the driver-level test: the fixture's `unpause_at_end` did not resume the world
  at the end of a step, so the host-level test did not need the second stop; with the fixture fixed, the third
  round (final code) kills all 34, that one at both levels (logs `mutants-r1.log` to `mutants-r3.log`).
- The fixture fix came after the second suite run; the two new test modules (47) and the package cases were run again
  after it and pass.
- SDK suite, run 1: 3,670 tests, 5 skipped, one failure: the changelog test, because `CHANGELOG.md` had not yet been
  regenerated for this record; after `tools/build_changelog.py` (109 fragments, `--check` passes) that test module
  passed (72 tests). Run 2 (final): 3,670 tests OK, 5 skipped, 709 s. The snapshot had 3,623 tests; the 47 new
  ones account for the rest.
- `collect.py --strict` over all 716 packages whose RESULT.json says pass: every gate passes, every fresh digest equals
  its RESULT.json, all 715 digests of snapshot-5 and all 688 of snapshot-3 are unchanged, rickstaa is the one new
  pass, and the only warning is the known `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`.
- rickstaa: the isolated gate passes G1-G9 (digest above); `show_refs.py` reports 0 bad citations for its 47 facts.
  socialgym2: the gate still passes on its fake with the unchanged digest; it stays blocked.
- `python3 -m mhs.driver --print-interface` equals `MHS/sdk/INTERFACE.md`.
- `MHS/registry/validate.py --no-corpus`: two errors, both for rickstaa and both settled by a registry rebuild (card
  `package_status` blocked against RESULT pass; record evidence `static_scan` against `contract_checked`); with
  `--allow-stale-cards` it passes.

Not run: a registry rebuild and `prepare.py --sync` (the rickstaa card still says blocked until then; the gate must be
re-run after the sync), `build_registry.py --check`, the OpenAI4S integration tests, `tools/oss_export_check.py`, and
any ROS master, Gazebo, MoveIt, UTMRS simulator or hardware.

## Rule deviations

- Once, early in the item, a shell command changed into the rickstaa clone directory to print its path and list it
  (read-only; each command of this harness runs in its own shell). Every other read used absolute paths.
- The UTMRS gitlink of socialgym2 was read through the SDK's own `UpstreamTree` (`git --no-optional-locks ls-tree`
  with an empty hooks path, as the gate reads every clone); nothing in any clone was written.
- One line-number check ran `python3` without the environment script: its import of the new driver test compiled three
  bytecode files into `MHS/sdk/tests/__pycache__` and `MHS/sdk/tests/driver/__pycache__` of the private copy (the known
  trap). They were moved aside to `development/p4-sim-host/moved-aside/pycache-1640/`; none is in the delta.

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and asked, when it was composed with five other
inputs onto the actual tree (`snapshot-5`), for the evidence lens's E1 if the local Noetic gazebo_ros_pkgs companion
fits rickstaa's profile; logged as I16 in the integrator's `MERGE-LOG.json`.

| Edit | Review item | What changed |
|---|---|---|
| I16 | evidence lens E1 | It fits. The corpus clone `ros-simulation/gazebo_ros_pkgs` at its corpus-lock commit `cd9cc952` is gazebo_ros 2.9.3, the ROS 1 Noetic release (`gazebo_ros/CHANGELOG.rst:5-7`, `package.xml:4`), the same reviewed companion the five Gazebo-classic packages of `COMPANION-SOURCES.md` cite; rickstaa's clone is a Noetic catkin package whose CI image is `osrf/ros:noetic-desktop-full` (`README.md:7`, `.ci/Dockerfile.noetic:1`, `package.xml:47`) and whose `GazeboConnection` calls `/gazebo/pause_physics` and `/gazebo/get_physics_properties` (`core/gazebo_connection.py:50`, `:63`). rickstaa's override (its Gymnasium routing of `ros-routing-20261102.json`, unchanged) moved to `MHS/registry/overrides/companion-sources.json` with `companions` gazebo_ros_pkgs (profile `ros1-noetic-gazebo11`, ten version-evidence ranges), because a repository is overridden once; the registry card and `task.json` now carry it. Eight facts cite the companion (`companion:gazebo_ros_pkgs/...`): the API plugin's node `gazebo` and its private namespace, the `pause_physics` and `get_physics_properties` services, `pausePhysics` calling `World::SetPaused(true)`, `getPhysicsProperties` setting `pause` to `IsPaused()` and succeeding only with the ODE engine (which the shipped config selects), and the `pause` field's definition. What a paused Gazebo world still runs is Gazebo classic's and stays uncited (no gazebo-classic companion: the clone shows no Gazebo 11 token). |

The "Found, not fixed" item above ("cannot cite gazebo_ros ... the companion mechanism serves ROS cards today") is
superseded: nothing in the registry or the gate restricts companions to ROS cards (an override needs a dispatchable
strategy; gate G4 lets facts cite a declared companion in any family), and the E-stop and read-back themselves stay
the host's (no ROS binding cites the companion).

Results: all nine gates pass with the companion (G1 checks the clone at its pin, unmodified, and the ten version-evidence ranges; G2 the lock's `companions`; G4 the eight citations), and the digest is unchanged, sha256:ec3be2c57949f5884d947ba594f2e472d9ebde16bbaa2ab3e0414df7eef4efaf; `show_refs.py`: 0 bad citations. A repository case checks the card's companion and the four cited ranges of the pause and the read-back (`test_driver.py`: 18 cases). One sentence was added to the `MODEL REVIEW` paragraph of `RESULT.json`.
