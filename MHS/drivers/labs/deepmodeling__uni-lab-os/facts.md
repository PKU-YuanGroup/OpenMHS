# Facts and limits: Runze syringe pump (`gh.deepmodeling/uni-lab-os`)

The card's package is `gh.deepmodeling/uni-lab-os` at
`43923ec9473e2f6d33d3ca1ebca4bf4d507e06b2`. Its entry symbols include
`unilabos.devices.pump_and_valve.runze_backbone:RunzeSyringePump` (`runze_backbone.py:80`), a concrete serial
pump class. The card names `family=pylabrobot` and `helper=PyLabRobotDriver`; that helper serves a PyLabRobot
`LiquidHandler` front end, not this class. The repository's LaiYu files are a PyLabRobot backend whose methods
mostly log and return `True` (`laiyu_backend.py:120-333`), not a complete `LiquidHandler`; this package therefore
integrates the concrete Runze pump as a direct Driver and records the deviation in `RESULT.json`. No upstream code
was imported, installed or run by the gate, and the clone was never modified.

## Tags

`syringe pump`, `serial`, `fluid`, `runze`, `pump`

## Facts

| Fact | Source | Reference |
|---|---|---|
| RunzeSyringePump opens a pyserial link in its constructor and controls one addressed pump. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:80-102` |
| The constructor takes `port`, `address`, `max_volume` (default 25.0) and `mode`; `max_volume` is a constructor option. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:81-85` |
| The constructor sets `total_steps` and `total_steps_vel` to 6000. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:86` |
| The constructor opens `Serial(baudrate=9600, port=port)`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:102` |
| `send_command` writes the command, sleeps 0.05 s and reads until a newline. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:118-123` |
| The constructor catches `OSError` and `SerialException` and stores the port string in `hardware_interface` instead of raising. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:94-106` |
| A command is framed as `/<address><command><R?>\r\n`; `R` is appended unless the command contains `?`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:125-133` |
| The status query `Q` maps a backtick reply to Idle and every other reply to Busy. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:192-198` |
| Position is computed as `pos_step / total_steps * max_volume`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:294-298` |
| `set_position` moves to an absolute volume documented in mL; its `max_velocity` is documented in ml/s. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:300-306` |
| `pull_plunger` and `push_plunger` move a fixed volume documented in mL. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:321-339` |
| `set_max_velocity` converts the velocity to an integer pulse frequency (`velocity / max_volume * total_steps_vel`), caps it at 6000 and runs the `V` command. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:225-229` |
| `get_max_velocity` converts the pulse frequency back with `pulse_freq / total_steps_vel * max_volume`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:231-236` |
| `_adjust_total_steps` would set `total_steps` to 6000 in Normal mode and 48000 otherwise, and `total_steps_vel` to 48000 in AccuratePosVel and 6000 otherwise. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:114-116` |
| `set_mode`, which would set the mode and call `_adjust_total_steps`, is commented out. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:206-210` |
| `_run` sends the command and polls `get_status` every 0.5 s until Idle, holding `_run_lock` for the whole operation. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:152-164` |
| `stop_operation` runs the `T` command through `_run`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:352-353` |
| `_query` holds only `_query_lock` while it frames and sends one command and reads its reply. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:125-134` |
| `get_valve_position` queries `?6` and returns the second character upper-cased. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:281-286` |
| `query_command_buffer_status`, `query_backlash_position`, `query_aux_input_status_1`, `query_aux_input_status_2` and `query_software_version` query the commands `?10`, `?12`, `?13`, `?14` and `?23`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:357-370` |
| `close` sets `_closing` and closes `hardware_interface`. | upstream_code | `unilabos/devices/pump_and_valve/runze_backbone.py:375-380` |

## Limits

No text file of the clone states a numeric flow, volume, position or duration range. The constructor's
`max_volume` is a syringe configuration (`runze_backbone.py:81-85`), and the catalogue's `10000 uL/s` pump maximum
is a class default; neither is a bound of this device. Every numeric write and action input is therefore
`Limit.operator_required`, and the runtime refuses the call with `MHS.SAFETY.LIMITS_UNSET` until the site supplies
the range.

| Input | Unit | Why the operator supplies it |
|---|---|---|
| state `position` | `uL` | The plunger travel is `pos_step / total_steps * max_volume`; `max_volume` is a constructor option and no text states the travel range. |
| state `max_velocity` | `uL/s` | `set_max_velocity` converts the value but states no numeric velocity range. |
| `cap.actuation.pump.v1.flow_rate` | `uL/s` | The clone states no flow-rate range for the installed syringe and tubing. |
| `cap.actuation.pump.v1.volume` | `uL` | The usable volume is the syringe configuration, not a clone-stated bound. |
| `cap.actuation.pump.v1.duration_s` | `s` | The clone has no timed run; it moves a volume and polls until Idle. |

`site-limits.example.json` supplies an example overlay for a 25 mL syringe. It is an operator example, not a claim
about an instrument, and it only narrows the catalogue envelope that the example site chooses.

