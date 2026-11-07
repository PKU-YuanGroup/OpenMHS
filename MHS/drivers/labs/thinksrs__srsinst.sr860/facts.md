# Facts and tags for gh.thinksrs/srsinst.sr860

Every fact cites its source at commit `c234ec204329c1682fcc5a77d28164e99cdd1f3e`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The SR860, SR865 and SR865A are one family: the identity pattern is 'SR86[05][A]?,' | upstream_code | srsinst/sr860/instruments/sr860.py:23 |
| OUTP returns a data value by index: X 0, Y 1, R 2, Theta 3 | vendor_doc | README.md:175-179 |
| Theta is an angle in degrees (180 / pi * arctan2(y, x)) | upstream_code | srsinst/sr860/instruments/components.py:738 |
| The signal input is a voltage (sensitivity in V) or a current (sensitivity in A) | upstream_code | srsinst/sr860/instruments/components.py:191-194 |
| The time constants are 1 and 3 times 10^k s for k = -6 to 4, numbered from 0 in that order | upstream_code | srsinst/sr860/instruments/components.py:166-171 |
| The SR865 reference class allows up to 2000000.0 Hz and the SR865A class up to 4000000.0 Hz | upstream_code | srsinst/sr860/instruments/components.py:103-118 |
| SLVL, the sine output amplitude, ranges from 0 to 2.0 V | upstream_code | srsinst/sr860/instruments/components.py:78 |
| A setting is sent as 'COMMAND value' (OAUT {index}) | upstream_code | srsinst/sr860/instruments/components.py:234 |
| A query with an argument is sent as 'COMMAND? argument' (CAPTUREVAL? {index}) | upstream_code | srsinst/sr860/instruments/components.py:583 |
| The upstream README prints the identity 'Stanford_Research_Systems,SR865A,002725,v1.34' on connecting | vendor_doc | README.md:63 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| frequency (Hz) | FREQ | 0.001 to 500000.0 | srsinst/sr860/instruments/components.py:26-60 (MaxFrequency on line 26, the minimum in the command on line 60) |
| amplitude (V) | SLVL | 0 to 2.0 | srsinst/sr860/instruments/components.py:78 |
| time_constant (s) | OFLT | one of the 22 time constants | srsinst/sr860/instruments/components.py:166-171 |

The limits are those of the SR860, the narrowest of the family: an SR865 or SR865A accepts them too.

Safety: the e-stop writes `SLVL 0`, the lowest value of the one output this driver sets (the sine output amplitude). It
does not touch outputs the driver never sets (DC offset, auxiliary outputs). There is no hardware e-stop to cite and
none is needed at R1.

Tags: lock-in amplifier, sr860, sr865, sr865a, scpi
