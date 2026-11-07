# Facts and tags for gh.vadter/hantek1008c

Every fact cites its source at commit `178773a7a7161e8ddf68a9230e944bb4c5205884`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The udev rule matches USB vendor id 0783 and product id 5725 | upstream_code | 60-hantek-1008C.rules:1 |
| The clone implements a variant of only the 8-channel operation mode | vendor_doc | README.md:5 |
| The README states that the sample rate is set from 300 ksamples/s to 5 ksamples/s and that the channels are placed near the middle of the 2048/4096 range | vendor_doc | README.md:6 |
| valid channel ids are 0 to 7 for the eight channels | upstream_code | pyhantek1008C.py:517-522 |
| get_time returns a 500-point time axis built as np.linspace(0., 499, 500) / samplerate, in seconds for a samplerate in samples per second | upstream_code | pyhantek1008C.py:261 |
| get_vscales returns the per-channel vertical scale factor; the allowed factors are 0.02, 0.125 and 1.0 (the setter comment calls them Volt/Div) | upstream_code | pyhantek1008C.py:277 |
| The upstream init1 sets the generator speed to 300000 rpm and switches the generator off | upstream_code | pyhantek1008C.py:332-333 |
| set_generator_on sends command 0xb7 then 0xbb with 0x01 for on and 0x00 for off; the class has no getter for the generator state | upstream_code | pyhantek1008C.py:632-636 |
| set_generator_speed asserts 1 <= speed_in_rpm <= 750_000 and sends the computed pulse length with command 0xb9 | upstream_code | pyhantek1008C.py:638-652 |
| get_generator_waveform_max_length returns 1440 | upstream_code | pyhantek1008C.py:628-630 |
| set_generator_waveform rejects a waveform longer than 62 bytes with 'Currently not supported' | upstream_code | pyhantek1008C.py:666 |
| set_generator_waveform accepts every waveform value at most 0b1111_1111 | upstream_code | pyhantek1008C.py:667 |
| pause starts a keep-alive thread that pings the device every 0.01 s; cancel_pause joins it and is_paused reports whether it is set | upstream_code | pyhantek1008C.py:677-700 |

Limits: the generator speed is 1 to 750000 rpm (`pyhantek1008C.py:641`); a generator waveform has at most 62 bytes
(`pyhantek1008C.py:666`) and every waveform value is at most 0b1111_1111 (`pyhantek1008C.py:667`). The class's
static maximum length of 1440 (`pyhantek1008C.py:630`) is larger than the length the setter actually accepts, so
the action uses the setter's bound.

Reads: `generator_on` and `generator_speed` report the last value this driver commanded. The upstream class sends
the generator commands but has no getter for either state (`pyhantek1008C.py:632-636`); after construction its
`init1` leaves the generator off at 300000 rpm (`pyhantek1008C.py:332-333`).

Safety: the e-stop and the safe-state action
`x-cap.vadter.generator_off.v1` stop the keep-alive pause thread and call `set_generator_on(False)`
(`pyhantek1008C.py:632-636`). No line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set; this is an R1 hardware driver and the safe-state action satisfies SAFE-045.

NOT COVERED: the sample arrays returned by `request_samples_burst_mode` and `request_samples_roll_mode`; the
per-channel getters that take a channel argument (`get_vscale`, `get_zero_offset`) because a `@read` takes no
input; and the zero-offset table (`get_zero_offsets`). No catalogue class carries the trace array, so the package
serves the settings and status scalars and does not transfer samples.

Tags: oscilloscope, usb, eight-channel, waveform-generator, measurement
