# Facts and tags for gh.gormleylab/spectramax

Every fact cites its source at commit `7940d4064663d576cbe8b1200e529f3acc1ef924`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Spectramax is the Python wrapper around the SoftMax Pro Automation API | upstream_code | spectramax.py:1-4 |
| initialize() creates an SMPAutomationClient, connects it to a server and port, and returns False if the connection fails | upstream_code | spectramax.py:66-98 |
| get_data() returns the current plate data as a tab-delimited string, or None on error | upstream_code | spectramax.py:353-358 |
| get_instrument_status() returns the status string stored by the InstrumentStatusChanged event | upstream_code | spectramax.py:405-412 |
| set_temperature() sets the incubator temperature in Celsius; 0 turns the incubator off | upstream_code | spectramax.py:383-388 |
| read_UVVis() takes a .spr method file and a results base path, starts the read, saves a .sda file and exports COLUMNS .csv and .xml files | upstream_code | spectramax.py:204-270 |
| read_UVVis() waits up to 120 s for the read command to complete | upstream_code | spectramax.py:242-244 |
| The automation interface queues commands and returns their results through CommandCompleted events | vendor_doc | spectramax_API.md:376-381 |

## Capabilities

- `x-cap.gormleylab.set_incubator_temperature.v1` is served by `set_incubator_temperature`, which calls the
  upstream `set_temperature(target_temperature)` and reports the requested set point. The upstream wrapper has no
  temperature getter, so the driver does not claim a measured temperature or a `reached` flag. No catalogue class
  fits: `cap.thermal.setpoint.v1` binds `thermal.zone`, `instrument.incubator` and `lab.thermal_block`, not the
  `instrument.spectrophotometer` kind of this plate reader; the incubator is one feature of the reader, and
  declaring the whole device as a thermal zone would misdescribe it.
- `x-cap.gormleylab.uvvis_read.v1` is served by `read_uvvis`, which calls the upstream
  `read_UVVis(method, results)` and reports the `.sda`, `.csv` and `.xml` paths the wrapper writes
  (spectramax.py:247-262). No catalogue class fits: `cap.measure.spectrum.v1` binds
  `instrument.spectrophotometer`, but it requires `wavelength_min` and `wavelength_max`, which the upstream method
  does not accept (it reads a .spr method file instead). The extensions are recorded in `RESULT.json`
  `catalogue_requests`.
- `x-cap.gormleylab.incubator_off.v1` is the safe-state action: `set_temperature(0.0)`, the documented off state
  (spectramax.py:388).

The card also suggested `cap.sensing.read.v1`; it binds `sensor`, `sensor.imu` and `sensor.force_torque`, not the
`instrument.spectrophotometer` kind of this plate reader. The plate data read is therefore a state parameter, and
the two actuating functions use extension ids with inline schemas (recorded in `RESULT.json`
`catalogue_requests`).

## Limits

`x-cap.gormleylab.set_incubator_temperature.v1` `target_temperature` is `Limit.operator_required`. The clone states
only that 0 turns the incubator off (spectramax.py:388) and never states an operating range; a constructor default
or a catalogue default is not a bound of the device. Until the site supplies the range of its unit, every call is
refused `MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an example overlay and not a statement about any
unit.

The extension inputs are paths (strings) and carry no numeric bound.

## Safety

The e-stop (`stop`) and the safe-state action (`x-cap.gormleylab.incubator_off.v1`) both call the upstream
`set_temperature(0.0)`, which turns the incubator off (spectramax.py:388). No line of the clone documents an
independent hardware emergency stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045
for this R2 hardware driver. The clone's `set_temperature()` waits for a command-completion event with its own
timeout (spectramax.py:397-398), so the stop is a queued software command, not a safety-rated channel.

This package is model-authored and unreviewed (`driver.lock.json` `reviewed_by` is null): the R2 hardware backend is
refused by the loader until a human reviews it, and only the fake backend was exercised here.

Tags: plate reader, spectrophotometer, uv-vis, softmax pro, incubator
