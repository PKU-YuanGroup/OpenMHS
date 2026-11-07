OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Runtime and gate fixes: a confirmed stop once per e-stop, transport natives resolved, record modes, a linear G4 reader

Four defects that the reviews of [ROS wave C](ROS-WAVE-C.md), [helper wave 1](HELPER-WAVE-1.md) and the
[helper integration](HELPER-INTEGRATION.md) recorded as found, not fixed. Claude (`claude-opus-5-5`, a model and not a
human) changed them in a private copy of the 2026-11-05 tree (`snapshot-2`), with tests, and compared every package's
gate before and after. Nothing ran on hardware, a ROS graph or upstream code; every result is `contract_checked` on a
fake.

## 1. A confirmed ROS stop request is not sent again in the same e-stop

The e-stop runs the native stop and then every `safe_state.achieved_by` action (CORE-074). When an action sent the
same upstream request as the native stop, the upstream received it twice per e-stop. The review of
coppolam/ros_mav_swarm_simulator showed why that matters: its hector LAND was bound both as `safety_bindings.estop`
and as a `safe_state=True` action, and every LAND goal first re-enables the motors. Twenty-two ROS packages of the tree
that load (twenty of them passing) bind one request both ways: Gazebo `pause_physics`, a joint lock that overwrites its
saved limits when repeated, a simulator reset that teleports the robot, a velocity-source selector, gripper and
dashboard stops.

