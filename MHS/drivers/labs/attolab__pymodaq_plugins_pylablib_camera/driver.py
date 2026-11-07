"""OpenMHS driver for gh.attolab/pymodaq_plugins_pylablib_camera: a Thorlabs camera through the PyMoDAQ
pylablib viewer class.

A direct Driver (decorated methods) over the upstream viewer class
``pymodaq_plugins_pylablib_camera.daq_viewer_plugins.plugins_2D.daq_2Dviewer_ThorlabsPLL:
DAQ_2DViewer_ThorlabsPLL``.  The class is one of the four concrete PyMoDAQ 2D viewers of the clone; it inherits
the camera handling of ``DAQ_2DViewer_GenericPylablibCamera`` and only names the camera family and opens the
pylablib controller (daq_2Dviewer_ThorlabsPLL.py:17, 24-29).  The viewer keeps that controller in
``self.controller`` and drives it through the pylablib camera API (daq_2Dviewer_GenericPylablibCamera.py:140-147,
153-158, 229-244, 326-330).

* reads: the serial numbers the Thorlabs enumeration reports at import, the camera information string, the
  exposure time in seconds, the detector size in pixels, the four ROI edges and the two binning factors;
* writes: exposure and the six ROI/binning values.  No text file of the clone states a usable exposure or ROI
  range of an installed camera: the viewer's settings (1 ms and ``limits: [1, 2]``) are UI defaults, not bounds a
  camera reports, and the camera model varies.  All seven writes are therefore ``Limit.operator_required``: every
  write is refused ``MHS.SAFETY.LIMITS_UNSET`` until the site supplies the range of its camera
  (``site-limits.example.json`` shows the overlay);
* the viewer's native ``stop`` (``controller.stop_acquisition`` then ``clear_acquisition``,
  daq_2Dviewer_GenericPylablibCamera.py:326-330) is the ``@estop``; the safe state is the stopped acquisition.

The image arrays the viewer produces are emitted from its Qt callback thread and are not carried by this package:
the standard's image form is an artifact reference and this package has no artifact store, so no image capability
is bound (see RESULT.json notes).  The driver serves the camera's scalar state and settings.

Every Fact cites a line of the clone at the pinned commit ff1e71510bc1a4b07a700034d37f74a5e916abf8.  This package
is model-authored and unreviewed: the acceptance gate runs the fake backend only, nothing in this package ran on a
camera, and the package is R1 (so the loader's refusal of an unreviewed model-written hardware backend, which
applies at R2 and R3, does not apply here; do not read this file as a hardware-run claim).
"""

from mhs.driver import Driver, Fact, Limit, estop, read, write

EXPOSURE_REASON = (
    "no text file of the clone states the exposure range of an installed camera: the viewer's 1 ms setting is a UI "
    "default (daq_2Dviewer_GenericPylablibCamera.py:30) and the usable range is reported by the camera at run time; "
    "the site supplies the range of its camera")

ROI_REASON = (
    "no text file of the clone states the usable ROI or binning range of an installed camera: the viewer's "
    "binning limits [1, 2] are UI defaults (daq_2Dviewer_GenericPylablibCamera.py:26), the detector size differs by "
    "model, and the site supplies the range of its camera")


