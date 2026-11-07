# Facts and tags for gh.jonathanvanschenck/sr830-python

Every fact cites its source at commit `fdce76ec409d2fd768a87719854deb2395152026`: `upstream_code` is a line of
`sr830.py` in the clone. The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The class controls a Stanford Research SR830 lock-in amplifier over a GPIB connection through pyVISA | upstream_code | sr830.py:5-11 |
| The constructor opens the VISA resource and queries '*IDN?' when it connects | upstream_code | sr830.py:46-49 |
| Sensitivity settings run from 2 nV at index 0 to 1 V at index 26 | upstream_code | sr830.py:50-58 |
| Integration times run from 10 us at index 0 to 30 ks at index 19 | upstream_code | sr830.py:69-75 |
| An integration time is written as 'OFLT <index>' and read back with 'OFLT ?' | upstream_code | sr830.py:98-106 |
| A sensitivity is written as 'SENS <index>' and read back with 'SENS ?' | upstream_code | sr830.py:122-130 |
| The synchronous filter is written as 'SYNC 0' (off) or 'SYNC 1' (on) and read back with 'SYNC ?'; the upstream docstring says it should only be on below 200 Hz | upstream_code | sr830.py:132-143 |
| The reference frequency is read with 'FREQ ?' in Hz | upstream_code | sr830.py:145-146 |
| A data value is read with 'OUTP? <index>': X at 1, Y at 2, R at 3 and phase in degrees at 4 | upstream_code | sr830.py:148-154 |
| getRTh returns R in volts and Theta in degrees, and getXY returns X and Y in volts | upstream_code | sr830.py:155-158 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| time_constant_index | OFLT | 0 to 19 | sr830.py:69-75 (index 0 on line 69, index 19 on line 75) |
| sensitivity_index | SENS | 0 to 26 | sr830.py:50-58 (index 0 on line 50, index 26 on line 58) |
| sync_filter | SYNC | 0 to 1 | sr830.py:136-137 (0->OFF, 1->ON) |

The writable state is the index the instrument stores, not the physical time constant or sensitivity: the upstream
read path returns the index (`getIT`, `getSens`), and an SCPI read map has no reverse lookup from an index to the
seconds or volts tables. The tables themselves are in `sr830.py:50-79`.

Safety: the upstream wrapper sets no excitation output, so the e-stop has no source to switch off. It writes
`SYNC 0` (synchronous filter off) and `SENS 26` (the least sensitive 1 V range), the two settings this driver can
write that reduce the chance of a misleading or overloaded measurement. R1 needs no independent hardware stop.

Tags: lock-in amplifier, sr830, gpib, scpi
