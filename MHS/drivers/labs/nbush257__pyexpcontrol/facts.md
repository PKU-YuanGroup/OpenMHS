# Facts and tags for gh.nbush257/pyexpcontrol

Every fact cites its source at commit `06e94c4d22ac2d9fc542a3ebee035a8b9e360ea7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Controller opens the Teensy serial link with ArCOMObject(port, 115200) | upstream_code | python/nebPod.py:267-270 |
| The olfactometer has eight valves: the leftmost bit of the binary string is Valve 1 and the rightmost bit is Valve 8 | upstream_code | python/nebPod.py:1743-1745 |
| set_all_olfactometer_valves asserts an eight-character pattern, reverses it and sends its decimal value as a uint8 | upstream_code | python/nebPod.py:1757-1762 |
| open_olfactometer sends the smell command, the open letter and the valve number as a uint8 | upstream_code | python/nebPod.py:1705-1707 |
| close_olfactometer sends the smell command, the close letter and the valve number as a uint8 | upstream_code | python/nebPod.py:1729-1731 |
| A laser amplitude is a float between 0 and 1 V | upstream_code | python/nebPod.py:782-783 |
| _amp2int clips the amplitude to 0 to 1 and scales it to an integer between 0 and 100 | upstream_code | python/nebPod.py:1318-1340 |
| turn_on_laser writes the letter o twice and the scaled amplitude; turn_off_laser writes o then x and the scaled amplitude | upstream_code | python/nebPod.py:786-806 |
| set_gpio accepts pins 0 to 7 (pins = list(range(8))) and the modes pulse, high and low | upstream_code | python/nebPod.py:1972-1976 |
| start_camera_trig sends the auxiliary begin command and an integer frame rate; stop_camera_trig sends the auxiliary end command and 0 | upstream_code | python/nebPod.py:1258-1284 |
| block_until_read waits until a reply byte is available and then reads one uint8 | upstream_code | python/nebPod.py:1288-1299 |
| set_all_olfactometer_valves waits through wait_for_response, whose default timeout is 10 seconds | upstream_code | python/nebPod.py:1765-1776 |
| start_camera_trig and stop_camera_trig send their command and return without waiting for a reply byte | upstream_code | python/nebPod.py:1258-1286 |

## Limits

- Laser amplitude: `Limit(min=0, max=1, unit="V")`, cited to python/nebPod.py:783 ("a float between 0-1 (v)").
- Olfactometer valve number: `Limit(min=1, max=8, unit="1")`, cited to python/nebPod.py:1743-1745 (Valve 1 and
  Valve 8).
- GPIO pin: `Limit(allowed=[0, 1, 2, 3, 4, 5, 6, 7], unit="1")`, cited to python/nebPod.py:1973
  (`pins = list(range(8))`). The set is written as an allowed set because the line gives the bounds of `range(8)`;
  the largest pin, 7, is one less than the 8 shown, so a min/max citation would not show its own upper bound.
- No other bound is declared: the camera frame rate is left at the upstream default and is not an input, and the
  pulse width of `set_gpio` is not exposed (no line of the clone states a pulse-width range).

## Reads are last-command shadows

`nebPod.Controller` has no method that reads back a valve, laser, GPIO or camera state. The actuator commands only
write: most then wait for one reply byte in `block_until_read` (python/nebPod.py:1288-1299),
`set_all_olfactometer_valves` waits in `wait_for_response` (python/nebPod.py:1765-1776), and the camera-trigger
commands return without waiting (python/nebPod.py:1258-1286). The four `@read` parameters therefore report the last
command this driver sent. They are not a measurement of the hardware, and a reset or a command sent by another
process is not visible to them. The initial values (laser 0 V, all valves closed, GPIO low, camera trigger off) are
the driver's conservative starting shadow, not a claim about a rig that was already running.

## Safety

The `@estop` method calls the upstream `turn_off_laser(0)` (python/nebPod.py:793-806), which sends 0 V to the laser
command. The `x-cap.nbush257.safe_state.v1` action (`safe_state=True`, no input) also calls
`set_all_olfactometer_valves("00000000")` (all eight valves closed, python/nebPod.py:1743-1745) and
`stop_camera_trig()` (python/nebPod.py:1267-1284). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R3 hardware driver (a model review raised it from R2: the README says the analog output drives a "cobalt MLD laser", README.md:50, a
Cobolt MLD head, and Cobolt classes every 06-01 series MLD head 3B). The package is
model-authored and unreviewed, so the loader refuses its hardware backend until a human sets `reviewed_by`.

## Not covered

- Laser power measurement and calibration (`poll_laser_power`, `auto_calibrate`, `mW_to_volts`, `volts_to_mW`): they
  need the Thorlabs photometer and a calibration table that the clone does not supply as a text range.
- Recording control (`start_recording`, `stop_recording`, `start_recording_TTL`, `start_recording_sglx`,
  `set_all_sglx_low`) and the gate/run name helpers (`get_gates`, `get_last_trigger`, `get_runname`,
  `get_subject_dir`): they call the SpikeGLX C API and the filesystem (python/nebPod.py:1628-1660), which the fake
  backend does not model.
- `set_gpio` pulse mode, `laser_pulse_gpio`, the Hering-Breuer commands, the tone and TTL commands, and the gas
  valves (`open_valve`, `present_gas`): no text file of the clone states their parameter ranges, so they are left out
  rather than given an invented bound.
- The camera frame rate is not an input; the action uses the upstream default.

Tags: teensy, olfactometer, laser, gpio, camera-trigger, serial
