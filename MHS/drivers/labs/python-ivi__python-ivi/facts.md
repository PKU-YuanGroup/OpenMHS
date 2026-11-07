# Facts and tags for gh.python-ivi/python-ivi

Every fact cites its source at commit `cfa45ceade0758debe4bc24ba4c8195222cad1e2` as `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone's WaveRunner Xi-A / MXi-A driver supports the models WR204MXI-A, WR204XI-A, WR104MXI-A, WR104XI-A, WR64MXI-A, WR64XI-A, WR62XI-A, WR44MXI-A and WR44XI-A | upstream_code | ivi/lecroy/lecroyWRXIA.py:78-79 |
| The WaveRunner 104MXi-A is a 4-channel, 1 GHz member: its constructor sets 4 analog channels, 0 digital channels and _bandwidth = 1e9 | upstream_code | ivi/lecroy/lecroyWR104MXIA.py:37-40 |
| The manufacturer identity field is 'LeCroy' | upstream_code | ivi/lecroy/lecroyBaseScope.py:212 |
| The identity response is split on commas into manufacturer (field 0), model (field 1) and firmware revision (field 3) | upstream_code | ivi/lecroy/lecroyBaseScope.py:477-481 |
| The clone turns the command header off when it constructs the driver ('CHDR OFF') so every response is a bare value | upstream_code | ivi/lecroy/lecroyBaseScope.py:221-222 |
| TriggerModes is the set auto, norm, single, stop | upstream_code | ivi/lecroy/lecroyBaseScope.py:44 |
| The trigger mode is set with TRMD and queried with TRMD? | upstream_code | ivi/lecroy/lecroyBaseScope.py:1209-1221 |
| The acquisition type is sent with :acquire:type, mapping normal to norm, peak_detect to peak, high_resolution to hres and average to aver | upstream_code | ivi/lecroy/lecroyBaseScope.py:35-40 |
| The sample mode is sent with :acquire:mode, mapping real_time to rtim and equivalent_time to etim | upstream_code | ivi/lecroy/lecroyBaseScope.py:94-95 |
| The number of averages is sent with :acquire:count and is limited to 1 through 65536 | upstream_code | ivi/lecroy/lecroyBaseScope.py:1589-1592 |
| The timebase mode is sent with :timebase:mode, mapping main to main, window to wind, xy to xy and roll to roll | upstream_code | ivi/lecroy/lecroyBaseScope.py:141-145 |
| The timebase reference is sent with :timebase:reference, mapping left to left, center to cent and right to righ | upstream_code | ivi/lecroy/lecroyBaseScope.py:146-149 |
| The measurement functions of the clone's mapping include frequency, period and voltage_peak_to_peak (sent as vpp) | upstream_code | ivi/lecroy/lecroyBaseScope.py:101-107 |
| A waveform measurement query is built as ':measure:<function>? <channel>', for example ':measure:frequency? C1' | upstream_code | ivi/lecroy/lecroyBaseScope.py:1527-1543 |
| A continuous acquisition is stopped with ':stop' (the boolean trigger-continuous setter writes 'run' for true and 'stop' for false) | upstream_code | ivi/lecroy/lecroyBaseScope.py:1573-1579 |
| Analog channels are named C1 through C4 | upstream_code | ivi/lecroy/lecroyBaseScope.py:563-564 |

Limits (all `upstream_code`):

| parameter | command | limit | ref |
|---|---|---|---|
| trigger_mode | TRMD | one of auto, norm, single, stop | ivi/lecroy/lecroyBaseScope.py:44 |
| acquisition_type | :acquire:type | one of norm, peak, hres, aver | ivi/lecroy/lecroyBaseScope.py:35-40 |
| sample_mode | :acquire:mode | one of rtim, etim | ivi/lecroy/lecroyBaseScope.py:94-95 |
| acquisition_averages | :acquire:count | 1 to 65536 | ivi/lecroy/lecroyBaseScope.py:1589-1592 |
| timebase_mode | :timebase:mode | one of main, wind, xy, roll | ivi/lecroy/lecroyBaseScope.py:141-145 |
| timebase_reference | :timebase:reference | one of left, cent, righ | ivi/lecroy/lecroyBaseScope.py:146-149 |

The string limits are the wire tokens of the clone's mapping dictionaries, which is what the corresponding query
returns: `:acquire:type?` answers `norm` and not `normal`.

Safety: the e-stop writes `:stop`, the clone's command that stops a continuous acquisition. It does not power the
instrument off and does not reset a trigger mode the operator chose. There is no hardware e-stop to cite and none is
needed at R0.

## Honest limits of this package

- The clone's driver turns the command header off on construction (`CHDR OFF`, line 222). The SCPI bridge has no
  configure-before-identity step, so this driver's reads assume the instrument is configured with the header off, or
  a reply such as `TRMD NORM` will not parse.
- Waveform (`:waveform?`, `fetch_waveform`) and screenshot (`HCSU`, `SCDP`) transfers are not covered: they return
  large arrays and this package does not fake them. `facts.md` and `driver.py` name no waveform Limit or Fact.
- Trigger type (`TRSE`) is not covered: its reply is a comma-separated list, which this read map cannot split.
- The channel settings (`C1:SCALE`, `C1:OFFSET`, `C1:TRLV`, probe attenuation) are not covered: the clone states no
  bound for them, and this package covers only what it can source.
- The wire syntax was not tried on an instrument.

Tags: oscilloscope, lecroy, waverunner, wr104mxia, scpi
