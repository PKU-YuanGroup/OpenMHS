# Facts and tags for gh.kajalbiju/psi_bluesky_backend

Every fact cites its source at commit `59252b014ef37fc4f2de2e37eda1fca755afe50f`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The module fixes the Mercury iTC device address STILL_DB6.T1 | upstream_code | Bluesky4/mercury_itc.py:6 |
| connect opens a pyvisa resource and sets the newline write and read terminators | upstream_code | Bluesky4/mercury_itc.py:9-14 |
| query connects, sends the command through pyvisa's query and disconnects | upstream_code | Bluesky4/mercury_itc.py:20-29 |
| write connects, sends the command and disconnects | upstream_code | Bluesky4/mercury_itc.py:31-38 |
| read_temperature sends READ:DEV:<address>:TEMP:SIG:TEMP and parses the last field, stripping a trailing K | upstream_code | Bluesky4/mercury_itc.py:41-49 |
| set_p_value sends SET:DEV:<address>:TEMP:LOOP:P:<value> and reads back LOOP:P | upstream_code | Bluesky4/mercury_itc.py:62-66 |
| set_i_value sends SET:DEV:<address>:TEMP:LOOP:I:<value> and reads back LOOP:I | upstream_code | Bluesky4/mercury_itc.py:68-72 |
| set_d_value sends SET:DEV:<address>:TEMP:LOOP:D:<value> and reads back LOOP:D | upstream_code | Bluesky4/mercury_itc.py:74-78 |
| set_heater_setpoint sends SET:DEV:<address>:TEMP:LOOP:HSET:<value> and reads back LOOP:HSET | upstream_code | Bluesky4/mercury_itc.py:80-84 |
| set_flow_setpoint sends SET:DEV:<address>:TEMP:LOOP:FSET:<value> and reads back LOOP:FSET | upstream_code | Bluesky4/mercury_itc.py:86-90 |
| set_gas_flow writes LOOP:TSET but its follow-up query is a literal string containing {device_address}, so this driver sends the SET line through write instead | upstream_code | Bluesky4/mercury_itc.py:56-60 |
| get_gas_flow reads LOOP:TSET and removes the last character of the reply as a unit suffix | upstream_code | Bluesky4/mercury_itc.py:153-161 |
| get_p_value, get_i_value, get_d_value and get_heater_setpoint read LOOP:P, LOOP:I, LOOP:D and LOOP:HSET | upstream_code | Bluesky4/mercury_itc.py:104-150 |
| The only numeric default in the class is the 10000 ms VISA timeout, a transport timeout and not a device range | upstream_code | Bluesky4/mercury_itc.py:12 |
| The upstream README describes the repository as the backend for controlling instruments at PSI | vendor_doc | README.md:1 |

Limits: no line of the clone states a range for TSET, HSET, P, I or D. Each of the five writes is therefore
`Limit.operator_required`; `site-limits.example.json` shows an operator overlay, but its numbers are examples, not a
statement about the unit.

Safety: the e-stop and the safe-state action `x-cap.kajalbiju.heater_off.v1` both write the temperature-loop
setpoint 0 K (`SET:DEV:STILL_DB6.T1:TEMP:LOOP:TSET:0`, the write this driver uses for TSET) and then call the upstream
`set_heater_setpoint(0.0)`, which sends `SET:DEV:STILL_DB6.T1:TEMP:LOOP:HSET:0.0` (`Bluesky4/mercury_itc.py:81`).
HSET is the heater output of manual mode; when the loop's PID control is on, the controller sets the heater output
itself, so the first version of this package, which wrote only HSET 0, would not stop a running loop from heating
(the reviewer added the TSET write). No text file of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2 hardware driver. The declared
risk is R2 because the controller drives a heater.

Scope: the package binds the Mercury iTC only. The SR830 lock-in and the SIM928 voltage source are separate
instruments in the same repository and are not covered. TSET is sent through `write` because the upstream
`set_gas_flow` follows its SET with a literal query string containing `{device_address}` (line 59); the flow
setpoint (FSET) is not exposed because the clone has a setter but no getter for it, and `get_gas_flow` is in fact
the TSET reader.

Tags: temperature controller, mercury itc, cryogenic, pid, visa
