"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_oceaninsight: an Ocean Insight spectrometer through its PyMoDAQ plugin.

A direct Driver (decorated methods) over the card's entry class
``pymodaq_plugins_oceaninsight.daq_viewer_plugins.plugins_1D.daq_1Dviewer_Omnidriver:DAQ_1DViewer_Omnidriver``
(src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:26).  The upstream class is a
PyMoDAQ 1D viewer plugin: it owns an OmniDriver ``NETWrapper`` as ``self.controller`` (:54-56, :79), reads the calibrated
wavelength axis through ``get_xaxis`` (:130-134), and stops the averaging of every spectrometer through ``stop``
(:168-173).  A command table cannot express this object (the driver has to pick the detector pixel nearest a
wavelength out of the returned axis and the spectrum), so this is a direct Driver; the card's ``decision`` is already
``direct-driver``.

* reads: the calibrated wavelength range of the spectrometer, its pixel count, and the integration time the
  controller reports in microseconds, published in milliseconds;
* one write: the same integration time, set through the plugin's own ``commit_settings`` exposure-time path
  (:59-66).  The value is milliseconds, which the plugin converts to the microseconds the controller takes;
* ``cap.measure.intensity.v1`` (the class verb is read): the intensity of the detector pixel whose calibrated
  wavelength is nearest to a declared wavelength, or the intensity of the brightest pixel when none is declared, in
  the arbitrary intensity units of the detector (:151).  The upstream plugin emits the whole spectrum as a
  ``DataToExport`` (:162); this package does not return that array, because the standard has no artifact transport
  for it, and the array is named NOT COVERED in RESULT.json;
* ``wavelength_nm`` is ``Limit.operator_required``: no text of the clone states a wavelength range.  The axis is read
  from the detector calibration at runtime (:130-134), so the site supplies the range of its spectrometer
  (site-limits.example.json shows the overlay) and every call carrying the field is refused
  ``MHS.SAFETY.LIMITS_UNSET`` until it does;
* the integration time is also ``Limit.operator_required``: the plugin builds its exposure bounds from the device's
  own ``getMinimumIntegrationTime``/``getMaximumIntegrationTime`` at runtime (:93-95, :110-111), so no line of the
  clone states one range for a generic spectrometer; the site supplies it in the same overlay;
* the native stop ``stop()`` (:168-173) is the e-stop.  The device only measures light, but the writable configure
  binding carries the catalogue's R1 floor (cap.device.configure.v1), so the device is declared R1; no independent
  hardware e-stop is claimed and none is cited.

Every Fact cites a line of the clone at the pinned commit 298f768a2f2c5643a45e61f416300b3805b8c893.  The MHS
resource is the first discovered spectrometer (index 0): the plugin can discover several (:79-91), and this package
does not expose the others.  This package is model-authored and unreviewed: it is checked on the fake backend only,
no hardware was attached, and the hardware factory in native.py never ran.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

#: The upstream plugin module whose class this package drives (a src-layout clone).
PLUGIN = "src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py"

#: Why the site must state the wavelength range: the detector calibration is read at runtime.
WAVELENGTH_REASON = (
    "no text of the clone states a wavelength range for the detector: the axis is the calibrated wavelength vector "
    "the controller returns at runtime (get_xaxis reading controller.getWavelengths, "
    "src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:130-134), and the "
    "spectrometers the plugin discovers are model-specific; the site states the range of its spectrometer")
INTEGRATION_REASON = (
    "no text of the clone states one integration time range for a generic spectrometer: the plugin reads "
    "getMinimumIntegrationTime and getMaximumIntegrationTime from the discovered device at initialization "
    "(src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:93-95) and builds the "
    "exposure-time bounds from those device values divided by 1000 (...:110-111); the site states the range of its "
    "spectrometer")


