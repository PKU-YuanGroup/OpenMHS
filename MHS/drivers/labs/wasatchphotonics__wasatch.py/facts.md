# Facts and tags for gh.wasatchphotonics/wasatch.py

Every fact cites its source at commit `c3ea52bde83d9d004d0b97850f09515dfc42f741`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| FeatureIdentificationDevice is the basic implementation of the Wasatch FID spectrometer USB API defined in ENG-0001 | upstream_code | wasatch/FeatureIdentificationDevice.py:41-47 |
| get_integration_time_ms reads GET_INTEGRATION_TIME_MS and returns the value in milliseconds | upstream_code | wasatch/FeatureIdentificationDevice.py:937-947 |
| set_integration_time_ms rounds to an integer millisecond value, sends SET_INTEGRATION_TIME_MS (0xB2) and stores the session value | upstream_code | wasatch/FeatureIdentificationDevice.py:1687-1713 |
| The minimum and maximum integration time are EEPROM fields of each unit, not constants of the class | upstream_code | wasatch/EEPROM.py:105-106 |
| get_spectrum returns the acquired pixel intensities as response.data | upstream_code | wasatch/FeatureIdentificationDevice.py:1652-1653 |
| The wavelength axis is generated from the EEPROM wavelength calibration coefficients | upstream_code | wasatch/SpectrometerSettings.py:325 |
| get_laser_enabled reports the laser enable state | upstream_code | wasatch/FeatureIdentificationDevice.py:2482-2502 |
| set_laser_enable turns the laser on or off and false turns it off | upstream_code | wasatch/FeatureIdentificationDevice.py:2504-2523 |
| The laser_enable setting is documented as turning the laser on or off | vendor_doc | README_SETTINGS.md:113-114 |
| get_detector_temperature_degC converts the detector temperature reading to degrees Celsius | upstream_code | wasatch/FeatureIdentificationDevice.py:2279-2290 |
| get_detector_tec_setpoint_degC reports the applied detector TEC set point in degrees Celsius | upstream_code | wasatch/FeatureIdentificationDevice.py:2325-2329 |
| get_tec_enabled reads the detector TEC enable state | upstream_code | wasatch/FeatureIdentificationDevice.py:3483-3491 |
| get_ambient_temperature_degC reports the ambient temperature on XS and Gen 1.5 spectrometers | upstream_code | wasatch/FeatureIdentificationDevice.py:3416-3423 |
| disconnect disables the laser if it was enabled and releases the interface | upstream_code | wasatch/FeatureIdentificationDevice.py:453-474 |

Limits: the integration time is `Limit.operator_required`. The minimum and maximum integration time are EEPROM fields
of each unit (`wasatch/EEPROM.py:105-106`), so no text file states one range for all units; the site supplies the
range of its unit (`site-limits.example.json` shows the overlay). The numbers in the example overlay are an example,
not a statement about any spectrometer.

Safety: the e-stop and the safe-state action `x-cap.wasatchphotonics.laser_off.v1` both call the native
`set_laser_enable(False)` (`wasatch/FeatureIdentificationDevice.py:2504-2523`). No line of the clone documents an
independent hardware e-stop, so `estop_physical_ref` is not set; the safe-state action satisfies SAFE-045 for this R2
hardware driver. The clone's laser interlock is read by `can_laser_fire`, but this package does not expose an
interlock binding and does not claim one.

Spectrum data: the action returns every pixel the upstream `get_spectrum` returns (the real array is the detector's
pixel count) and the wavelength axis from the EEPROM wavecal coefficients. The fake returns eight pixels as test
data; the real length is not fixed by the class.

Tags: spectrometer, raman, spectrum, tec, laser
