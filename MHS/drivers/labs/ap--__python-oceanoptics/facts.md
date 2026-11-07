# Facts and tags for gh.ap/python-oceanoptics

Every fact cites its source at commit `3df0c263e47c374dcd569681780cf5fc5faa2029`, all of them `upstream_code`:
the clone has no TEC documentation page, and `docs/USB_CMD_INTERFACE.md` only lists the command bytes.  The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from
this page.

| fact | source | ref |
|---|---|---|
| OceanOpticsTEC is the class for the TEC found in QE65000 and QE65Pro spectrometers | upstream_code | oceanoptics/base.py:312-315 |
| get_temperatures() sends command 0x6C and returns the PCB and heatsink temperatures, each decoded as a signed 16-bit value scaled by 0.003906 | upstream_code | oceanoptics/base.py:357-370 |
| The TEC controller read is command 0x72 | upstream_code | oceanoptics/base.py:336-345 |
| get_TEC_temperature() decodes the TEC temperature as a signed 16-bit integer divided by 10 | upstream_code | oceanoptics/base.py:373-380 |
| The setpoint command 0x73 carries the temperature times 10 as a signed 16-bit integer | upstream_code | oceanoptics/base.py:348-355 |
| set_TEC_temperature() reads the temperature, disables the TEC controller, writes the setpoint, enables the fan, re-enables the TEC controller and waits 2 s | upstream_code | oceanoptics/base.py:383-395 |
| _set_tec_controller_state() switches the TEC controller off with state 0x00 and on with state 0x01 (command 0x71) | upstream_code | oceanoptics/base.py:327-333 |
| _set_fan_state() sends command 0x70 with state 0x01, and its docstring says the fan is always switched on because switching the fan off might be unsafe | upstream_code | oceanoptics/base.py:317-323 |
| _tec_controller_get_status() queries information address 17 and decodes the TEC enable state, the fan enable state and the setpoint as a signed 16-bit integer divided by 10 | upstream_code | oceanoptics/base.py:430-439 |
| initialize_TEC() describes a setpoint of -17 as the standard value that results in a TEC temperature of -15 degrees Celsius; it is a chosen standard value, not a stated device range | upstream_code | oceanoptics/base.py:398-404 |

Limits: the TEC setpoint is `Limit.operator_required`.  No text of the clone states a setpoint range; the only
setpoint in the code is the -17 default that `initialize_TEC()` chooses and describes as a value that "should work
for most cases" (oceanoptics/base.py:398-404), which is a method default, not a device bound.  The operator supplies
the range at the site (`site-limits.example.json` shows the overlay for both the writable `setpoint` state field
and the `target_temperature` input of `cap.thermal.setpoint.v1`).

Safety: the e-stop `stop()` and the safe-state action `x-cap.ap.tec_safe_off.v1` both call
`_set_tec_controller_state(0x00)` to switch the TEC controller off and `_set_fan_state(0x01)` to leave the fan on.
The class's own comment says switching the fan off might be unsafe (oceanoptics/base.py:317-323), so the driver never
does.  No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the
safe-state action satisfies SAFE-045 for this R2 hardware driver.

The setpoint is read through `_tec_controller_get_status()` (oceanoptics/base.py:430-439), the class's status query.
The upstream marks the two functions around it as "not needed probably" (oceanoptics/base.py:428); the driver uses
the status query only to report the stored setpoint and the enable states, never to decide a safety action.

Tags: tec, temperature-control, spectrometer, thermoelectric-cooler
