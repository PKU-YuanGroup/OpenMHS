# Facts and tags for gh.squad-lab/qcdrivers

Every fact cites the pinned clone at commit `6704e1c1794eff30811b8db62593673b2e39b6b4`. Below, `mux.py` is
`src/qcdrivers/squad/mux/mux.py` and `firmware.ino`, `AD75019_24.cpp`, `AD75019_24.h`, `AD75019.cpp` and `AD75019.h`
are files of `src/qcdrivers/squad/mux/helpers/`. The same facts are in `driver.py` (`facts = [...]`); the reference
file is generated from the driver.

Tags: `qcodes`, `visa`, `crosspoint`, `switch`, `ad75019`, `squad-lab`.

Author: Claude (claude-opus-5-5, a model and not a human), 2026-11-05, re-authoring the blocked DeepSeek package
(user decision of 2026-11-05: Claude authors, Claude Sonnet reviews). Model-written; `reviewed_by` is null.
The e-stop confirmation repair (BL-19) is by Grok (grok-4.7, a model and not a human), 2026-11-05;
`authored_by` stays the original author and `reviewed_by` stays null.

## Facts

| fact | source | ref |
|---|---|---|
| Muxi is a QCoDeS VisaInstrument that controls an AD75019 crosspoint switch over pyVISA. | upstream_code | mux.py:29-35 |
| The constructor sets the baud rate (default 9600), newline write and CRLF read terminators and a 2000 ms VISA timeout, calls connect_message and clears the VISA handle. | upstream_code | mux.py:37-58 |
| send_command queries the VISA handle; on VisaIOError it calls `self.visa.handle.clear()`, an attribute path the class never defines, before sleeping 0.1 s and querying again. | upstream_code | mux.py:85-92 |
| switch32 returns "Route skipped: disabled range" without sending a command for x or y in 12-15 or 28-31, and otherwise sends `SWITCH32 x,y`. | upstream_code | mux.py:105-114 |
| status sends `MUX:STATUS? PIN,OUT`, a command the firmware does not register. | upstream_code | mux.py:144-146 |
| reset sends `*RST` through send_command, which reads one reply line. | upstream_code | mux.py:148-158 |
| printconfig sends `PRINT` and then reads a further line from the VISA handle. | upstream_code | mux.py:170-172 |
| close closes the VISA handle. | upstream_code | mux.py:225-235 |
| The firmware registers `*IDN?`, `*RST`, `STAT?`, `SWITCH16`, `SWITCH32`, `CLEAR` and `PRINT`. | upstream_code | firmware.ino:34-40 |
| `*IDN?` prints the line `SQUAD, Arduino AD75019 Switch, 1.0, 1.0`. | upstream_code | firmware.ino:47-49 |
| The `*RST` handler runs Clear, flushes the 16x16 and the 32x32 matrices and then prints "Reset complete". | upstream_code | firmware.ino:51-56 |
| Clear sets both route buffers to zero and prints "Clear complete". | upstream_code | firmware.ino:108-112 |
| `SWITCH32` prints "Route skipped: disabled range" for x or y in 12-15 or 28-31; otherwise it adds the route, flushes the 32x32 matrix and prints "Route added 32x32". | upstream_code | firmware.ino:71-88 |
| `STAT? x,y` prints `16x16: ` and `32x32: ` each followed by 1 or 0 from isRouted of the two route buffers, or "Usage: STAT? x,y" without two parameters. | upstream_code | firmware.ino:90-106 |
| The two matrix objects share one PCLK, SCLK and SIN pin set. | upstream_code | firmware.ino:6-13 |
| AD75019_24.flush shifts the route buffer out bit by bit and then pulses PCLK; clear sets every word of the buffer to 0. | upstream_code | AD75019_24.cpp:95-150 |
| isRouted reads the bit of the configuration buffer, not the chip. | upstream_code | AD75019_24.cpp:91-93 |
| The 32x32 matrix class's X and Y pin mappings have 32 entries. | upstream_code | AD75019_24.h:115-116 |
| The 16x16 matrix class's X and Y pin mappings have 16 entries. | upstream_code | AD75019.h:124-125 |
| The 16x16 matrix class's isRouted indexes its X and Y pin mappings with the x and y it is given. | upstream_code | AD75019.cpp:79-82 |
| `STAT?` passes the x and y it parses to isRouted of both the 16x16 and the 32x32 matrix. | upstream_code | firmware.ino:90-96 |
| Four AD75019 chips are daisy-chained for the 24x24 array, each with X12-X15 and Y12-Y15 disabled and grounded. | vendor_doc | src/qcdrivers/squad/mux/README.md:8-9 |

## Scope

The card's entry is `qcdrivers.squad.mux.mux:Muxi` (override). This package is a decorated direct `Driver` over it,
not the card's `PythonObjectDriver` helper (DEVIATION FROM THE CARD, RESULT.json): a Python-object result map cannot
report the route sent, and the firmware prints more reply lines than the class's methods read.

