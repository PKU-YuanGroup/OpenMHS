# Facts and tags for gh.freespace/pysmc100

Every fact cites `smc100.py` in the clone at commit `8c65638934edb9c50381b7a25488bdc728619ffc`. The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SMC100 is Newport's single-axis motion controller | upstream_code | smc100.py:49 |
| Commands are <ID><command><arguments><CR><LF> and replies are <ID><command><result><CR><LF> | upstream_code | smc100.py:51-57 |
| The serial link is 57600 baud, 8 data bits, no parity, 1 stop bit, XON/XOFF flow control with a 50 ms read timeout | upstream_code | smc100.py:112-119 |
| A command is the controller ID, the command word and the argument, then CR LF | upstream_code | smc100.py:371-386 |
| A query passes '?' as the argument; sendcmd refuses a command that ends with '?' | upstream_code | smc100.py:348-363 |
| TS? returns a four-hex-digit error code followed by the two-character controller state | upstream_code | smc100.py:187-191 |
| TP? returns the position in millimetres | upstream_code | smc100.py:239-241 |
| PR moves by a relative distance in millimetres and PA to an absolute position in millimetres | upstream_code | smc100.py:246-277 |
| OR starts homing; after homing the upstream moves the stage to 0 mm | upstream_code | smc100.py:169-176 |
| ST stops the stage | upstream_code | smc100.py:178-179 |
| The stage units are stage-dependent; the author's TRB25CC stage uses millimetres | upstream_code | smc100.py:65-68 |
| The controller reports the DISABLE states 3C, 3D and 3E | upstream_code | smc100.py:22-24 |
| wait_states gives up after MAX_WAIT_TIME_SEC = 12 s | upstream_code | smc100.py:8 |
| A command that expects no reply is followed by at least COMMAND_WAIT_TIME_SEC = 0.06 s | upstream_code | smc100.py:12 |
| PR and OR are never retried automatically | upstream_code | smc100.py:374-377 |

Limits: the clone states no stage travel. The controller can drive different stages, and the author only had a
TRB25CC whose native units are millimetres (`smc100.py:65-68`). Both motion inputs therefore use
`Limit.operator_required`: the operator supplies the travel in `site-limits.json` and, until then, the runtime
refuses every move with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay with a 25 mm
working range; it is not a fact about the hardware.

Safety: the e-stop calls the upstream `stop()` (line 179), which sends `ST`. The safe state is "stage motion stopped
by the ST command"; the controller reports its DISABLE states separately (`smc100.py:22-24`). This is an R1
single-axis stage, not a high-force or high-voltage device. No hardware was attached and no hardware run is claimed.

The upstream module is Python 2: line 110 uses a `print` statement and line 400 uses `except Exception, ex`, so a
Python 3 import is impossible. The hardware backend in `native.py` is a Python 3 port of the same wire protocol.
The package does not import or run the clone.

Tags: newport, smc100, motion, stage, serial, rs232
