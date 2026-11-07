# Facts and tags for gh.simonmeersschaut/stagecontroller

Every fact cites a line of the clone at commit `7edb1ac137a0cfedba78966815421fbfd5e73b38`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The script toggles a Phytron stepper motor on the press of a button | vendor_doc | README.md:3 |
| The serial line is /dev/ttyUSB0 at 9600 baud, no parity, eight data bits and one stop bit | upstream_code | stage.py:25-31 |
| A request is framed as STX (0x02), the address byte '0', the ASCII command and ETX (0x03) | upstream_code | stage.py:73-75 |
| A reply is the bytes between STX (0x02) and ETX (0x03) | upstream_code | stage.py:58-67 |
| The script sends XS once when it starts | upstream_code | stage.py:82 |
| The script stops the motor with XS, waits one second, then sends X0- | upstream_code | stage.py:93-97 |
| The script starts the motor with XL+ and marks it as rotating | upstream_code | stage.py:98-100 |
| The button that toggles the rotation is wired to GPIO 2 | upstream_code | stage.py:84 |
| The README points to the Phytron PhyLogic manual for the serial commands | vendor_doc | README.md:10-11 |

## Commands used by this driver

| capability | upstream command | ref |
|---|---|---|
| `x-cap.simonmeersschaut.start_rotation.v1` | `XL+` | stage.py:99 |
| `x-cap.simonmeersschaut.stop_rotation.v1` (also the safe-state action) | `XS` | stage.py:94 |
| the e-stop (`@estop`) | `XS` | stage.py:94 |

`stage.Serial.send` adds the STX, the address byte `'0'` and the ETX itself (stage.py:73-75), so the driver passes
the bare command to it.

## Limits

The driver declares no Limit. It has no numeric input: the clone states no bound for any value, and the three
commands above take no argument. The operator therefore has no bound to supply for this package.

## Safety

The e-stop and the safe state both send the upstream stop command `XS` through `send`; the runtime latches before
the native stop runs. The clone describes no independent hardware e-stop and no position or speed feedback, so
this R1 package cannot cite one.

## What this package does not cover

- `X0-` is not exposed: the clone sends it after the stop (stage.py:93-97) but neither README.md nor stage.py says
  what it changes, so the driver does not guess. The stop sends `XS` only.
- There is no read capability: the upstream class has no getter, and the clone has no position, speed or status
  query. The only public method of `Serial` is `send` (stage.py:73-76), which returns the framed reply bytes.
- The port is fixed at /dev/ttyUSB0 by the clone (stage.py:25-31); `native.py` passes no option.
- Nothing in this package was run on a controller; the evidence is the fake backend only.

Tags: stage, stepper, motion, phytron, serial
