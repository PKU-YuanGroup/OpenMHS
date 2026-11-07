# Facts and tags for gh.masahiro-999/oscilloscope-mcp

Every fact cites the pinned clone at commit `e45773551e2b956e1fb086ad99cbfec546eaad4b`.
The same facts are written into `driver.py` (`facts = [...]`); `reference.json` and
`REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The DS1000Z module drives the DS1054Z, DS1074Z and DS1104Z over line-based SCPI on raw TCP port 5555 | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:1-6 |
| RigolDs1000z implements the Scope interface for every DS1000Z-series scope | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:54-55 |
| get_channel reads scale, offset, coupling, display, probe, bandwidth limit, invert and units for one channel | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:104-116 |
| set_channel validates every requested field before sending one burst, with the probe ratio first | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:118-145 |
| get_timebase reads :TIM:MAIN:SCAL?, :TIM:MAIN:OFFS? and :TIM:MODE? | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:147-152 |
| set_timebase validates the mode, scale and offset before sending one burst | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:154-168 |
| get_acquire reads :ACQ:TYPE?, :ACQ:AVER?, :ACQ:MDEP? and :ACQ:SRAT? | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:174-188 |
| set_acquire validates every requested field before sending one burst | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:190-206 |
| get_trigger reads the global trigger fields and every readable parameter of the current trigger mode | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:212-236 |
| set_trigger validates all parameters up front and sends them in one burst with the mode first | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:238-280 |
| run_control writes the root command the profile maps to RUN, STOP, SINGLE or FORCE | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:282-287 |
| measure validates the measurement items and sources before querying :MEAS:ITEM? per item | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:293-333 |
| read_waveform reads about 1200 screen points in NORMal mode and up to 24M acquisition points in RAW mode, which requires the scope to be stopped | upstream_code | src/oscilloscope_mcp/instruments/rigol_ds1000z.py:399-404 |
| The vertical scale range is 1.0e-3 to 100.0 V/div and the vertical offset range is -100.0 to 100.0 V | upstream_code | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:65-66 |
| The timebase scale range is 5.0e-9 to 50 s/div and the timebase offset range is -100.0 to 100.0 s | upstream_code | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:69-70 |
| The channel probe ratios are the 16 declared ratios from 0.01 to 1000 | upstream_code | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:62 |
| The averaging counts are the powers of two from 2 to 1024 | upstream_code | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:73 |
| The profile declares channel coupling AC/DC/GND, timebase modes MAIN/XY/ROLL, acquire types NORMal/AVERages/PEAK/HRESolution, trigger sweeps AUTO/NORMAL/SINGLE and trigger couplings AC/DC/LFReject/HFReject | upstream_code | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:61-80 |
| The DS1104Z has four analog channels and 24 Mpts of acquisition memory | upstream_code | src/oscilloscope_mcp/instruments/profiles/rigol_ds1104z.yaml:14-21 |

## Limits

Every numeric write carries a bound from the DS1000Z family profile:

| state field | limit | ref |
|---|---|---|
| channel_1_scale | 1.0e-3 to 100.0 V/div | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:65 |
| channel_1_offset | -100.0 to 100.0 V | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:66 |
| channel_1_probe | one of the 16 declared ratios | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:62 |
| timebase_scale | 5.0e-9 to 50 s/div | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:69 |
| timebase_offset | -100.0 to 100.0 s | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:70 |
| acquire_averages | one of 2, 4, ..., 1024 | src/oscilloscope_mcp/instruments/profiles/_ds1000z_family.yaml:73 |

The enum fields (`channel_1_coupling`, `timebase_mode`, `acquire_type`, `trigger_sweep`,
`trigger_coupling`) take only the values the same profile lists.  No operator-required
limit is used, so the package has no `site-limits.example.json`.

## Safety

The native stop is `run_control("STOP")` (`:STOP`); the `@estop` method calls it after the
runtime latches.  The safe state is acquisition stopped.  No `estop_physical_ref` is set:
the package is R1, where SAFE-045's physical-stop requirement does not apply, and the
stop is the native software command.  The package is model-authored and unreviewed; the
hardware backend was never run.

## Not covered

The waveform array (`:WAV:DATA?`, about 1200 NORMal points or up to 24M RAW points) and the
screenshot block (`:DISP:DATA?`, a PNG/BMP binary block) are not exposed; the standard
carries scalar state and measurements, not those arrays.  Measurement statistics are also
not exposed, to keep the action set to the scalar measurements and controls.

Tags: oscilloscope, instrument, scpi, rigol, ds1000z, measurement
