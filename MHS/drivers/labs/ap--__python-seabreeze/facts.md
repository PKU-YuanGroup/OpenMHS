# Facts and tags for gh.ap/python-seabreeze

Every fact cites its source at commit `3de4fdd6bbb533a701309c746c94cac2ffc05be0`: `upstream_code` (a code or a
docstring line of the clone) or `vendor_doc` (a text file of the clone such as README.md).  The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

The package drives one Ocean Optics spectrometer through the model independent class
`seabreeze.spectrometers:Spectrometer` (the card's first entry symbol).  It exposes the device state, one intensity
measurement of the class `cap.measure.intensity.v1` (optionally at a declared wavelength and with a declared
integration time), and one extension action that sets the detector integration time persistently.  Both settings
are actions rather than writable state because the class has no getter that would report them back.

| fact | source | ref |
|---|---|---|
| Spectrometer is the model independent interface to all spectrometers the backends support | upstream_code | src/seabreeze/spectrometers.py:97-98 |
| from_first_available opens the first available unopened spectrometer | upstream_code | src/seabreeze/spectrometers.py:140-141 |
| from_serial_number opens the spectrometer with the given serial number and refuses one that is already open | upstream_code | src/seabreeze/spectrometers.py:155-185 |
| wavelengths() returns the wavelength in (nm) that corresponds to each pixel of the spectrometer | upstream_code | src/seabreeze/spectrometers.py:187-190 |
| intensities() returns the measured intensities in arbitrary units (a.u.), and the measuring behavior can be adjusted by setting the trigger mode | upstream_code | src/seabreeze/spectrometers.py:202-205 |
| The intensities are in arbitrary units and their range depends on the ADC bit resolution of the hardware of the specific spectrometer | upstream_code | src/seabreeze/spectrometers.py:212-213 |
| max_intensity is the maximum intensity the spectrometer can return in (a.u.); the spectrometer may saturate at lower values | upstream_code | src/seabreeze/spectrometers.py:265-271 |
| integration_time_micros() sets the detector integration time, in microseconds | upstream_code | src/seabreeze/spectrometers.py:305-310 |
| integration_time_micros_limits returns the min and max integration time in microseconds that the device reports | upstream_code | src/seabreeze/spectrometers.py:334-342 |
| The trigger mode value is the one the device's datasheet defines; the class states no enumeration for a generic device | upstream_code | src/seabreeze/spectrometers.py:344-351 |
| serial_number is the spectrometer's serial number and model is its model type | upstream_code | src/seabreeze/spectrometers.py:356-363 |
| pixels is the number of pixels of the spectrometer's detector | upstream_code | src/seabreeze/spectrometers.py:366-367 |
| features returns a dictionary of all supported features of the spectrometer and gives direct access to the features provided by the backend interface | upstream_code | src/seabreeze/spectrometers.py:372-376 |
| close() closes the connection to the SeaBreezeDevice | upstream_code | src/seabreeze/spectrometers.py:413-414 |
| The pyseabreeze backend declares the integration time bounds per spectrometer model: USB2000PLUS 1000 and 655350000 microseconds | upstream_code | src/seabreeze/pyseabreeze/devices.py:503-504 |
| The pyseabreeze backend declares different integration time bounds for the USB2000: 3000 and 655350000 microseconds | upstream_code | src/seabreeze/pyseabreeze/devices.py:579-580 |
| The GPIO feature class of the pyseabreeze backend is a definition only: the module is marked TODO and every method raises NotImplementedError | upstream_code | src/seabreeze/pyseabreeze/features/gpio.py:7 |
| The pixel-binning feature class of the pyseabreeze backend is a definition only: the module is marked TODO and every method raises NotImplementedError | upstream_code | src/seabreeze/pyseabreeze/features/pixelbinning.py:7 |
| The README acquires a spectrum by setting the integration time and then calling wavelengths() and intensities() | vendor_doc | README.md:56-67 |

Limits: the two numeric inputs of this package carry `Limit.operator_required`.  No line of the clone states one
integration time range or one wavelength range for a spectrometer: the integration time bounds are declared per
model in the pyseabreeze backend (`src/seabreeze/pyseabreeze/devices.py:503-504` for USB2000PLUS, `:579-580` for
USB2000) and read from the device at runtime (`Spectrometer.integration_time_micros_limits`); the wavelength range
comes from the detector's own wavelength calibration (`Spectrometer.wavelengths`).  A bound of one model is not a
bound of another device, so the site states the range of its spectrometer in `site-limits.json`;
`site-limits.example.json` is an example overlay, not a statement about any device.

Safety: the device of this package only measures and sets no output, so the e-stop calls the upstream `close()`
(`src/seabreeze/spectrometers.py:413-414`), which closes the device connection and thereby ends an acquisition.  The
upstream class has no separate acquisition stop and no getter that would report a trigger mode or an integration
time back, so the two settings are actions and not writable state.  The card's risk floor is R1 and no line of the
clone documents an independent hardware e-stop, so `estop_physical_ref` is not set (SAFE-045's R2+ rule does not
apply).

Conformance input: `fixtures/conformance.json` pins the input of `cap.measure.intensity.v1` to the empty object,
the measurement with neither a wavelength nor an integration time, because the class example carries the two
operator-required fields and the acceptance gate serves the operator overlay to the conformance run but not to the
state read it takes before the actions.  The same empty input is a valid measurement: it reads the brightest pixel.

Not exposed: the spectral array itself (the full wavelength and intensity arrays of all pixels).  The standard has
no artifact transport and a fake cannot reproduce the model-dependent pixel count of a real detector, so an array
capability would either ship a truncated spectrum or need the artifact store that `cap.measure.spectrum.v1`
references with `artifact_ref`.  The GPIO, pixel-binning, optical-bench and Wi-Fi feature classes of the card's
entry_symbols are definitions in the pyseabreeze backend (TODO, `NotImplementedError`), are reached through the
device's feature dictionary rather than through `Spectrometer`, and bind io resource kinds that an
`instrument.spectrometer` does not declare; they are not exposed.  The trigger mode is not exposed either, because
the class documents its value as device-datasheet specific and has no getter.

Tags: spectrometer, ocean-optics, seabreeze, spectroscopy, intensity