- **ROS bridge** (`bridge/ros.py`): `estop()` opens a ledger of the stop requests of this e-stop. Two bindings are one
  request when they call the same service or action with the same type, profile, literal request, success predicate and
  timeout (a binding with another timeout sends its own request). Identical `safety_bindings.estop` and `.safe_state`
  bindings are sent once when the first succeeds. A safe-state command of the e-stop attempt whose request is in the
  ledger and was confirmed successful is answered from that request's response, which it still maps and checks against
  its own output contract before the safe state is committed (an existing test,
  `test_stock_safe_action_validates_complete_output_before_achieved`, failed while a first version skipped the call).
  After any other outcome the command sends its own request at once: the earlier request failed, timed out or was not
  confirmed. A first version failed the command without a second transmission; the orchestrator decided after the review
  that a repeated stop is harmless and that the independent safe-state path must not be lost within an attempt (the
  principle of S9-01). A request still in flight is awaited until the command's budget is down to its own request's
  timeout or to half, whichever is less; if it has not succeeded by then, the command sends its own request with the
  rest of its budget. Native work after the request (an interrupted goal's terminal result) still makes a fresh stop
  due. The bridge's own stop never consults the ledger: should a safe-state command ever send the identical request
  before it (by winning the safety lane first), the request goes out twice; a stop is never lost.
- **Server** (`server.py`): every action is called; the server skips nothing. On an SDK-owned ROS route only (the SDK's
  RosBridge itself, or a RosDriver whose `call` and `make_bridge` are the SDK's, read statically with
  `inspect.getattr_static` from modules already loaded, so no package code runs and nothing is imported on the e-stop
  path; an import there outlasted the reference conveyor's stop budget in a first run), each action call of an e-stop
  attempt gets `ctx.extra["estop_shared"]`, a report list of that call only; the server records a report only when it
  names `native` or another `achieved_by` action, and nothing in the list can break the receipt. The e-stop receipt, and
  the background confirmation receipt of a retry, list the shared commands in `x-vendor.shared_stop_requests` (x-vendor,
  because the output schema of `cap.motion.estop.v1` is closed).
- **Direct drivers are unchanged**: the runtime cannot see which native calls a method makes, so an `@estop` method
  and a `safe_state=True` action that reach one native method both run (found, not fixed below). A first version had
  an opt-in declaration; the Sonnet review (s9) found that it skipped the action even when the native stop failed or
  hung, and that a driver could forge the skip, so it was withdrawn.
- **Unchanged**: the latch is set first; running operations are cancelled; the receipt is `completed` only when every
  step succeeded; a failed or unconfirmed stop keeps the latch and is retried in the background (SAFE-040), each retry
  a new e-stop that sends the stop once more; a client's own call of a safe-state action is always sent.
- **Spec and docs**: CORE-074 (`spec/core.md`), `docs/ros-driver.md`, `docs/driver-authoring.md` (the fakes section).

Tests: `tests/safety/test_estop_stop_once.py` (19): a service and an action goal bound twice, identical `estop` and
`safe_state` bindings, a different request still sent, another success predicate and another timeout (each sends its own
request, another timeout even after a success), the command's own output contract, a failed, a timed-out and an
unconfirmed identical request (each leads to exactly one more send, by the command, which is confirmed) and the retry, a
native stop still in flight when the actions start (answered within the wait: shared; still unanswered: the command
sends its own within its budget, and the wait spends that budget), an explicit call, a package that overrides the call
path (no report, no sharing), the server's check of the reported sender, the route check importing nothing, and a direct
driver whose action still runs. Seven of the eight first ROS cases fail on the unchanged SDK. Nine mutants of the shared
logic (identity without the success predicate or the timeout, a failed request reused as a success, a failed or
unanswered request failing the command unsent, a request in flight awaited for the whole budget or not at all, every
route or no route reporting, any sender recorded) are each caught. A probe of the 22 ROS packages above
(`scratch/probe_ros_estop_sends.py` in the batch directory) counted two transmissions of the stop per e-stop before the
change; after it, 18 of them (17 passing) send it once, every receipt `completed` with the safe state achieved, and four
whose package wraps `call` or `make_bridge` (to shape receipts or check inputs: anhtuduong/ur5legovision,
frankarobotics/franka_ros and franka_ros2, yizhengzhang1/robomaster-simulator) are served as before and still send it
twice.

## 2. G7 resolves a transport family's native

G7 checked a serial or SCPI driver's sent command tokens and never looked up its `native`, so an invented symbol
passed (`check.py`, the transport branch): moler-group/scanning-squid named
`scanning_squid.instruments.heater:EL320P`, a module path its clone does not have. G7 now resolves the native of a
serial, SCPI, ROS, HTTP, SiLA 2 or MCP-client driver in the clone at the pinned commit, with the card's file hint, as it
resolves other families' classes (`_g7_transport_native`, `upstream.definition_surface`). Such a native is provenance
and never imported, so a module-level function or name counts as well as a class: seven passing SCPI and serial
packages name a script's function or its instrument variable (`keithley2400:open_connection`,
`AgilentControl:inst`). The module's statements are read in the order they run: a bare annotation, an augmented
assignment, a name bound only under `if False:`, `if 0:`, `if TYPE_CHECKING:` or `while False:`, and a deleted name
bind nothing (Sonnet review s9). An unset native (every ROS package) has nothing to resolve; the tag bridge already
resolved its own. All 155 transport-family packages resolve exactly as before this refinement. Tests:
`tests/driver/test_transport_native.py` (9).

## 3. A reviewed override field for a record's modes

A record's modes come from the catalogue row, a README-head scan and role defaults; no override could correct them.
mrw-code/ros_morphology_robot (an Arduino G-code stage over pyserial) and mgreiff/crazyflie-project (a Crazyflie over a
Crazyradio; its only simulation is a Simulink model) are real hardware that the scan recorded as simulated. An override
may now carry `modes`, the record's complete mode set (1 to 3 of `hardware`, `simulated`, `replay`, hardware first):
it replaces the record's modes (classification `mode_override`, rule `override:modes`, with the scanned modes kept as
`scanned_modes`), so `simulation`, `hardware_free`, the device plan and the card's `safety.expected_mode` follow. It
never removes a hardware mode the scan found, which would lift the hardware rules on one model-written line (Sonnet
review s9): `build_registry.py` refuses such an override and one on a record of tier D or X, and `validate.py` checks
both and that the record carries the reviewed modes. Changed: the overrides schema, `triage.py`, `build_registry.py`,
`validate.py`, the `taskcards.py` docstring and the overrides README; tests `MHS/registry/tests/test_mode_overrides.py`
(8).

`MHS/registry/overrides/mode-corrections.json` holds the two reviewed entries, each justified "Model review of the
waiting cards, 2026-11-05: ...". Each repository may appear once across the override files, so the two wave C routing
entries moved there from `ros-wave-c-routing.json`, unchanged except for `modes` and the justification.

