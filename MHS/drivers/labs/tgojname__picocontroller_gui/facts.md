# Facts and limits for gh.tgojname/picocontroller_gui

Every fact cites the clone at commit `82a5f65663c916fd971e18deaadbab0eb714f233`. The same facts are written into
`driver.py` (`facts = [...]`); the reference files are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Controller.command sends a New Focus style command through the USB endpoints and returns a parsed reply only when the command contains `?` | upstream_code | picomotor_terminal_based.py:221-243 |
| parse_command builds `1><driver> <command> <parameter>\r` from the New Focus command text | upstream_code | picomotor_terminal_based.py:163-205 |
| The connection check queries `QM?` for motor channels 1 to 4 | upstream_code | picomotor_terminal_based.py:137-142 |
| MOTOR_TYPE maps the `QM?` reply code 0 to 3 to a motor description | upstream_code | picomotor_terminal_based.py:53-58 |
| The joystick loop starts a move only when the `MD?` reply ends in 1 | upstream_code | picomotor_terminal_based.py:296-304 |
| An axis is moved by writing its velocity with `VA` and then sending `MV+` or `MV-` | upstream_code | picomotor_terminal_based.py:294-304 |
| The comment calls 2000 the maximal speed for the New Focus 8821-L motor | upstream_code | picomotor_terminal_based.py:294 |
| The terminal program sends `ST` before the control loop and stops one axis with `<axis>ST` | upstream_code | picomotor_terminal_based.py:278-291 |

Limits:

- `axis`: `allowed=[1, 2, 3, 4]`, from the four channel keys in the clone (`picomotor_GUI.py:85`).
- `direction`: `allowed=["+", "-"]`, from the direction branch that builds `1MV+`/`1MV-`
  (`picomotor_terminal_based.py:299-304`).
- `velocity`: `min=0`, `max=2000`, unit `1`; the clone multiplies a magnitude by 2000 and calls 2000 the maximal
  speed for the 8821-L motor (`picomotor_terminal_based.py:294`).

Safety: the e-stop and the safe-state action `cap.motion.stop.v1` both call the native `ST` command, which the
clone sends before its control loop (`picomotor_terminal_based.py:278`). The driver is R1 because it commands small
open-loop picomotor motion. No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; at R1 SAFE-045 does not require one, and the safe-state action is still declared.
`cap.motion.stop.v1` also declares an optional `deceleration`; the 8742 `ST` command has no deceleration setting, so
the driver accepts that optional field for the class contract and ignores its value.

Tags: picomotor, motion, usb, newfocus
