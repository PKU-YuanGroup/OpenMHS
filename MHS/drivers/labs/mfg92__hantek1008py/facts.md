# Facts and tags for gh.mfg92/hantek1008py

Every fact cites its source at commit `302e45ad9d47dafec8a57c36aaca0b76647b221d`: `upstream_code` for a line of
the clone, `vendor_doc` for a text document of the clone. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Hantek1008Raw communicates with a Hantek1008 device over USB and supports configuring the device and measuring samples with it | upstream_code | hantek1008.py:37-42 |
| Hantek1008 extends Hantek1008Raw with raw-to-volt conversion and zero-offset shift compensation | upstream_code | hantek1008.py:683-687 |
| The device has 8 channels | upstream_code | hantek1008.py:434-435 |
| Channel ids and indices are zero based, and channel names are one based | upstream_code | hantek1008.py:43-44 |
| The vertical scale factors are 0.02, 0.125 and 1.0 | upstream_code | hantek1008.py:47 |
| get_vscales returns one vertical scale factor per channel and get_active_channels returns the active channel ids | upstream_code | hantek1008.py:637-645 |
| get_zero_offset returns the zero offset of one channel at a vertical scale | upstream_code | hantek1008.py:525-536 |
| init measures the zero offsets of all eight channels at each of the three vertical scales | upstream_code | hantek1008.py:327-353 |
| get_generator_waveform_max_length reports 1440 | upstream_code | hantek1008.py:539-540 |
| set_generator_waveform currently accepts at most 62 bytes; each byte is a bit pattern for the eight digital outputs | upstream_code | hantek1008.py:564-577 |
| set_generator_speed asserts a speed of 1 to 750000 rpm and sends a computed pulse length | upstream_code | hantek1008.py:548-562 |
| set_generator_on turns the generator on with parameter 0x01 and off with 0x00 | upstream_code | hantek1008.py:542-546 |
| init sets the generator speed to 300000 and turns the generator off | upstream_code | hantek1008.py:284-285 |
| pause starts a thread that sends a ping every 10 ms, cancel_pause stops it, and is_paused reports whether it runs | upstream_code | hantek1008.py:587-610 |
| connect finds the USB device by vendor id 0x0783 and product id 0x5725 | upstream_code | hantek1008.py:103-110 |
| close cancels a running pause, sends a ping and command 0xf4, then resets the USB device | upstream_code | hantek1008.py:612-620 |
| The README describes the project as tooling for Hantek 1008 USB oscilloscopes | vendor_doc | README.md:3 |
| The README states Python >= 3.6 and requires pyusb and overrides | vendor_doc | README.md:23-24 |

Limits: the generator speed action is bounded to 1 to 750000 rpm by the upstream assertion (`hantek1008.py:551`);
the comment at `hantek1008.py:553-554` says larger values are possible but use a different decoding the clone does
not understand. Every waveform byte is bounded to 0 to 255 by the upstream assertion (`hantek1008.py:577`) and the
conversion to ``bytes`` (`hantek1008.py:162-164`); the action accepts at most 62 bytes because
``set_generator_waveform`` asserts that as the currently supported length (`hantek1008.py:576`). No further
electrical bound (output voltage, current, load) is stated by a text file of the clone, so none is declared.

Safety: the e-stop and the safe-state action `x-cap.mfg92.generator_off.v1` both call
`Hantek1008.set_generator_on(False)` (`hantek1008.py:542-546`), which disables the generator outputs. ``init``
already turns the generator off (`hantek1008.py:284-285`). No line of the clone documents an independent hardware
e-stop, so `estop_physical_ref` is not set; the card's floor is R1 and the package drives no heater, pump, laser,
motion axis or other high-energy actuator.

The generator commands have no upstream getter: the driver reports the value it commanded and does not claim a
device readback. The fake is an in-memory stand-in, not a recording of a device, and every number in it is
placeholder test data.

Tags: oscilloscope, hantek, usb, signal-generator, measurement
