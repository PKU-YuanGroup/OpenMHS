# Facts and tags for gh.drmcnelson/linear-ccd-with-ltspice-kicad-firmware-and-python-library

Every fact cites its source at commit `fcda5364d1ec63bc1b0e17efc40508b7fdef76b3`: `upstream_code` (a code or a
docstring line of the clone) or `vendor_doc` (a text file of the clone such as README.md or the firmware help.txt).
The same facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not
from this page.

The package drives a Toshiba TCD1304 linear CCD through the serial controller
`TCD1304Rev2_Python.TCD1304Rev2Controller:LCCDCONTROLLER` (the card's first entry symbol, line 494).  It exposes the
identifier, the configuration line and the three values the controller parses from it (pixel count, dark-pixel
count and sensor name), one intensity measurement of the class `cap.measure.intensity.v1`, the extension action
`x-cap.drmcnelson.set_holdoff.v1` for the firmware sync holdoff, and the firmware stop as the e-stop.

| fact | source | ref |
|---|---|---|
| The design is based on the Toshiba TCD1304 (3648/3694 pixels) | vendor_doc | README.md:12 |
| The device appears as a serial port with commands and responses in ASCII and frames returned as binary or formatted | vendor_doc | README.md:18 |
| The controller writes each command followed by a newline and reads lines until a line starts with DONE | upstream_code | TCD1304Rev2_Python/TCD1304Rev2Controller.py:690-703 |
| On connect the controller sends stop, reads the identifier and reads the configuration line | upstream_code | TCD1304Rev2_Python/TCD1304Rev2Controller.py:561-583 |
| The configuration line carries PIXELS, DARK, INVERT and SENSOR, and optionally VPERBIT, BITS and VFS | upstream_code | TCD1304Rev2_Python/TCD1304Rev2Controller.py:579-593 |
| The reader scales each ADC sample by vperbit and subtracts the mean of the first darklength samples when baseline subtraction is on | upstream_code | TCD1304Rev2_Python/TCD1304Rev2Controller.py:1024-1028 |
| A completed frame is queued as [[data], shutter, interval, clock, counter, outercounter, frames, sets, every, mode, elapsed, 0, timestamp] | upstream_code | TCD1304Rev2_Python/TCD1304Rev2Controller.py:891-898 |
| The clock command takes the shutter time in microseconds: 'clock <n> <shutter>' reads n frames | vendor_doc | TCD1304Rev2_Python/help.txt:49-52 |
| The stop command stops clocks, triggers and gate | vendor_doc | TCD1304Rev2_Python/help.txt:6-7 |
| The send command sends the contents of the current buffer | vendor_doc | TCD1304Rev2_Python/help.txt:28-30 |
| The holdoff time is set with 'set holdoff usecs' | vendor_doc | TCD1304Rev2_Python/help.txt:82 |
| The full detector record has 12 dummy outputs, 13 light-shielded elements, 3 shadowed elements, 3648 effective elements and 14 dummy elements | vendor_doc | README.md:223 |
| The master clock is 800 kHz to 4 MHz and the data readout rate is one quarter of it, 200 kS/s to 1 MS/s (500 kS/s below 4 V) | vendor_doc | README.md:69 |
| At a 2 MHz master clock one record takes about 7.4 ms to read; transfer to the host adds 5 ms on a Teensy 3.x and about 120 us on a Teensy 4.x | vendor_doc | README.md:186 |

Limits: the two numeric inputs of `cap.measure.intensity.v1` and the holdoff input of
`x-cap.drmcnelson.set_holdoff.v1` carry `Limit.operator_required`.  The clone states that the clock command takes a
shutter time in microseconds (`TCD1304Rev2_Python/help.txt:49-52`), that one record takes about 7.4 ms to read at
2 MHz (`README.md:186`), and that the holdoff command takes microseconds (`TCD1304Rev2_Python/help.txt:82`), but it
states no minimum or maximum for either.  The pixel coordinates come from calibration coefficients supplied by the
device at run time (`TCD1304Rev2_Python/TCD1304Rev2Controller.py:602-620, 669-684`) and the clone states no
wavelength range.  A bound of one detector or one optical bench is not a bound of another, so the site states all
three ranges in `site-limits.json`; `site-limits.example.json` is an example overlay, not a statement about any
device.

Safety: the device only measures light and clocks frames; it has no output that the driver actuates beyond the
readout.  The card's risk floor is R0 and no line of the clone documents an independent hardware e-stop, so
`estop_physical_ref` is not set.  The e-stop writes the firmware `stop` command (`TCD1304Rev2_Python/help.txt:6-7`),
and `safe_state` says that readout and clocking are stopped.

Not covered: the full wavelength/intensity array of the detector.  The upstream reader queues the whole frame in
`dataqueue` (`TCD1304Rev2_Python/TCD1304Rev2Controller.py:891-898`), but this package returns only one scalar
intensity per action, at the brightest pixel or at the pixel nearest a declared wavelength.  The fake returns 16
pixels as test data; the clone names the TCD1304 detector with 3648/3694 pixels (`README.md:12`) and the full record
also has dummy, dark and shadowed elements (`README.md:223`).  The acceptance gate was run on the fake backend only;
no hardware run was made, and the upstream controller's reader process and its graphics dependency were not tried.

Tags: linear ccd, tcd1304, spectrometer, spectroscopy, serial