The registry was rebuilt in the private copy (`build_registry.py --jobs 8`: five generated files changed) and
`prepare.py --sync` refreshed no `task.json`: no card changed, because the wave C routing had already made both cards'
`safety.expected_mode` hardware. The records changed: both carry the `mode_override` (rule `override:modes`, with the
justification as evidence); mgreiff's modes went from `hardware, simulated` to `hardware`, so `simulation` and
`hardware_free` became false and its device plan lost the planned simulated device; mrw-code's modes were already
`hardware`. The registry README, `coverage.md` and the ROS 1 family page count one dual-mode and one simulated record
fewer. Both packages were re-gated: each still declares `mode = "simulated"` and fails G3 `MODE_MISMATCH` against the
hardware card (G5 to G9 not run), as it already did on the unchanged tree. That failure is not new: their `RESULT.json`
digests were recorded by the wave C review before the routing rebuild flipped the cards, and `collect.py` does not
compare a blocked package's digest. Their `RESULT.json` files were re-recorded with the current digest, `failed: [G3]`
and one sentence in the model review paragraph; both stay blocked until a rebuild as hardware drivers with a fake
backend. toppers/hakoniwa-digital-twin got no entry: its clone is a digital twin with a Unity-simulated sensor and
robot beside the real LiDAR and TurtleBot3 (`digital/`, `real/`, README.md:114-115), so the evidence is not as clear,
and its passing package (mode `simulated`) would fail G3 under a hardware card.

## 4. G4's number reader runs in linear time

The pi-term and quantity patterns wrote a number `\d+\.?\d*` before a required continuation, so on a run of digits
they retried every split at every digit (cubic: 800 digits about a second, 5,000 more than two minutes); the
`np.ones` pattern had two adjacent blank runs (quadratic on blanks). A number is now `\d+(?:\.\d*)?`, which matches
the same strings and tries their ends in the same order with one split each; a number that must be followed by more
of the pattern never starts right after a digit, and a pi term without a sign never starts right after a blank,
where a match never starts anyway (the same match starts one character earlier). 50,000 digits now take milliseconds.
A cited `pi / 0`, which raised ZeroDivisionError and stopped the gate, now shows no angle, and a literal no float
holds (`Discrete(n)` of more than 308 digits, a hex, binary or octal literal past the float range), which raised
OverflowError or ValueError, now shows nothing more, as `range()` already did. Tests:
`tests/driver/test_ref_values_linear.py` (6: the snapshot's patterns as the reference reader on 6,008 lines in three
units, the zero divisor, the huge literals, timing bounds on runs of digits, decimals, blanks and signs, linear growth,
the 4,301-digit line that `test_ref_values` could only read in parts). During the change, 1.2 million random lines
built from the reader's forms gave the same numbers under both readers.

## Gate digests

The gate of every package with code ran on the unchanged copy and on the changed one: 788 packages (681 pass, 106
blocked, 1 skip-proposed), comparing the stable digest and the findings of every report, not only the digests of the
passing packages that `collect.py` compares.

- **All 681 passing packages keep their digests**, each equal to its `RESULT.json`. The passing ROS packages that bind
  one stop request twice send it once per e-stop when it succeeds (seventeen) or, behind a package wrapper, twice as
  before (three), with the same findings; direct drivers are unchanged; every passing transport native resolves; the G4
  reader reads the same numbers.
- **One digest changed**: moler-group/scanning-squid (blocked) now fails G7 `NATIVE_NOT_FOUND` for its invented native
  (G9 not run). This is the intended correction. Its `RESULT.json` was re-recorded (`gate.digest`, `failed: [G7]`, one
  sentence in the model review paragraph); its `RESULT_UNTRUSTED` warning (a passing gate on a blocked package) is gone.
  The author's opening "PASS on the fake backend" of its notes, and of mgreiff's, is marked superseded (mgreiff's
  author text lost 72 characters at its end to the 8,000-character limit, marked " [...]").
- **Re-recorded although their digests did not change here**: mrw-code/ros_morphology_robot and
  mgreiff/crazyflie-project (section 3), whose recorded digests had been stale since the wave C routing rebuild.
- **Unchanged and not re-recorded**: four blocked or skip-proposed packages without a recorded digest
  (mattgbiz/velmex-xyz-stagecontrol-python, quantumquadrate/k10cr1, tolland/python-tecan-genesis,
  simpler-env/simplerenv) and caelan/ltamp with an older one; each gave the same digest before and after.

Every re-record keeps `status` and `blocked_on`; no `driver.lock.json` changed (`authored_by` kept, `reviewed_by`
null); the original `RESULT.json` files are kept in the batch directory.

## Found, not fixed

