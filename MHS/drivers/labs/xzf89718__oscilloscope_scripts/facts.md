# Facts and tags for gh.xzf89718/oscilloscope_scripts

Every fact cites its source at commit `105e6021650f5b4f6557e733451612e4696a860d`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

Path prefix: `Tektronix_TBS2000B_control/oscilloscope_control.py`.

| fact | source | ref |
|---|---|---|
| The supported instrument is the Tektronix TBS2000B | vendor_doc | README.md:3 |
| The upstream connects over pyvisa to a VISA resource and writes '*cls' and 'header OFF' on connect | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:22-37 |
| SetChannel accepts CH1, CH2, CH3 and CH4 and raises for any other value | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:146-172 |
| The measure methods take comma-separated channels and default to CH1 | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:106-136 |
| MeasureFreq sends the immediate source and the FREQuency type and then queries `:MEASUrement:IMMed:VALue?` | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:106-114 |
| MeasureAmpl sends the immediate source and the AMPlitude type and then queries `:MEASUrement:IMMed:VALue?` | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:116-124 |
| MeasureHigh sends the immediate source and the HIGH type and then queries `:MEASUrement:IMMed:VALue?` | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:126-134 |
| MeasureLow formats a stray '}' and iterates the characters of its channel argument, unlike the other measure methods | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:136-144 |
| For the TBS2000B, 1 to 2500 is a full waveform in the clone's waveform comment | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:56-58 |
| The vertical waveform scale is in volts: ymult is 'volts / level' and yzero is a reference voltage | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:78-81 |
| Close closes the pyvisa resource and the resource manager | upstream_code | Tektronix_TBS2000B_control/oscilloscope_control.py:178-180 |

## Limits

All limits are `upstream_code`:

| parameter | command | limit | ref |
|---|---|---|---|
| channel | `:MEASUrement:IMMed:SOUrce1 <channel>` (inside the Measure methods) | one of CH1, CH2, CH3, CH4 | Tektronix_TBS2000B_control/oscilloscope_control.py:156-167 |

No numeric write is exposed, so there is no numeric bound to declare. The channel limit is the set `SetChannel`
accepts; `DEFAULT` is not offered because the upstream only prints a warning for it and leaves the earlier channel
unset.

## Not covered

- The waveform arrays returned by `Sampling` (scaled time and voltage arrays per channel). The standard has no
  waveform-array contract; the clone's comment names 1 to 2500 samples as a full waveform (line 57).
- `MeasureLow`: the upstream method formats a trailing `}` in its source command and iterates the characters of its
  channel argument (lines 138-142), so it cannot produce a valid measurement.

## Safety

This is a measurement-only oscilloscope driver at R1. The e-stop calls the upstream `Close`, which closes the pyvisa
resource and the resource manager; the runtime latches the e-stop before that call. The driver never writes an
acquisition, trigger or output setting, so the safe state is a closed session rather than a changed instrument mode.

Tags: oscilloscope, tektronix, tbs2000b, scpi, measurement
