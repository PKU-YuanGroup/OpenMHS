# Facts and tags for gh.croningp/pylabware (Tricontinent C3000 syringe pump)

The upstream clone is pinned at commit `fbf287c7866ad3ac1e1a3bc44845035b8ae4a7b9`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| C3000SyringePump is the PyLabware class for the Tricontinent C3000 syringe pump with integrated valve, based on the operation manual 8694-12 E | upstream_code | PyLabware/devices/tricontinent_c3000.py:289-293 |
| The DT-protocol command prefix is `/` plus the switch address; the terminator is the autorun command PRG_RUN plus CRLF, the reply prefix is `/0`, the reply terminator is ETX CRLF and arguments are not separated | upstream_code | PyLabware/devices/tricontinent_c3000.py:321-333 |
| is_connected queries the firmware version and returns False only on a connection error | upstream_code | PyLabware/devices/tricontinent_c3000.py:389-399 |
| is_initialized reads the initialized status and returns False on a connection error | upstream_code | PyLabware/devices/tricontinent_c3000.py:449-458 |
| is_idle reads the status byte and returns False when bit 5 reports busy or an error is present | upstream_code | PyLabware/devices/tricontinent_c3000.py:460-484 |
| The absolute-position query is the `?` command (GET_SYR_POS) | upstream_code | PyLabware/devices/tricontinent_c3000.py:233-234 |
| get_plunger_position sends the absolute-position query and returns an integer | upstream_code | PyLabware/devices/tricontinent_c3000.py:530-535 |
| The valve-position query is `?6` (GET_VALVE_POS) and its reply is upper-cased | upstream_code | PyLabware/devices/tricontinent_c3000.py:249-250 |
| get_valve_position sends the valve-position query | upstream_code | PyLabware/devices/tricontinent_c3000.py:605-610 |
| move_home is move_plunger_absolute(0) | upstream_code | PyLabware/devices/tricontinent_c3000.py:516-517 |
| move_plunger_absolute sends the absolute move command and waits until the pump is idle | upstream_code | PyLabware/devices/tricontinent_c3000.py:519-528 |
| move_plunger_relative converts its argument with int(), withdraws when it is positive and dispenses its absolute value otherwise | upstream_code | PyLabware/devices/tricontinent_c3000.py:537-545 |
| dispense sends the relative dispense command (SYR_SPIT_REL) | upstream_code | PyLabware/devices/tricontinent_c3000.py:547-557 |
| withdraw sends the relative aspiration command (SYR_SUCK_REL) | upstream_code | PyLabware/devices/tricontinent_c3000.py:559-568 |
| The valve-position strings are built from I, O, B and E with the numbered I1..I6 and O1..O6 forms; VALVE_POSITIONS holds the bare digits and the empty IOBE argument | upstream_code | PyLabware/devices/tricontinent_c3000.py:44-56 |
| set_valve_position picks the command from the first character (I, O, B or E) and sends the rest as the argument | upstream_code | PyLabware/devices/tricontinent_c3000.py:588-603 |
| SET_MAX_VEL checks a maximum velocity of 1 to 48000 increments per second | upstream_code | PyLabware/devices/tricontinent_c3000.py:269-270 |
| set_speed sends SET_MAX_VEL | upstream_code | PyLabware/devices/tricontinent_c3000.py:499-504 |
| SET_START_VEL checks a starting velocity of 1 to 8000 | upstream_code | PyLabware/devices/tricontinent_c3000.py:267-268 |
| set_start_velocity sends SET_START_VEL | upstream_code | PyLabware/devices/tricontinent_c3000.py:619-624 |
| SET_STOP_VEL checks a cut-off velocity of 1 to 21600 | upstream_code | PyLabware/devices/tricontinent_c3000.py:273-274 |
| set_stop_velocity sends SET_STOP_VEL | upstream_code | PyLabware/devices/tricontinent_c3000.py:626-631 |
| SPEED_MODES is keyed by the speed codes 0 to 40 | upstream_code | PyLabware/devices/tricontinent_c3000.py:101-144 |
| SET_MAX_VEL_CODE checks its argument against the SPEED_MODES keys | upstream_code | PyLabware/devices/tricontinent_c3000.py:271-272 |
| set_predefined_speed sends SET_MAX_VEL_CODE | upstream_code | PyLabware/devices/tricontinent_c3000.py:509-514 |
| RAMP_PLOPE_MODES is keyed by the ramp codes 1 to 20 | upstream_code | PyLabware/devices/tricontinent_c3000.py:77-99 |
| SET_RAMP_PLOPE checks its argument against the RAMP_PLOPE_MODES keys | upstream_code | PyLabware/devices/tricontinent_c3000.py:265-266 |
| set_ramp_slope sends SET_RAMP_PLOPE | upstream_code | PyLabware/devices/tricontinent_c3000.py:612-617 |
| RESOLUTION_MODES is keyed by N0, N1 and N2 | upstream_code | PyLabware/devices/tricontinent_c3000.py:70-75 |
| SET_RES_MODE checks its argument against the RESOLUTION_MODES keys | upstream_code | PyLabware/devices/tricontinent_c3000.py:277-278 |
| set_resolution_mode sends SET_RES_MODE | upstream_code | PyLabware/devices/tricontinent_c3000.py:633-638 |
| The usage guide calls the relative amounts units and shows withdraw(200) leaving position 200 and dispense(200) returning it to 0 | vendor_doc | docs/usage.rst:78-90 |
| PRG_TERM is the terminate command `T` | upstream_code | PyLabware/devices/tricontinent_c3000.py:222 |
| stop sends PRG_TERM, which terminates command execution immediately | upstream_code | PyLabware/devices/tricontinent_c3000.py:494-497 |
| get_speed raises NotImplementedError, so the configured speed cannot be read back | upstream_code | PyLabware/devices/tricontinent_c3000.py:506-507 |

Limits: only the three motor velocities have a bound in the clone: `speed` 1 to 48000 (SET_MAX_VEL, whose
comment says increments per second), `start_velocity` 1 to 8000 (SET_START_VEL) and `stop_velocity` 1 to 21600
(SET_STOP_VEL).
The clone states no plunger travel and no dispensed amount, so `transfer.increments` and `move_plunger.position` are
`Limit.operator_required`: they are refused `MHS.SAFETY.LIMITS_UNSET` until the operator supplies the travel of the
syringe in `site-limits.json`. `site-limits.example.json` is an example overlay, not a statement about any pump.

Safety: the e-stop and the safe-state action `x-cap.croningp.stop_pump.v1` both call the native `stop()` (the `T`
command). No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set; the
safe-state action satisfies SAFE-045 for this R2 hardware driver.

Tags: syringe-pump, pump, valve, serial, dt-protocol