- Only the ROS bridge takes part in the sharing rule. The SCPI, serial, python-object, tag-bridge, HTTP,
  SiLA 2, MCP-client and pymmcore bridges do not share their stop requests, so a stop bound both as their e-stop and as
  a safe-state command still goes out twice (scanning-squid wrote `OFF` both ways).
- Direct-driver stops bound both ways still go out twice: 127 passing direct drivers make the same native call (104)
  or call the same helper (23) in their `@estop` method and a `safe_state=True` action (a static scan of `driver.py`).
  A future opt-in must skip such an action only after a confirmed successful native stop (never after a failed or
  unanswered one, which loses the independent safe-state path), take the coverage from the validated model rather
  than from methods a package can override, and check it in states other than a fresh one.
- A ROS stop can still arrive more than once per e-stop by design: a safe-state command after an identical request that
  failed, timed out or was not confirmed, or that was still unanswered when the command had to send; the fresh stop
  after an interrupted goal's terminal result; a safe-state command that runs after such a terminal (the state changed);
  and every background retry. A stop that must never arrive twice (hector's LAND) is still not an acceptable stop. A
  `cap.motion.estop.v1` command used as the native stop opens no ledger (no package does this).
- G7 checks that a transport family's native exists, not that it is the card's entry symbol, and not the members its
  commands use.
- No other super-linear input of the G4 reader was found (runs of digits, decimals, blanks, signs, exponents,
  underscores, separators and the bracketed forms were timed up to 100,000 characters); other gates' scans of cited
  text were not timed.
- Blocked packages' recorded digests are not compared by `collect.py`: mrw-code and mgreiff had failed G3
  `MODE_MISMATCH` since the wave C routing rebuild flipped their cards to hardware, under digests recorded before it.
- Other records may carry scanned modes a review would correct: toppers/hakoniwa-digital-twin keeps `simulated` for a
  read-only package whose documented run includes real hardware (see section 3); only the two named records were
  corrected.

## Result

The change was made and checked in a private copy of the 2026-11-05 tree
(`work/handoff-runs/claude-20261104/development/s2-small-fixes/project`, read-only links to the clones and to the
registry builder's inputs); a second untouched copy gave the "before" of every comparison. On the final state:

- The SDK suite: 3,246 tests OK, 6 skipped (3,212 before; 34 new); its folders `tests/safety` (497), `tests/driver`
  (761, 1 skipped), `tests/bridges` (581, 1 skipped) and `tests/endpoints` (78, 4 skipped) also ran on their own. The
  registry suite: 318 tests OK (310 before; 8 new).
- `collect.py --strict` over the 681 passing packages and the three re-recorded ones: the 681 pass the gate with the
  digests their `RESULT.json` records, and the only warning among them is the historical `UNVERIFIABLE_CITATION` of
  gh.amsikking/thorlabs_mcm3000; the three re-recorded packages fail as recorded (G7, G3, G3) with their recorded
  digests. After the last ROS change (a command sends its own request after a failed, timed-out or unconfirmed identical
  one) it ran again over the 75 passing ROS packages, the two blocked ones of the 22 that bind one request both ways and
  unitreerobotics/unitree_ros (which does not load), 78 packages: the same digests, the three non-passing ones included.
  Comparing the stable digests and findings of all 788 packages with code before and after (on the final code) found
  only scanning-squid's changed; nine blocked packages whose gate passes keep their `RESULT_UNTRUSTED` warning, as
  before (scanning-squid left that list).
- `build_registry.py --jobs 8` changed five generated files (the two records, the registry README, `coverage.md`,
  `families/ros1.md`) and the aggregates; after the three re-records a second build changed the `gate_digest` that the
  records of scanning-squid, mrw-code and mgreiff copy from their packages, and after the review's fix round a third
  added `scanned_modes` to the two corrected records; `prepare.py --sync` refreshed no `task.json` any time;
  `validate.py --no-corpus` passes; `build_changelog.py --check` passes.
- `build_registry.py --check` on the final state: 0 generated files differ.
- Not run: the OpenAI4S integration tests, `tools/oss_export_check.py`, `dispatch.py --check-pilot`, any ROS graph,
  simulator, native transport, upstream code or hardware. Claude Sonnet (`claude-sonnet-5-5`, a model) reviewed the
  first version (review s9); this record describes the fix round that answered it, which has not been re-reviewed.