class OmnidriverSpectrometer(Driver):
    device_id = "oceaninsight-omnidriver"
    device_kind = "instrument.spectrometer"
    mode = "hardware"
    risk = "R1"
    native = ("pymodaq_plugins_oceaninsight.daq_viewer_plugins.plugins_1D.daq_1Dviewer_Omnidriver:"
              "DAQ_1DViewer_Omnidriver")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeOmnidriver"}
    vendor, model = "Ocean Insight", "OmniDriver NETWrapper spectrometer (PyMoDAQ plugin)"
    display_name = "Ocean Insight spectrometer (PyMoDAQ Omnidriver plugin)"
    tags = ["spectrometer", "ocean-insight", "ocean-optics", "omnidriver", "pymodaq", "spectroscopy"]
    facts = [
        Fact("DAQ_1DViewer_Omnidriver is the PyMoDAQ viewer plugin that controls Ocean Insight spectrometers through "
             "the OmniDriver NETWrapper", source="upstream_code", ref=f"{PLUGIN}:26-30"),
        Fact("The plugin discovers every connected spectrometer with NETWrapper.openAllSpectrometers, reads its name "
             "with getName and keeps the names and ids of the discovered devices", source="upstream_code",
             ref=f"{PLUGIN}:79-91"),
        Fact("get_xaxis(ind_spectro) reads the calibrated wavelengths from controller.getWavelengths and returns them "
             "as an array", source="upstream_code", ref=f"{PLUGIN}:130-134"),
        Fact("The millisecond exposure setting is multiplied by 1000 before setIntegrationTime and divided by 1000 "
             "after getIntegrationTime, so the controller integration time is in microseconds", source="upstream_code",
             ref=f"{PLUGIN}:62-66"),
        Fact("The plugin reads getMaximumIntegrationTime and getMinimumIntegrationTime for every discovered "
             "spectrometer at initialization", source="upstream_code", ref=f"{PLUGIN}:93-95"),
        Fact("The exposure-time parameter bounds are the device values divided by 1000 and cast to int, so they are "
             "read from the device at runtime", source="upstream_code", ref=f"{PLUGIN}:110-111"),
        Fact("The plugin keeps each spectrometer's exposure_time child in self.settings, the Parameter tree of its "
             "base class, and commit_settings reads the changed parameter back", source="upstream_code",
             ref=f"{PLUGIN}:103-111"),
        Fact("grab_data sets the hardware averaging with setScansToAverage, reads the spectrum with getSpectrum and "
             "emits it in a DataToExport", source="upstream_code", ref=f"{PLUGIN}:142-162"),
        Fact("The emitted wavelength axis is the get_xaxis vector in nanometres multiplied by 1e-9, and the axis is "
             "labelled in metres", source="upstream_code", ref=f"{PLUGIN}:153-159"),
        Fact("stop calls controller.stopAveraging for every discovered spectrometer", source="upstream_code",
             ref=f"{PLUGIN}:168-173"),
        Fact("close calls controller.closeAllSpectrometers", source="upstream_code", ref=f"{PLUGIN}:136-140"),
        Fact("The OmniDriver wrapper is imported through pythonnet/clr only when omnidriver_path is configured; "
             "otherwise the module global omnidriver stays None", source="upstream_code", ref=f"{PLUGIN}:16-23"),
    ]
    safe_state = ("acquisition stopped: the hardware averaging is stopped on every discovered spectrometer "
                  "(the native stop)")

    # -- reads ----------------------------------------------------------------------------------------------------
    @read("wavelength_min_nm", unit="nm",
          description="Calibrated wavelength of the detector pixel with the shortest wavelength")
    def wavelength_min_nm(self):
        return float(min(self.native.get_xaxis(0)))

    @read("wavelength_max_nm", unit="nm",
          description="Calibrated wavelength of the detector pixel with the longest wavelength")
    def wavelength_max_nm(self):
        return float(max(self.native.get_xaxis(0)))

    @read("pixel_count", type="integer", unit="1",
          description="Number of detector pixels in the calibrated wavelength axis")
    def pixel_count(self):
        return int(len(self.native.get_xaxis(0)))

    @read("integration_time_ms", unit="ms",
          description="Integration time the controller reports for the spectrometer, converted from microseconds "
                      "to milliseconds")
    def integration_time_ms(self):
        return float(self.native.controller.getIntegrationTime(0)) / 1000.0

    @write("integration_time_ms", unit="ms",
           description="Integration time of the spectrometer in milliseconds; the plugin converts it to the "
                       "microseconds the controller takes",
           limit=Limit.operator_required(INTEGRATION_REASON))
    def set_integration_time(self, value):
        param = self.native.settings.child("spectrometers", "spectro0", "exposure_time")
        param.setValue(float(value))                   # the plugin reads param.value() in commit_settings
        self.native.commit_settings(param)             # upstream :59-66: setIntegrationTime and read back
        return float(self.native.controller.getIntegrationTime(0)) / 1000.0

    # -- measurement ----------------------------------------------------------------------------------------------
    @action(cap="cap.measure.intensity.v1",
            description="Measure the intensity of one detector pixel: the pixel whose calibrated wavelength is "
                        "nearest to the declared wavelength, or the brightest pixel when no wavelength is declared, "
                        "in the arbitrary intensity units of the detector. The plugin's full spectrum array is not "
                        "returned (the standard has no artifact transport for it)",
            input={"wavelength_nm": Field(
                "number", unit="nm",
                description="Wavelength in nanometres; the driver reads the detector pixel whose calibrated "
                            "wavelength is nearest to it. Leave it out to read the brightest pixel",
                limit=Limit.operator_required(WAVELENGTH_REASON))})
    def measure_intensity(self, wavelength_nm=None):
        wavelengths = [float(item) for item in self.native.get_xaxis(0)]
        spectrum = [float(item) for item in self.native.controller.getSpectrum(0)]
        count = min(len(wavelengths), len(spectrum))
        if count == 0:
            raise DriverFailed("MHS.DEVICE.NO_DATA", "the spectrometer returned no detector pixel")
        if wavelength_nm is None:
            index = max(range(count), key=lambda item: spectrum[item])
        else:
            target = float(wavelength_nm)
            index = min(range(count), key=lambda item: abs(wavelengths[item] - target))
        return {"intensity": spectrum[index]}

    # -- safety ---------------------------------------------------------------------------------------------------
    @estop(native="stop")
    def stop(self):
        """The native stop: the runtime latches first, then stops the averaging of every spectrometer."""
        self.native.stop()

    def teardown(self):
        self.native.close()
