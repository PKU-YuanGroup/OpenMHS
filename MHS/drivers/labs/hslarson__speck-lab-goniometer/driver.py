"""OpenMHS driver for gh.hslarson/speck-lab-goniometer: the Thorlabs compact spectrometer channel.

A direct Driver (decorated methods) over ``components.pyCCT.pyCCT:SpectrometerWrapper``, the upstream handle around
the Thorlabs Compact Spectrograph SDK driver (src/components/pyCCT/pyCCT.py:222-228).  The repository also contains
two Zaber stage wrappers, but a package has one ``native`` entry class and the catalogue classes for motion cannot be
bound to a spectrometer resource; this package therefore exposes only the spectrometer that supplies the goniometer
measurements.

* reads: the device id, the manual exposure, the hardware-average frame count, the three input-trigger settings, the
  output-trigger delay and the amplitude-correction flag;
* writes: those settings.  No line of the clone states a numeric range for any of them, so each numeric write and the
  action's wavelength range are ``Limit.operator_required``: they are refused with ``MHS.SAFETY.LIMITS_UNSET`` until
  the site overlay supplies the limits of its unit (``site-limits.example.json`` shows an example overlay);
* action: ``cap.measure.spectrum.v1`` acquires one spectrum and returns the part of the detector axis inside the
  requested wavelength range;
* safety: the e-stop closes the mechanical shutter with the native ``set_shutter(False)`` (src/components/pyCCT/
  pyCCT.py:306-325), the declared safe state.

The fake returns 64 points as test data.  The clone does not state the detector pixel count, so the real array length
is not named here.  Every Fact cites a line of the clone at the pinned commit
9ca84d8c8c6c6ec9f9f3a3bd3cd968fc6657a803.  This package is model-authored and unreviewed, it is checked on the fake
backend only, and no hardware run was made.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write


def _require(applied, what):
    """Turn an upstream ``bool`` return into a typed failure when the device reported that it did not apply it."""
    if not applied:
        raise DriverFailed("MHS.DEVICE.FAULTED", f"{what} returned False")
    return applied


class SpeckLabSpectrometer(Driver):
    device_id = "speck-spectrometer"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = "components.pyCCT.pyCCT:SpectrometerWrapper"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeSpectrometerWrapper"}
    vendor, model = "Thorlabs", "Compact Spectrograph SDK (pyCCT SpectrometerWrapper)"
    display_name = "Thorlabs compact spectrometer (pyCCT SpectrometerWrapper)"
    tags = ["spectrometer", "spectrum", "thorlabs", "pycct", "goniometer"]
    facts = [
        Fact("SpectrometerWrapper is the upstream handle around the Compact Spectrometer SDK instance and stores it "
             "in self.spectrometer", source="upstream_code", ref="src/components/pyCCT/pyCCT.py:222-228"),
        Fact("get_device_id returns the SDK DeviceId string", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:236-240"),
        Fact("set_manual_exposure takes an exposure time in milliseconds and returns the result of "
             "SetManualExposureAsync", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:242-255"),
        Fact("get_manual_exposure returns ManualExposure rounded to 2 decimals", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:260-264"),
        Fact("set_hardware_average takes a frame count and returns the result of SetHwAverageAsync",
             source="upstream_code", ref="src/components/pyCCT/pyCCT.py:266-279"),
        Fact("get_hardware_average returns HwAverage as an int", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:284-288"),
        Fact("acquire_single_spectrum returns wavelength and intensity lists, SensorExposureMs rounded to 2 decimals, "
             "and HardwareAverage", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:290-304"),
        Fact("set_shutter passes open_position to SetShutterAsync, waits 0.04 s, and returns its result",
             source="upstream_code", ref="src/components/pyCCT/pyCCT.py:306-325"),
        Fact("set_input_hw_trigger takes enabled, ave_no_wait and slope_falling_edge flags and returns the result of "
             "SetInputHwTriggerAsync", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:345-364"),
        Fact("get_input_hw_trigger_state returns HwTriggerIn, HwTriggerInAveNoWait and HwTriggerInSlope",
             source="upstream_code", ref="src/components/pyCCT/pyCCT.py:366-370"),
        Fact("set_output_hw_trigger_delay takes a delay in milliseconds; the docstring says a negative value "
             "schedules acquisition start after the output trigger", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:372-388"),
        Fact("get_output_hw_trigger_delay returns HwTriggerOutDelayMs rounded to 2 decimals", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:393-397"),
        Fact("get_use_amplitude_correction returns UseAmplitudeCorrection", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:399-403"),
        Fact("set_use_amplitude_correction assigns state to UseAmplitudeCorrection", source="upstream_code",
             ref="src/components/pyCCT/pyCCT.py:405-409"),
        Fact("PyCCT.discover_devices returns the known device connection keys or an empty list",
             source="upstream_code", ref="src/components/pyCCT/pyCCT.py:91-118"),
        Fact("PyCCT.connect_to_device returns a SpectrometerWrapper around GetCompactSpectrographById or None",
             source="upstream_code", ref="src/components/pyCCT/pyCCT.py:120-136"),
    ]
    safe_state = "shutter closed (the native set_shutter(False))"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("device_id", type="string", description="Device id reported by the Compact Spectrometer SDK")
    def read_device_id(self):
        return self.native.get_device_id()

    @read("manual_exposure", unit="ms", description="Manual exposure time in milliseconds")
    def read_manual_exposure(self):
        return self.native.get_manual_exposure()

    @read("hardware_average", type="integer", unit="1",
          description="Number of frames the spectrometer averages in hardware")
    def read_hardware_average(self):
        return self.native.get_hardware_average()

    @read("input_hw_trigger_enabled", type="boolean",
          description="True while the input hardware trigger is enabled; false for free running")
    def read_input_hw_trigger_enabled(self):
        return self.native.get_input_hw_trigger_state()[0]

    @read("input_hw_trigger_average_no_wait", type="boolean",
          description="True when one trigger event starts immediate averaging; false when every frame needs a trigger")
    def read_input_hw_trigger_average_no_wait(self):
        return self.native.get_input_hw_trigger_state()[1]

    @read("input_hw_trigger_falling_edge", type="boolean",
          description="True for a falling-edge input trigger; false for a rising edge")
    def read_input_hw_trigger_falling_edge(self):
        return self.native.get_input_hw_trigger_state()[2]

    @read("output_hw_trigger_delay", unit="ms",
          description="Delay of the output hardware trigger in milliseconds; a negative value schedules the "
                      "acquisition after the trigger")
    def read_output_hw_trigger_delay(self):
        return self.native.get_output_hw_trigger_delay()

    @read("use_amplitude_correction", type="boolean",
          description="True while the SDK applies its amplitude correction")
    def read_use_amplitude_correction(self):
        return self.native.get_use_amplitude_correction()

    # -- writes -------------------------------------------------------------------------------------------------
    @write("manual_exposure", unit="ms", description="Manual exposure time in milliseconds",
           limit=Limit.operator_required(
               "the clone names milliseconds as the unit of the exposure time "
               "(src/components/pyCCT/pyCCT.py:247) but states no minimum or maximum; the site supplies the range "
               "of its spectrometer"))
    def set_manual_exposure(self, value):
        _require(self.native.set_manual_exposure(value), "set_manual_exposure")
        return self.native.get_manual_exposure()

    @write("hardware_average", type="integer", unit="1",
           description="Number of frames the spectrometer averages in hardware",
           limit=Limit.operator_required(
               "the clone names frames as the unit of the hardware average "
               "(src/components/pyCCT/pyCCT.py:268-270) but states no minimum or maximum; the site supplies the "
               "range of its spectrometer"))
    def set_hardware_average(self, value):
        _require(self.native.set_hardware_average(value), "set_hardware_average")
        return self.native.get_hardware_average()

    def _set_trigger(self, position, value):
        current = list(self.native.get_input_hw_trigger_state())
        if len(current) != 3 or any(item is None for item in current):
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "the spectrometer did not report all three input-trigger settings")
        current[position] = bool(value)
        _require(self.native.set_input_hw_trigger(enabled=current[0], ave_no_wait=current[1],
                                                  slope_falling_edge=current[2]),
                 "set_input_hw_trigger")
        return bool(value)

    @write("input_hw_trigger_enabled", type="boolean",
           description="Enable the input hardware trigger; false selects free running")
    def set_input_hw_trigger_enabled(self, value):
        return self._set_trigger(0, value)

    @write("input_hw_trigger_average_no_wait", type="boolean",
           description="Average immediately on one trigger event instead of requiring a trigger for every frame")
    def set_input_hw_trigger_average_no_wait(self, value):
        return self._set_trigger(1, value)

    @write("input_hw_trigger_falling_edge", type="boolean",
           description="Use the falling edge of the input trigger instead of the rising edge")
    def set_input_hw_trigger_falling_edge(self, value):
        return self._set_trigger(2, value)

    @write("output_hw_trigger_delay", unit="ms",
           description="Delay of the output hardware trigger in milliseconds; a negative value schedules the "
                       "acquisition after the trigger",
           limit=Limit.operator_required(
               "the clone names milliseconds as the unit of the output-trigger delay "
               "(src/components/pyCCT/pyCCT.py:380) and permits negative values "
               "(src/components/pyCCT/pyCCT.py:377), but states no minimum or maximum; the site supplies the range"))
    def set_output_hw_trigger_delay(self, value):
        _require(self.native.set_output_hw_trigger_delay(value), "set_output_hw_trigger_delay")
        return self.native.get_output_hw_trigger_delay()

    @write("use_amplitude_correction", type="boolean",
           description="Apply the SDK amplitude correction")
    def set_use_amplitude_correction(self, value):
        self.native.set_use_amplitude_correction(value)
        return self.native.get_use_amplitude_correction()

    # -- action -------------------------------------------------------------------------------------------------
    @action(cap="cap.measure.spectrum.v1",
            description="Acquire one spectrum and return the detector samples inside the requested wavelength range",
            input={
                "wavelength_min": Field(
                    "number", unit="nm", description="Lower bound of the returned wavelength range",
                    limit=Limit.operator_required(
                        "no line of the clone states the wavelength range of the detector; the site supplies the "
                        "range it will allow for its spectrometer")),
                "wavelength_max": Field(
                    "number", unit="nm", description="Upper bound of the returned wavelength range",
                    limit=Limit.operator_required(
                        "no line of the clone states the wavelength range of the detector; the site supplies the "
                        "range it will allow for its spectrometer")),
            })
    def acquire_spectrum(self, wavelength_min, wavelength_max):
        wavelengths, intensities, _exposure_ms, _average = self.native.acquire_single_spectrum()
        if wavelengths is None or intensities is None:
            raise DriverFailed("MHS.DEVICE.FAULTED", "acquire_single_spectrum returned no spectrum")
        if len(wavelengths) != len(intensities):
            raise DriverFailed("MHS.DEVICE.FAULTED", "the spectrum's wavelength and intensity arrays differ in length")
        pairs = [(float(wavelength), float(intensity))
                 for wavelength, intensity in zip(wavelengths, intensities)
                 if float(wavelength_min) <= float(wavelength) <= float(wavelength_max)]
        return {"wavelengths": [item[0] for item in pairs],
                "intensities": [item[1] for item in pairs]}

    # -- safety -------------------------------------------------------------------------------------------------
    @estop(native="set_shutter")
    def emergency_stop(self):
        """Close the native mechanical shutter; the runtime latches the e-stop before this method runs."""
        _require(self.native.set_shutter(False), "set_shutter(False)")
