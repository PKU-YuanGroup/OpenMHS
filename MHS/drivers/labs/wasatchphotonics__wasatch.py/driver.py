"""OpenMHS driver for gh.wasatchphotonics/wasatch.py: a Wasatch Photonics FID spectrometer.

A direct Driver (decorated methods) over the upstream class
``wasatch.FeatureIdentificationDevice:FeatureIdentificationDevice``, the basic
implementation of the Wasatch Feature Identification Device USB API
(wasatch/FeatureIdentificationDevice.py:41-47).

* reads: the integration time, the detector temperature, the detector TEC
  enable state and set point, the ambient temperature, and the laser enable
  state;
* one write: the integration time.  The minimum and maximum integration time
  are EEPROM fields of each unit (wasatch/EEPROM.py:105-106), so the limit is
  ``Limit.operator_required``: every write is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its unit
  (``site-limits.example.json`` shows the overlay);
* actions: one spectrum acquisition (an extension with an inline output
  schema) and the safe-state action that disables the laser;
* the native laser disable (``set_laser_enable(False)``) is both the e-stop
  and the safe-state action.

The spectrum action returns the pixel intensities of the upstream
``get_spectrum`` and the wavelength axis generated from the EEPROM wavecal
coefficients.  The fake returns a small array; the real length is the
detector's pixel count (see RESULT.json).

Every Fact cites a line of the clone at the pinned commit
c3ea52bde83d9d004d0b97850f09515dfc42f741.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


def _data(response, label):
    """The ``data`` of an upstream SpectrometerResponse, or a typed failure."""
    if response is None:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{label} returned no response")
    value = getattr(response, "data", None)
    if value is None:
        error = getattr(response, "error_msg", None) or "no data"
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{label} returned no data ({error})",
                           native_code=error)
    return value


class WasatchSpectrometer(Driver):
    device_id = "wasatch"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R2"
    native = "wasatch.FeatureIdentificationDevice:FeatureIdentificationDevice"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeWasatchSpectrometer"}
    vendor = "Wasatch Photonics"
    model = "FeatureIdentificationDevice (FID) spectrometer"
    display_name = "Wasatch Photonics FID spectrometer (wasatch.FeatureIdentificationDevice)"
    tags = ["spectrometer", "raman", "spectrum", "tec", "laser"]
    facts = [
        Fact("FeatureIdentificationDevice is the basic implementation of the Wasatch FID spectrometer USB API "
             "defined in ENG-0001", source="upstream_code", ref="wasatch/FeatureIdentificationDevice.py:41-47"),
        Fact("get_integration_time_ms reads GET_INTEGRATION_TIME_MS and returns the value in milliseconds",
             source="upstream_code", ref="wasatch/FeatureIdentificationDevice.py:937-947"),
        Fact("set_integration_time_ms rounds to an integer millisecond value, sends SET_INTEGRATION_TIME_MS "
             "(0xB2) and stores the session value", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:1687-1713"),
        Fact("The minimum and maximum integration time are EEPROM fields of each unit, not constants of the "
             "class", source="upstream_code", ref="wasatch/EEPROM.py:105-106"),
        Fact("get_spectrum returns the acquired pixel intensities as response.data", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:1652-1653"),
        Fact("The wavelength axis is generated from the EEPROM wavelength calibration coefficients",
             source="upstream_code", ref="wasatch/SpectrometerSettings.py:325"),
        Fact("get_laser_enabled reports the laser enable state", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:2482-2502"),
        Fact("set_laser_enable turns the laser on or off and false turns it off", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:2504-2523"),
        Fact("The laser_enable setting is documented as turning the laser on or off", source="vendor_doc",
             ref="README_SETTINGS.md:113-114"),
        Fact("get_detector_temperature_degC converts the detector temperature reading to degrees Celsius",
             source="upstream_code", ref="wasatch/FeatureIdentificationDevice.py:2279-2290"),
        Fact("get_detector_tec_setpoint_degC reports the applied detector TEC set point in degrees Celsius",
             source="upstream_code", ref="wasatch/FeatureIdentificationDevice.py:2325-2329"),
        Fact("get_tec_enabled reads the detector TEC enable state", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:3483-3491"),
        Fact("get_ambient_temperature_degC reports the ambient temperature on XS and Gen 1.5 spectrometers",
             source="upstream_code", ref="wasatch/FeatureIdentificationDevice.py:3416-3423"),
        Fact("disconnect disables the laser if it was enabled and releases the interface", source="upstream_code",
             ref="wasatch/FeatureIdentificationDevice.py:453-474"),
    ]
    safe_state = "laser disabled (the native set_laser_enable(False))"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("integration_time_ms", type="integer", unit="ms",
          description="Integration time in milliseconds reported by the spectrometer")
    def integration_time_ms(self):
        return _data(self.native.get_integration_time_ms(), "get_integration_time_ms")

    @read("detector_temperature_degC", unit="Cel", description="Detector temperature")
    def detector_temperature_degC(self):
        return _data(self.native.get_detector_temperature_degC(), "get_detector_temperature_degC")

    @read("detector_tec_setpoint_degC", unit="Cel", description="Applied detector TEC set point")
    def detector_tec_setpoint_degC(self):
        return _data(self.native.get_detector_tec_setpoint_degC(), "get_detector_tec_setpoint_degC")

    @read("tec_enabled", type="boolean", description="True while the detector TEC is enabled")
    def tec_enabled(self):
        return _data(self.native.get_tec_enabled(), "get_tec_enabled")

    @read("ambient_temperature_degC", unit="Cel",
          description="Ambient temperature (available on XS and Gen 1.5 spectrometers)")
    def ambient_temperature_degC(self):
        response = self.native.get_ambient_temperature_degC()
        if response is None:
            return None                     # unsupported on this model; the runtime omits it from the state
        return _data(response, "get_ambient_temperature_degC")

    @read("laser_enabled", type="boolean", description="True while the laser is enabled")
    def laser_enabled(self):
        return _data(self.native.get_laser_enabled(), "get_laser_enabled")

    # -- the one write ------------------------------------------------------------------------------------------
    @write("integration_time_ms", type="integer", unit="ms",
           description="Integration time in milliseconds",
           limit=Limit.operator_required(
               "the minimum and maximum integration time are EEPROM fields of each unit "
               "(wasatch/EEPROM.py:105-106), so no text states one range for all units; the site sets the "
               "range of its unit"))
    def set_integration_time_ms(self, value):
        self.native.set_integration_time_ms(value)
        return _data(self.native.get_integration_time_ms(), "get_integration_time_ms")

    # -- actions --------------------------------------------------------------------------------------------------
    @action(name="x-cap.wasatchphotonics.acquire_spectrum.v1",
            description="Acquire one spectrum with the current integration time",
            output={
                "wavelengths": Field("array",
                                     items=Field("number", unit="nm", description="Wavelength of the pixel"),
                                     description="Wavelength axis from the EEPROM wavelength calibration"),
                "intensities": Field("array",
                                     items=Field("number", unit="1", description="Raw pixel intensity"),
                                     description="Pixel intensities returned by get_spectrum"),
            })
    def acquire_spectrum(self):
        intensities = _data(self.native.get_spectrum(), "get_spectrum")
        wavelengths = self.native.settings.wavelengths
        if wavelengths is None or len(wavelengths) != len(intensities):
            raise DriverFailed("MHS.DEVICE.FAULTED",
                               "the wavelength axis does not match the acquired spectrum")
        return {"wavelengths": [float(value) for value in wavelengths],
                "intensities": [float(value) for value in intensities]}

    @action(name="x-cap.wasatchphotonics.laser_off.v1", safe_state=True,
            description="Disable the laser (the safe state); it takes no input",
            output={"laser_enabled": Field("boolean", description="False once the laser is disabled")})
    def laser_off(self):
        self.native.set_laser_enable(False)
        return {"laser_enabled": _data(self.native.get_laser_enabled(), "get_laser_enabled")}

    # -- safety -------------------------------------------------------------------------------------------------------
    @estop(native="set_laser_enable")
    def stop(self):
        """The native laser disable: the runtime latches first, then turns the laser off."""
        self.native.set_laser_enable(False)

    def teardown(self):
        self.native.disconnect()            # wasatch/FeatureIdentificationDevice.py:453-474
