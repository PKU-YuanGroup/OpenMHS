# Facts and limits for gh.jovanmarkov96/keysight-dsox1200-control

Every fact cites its source at commit `34ba50a758b9f4e8773dee788c3f9a4c04455f8f`.  The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.  The clone has
no text manual under `docs/vendor_manuals/` (the directory is excluded from version control), so no PDF page is
cited.

| fact | source | ref |
|---|---|---|
| The clone supports the DSOX1202A/G, DSOX1204A/G and EDUX1052A/G oscilloscopes | upstream_code | src/keysight_dsox1200/instrument.py:3 |
| The connection is a VISA resource opened by pyvisa with a newline read and write terminator | upstream_code | src/keysight_dsox1200/instrument.py:86-91 |
| identify queries *IDN? and returns the stripped identity string | upstream_code | src/keysight_dsox1200/instrument.py:165-167 |
| reset sends *RST and waits 0.5 s | upstream_code | src/keysight_dsox1200/instrument.py:169-172 |
| run, stop and single send :RUN, :STOP and :SINGle; the stop docstring says it halts acquisitions | upstream_code | src/keysight_dsox1200/instrument.py:215-225 |
| A channel number must be one of 1, 2, 3 and 4; another value raises ValidationError | upstream_code | src/keysight_dsox1200/instrument.py:46-54 |
| configure_channel sets the channel display, coupling, probe, range, scale, offset, invert, label, bandwidth limit and unit | upstream_code | src/keysight_dsox1200/instrument.py:319-354 |
| channel_scale takes volts per division, channel_range takes the full-scale voltage and channel_offset takes volts | upstream_code | src/keysight_dsox1200/instrument.py:273-289 |
| timebase_scale takes seconds per division and timebase_position takes seconds | upstream_code | src/keysight_dsox1200/instrument.py:373-385 |
| configure_trigger_edge sets the source, level in volts, slope, sweep and coupling | upstream_code | src/keysight_dsox1200/instrument.py:466-479 |
| acquire_count sets the number of averages, 2 to 65536, when the acquisition type is AVERage | upstream_code | src/keysight_dsox1200/instrument.py:496-498 |
| acquire_srate_query reads the sample rate the scope derives from the timebase | upstream_code | src/keysight_dsox1200/instrument.py:510-512 |
| acquire_complete returns the percentage of required waveforms acquired | upstream_code | src/keysight_dsox1200/instrument.py:514-516 |
| The automatic measurements query :MEASure:<item>? and return a float; measure_counter is the hardware counter frequency measurement | upstream_code | src/keysight_dsox1200/instrument.py:644-704 |
| capture_waveform transfers :WAVeform:DATA? as a binary block and returns time and voltage arrays | upstream_code | src/keysight_dsox1200/instrument.py:551-608 |
| The enums carry the exact SCPI spellings used by the setters: coupling, acquire type, trigger sweep, trigger slope, trigger source and timebase mode | upstream_code | src/keysight_dsox1200/models.py:13-72 |

Limits:

| parameter | limit | source | ref |
|---|---|---|---|
| channel1_coupling | one of AC, DC, GND | upstream_code | src/keysight_dsox1200/models.py:13-16 |
| trigger_source | one of CHANnel1 to CHANnel4, EXTernal, LINE | upstream_code | src/keysight_dsox1200/models.py:50-56 |
| acquire_type | one of NORMal, AVERage, HRESolution, PEAK | upstream_code | src/keysight_dsox1200/models.py:30-34 |

The settings without a stated range use `Limit.operator_required`: `channel1_scale_v_per_div`,
`channel1_offset_v`, `timebase_scale_s_per_div` and `trigger_level_v`.  Their bounds depend on the probe ratio, the
model and the timebase or trigger mode; the clone's text states only the units and the full-scale formulas.
`site-limits.example.json` is an example overlay that narrows them for a bench; it is not a source of device
bounds.

The other settings the clone exposes (probe ratio, invert, timebase mode and position, trigger slope and sweep,
acquisition count and points) are read-only in this package.  They stay readable state, but the package does not
write them: the MCP projection bounds one tool to 2048 bytes and `cap.device.configure.v1` is the only
writable-state tool.  Their bounds, where the clone states none, would be operator_required if they were writable.

Safety: the e-stop calls the native `stop()` (`:STOP`, instrument.py:219-221), which halts acquisitions; the frozen
display is the safe state.  There is no actuation other than the acquisition itself, and the card's floor is R1.

Tags: oscilloscope, keysight, infiniivision, dsox1200, edux1052, scpi, visa

Authoring: model-authored (`driver.lock.json` `authored_by` kind `model`, model `deepseek-v4.1-flash:1017`, run
`wB1-038`); `reviewed_by` is null.  The package is checked on the fake backend only; nothing here ran on hardware.
