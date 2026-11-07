# Facts and tags for gh.pmezydlo/oscilloscope_lan_data_capture

Upstream clone at commit `f68c0b8d5acb7592ad21fd39b453d5a4d892a91e`.  Every fact below is also declared as a `Fact`
in `driver.py`; the reference file is generated from the driver, not from this page.  `source` is `upstream_code`
(`path/in/clone:LINE`) or `vendor_doc` (a text file of the clone).

| fact | source | ref |
|---|---|---|
| The project captures data from a Rigol DS1000Z series oscilloscope over LAN | vendor_doc | README.md:2 |
| The oscilloscope class extends the device transport class | upstream_code | oscilloscope_functions.py:6 |
| The device constructor sends *IDN? on connect | upstream_code | measure_interfaces.py:144 |
| The *IDN? reply is split into manufacturer, device name, serial number and firmware version | upstream_code | measure_interfaces.py:152-155 |
| The active-channel list is empty at construction and get_active_channel fills it | upstream_code | oscilloscope_functions.py:11-19 |
| get_active_channel builds channel names CHAN1 through CHANn from the configured channel count | upstream_code | oscilloscope_functions.py:14 |
| A channel is kept as active when its display query answers '1\n' | upstream_code | oscilloscope_functions.py:17-19 |
| The clone's example constructs the oscilloscope with four channels over USB | upstream_code | oscilloscope.py:14 |
| plot reads the timebase scale with :TIM:SCAL? and the timebase offset with :TIM:OFFS? | upstream_code | oscilloscope_functions.py:26-27 |
| plot reads each active channel's vertical scale with :<CHANn>:SCAL? and offset with :<CHANn>:OFFS? | upstream_code | oscilloscope_functions.py:32-33 |
| The captured time axis runs from time_offset - 6 * time_scale to time_offset + 6 * time_scale | upstream_code | oscilloscope_functions.py:48 |
| plot sets the waveform point mode with :WAV:POIN:MODE RAW, reads :WAV:DATA? with the channel name and writes :KEY:FORCE | upstream_code | oscilloscope_functions.py:37-39 |
| The waveform reply drops its first 10 characters before the samples are converted | upstream_code | oscilloscope_functions.py:38 |
| plot references tUnit, but tUnit is only named in commented-out code, so the method cannot complete | upstream_code | oscilloscope_functions.py:62 |
| The serial transport writes a command and reads one line back | upstream_code | measure_interfaces.py:22-25 |
| The LAN transport sends *OPC? until it reads 1\n, then sends the command with a newline and reads until a newline | upstream_code | measure_interfaces.py:90-98 |
| The LAN transport is a copy of the Python 2.7 telnetlib with a patch that keeps null characters | upstream_code | telnetlib_receive_all.py:1-2 |
| The USB transport read ignores its command argument and sends *OPC? without returning a value | upstream_code | measure_interfaces.py:58-67 |

Tags (short lowercase keywords): oscilloscope, rigol, ds1000z, scpi, lan, serial, usb, waveform.

Limits: none.  The clone sends no numeric instrument setting; the only writes are the fixed strings
`:WAV:POIN:MODE RAW` and `:KEY:FORCE` (oscilloscope_functions.py:37-39), which are not exposed as writes.  No bound is
invented from the constructor's channel count, a sample capture or a default.

NOT COVERED: the waveform array and the PNG plot.  `plot` cannot complete because it references `tUnit`
(oscilloscope_functions.py:62) while only the commented-out lines 50-57 assign it, and the clone's transport is
Python 2.  The package reads the scalar settings with the clone's own queries and does not transfer samples.

Hardware: no hardware backend is registered.  The clone's LAN transport is a copy of the Python 2.7 telnetlib
(telnetlib_receive_all.py:1-2) imported by the `device` constructor, and its serial path passes text to
`serial.write`; the package runs on Python 3 and is checked on the fake backend only.  No hardware was attached and
no hardware run is claimed.
