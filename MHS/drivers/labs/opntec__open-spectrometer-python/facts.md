# Facts and tags for gh.opntec/open-spectrometer-python

Every fact cites its source at commit `a15b67d9afb48713baeb748000433554adf26980`: `upstream_code` for a line of
`TCD1304.py`, `vendor_doc` for a text file of the clone. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The module is a TCD1304 linear CCD driver for Open Spectrometer; its pin map assigns master_clock to SQ1, sh_clock to SQ2, icg_clock to SQ3, +5V to PV1, GND to GND and OS to CH1 | upstream_code | TCD1304.py:1-10 |
| The module imports SerialHandler, Oscilloscope, PowerSupply and PWMGenerator from the external pslab SDK | upstream_code | TCD1304.py:15-18 |
| TCD1304 is a linear CCD suitable for visible spectrum analysis | upstream_code | TCD1304.py:24-25 |
| The class declares 3694 integration elements, a CH1 range constant of 4, a trigger voltage constant of 2 and two samples per element | upstream_code | TCD1304.py:27-30 |
| The constructor accepts a device, an integration time defaulting to 10e-6 and a master clock frequency defaulting to 2e6; without a device it creates SerialHandler and composes the PWM generator, oscilloscope and power supply over it | upstream_code | TCD1304.py:32-43 |
| Construction powers the CCD on and starts the SQ3, master and SH clocks | upstream_code | TCD1304.py:45-48 |
| poweron sets the PV1 supply to 5 and poweroff sets it to 0 | upstream_code | TCD1304.py:50-56 |
| poweron is documented as turning the TCD1304 on and poweroff as turning it off | upstream_code | TCD1304.py:50-56 |
| The ICG readout waits 3694 * integration_time seconds before the waveform is fetched | upstream_code | TCD1304.py:58-64 |
| The oscillator frequency constant is 128e6 and the microseconds constant is 1e6 | upstream_code | TCD1304.py:20-21 |
| The master clock prescaler is derived from the oscillator frequency and the master clock frequency | upstream_code | TCD1304.py:66-70 |
| The SH clock is generated at 1 / integration_time with a 50 percent duty cycle | upstream_code | TCD1304.py:72-73 |
| read_signal selects the CH1 range and trigger, captures 3694 * 2 samples with a time gap of integration_time / 2 in microseconds, starts the ICG clock and returns the fetched waveform | upstream_code | TCD1304.py:75-87 |
| The README describes the repository's main components as analyse.py and calibrate.py for webcam spectrometer images; it does not document the TCD1304 class | vendor_doc | README.md:8 |
| The README's calibration procedure assigns wavelength values to pixels by hand from a CFL reference; the TCD1304 class itself applies no wavelength calibration | vendor_doc | README.md:46-55 |

Limits: the writable state `integration_time` (served through `cap.device.configure.v1`) and the optional
`integration_ms` input of `cap.measure.intensity.v1` are `Limit.operator_required`. The constructor default
`integration_time=10e-6` s (TCD1304.py:35) is a default of the class, not a bound of the device, and the clone
states no range; the site supplies the per-element range of its CCD (`site-limits.example.json` is an example
overlay only).

Safety: the e-stop is the native `poweroff` (PV1 = 0, TCD1304.py:54-56); the declared safe state is the CCD
powered off. A safety reset releases the latch and re-arms nothing (SAFE-042): the driver has no `@reset` hook,
so the supply stays off after a reset. The native `poweron` (PV1 = 5, TCD1304.py:50-52) is the declared re-enable
`x-cap.opntec.power_on.v1` (`reenable=True`, CORE-086): a command of its own, with no input, refused while the
e-stop is latched and named in the reset receipt. Until 2026-11-05 the `@reset` hook called `poweron` itself, which
SAFE-042 forbids. No line of the clone documents an independent hardware e-stop; the device is R1 (the class
floor of `cap.device.configure.v1`, above the card floor R0) and SAFE-045 asks for an independent physical stop
only at R2 or above, so no `estop_physical_ref` is claimed. This is a software stop, not a safety-rated channel.

Coverage: the upstream `read_signal` returns a raw waveform of 3694 * 2 = 7388 samples without a wavelength axis
(TCD1304.py:75-87); the driver exposes only the largest sample of one capture and the integration time. The raw
array is NOT COVERED. `cap.measure.spectrum.v1` is not bound because its wavelength inputs would be unapplied and
the clone states no TCD1304 calibration.

Tags: spectrometer, ccd, tcd1304, pslab, optics, intensity
