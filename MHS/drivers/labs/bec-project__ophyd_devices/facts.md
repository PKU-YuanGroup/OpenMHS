# Facts and tags for gh.bec-project/ophyd_devices

Every fact cites the pinned clone at commit `2141d541b915562deb9d530d6d41ebb8e4585b1d`. `upstream_code` refs name
`path/in/clone:LINE` or an adjacent range. The same facts are written into `driver.py` (`facts = [...]`); the
reference file is generated from the driver, not from this page.

Tags: `ophyd`, `epics`, `motion`, `positioner`, `bec`, `psi`.

## Selected entry

`PSISimplePositioner` (`ophyd_devices/devices/simple_positioner.py:7`) is the selected card entry symbol. It is a
concrete positioner with four direct `Component(EpicsSignal, ...)` declarations and the inherited `move()` and
`stop()` interface. `EpicsMotorEC` and `EpicsUserMotorVME` were not selected: their class bodies and ancestry carry
executable class-body values, external motor ancestry and helper calls that the direct driver would have to replace
with a small, reviewable subset; `PSISimplePositioner` exposes the primary axis control with less unexposed behavior.
`SLSInfo` is a read-only monitor whose `__init__` subscribes with a Signal method that the Ophyd source proof
refuses, and `DelayGenerator` is a PseudoPositioner whose constructor rewrites suffixes dynamically; neither is the
card's motion control here.

## Facts

| fact | source | ref |
|---|---|---|
| `PSISimplePositioner` subclasses `PSISimplePositionerBase` and declares `user_readback`, `user_setpoint`, `velocity` and `motor_done_move` as ophyd `EpicsSignal` Components at suffixes R, S, V and D, and no `motor_stop`. | upstream_code | ophyd_devices/devices/simple_positioner.py:7-11 |
| `PSISimplePositionerBase` declares `user_readback` and `user_setpoint` as required Signals, `velocity`, `motor_stop` and `motor_done_move` as optional Signals, `stop_value=1`, `done_value=1` and `use_put_complete=False`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:76-84 |
| The constructor accepts `prefix`, `name`, optional `limits`, `deadband` and `override_suffixes`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:86-97 |
| `override_suffixes` re-initialises a named Signal with `prefix + suffix` only when the class implements it; for a Signal still set to the optional sentinel it only logs that the class does not implement it. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:133-146 |
| `move()` calls `super().move(position, timeout=..., moved_cb=...)`, calls `_setup_move(position)`, waits only when `wait` is true, and returns the `MoveStatus`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:232-276 |
| `stop()` writes `stop_value` to `motor_stop` when `motor_stop` is not the optional sentinel; otherwise it reads `user_readback.get()` and puts that value to `user_setpoint`, then calls `super().stop`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:316-322 |
| `PSIDeviceBase.stop()` calls `on_stop()`, sets `stopped=True`, cancels registered stoppable status objects and calls `super().stop`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_device_base.py:158-168 |
| `stage()` sets `stopped` back to False when the device is not staged. | upstream_code | ophyd_devices/interfaces/base_classes/psi_device_base.py:109-118 |
| `_stop_stoppable_status_objects` sets a `DeviceStoppedError` on every registered status that is not done. | upstream_code | ophyd_devices/interfaces/base_classes/psi_device_base.py:201-211 |
| `_setup_move` puts the target to `user_setpoint` without waiting and resolves the move through a `TransitionStatus` on `motor_done_move` from 0 to 1 that is registered to be cancelled on stop. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:191-230 |
| The device has no built-in travel range: `limits` is an optional constructor argument; when it is `None`, `check_value` delegates to `user_setpoint.check_value`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:118-174 |
| The constructor takes an egu keyword and stores kwargs.get('egu') or an empty string in _egu. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:123 |
| The `egu` property returns `_egu`. | upstream_code | ophyd_devices/interfaces/base_classes/psi_positioner_base.py:162-165 |

## Scope

The driver serves four fresh reads and two commands:

- `position`, `setpoint` and `velocity` call the corresponding Signal's `get(use_monitor=False)`; `done_moving`
  calls `motor_done_move.get(use_monitor=False)` and compares the result with the device's `done_value`.
- `x-cap.bec-project.axis_move.v1` calls `native.move(target, wait=False)` and polls the device's own
  `motor_done_move` flag, checking the driver's cancellation token between polls. It reports the target, the fresh
  readback and whether the native `MoveStatus` completed successfully. The target has no source bound, so it is
  `Limit.operator_required`; every move is refused with `MHS.SAFETY.LIMITS_UNSET` until the operator's overlay
  supplies the axis envelope.
- `x-cap.bec-project.axis_stop.v1` calls `native.stop()` and reports whether the fresh done flag is set and the
  fresh readback. It declares no input because the native stop has no deceleration parameter. Since the model review
  of 2026-11-05 it is an ordinary hold request, not a `safe_state=True` action (see Safety).

No catalogue motion class fits the source. `cap.motion.joint_position.v1` publishes joint positions in radians and
requires per-binding travel limits, while the clone states no engineering unit and no range. `cap.motion.stop.v1`
is not used either: its optional `deceleration` input would be inherited by the binding, and the native stop has no
deceleration parameter to apply it to. Both extensions are declared in `RESULT.json` `catalogue_requests`.

Not exposed: `motor_stop` does not exist on this class, and `override_suffixes` cannot add it (it only warns about a
Signal the class does not implement). The driver does not expose `velocity` as a write, because the clone states no
velocity range. The `position` property and `report` property of the base class are not used; the driver reads
`user_readback` directly.

Units: the clone states no engineering unit and this driver never supplies the optional `egu` keyword, so `_egu` is
empty and the fields are published as UCUM `1` (dimensionless). A deployment's EPICS EGU is the axis unit; do not
assume a unit. The driver performs no unit conversion.

## Safety

Risk is R1, the card floor. Model review (2026-11-05): PSISimplePositioner has no `motor_stop` Signal, so the
native `stop()` always reads `user_readback.get()` and writes that value into `user_setpoint` (without
`use_monitor=False`; whether that read is fresh depends on the installed ophyd, which is not in the clone), then
cancels the registered move status. That is a new target for the axis, not a stop: a motor record retargets and may
overshoot before it returns, and nothing senses quiescence. The `@estop` method still sends it and then raises
`MHS.SAFETY.SAFE_STATE_UNREACHED`, so the e-stop reports the safe state as not reached with the latch held, and the
stop action is no longer a safe-state action. The selected class has no source-backed stop; the package is blocked
and the gate fails G6.ESTOP_FAILED. The fake's earlier `stop()` froze the axis and set the done flag at once, and its
`move()` reset `stopped`, which upstream only `stage()` does; both hid upstream behaviour and were corrected. The
endpoint's e-stop latch is software; reads stay available while actuating commands are refused.

## Hardware backend

`native.py` imports `ophyd_devices.devices.simple_positioner` only when an operator loads the hardware backend. It
constructs `PSISimplePositioner` under an operator-given prefix and name, passes optional native `limits`,
`deadband` and `override_suffixes`, and waits for the Device's Signals for at most `connection_timeout_s`. The
package has never run the hardware backend and has never connected to an IOC. The fake backend is the only evidence
in this package; its numbers are placeholders and its motion timing is the fake's, not the upstream device's.

## Licence

The card and `driver.lock.json` record BSD-3-Clause. The clone's `pyproject.toml` and `LICENSE` were not changed. This
package is model-authored and unreviewed (`reviewed_by` is null); it is not a hardware review and it makes no claim
of a hardware run.
