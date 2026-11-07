# Facts and tags for gh.jieunboy0516/newport-smc100-motor-controller-library-python

Every fact cites its source at commit `b828102ddcc30495084606fd1634066c95c985a0`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a Python library for the Newport SMC100 motor controller | vendor_doc | README.md:1-2 |
| The class smc100 talks to an SMC100 through a serial port | upstream_code | smc100_base.py:73-74 |
| The constructor opens the serial port at 57600 baud with 8 data bits, no parity, one stop bit and a 10 s timeout | upstream_code | smc100_base.py:82-87 |
| A command is sent as the command text plus CRLF; a query returns the reply with the first len(command) characters removed | upstream_code | smc100_base.py:103-112 |
| The controller state is queried with '%02dTS' and the last two characters of the reply are looked up in controller_state_map | upstream_code | smc100_base.py:121-127 |
| controller_state_map names MOVING, READY from MOVING and DISABLE from READY | upstream_code | smc100_base.py:6-28 |
| get_position queries '%02dTP' and its docstring says the value is in mm, but the parsed value is printed and the method returns None | upstream_code | smc100_base.py:145-151 |
| get_errors queries '%02dTS', maps the error bits through error_names and returns [None] when there is no error | upstream_code | smc100_base.py:131-143 |
| set_velocity writes '%02dVA%f' and get_velocity queries '%02dVA?', but the parsed velocity is printed and get_velocity returns None | upstream_code | smc100_base.py:218-229 |
| move_absolute writes '%02dPA%f' and move_relative writes '%02dPR%f' | upstream_code | smc100_base.py:176-182 |
| home writes '%02dOR'; home_until_done polls get_state with a 0.5 s sleep in an unbounded loop | upstream_code | smc100_base.py:159-173 |
| stop_motion writes '%02dST' | upstream_code | smc100_base.py:202-204 |
| reset writes '%02dRS' | upstream_code | smc100_base.py:207-210 |
| kill closes the serial connection | upstream_code | smc100_base.py:153-156 |
| The constructor sets motors_count to 1 and reads info for one controller | upstream_code | smc100_base.py:97-101 |
| When the serial open fails the constructor prints that it uses a dummy motor controller but does not replace the serial object | upstream_code | smc100_base.py:89-95 |
| The README calls the controller argument the motor number, usually 1 | vendor_doc | README.md:27 |
| The README describes the move position as between 0-27 without a unit | vendor_doc | README.md:28 |
| The README links an external SMC100CC/SMC100PP user manual and says to refer to it | vendor_doc | README.md:14-15 |

Limits: the absolute position, the relative offset and the velocity are `Limit.operator_required`.  No text file of
the clone states the travel of the configured stage, a relative move bound or a velocity range with a unit.  The
README's 0-27 for the move position (README.md:28) has no unit and is the library author's example, so it is not used
as a device bound.  `site-limits.example.json` shows the overlay; until a site supplies `site-limits.json` every write
is refused `MHS.SAFETY.LIMITS_UNSET`.

Safety: the e-stop and the safe-state action `cap.motion.stop.v1` both call the native `stop_motion` (`%02dST`,
smc100_base.py:202-204).  No line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is
not set; this is an R1 package, below the R2 requirement for SAFE-045.  The native recovery `@reset` calls `%02dRS`
(smc100_base.py:207-210).

Not covered: the upstream `home_until_done` and `move` busy-wait without a timeout (smc100_base.py:163-173, 184-200),
so they are not exposed; `home` reports command acceptance rather than completion.  The upstream `get_position`,
`get_velocity` and `get_JOGGING_state` parse but return None, so the driver queries TP and VA? through `send_rcv`
itself.  The arbitrary `send`, the disable/enable (`MM0`/`MM1`) and the jogging commands are not exposed.

Tags: newport, smc100, motor controller, motion axis, serial
