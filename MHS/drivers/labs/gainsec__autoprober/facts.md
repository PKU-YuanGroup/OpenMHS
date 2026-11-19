# Facts and tags for gh.gainsec/autoprober

Every fact cites its source at commit `ff0e01fe556c7e183d46462dbc1ebce7b6a10e74`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| CNC is the GRBL CNC wrapper; its constructor takes port, baud and log_source and leaves the serial object unset | upstream_code | autoprober/cnc.py:46-53 |
| connect opens serial.Serial on port and baud, waits, resets the input buffer, writes CRLF and resets again | upstream_code | autoprober/cnc.py:55-64 |
| parse_status parses a GRBL status line into state, an MPos tuple of three floats, the raw Pn field and the subset of X, Y and Z pins | upstream_code | autoprober/cnc.py:22-43 |
| get_status writes '?' and returns the first parsed status line before its 2 s deadline | upstream_code | autoprober/cnc.py:90-101 |
| read_settings writes '$$' and collects $N=value lines until 'ok' or its 10 s deadline | upstream_code | autoprober/cnc.py:103-119 |
| home writes '$H' and returns without waiting for the homing cycle | upstream_code | autoprober/cnc.py:81-82 |
| feed_hold writes the single GRBL feed-hold byte '!' and returns without waiting for motion to stop | upstream_code | autoprober/cnc.py:84-88 |
| unlock writes '$X' and sleeps 0.2 s; it has no acknowledgement read | upstream_code | autoprober/cnc.py:77-79 |
| move_absolute builds G90 G1 with the supplied X, Y and Z words and an F feed word | upstream_code | autoprober/cnc.py:131-146 |
| move_relative builds G91 G1 with the supplied X, Y and Z deltas and an F feed word | upstream_code | autoprober/cnc.py:148-163 |
| wait_for_idle polls get_status and returns only when the state is exactly Idle | upstream_code | autoprober/cnc.py:121-129 |
| _write raises CNCError when no serial object is open | upstream_code | autoprober/cnc.py:71-73 |
| The independent safety endstop is oscilloscope Channel 4; below 1.0 V is triggered, 1.0 to 4.5 V is a fault and 4.5 V or more is clear | vendor_doc | docs/safety.md:3-10 |
| STOP means feed hold has been sent if possible, the workflow ends and the operator must inspect and explicitly restart | vendor_doc | docs/safety.md:12 |
| GRBL Pn:P is ignored for safety; real limit flags are X, Y and Z, including the X/Y/Z part of Pn:PX, Pn:PY and Pn:PZ | vendor_doc | AGENTS.md:8-22 |
| Channel 4 must be monitored continuously during motion and a trigger must issue feed hold immediately | vendor_doc | AGENTS.md:47-51 |
| On a trigger the operator must stop and report; automatic back-off, jog, retry or continued scanning is forbidden | vendor_doc | AGENTS.md:84-93 |
| The clone says to stay inside the known travel envelope and that a hard limit alarm is not a safety strategy, but states no travel number | vendor_doc | AGENTS.md:117-118 |
| The clone recommends feed-rate ranges by operation but states no single device feed bound | vendor_doc | AGENTS.md:123-128 |
| All motion workflows must create an EndstopMonitor before motion starts and stop it after motion has ended; if the monitor enters STOP, the app exits without more motion | vendor_doc | docs/operations.md:13 |
| CNC's public methods are connect, close, unlock, home, feed_hold, get_status, read_settings, wait_for_idle, move_absolute and move_relative; the class has no cycle-start or resume method | upstream_code | autoprober/cnc.py:46-163 |

## Scope and limits

The package serves the CNC actuator, the first entry symbol of the card (`autoprober/cnc.py:46`). It does not bind
`autoprober.scope:Scope` or `autoprober.microscope:Microscope`; one OpenMHS driver binds one native object.

* BLOCKER: the oscilloscope Channel 4 endstop monitor (`autoprober.safety:EndstopMonitor`). The clone requires
  it during motion (docs/operations.md:13, AGENTS.md:47-51), but this driver has no monitor, status interlock or
  fail-closed enforcement of that requirement. Merely advising a deployment to run a separate monitor does not
  establish its presence, correct callback, or continued operation.
* NOT COVERED: the USB microscope snapshot path (`autoprober.microscope:Microscope.capture`, HTTP mjpg_streamer).
* NOT COVERED: a cycle-start/resume command after feed hold. The clone has no method for it (docs/safety.md:12 says
  the operator must explicitly restart). The fake's `$X` alarm clear no longer invents recovery from Hold.

Travel and feed bounds are `Limit.operator_required`. The clone names no travel number (AGENTS.md:117-118) and gives
only recommended feed-rate ranges by operation (AGENTS.md:123-128). The operator's overlay supplies the envelope of
the installed machine; `site-limits.example.json` is an example, not a statement about any machine. A relative delta
is bounded only by the current position and the same unstated envelope; the driver cannot compute a cumulative
travel check from the clone either.

Safety: `CNC.feed_hold` only writes `!` to the serial line (`autoprober/cnc.py:84-88`); it reads no acknowledgement
or stopped state and even ignores the serial write count. Both `@estop` and `cap.motion.stop.v1` attempt the write
and then fail with `MHS.SAFETY.SAFE_STATE_UNREACHED`; the action is no longer marked `safe_state=True`.
The endpoint latch remains engaged, and neither transport success nor the fake's instantaneous Hold state
certifies physical standstill. The clone documents no independent hardware emergency stop. The separate scope
measurement is a software-polled endstop, not that physical stop. `x-cap.gainsec.unlock.v1` remains the explicit
alarm-clear command and is never called by a reset; its unacknowledged write does not prove recovery.

Additional blockers before live use: per-call relative-delta limits do not enforce absolute travel after repeated
moves; an initial or stale Idle reply can be mistaken for completion because the wrapper does not read motion
acknowledgements; a status exception in `_wait_idle` can leave a commanded move running without a hold attempt.
The fake does not model these transport or planner hazards. The source-available noncommercial licence and
the card's required publication review remain owner decisions.

Tags: autoprober, cnc, grbl, motion, flying-probe, serial.
