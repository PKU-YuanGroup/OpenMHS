# Facts and tags for gh.labpy/lantz

This package drives the LabJack U12 wrapper `lantz.drivers.labjack._internal.u12:U12` (u12.py:395). Every fact cites
its source at commit `3e878e3f765a4295b0089d04e241d4beb7b8a65b`: `upstream_code` is a line of the clone. The same
facts are in `driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not
from this page.

| fact | source | ref |
|---|---|---|
| U12 is the LabJack U12 command class of the Lantz labjack driver | upstream_code | lantz/drivers/labjack/_internal/u12.py:395-401 |
| eAnalogIn reads the voltage from one analog input | upstream_code | lantz/drivers/labjack/_internal/u12.py:1908-1916 |
| eCount reads the counter (CNT); resetCounter selects whether it is reset after reading | upstream_code | lantz/drivers/labjack/_internal/u12.py:1977-1983 |
| aiBurst reads a specified number of scans (up to 4096) at a scan rate up to 8192 Hz from 1, 2 or 4 analog inputs | upstream_code | lantz/drivers/labjack/_internal/u12.py:2155-2159 |
| eAnalogOut sets the voltage of both analog outputs | upstream_code | lantz/drivers/labjack/_internal/u12.py:1942-1947 |
| pulseOut creates pulses on any/all of D0-D7 | upstream_code | lantz/drivers/labjack/_internal/u12.py:2624-2628 |
| pulseOutStart takes a bit selection, a pulse count and four cycle-time values as an alternative to pulseOut | upstream_code | lantz/drivers/labjack/_internal/u12.py:2645-2652 |
| reset causes the LabJack to reset after about 2 seconds | upstream_code | lantz/drivers/labjack/_internal/u12.py:2729-2733 |
| localID changes the local ID of a specified LabJack | upstream_code | lantz/drivers/labjack/_internal/u12.py:2584-2588 |
| rawReadLocalId reads the Local ID from internal memory and returns it as an integer | upstream_code | lantz/drivers/labjack/_internal/u12.py:568-576 |
| getDriverVersion returns the version number of ljackuw.dll without hardware communication | upstream_code | lantz/drivers/labjack/_internal/u12.py:2497-2501 |
| getFirmwareVersion retrieves the firmware version from the LabJack's processor | upstream_code | lantz/drivers/labjack/_internal/u12.py:2510-2514 |
| For analog input channels below 8, bitsToVolts maps a 12-bit sample (0-4095) to (bits*20/4096)-10 volts | upstream_code | lantz/drivers/labjack/_internal/u12.py:2388-2403 |

## Limits

| path | rule | why |
|---|---|---|
| local ID write | `Limit.operator_required` | no text file of the clone states the local ID range; the site supplies it in `site-limits.example.json` (the example shows 0 to 255) |
| `x-cap.labpy.sample_voltages.v1.count` | max 4096 | the aiBurst docstring says "up to 4096" scans (u12.py:2159) |
| `x-cap.labpy.sample_voltages.v1.scan_rate` | max 8192 Hz | the aiBurst docstring says "up to 8192 Hz" (u12.py:2159) |
| `x-cap.labpy.set_analog_outputs.v1.analog_output_0` | `Limit.operator_required` | no text file of the clone states the analog output voltage range (the User's Guide is not in the clone); the site supplies it |
| `x-cap.labpy.set_analog_outputs.v1.analog_output_1` | `Limit.operator_required` | the same missing analog output voltage range; the site supplies it |
| `x-cap.labpy.pulse_out.v1.bit_select` | `Limit.operator_required` | no text file of the clone states the bit-selection range; the site supplies it |
| `x-cap.labpy.pulse_out.v1.num_pulses` | `Limit.operator_required` | no text file of the clone states the pulse-count range; the site supplies it |
| `x-cap.labpy.pulse_out.v1.time_b1`, `time_c1`, `time_b2`, `time_c2` | `Limit.operator_required` | no text file of the clone states the cycle-time range; the site supplies it |

The example overlay fills every `operator_required` path. It is an example, not a statement about a real device.

## Safety

The native stop is `U12.reset` (`reset` causes the LabJack to reset after about 2 seconds, u12.py:2733). The e-stop
method calls it, and `x-cap.labpy.reset_device.v1` is the safe-state action that calls the same native reset. No line
of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. This is an R1 hardware
package; the safe-state action and the e-stop method are present, and the runtime latches before either runs.

The package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null). The loader's reviewed_by
refusal applies to a model-written package only at R2 and R3; this R1 package does not claim that protection. The
hardware backend was never opened. The fake backend is an in-memory stand-in, not a recording of a device; its
numbers are placeholders and it returns the requested number of block samples (the real U12 aiBurst arrays have
room for 4096 scans per channel).

NOT COVERED: continuous streaming (`aiStreamStart`/`aiStreamRead`/`aiStreamClear`), digital I/O, the Windows-only
`getWinVersion`, the watchdog, and the low-level raw commands are not exposed. The analog output action echoes the
applied values because the wrapper's `eAnalogOut` has no readback; the local ID write reads back through
`rawReadLocalId`.

Tags: daq, labjack, u12, analog input, analog output, pulse, counter
