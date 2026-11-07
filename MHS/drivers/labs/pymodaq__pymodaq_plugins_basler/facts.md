# Facts and tags for gh.pymodaq/pymodaq_plugins_basler

Every fact cites its source at commit `2bb80b0f2f1f904675065ff432302b885389ee99`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BaslerCamera is the PyMoDAQ plugin's camera class and wraps one pylon.InstantCamera | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:41-57 |
| open() attaches the pylon device, opens it and reads the per-model attribute configuration | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:91-102 |
| get_roi returns x0, x0+width, y0, y0+height, xbin and ybin from the pylon OffsetX, Width, OffsetY, Height, BinningHorizontal and BinningVertical nodes | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:141-149 |
| set_roi clamps the start and end coordinates to the detector size, aligns each start to Width.Inc and writes OffsetX, Width, OffsetY, Height, BinningHorizontal and BinningVertical | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:151-167 |
| detector_clamp bounds a coordinate to 0 and the detector extent | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:543-545 |
| get_detector_size returns the SensorWidth and SensorHeight pylon nodes in pixels | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:169-171 |
| start_grabbing writes AcquisitionFrameRate when a rate is given and starts grabbing with GrabStrategy_LatestImageOnly; stop_grabbing calls StopGrabbing | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:193-209 |
| check_attribute_names looks for ExposureTime, ExposureTimeAbs or ExposureTimeRaw and for Gain, GainRaw or GainAll | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:267-296 |
| close closes and detaches the pylon camera | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:189-191 |
| list_cameras enumerates the pylon devices from the transport-layer factory | upstream_code | src/pymodaq_plugins_basler/hardware/basler.py:120-124 |
| The DAQ viewer writes an exposure setting to the pylon node as int(value * 1e3), milliseconds to microseconds | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:185-190 |
| The DAQ viewer reads an exposure value from the pylon node in microseconds and multiplies it by 1e-3 for the GUI | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:564-579 |
| The DAQ viewer reads the pylon node minimum and maximum with GetMin() and GetMax(), so the usable range is reported by the camera at run time | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:571-582 |
| The DAQ viewer changes the ROI through set_roi with hstart, hend=hstart+width, vstart, vend=vstart+height and the two binning factors | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:322-331 |
| The DAQ viewer calls setup_acquisition when the camera is initialised | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:86-91 |
| The DAQ viewer starts grabbing with the configured frame rate or with None when the model has no frame-rate parameter | upstream_code | src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:338-346 |
| The README says the plugin handles gain, exposure and ROI and uses the pypylon library | vendor_doc | README.rst:17 |
| The README names the acA640-120gm, acA1920-40gm and puA1600-60um models as those the plugin was tested with | vendor_doc | README.rst:21 |
| The README says the config file names are pylon API feature names such as ExposureTime or GainRaw and that a config file is needed per camera model | vendor_doc | README.rst:23-26 |

Limits: the six ROI values (`roi_x0`, `roi_x1`, `roi_y0`, `roi_y1`, `binning_x`, `binning_y`) are
`Limit.operator_required`. No text file of the clone states the usable ROI range of an installed camera: the pylon
nodes report their minimum and maximum only at run time (`daq_2Dviewer_Basler.py:571-582`), the sensor size differs
by model (`README.rst:21`), and the site supplies the range of its camera. Until then every ROI write is refused
`MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` supplies placeholder example ranges only; it is not a
measurement or a statement about any installed camera.

Safety: the e-stop and the safe-state action `x-cap.pymodaq.stop_grabbing.v1` both call the native
`stop_grabbing()` (`StopGrabbing`, `hardware/basler.py:207-209`). No line of the clone documents an independent
hardware e-stop, so `estop_physical_ref` is not set. At R1 the gate requires the e-stop and a safe state; the
safe-state action also provides the independent stop path that SAFE-045 requires at R2 and R3. The loader's R2/R3
refusal of an unreviewed model-written hardware backend does not cover this R1 package, and this package makes no
hardware-run claim.

Not covered: the image arrays from `on_image_grabbed`/the DAQ viewer. The standard's image form is an artifact
reference and this package has no artifact store. Exposure and gain are read-only because `BaslerCamera` has no
setter method for them; the DAQ viewer writes the pylon nodes directly (`daq_2Dviewer_Basler.py:243-245`).

Tags: camera, basler, pypylon, imaging, roi
