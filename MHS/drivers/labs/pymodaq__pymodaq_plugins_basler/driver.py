"""OpenMHS driver for gh.pymodaq/pymodaq_plugins_basler: a Basler camera through pypylon.

A direct Driver over ``pymodaq_plugins_basler.hardware.basler:BaslerCamera``, the class the PyMoDAQ plugin uses
for every camera operation (README.rst:17).  The class wraps one ``pylon.InstantCamera`` and reads and writes the
camera features through the pylon nodes; the DAQ viewer drives those nodes directly, while this package calls the
methods of the native class itself.

* reads: the model name, the detector size, the six values of the current ROI (x0, x1, y0, y1 and the two binning
  factors), exposure in milliseconds, gain, frame rate, pixel format and the grabbing state;
* writes: the six ROI values.  The native class has no setter method for exposure or gain (the viewer writes the
  pylon nodes directly, daq_2Dviewer_Basler.py:243-245), so those two settings are read-only here.  Every ROI value
  is ``Limit.operator_required``: no text file of the clone states the usable range of an installed camera, the
  pylon nodes report their minimum and maximum only at run time (daq_2Dviewer_Basler.py:571-582), and the sensor
  size differs by model (README.rst:21).  Every write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site
  supplies the range of its camera (``site-limits.example.json`` shows the overlay);
* actions: start and stop continuous acquisition (``start_grabbing`` and ``stop_grabbing``), and clear the ROI and
  binning back to the full detector (the viewer's "Clear ROI+Bin", daq_2Dviewer_Basler.py:272-278);
* the native ``stop_grabbing`` (``StopGrabbing``, hardware/basler.py:207-209) is the e-stop and the safe-state
  action.

The image arrays the camera produces are not carried: the standard's image form is an artifact reference and this
package has no artifact store, so no image capability is bound (see RESULT.json notes).

Every Fact cites a line of the clone at the pinned commit (2bb80b0f2f1f904675065ff432302b885389ee99).  This
package is model-authored and unreviewed.  The acceptance gate runs the fake backend only and nothing in this
package ran on a camera.  The package is R1, so the loader's refusal of an unreviewed model-written hardware
backend (which applies at R2 and R3) does not apply here; do not read this file as a hardware-run claim.
"""

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read, write

ROI_REASON = (
    "no text file of the clone states the usable ROI range of an installed camera: the pylon nodes report their "
    "minimum and maximum only at run time (daq_2Dviewer_Basler.py:571-582), the sensor size differs by model "
    "(README.rst:21), and the site supplies the range of its camera")