class PylablibCamera(Driver):
    device_id = "pylablib-camera"
    device_kind = "sensor.camera"
    mode = "hardware"
    risk = "R1"
    native = ("pymodaq_plugins_pylablib_camera.daq_viewer_plugins.plugins_2D.daq_2Dviewer_ThorlabsPLL:"
              "DAQ_2DViewer_ThorlabsPLL")
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeThorlabsCamera"}
    vendor, model = "Thorlabs", "Thorlabs camera through the PyMoDAQ pylablib viewer"
    display_name = "Thorlabs camera (pymodaq_plugins_pylablib_camera DAQ_2DViewer_ThorlabsPLL)"
    tags = ["camera", "thorlabs", "pylablib", "imaging", "roi", "binning"]
    facts = [
        Fact("The repository is a generic PyMoDAQ camera plugin meant to be subclassed for a camera through the "
             "pylablib library, and the plugin does not work on its own",
             source="vendor_doc", ref="README.rst:16-19"),
        Fact("The generic viewer handles hardware ROI, hardware binning and frames through a callback",
             source="vendor_doc", ref="README.rst:35"),
        Fact("DAQ_2DViewer_ThorlabsPLL enumerates the Thorlabs serial numbers at import with "
             "Thorlabs.list_cameras_tlcam()", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_ThorlabsPLL.py:17"),
        Fact("DAQ_2DViewer_ThorlabsPLL.init_controller opens Thorlabs.ThorlabsTLCamera with the serial number "
             "selected in settings['camera_list']", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/daq_2Dviewer_ThorlabsPLL.py:24-29"),
        Fact("The viewer keeps the pylablib camera controller in self.controller and reads the camera information "
             "string from controller.get_device_info()[1]", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:140-144"),
        Fact("A change of the exposure setting is written to the controller as param.value()/1000, milliseconds to "
             "seconds", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:61-63"),
        Fact("exposure reads controller.get_exposure() and writes controller.set_exposure(value)",
             source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:114-122"),
        Fact("get_roi returns hstart, hend, vstart, vend, hbin and vbin; the viewer derives the image width and "
             "height from the first four values", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:153-158"),
        Fact("Some pylablib get_roi calls return only four values instead of six and the viewer then assumes a "
             "binning of 1", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:186-190"),
        Fact("update_rois calls controller.set_roi with hstart, hend=hstart+width, vstart, vend=vstart+height and "
             "the two binning factors", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:229-244"),
        Fact("The viewer reads the detector size with controller.get_detector_size() when it clears the ROI",
             source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:97-108"),
        Fact("stop calls controller.stop_acquisition() and then controller.clear_acquisition()",
             source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:326-330"),
        Fact("close closes the pylablib controller with controller.close()", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:315-321"),
        Fact("The viewer's exposure-time setting starts at 1 ms and its binning setting admits [1, 2]; these are UI "
             "defaults of the parameter tree, not bounds reported by a camera", source="upstream_code",
             ref="src/pymodaq_plugins_pylablib_camera/daq_viewer_plugins/plugins_2D/"
                 "daq_2Dviewer_GenericPylablibCamera.py:26-30"),
    ]
    safe_state = ("camera acquisition stopped by the native stop (controller.stop_acquisition then "
                  "clear_acquisition); the exposure and ROI settings stay configured and the camera stays open")

    # -- reads ------------------------------------------------------------------------------------------------
    @read("camera_list", type="array", items="string",
          description="Serial numbers the Thorlabs camera enumeration reports at plugin import")
    def camera_list(self):
        return [str(item) for item in self.native.camera_list]

    @read("camera_info", type="string",
          description="Camera information string the pylablib controller reports")
    def camera_info(self):
        return str(self.native.controller.get_device_info()[1])

    @read("exposure", unit="s", description="Exposure time of the camera in seconds")
    def exposure(self):
        return float(self.native.exposure)

    @read("detector_size", type="array", items="integer", length=2, unit="1",
          description="Detector width and height in pixels")
    def detector_size(self):
        width, height = self.native.controller.get_detector_size()
        return [int(width), int(height)]

    @read("roi_x0", type="integer", unit="1",
          description="Horizontal ROI start in detector pixels (pylablib hstart)")
    def roi_x0(self):
        return int(self.native.controller.get_roi()[0])

    @read("roi_x1", type="integer", unit="1",
          description="Horizontal ROI end in detector pixels (pylablib hend, exclusive)")
    def roi_x1(self):
        return int(self.native.controller.get_roi()[1])

    @read("roi_y0", type="integer", unit="1",
          description="Vertical ROI start in detector pixels (pylablib vstart)")
    def roi_y0(self):
        return int(self.native.controller.get_roi()[2])

    @read("roi_y1", type="integer", unit="1",
          description="Vertical ROI end in detector pixels (pylablib vend, exclusive)")
    def roi_y1(self):
        return int(self.native.controller.get_roi()[3])

    @read("binning_x", type="integer", unit="1",
          description="Horizontal binning factor the camera applies (pylablib hbin)")
    def binning_x(self):
        return int(self.native.controller.get_roi()[4])

    @read("binning_y", type="integer", unit="1",
          description="Vertical binning factor the camera applies (pylablib vbin)")
    def binning_y(self):
        return int(self.native.controller.get_roi()[5])

    # -- writes -----------------------------------------------------------------------------------------------
    @write("exposure", unit="s", description="Exposure time of the camera in seconds",
           limit=Limit.operator_required(EXPOSURE_REASON))
    def set_exposure(self, value):
        self.native.exposure = float(value)
        return float(self.native.exposure)

    @write("roi_x0", type="integer", unit="1",
           description="Horizontal ROI start in detector pixels (pylablib hstart)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_x0(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((int(value), x1 - int(value), xbin, y0, y1 - y0, ybin))
        return self._roi()[0]

    @write("roi_x1", type="integer", unit="1",
           description="Horizontal ROI end in detector pixels (pylablib hend, exclusive)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_x1(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((x0, int(value) - x0, xbin, y0, y1 - y0, ybin))
        return self._roi()[1]

    @write("roi_y0", type="integer", unit="1",
           description="Vertical ROI start in detector pixels (pylablib vstart)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_y0(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((x0, x1 - x0, xbin, int(value), y1 - int(value), ybin))
        return self._roi()[2]

    @write("roi_y1", type="integer", unit="1",
           description="Vertical ROI end in detector pixels (pylablib vend, exclusive)",
           limit=Limit.operator_required(ROI_REASON))
    def set_roi_y1(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((x0, x1 - x0, xbin, y0, int(value) - y0, ybin))
        return self._roi()[3]

    @write("binning_x", type="integer", unit="1",
           description="Horizontal binning factor the camera applies (pylablib hbin)",
           limit=Limit.operator_required(ROI_REASON))
    def set_binning_x(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((x0, x1 - x0, int(value), y0, y1 - y0, ybin))
        return self._roi()[4]

    @write("binning_y", type="integer", unit="1",
           description="Vertical binning factor the camera applies (pylablib vbin)",
           limit=Limit.operator_required(ROI_REASON))
    def set_binning_y(self, value):
        x0, x1, y0, y1, xbin, ybin = self._roi()
        self.native.update_rois((x0, x1 - x0, xbin, y0, y1 - y0, int(value)))
        return self._roi()[5]

    # -- safety ------------------------------------------------------------------------------------------------
    @estop
    def stop(self):
        """The native stop of the viewer: stop and clear the acquisition; the runtime latches first."""
        self.native.stop()

    def teardown(self):
        self.native.close()

    # -- helpers -----------------------------------------------------------------------------------------------
    def _roi(self):
        """The six values controller.get_roi() reports, as integers (hstart, hend, vstart, vend, hbin, vbin).

        Some pylablib cameras return only four values; the viewer then assumes binning 1 (see
        daq_2Dviewer_GenericPylablibCamera.py:188-190).
        """
        values = [int(item) for item in self.native.controller.get_roi()]
        if len(values) == 4:
            values += [1, 1]
        return values
