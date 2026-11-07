# Facts and tags for gh.tolland/python-tecan-genesis

Every fact cites the clone at commit `37e825db120b56199519bea72c82116f75269608`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The project is a Python module for controlling the Tecan Genesis RSP 200 | vendor_doc | README.md:2 |
| The module opens /dev/ttyUSB0 at 9600 baud with a 1 s read timeout and a 5 s write timeout; the portmon dump above it shows 8 data bits, no parity and one stop bit | upstream_code | bin/tecan_funcs.py:9-13 |
| A command frame is STX (0x02), the sequence letter, the unit address, the ASCII command, ETX (0x03), the XOR of those bytes, and a trailing newline | upstream_code | bin/tecan_funcs.py:147-164 |
| The sequence letters rotate through A-G | upstream_code | bin/tecan_funcs.py:39-51 |
| do_cmd reads a first acknowledgement and then a second acknowledgement/data frame | upstream_code | bin/tecan_funcs.py:166-176 |
| read consumes the byte after ETX as the XOR and does not compare it before returning a frame | upstream_code | bin/tecan_funcs.py:210-281 |
| Cmd_delayed stores (command, unit) pairs in cmdStack and start sends GFC, every stacked command and then GSC to the M1 controller | upstream_code | bin/tecan_funcs.py:57-108 |
| add_cmd appends to cmdStack and increments the class counter cmdCount | upstream_code | bin/tecan_funcs.py:65-67 |
| The logged firmware reply is @M1@GENESIS-V1.61-07/2001 | upstream_code | rs232_logs/BIOBULLS-L3YMYO.LOG:51 |
| The logged write 02 41 4D 31 52 46 56 30 03 4E is STX A M1 RFV0 ETX and the XOR 0x4E | upstream_code | rs232_logs/BIOBULLS-L3YMYO.LOG:52 |
| PAZ moves all installed tips to absolute Z positions in 0.1 mm; the range is set by the SRA command | upstream_code | bin/tecan:241-243 |
| The ROMA home action sends PAZ2480, PAR0, PAY0 and PAX0 to the R1 unit | upstream_code | bin/tecan:43-46 |
| The initialization sequence sends PIS to the M1 controller and PIA to the R1 arm | upstream_code | bin/tecan:182-189 |
| The dispense example sends V3600c900D217M0R to each of the diluter units D1 through D8 | upstream_code | bin/dispense_1.py:30-31 |
| Cmd_delayed defines only __init__, add_cmd and start (lines 57-108), and the module's only close() closes the serial port (lines 201-203); no stop, abort, halt or emergency command exists | upstream_code | bin/tecan_funcs.py:57-203 |

## Limits

The only numeric input is `z_mm` of `x-cap.tolland.move_liha_z.v1`.  The PAZ doc block gives no absolute range: it
says the range is set by the SRA command (`bin/tecan:243`), a per-instrument setting.  The field therefore carries
`Limit.operator_required`: every move is refused `MHS.SAFETY.LIMITS_UNSET` until an operator overlay supplies the
range.  `site-limits.example.json` is an example overlay, not a statement about any instrument.

## Safety

The clone defines no stop, abort, halt or emergency command.  `Cmd_delayed` has only `__init__`, `add_cmd` and
`start` (`bin/tecan_funcs.py:57-108`); the module's only `close()` closes the serial port
(`bin/tecan_funcs.py:201-203`).  A move already sent therefore cannot be stopped through this library, and no text
of the clone documents an independent hardware e-stop.  The driver is R2 because it moves a liquid-handling arm and
dispenses; SAFE-045 cannot be met without inventing a stop command, so the package is blocked (RESULT.json).  No
hardware was attached and the hardware backend was never started.

## Tags

Tecan, genesis, RSP 200, liquid handler, pipetting, serial, RS-232.