| capability | wire | note |
|---|---|---|
| `identity` (state read) | `*IDN?` | the firmware's identity line; any other line fails the read (a desynchronised stream) |
| `x-cap.squad-lab.mux_connect.v1` | `SWITCH32 x,y`, then `STAT? x,y` | reports the route sent, the firmware's reply and the read-back of the 32x32 route-buffer bit |
| `x-cap.squad-lab.mux_status.v1` | `STAT? x,y` | reads one bit of the 32x32 route buffer (R0); the 16x16 line is read and checked for its label, its value ignored (for a pin above 15 that lookup reads past the 16-entry mappings: the four facts above) |
| `x-cap.squad-lab.mux_reset.v1` | `*RST` | opens every crosspoint; reads this command's two reply lines after any lines still owed; checks for cancellation under the line lock first |
| e-stop | `*RST` | the same exchange; the stop succeeds only when this command's next two lines are "Clear complete" then "Reset complete" |

The driver sends every command with the upstream handle's `query` (the call `send_command` makes, mux.py:86) and reads
the further lines with the handle's `read` (as `printconfig` does, mux.py:171), one exchange at a time under a lock.
The connect and reset actions check for cancellation under that lock right before they write; the server cancels
operations before it stops, so neither writes after the e-stop's `*RST` (package cases check both). It does not call
`send_command`, `switch32` or `reset`: their retry path raises AttributeError on a VISA timeout (mux.py:87-90), and
`reset` reads only the first of the two `*RST` lines (mux.py:158, firmware.ino:51-56).

Not covered: `SWITCH16` and the 16x16 matrix, `CLEAR`, `PRINT`/`printconfig`, `full_status` (a local placeholder
matrix, mux.py:187-200) and the QCoDeS Parameters of the repository's other instruments (BaselDac2, QDac2, Decadac and
the others build theirs with `add_parameter`, which the QCoDeS family cannot prove).

## Limits

The X and Y pin inputs of the connect and status actions carry `Limit.operator_required`: the firmware's 32x32 buffer
takes pins 0-31 (AD75019_24.h:115-116) and refuses 12-15 and 28-31 (firmware.ino:76-80), but which pins of a crate are
cabled is deployment data. `site-limits.example.json` narrows an example bench to pins 0-11; it is not a device range.
A pin the firmware refuses gives a failed receipt `MHS.DEVICE.PRECONDITION_UNMET` (nothing changed).

## Safety and stop

R1 hardware. The e-stop sends `*RST` and confirms only when the two lines that follow every line still owed by an
earlier command are exactly "Clear complete" then "Reset complete". The sketch prints a fixed number of lines for each
command this driver sends, and prints them before the handler returns: `*IDN?` one (firmware.ino:48), `SWITCH32` one
(firmware.ino:78 or 84), `STAT?` two (firmware.ino:98-102), `*RST` two (Clear's line at firmware.ino:111, then
firmware.ino:55). `loop` processes input one call at a time (firmware.ino:43-44), so those owed lines are printed
before this `*RST`'s pair. A pair left by an earlier `*RST` whose reads timed out is part of that debt, including
after the latch is released, and so is the line of a `SWITCH32` whose read timed out. The e-stop does not treat the
earlier pair as its own. Without this command's pair, or on a transport error, the e-stop fails and the runtime
reports `MHS.SAFETY.SAFE_STATE_UNREACHED`, keeps the latch and retries; the unread debt stays on the driver. The pair
confirms that this `*RST` cleared both route buffers and shifted them out (firmware.ino:51-56, 108-112;
AD75019_24.cpp:95-150); nothing in the clone senses the analog switches. The e-stop waits for a connect that has nothing owed and has already started its own reply: that connect holds the
line lock across `SWITCH32` and the `STAT?` read-back, so `*RST` does not fall between those two reads (a package case
lands an e-stop there). It does not wait out a prefix of lines owed by earlier commands. An ordinary exchange stops
while that prefix is unread, and again after the last owed line before this command's own reply, when `estop_epoch`
moves (`_engage_estop` runs before `stop` takes the lock; a state read has no cancel context), when the operation is
cancelled, or after one 2000 ms VISA timeout (mux.py:55). Connect also does not start the `STAT?` read-back once that
stop has begun. The unread count stays owed, and the yielded call raises out of the lock, including a connect's outer
hold of it. The e-stop's own `*RST` is not stopped this way: it is the first
query once the line is free, and the following reads are its confirmation. The lock does not serve waiters in order; a
queued connect or reset finds itself cancelled and writes nothing; a read that runs updates the same debt. A read that
times out ends its exchange. Lines already in the buffer are skipped without another timeout. The e-stop declares a
latency of 5000 ms. On a slower confirmation the first receipt fails (latch kept, stop retried). No independent
hardware stop is in the source. A reset releases the latch and changes nothing on the switch, and it does not clear
the reply debt.

The upstream handle's `clear` (viClear) is not used to drop unread lines: on a serial resource its effect on this
firmware's parser is not shown in the source, and lines still in transit would arrive after it. The debt above counts
the sketch's lines instead. A line this driver did not write (the constructor clears the handle, mux.py:58; another
master on the same port is not the clone's use) is outside the count. RESULT.json lists this for the human reviewer.

A transport error after an effectful command was written, or an unexpected reply line, gives `MHS.OUTCOME.UNKNOWN`
(the firmware may have acted); a failed read or query gives a failed receipt.
