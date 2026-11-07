# Facts and tags for pymodaq/pymodaq_plugins_oceaninsight

Every fact cites its source at commit `298f768a2f2c5643a45e61f416300b3805b8c893`; the same facts are written into
`driver.py` (`facts = [...]`) and the reference file is generated from the driver, not from this page.  The clone is a
src-layout repository, so the plugin path keeps its `src/` prefix.

| fact | source | ref |
|---|---|---|
| DAQ_1DViewer_Omnidriver is the PyMoDAQ viewer plugin that controls Ocean Insight spectrometers through the OmniDriver NETWrapper | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:26-30 |
| The plugin discovers every connected spectrometer with NETWrapper.openAllSpectrometers, reads its name with getName and keeps the names and ids of the discovered devices | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:79-91 |
| get_xaxis(ind_spectro) reads the calibrated wavelengths from controller.getWavelengths and returns them as an array | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:130-134 |
| The millisecond exposure setting is multiplied by 1000 before setIntegrationTime and divided by 1000 after getIntegrationTime, so the controller integration time is in microseconds | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:62-66 |
| The plugin reads getMaximumIntegrationTime and getMinimumIntegrationTime for every discovered spectrometer at initialization | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:93-95 |
| The exposure-time parameter bounds are the device values divided by 1000 and cast to int, so they are read from the device at runtime | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:110-111 |
| The plugin keeps each spectrometer's exposure_time child in self.settings, the Parameter tree of its base class, and commit_settings reads the changed parameter back | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:103-111 |
| grab_data sets the hardware averaging with setScansToAverage, reads the spectrum with getSpectrum and emits it in a DataToExport | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:142-162 |
| The emitted wavelength axis is the get_xaxis vector in nanometres multiplied by 1e-9, and the axis is labelled in metres | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:153-159 |
| stop calls controller.stopAveraging for every discovered spectrometer | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:168-173 |
| close calls controller.closeAllSpectrometers | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:136-140 |
| The OmniDriver wrapper is imported through pythonnet/clr only when omnidriver_path is configured; otherwise the module global omnidriver stays None | upstream_code | src/pymodaq_plugins_oceaninsight/daq_viewer_plugins/plugins_1D/daq_1Dviewer_Omnidriver.py:16-23 |

## What the driver exposes

* reads: `wavelength_min_nm`, `wavelength_max_nm`, `pixel_count` and `integration_time_ms` (the controller reports
  microseconds and the upstream converts them to milliseconds, :62-66);
* one write: `integration_time_ms`, applied through the plugin's own `commit_settings` exposure-time path (:59-66),
  which calls `controller.setIntegrationTime` with the milliseconds multiplied by 1000; the driver sets the
  per-spectrometer `exposure_time` parameter of the plugin's settings tree (:103-114) before calling the hook;
* `cap.measure.intensity.v1`: the intensity of the detector pixel nearest to a declared wavelength, or of the
  brightest pixel when no wavelength is declared.  The full spectrum is emitted by the plugin as a `DataToExport`
  array (:142-162); it is NOT COVERED by the standard, and the driver never returns it.
* the native stop `stop()` (:168-173) is the e-stop and the declared safe state.

## Limits

Two operator-required bounds, both filled by one site overlay:

* `wavelength_nm`: no text of the clone states a wavelength range, because the axis is the detector calibration
  returned at runtime (:130-134) and the discovered spectrometers are model-specific;
* `integration_time_ms`: the plugin builds the exposure bounds from the device's own
  `getMinimumIntegrationTime`/`getMaximumIntegrationTime` values at initialization (:93-95, :110-111), so no line of
  the clone states one range for a generic spectrometer.

`site-limits.example.json` is an example overlay for one bench, not a statement about any unit.

## Safety

The device is a passive optical measurement: it emits no light and actuates nothing.  The read-only part alone would
be R0, but the writable configuration binding carries the catalogue's R1 floor (`cap.device.configure.v1`), so the
device is declared R1.  The native stop stops the hardware averaging on every discovered spectrometer (:168-173); it
is declared as an `@estop`, so the runtime latches before calling it and the e-stop receipt reports the safe state as
achieved.  No independent hardware e-stop is claimed and none is cited (SAFE-045 applies at R2 and above).

## Tags

`spectrometer, ocean-insight, ocean-optics, omnidriver, pymodaq, spectroscopy`
