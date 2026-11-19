# Facts and tags for gh.kitour/rigol-mho98-mcp

Every fact cites its source at commit `22fc52291dee96b01e75c0e6549c3175d1d5ec35`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Session is an MHO98 instrument session; production sessions open it lazily on first I/O | upstream_code | src/rigol_mcp/mho98/session.py:75-80 |
| A Session accepts an identity only when its second comma-separated field is MHO98 | upstream_code | src/rigol_mcp/mho98/session.py:70-72 |
| idn() sends *IDN? and refuses an identity that is not MHO98, closing the transport | upstream_code | src/rigol_mcp/mho98/session.py:324-338 |
| query() runs exactly the requested text query; write() sends one command without a readback | upstream_code | src/rigol_mcp/mho98/session.py:357-374 |
| binary_query() returns one validated IEEE-488.2 definite-length payload, and write_binary() uploads one bounded binary block | upstream_code | src/rigol_mcp/mho98/session.py:623-663 |
| is_healthy is false after a transport fault or close | upstream_code | src/rigol_mcp/mho98/session.py:141-144 |
| query_error() drains :SYSTem:ERRor? and returns the first non-zero response | upstream_code | src/rigol_mcp/mho98/session.py:342-354 |
| The waveform selector accepts CHAN1-CHAN4 and MATH1-MATH4, modes NORM/MAX/RAW and formats WORD/BYTE/ASC | upstream_code | src/rigol_mcp/mho98/waveform.py:19-21 |
| The waveform module declares ceilings of 1000 NORM points, 500000000 memory points and 100000 inline points | upstream_code | src/rigol_mcp/mho98/waveform.py:23-25 |
| get_waveform defaults to source CH1, start 1, 1000 points, mode NORM and format ASC | upstream_code | src/rigol_mcp/mho98/waveform.py:445-452 |
| The waveform preamble has ten comma-separated fields and is rejected unless it has exactly ten | upstream_code | src/rigol_mcp/mho98/waveform.py:187-215 |
| The waveform preamble format code must match the transfer format: BYTE 0, WORD 1, ASC 2 | upstream_code | src/rigol_mcp/mho98/waveform.py:217-222 |
| BYTE samples convert as (sample - yorigin - yreference) * yincrement | upstream_code | src/rigol_mcp/mho98/waveform.py:249-253 |
| Waveform times are xorigin + (start - 1 + index - xreference) * xincrement | upstream_code | src/rigol_mcp/mho98/waveform.py:293-297 |
| The pinned cursor state reads :CURSor:MODE? and the manual cursor A/B X screen positions with :CURSor:MANual:CAX? and :CURSor:MANual:CBX? | upstream_code | src/rigol_mcp/mho98/cursor.py:147-176 |
| set_cursor sends :CURSor:MODE, :CURSor:MANual:TYPE, :CURSor:MANual:SOURce and the CAX/CBX positions for explicitly requested manual fields | upstream_code | src/rigol_mcp/mho98/cursor.py:336-359 |
| The main timebase scale is read with :TIMebase:MAIN:SCALe? and written as :TIMebase:MAIN:SCALe | upstream_code | src/rigol_mcp/mho98/timebase.py:96-212 |
| The main timebase scale must be positive; the clone states no maximum | upstream_code | src/rigol_mcp/mho98/timebase.py:175 |
| CH1 scale and offset are read with :CHANnel1:SCALe? and :CHANnel1:OFFSet? and written under the same prefix | upstream_code | src/rigol_mcp/mho98/channel.py:142-309 |
| The channel scale bound depends on the input impedance and the probe ratio, which this driver does not read, so the clone does not state one fixed range | upstream_code | src/rigol_mcp/mho98/channel.py:160-175 |
| acquisition_control maps RUN to :RUN, STOP to :STOP, SINGLE to :SINGle and FORCE to :TFORce | upstream_code | src/rigol_mcp/mho98/acquire.py:236-254 |
| The upstream scope stop helper writes :STOP, rejects a queued SCPI error and reads :TRIGger:STATus? | upstream_code | src/rigol_mcp/scope.py:366-371 |
| The main-offset validator treats trigger status STOP as the stopped case | upstream_code | src/rigol_mcp/mho98/timebase.py:132-137 |
| Acquisition averages are 2 through 65536 and must be a power of two | upstream_code | src/rigol_mcp/mho98/acquire.py:28-110 |
| Reference waveform slots are 1 through 10 | upstream_code | src/rigol_mcp/mho98/reference.py:18-64 |
| Search event requests are limited to 1000 events | upstream_code | src/rigol_mcp/mho98/search.py:19-316 |
| The upstream README prints the MHO98 identity as RIGOL TECHNOLOGIES,MHO98,MHO9A274501253,... | vendor_doc | README_MHO98.md:220 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| waveform_source | :WAVeform:SOURce | CHAN1-CHAN4, MATH1-MATH4 | waveform.py:19 |
| waveform_mode | :WAVeform:MODE | NORM, MAX, RAW | waveform.py:20 |
| waveform_format | :WAVeform:FORMat | ASC, BYTE (WORD needs caller-declared encoding) | waveform.py:21,115-185 |
| timebase_scale_s_div | :TIMebase:MAIN:SCALe | operator required: positive but no stated maximum | timebase.py:175 |
| timebase_offset_s | :TIMebase:MAIN:OFFSet | operator required: no numeric range stated | timebase.py:154-230 |
| ch1_scale_v_div | :CHANnel1:SCALe | operator required: bound depends on impedance and probe | channel.py:160-175 |
| ch1_offset_v | :CHANnel1:OFFSet | operator required: no numeric range stated | channel.py:177-183 |
| cursor A/B X position | :CURSor:MANual:CAX/CBX | operator required: no numeric range stated | cursor.py:264-359 |

