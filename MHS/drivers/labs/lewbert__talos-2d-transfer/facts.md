# Facts and tags for gh.lewbert/talos-2d-transfer

Every fact cites its source at commit `2b85b6a9c74b194d4507e3d7713f343a00680a32`: `vendor_doc` (a text file of the
clone such as `README.md` or `docs/*.md`) or `upstream_code` (`path/in/clone.py:LINE`).  The same facts are written
into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The ZC300 XYR stage is driven over Modbus RTU at 115200 8N1 with function codes 0x03/0x04 for reads, 0x06 for single-register writes and 0x10 only for the opcode block (three registers for a move, two for a stop) | vendor_doc | docs/DESIGN.md:45-49 |
| Position X, Y and R is in registers 30016-30021 as IEEE-754 float32 big-endian pairs, and the status register 30012-30015 has bit 9 as the emergency stop | vendor_doc | docs/DESIGN.md:51-54 |
| The opcode block is 30050: 0x0064 absolute, 0x0065 fixed-length, 0x0066 continuous, 0x0067 decel stop, 0x0068 immediate stop and 0x0069 home; axis 0x31 X, 0x32 Y, 0x33 R | vendor_doc | docs/DESIGN.md:55-56 |
| The documented scale is 0.625 micrometres per pulse in X and Y and 0.00125 degrees per pulse in R | vendor_doc | docs/DESIGN.md:58 |
| The absolute-move opcode silently does nothing on the real controller, so every absolute move is composed from fixed-length moves and each distance register is read back before the motion opcode | vendor_doc | docs/DESIGN.md:60-64 |
| move_abs_um computes the relative delta from get_position and calls move_rel_um, which rounds the deltas to pulses with the configured scale | upstream_code | talos/hal/devices/zolix.py:238-268 |
| stop() sends the configured stop opcode to AXIS_ALL, waits with _wait_stopped(0.3), and when that returns False sends the immediate stop and waits with _wait_stopped(0.2); it catches and logs every exception and never raises | upstream_code | talos/hal/devices/zolix.py:347-365 |
| _wait_stopped returns True once no axis reports moving and also when a status read raises, and False when its timeout passes | upstream_code | talos/hal/devices/zolix.py:367-384 |
| get_status reads 10 input registers from 30012 and returns a moving flag per axis (motion word equal to 1), the X and Y limit bits, the three home bits, the estop bit and an alarm flag set when any axis alarm bit is set | upstream_code | talos/hal/devices/zolix.py:390-415 |
| The status word assigns limit bits 0, 1, 3, 4, 6 and 7, home bits 2, 5 and 8, the emergency-stop bit 9 and the axis alarm bits 10, 11 and 12 | upstream_code | talos/hal/devices/zolix.py:83-86 |
| get_position reads six input registers from 30016 and converts pulses to micrometres and degrees with the configured scale | upstream_code | talos/hal/devices/zolix.py:417-431 |
| The constructor creates the driver's lock as a threading.RLock | upstream_code | talos/hal/devices/zolix.py:123 |
| move_rel_um holds the lock while it calls _ensure_not_moving and then, axis by axis, calls _ensure_speed, writes the distance, reads it back and writes the fixed-length opcode | upstream_code | talos/hal/devices/zolix.py:269-290 |
| connect() opens the port at 115200 8N1, reads the motion-state and model registers, and for each axis of _axes_here() writes 0x01 to its enable register and accel_pps2 to its acceleration register | upstream_code | talos/hal/devices/zolix.py:136-164 |
| The constructor defaults include port COM3, slave_address 1, slow_speed_pps 500, fast_speed_pps 2000, accel_pps2 10_000_000 and stop_mode immediate | upstream_code | talos/hal/devices/zolix.py:104-117 |
| TALOS is a desktop application that owns an entire 2D-material transfer bench: the camera, the XYR sample stage, the XYZ transfer stage, the focus axis and the hot stage | vendor_doc | docs/DESIGN.md:25-31 |
| The README warns that controllers can forget their position on power-cycle and says to treat stored coordinates as session-relative and re-establish references after a reset | vendor_doc | README.md:74-75 |

## Scope

The repository is one application for a whole transfer bench (docs/DESIGN.md:25-31).  This package serves one device
class, the Zolix ZC300 XYR sample stage (`talos.hal.devices.zolix:ZolixXYRStage`, talos/hal/devices/zolix.py:99), the
first entry symbol of the card and the device whose upstream stop verifies and escalates.  The other devices of the
repository are not served: the DIY SigmaKoki XYZ transfer stage (`SigmaKokiXYZStage`,
talos/hal/devices/sigmakoki.py:62), the DIY focus axis without a limit sensor (`FocusStageDriver`,
talos/hal/devices/focus.py:59; docs/DESIGN.md:74-87), the Yudian AI-828 hot-stage controller
(`YudianTempController`, talos/hal/devices/yudian.py:50, whose `set_sv` clamps to a configured range, :143-158) and
the camera backends under `talos/hal/devices/camera/`.

## Limits

