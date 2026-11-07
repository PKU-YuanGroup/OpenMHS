# Facts and tags for gh.asvela/tektronix-func-gen

Every fact cites the clone at commit `30f7406e89bd9f344487b84913f5111e8bb110a7`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The module provides basic control of AFG1000 and AFG3000 series Tektronix arbitrary function generators | vendor_doc | README.md:6-9 |
| FuncGen exposes two channels, ch1 and ch2, as FuncGenChannel objects | upstream_code | tektronix_func_gen.py:145-153 |
| The channel command prefix is SOURceN: | upstream_code | tektronix_func_gen.py:810-813 |
| The frequency limits are selected from the connected model: AFG1022 and AFG3022 allow 1e-6 to 25e6 Hz, AFG1062 allows 1e-6 to 60e6 Hz | upstream_code | tektronix_func_gen.py:214-267 |
| The amplitude limits also depend on the impedance: AFG1022 50 ohm 0.001 to 10 Vpp and highZ 0.002 to 20 Vpp; AFG3022 50 ohm 0.01 to 10 Vpp and highZ 0.02 to 20 Vpp | upstream_code | tektronix_func_gen.py:221-262 |
| The output impedance (50 ohm or high Z) cannot be controlled or read remotely | vendor_doc | README.md:197-200 |
| The frequency limits are those of a sine; other functions may have a lower limit | vendor_doc | README.md:29-31 |
| The output state query returns 0 for OFF and 1 for ON | upstream_code | tektronix_func_gen.py:939-941 |
| The channel settings map converts the output state 0 or 1 to OFF or ON | upstream_code | tektronix_func_gen.py:807-808 |
| The output is set with OUTPutN:STATe | upstream_code | tektronix_func_gen.py:1044-1047 |
| The function is read with SOURceN:FUNCtion:SHAPe? | upstream_code | tektronix_func_gen.py:943-945 |
| The function is set with SOURceN:FUNCtion:SHAPe <shape> | upstream_code | tektronix_func_gen.py:1088-1089 |
| The function setter documents SINusoid, SQUare, PULSe, RAMP, PRNoise, built-in shapes and DC | upstream_code | tektronix_func_gen.py:1071-1079 |
| The README sets the channel function to SIN | vendor_doc | README.md:53 |
| The amplitude is read with SOURceN:VOLTage:AMPLitude? | upstream_code | tektronix_func_gen.py:947-949 |
| The amplitude is set with SOURceN:VOLTage:LEVel <amplitude>Vpp | upstream_code | tektronix_func_gen.py:1149-1152 |
| The offset is read with SOURceN:VOLTage:OFFSet? | upstream_code | tektronix_func_gen.py:951-953 |
| The offset is set with SOURceN:VOLTage:LEVel:OFFSet <offset>V | upstream_code | tektronix_func_gen.py:1202-1205 |
| The frequency is read with SOURceN:FREQuency? | upstream_code | tektronix_func_gen.py:955-957 |
| The frequency is set with SOURceN:FREQuency:FIXed <freq>Hz | upstream_code | tektronix_func_gen.py:1251-1255 |
| A channel set_settings turns the channel off, applies function, amplitude, offset and frequency, then restores the output state | upstream_code | tektronix_func_gen.py:1007-1026 |
| Frequency lock is read with SOURCE1:FREQuency:CONCurrent? | upstream_code | tektronix_func_gen.py:451-452 |
| Frequency lock is set with SOURCE{use_channel}:FREQuency:CONCurrent <state> | upstream_code | tektronix_func_gen.py:482-484 |
| The waveform catalogue is read with DATA:CATalog? | upstream_code | tektronix_func_gen.py:501-503 |
| The error queue is read with SYSTEM:ERROR:NEXT? | upstream_code | tektronix_func_gen.py:369-377 |

## Limits

The numeric channel settings (`amplitude_ch1`, `amplitude_ch2`, `offset_ch1`, `offset_ch2`, `frequency_ch1`,
`frequency_ch2`) have no single sourced bound. The clone selects the frequency and amplitude range from the
connected model (tektronix_func_gen.py:214-267), the amplitude and offset checks also depend on the impedance setting
(tektronix_func_gen.py:1188-1201), and the impedance cannot be read remotely (README.md:197-200). Every numeric
write is therefore `Limit.operator_required`: without an operator overlay it is refused with
`MHS.SAFETY.LIMITS_UNSET`, and `site-limits.example.json` shows an example overlay for one bench.

The function values are limited to the names the upstream `set_function` docstring documents plus the `SIN` name
the README uses (`tektronix_func_gen.py:1071-1079`, `README.md:53`). The output states are `ON` and `OFF`
(`tektronix_func_gen.py:1033-1036`). The frequency lock is a boolean.

## Coverage and safety

The driver serves the two channels' scalar settings, the frequency lock, the error queue and the waveform catalogue.
NOT COVERED: the arbitrary-waveform arrays (`get_custom_waveform` / `set_custom_waveform`, binary VISA transfers of
2 to 8192 or more 14-bit points, tektronix_func_gen.py:505-541 and 543-636).

The e-stop turns both channel outputs off with `OUTPut1:STATe OFF` and `OUTPut2:STATe OFF`, the commands the
upstream output setter builds (tektronix_func_gen.py:1044-1047). `safe_state` is "both channel outputs off". There
is no cited independent hardware e-stop in the clone, and the card's risk floor is R1, so `estop_physical_ref` is
not set.

The fake is an in-memory stand-in written for this package. Its starting values are test data, marked `# placeholder`,
never facts or limits. No hardware was attached.

Tags: function generator, arbitrary waveform generator, afg1000, afg3000, tektronix, visa