Safety: the e-stop and the safe-state action send `:STOP`, drain/check the SCPI error queue and require
`:TRIGger:STATus?` to return `STOP`. This follows the upstream scope stop helper (scope.py:366-371), with
`STOP` recognized by the main-offset validator (timebase.py:132-137). An ignored stop, an error or any other
status fails the e-stop and keeps the latch held. This is one acquisition-state readback, not a persistent
safety guarantee. The driver controls no instrument output and does not abort an in-flight SCPI exchange.
The R1 floor is retained. `:RUN` remains an explicit re-enable after reset; the reset never sends it.

Every configuration/cursor/acquisition write checks the SCPI error queue, so an instrument rejection is not
reported as completion. Successful setting writes report the requested setting without an independent setting
readback; this matches the upstream feature modules' `verified: false` responses. The ordinary state reads
provide subsequent readback. The queue is shared with other clients and draining it consumes errors.

The waveform action uses the ten-field preamble internally and returns source, format, point count, samples and
times; it does not return the preamble itself. It refuses a preamble above the upstream 100000-point inline
ceiling before querying samples or constructing a time array, bounds BYTE transfers to the same byte count,
and refuses nonfinite samples and malformed fields. The fake's eight samples and axis values remain placeholders.

Deployment gaps: Session's default timeout is `None`, an infinite VISA timeout (session.py:23, 83-100,
161-179). `native.py` now requires an explicit positive integer `timeout_ms`, which Session additionally checks
against VISA's infinite-timeout sentinel before any I/O. A finite per-exchange timeout is not an end-to-end
e-stop guarantee: the error drain can issue up to 16 queries (session.py:342-352), and slow I/O can exceed the
runtime's 1 s budget and leave the stop failed and latched. The fake does not reproduce USB/LAN framing,
latency, reconnects, concurrent access or Session.transaction's process/interprocess locks
(session.py:147-159). The package does not acquire that transaction lock around calls; deployment must exclude
other VISA clients, and an e-stop can still contend with an in-flight exchange on the same transport.
No hardware backend or upstream code was imported or run in this model review.

Tags: oscilloscope, rigol, mho98, scpi, waveform, instrument