## Units

* `position`, `plunger_position`, `volume` and `dispensed_volume`: `uL`. The upstream conversions and docstrings
  are in mL (`runze_backbone.py:298`, `300-306`, `321-339`); the driver multiplies by 1000 on reads and divides
  by 1000 on writes and action inputs.
* `max_velocity`, `velocity_init`, `velocity_end` and `flow_rate`: `uL/s`, converted the same way from the clone's
  mL/s (`runze_backbone.py:235`, `255`, `262`; the ml/s unit is documented at `300-306`).
* Step and pulse resolution (model review): the clone converts with `total_steps = total_steps_vel = 6000`
  (`runze_backbone.py:86`) and never changes them, because `set_mode` is commented out (`206-210`). A pump set to a
  higher-resolution mode on its own would therefore move a different volume than commanded. Volumes are truncated
  to whole steps (`318`, `331`, `344`) and velocities to whole pulse frequencies (`227`): with a 25 mL syringe one
  step is about 4.2 uL and one pulse per second about 4.2 uL/s, so a flow rate below that sends `V0`.
* `valve_position`, `velocity_grade`, `status`, `command_buffer_status`, `backlash_position`,
  `aux_input_status_1`, `aux_input_status_2` and `software_version`: strings exactly as the clone returns them.
  The driver does not interpret the auxiliary-input, backlash, command-buffer or valve encodings.

## Stop path and its limits

The `@estop` method sends the same `T` command as `stop_operation`, but through `_query` so it does not wait for
the move's `_run_lock`; it then reads `get_status` until Idle or 0.5 s elapses, and raises
`MHS.SAFETY.SAFE_STATE_UNREACHED` if the pump is still Busy. This is a protocol stop, not a physical e-stop:

* bytes already written into the serial driver's buffer are not flushed, and the upstream class has no flush
  method;
* the pump's valve and plunger hold their last positions;
* the command-buffer query `?10` is only reported as a raw string, not parsed or acted on;
* a move already in flight is interrupted only if the pump honours `T`; the host-side `_run` loop is not
  cancelled, it returns after the next status poll sees Idle;
* the clone documents no Runze command and nothing in it shows `T` holding a later command, so a move command sent
  after `T` is taken to run. The pump action therefore checks for cancellation right before its move command, and
  the position write right after its move, so no move command is sent once an e-stop has started and a move that
  `T` ended is reported cancelled, not applied (model review; the author's version could send the move after a
  completed e-stop, and its fake hid this with a halt flag that also refused every later move);
* a stop that is still Busy after 0.5 s is reported unreached rather than claimed; `get_status` reports Busy for
  every status reply other than the idle byte, so a pump that reports an error after `T` also leaves the e-stop
  unreached;
* the serial port is opened without a read timeout (`runze_backbone.py:102`) and every command reads until a newline
  (`118-123`) while holding `_query_lock`: a pump that stops answering blocks that command, every later command and
  the e-stop's `T` indefinitely; the runtime then reports `SAFE_STATE_UNREACHED` after its e-stop budget.

No text of the clone documents an independent physical e-stop, so the independent stop required at R2 is the
`safe_state=True` action `x-cap.deepmodeling.stop_pump.v1`, which runs the same `T` path. The driver never claims
that the valve, the serial buffer or the host queue is cleared.

## Fake

`fake.py` is a stateful in-memory stand-in for `RunzeSyringePump`. It implements the upstream public methods this
driver uses and the private `_query` used by the stop, with the same names and units. Its starting position,
syringe volume, step count, valve label and query replies are canned test data marked `# placeholder`; none is a
fact, limit or reference, and the fake is not a recording of a hardware run. Motion is modelled in five chunks so
`T` can interrupt it part-way; this is F0 test data, not the upstream simulator or the device's timing. Since the
model review a move holds `_run_lock` as the upstream `_run` does, `T` ends only the move in progress (the
conservative reading above), and the velocity uses the upstream integer pulse frequency; the fake does not model the
serial line, error status bytes or a pump that stops answering.

## Not covered

* The valve port set is not exposed as a write: the clone encodes integer and float positions as `I<number>` and
  accepts a string as an upper-cased command (`runze_backbone.py:273-279`) but states no port map or allowed
  labels, so the driver only reads the current label.
* `set_baudrate`, `initialize` (the `Z` homing command), `set_velocity_grade`, `wait_error` and the raw
  `send_command` are not exposed; `initialize` moves the mechanism and has no MHS homing envelope in this package.
* The `RunzeMultiplePump` multi-address controller and the LaiYu liquid-handling backend are not integrated. The
  LaiYu backend is a stub whose methods return `True` after a log line (`laiyu_backend.py:120-333`), and the
  PyLabRobot-style controllers are not a `LiquidHandler` front end.
* No hardware was attached or run, no upstream code was imported by the gate, and no human reviewed or tested
  anything. `driver.lock.json` has `reviewed_by: null`.
