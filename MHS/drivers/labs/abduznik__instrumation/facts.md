# Facts and tags for gh.abduznik/instrumation

The package covers the Rigol DS1054Z oscilloscope class of the upstream clone.  Every fact and bound cites the clone
at commit `483d6d5d0b6984f0e261e340363f784f6e2dd2f8`: `vendor_doc` is a text file of the clone
(`docs/experiments/rigol_ds1054z.md`) and `upstream_code` is `src/instrumation/drivers/rigol.py`.  The driver copies
the facts below into `facts = [Fact(...)]`; the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The DS1054Z is a 50 MHz, 4-channel digital oscilloscope with a 1 GSa/s sample rate | vendor_doc | docs/experiments/rigol_ds1054z.md:10 |
| The DS1054Z belongs to the MSO1000Z/DS1000Z family | vendor_doc | docs/experiments/rigol_ds1054z.md:3-4 |
| The driver supports the MSO1000Z/DS1000Z series and implements edge trigger only | upstream_code | src/instrumation/drivers/rigol.py:56-61 |
| The scope has four channels and the driver rejects a channel outside 1..4 | upstream_code | src/instrumation/drivers/rigol.py:159-161 |
| Identity is queried with `*IDN?`; the document prints `RIGOL,DS1054Z,...` | vendor_doc | docs/experiments/rigol_ds1054z.md:44 |
| `set_acquire_type` accepts NORMAL, AVERAGES, PEAK and HRESOLUTION | upstream_code | src/instrumation/drivers/rigol.py:124-127 |
| `set_acquire_averages` accepts powers of two from 2 to 1024 (2^n, n=1..10) | upstream_code | src/instrumation/drivers/rigol.py:133-143 |
| The memory depth is given only as examples, 14k, 140k and 14M points; the document uses 14000000 | upstream_code | src/instrumation/drivers/rigol.py:145-151 |
| The document configures the timebase with 1 ms/div and the trigger level with 1.0 V | vendor_doc | docs/experiments/rigol_ds1054z.md:51-55 |
| Channel coupling is AC, DC or GND | upstream_code | src/instrumation/drivers/rigol.py:186-188 |
| The bandwidth limit accepts 20M or OFF | upstream_code | src/instrumation/drivers/rigol.py:249-251 |
| The edge trigger source list is CHANnel1..CHANnel4, EXT and DEMath | upstream_code | src/instrumation/drivers/rigol.py:323-329 |
| The edge trigger slopes are POSITIVE, NEGATIVE and RFALL | upstream_code | src/instrumation/drivers/rigol.py:341-344 |
| The trigger sweeps are AUTO, NORMAL and SINGLE | upstream_code | src/instrumation/drivers/rigol.py:362-367 |
| `run` writes `:RUN`, `stop` writes `:STOP` and `force_trigger` writes `:TFORce` | upstream_code | src/instrumation/drivers/rigol.py:100-114 |
| `shutdown_safety` stops the acquisition and then synchronises the instrument | upstream_code | src/instrumation/drivers/rigol.py:560-562 |

## Limits

| field | rule | source | ref |
|---|---|---|---|
| `acquire_type` | allowed NORMAL, AVERAGES, PEAK, HRESOLUTION | upstream_code | src/instrumation/drivers/rigol.py:124-127 |
| `ch1_coupling` | allowed AC, DC, GND | upstream_code | src/instrumation/drivers/rigol.py:186-188 |
| `ch1_bw_limit` | allowed 20M, OFF | upstream_code | src/instrumation/drivers/rigol.py:249-251 |
| `trigger_sweep` | allowed AUTO, NORMAL, SINGLE | upstream_code | src/instrumation/drivers/rigol.py:362-367 |
| `edge_trigger_source` | allowed CHANnel1..CHANnel4, EXT, DEMath | upstream_code | src/instrumation/drivers/rigol.py:323-329 |
| `edge_trigger_slope` | allowed POSITIVE, NEGATIVE, RFALL | upstream_code | src/instrumation/drivers/rigol.py:341-344 |
| `timebase_scale`, `edge_trigger_level`, `ch1_scale` | operator-required: the clone gives examples only, not the bounds of the installed unit | upstream_code | src/instrumation/drivers/rigol.py:201, 297, 350-352 |

An operator-required bound is supplied in `site-limits.example.json` (narrow-only) and, at deployment, in
`site-limits.json`.  Until then every write of that field is refused with `MHS.SAFETY.LIMITS_UNSET`.

The acquisition averages and memory depth, the timebase offset, the channel 1 offset, probe ratio and inversion,
channels 2-4, the waveform array, the screenshot and the measurement helpers are not exposed by this scalar package.


## Tags

`oscilloscope`, `rigol`, `ds1054z`, `ds1000z`, `scpi`, `instrument`
