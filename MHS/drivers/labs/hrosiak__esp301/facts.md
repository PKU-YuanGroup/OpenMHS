# Facts and tags for gh.hrosiak/esp301

Every fact cites its source at commit `b0d1921faf37a8afcceee73d2e9a38f2639adc79`: `vendor_doc` (README.md) or
`upstream_code` (`esp.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a simple Python module to control a Newport ESP 301 stepper motion controller | vendor_doc | README.md:2 |
| The clone requires a USB or serial connection to the ESP301 and the PySerial module | vendor_doc | README.md:5-6 |
| The constructor takes dev, b, axis, reset, initpos and useaxis and opens serial.Serial(dev, b) | upstream_code | esp.py:4-5 |
| The served axes are useaxis, or axis alone when useaxis is empty; axis is kept as defaxis | upstream_code | esp.py:6-9 |
| When reset is true the constructor resets each axis in use and calls check_errors, and for a nonzero initpos it calls setpos | upstream_code | esp.py:10-20 |
| reset(axis) writes '<axis>OR;<axis>WS0' followed by a carriage return | upstream_code | esp.py:22-23 |
| check_errors writes 'TE?' followed by a carriage return and returns the reply as a float | upstream_code | esp.py:25-27 |
| getpos(axis) writes '<axis>TP' followed by a carriage return and returns the reply as a float | upstream_code | esp.py:29-34 |
| setpos(pos, axis) writes '<axis>PA<pos with four decimals>;<axis>WS1;<axis>TP' followed by a carriage return and returns the reply as a float | upstream_code | esp.py:36-42 |
| position(pos) with a numeric pos calls setpos, getpos and setpos again, and finally returns getpos | upstream_code | esp.py:44-49 |
| The clone defines no stop, abort or halt method: its methods are reset, check_errors, getpos, setpos and position | upstream_code | esp.py:22-49 |
| The clone reads and writes positions as bare floats and names no physical unit | upstream_code | esp.py:29-42 |
| The README usage example opens a device at 19200 baud with default axis 1 and calls setpos(20.0, 1); neither number is a travel range | vendor_doc | README.md:12-14 |

Limits:

| parameter | command | limit | ref |
|---|---|---|---|
| target_position (the controller's own position units, unit `1`) | PA | `Limit.operator_required`: the clone states no travel range; the site supplies the axis envelope | esp.py:36-42 (setpos accepts any float) |

The clone never validates a position: `setpos` formats the given number into the `PA` command (`esp.py:41`). The
constructor default `initpos = 0.0` (`esp.py:4`) and the README usage value `20.0` (`README.md:13`) are configuration
and usage examples, not device travel bounds, so they are not Limits. `site-limits.example.json` uses those two
numbers only as an example overlay that makes the conformance run able to write; it is not a statement about any
stage and the real bench must supply its own minimum and maximum.

Safety: the clone defines no stop, abort or halt method; its only state-changing methods are `reset` (writes
`<axis>OR;<axis>WS0`, `esp.py:22-23`) and `setpos` (writes the PA/WS/TP line, `esp.py:36-42`). The e-stop and the
`x-cap.hrosiak.reset_axis.v1` action send the upstream reset. This package does not claim that the reset stops a move
already in progress, and it is R1: no independent hardware stop is declared here, and none was tested.

Tags: motion, stepper, controller, esp301, serial, newport
