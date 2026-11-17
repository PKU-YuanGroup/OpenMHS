# Facts and tags for gh.ursa-laboratories/cubos

Every fact cites the pinned clone at commit `38ccd0e7109926ac54cc90b018ff674161f87031`:
`upstream_code` (`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone).  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Gantry is the high-level wrapper around the low-level Mill driver | upstream_code | packages/core/src/cubos/gantry/gantry.py:37-38 |
| The Gantry frame is signed: +X is operator-right, +Y is back and +Z is up; deck_origin puts WPos zero at the front-left-bottom deck corner | upstream_code | packages/core/src/cubos/gantry/gantry.py:40-46 |
| Gantry.connect opens the CNC mill through self._mill.connect and then validates the GRBL settings and checks the alarm state | upstream_code | packages/core/src/cubos/gantry/gantry.py:86-106 |
| Gantry.home homes the gantry with GRBL's standard homing command through Mill.home | upstream_code | packages/core/src/cubos/gantry/gantry.py:158-164 |
| Gantry.move_to takes absolute gantry coordinates x, y and z and an optional travel_z for the height during XY travel | upstream_code | packages/core/src/cubos/gantry/gantry.py:209-223 |
| Mill.move_to documents the direct move order as X, then Y, then Z, with no diagonal interpolation | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:942-943 |
| execute_command writes the command and calls _wait_until_idle when the command does not start with $ | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:413-419 |
| _wait_until_idle blocks until the status line contains idle and raises on an error, an alarm or a timeout | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:656-678 |
| Gantry.stop returns immediately in offline mode and otherwise calls Mill.stop | upstream_code | packages/core/src/cubos/gantry/gantry.py:336-342 |
| Mill.stop sends the real-time feed hold and verifies that the controller entered Hold; it raises when the status is not Hold | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:452-459 |
| GRBL strips real-time characters out of the stream wherever they appear, and the write lock serialises only the write syscall, never a command/response cycle | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:95-106 |
| Gantry.resume delegates to Mill.resume when not offline | upstream_code | packages/core/src/cubos/gantry/gantry.py:358-364 |
| Mill.resume writes the real-time cycle-start byte ~ to the serial controller | upstream_code | packages/core/src/cubos/gantry/gantry_driver/driver.py:466-469 |
| A HOLD pauses motion; Resume can continue the held motion, so the path must be checked before resuming | vendor_doc | docs/operator-ui/gantry.md:93 |
| Gantry.get_coordinates returns the current gantry coordinates as a dict with x, y and z | upstream_code | packages/core/src/cubos/gantry/gantry.py:369-375 |
| Gantry.get_status returns the current status string with normalized coordinates | upstream_code | packages/core/src/cubos/gantry/gantry.py:325-331 |
| The operator UI reports position as current work coordinates; Idle means ready, Jog/Run means moving and ALARM means the controller is locked | vendor_doc | docs/operator-ui/gantry.md:73-75 |
| The Working Volume is the allowed travel range of the configured machine; it cannot detect misplaced labware or loose objects | vendor_doc | docs/operator-ui/gantry.md:22 |
| Working volume bounds are machine-specific and calibrated: use Calibration to measure the physical working volume | vendor_doc | docs/gantry.md:155-169 |
| Homing and jogging move real hardware; before connecting, clear the deck, check the travel path and keep the E-stop within reach | vendor_doc | docs/operator-ui/gantry.md:29-32 |
| CubOS can move real lab hardware; keep an E-stop reachable and start with minimal motion | vendor_doc | README.md:29-31 |
| Always home after connecting; homing drives each axis to its end stops to establish a known reference | vendor_doc | docs/operator-ui/gantry.md:49-54 |
| After a physical crash, hit the E-stop if the gantry is still moving, then re-home; never trust WPos after a crash without re-homing first | vendor_doc | docs/troubleshooting.md:85-91 |

## Interface covered

- Reads: `position` (`Gantry.get_coordinates`, x/y/z in mm), `status` (`Gantry.get_status`) and `healthy`
  (`Gantry.is_healthy`).
- Actions: `x-cap.ursa-laboratories.home_axes.v1` (native `Gantry.home` -> GRBL `$H`),
  `cap.motion.cartesian_pose.v1` (native `Gantry.move_to(x, y, z)`), `x-cap.ursa-laboratories.stop_motion.v1`
  (native `Gantry.stop`, safe_state=True) and `x-cap.ursa-laboratories.resume_motion.v1` (native
  `Gantry.resume`, reenable=True).
- No write: the clone keeps feed rates, travel and controller settings in the machine configuration; this package
  exposes no unbounded or invented setter.
- `device_kind` is `robot.arm` because `cap.motion.cartesian_pose.v1` binds only `robot.arm` (catalog show); the
  machine is a three-axis Cartesian gantry, not an articulated arm.  The driver does not use the other listed card
  entries (Sartorius, Excelitas, Thorlabs and Opentrons instruments): one package integrates one device.

## Limits

- The X, Y and Z targets of `cap.motion.cartesian_pose.v1` are `Limit.operator_required`: the clone stores the
  travel envelope in each machine's calibrated `working_volume` (docs/gantry.md:155-169) and the upstream `Gantry`
  itself only validates that the coordinates are finite (gantry_driver/driver.py:957-959); it does not enforce a
  working volume.  `site-limits.example.json` shows the operator overlay and is an example, not a statement about any
  machine.
- No speed, feed-rate or acceleration write is exposed, so no such bound is declared.

## Safety

- The gantry commands real mechanical motion (README.md:29-31), so the driver declares R2, matching the card floor.
- The native stop is `Gantry.stop` -> `Mill.stop`: a GRBL real-time feed hold that is sent outside the command/response
  cycle (gantry_driver/driver.py:95-106) and checked with one status read containing Hold
  (gantry_driver/driver.py:452-459). There is no polling for stationary axes. It is a pause, not a power removal.
- `estop_physical_ref` cites the machine E-stop the operator documentation keeps within reach
  (docs/operator-ui/gantry.md:32; README.md:30; docs/troubleshooting.md:86-87). These instructions do not supply a
  stop circuit, wiring diagram or validated latency.
- The safe-state action is the same native feed hold.  The declared re-enable is `Gantry.resume`, which writes the
  real-time cycle-start character; the clone warns that Resume can continue held motion (docs/operator-ui/gantry.md:93),
  so it is an explicit new command after the operator reset, never part of it.  There is no `@reset` hook.
- The stop does not cancel a queued multi-axis move: a hold pauses the planner and the pending `execute_command` stays
  in its wait loop; the held path remains and only the operator's explicit resume continues it.  After a feed hold the
  controller status is Hold. The driver now checks controller state before dispatch: moves require Idle; homing
  accepts Idle or Alarm so it can clear a homing lock. Hold, missing and unrecognized states fail before the motion
  call, preventing this endpoint from adding a new queued target while it observes Hold. This check cannot exclude
  another client changing the controller after the read. An explicit resume can continue previously queued motion,
  and a fresh move still needs a checked path (docs/operator-ui/gantry.md:93). Homing is rejected while latched.
- Connection can probe other serial devices even when a preferred port is supplied
  (gantry_driver/driver.py:119-184). Outside Alarm it sets WPos reporting ($10=0), absolute positioning (G90) and
  the configured/default feed rate (gantry_driver/driver.py:302-306,756-769). This changes controller state and must
  not be called as an MHS reset. The reviewed gantry source issues no G21 command: the deployment must establish
  length units before relying on millimetre envelopes.
- Serial reads and in-flight native operations may exceed the MHS stop budget; concurrent readers can consume each
  other's replies because only writes are serialized. Unconfirmed stops remain failed and latched. No controller
  timing or physical-stop performance was measured.
- This package is model-authored and unreviewed.  The loader refuses its hardware backend at R2 until a human sets
  `reviewed_by`; the gate and the tests here exercise the fake backend only, and no hardware run is claimed.

## Fake fidelity

- `fake.py` is an analytic in-memory stand-in, not a recording.  Starting position, status strings and counts are
  test data (`# placeholder`), not upstream facts.
- It models the feed hold as a latched `Hold` status, `resume` as the cycle start, and rejects `move_to`/`home` while
  held; the real controller queues motion during a hold and `_wait_until_idle` times out instead of raising the fake's
  immediate error. Driver guards are tested with accepting native stand-ins so that the fake's refusal cannot hide
  a queued-command defect. It does not model GRBL soft limits, alarms, homing end stops, the serial transport, or timing.
- It implements only public members that exist on `Gantry` (G7) and imports nothing from the clone.

Tags: gantry, cartesian, motion, grbl, cubos
