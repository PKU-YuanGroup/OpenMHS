# Facts and tags for gh.pymodaq/pymodaq_plugins_andor

Every fact cites its source at commit `673a12ae4e9eaf13ed58ce7412d180002386fd5c`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone, or a PDF page as
`docs/manual.pdf:PAGE`).  The same facts are written into `driver.py` (`facts = [...]`); the reference
file is generated from the driver, not from this page.  Paths keep the clone's `src/` layout.

| fact | source | ref |
|---|---|---|
| SetIntegTime takes milliseconds, writes iTime * 1e-3 to ExposureTime, and GetIntegTime returns ExposureTime.getValue() * 1000 | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:125-132 |
| GetCCDWidth/GetCCDHeight return SensorWidth/SensorHeight and GetPicWidth/GetPicHeight the AOIWidth/AOIHeight | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:134-151 |
| GetSerialNumber returns SerialNumber.getValue() | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:122-123 |
| GetFPS returns FrameRate.getValue() | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:194-195 |
| SensorTemperature, SensorCooling, FrameRate and ActualExposureTime are SDK3 camera attributes created in AndorBase.__init__ | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:78-81 |
| AndorCamera adds Overlap, TemperatureControl, TemperatureStatus and ActualExposureTime to the AndorBase attributes | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:234-249 |
| TemperatureControl and TemperatureStatus are ATEnum properties; ATEnum.getString returns the current symbol | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/sdk3cam.py:96-106 |
| StopAq calls AcquisitionStop() only when CameraAcquiring is true | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:161-163 |
| The SCMOS viewer reads SensorTemperature.getValue() into the current temperature display and FrameRate.getValue() for the frame rate | upstream_code | src/pymodaq_plugins_andor/daq_viewer_plugins/plugins_2D/daq_2Dviewer_AndorSCMOS.py:435-441 |
| The SDK2 camera wrapper documents GetTemperature/GetTemperatureRange in degrees Celcius | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk2/sdk2.py:304-324 |
| The camera image is returned by get_image_fom_buffer(Ny, Nx, buffer) as a uint16 array | upstream_code | src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:107-116 |

Limits: the integration time is `Limit.operator_required`.  The clone has no text that states an
exposure range: `ExposureTime.min()/max()` are read from the SDK at run time
(`daq_2Dviewer_AndorSCMOS.py:462-463`), and the constructor defaults of the upstream class are not a
device bound.  The operator supplies the range of the camera in `site-limits.json`;
`site-limits.example.json` is an example only, not a statement about any camera.

Safety: the native stop is `StopAq`, which sends `AcquisitionStop` when `CameraAcquiring` is true
(`api.py:161-163`).  It is the `@estop` and defines the safe state (acquisition stopped; the sensor
cooler is left as it is).  The package is R1, so no independent hardware e-stop is claimed and none is
documented in the clone.

Not covered by this package: the image array from `get_image_fom_buffer` (`api.py:107-116`).  The
scalar camera state and settings are served instead.

Tags: camera, ccd, scmos, andor, sdk3
