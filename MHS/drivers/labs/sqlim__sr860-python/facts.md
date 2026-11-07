# Facts and tags for gh.sqlim/sr860-python

Every fact and limit cites the clone at commit `00fa066450759cfa994b1e999eeec7074bc5724c`.  The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| A setting is written as its command word and a formatted value and read back with the same word plus '?' (for example 'FREQ {:.3f}' and 'FREQ?') | upstream_code | srs/sr860.py:11 |
| The *IDN? reply is comma separated and the second field is the model used to choose the frequency range | upstream_code | srs/sr860.py:132-134 |
| The SR860 frequency range is 0.001 Hz to 500 kHz with 1 mHz resolution; the SR865 range is 0.001 Hz to 2 MHz and the SR865A range is 0.001 Hz to 4 MHz | upstream_code | srs/sr860.py:80-84 |
| The sine output amplitude range is 1e-9 V to 2.0 V | upstream_code | srs/sr860.py:201 |
| The reference phase range is -360000 to 360000 degrees | upstream_code | srs/sr860.py:231 |
| The sine output DC offset range is -5.0 V to 5.0 V | upstream_code | srs/sr860.py:261 |
| The harmonic number range is 1 to 99 | upstream_code | srs/sr860.py:291 |
| The time constants are the 22 values 1e-6, 3e-6, 1e-5, 3e-5 and so on up to 30000 s | upstream_code | srs/sr860.py:559 |
| The X, Y and R offsets are percentages in the range -999.99% to 999.99% | upstream_code | srs/sr860.py:798 |
| The offset enables are written with 'COFA n, value' and read with 'COFA? n' for n = 0 (X), 1 (Y) and 2 (R) | upstream_code | srs/sr860.py:50-52 |
| The advanced filter is written with ADVFILT and read with ADVFILT? | upstream_code | srs/sr860.py:27 |
| X, Y, R and P are read with OUTP? 0, OUTP? 1, OUTP? 2 and OUTP? 3 | upstream_code | srs/sr860.py:62-65 |
| The X data output is in volts | upstream_code | srs/sr860.py:1020 |
| The P data output is in degrees | upstream_code | srs/sr860.py:1044 |
| init() writes a known state: 1 kHz frequency, 1 V amplitude, 0 phase, 0 DC offset, harmonic 1, AC coupling, 24 dB/oct filter and the sync filter on | upstream_code | srs/sr860.py:88-112 |

## Limits

All limits are `upstream_code`:

| parameter | command | limit | ref |
|---|---|---|---|
| frequency (Hz) | FREQ | 0.001 to 500000.0 (the SR860 range; the SR865 and SR865A extend it, see the facts) | srs/sr860.py:80 |
| amplitude (V) | SLVL | 1e-9 to 2.0 | srs/sr860.py:201 |
| phase (deg) | PHAS | -360000 to 360000 | srs/sr860.py:231 |
| dc_offset (V) | SOFF | -5.0 to 5.0 | srs/sr860.py:261 |
| harmonic | HARM | 1 to 99 | srs/sr860.py:291 |
| time_constant (s) | OFLT | one of the 22 time constants | srs/sr860.py:559 |
| x_offset, y_offset, r_offset (%) | COFP | -999.99 to 999.99 | srs/sr860.py:798 |

The boolean settings (SYNC, ADVFILT, COFA) take no numeric bound; the upstream code sends a Python boolean as an
integer (srs/instr.py:50) and this driver writes 1 or 0.

## Safety

The e-stop writes `SLVL 0.000000001`, the lowest amplitude the upstream code states (1e-9 V, srs/sr860.py:201).
This lowers the one output the driver sets; it does not change the signal input, the reference or any output the
driver never sets.  The driver is R1; there is no independent hardware e-stop cited and none is required at R1.

## Tags

lock-in amplifier, sr860, sr865, sr865a, scpi
