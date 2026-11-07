# Facts and tags for gh.ludwigregalado/lock-in_sr830

Every fact cites its source at commit `fbd78df88f25a051d938cdbe5b0a1263b938e6de`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The README says the code sends and requests information from an SR830 lock-in amplifier | vendor_doc | README.md:2 |
| The README says the code is written in a sequential fashion and is to be updated to object-oriented code | vendor_doc | README.md:5 |
| The only third-party import is pyserial (import serial) | upstream_code | SR830.py:9 |
| ask_device opens /dev/ttyUSB0 at 9600 baud, 8 data bits, no parity, one stop bit and a 0.1 s timeout | upstream_code | SR830.py:13 |
| ask_device encodes the command as text, writes and flushes it, reads one line and decodes it as UTF-8 | upstream_code | SR830.py:16-20 |
| set_device opens the same port, writes and flushes the encoded command, closes the port and reads no reply | upstream_code | SR830.py:24-29 |
| Commands are newline-terminated text (ask_device('PHAS?\n')) | upstream_code | SR830.py:37 |
| PHAS? queries the reference phase shift | upstream_code | SR830.py:36-37 |
| FREQ? queries the reference frequency | upstream_code | SR830.py:40-41 |
| FREQ sets the reference frequency when the source is internal and accepts 0.001 to 102000 Hz | upstream_code | SR830.py:183-189 |
| SLVL? queries the sine output amplitude | upstream_code | SR830.py:46-47 |
| SLVL sets the sine output amplitude and accepts 0.004 to 5.000 | upstream_code | SR830.py:202-204 |
| OUTP? returns X for index 1, Y for 2, R for 3 and theta for 4 | upstream_code | SR830.py:373-378 |
| ISRC sets the input configuration to 0, 1, 2 or 3 | upstream_code | SR830.py:209-212 |
| IGND sets the input shield grounding to 0 or 1 | upstream_code | SR830.py:213-216 |
| ICPL sets the input coupling to 0 or 1 | upstream_code | SR830.py:217-220 |
| ILIN sets the line notch filter to 0, 1, 2 or 3 | upstream_code | SR830.py:221-224 |
| RMOD sets the reserve mode to 0, 1 or 2 | upstream_code | SR830.py:258-261 |
| OFLT selects one of the 20 time-constant indexes of the set_tau table, 0 for 10 us through 19 for 30 ks | upstream_code | SR830.py:264-286 |
| OFSL sets the low-pass filter slope to 0, 1 or 2 | upstream_code | SR830.py:289-292 |
| SYNC sets the synchronous filter to 0 or 1 | upstream_code | SR830.py:293-296 |
| *IDN? queries the device identification string | upstream_code | SR830.py:408-409 |
| set_phas sends FREQ instead of PHAS, so the clone has no working phase write command | upstream_code | SR830.py:165-167 |
| set_aux_inp builds the AUXV command with ++, which raises TypeError when called | upstream_code | SR830.py:319-322 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| frequency (Hz) | FREQ | 0.001 to 102000 | SR830.py:185 |
| amplitude | SLVL | 0.004 to 5.000 | SR830.py:203 |
| input_config | ISRC | one of 0, 1, 2, 3 | SR830.py:211 |
| ground | IGND | one of 0, 1 | SR830.py:215 |
| coupling | ICPL | one of 0, 1 | SR830.py:219 |
| line_filter | ILIN | one of 0, 1, 2, 3 | SR830.py:223 |
| reserve | RMOD | one of 0, 1, 2 | SR830.py:260 |
| time_constant_index | OFLT | one of the indexes 0 through 19 | SR830.py:267-286 |
| slope | OFSL | one of 0, 1, 2 | SR830.py:291 |
| sync | SYNC | one of 0, 1 | SR830.py:295 |

The clone states no unit for the sine output amplitude, the phase, theta, X, Y or R, so the driver does not
name a physical unit. Amplitude and the integer indexes carry the dimensionless UCUM unit `1`; frequency is
in Hz because the clone's set_freq reports the value in Hz.

Safety: the e-stop writes `SLVL 0.004`, the lowest amplitude the clone's set_ampl accepts. It does not touch
settings the driver never sets and it does not reset the instrument. The driver is R1 (a low-energy measurement
instrument above the card's R0 floor); no independent hardware e-stop is claimed.

The clone's `set_phas` sends `FREQ` (SR830.py:165-167) and its `set_aux_inp` uses `++` (SR830.py:319-322). The
driver therefore exposes the phase as a read only and does not expose the auxiliary input write.

Tags: lock-in amplifier, sr830, serial, measurement, phase
