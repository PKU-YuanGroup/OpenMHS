"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_andor: an Andor SDK3 camera.

A direct Driver (decorated methods) over the upstream camera class
``pymodaq_plugins_andor.hardware.andor_sdk3.api:AndorCamera``.  The upstream object owns the ctypes SDK3
camera and exposes its state through SDK3 attribute objects (``SensorWidth``, ``ExposureTime``,
``SensorTemperature``, ...) and through the getter methods of ``AndorBase``/``AndorCamera``
(``src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py``).  The read parameters below return scalar
values; the image array (``get_image_fom_buffer``) is not carried by this package (see RESULT.json).

* reads: sensor and active-ROI geometry, serial number, integration and actual exposure times, the
  sensor temperature, the cooler state, the temperature status and control symbols, the frame rate and
  the overlap flag;
* one write: the integration time in milliseconds, through ``SetIntegTime``.  No text of the clone
  states an exposure range (``ExposureTime.min()/max()`` are runtime values), so the bound is
  ``Limit.operator_required``: every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the operator
  supplies the range of the camera (``site-limits.example.json`` shows the overlay);
* the native stop is ``StopAq`` (``AcquisitionStop`` when ``CameraAcquiring`` is true): it is the
  ``@estop`` and the declared safe state.

Every Fact cites a line of the clone at the pinned commit
673a12ae4e9eaf13ed58ce7412d180002386fd5c.  This package is model-authored and unreviewed: it is checked
on the fake backend only and never on hardware.
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write


class AndorCamera(Driver):
    device_id = "andor_camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_andor.hardware.andor_sdk3.api:AndorCamera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeAndorCamera"}
    vendor, model = "Andor", "SDK3 camera (Neo / SCMOS family)"
    display_name = "Andor SDK3 camera (pymodaq_plugins_andor AndorCamera)"
    tags = ["camera", "ccd", "scmos", "andor", "sdk3"]
    facts = [
        Fact("SetIntegTime takes milliseconds, writes iTime * 1e-3 to ExposureTime, and GetIntegTime "
             "returns ExposureTime.getValue() * 1000", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:125-132"),
        Fact("GetCCDWidth/GetCCDHeight return SensorWidth/SensorHeight and GetPicWidth/GetPicHeight the "
             "AOIWidth/AOIHeight", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:134-151"),
        Fact("GetSerialNumber returns SerialNumber.getValue()", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:122-123"),
        Fact("GetFPS returns FrameRate.getValue()", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:194-195"),
        Fact("SensorTemperature, SensorCooling, FrameRate and ActualExposureTime are SDK3 camera "
             "attributes created in AndorBase.__init__", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:78-81"),
        Fact("AndorCamera adds Overlap, TemperatureControl, TemperatureStatus and ActualExposureTime to "
             "the AndorBase attributes", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:234-249"),
        Fact("TemperatureControl and TemperatureStatus are ATEnum properties; ATEnum.getString returns "
             "the current symbol", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/sdk3cam.py:96-106"),
        Fact("StopAq calls AcquisitionStop() only when CameraAcquiring is true", source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:161-163"),
        Fact("The SCMOS viewer reads SensorTemperature.getValue() into the current temperature display "
             "and FrameRate.getValue() for the frame rate", source="upstream_code",
             ref="src/pymodaq_plugins_andor/daq_viewer_plugins/plugins_2D/daq_2Dviewer_AndorSCMOS.py:435-441"),
        Fact("The SDK2 camera wrapper documents GetTemperature/GetTemperatureRange in degrees Celcius",
             source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk2/sdk2.py:304-324"),
        Fact("The camera image is returned by get_image_fom_buffer(Ny, Nx, buffer) as a uint16 array",
             source="upstream_code",
             ref="src/pymodaq_plugins_andor/hardware/andor_sdk3/api.py:107-116"),
    ]
    safe_state = "camera acquisition stopped by the native StopAq/AcquisitionStop; the sensor cooler is left as it is"

    # -- reads ------------------------------------------------------------------------------------------------
    @read("sensor_width", type="integer", unit="1", description="Physical sensor width in pixels")
    def sensor_width(self):
        return self.native.GetCCDWidth()

    @read("sensor_height", type="integer", unit="1", description="Physical sensor height in pixels")
    def sensor_height(self):
        return self.native.GetCCDHeight()

    @read("roi_width", type="integer", unit="1", description="Width in pixels of the active region of interest")
    def roi_width(self):
        return self.native.GetPicWidth()

    @read("roi_height", type="integer", unit="1", description="Height in pixels of the active region of interest")
    def roi_height(self):
        return self.native.GetPicHeight()

    @read("serial_number", type="string", description="Camera serial number reported by the SDK")
    def serial_number(self):
        return self.native.GetSerialNumber()

    @read("integration_time", unit="ms", description="Configured integration (exposure) time in milliseconds")
    def integration_time(self):
        return self.native.GetIntegTime()

    @read("actual_exposure_time", unit="s",
          description="Exposure time the SDK reports as actually applied, in seconds")
    def actual_exposure_time(self):
        return self.native.ActualExposureTime.getValue()

    @read("sensor_temperature", unit="Cel", description="Current sensor temperature in degrees Celsius")
    def sensor_temperature(self):
        return self.native.SensorTemperature.getValue()

    @read("sensor_cooling", type="boolean", description="True when the sensor cooler is enabled")
    def sensor_cooling(self):
        return self.native.SensorCooling.getValue()

    @read("temperature_status", type="string", description="Current SDK temperature status symbol")
    def temperature_status(self):
        return self.native.TemperatureStatus.getString()

    @read("temperature_control", type="string",
          description="Current SDK temperature control symbol (the target temperature setting)")
    def temperature_control(self):
        return self.native.TemperatureControl.getString()

    @read("frame_rate", unit="Hz", description="Camera frame rate reported by the SDK")
    def frame_rate(self):
        return self.native.GetFPS()

    @read("overlap", type="boolean", description="True when SDK overlap (overlapped exposure and readout) is on")
    def overlap(self):
        return self.native.Overlap.getValue()

    # -- the one write ------------------------------------------------------------------------------------------
    @write("integration_time", unit="ms",
           description="Integration (exposure) time in milliseconds, written through SetIntegTime",
           limit=Limit.operator_required(
               "no text of the clone states an integration-time range: ExposureTime.min()/max() are runtime "
               "SDK values (daq_2Dviewer_AndorSCMOS.py:462-463), and a constructor default is not a device "
               "bound; the operator supplies the range of the camera"))
    def set_integration_time(self, value):
        self.native.SetIntegTime(value)
        return self.native.GetIntegTime()          # the exposure the SDK stored

    # -- safety -------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: the runtime latches first, then StopAq sends AcquisitionStop if acquiring."""
        self.native.StopAq()
