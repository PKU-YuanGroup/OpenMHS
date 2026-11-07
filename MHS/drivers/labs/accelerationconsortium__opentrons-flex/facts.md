# Facts and tags for gh.accelerationconsortium/opentrons-flex

Every fact cites its source at commit `2639016ee9f234949aaf596c2ab2b93694eb0e0b`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`).  The driver repeats each fact;
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FlexMotionController is a thin wrapper of OT3API: it reuses the OT3API implementation (CAN, calibration), provides a surface for motion, pipette and lights, and serialises hardware access through a lock shared with HardwareProxy | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:99-110 |
| stop() is documented to halt all motion without waiting for the operation lock: it marks the recovery state halted, runs the OT3API halt() as a task and awaits it to completion; a cancellation that arrives meanwhile is re-raised only after the halt finished | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:291-305 |
| mark_halted() increments the operation generation, requires a full robot home and cancels every active robot operation task other than the current one | upstream_code | src/unitelabs/opentrons_flex/io/recovery_state.py:47-54 |
| operation_ready is false while a full re-home is required, and the operator guidance then begins with 'Fully re-home all robot axes' | upstream_code | src/unitelabs/opentrons_flex/io/recovery_state.py:24-45 |
| _assert_operation_ready raises NotHomedError ('The robot is recovery-gated. ... before retrying.') when the recovery state is not operation-ready | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:496-499 |
| A cancelled actuation registered by _active_operation marks the robot halted and awaits an OT3API halt() before its hardware lock is released; a failure of that halt is logged, not raised | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:208-234 |
| home(axes=None) homes all axes; the operation-ready check runs only for a partial home (axes given), and a full home that no halt interrupted marks the robot fully homed | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:239-249 |
| move_to(mount, point, speed=None) checks the recovery gate, validates the target, moves the mount to the absolute deck point and returns the gantry position read back after the move | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:255-269 |
| The absolute-target validation rejects deck targets outside the transformed Flex machine-axis bounds of the OT3API backend | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:512-534 |
| translate_motion_errors turns the OT3API PositionUnknownError and PositionEstimationInvalidError into NotHomedError and OutOfBoundsMove into MovementOutOfBoundsError | upstream_code | src/unitelabs/opentrons_flex/io/_errors.py:370-395 |
| NotHomedError is documented as a move refused because the robot's position is unknown: home the robot before requesting a move | upstream_code | src/unitelabs/opentrons_flex/io/_errors.py:177-184 |
| The connector's SiLA EmergencyStop runs FlexMotionController.stop() and states that a re-home is required before resuming | upstream_code | src/unitelabs/opentrons_flex/features/motion_control.py:440-461 |
| The connector's SiLA Home homes every axis and is documented as required after an emergency stop before further motion | upstream_code | src/unitelabs/opentrons_flex/features/motion_control.py:163-182 |
| The parity matrix names MotionControlFeature.EmergencyStop as the single pre-emptive, robot-wide halt path | vendor_doc | docs/parity_matrix.json:124 |
| set_lights(button=None, rails=None) sets the status-bar and/or deck lights under the operation lock; get_lights() returns the light state through the lock's observation view | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:714-722 |
| The lock's observation view acquires the underlying lock with acquire() unless that lock offers acquire_observation, waiting at most the lock's timeout_s | upstream_code | src/unitelabs/opentrons_flex/io/hardware_proxy.py:65-89 |
| machine_status() reads the cached E-stop state, the door state and the derived error flag without CAN I/O or the operation lock | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:181-194 |
| is_simulating reports whether the underlying OT3API is a simulator backend | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:174-177 |
| build() makes a standalone controller with its own OT3API and lock: simulate=True builds the OT3API hardware simulator, simulate=False the real CAN hardware controller | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:130-153 |
| disconnect() releases the hardware resources of a standalone controller by calling the OT3API clean_up() under the operation lock | upstream_code | src/unitelabs/opentrons_flex/io/flex_motion.py:726-729 |
| The README says one shared OT3API serialises the SiLA and HTTP servers so their CAN commands cannot interleave, and avoids the 'hardware already initialised' error two separate processes would hit | vendor_doc | README.md:16-20 |
| The README says the standard opentrons-robot-server service is disabled on deployment and the sila2-connector service owns the hardware | vendor_doc | README.md:32-33 |
| Motion is exposed per mount (LEFT, RIGHT, GRIPPER) in deck coordinates (x, y, z mm), matching the Flex hardware API | vendor_doc | README.md:39-40 |
| The operator preparation checklist says to close the door, disengage the E-stop, clear all travel corridors and keep the E-stop reachable | vendor_doc | docs/flex_system_acceptance.md:56-58 |

## Tags

`opentrons`, `flex`, `ot-3`, `gantry`, `robot-arm`, `motion`, `asyncio`

## Coverage and gaps

- Bound: the OT3 simulator flag, status-bar/deck lights (read and write), cached machine status, full home
  (`x-cap.accelerationconsortium.home_all.v1`, also the declared re-enable), one absolute deck move
  (`cap.motion.cartesian_pose.v1`) and the native halt (`x-cap.accelerationconsortium.halt_motion.v1`, also the
  safe-state action and the `@estop` path).
- The catalogue classes `cap.motion.home.v1` and `cap.motion.stop.v1` are not bound: their optional `axes`,
  `speed_scale` and `deceleration` inputs have no counterpart in the native `home()` (full home only in this binding)
  and `stop()` (no deceleration profile), so the skeleton-schema expansion would publish inputs the driver refuses.
  The two extensions are the exact full-home and halt operations.
- The move action addresses the LEFT pipette mount because `cap.motion.cartesian_pose.v1` has no mount field.  The
  production adapter and the fake also accept `right` and `gripper`, but the driver does not expose a mount input.
  No text file of the clone states the deck travel, so x, y and z are `operator_required`; the upstream also checks
  each target against the OT3API machine-axis bounds before the move (`flex_motion.py:263`, `:512-534`).
- NOT COVERED: aspirate/dispense, blow-out, prepare-for-aspirate, tip pickup/drop and tip presence
  (`get_tip_presence` needs an `OT3Mount`); nozzle configuration; the gripper and labware movement; the Heater-Shaker,
  Thermocycler, Temperature Module, Plate Reader and Stacker controllers; calibration; pause/resume (the native
  `pause()` is a software pause with no sensed state, so the driver does not report it as quiescence); the embedded
  HTTP robot-server; and the SiLA2 feature layer (this driver binds the IO controller class instead).
- Stop path: the `@estop` method and the safe-state action call `FlexMotionController.stop()`, the call behind the
  connector's own SiLA EmergencyStop.  It cancels the registered in-flight operation and awaits the OT3API `halt()`
  without the operation lock; the cancelled operation awaits a halt of its own before releasing the lock.  A failure
  of the e-stop's halt propagates (the receipt fails and the latch stays); a failure of the cancelled operation's
  halt is only logged upstream.  Nothing senses motor standstill afterwards, and what `OT3API.halt()` sends on the
  CAN bus, and whether the motors stay energised or hold position, is Opentrons code outside the clone.  The halt
  does not engage the physical E-stop; `estop_physical_ref` cites the operator checklist that keeps the independent
  Flex E-stop reachable.  One e-stop sends the halt several times (the `@estop` method, the safe-state action, the
  runtime's cancellation-to-safe-state of every cancelled command, and the second run that CORE-086 makes after
  commands in flight settled); each repeat only marks the robot halted again.
- Recovery: after a halt the connector refuses every actuation except a full home (`recovery_state.py:24-54`,
  `flex_motion.py:239-249`, `:496-499`).  The full home is the declared re-enable (CORE-086): the latch refuses it,
  the safety reset (no `@reset` hook) only releases the latch and moves nothing, and the reset output names it.  A
  move refused for a required home is reported `MHS.DEVICE.PRECONDITION_UNMET`.  Any home or move that the runtime
  cancels, or that outlasts its request deadline (30 s unless the client passes a longer one, at most 600 s), is
  halted by the upstream cancel path and leaves the robot needing a full home again; the clone states no duration
  for a full home, so a client sends it with a deadline long enough for the robot.
- The fake: the upstream simulator (`FlexMotionController.build(simulate=True)`, OT3API `build_hardware_simulator`)
  needs the uninstalled Opentrons 8.8.1 stack on Python 3.10 and cannot run in the gate.  The package fake is an
  in-memory stationary stand-in (F0), not the upstream simulator and not a recording; its initial values are
  placeholders.  It models the connector's recovery gate as the clone defines it (a halt requires a full home;
  moves and partial homes are refused `NotHomedError` until one), and refuses non-finite targets.  It does not
  model the OT3API machine-axis bounds, an unknown position before the first home (OT3API `PositionUnknownError`,
  translated at `_errors.py:386-389`; the upstream tests home before moving), E-stop or door changes, moves that take
  time, or the operation lock: on the standalone controller a light read or write waits for a running move.
- Deployment of `native.py`: it builds its own OT3API on the Flex CAN bus with the standalone `build(simulate=False)`
  (no shared-lock mode, no HTTP robot-server).  The README says one shared OT3API avoids the "hardware already
  initialised" error of two processes and that the connector service owns the hardware (`README.md:16-20`,
  `:32-33`), so the `sila2-connector` and `opentrons-robot-server` services must be stopped first.  The upstream needs
  Python 3.10 and `opentrons==8.8.1` (`pyproject.toml:20-23`).  `teardown` calls `disconnect()` (OT3API
  `clean_up()`), as the connector's own exit path does.
- Licence: the clone has no LICENSE file and `pyproject.toml` declares no licence; the card says `NOASSERTION` and
  `publish_review: required`, so the owner decides before publication.
