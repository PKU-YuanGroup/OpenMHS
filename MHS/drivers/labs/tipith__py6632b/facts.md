# Facts and tags for gh.tipith/py6632b

Every fact cites its source at commit `a91f78a004f592e7588d483f28daebcbab8572e8`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The upstream clone
has no README or manual text, so every fact below is `upstream_code`; no PDF page is cited.

| fact | source | ref |
|---|---|---|
| The serial line is opened at 9600 baud with a 0.5 s read timeout | upstream_code | py6632B/py6632B.py:36 |
| The constructor resets the instrument and identifies it with `*IDN?`; it accepts the unit when the reply contains `HEWLETT-PACKARD,6632B` | upstream_code | py6632B/py6632B.py:41-44 |
| A measurement is read with `MEAS:VOLT?;CURR?` and split into voltage and current | upstream_code | py6632B/py6632B.py:112-115 |
| The source is set with `SOUR:VOLT %.3f; CURR %u MA`: voltage in volts with three decimals and current in milliamperes as an integer | upstream_code | py6632B/py6632B.py:119-122 |
| Output enable writes `OUTP:STAT 1` or `OUTP:STAT 0`; `OUTP:STAT?` reads the state | upstream_code | py6632B/py6632B.py:124-135 |
| The native stop sets the output state to 0, clears the logging run flag and joins the logging thread | upstream_code | py6632B/py6632B.py:84-88 |
| A measurement query takes about 109 ms | upstream_code | py6632B/py6632B.py:48-50 |
| The upstream code charges and discharges a Li-ion battery, deriving the current from the battery capacity | upstream_code | py6632B/py6632B.py:178-185 |
| The upstream `oscillate()` sets 15 V and 1000 mA before toggling the output | upstream_code | py6632B/py6632B.py:158-162 |
| The display accepts mode NORM or TEXT and at most 14 characters of text | upstream_code | py6632B/py6632B.py:137-147 |
| `stop()` calls `isAlive()`, a Python 2 Thread method | upstream_code | py6632B/py6632B.py:87 |
| `oscillate()` iterates with `xrange()`, a Python 2 built-in | upstream_code | py6632B/py6632B.py:160 |
| The package `__init__` imports `HP6632B` with an implicit relative import | upstream_code | py6632B/__init__.py:1 |

Limits: the output voltage and current inputs of `x-cap.tipith.set_source.v1` are `Limit.operator_required`. No text
file of the clone states an output voltage or current range; the numbers in the source are commands the upstream code
chooses (15 V and 1000 mA at py6632B/py6632B.py:159, battery-derived currents at py6632B/py6632B.py:183-185), not
device ratings. The operator supplies the bounds of the bench in `site-limits.json`;
`site-limits.example.json` is an example with 0 to 5 V and 0 to 100 mA, not a statement about a particular unit.
Without that overlay every call that sets voltage or current is refused `MHS.SAFETY.LIMITS_UNSET`.

Risk: R2. The upstream package is a battery charger/discharger (py6632B/py6632B.py:178-185, 268-271): the output is
an energy source that can heat or damage a cell if a set point is wrong, not an observation-only instrument. The
catalogue class floor is R1 (`cap.device.configure.v1`) but the device itself is at least R2.

Safety: the native stop (`stop()`, py6632B/py6632B.py:84-88) sets `OUTP:STAT 0` and is the `@estop` method. The
safe-state action `x-cap.tipith.stop_output.v1` writes `OUTP:STAT 0` again, so SAFE-045 is satisfied by a safe-state
action; no line of the clone documents an independent hardware e-stop, so `estop_physical_ref` is not set. The e-stop
is the device's software stop, not a certified protective function.

Tags: power-supply, dc-source, battery-charger, serial

## Honest limits of this package

- The hardware backend (`native.py`) was never run. The upstream module is Python 2-era code: `oscillate()` uses
  `xrange` (py6632B/py6632B.py:160), `stop()` calls `isAlive` (py6632B/py6632B.py:87), and `py6632B/__init__.py:1`
  uses an implicit relative import. The loader refuses the R2 hardware backend of this unreviewed model-written
  package until a human signs `reviewed_by`.
- The fake is an in-memory object, not a recording of a device. Its start values and identity reply are placeholders;
  it keeps the set points as the measured values, which is only true in constant-voltage operation.
- The driver does not expose the display, the CSV logging loop, the callback, `hiZ()` or the battery charge/discharge
  helpers. They are not needed to read or control the source, and the logging thread's lifecycle is not modelled.
- The measurement read is a pair of scalar values. No array or waveform is produced by this device.
