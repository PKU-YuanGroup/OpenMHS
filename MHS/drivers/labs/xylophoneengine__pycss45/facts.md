# Facts and tags for gh.xylophoneengine/pycss45

Every fact cites its source at commit `e4364bae4d889efd579ffb3c4947099405becb27`: `upstream_code` (a code or
docstring line of the clone) or `vendor_doc` (a text file of the clone, here `README.md`).  The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

The package drives one Gigahertz-Optik CSS45/MSC15 spectral sensor through the card's entry class
`pycss45:CSS45` (pycss45.py:438).  It exposes the device state, one spectrum measurement of the catalogue
class `cap.measure.spectrum.v1` (a device kind `instrument.spectrometer`), and nothing that actuates: no
method of the upstream class sets an output, a heater or a motor.

| fact | source | ref |
|---|---|---|
| The module is a cross-platform driver for the Gigahertz-Optik CSS45/MSC15 spectral sensor and speaks the wire protocol over USB HID or RS232/RS485 | upstream_code | pycss45.py:1-9 |
| The spectral unit has 288 pixels (N_PIXELS) | upstream_code | pycss45.py:31 |
| A Measurement holds the wavelengths in nm, the spectrum in W m^-2 nm^-1 per vendor calibration, the integration time in s, the CCT in K, the photopic integral and PAR | upstream_code | pycss45.py:136-142 |
| measure() is the automatic integration time measurement (wire G07200, Ihi, G17) and returns a Measurement | upstream_code | pycss45.py:786-789 |
| get_cct reads G22 in K, get_photopic reads G2R and get_par reads G2L | upstream_code | pycss45.py:859-872 |
| get_temperature returns the PCB temperature in deg C; the unit is unverified | upstream_code | pycss45.py:779-780 |
| get_wl_borders returns the first and last wavelength of the per-pixel mapping in nm | upstream_code | pycss45.py:830-836 |
| get_radiometric_unit reads IhcU and returns W or W/m2 | upstream_code | pycss45.py:896-899 |
| get_last_integration_time reads Ihi in microseconds and returns seconds | upstream_code | pycss45.py:811-815 |
| get_serial_number returns the USB descriptor serial on the hid transport and an empty string on the serial transport | upstream_code | pycss45.py:751-759 |
| get_firmware_version sends P and returns the reply string | upstream_code | pycss45.py:761-765 |
| get_status reads the I0 status word; positive codes are warnings and negative codes raise | upstream_code | pycss45.py:767-777 |
| The README states the measured spectrum plots as nm vs W m^-2 nm^-1 | vendor_doc | README.md:58-66 |
| The README states the wavelength borders of the CSS45 are 360-830 nm, verified on a live CSS45 | vendor_doc | README.md:100-103 |
| The README states the GUI shows the photopic integral in lx and the radiometric integral in W/m2 | vendor_doc | README.md:119-120 |
| The README states the fixed integration times run from 12 us to 2.56 s | vendor_doc | README.md:105-106 |

Limits: both inputs of `cap.measure.spectrum.v1` are bounded to 360-830 nm, the wavelength borders the
README states for the CSS45 (`README.md:102`).  The per-pixel borders are read from the device at runtime by
`get_wl_borders()` (`pycss45.py:830-836`), so the driver filters the measured native grid rather than
inventing a grid.  A request outside 360-830 nm is refused by the runtime with
`MHS.SAFETY.ENVELOPE_VIOLATION` before any native call.  A range narrower than one pixel returns the
nearest device pixel, so an accepted request never produces an empty spectrum.

The catalogue class publishes `intensities` with the unit `1`; the upstream spectrum is calibrated in
`W m^-2 nm^-1` per the vendor calibration (`pycss45.py:138`).  The driver returns those values unchanged and
says so in the action description; no unit conversion is applied.

Safety: the device only observes light (MHS/spec/04-safety.md R0, observational, data only).  No upstream
method sets an output, a heater or a motor, so the package declares `risk = "R0"` with no native e-stop and
no safe-state action; the runtime still latches a software-only e-stop.  No text file of the clone documents
an independent hardware e-stop, and none is claimed.  This package is model-authored and unreviewed; the
fake backend is not a recording of a device.

Fake: `fake.py` implements only public methods of `pycss45:CSS45` (gate G7).  It returns a deterministic
288-point synthetic spectrum and fixed state values; each is test data and is marked `# placeholder` in the
file.  It is not the upstream simulator (`DemoCSS45` in `pycss45_gui.py`) because the card's
`mock_strategy.preferred` is `fake`; nothing here imports or runs the upstream package.

Tags: spectrometer, spectral-sensor, optical, gigahertz-optik, css45, msc15