The X, Y and R travel ranges are `Limit.operator_required`.  The clone states the register map, the scale and the
position encoding but no end stops or travel range for the stage (docs/DESIGN.md:45-58; the defaults file
resources/defaults/default_settings.json:27-46 has none either), and the constructor's serial defaults are deployment
defaults, not a device envelope.  Every move is therefore refused `MHS.SAFETY.LIMITS_UNSET` until the site supplies
its stage envelope.  `site-limits.example.json` is only an example overlay, not a statement about any physical stage.
The envelope bounds targets in the controller's own position frame, and the README says controllers can forget their
position on power-cycle (README.md:74-75); this package exposes no homing, so the site re-establishes the reference
before it relies on the envelope.  Speed and acceleration are not inputs: they are the backend options of `native.py`
(upstream defaults talos/hal/devices/zolix.py:112-116).

## Safety

The native `stop()` is the e-stop (`@estop`) and the safe-state action (`cap.motion.stop.v1`, `safe_state=True`).  It
sends the configured stop opcode (immediate by default) to the all-axes selector, polls the status for up to 0.3 s,
and while an axis still reports moving sends the immediate stop and polls for up to 0.2 s more
(talos/hal/devices/zolix.py:347-365).  It catches every exception, a failed stop write included, and never raises,
and its poll counts a failed status read as stopped (talos/hal/devices/zolix.py:367-384).  The safe-state action
therefore calls the native stop and then makes its own status read: it completes only when that read reports no axis
moving, and it fails `MHS.SAFETY.SAFE_STATE_UNREACHED` when an axis still moves or when the read itself fails, so the
runtime keeps the latch and retries the stop path.  (Model review: the author's version returned `stopped: false` as
a completed result, which the runtime counts as the safe state reached; `test_driver.py` now covers the case.)  The
class's optional `deceleration` input is accepted for schema compatibility but is not applied: the native stop takes
no deceleration parameter and uses the configured stop mode.  The upstream's own comment says this stop path runs on
every release-stop (talos/hal/devices/zolix.py:370-373), so a repeated stop is its normal use; the runtime sends it
twice per e-stop (the `@estop` method and the safe-state action) and once more when a cancelled move ends.

The stop writes no axis-enable register, so the package declares no re-enable, and it has no `@reset` hook: an
accepted operator reset only releases the runtime latch and sends nothing to the controller.  Opening the hardware
backend does change the controller: the upstream `connect()` writes the enable register and the acceleration
(`accel_pps2`, 10_000_000 unless the site passes another value) of every axis in use (talos/hal/devices/zolix.py:104-164).

The native stop waits for the upstream lock, which a move holds while it writes its frames (not while the stage
travels; talos/hal/devices/zolix.py:269-290).  A move that read its start position but had not yet taken that lock
when the e-stop arrived can write its frames after the first stop; the safe-state action's second stop, and the stop
the runtime sends when the cancelled move ends, stop them.  The e-stop budget is the runtime default of 1000 ms (no
`estop_latency_ms` is declared); a stop that has to escalate can use most of it, and an attempt that outlasts it is
reported `SAFE_STATE_UNREACHED` and confirmed later by the background retry.

The controller status register documents bit 9 as the emergency stop (docs/DESIGN.md:54), and the driver exposes it
as a read and as an interlock that blocks the move action.  No line of the clone documents a separate physical
e-stop switch, an e-stop wiring diagram or a safety-rated channel, so the package does not set
`estop_physical_ref` and claims only the safe-state action of SAFE-045.

The move waits for rest by polling the controller status.  An alarm bit, the e-stop bit or the request deadline ends
the wait with a failed receipt; no stop is sent then, so an axis that is still moving finishes its commanded
fixed-length move unless the caller stops it.  Limit-switch bits are not checked: the reported rest position is the
evidence of where the stage stopped.

## Mock

The clone ships a simulated twin of the class, `talos.hal.sim.sim_zolix:SimZolixXYRStage`
(talos/hal/sim/sim_zolix.py:1-2, 23), and no recorded serial traffic.  This package does not use the twin:
`fake.py` is an analytic in-memory fake at the level of the upstream ZolixXYRStage methods, uses only method names
that exist on that class (gate G7), opens no port, and marks every start value and duration `# placeholder`.  It is
not a recording and its fixed 0.08 s move time is not the controller's timing; it does not round targets to whole
pulses, a stop leaves it at its pre-move position, and it has no limit switches, alarm sources or serial faults.  The
fake backend's evidence is `contract_checked` at F0, never a device-level run.

## Not covered

- The native home opcode (0x0069) is not exposed: the upstream `home()` only sends the opcode and returns, and the
  controller's home completion is reported by status bits that the upstream does not wait on; exposing it would
  claim a homed reference the driver cannot confirm.
- The continuous-jog opcode (0x0066) and the per-axis stop are not exposed; the package's primary control is an
  absolute, bounded move and one stop for all axes.
- The upstream `move_abs_um`/`move_rel_um` issue one axis move at a time and do not roll back the axes already
  commanded when a later axis fails; the driver reports that failure as the runtime's failed receipt and does not
  retry.  The controller's configured stop mode, acceleration, speed and pulse scale are deployment settings read
  from `native.py` options, not facts of this bench.
- The clone states no independent hardware e-stop switch and no safety-rated stop; the physical e-stop, if any,
  stays authoritative.

Tags: zolix, zc300, xyr stage, motion, modbus rtu, serial