class Basler(Driver):
    device_id = "basler"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = "pymodaq_plugins_basler.hardware.basler:BaslerCamera"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeBaslerCamera"}
    vendor, model = "Basler", "Basler camera through pypylon (pymodaq_plugins_basler)"
    display_name = "Basler camera (pymodaq_plugins_basler.hardware.basler:BaslerCamera)"
    tags = ["camera", "basler", "pypylon", "imaging", "roi"]
    facts = [
        Fact("BaslerCamera is the PyMoDAQ plugin's camera class and wraps one pylon.InstantCamera",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:41-57"),
        Fact("open() attaches the pylon device, opens it and reads the per-model attribute configuration",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:91-102"),
        Fact("get_roi returns x0, x0+width, y0, y0+height, xbin and ybin from the pylon OffsetX, Width, OffsetY, "
             "Height, BinningHorizontal and BinningVertical nodes",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:141-149"),
        Fact("set_roi clamps the start and end coordinates to the detector size, aligns each start to Width.Inc "
             "and writes OffsetX, Width, OffsetY, Height, BinningHorizontal and BinningVertical",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:151-167"),
        Fact("detector_clamp bounds a coordinate to 0 and the detector extent",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:543-545"),
        Fact("get_detector_size returns the SensorWidth and SensorHeight pylon nodes in pixels",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:169-171"),
        Fact("start_grabbing writes AcquisitionFrameRate when a rate is given and starts grabbing with "
             "GrabStrategy_LatestImageOnly; stop_grabbing calls StopGrabbing",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:193-209"),
        Fact("check_attribute_names looks for ExposureTime, ExposureTimeAbs or ExposureTimeRaw and for Gain, "
             "GainRaw or GainAll",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:267-296"),
        Fact("close closes and detaches the pylon camera",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:189-191"),
        Fact("list_cameras enumerates the pylon devices from the transport-layer factory",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/hardware/basler.py:120-124"),
        Fact("The DAQ viewer writes an exposure setting to the pylon node as int(value * 1e3), milliseconds to "
             "microseconds",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:185-190"),
        Fact("The DAQ viewer reads an exposure value from the pylon node in microseconds and multiplies it by "
             "1e-3 for the GUI",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:564-579"),
        Fact("The DAQ viewer reads the pylon node minimum and maximum with GetMin() and GetMax(), so the usable "
             "range is reported by the camera at run time",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:571-582"),
        Fact("The DAQ viewer changes the ROI through set_roi with hstart, hend=hstart+width, vstart, "
             "vend=vstart+height and the two binning factors",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:322-331"),
        Fact("The DAQ viewer calls setup_acquisition when the camera is initialised",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:86-91"),
        Fact("The DAQ viewer starts grabbing with the configured frame rate or with None when the model has no "
             "frame-rate parameter",
             source="upstream_code",
             ref="src/pymodaq_plugins_basler/daq_viewer_plugins/plugins_2D/daq_2Dviewer_Basler.py:338-346"),
        Fact("The README says the plugin handles gain, exposure and ROI and uses the pypylon library",
             source="vendor_doc", ref="README.rst:17"),
        Fact("The README names the acA640-120gm, acA1920-40gm and puA1600-60um models as those the plugin was "
             "tested with",
             source="vendor_doc", ref="README.rst:21"),
        Fact("The README says the config file names are pylon API feature names such as ExposureTime or GainRaw "
             "and that a config file is needed per camera model",
             source="vendor_doc", ref="README.rst:23-26"),
    ]
    safe_state = ("camera acquisition stopped (the native stop_grabbing); exposure and ROI stay configured and the "
                  "camera stays open")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("model_name", type="string", description="Camera model name the pylon device reports")
    def model_name(self):
        return str(self.native.model_name)

    @read("detector_size", type="array", items="integer", length=2,
          description="Detector size as [width, height] in pixels (get_detector_size)")
    def detector_size(self):
        width, height = self.native.get_detector_size()
        return [int(width), int(height)]

    @read("roi_x0", type="integer", unit="1",
          description="Horizontal ROI start in pixels (OffsetX, the first value of get_roi)")
    def roi_x0(self):
        return int(self.native.get_roi()[0])

    @read("roi_x1", type="integer", unit="1",
          description="Horizontal ROI end in pixels (x0 + Width, the second value of get_roi)")
    def roi_x1(self):
        return int(self.native.get_roi()[1])

    @read("roi_y0", type="integer", unit="1",
          description="Vertical ROI start in pixels (OffsetY, the third value of get_roi)")
    def roi_y0(self):
        return int(self.native.get_roi()[2])

    @read("roi_y1", type="integer", unit="1",
          description="Vertical ROI end in pixels (y0 + Height, the fourth value of get_roi)")
    def roi_y1(self):
        return int(self.native.get_roi()[3])

    @read("binning_x", type="integer", unit="1",
          description="Horizontal binning factor (BinningHorizontal, the fifth value of get_roi)")
    def binning_x(self):
        return int(self.native.get_roi()[4])

    @read("binning_y", type="integer", unit="1",
          description="Vertical binning factor (BinningVertical, the sixth value of get_roi)")
    def binning_y(self):
        return int(self.native.get_roi()[5])

    @read("exposure_ms", unit="ms", native_unit="us",
          description="Exposure time in milliseconds; the pylon node reports microseconds")
    def exposure_ms(self):
        exposure, _gain, _raw = self.native.check_attribute_names()
        return float(getattr(self.native.camera, exposure).GetValue())

    @read("gain", unit="1", description="Gain in the native scale of the pylon gain node")
    def gain(self):
        _exposure, gain, _raw = self.native.check_attribute_names()
        return float(getattr(self.native.camera, gain).GetValue())

    @read("frame_rate", unit="/s", description="Acquisition frame rate in frames per second")
    def frame_rate(self):
        return float(self.native.camera.AcquisitionFrameRate.GetValue())

    @read("pixel_format", type="string", description="Pixel format the pylon camera reports")
    def pixel_format(self):
        return str(self.native.camera.PixelFormat.GetValue())

    @read("grabbing", type="boolean", description="True while the pylon camera is grabbing")
    def grabbing(self):
        return bool(self.native.camera.IsGrabbing())

    # -- writes: the six ROI values ---------------------------------------------------------------------------
    @write("roi_x0", type="integer", unit="1", description="Horizontal ROI start in pixels (OffsetX)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_x0(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(value), int(x1), int(y0), int(y1), int(xbin), int(ybin))
        return int(self.native.get_roi()[0])

    @write("roi_x1", type="integer", unit="1", description="Horizontal ROI end in pixels (x0 + Width)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_x1(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(x0), int(value), int(y0), int(y1), int(xbin), int(ybin))
        return int(self.native.get_roi()[1])

    @write("roi_y0", type="integer", unit="1", description="Vertical ROI start in pixels (OffsetY)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_y0(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(x0), int(x1), int(value), int(y1), int(xbin), int(ybin))
        return int(self.native.get_roi()[2])

    @write("roi_y1", type="integer", unit="1", description="Vertical ROI end in pixels (y0 + Height)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_y1(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(x0), int(x1), int(y0), int(value), int(xbin), int(ybin))
        return int(self.native.get_roi()[3])

    @write("binning_x", type="integer", unit="1", description="Horizontal binning factor (BinningHorizontal)",
           limit=Limit.operator_required(ROI_REASON))
    def set_binning_x(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(x0), int(x1), int(y0), int(y1), int(value), int(ybin))
        return int(self.native.get_roi()[4])

    @write("binning_y", type="integer", unit="1", description="Vertical binning factor (BinningVertical)",
           limit=Limit.operator_required(ROI_REASON))
    def set_binning_y(self, value):
        x0, x1, y0, y1, xbin, ybin = self.native.get_roi()
        self.native.set_roi(int(x0), int(x1), int(y0), int(y1), int(xbin), int(value))
        return int(self.native.get_roi()[5])

    # -- actions -----------------------------------------------------------------------------------------------
    @action(name="x-cap.pymodaq.start_grabbing.v1",
            description="Start continuous acquisition with the camera's current frame rate (the native "
                        "start_grabbing with None)",
            output={"grabbing": Field("boolean", description="True once the camera reports that it is grabbing")})
    def start_grabbing(self):
        self.native.start_grabbing(None)
        return {"grabbing": bool(self.native.camera.IsGrabbing())}

    @action(name="x-cap.pymodaq.stop_grabbing.v1", safe_state=True,
            description="Stop continuous acquisition (the native stop, the safe state); it takes no input",
            output={"grabbing": Field("boolean", description="False once the camera reports that it has stopped")})
    def stop_grabbing(self):
        self.native.stop_grabbing()
        return {"grabbing": bool(self.native.camera.IsGrabbing())}

    @action(name="x-cap.pymodaq.clear_roi.v1",
            description="Reset the ROI and binning to the full detector (the native set_roi with binning 1)",
            output={"roi": Field("array", items="integer", length=6,
                                 description="[x0, x1, y0, y1, xbin, ybin] after the reset")})
    def clear_roi(self):
        width, height = self.native.get_detector_size()
        self.native.set_roi(0, int(width), 0, int(height), 1, 1)
        return {"roi": [int(value) for value in self.native.get_roi()]}

    # -- safety and lifecycle ----------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop: StopGrabbing through stop_grabbing."""
        self.native.stop_grabbing()

    def setup(self):
        self.native.setup_acquisition()

    def teardown(self):
        self.native.stop_grabbing()
        self.native.close()
