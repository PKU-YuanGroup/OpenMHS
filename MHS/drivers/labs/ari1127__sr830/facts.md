# Facts and tags for gh.ari1127/sr830

Every fact cites its source at commit `930c9c5dcd8016b19e8c0988599f8f76cd928a12`. The clone has no README or
manual: every fact below is `upstream_code` from `SR830.py`. The same facts are in `driver.py` (`facts = [...]`)
and the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The upstream class is `device` and opens the VISA resource passed to `__init__` (default `GPIB0::14`) | upstream_code | SR830.py:5-7 |
| X, Y, R and Theta are read with `OUTP? 1` through `OUTP? 4` and each reply is converted to float | upstream_code | SR830.py:151-158 |
| `get_all` asks `SNAP?1,2,3,4` for the four data values in one exchange | upstream_code | SR830.py:149-150 |
| The demo block parses the `get_all` reply as comma-separated X, Y, R and Theta in that order | upstream_code | SR830.py:180-184 |
| The time constant is addressed by index: 0 is 10 us, 6 is 10 ms, 10 is 1 s and 19 is 30 ks | upstream_code | SR830.py:8-28 |
| The sensitivity is addressed by index: 0 is 2 nV, 17 is 1 mV, 23 is 100 mV and 26 is 1 V | upstream_code | SR830.py:29-56 |
| A setting is sent as the command word followed by one argument (`FREQ %f`, `SLVL %f`, `PHAS %f`) | upstream_code | SR830.py:109-120 |
| A query with an argument is sent as the command word, a question mark and the argument (`DDEF? %i`) | upstream_code | SR830.py:101-104 |
| The front panel is overridden with `OVRM 1` (disabled) and `OVRM 0` (enabled) | upstream_code | SR830.py:62-65 |
| The reset method writes `*RST` | upstream_code | SR830.py:58-59 |
| The auxiliary output is written as `AUXV output, value` with three decimal places | upstream_code | SR830.py:121-122 |
| The auxiliary output is read back as `AUXV? output` | upstream_code | SR830.py:169-170 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| time_constant_index | OFLT | one of 0..19 | SR830.py:8-28 (the 20-entry table) |
| sensitivity_index | SENS | one of 0..26 | SR830.py:29-56 (the 27-entry table) |
| frequency (Hz) | FREQ | operator_required: no line of the clone states a range |  |
| amplitude (V) | SLVL | operator_required: no line of the clone states a range |  |
| phase (deg) | PHAS | operator_required: no line of the clone states a range |  |
| reference_source | FMOD | operator_required: the integer is passed through, no allowed values stated |  |
| input_source | ISRC | operator_required: the integer is passed through, no allowed values stated |  |
| coupling | ICPL | operator_required: the integer is passed through, no allowed values stated |  |

No line of the clone states a frequency, amplitude or phase range, so those limits are
`Limit.operator_required`: until the operator supplies them in `site-limits.json`, every write of the field is
refused with `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay for one bench.

Safety: the e-stop writes `SLVL 0`, the lowest value of the sine output amplitude, the one output this driver sets.
The driver does not touch the front panel or the display. There is no hardware e-stop to cite and none is needed at
R1.

Not covered: `set_disp_rat` and `set_exp_off` take three arguments (`DDEF`/`OEXP`) and the scalar SCPI write map
carries one; their current values are still read as raw strings. `set_aux` selects one of two outputs with a
compound argument, so both auxiliary outputs are read but not written. `set_ground`, `set_filter`, `set_reserve`,
`set_slope`, `set_sync`, `set_trigshape` and `set_harm` (which the class does not define) are not exposed; their
current values are still read. The front-panel override (`OVRM`), reset (`*RST`), clear (`*CLS`), auto phase
(`APHS`), auto gain (`AGAN`), auto reserve (`ARSV`) and auto offset (`AOFF`) have no query in the clone, so their
effect cannot be observed and they are not exposed. `get_all`/`SNAP?1,2,3,4` is exposed as the raw comma-separated
string; it is not split into four values. The clone has no `*IDN?` line, so the driver sends no identity query.

Tags: lock-in amplifier, sr830, scpi, phase-sensitive detection.
