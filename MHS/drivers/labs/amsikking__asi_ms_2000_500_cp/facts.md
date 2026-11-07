# Facts and limits for gh.amsikking/asi_ms_2000_500_cp

Every fact cites its source at commit `5f1f6d2cad545d5ae20359fd01e014dfdd21f11f`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`asi_MS_2000_500_CP.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Python device adaptor for the ASI MS-2000-500-CP multi-axis stage controller | vendor_doc | README.md:2 |
| The constructor opens a serial port at 115200 baud with a 5 s timeout; for that baud rate DIP switches 4 and 5 must be DOWN | upstream_code | asi_MS_2000_500_CP.py:24-28 |
| The controller must answer 'Version: USB-9.2k'; another version is refused by an assertion | upstream_code | asi_MS_2000_500_CP.py:32-34 |
| The constructor accepts only the axis tuples ('X','Y'), ('Z',) and ('X','Y','Z') | upstream_code | asi_MS_2000_500_CP.py:39 |
| The lead-screw table gives pitch in mm, encoder resolution in nm and maximum velocity in mm/s for UC, SC, S, F and XF | upstream_code | asi_MS_2000_500_CP.py:43-48 |
| The travel range is required from the caller: axes_min_mm and axes_max_mm become min_position_um and max_position_um in micrometres | upstream_code | asi_MS_2000_500_CP.py:57-64 |
| The upstream default encoder resolution is 10 counts per micrometre and can be overridden at construction | upstream_code | asi_MS_2000_500_CP.py:65-69 |
| _get_position returns the axis positions in micrometres, computed as encoder counts divided by the configured counts per micrometre | upstream_code | asi_MS_2000_500_CP.py:279-298 |
| move_um takes target positions in micrometres, checks them against the configured min_position_um and max_position_um, and rounds them to 0.001 um | upstream_code | asi_MS_2000_500_CP.py:353-365 |
| The motor-moving query reports False only when the controller answers 'N' | upstream_code | asi_MS_2000_500_CP.py:300-309 |
| get_pwm_intensity reads the LED X value as an integer percent | upstream_code | asi_MS_2000_500_CP.py:382-390 |
| set_pwm_intensity accepts an integer from 1 to 99 | upstream_code | asi_MS_2000_500_CP.py:392-398 |
| set_pwm_state accepts off, on, pwm and external | upstream_code | asi_MS_2000_500_CP.py:404-407 |
| The TTL input mode code is 0 for disabled and 10 for toggle_ttl_out; the TTL output mode code is 0 for low, 1 for high and 9 for pwm | upstream_code | asi_MS_2000_500_CP.py:113-155 |
| set_pwm_state programs off as disabled/low, on as disabled/high, pwm as disabled/pwm and external as toggle_ttl_out/low | upstream_code | asi_MS_2000_500_CP.py:408-419 |
| close turns the PWM output off before it closes the serial port | upstream_code | asi_MS_2000_500_CP.py:425-431 |
| The README warns that the test block moves the XY and Z stages and asks to remove samples and the objective before testing | vendor_doc | README.md:5 |
| The README says MS-2000 controllers come in many variants that can connect different devices, so the attached hardware is configuration data | vendor_doc | README.md:10 |
| The README says the adaptor was tested with an MS-2000-500-CP at firmware USB-9.2k, an MS-2000 flat top XY stage with standard lead screws, an LS-50 Z stage with a fine lead screw and an ASI PWM transmitted light LED | vendor_doc | README.md:11 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| pwm_intensity (%) | 1 to 99 | upstream_code | asi_MS_2000_500_CP.py:397 (`assert 1 <= intensity <= 99`) |
| pwm_state | one of off, on, pwm, external | upstream_code | asi_MS_2000_500_CP.py:407 (`assert state in ('off', 'on', 'pwm', 'external')`) |
| move_stage x_um | operator_required | none: the clone requires the caller's travel (asi_MS_2000_500_CP.py:57-64) | site-limits.json |
| move_stage y_um | operator_required | none: the clone requires the caller's travel (asi_MS_2000_500_CP.py:57-64) | site-limits.json |
| move_stage z_um | operator_required | none: the clone requires the caller's travel (asi_MS_2000_500_CP.py:57-64) | site-limits.json |

The three travel bounds are not facts of the controller. The clone asserts a target against
`min_position_um`/`max_position_um` built from the caller's `axes_min_mm`/`axes_max_mm` (`asi_MS_2000_500_CP.py:57-64`),
and the numbers in its test block are example configurations marked "recommended to check and use!"
(`asi_MS_2000_500_CP.py:443-444`). The site overlay supplies the actual envelope; until then the runtime refuses every
move with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example, not a statement about any particular
stage.

Safety: the e-stop calls `set_pwm_state('off')`, which drives the TTL input to disabled and the TTL output to low
(`asi_MS_2000_500_CP.py:408-410`): the LED output is off. The clone exposes no motion-abort command (`move_um` only
starts a move and `_finish_moving` only waits for it; `asi_MS_2000_500_CP.py:335-380`), so a stage move already
commanded runs to its target. This package is R1 and does not claim to stop the stage.

NOT COVERED: velocity, acceleration, settle time and precision settings (the clone exposes `_set_velocity`,
`_set_acceleration`, `_set_settle_time` and `_set_precision`), the joystick enable and status-byte reads, and the raw
serial transport. This package serves the three axis positions, the motion flag, the PWM output and one absolute
three-axis move.

Tags: stage, motion, controller, asi, ms-2000, serial, pwm
