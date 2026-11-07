# Facts and tags for gh.erikbgithub/python3-tecan-genesis

Every fact cites its source at commit `f85fb168886b26e002f05dc984127cbb2164e9b5`: `vendor_doc` for a text file of
the clone (README.md) or `upstream_code` for a code or comment line of the clone.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is a Python module for flow control of the Tecan Genesis RSP 200 and other devices | vendor_doc | README.md:3 |
| Tecan devices automate pipetting activities | vendor_doc | README.md:7 |
| The architecture translates steps into commands that the Tecan device reads via a serial connector | vendor_doc | README.md:11-13 |
| The module imports pyserial and opens a serial port | upstream_code | tecan_funcs.py:5-10 |
| The serial link is opened at 9600 baud on /dev/ttyUSB0 | upstream_code | tecan_funcs.py:10 |
| Cmd_delayed queues (command, device) pairs and add_cmd appends one to cmdStack | upstream_code | tecan_funcs.py:50-61 |
| Cmd_delayed.start sends GFC M1, every queued command, then GSC M1, and records each device in runningStack | upstream_code | tecan_funcs.py:63-72 |
| A delayed command is the sequence letter + device + command, prefixed with STX, suffixed with ETX and an XOR byte, then a newline | upstream_code | tecan_funcs.py:92-113 |
| do_cmd sends one command with the same STX/ETX/XOR framing and a rotating sequence letter | upstream_code | tecan_funcs.py:120-135 |
| read collects the bytes between STX and ETX and returns the message that starts with @device | upstream_code | tecan_funcs.py:165-209 |
| The init action sends PIS to device M1 | upstream_code | tecan_funcs.py:229-230 |
| The init_r action sends PIA to device R1 (the RoMa arm) | upstream_code | tecan_funcs.py:234-235 |
| The init_l action sends PIA to device A1 (the LiHa arm) | upstream_code | tecan_funcs.py:238-239 |
| The go_waste action sends PAA with the fixed waste coordinates to device A1 | upstream_code | tecan_funcs.py:336-337 |
| PSY sets the Y-spacing of the eight tips and takes the space in 0.1 mm, range [90...380] | upstream_code | tecan:222-224 |
| The liha_spacey action sends PSY followed by the spacing to device A1 | upstream_code | tecan:230-233 |
| PAA positions are in 0.1 mm and their ranges are set by the SRA command and the init offset | upstream_code | tecan:35-39 |
| The do_action dispatcher in the clone has init, init_r, init_l, move, go_waste and error-read branches but no halt or abort action | upstream_code | tecan_funcs.py:224-345 |

## Limits

The only numeric action input is `spacing` of `x-cap.erikbgithub.set_tip_spacing.v1`.  PSY takes the tip-to-tip space
as 90...380 in 0.1 mm units, which the clone states as 9...38 mm (`tecan:224`), so the field is limited to 9...38 mm
and the driver writes the selector in 0.1 mm.  Every other action takes no input.  The clone states no set-point-like writable state, so the package has no `@write` parameter.

## Safety

No line of the clone documents an independent hardware e-stop.  The clone also has no halt, stop or abort command:
`do_action` maps only initialisation, moves, go_waste and error reads (`tecan_funcs.py:224-345`).  The native e-stop
therefore discards the queued `Cmd_delayed.cmdStack` and `runningStack` and sends no further command, and the
safe-state action `x-cap.erikbgithub.discard_queued_commands.v1` does the same.  This stops the command flow, not an
axis that is already moving; it is not a claim of an independent stop.  `estop_physical_ref` is not set.  The package
is model-authored and unreviewed, and its hardware backend has never been run.

## What the fake covers

The fake implements only the two public methods and the two instance lists of `tecan_funcs.Cmd_delayed`.  It records
the queued command and the device that `start` dispatches; it does not reproduce the serial frame or the device's
acknowledgements.  The real device sends its replies as STX/ETX frames (tecan_funcs.py:165-209), which the fake does
not simulate.

Tags: tecan, genesis, liquid handling, pipetting, robot arm, serial
