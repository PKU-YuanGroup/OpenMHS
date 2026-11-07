# Facts and tags for gh.hslarson/speck-lab-goniometer

Every fact cites `upstream_code` in the clone at commit `9ca84d8c8c6c6ec9f9f3a3bd3cd968fc6657a803`. The same facts
are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SpectrometerWrapper is the upstream handle around the Compact Spectrometer SDK instance and stores it in self.spectrometer | upstream_code | src/components/pyCCT/pyCCT.py:222-228 |
| get_device_id returns the SDK DeviceId string | upstream_code | src/components/pyCCT/pyCCT.py:236-240 |
| set_manual_exposure takes an exposure time in milliseconds and returns the result of SetManualExposureAsync | upstream_code | src/components/pyCCT/pyCCT.py:242-255 |
| get_manual_exposure returns ManualExposure rounded to 2 decimals | upstream_code | src/components/pyCCT/pyCCT.py:260-264 |
| set_hardware_average takes a frame count and returns the result of SetHwAverageAsync | upstream_code | src/components/pyCCT/pyCCT.py:266-279 |
| get_hardware_average returns HwAverage as an int | upstream_code | src/components/pyCCT/pyCCT.py:284-288 |
| acquire_single_spectrum returns wavelength and intensity lists, SensorExposureMs rounded to 2 decimals, and HardwareAverage | upstream_code | src/components/pyCCT/pyCCT.py:290-304 |
| set_shutter passes open_position to SetShutterAsync, waits 0.04 s, and returns its result | upstream_code | src/components/pyCCT/pyCCT.py:306-325 |
| set_input_hw_trigger takes enabled, ave_no_wait and slope_falling_edge flags and returns the result of SetInputHwTriggerAsync | upstream_code | src/components/pyCCT/pyCCT.py:345-364 |
| get_input_hw_trigger_state returns HwTriggerIn, HwTriggerInAveNoWait and HwTriggerInSlope | upstream_code | src/components/pyCCT/pyCCT.py:366-370 |
| set_output_hw_trigger_delay takes a delay in milliseconds; the docstring says a negative value schedules acquisition start after the output trigger | upstream_code | src/components/pyCCT/pyCCT.py:372-388 |
| get_output_hw_trigger_delay returns HwTriggerOutDelayMs rounded to 2 decimals | upstream_code | src/components/pyCCT/pyCCT.py:393-397 |
| get_use_amplitude_correction returns UseAmplitudeCorrection | upstream_code | src/components/pyCCT/pyCCT.py:399-403 |
| set_use_amplitude_correction assigns state to UseAmplitudeCorrection | upstream_code | src/components/pyCCT/pyCCT.py:405-409 |
| PyCCT.discover_devices returns the known device connection keys or an empty list | upstream_code | src/components/pyCCT/pyCCT.py:91-118 |
| PyCCT.connect_to_device returns a SpectrometerWrapper around GetCompactSpectrographById or None | upstream_code | src/components/pyCCT/pyCCT.py:120-136 |

Limits: the numeric settings `manual_exposure`, `hardware_average`, `output_hw_trigger_delay` and the spectrum
action's `wavelength_min` / `wavelength_max` are `Limit.operator_required`. The clone names the units but no line
states a numeric range for any of them, so no bound is copied from a constructor default. The site supplies the
limits of its own unit; `site-limits.example.json` is an example overlay, not a statement about a real spectrometer.

Safety: the R1 safe state is the mechanical shutter closed. The e-stop calls the native `set_shutter(False)`
(src/components/pyCCT/pyCCT.py:306-325). No line of the clone documents an independent hardware e-stop, and this R1
package does not declare one. Nothing here is a safety-rated channel.

Scope: this package serves `components.pyCCT.pyCCT:SpectrometerWrapper`. The Zaber stage wrappers in the same clone
are not exposed: a Driver has one native class, and the motion catalogue classes cannot bind an
`instrument.spectrometer` resource. No motion, homing or stage limit is claimed by this package.

Spectrum data: the fake returns 64 points as test data (`# placeholder`). The clone does not state the detector's
pixel count, so the real array length is not named. The action filters the returned detector samples to the requested
wavelength range and returns the matching wavelength and intensity arrays.

Tags: spectrometer, spectrum, thorlabs, pycct, goniometer
