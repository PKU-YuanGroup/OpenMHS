# Facts and tags for gh.vadter/hantek6022be

Every fact cites its source at commit `548ff23984044ed1b8265358cfd20312e37cce8b`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. Every Fact is
`upstream_code` with a `pyhantek6022BE.py:LINE` reference; the clone has no text manual.

| fact | source | ref |
|---|---|---|
| Hantek is the USB oscilloscope class: it loads firmware through USB vendor 0x04b4 product 0x6022 and then talks to vendor 0x04b5 product 0x6022 | upstream_code | pyhantek6022BE.py:8-39 |
| The samplerate table maps 48, 16, 8, 4 and 1 MS/s and 500, 200 and 100 kS/s | upstream_code | pyhantek6022BE.py:83-85 |
| set_samplerate accepts a rate only when it is a key of dictN_SR; otherwise it prints the available rates and leaves the device unchanged | upstream_code | pyhantek6022BE.py:176-202 |
| The vertical-division table is {1: 1, 2: 0.5, 5: 0.2, 10: 0.1}; dictN_VDiv reverses it | upstream_code | pyhantek6022BE.py:77-78 |
| set_chvdiv accepts a channel value only when it is a key of dictN_VDiv | upstream_code | pyhantek6022BE.py:204-222 |
| The default samplerate is 16 MS/s per channel and both channels start at 1 V/div | upstream_code | pyhantek6022BE.py:80-88 |
| GetData reads dictDatLen_N[samplerate] bytes and returns two voltage arrays scaled by (raw - 128) / 255 * 10 * ChVDiv | upstream_code | pyhantek6022BE.py:162-174 |
| buf_len is data_len // 2 samples per channel and dictDatLen_N maps each samplerate to its data length | upstream_code | pyhantek6022BE.py:91-97 |
| get_rate returns the samplerate and get_time returns linspace(0, buf_len - 1, buf_len) / samplerate | upstream_code | pyhantek6022BE.py:227-233 |
| get_rates returns 50 kHz, 250 kHz, 500 kHz, 2 MHz, 4 MHz, 8 MHz and 24 MHz | upstream_code | pyhantek6022BE.py:235-240 |
| close() resets the USB device and disposes its resources | upstream_code | pyhantek6022BE.py:494-506 |

Limits: the sample rate is limited to the keys of `dictN_SR` (100 kS/s, 200 kS/s, 500 kS/s, 1 MS/s, 4 MS/s,
8 MS/s, 16 MS/s and 48 MS/s) and each channel's vertical division to the keys of `dictN_VDiv` (1, 0.5, 0.2 and
0.1 V/div). Both are `Limit(allowed=...)` with `source="upstream_code"` and the line that shows the table. The
runtime refuses any other value with `MHS.SAFETY.ENVELOPE_VIOLATION` before the native call.

The list of `get_rates()` is not the accepted samplerate set: it contains seven values (50 kHz to 24 MHz) that
`set_samplerate()` does not accept, while `set_samplerate()` accepts the eight keys of `dictN_SR`
(pyhantek6022BE.py:176-178, 235-240). The driver reads the rate with `get_rate()` and writes it with
`set_samplerate()`, never with the `get_rates()` list.

Safety: the e-stop and `teardown()` both call the native `close()`, which resets the USB device and disposes its
resources. The scope generates no output, so no independent hardware e-stop is documented in the clone and
`estop_physical_ref` is not set.

NOT COVERED: the waveform array. `GetData()` returns one voltage array per channel of `buf_len = data_len // 2`
samples (131072 at 16 MS/s; pyhantek6022BE.py:91-97, 162-174). No catalogue class carries an oscilloscope trace,
so the driver reports the sample count, the window duration and the minimum, maximum and RMS voltage of each
channel instead of transferring the samples. The fake returns 512 samples per channel as placeholder test data.

Tags: oscilloscope, usb, instrument, acquisition, voltage
